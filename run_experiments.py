"""
run_experiments.py — 实验批量调度入口

观测目标：单一漂绿事件（Blackstone 丑闻，Tick 5）后，
         12 种企业澄清策略（2×内容 × 2×渠道 × 3×时机）的信任恢复差异。

设计原则：
  1. 单事件控制  — 临时 patch ENTERPRISE_STRATEGY 为仅含 Tick 5 的漂绿事件，
                   屏蔽 Tick 10/15 的后续事件，确保策略效果归因干净。
  2. 路径对齐   — 先跑 no-clarification 对照组并缓存 LLM 响应（RecordingRouter），
                   其余 11 组在澄清 Tick 之前 Replay 同一份缓存，
                   保证 Tick 1~(clarification_tick-1) 的信任轨迹完全一致。
  3. 真实 LLM   — 澄清 Tick 当天及之后走真实 LLM，差异完全由策略内容决定。

用法：
    python run_experiments.py
"""
import sys
import os
import asyncio
import csv
import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from experiment_config import generate_experiment_matrix, ExperimentConfig
from simulation_core import run_simulation_core, ENTERPRISE_STRATEGY


# ══════════════════════════════════════════════════════════════════════
# 单事件 patch：只保留 Tick 5 的 Blackstone 漂绿丑闻
# ══════════════════════════════════════════════════════════════════════
_SINGLE_SCANDAL = {5: ENTERPRISE_STRATEGY[5]}


# ══════════════════════════════════════════════════════════════════════
# Recording / Replay Router（复用 run_clarification_trial 的设计）
# ══════════════════════════════════════════════════════════════════════

class RecordingRouter:
    """记录所有 LLM 调用：(prompt_hash, tick, call_index) → response"""

    def __init__(self, inner_router):
        self._inner = inner_router
        self._cache: dict = {}
        self._current_tick: int = 0
        self._call_counts: dict = {}

    def set_tick(self, tick: int):
        self._current_tick = tick
        self._call_counts = {}

    @staticmethod
    def _pk(prompt: str) -> str:
        return str(hash(prompt[:200]) & 0xFFFFFFFF)

    async def chat(self, prompt: str) -> str:
        pk = self._pk(prompt)
        count = self._call_counts.get(pk, 0)
        self._call_counts[pk] = count + 1
        response = await self._inner.chat(prompt)
        self._cache[(pk, self._current_tick, count)] = response
        return response

    @property
    def cache(self) -> dict:
        return self._cache


class ReplayRouter:
    """在 replay_until_tick 之前回放缓存，之后走真实 LLM"""

    def __init__(self, inner_router, cache: dict, replay_until_tick: int):
        self._inner = inner_router
        self._cache = cache
        self._replay_until = replay_until_tick
        self._current_tick: int = 0
        self._call_counts: dict = {}
        self.miss_count: int = 0

    def set_tick(self, tick: int):
        self._current_tick = tick
        self._call_counts = {}

    async def chat(self, prompt: str) -> str:
        pk = RecordingRouter._pk(prompt)
        count = self._call_counts.get(pk, 0)
        self._call_counts[pk] = count + 1

        if self._current_tick < self._replay_until:
            key = (pk, self._current_tick, count)
            if key in self._cache:
                return self._cache[key]
            self.miss_count += 1
            if self.miss_count <= 3:
                print(f"  ⚠️  [ReplayRouter] cache miss tick={self._current_tick}")
        return await self._inner.chat(prompt)


# ══════════════════════════════════════════════════════════════════════
# CSV 写入函数
# ══════════════════════════════════════════════════════════════════════

