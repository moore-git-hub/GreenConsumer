"""
run_experiments.py — 实验批量调度入口

遍历 2×2×3=12 个策略组合，顺序执行仿真，汇总结果并生成帕累托分析。

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

from experiment_config import generate_experiment_matrix
from simulation_core import run_simulation_core


# ══════════════════════════════════════════════════════════════════════
# CSV 写入函数
# ══════════════════════════════════════════════════════════════════════

def write_summary_csv(results: list, output_path: str):
    """将所有实验结果写入汇总 CSV（含高区分度指标）"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "exp_id", "content_factor", "channel_factor", "timing_factor",
            "delta_recovery", "auc_post_scandal", "recovery_speed",
            "steady_state_score", "recovery_rate", "t50", "t80",
            "trust_min", "trust_min_tick", "baseline_trust", "clarification_effect",
        ])
        for r in results:
            if "error" in r:
                writer.writerow([r["exp_id"]] + ["ERROR"] * 15)
                continue
            cfg = r["config"]
            m   = r["metrics"]
            writer.writerow([
                r["exp_id"], cfg["content_factor"], cfg["channel_factor"], cfg["timing_factor"],
                m.delta_recovery, m.auc_post_scandal, m.recovery_speed,
                m.steady_state_score, m.recovery_rate, m.t50, m.t80,
                m.trust_min, m.trust_min_tick, m.baseline_trust, m.clarification_effect,
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

async def main():
    print("=" * 60)
    print("🧪 GABM 策略因子化实验 — 批量调度启动")
    print("   实验矩阵: 2(内容) × 2(渠道) × 3(时机) = 12 组")
    print("=" * 60)

    configs = generate_experiment_matrix()
    total   = len(configs)
    results = []
    errors  = []

    for i, config in enumerate(configs, 1):
        print(f"\n{'─'*60}")
        print(f"  [{i}/{total}] 🚀 Running: {config.exp_id}")
        print(f"    Content={config.content_factor} | Channel={config.channel_factor} | Timing={config.timing_factor}")
        print(f"{'─'*60}")
        try:
            result = await run_simulation_core(config)
            results.append(result)
        except Exception as e:
            error_msg = f"{config.exp_id}: {type(e).__name__}: {e}"
            print(f"  ❌ FAILED: {error_msg}")
            errors.append(error_msg)
            results.append({"exp_id": config.exp_id, "error": str(e)})

    # ── 写入输出文件 ─────────────────────────────────────────────────
    results_dir = os.path.join(current_dir, "results", "experiments")
    os.makedirs(results_dir, exist_ok=True)

    summary_path = os.path.join(results_dir, "summary.csv")
    write_summary_csv(results, summary_path)
    print(f"\n📄 汇总表已保存: {summary_path}")

    trajectories_path = os.path.join(results_dir, "trajectories.csv")
    write_trajectories_csv(results, trajectories_path)
    print(f"📈 轨迹数据已保存: {trajectories_path}")

    agent_records_path = os.path.join(results_dir, "agent_records.csv")
    write_agent_records_csv(results, agent_records_path)
    print(f"🧬 逐Agent详细记录已保存: {agent_records_path}")

    # ── 写入错误日志 ─────────────────────────────────────────────────
    if errors:
        error_path = os.path.join(results_dir, "errors.log")
        with open(error_path, "w", encoding="utf-8") as f:
            f.write(f"Experiment Errors — {datetime.datetime.now()}\n")
            f.write("=" * 50 + "\n")
            for err in errors:
                f.write(f"  {err}\n")
        print(f"⚠️ {len(errors)} 次运行失败，详见: {error_path}")

    # ── 可视化（帕累托 + 实验图表）──────────────────────────────────
    successful = [r for r in results if "error" not in r]
    if successful:
        # 帕累托分析
        try:
            from plot_pareto import analyze_and_plot_pareto
            analyze_and_plot_pareto(successful, results_dir)
        except Exception as e:
            print(f"⚠️ 帕累托分析失败（{type(e).__name__}）: {e}")

        # plot_experiments.py 的 5 张实验图
        analysis_dir = os.path.join(current_dir, "analysis")
        if analysis_dir not in sys.path:
            sys.path.insert(0, analysis_dir)
        try:
            import plot_experiments as _pe
            print("\n🎨 生成实验结果图表...")
            df_exp = _pe.load_data()
            _pe.plot_main_effects(df_exp)
            _pe.plot_heatmap_interactions(df_exp)
            df_exp = _pe.plot_pareto_frontier(df_exp)
            _pe.plot_strategy_ranking(df_exp)
            _pe.plot_clarification_diagnosis(df_exp)
            print(f"  → 图表已保存至: {_pe.OUTPUT_DIR}")
        except Exception as e:
            print(f"⚠️ 实验图表生成失败（{type(e).__name__}）: {e}")

    # ── 最终汇总 ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"✅ 实验完成: {len(successful)}/{total} 成功, {len(errors)}/{total} 失败")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