def write_summary_csv(results: list, output_path: str):
    """将所有实验结果写入汇总 CSV（含高区分度指标 + 相对对照组的增益）"""

    # 预计算对照组（no-clarification）的基线信任，用于计算相对增益
    # 按渠道分组取对应的 no-clr 基线（hub vs random 的基线不同）
    ctrl_baseline: dict = {}   # channel → final_trust
    for r in results:
        if "error" in r:
            continue
        if r["config"].get("timing_factor") == "no-clarification":
            channel = r["config"].get("channel_factor", "hub")
            final_trust = r["trust_trajectory"][-1] if r.get("trust_trajectory") else 0.0
            ctrl_baseline[channel] = round(final_trust, 4)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "exp_id", "content_factor", "channel_factor", "timing_factor",
            "delta_recovery", "auc_post_scandal", "recovery_speed",
            "steady_state_score", "recovery_rate", "t50", "t80",
            "trust_min", "trust_min_tick", "baseline_trust", "clarification_effect",
            # 新增：相对对照组的净信任增益（同渠道 no-clr 为基线）
            "trust_gain_vs_control",
        ])
        for r in results:
            if "error" in r:
                writer.writerow([r["exp_id"]] + ["ERROR"] * 16)
                continue
            cfg = r["config"]
            m   = r["metrics"]

            # 计算相对对照组的净增益
            channel = cfg["channel_factor"]
            final_trust = r["trust_trajectory"][-1] if r.get("trust_trajectory") else 0.0
            ctrl_final  = ctrl_baseline.get(channel, final_trust)
            trust_gain  = round(final_trust - ctrl_final, 4)

            writer.writerow([
                r["exp_id"], cfg["content_factor"], cfg["channel_factor"], cfg["timing_factor"],
                m.delta_recovery, m.auc_post_scandal, m.recovery_speed,
                m.steady_state_score, m.recovery_rate, m.t50, m.t80,
                m.trust_min, m.trust_min_tick, m.baseline_trust, m.clarification_effect,
                trust_gain,
            ])


def write_trajectories_csv(results: list, output_path: str):
    """将所有实验的逐 Tick 轨迹写入 CSV（供折线图使用）"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "exp_id", "content_factor", "channel_factor", "timing_factor",
            "tick", "avg_trust", "conversion_rate",
        ])
        for r in results:
            if "error" in r:
                continue
            cfg        = r["config"]
            trust_traj = r.get("trust_trajectory", [])
            conv_traj  = r.get("conversion_trajectory", [])
            for tick_idx, (trust, conv) in enumerate(zip(trust_traj, conv_traj), start=1):
                writer.writerow([
                    r["exp_id"], cfg["content_factor"], cfg["channel_factor"], cfg["timing_factor"],
                    tick_idx, round(trust, 4), round(conv, 4),
                ])


def write_agent_records_csv(results: list, output_path: str):
    """将所有实验的逐 Agent 逐 Tick 详细记录写入 CSV（供后续统计分析使用）"""
    fieldnames = [
        "exp_id", "tick", "agent_id", "cluster_type", "social_role",
        "trust_score", "baseline_trust", "trust_after_decay",
        "affective_change", "shock_anchor", "quiet_ticks", "decay_lambda",
        "is_buying", "is_posting", "post_content",
        "hypocrisy_perceived", "importance", "reasoning",
        "has_global_event", "has_clarification", "cumulative_buyers",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            if "error" in r or "agent_records" not in r:
                continue
            for rec in r["agent_records"]:
                writer.writerow(rec)


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

async def _run_with_patch(config: ExperimentConfig, override_router=None) -> dict:
    """
    在单事件策略下运行一组实验。
    临时 patch ENTERPRISE_STRATEGY → 只保留 Tick 5 漂绿丑闻。
    """
    import simulation_core as _sc
    original = _sc.ENTERPRISE_STRATEGY.copy()
    _sc.ENTERPRISE_STRATEGY.clear()
    _sc.ENTERPRISE_STRATEGY.update(_SINGLE_SCANDAL)
    try:
        return await run_simulation_core(config, override_router=override_router)
    finally:
        _sc.ENTERPRISE_STRATEGY.clear()
        _sc.ENTERPRISE_STRATEGY.update(original)


async def main():
    print("=" * 65)
    print("🧪 GABM 批量实验 — 单一漂绿事件 × 12 种澄清策略")
    print("   Scandal : Tick 5 (Blackstone 丑闻，其余事件屏蔽)")
    print("   矩阵    : 2(内容) × 2(渠道) × 3(时机) = 12 组")
    print("   对齐    : 澄清前路径 Replay 对照组 LLM 响应，消除采样噪声")
    print("=" * 65)

    configs = generate_experiment_matrix()
    total   = len(configs)

    # ── 执行顺序设计 ─────────────────────────────────────────────────
    # 1. 先跑单一 no-clarification 基线（hub+rational），录制全局 LLM 缓存
    # 2. 其余 11 组（含另外 3 个 no-clr）全部 replay 该缓存到 clarification_tick 前，
    #    保证所有实验在澄清注入前路径完全一致，差异仅来自策略本身
    baseline_config = next(
        c for c in configs
        if c.timing_factor == "no-clarification"
        and c.channel_factor == "hub"
        and c.content_factor == "rational-evidence"
    )
    other_configs = [c for c in configs if c != baseline_config]
    ordered_configs = [baseline_config] + other_configs

    # ── 获取真实 Router ───────────────────────────────────────────────
    import yaml
    try:
        with open(os.path.join(current_dir, "configs/models_config.yaml"), "r") as f:
            _models_conf = yaml.safe_load(f)
        from agentkernel_standalone.toolkit.models.router import ModelRouter, AsyncModelRouter
        _real_router = ModelRouter(AsyncModelRouter(_models_conf))
        print("🧠 LLM 引擎已就绪")
    except Exception:
        import json as _json
        class _MockInner:
            async def chat(self, prompt: str) -> str:
                if "trust_change_affective" in prompt or "hypocrisy_perceived" in prompt:
                    return _json.dumps({"hypocrisy_perceived": True,
                                        "trust_change_affective": -1.5,
                                        "importance": 7.0,
                                        "reasoning": "Mock: betrayed."})
                return _json.dumps({"is_buying": False, "is_posting": True,
                                    "post_content": "Upset about this.", "reason": "Mock."})
        _real_router = _MockInner()
        print("⚠️  使用 Mock Router")

    results = []
    errors  = []
    llm_cache: dict = {}   # 对照组建立后填入

    for i, config in enumerate(ordered_configs, 1):
        is_baseline = (config == baseline_config)

        print(f"\n{'─'*65}")
        print(f"  [{i}/{total}] 🚀 {config.exp_id}")
        print(f"    Content={config.content_factor} | Channel={config.channel_factor} "
              f"| Timing={config.timing_factor}"
              + (" [RECORDING — baseline]" if is_baseline else
                 f" [REPLAY until T{config.clarification_tick}]" if config.clarification_tick
                 else f" [REPLAY full — no clarification]"))
        print(f"{'─'*65}")

        try:
            if is_baseline:
                # ── 唯一的录制组：建立全局 LLM 缓存 ────────────────────
                rec_router = RecordingRouter(_real_router)
                result = await _run_with_patch(config, override_router=rec_router)
                llm_cache.update(rec_router.cache)
                print(f"  📼 全局缓存已建立: {len(llm_cache)} 条 LLM 响应")
            else:
                # ── 其余 11 组（含另外 3 个 NoClr）：全程 Replay 到 clr_tick 前 ──
                # no-clarification 组没有澄清，replay_until_tick=total_ticks+1 意味着全程回放
                clr_tick = config.clarification_tick if config.clarification_tick else config.total_ticks + 1
                rp_router = ReplayRouter(_real_router, llm_cache, replay_until_tick=clr_tick)
                result = await _run_with_patch(config, override_router=rp_router)
                if rp_router.miss_count > 0:
                    print(f"  ⚠️  ReplayRouter cache miss: {rp_router.miss_count} 次")

            results.append(result)

        except Exception as e:
            import traceback
            error_msg = f"{config.exp_id}: {type(e).__name__}: {e}"
            print(f"  ❌ FAILED: {error_msg}")
            traceback.print_exc()
            errors.append(error_msg)
            results.append({"exp_id": config.exp_id, "error": str(e)})

    # ── 写入输出文件 ─────────────────────────────────────────────────
    # 每次运行创建独立的带时间戳子目录，避免覆盖历史结果
    # latest/ 目录始终指向最新一次运行，供可视化脚本直接读取
    timestamp  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir   = os.path.join(current_dir, "results", "experiments")
    run_dir    = os.path.join(base_dir, f"run_{timestamp}")
    latest_dir = os.path.join(base_dir, "latest")
    os.makedirs(run_dir,    exist_ok=True)
    os.makedirs(latest_dir, exist_ok=True)

    summary_path = os.path.join(run_dir, "summary.csv")
    write_summary_csv(results, summary_path)
    print(f"\n📄 汇总表: {summary_path}")

    trajectories_path = os.path.join(run_dir, "trajectories.csv")
    write_trajectories_csv(results, trajectories_path)
    print(f"📈 轨迹数据: {trajectories_path}")

    agent_records_path = os.path.join(run_dir, "agent_records.csv")
    write_agent_records_csv(results, agent_records_path)
    print(f"🧬 逐Agent记录: {agent_records_path}")

    # ── 写入错误日志 ─────────────────────────────────────────────────
    if errors:
        error_path = os.path.join(run_dir, "errors.log")
        with open(error_path, "w", encoding="utf-8") as f:
            f.write(f"Experiment Errors — {datetime.datetime.now()}\n")
            f.write("=" * 50 + "\n")
            for err in errors:
                f.write(f"  {err}\n")
        print(f"⚠️ {len(errors)} 次运行失败，详见: {error_path}")

    # ── 更新 latest/ 目录 ────────────────────────────────────────────
    import shutil
    for fname in ("summary.csv", "trajectories.csv", "agent_records.csv"):
        src = os.path.join(run_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(latest_dir, fname))
    with open(os.path.join(latest_dir, "run_info.txt"), "w", encoding="utf-8") as f:
        f.write(f"run_id   : {timestamp}\n")
        f.write(f"run_dir  : {run_dir}\n")
        f.write(f"generated: {datetime.datetime.now()}\n")
        f.write(f"success  : {len([r for r in results if 'error' not in r])}/{total}\n")
    print(f"📁 本次结果目录 : {run_dir}")
    print(f"🔗 最新结果快照 : {latest_dir}  (可视化脚本读此目录)")

    # results_dir 供后续可视化使用（指向 latest）
    results_dir = latest_dir

    # ── 可视化 ────────────────────────────────────────────────────────
    successful = [r for r in results if "error" not in r]
    if successful:
        try:
            from plot_pareto import analyze_and_plot_pareto
            analyze_and_plot_pareto(successful, results_dir)
        except Exception as e:
            print(f"⚠️ 帕累托分析失败: {e}")

        analysis_dir = os.path.join(current_dir, "analysis")
        if analysis_dir not in sys.path:
            sys.path.insert(0, analysis_dir)
        try:
            import plot_experiments as _pe
            import plot_trajectories as _pt_traj
            import shutil as _shutil
            # 图像输出到本次 run_dir（带时间戳），历史图像永久保留
            run_figures_dir = os.path.join(run_dir, "figures")
            os.makedirs(run_figures_dir, exist_ok=True)
            _pe.OUTPUT_DIR     = run_figures_dir
            _pe.RESULTS_DIR    = run_dir
            _pt_traj.OUTPUT_DIR  = run_figures_dir
            _pt_traj.RESULTS_DIR = run_dir
            print("\n🎨 生成实验结果图表...")
            df_exp = _pe.load_data()
            _pe.plot_main_effects(df_exp)
            _pe.plot_heatmap_interactions(df_exp)
            df_exp = _pe.plot_pareto_frontier(df_exp)
            _pe.plot_strategy_ranking(df_exp)
            _pe.plot_clarification_diagnosis(df_exp)
            df_traj = _pt_traj.load_trajectories()
            _pt_traj.plot_timing_effect(df_traj)
            _pt_traj.plot_content_channel(df_traj)
            _pt_traj.plot_all_12_strategies(df_traj)
            _pt_traj.plot_trust_recovery_zoom(df_traj)
            # 同步到 latest/figures/（方便快速查看最新图像，但历史图在 run_dir 里永久保存）
            latest_figures = os.path.join(latest_dir, "figures")
            if os.path.exists(latest_figures):
                _shutil.rmtree(latest_figures)
            _shutil.copytree(run_figures_dir, latest_figures)
            print(f"  → 本次图表: {run_figures_dir}")
            print(f"  → 最新快照: {latest_figures}")
        except Exception as e:
            print(f"⚠️ 实验图表生成失败（{type(e).__name__}）: {e}")

    # ── 最终汇总 ─────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"✅ 实验完成: {len(successful)}/{total} 成功, {len(errors)}/{total} 失败")
    print(f"   结果目录: {results_dir}")
    print(f"{'='*65}")


if __name__ == "__main__":
    asyncio.run(main())
