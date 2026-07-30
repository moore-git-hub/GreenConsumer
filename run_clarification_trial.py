"""
run_clarification_trial.py — 澄清策略对照实验

实验设计（单一漂绿事件，屏蔽后续多事件）：
  - Tick 5：Blackstone 漂绿丑闻（唯一全局事件）
  - 三组平行仿真，相同 Agent / 相同 seed：
      1. 对照组          — 不澄清
      2. 澄清组-理性证据  — Tick 8 注入（rational-evidence），全员接收
      3. 澄清组-情感共情  — Tick 8 注入（emotional-empathy），全员接收

核心创新：
  - 复用 simulation_core.run_simulation_core，通过自定义 ExperimentConfig
    + 修补 ENTERPRISE_STRATEGY 实现单事件控制，无需重复 Agent 初始化代码
  - 所有数据（thoughts CSV / metrics / trajectories）在 results/trial/ 下

用法：
    python run_clarification_trial.py

输出（results/trial/）：
    trial_thoughts_<ts>.csv         — 逐 Tick 逐 Agent 完整记录
    trial_agent_records_<ts>.csv    — simulation_core 返回的详细 agent_records
    trial_summary_<ts>.txt          — 量化摘要（信任差值 + 核心指标）
    trial_trajectories_<ts>.csv     — 逐 Tick 均值轨迹（3组 × 20 Tick）
    figures/                        — 6 张可视化图（由 plot_trial.py 生成）
"""
import sys
import os
import asyncio
import csv
import json
import datetime
import logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
standalone_path = os.path.join(project_root, "packages", "agentkernel-standalone")
if os.path.exists(standalone_path) and standalone_path not in sys.path:
    sys.path.insert(0, standalone_path)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

logging.getLogger("agentkernel_standalone").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from experiment_config import ExperimentConfig
from simulation_core import run_simulation_core, ENTERPRISE_STRATEGY
from clarification_injector import CONTENT_TEMPLATES

# ══════════════════════════════════════════════════════════════════════
# 实验参数
# ══════════════════════════════════════════════════════════════════════
TRIAL_PARAMS = dict(
    num_agents   = 10,
    total_ticks  = 20,    # 丑闻后有足够的观察窗口
    scandal_tick = 5,
    random_seed  = 42,
    budget_k     = 10,    # 全员接收澄清
)

CLARIFICATION_TICK = 8    # scandal_tick + 3（丑闻后第 3 天）
CONTENT_TYPES = ["rational-evidence", "emotional-empathy"]

# 单事件策略：只保留 Tick 5 的 Blackstone 丑闻
_SINGLE_SCANDAL = {5: ENTERPRISE_STRATEGY[5]}

# 样式常量
CLUSTER_COLORS = {
    "Active_Greens":     "#2166ac",
    "Convenient_Greens": "#4dac26",
    "Dormant_Greens":    "#f46d43",
    "Non_Greens":        "#999999",
}
CLUSTER_LABELS = {
    "Active_Greens":     "Active Greens",
    "Convenient_Greens": "Convenient Greens",
    "Dormant_Greens":    "Dormant Greens",
    "Non_Greens":        "Non-Greens",
}
CLUSTER_ORDER = ["Active_Greens", "Convenient_Greens", "Dormant_Greens", "Non_Greens"]


# ══════════════════════════════════════════════════════════════════════
# Recording / Replay Router
# ══════════════════════════════════════════════════════════════════════

class RecordingRouter:
    """包装真实 Router，记录每次 (prompt_hash, tick, call_index) → response"""

    def __init__(self, inner_router):
        self._inner = inner_router
        self._cache: dict = {}
        self._current_tick: int = 0
        self._call_counts: dict = {}

    def set_tick(self, tick: int):
        self._current_tick = tick
        self._call_counts = {}

    @staticmethod
    def _key_from_prompt(prompt: str) -> str:
        return str(hash(prompt[:200]) & 0xFFFFFFFF)

    async def chat(self, prompt: str) -> str:
        pk = self._key_from_prompt(prompt)
        count = self._call_counts.get(pk, 0)
        self._call_counts[pk] = count + 1
        response = await self._inner.chat(prompt)
        self._cache[(pk, self._current_tick, count)] = response
        return response

    @property
    def cache(self) -> dict:
        return self._cache


class ReplayRouter:
    """在 clarification_tick 之前回放缓存，之后走真实 LLM"""

    def __init__(self, inner_router, cache: dict, replay_until_tick: int):
        self._inner = inner_router
        self._cache = cache
        self._replay_until = replay_until_tick
        self._current_tick: int = 0
        self._call_counts: dict = {}
        self._miss_count: int = 0

    def set_tick(self, tick: int):
        self._current_tick = tick
        self._call_counts = {}

    async def chat(self, prompt: str) -> str:
        pk = RecordingRouter._key_from_prompt(prompt)
        count = self._call_counts.get(pk, 0)
        self._call_counts[pk] = count + 1

        if self._current_tick < self._replay_until:
            key = (pk, self._current_tick, count)
            if key in self._cache:
                return self._cache[key]
            self._miss_count += 1
            if self._miss_count <= 5:
                print(f"  ⚠️  [ReplayRouter] cache miss tick={self._current_tick}")
        return await self._inner.chat(prompt)


# ══════════════════════════════════════════════════════════════════════
# 核心：patch ENTERPRISE_STRATEGY 后复用 simulation_core
# ══════════════════════════════════════════════════════════════════════

async def run_trial_group(
    timing_factor: str,
    content_factor: str,
    output_dir: str,
    thought_writer,
    override_router=None,
) -> dict:
    """
    运行单组实验。

    通过临时替换 simulation_core.ENTERPRISE_STRATEGY 为单事件版本，
    复用完整的 run_simulation_core 管线。

    Args:
        override_router: 可选 RecordingRouter 或 ReplayRouter，实现组间路径对齐。
                         为 None 时使用 simulation_core 内部默认 router。
    """
    import simulation_core as _sc

    original_strategy = _sc.ENTERPRISE_STRATEGY.copy()
    _sc.ENTERPRISE_STRATEGY.clear()
    _sc.ENTERPRISE_STRATEGY.update(_SINGLE_SCANDAL)

    try:
        config = ExperimentConfig(
            content_factor=content_factor,
            channel_factor="hub",
            timing_factor=timing_factor,
            budget_k=TRIAL_PARAMS["budget_k"],
            random_seed=TRIAL_PARAMS["random_seed"],
            num_agents=TRIAL_PARAMS["num_agents"],
            total_ticks=TRIAL_PARAMS["total_ticks"],
            scandal_tick=TRIAL_PARAMS["scandal_tick"],
        )
        result = await run_simulation_core(config, override_router=override_router)
    finally:
        _sc.ENTERPRISE_STRATEGY.clear()
        _sc.ENTERPRISE_STRATEGY.update(original_strategy)

    if timing_factor == "no-clarification":
        group_label = "Control (No-Clr)"
    elif content_factor == "rational-evidence":
        group_label = f"Rational (T{config.clarification_tick})"
    else:
        group_label = f"Empathy (T{config.clarification_tick})"

    result["group_label"]   = group_label
    result["content_factor"] = content_factor

    if thought_writer and "agent_records" in result:
        for rec in result["agent_records"]:
            thought_writer.writerow([
                group_label,
                rec["tick"], rec["agent_id"], rec["cluster_type"],
                rec["trust_score"], rec["trust_after_decay"],
                rec["affective_change"], rec["shock_anchor"],
                rec["quiet_ticks"],
                rec["hypocrisy_perceived"], rec["importance"],
                rec["reasoning"][:300] if rec["reasoning"] else "",
                rec["post_content"][:200] if rec["post_content"] else "",
                rec["is_buying"], rec["is_posting"],
                rec["has_clarification"],
            ])

    return result


# ══════════════════════════════════════════════════════════════════════
# 数据导出
# ══════════════════════════════════════════════════════════════════════

def write_trajectories_csv(all_results: list, output_path: str):
    """逐 Tick 均值轨迹（3 组 × total_ticks 行）"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["group", "tick", "avg_trust", "conversion_rate"])
        for r in all_results:
            lbl = r["group_label"]
            for t_idx, (trust, conv) in enumerate(
                zip(r["trust_trajectory"], r["conversion_trajectory"]), start=1
            ):
                writer.writerow([lbl, t_idx, round(trust, 4), round(conv, 4)])


def write_agent_records_csv(all_results: list, output_path: str):
    """逐 Agent 逐 Tick 完整快照（所有组合并）"""
    fieldnames = [
        "group", "tick", "agent_id", "cluster_type", "social_role",
        "trust_score", "baseline_trust", "trust_after_decay",
        "affective_change", "shock_anchor", "quiet_ticks", "decay_lambda",
        "is_buying", "is_posting", "post_content",
        "hypocrisy_perceived", "importance", "reasoning",
        "has_global_event", "has_clarification", "cumulative_buyers",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            for rec in r.get("agent_records", []):
                row = {k: rec.get(k, "") for k in fieldnames}
                row["group"] = r["group_label"]
                writer.writerow(row)


def write_summary_txt(all_results: list, output_path: str):
    """文字摘要：信任轨迹表 + 澄清效果 Δ"""
    control = next((r for r in all_results if "No-Clr" in r["group_label"]), None)
    clr_list = [r for r in all_results if "No-Clr" not in r["group_label"]]
    total_ticks = TRIAL_PARAMS["total_ticks"]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("CLARIFICATION TRIAL — SUMMARY REPORT\n")
        f.write(f"Generated : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Scandal Tick     : {TRIAL_PARAMS['scandal_tick']}\n")
        f.write(f"Clarification    : Tick {CLARIFICATION_TICK}\n")
        f.write(f"Num Agents       : {TRIAL_PARAMS['num_agents']}\n")
        f.write(f"Total Ticks      : {total_ticks}\n\n")

        # ── 信任轨迹表 ─────────────────────────────────────────────
        all_labels = [r["group_label"] for r in all_results]
        header = f"{'Tick':<6}" + "".join(f"{lbl[:22]:>24}" for lbl in all_labels)
        f.write("── Trust Trajectory ──\n")
        f.write(header + "\n" + "─" * len(header) + "\n")
        for t_idx in range(total_ticks):
            row = f"{t_idx + 1:<6}"
            for r in all_results:
                row += f"{r['trust_trajectory'][t_idx]:>24.4f}"
            f.write(row + "\n")

        # ── 澄清效果 Δ ─────────────────────────────────────────────
        if control and clr_list:
            f.write("\n── Clarification Effect (Δ vs Control) ──\n")
            for r in clr_list:
                f.write(f"\n  {r['group_label']}:\n")
                start = CLARIFICATION_TICK - 1
                end   = min(total_ticks, CLARIFICATION_TICK + 4)
                for t_idx in range(start, end):
                    delta = r["trust_trajectory"][t_idx] - control["trust_trajectory"][t_idx]
                    f.write(
                        f"    Tick {t_idx+1:2d}: clr={r['trust_trajectory'][t_idx]:.4f}"
                        f"  ctrl={control['trust_trajectory'][t_idx]:.4f}"
                        f"  Δ={delta:+.4f}\n"
                    )

        # ── 核心指标汇总 ────────────────────────────────────────────
        f.write("\n── Core Metrics ──\n")
        f.write(f"{'Group':<30} {'ΔRecov':>10} {'AUC':>10} {'Speed':>10} {'Steady':>10}\n")
        f.write("─" * 62 + "\n")
        for r in all_results:
            m = r["metrics"]
            f.write(
                f"{r['group_label']:<30}"
                f"{m.delta_recovery:>10.4f}"
                f"{m.auc_post_scandal:>10.4f}"
                f"{m.recovery_speed:>10.4f}"
                f"{m.steady_state_score:>10.3f}\n"
            )


# ══════════════════════════════════════════════════════════════════════
# 可视化（内嵌版，不依赖 plot_trial.py，避免循环导入）
# ══════════════════════════════════════════════════════════════════════

def _gc(grp: str) -> str:
    if "No-Clr" in grp:  return "#d62728"
    if "Rational" in grp: return "#2166ac"
    return "#e6550d"


def _gls(grp: str) -> str:
    return "--" if "No-Clr" in grp else "-"


def plot_trust_trajectories(all_results: list, output_dir: str, timestamp: str):
    """图1：信任轨迹对比（全员均值 + 按人群 2×2）"""
    scandal_tick = TRIAL_PARAMS["scandal_tick"]
    groups       = [r["group_label"] for r in all_results]
    total_ticks  = TRIAL_PARAMS["total_ticks"]
    ticks        = list(range(1, total_ticks + 1))

    control   = next((r for r in all_results if "No-Clr" in r["group_label"]), None)
    clr_list  = [r for r in all_results if "No-Clr" not in r["group_label"]]
    n_clr     = len(clr_list)
    fig       = plt.figure(figsize=(14, 4.5 + 4.5 * n_clr))
    gs        = gridspec.GridSpec(1 + n_clr, 2, figure=fig, hspace=0.45, wspace=0.3)

    def _vlines(ax):
        ylim = ax.get_ylim()
        span = ylim[1] - ylim[0]
        ax.axvline(scandal_tick, color="#d62728", ls="--", lw=1.5, alpha=0.7)
        ax.text(scandal_tick + 0.2, ylim[0] + span * 0.04,
                "Scandal", color="#d62728", fontsize=8, va="bottom")
        ax.axvspan(CLARIFICATION_TICK - 0.45, CLARIFICATION_TICK + 0.45,
                   alpha=0.10, color="#2ca02c")
        ax.text(CLARIFICATION_TICK + 0.2, ylim[0] + span * 0.55,
                f"Clr (T{CLARIFICATION_TICK})", color="#2ca02c", fontsize=8)

    # ── 行0：全员均值 ─────────────────────────────────────────────────
    ax0 = fig.add_subplot(gs[0, :])
    for r in all_results:
        ax0.plot(ticks, r["trust_trajectory"],
                 color=_gc(r["group_label"]), ls=_gls(r["group_label"]),
                 lw=2.5, marker="o", ms=4, label=r["group_label"])
    ax0.set_ylim(bottom=0)
    _vlines(ax0)
    ax0.set_title("Average Trust Score — All Groups", fontsize=13, fontweight="bold")
    ax0.set_xlabel("Tick"); ax0.set_ylabel("Avg Trust (0–10)")
    ax0.legend(fontsize=9, loc="lower right"); ax0.grid(True, ls=":", alpha=0.4)
    ax0.set_xticks(ticks[::2])

    # ── 行1+：按人群 ──────────────────────────────────────────────────
    for ri, clr_r in enumerate(clr_list):
        for ci, (src, title) in enumerate([
            (clr_r, clr_r["group_label"]),
            (control, "Control (No-Clr)"),
        ]):
            if src is None:
                continue
            ax = fig.add_subplot(gs[ri + 1, ci])
            # 从 agent_records 重建按人群轨迹
            recs_df = pd.DataFrame(src.get("agent_records", []))
            for cluster in CLUSTER_ORDER:
                meta = CLUSTER_COLORS.get(cluster, "#888")
                label = CLUSTER_LABELS.get(cluster, cluster)
                if recs_df.empty or "cluster_type" not in recs_df.columns:
                    continue
                sub = recs_df[recs_df["cluster_type"] == cluster]
                if sub.empty:
                    continue
                traj = sub.groupby("tick")["trust_score"].mean()
                ax.plot(traj.index, traj.values, color=meta, lw=1.8,
                        marker="o", ms=3.5, label=label)
            ax.set_ylim(bottom=0)
            _vlines(ax)
            ax.set_title(f"{title} — by Segment", fontsize=10, fontweight="bold")
            ax.set_xlabel("Tick"); ax.set_ylabel("Trust")
            ax.legend(fontsize=7, loc="lower right", ncol=2)
            ax.grid(True, ls=":", alpha=0.4)

    out = os.path.join(output_dir, f"trial_trust_trajectory_{timestamp}.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  🖼️  信任轨迹图: {out}")


def plot_clarification_detail(all_results: list, output_dir: str, timestamp: str):
    """图2：澄清窗口细节（±3 Tick 信任 + 情绪冲击箱线图）"""
    clr_list = [r for r in all_results if "No-Clr" not in r["group_label"]]
    control  = next((r for r in all_results if "No-Clr" in r["group_label"]), None)
    if not clr_list or control is None:
        return

    ct     = CLARIFICATION_TICK
    wstart = max(1, ct - 3)
    wend   = min(TRIAL_PARAMS["total_ticks"], ct + 3)
    window = list(range(wstart, wend + 1))

    fig, axes = plt.subplots(len(clr_list), 2, figsize=(14, 5 * len(clr_list)))
    if len(clr_list) == 1:
        axes = [axes]
    fig.suptitle(f"Clarification Detail (Tick {wstart}–{wend})",
                 fontsize=13, fontweight="bold")

    for row_i, clr_r in enumerate(clr_list):
        ax_l, ax_r = axes[row_i][0], axes[row_i][1]

        # 左：信任轨迹（澄清组 vs 对照组，按人群）
        for src, ls, suffix in [(clr_r, "-", " [Clr]"), (control, "--", " [Ctrl]")]:
            recs_df = pd.DataFrame(src.get("agent_records", []))
            recs_w  = recs_df[recs_df["tick"].isin(window)] if not recs_df.empty else pd.DataFrame()
            for cluster in CLUSTER_ORDER:
                if recs_w.empty or "cluster_type" not in recs_w.columns:
                    continue
                sub = recs_w[recs_w["cluster_type"] == cluster]
                if sub.empty:
                    continue
                traj = sub.groupby("tick")["trust_score"].mean()
                ax_l.plot(traj.index, traj.values,
                          color=CLUSTER_COLORS.get(cluster, "#888"), ls=ls, lw=2,
                          marker="o", ms=4,
                          label=f"{CLUSTER_LABELS.get(cluster, cluster)}{suffix}")

        ax_l.axvline(ct, color="#2ca02c", lw=2, alpha=0.8, label=f"Clarification (T{ct})")
        ax_l.axvline(TRIAL_PARAMS["scandal_tick"], color="#d62728", lw=1.5, ls="--", alpha=0.6)
        ax_l.set_title(f"{clr_r['group_label']} — Trust (window)", fontsize=10)
        ax_l.set_xlabel("Tick"); ax_l.set_ylabel("Trust Score")
        ax_l.legend(fontsize=7, ncol=2); ax_l.grid(True, ls=":", alpha=0.4)
        ax_l.set_xticks(window)

        # 右：情绪冲击箱线图
        for c_idx, cluster in enumerate(CLUSTER_ORDER):
            clr_day  = [rec["affective_change"] for rec in clr_r.get("agent_records", [])
                        if rec["tick"] == ct and rec["cluster_type"] == cluster]
            ctrl_day = [rec["affective_change"] for rec in control.get("agent_records", [])
                        if rec["tick"] == ct and rec["cluster_type"] == cluster]
            pos_clr  = c_idx * 3 + 0.7
            pos_ctrl = c_idx * 3 + 1.7
            for pos, data, fc in [(pos_clr, clr_day, CLUSTER_COLORS.get(cluster, "#888")),
                                   (pos_ctrl, ctrl_day, "#cccccc")]:
                if data:
                    bp = ax_r.boxplot(data, positions=[pos], widths=0.6,
                                      patch_artist=True, manage_ticks=False)
                    bp["boxes"][0].set_facecolor(fc)
                    bp["boxes"][0].set_alpha(0.75)

        ax_r.axhline(0, color="black", ls="--", lw=0.8, alpha=0.5)
        ax_r.set_xticks([c * 3 + 1.2 for c in range(len(CLUSTER_ORDER))])
        ax_r.set_xticklabels([CLUSTER_LABELS.get(c, c)[:10] for c in CLUSTER_ORDER], fontsize=8)
        ax_r.set_title(f"Affective Change on Clarification Day (T{ct})", fontsize=10)
        ax_r.set_ylabel("Affective Impact (Δ)")
        from matplotlib.patches import Patch
        ax_r.legend(handles=[Patch(color="#aaa", label="Clr Group"),
                              Patch(color="#ccc", label="Control")], fontsize=8)
        ax_r.grid(True, axis="y", ls=":", alpha=0.4)

    plt.tight_layout()
    out = os.path.join(output_dir, f"trial_clarification_detail_{timestamp}.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  🖼️  澄清细节图: {out}")


# ══════════════════════════════════════════════════════════════════════
# 终端摘要打印
# ══════════════════════════════════════════════════════════════════════

def print_thought_summary(all_results: list):
    """在关键 Tick 打印每个 Agent 的信任分、情绪冲击、内心独白"""
    scandal_tick = TRIAL_PARAMS["scandal_tick"]
    max_tick     = TRIAL_PARAMS["total_ticks"]

    focus = {scandal_tick: "🚨 SCANDAL DAY"}
    if CLARIFICATION_TICK <= max_tick:
        focus[CLARIFICATION_TICK] = "💊 CLARIFICATION DAY"
    if CLARIFICATION_TICK + 1 <= max_tick:
        focus[CLARIFICATION_TICK + 1] = "📅 +1 DAY AFTER CLR"
    if CLARIFICATION_TICK + 2 <= max_tick:
        focus[CLARIFICATION_TICK + 2] = "📅 +2 DAYS AFTER CLR"

    for r in all_results:
        print(f"\n{'═'*72}")
        print(f"  GROUP: {r['group_label']}")
        print(f"{'═'*72}")
        recs = r.get("agent_records", [])
        for tick, label in sorted(focus.items()):
            day_recs = [rec for rec in recs if rec["tick"] == tick]
            if not day_recs:
                continue
            print(f"\n  ── {label} (Tick {tick}) ──")
            print(f"  {'Agent':<14} {'Segment':<20} {'Trust':>6} {'Affect':>7} {'Hypo':>5}  Reasoning")
            print(f"  {'─'*90}")
            for rec in sorted(day_recs, key=lambda x: x["cluster_type"]):
                reasoning = str(rec.get("reasoning", ""))[:75].replace("\n", " ") or "(no thought)"
                hypo = "✓" if rec.get("hypocrisy_perceived") else "✗"
                print(f"  {rec['agent_id']:<14} {rec['cluster_type']:<20}"
                      f" {rec['trust_score']:>6.2f} {rec['affective_change']:>+7.3f}"
                      f" {hypo:>5}  {reasoning}")
            # 人群均值
            by_type: dict = {}
            for rec in day_recs:
                by_type.setdefault(rec["cluster_type"], []).append(rec["trust_score"])
            print(f"\n  Segment Avg Trust:")
            for ct_name, vals in sorted(by_type.items()):
                print(f"    {ct_name:<24} → {np.mean(vals):.3f}")


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 68)
    print("🧪 澄清策略对照实验 — 单漂绿事件 (Blackstone 丑闻)")
    print(f"   Scandal   : Tick {TRIAL_PARAMS['scandal_tick']}")
    print(f"   Clr Tick  : Tick {CLARIFICATION_TICK}（丑闻后第 {CLARIFICATION_TICK - TRIAL_PARAMS['scandal_tick']} 天）")
    print(f"   Content   : {CONTENT_TYPES}")
    print(f"   Agents={TRIAL_PARAMS['num_agents']}  Ticks={TRIAL_PARAMS['total_ticks']}  Seed={TRIAL_PARAMS['random_seed']}")
    print("=" * 68)

    output_dir = os.path.join(current_dir, "results", "trial", f"run_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    # 同时维护 latest/ 快照供快速查看
    latest_trial_dir = os.path.join(current_dir, "results", "trial", "latest")
    os.makedirs(latest_trial_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── 打开思维日志 ──────────────────────────────────────────────────
    thoughts_path = os.path.join(output_dir, f"trial_thoughts_{timestamp}.csv")
    thoughts_file = open(thoughts_path, "w", newline="", encoding="utf-8")
    thought_writer = csv.writer(thoughts_file)
    thought_writer.writerow([
        "group", "tick", "agent_id", "cluster_type",
        "trust_score", "trust_after_decay", "affective_change", "shock_anchor",
        "quiet_ticks", "hypocrisy_perceived", "importance",
        "reasoning", "post_content",
        "is_buying", "is_posting", "is_clarification_tick",
    ])

    all_results = []

    try:
        # ── 第一步：用 RecordingRouter 跑对照组，缓存所有 LLM 响应 ─────
        print(f"\n{'─'*68}\n  [1/3] 🔵 对照组 — No Clarification (Recording LLM responses)\n{'─'*68}")

        # 获取真实 router（需要先构建一次，复用内部逻辑）
        import yaml
        try:
            import simulation_core as _sc_ref
            with open(os.path.join(current_dir, "configs/models_config.yaml"), "r") as f:
                _models_conf = yaml.safe_load(f)
            from agentkernel_standalone.toolkit.models.router import ModelRouter, AsyncModelRouter
            _real_router = ModelRouter(AsyncModelRouter(_models_conf))
        except Exception:
            class _MockInner:
                async def chat(self, prompt: str) -> str:
                    if "trust_change_affective" in prompt or "hypocrisy_perceived" in prompt:
                        return json.dumps({"hypocrisy_perceived": True,
                                           "trust_change_affective": -1.5,
                                           "importance": 7.0,
                                           "reasoning": "Mock: betrayed."})
                    return json.dumps({"is_buying": False, "is_posting": True,
                                       "post_content": "Upset about this brand.",
                                       "reason": "Mock: low trust."})
            _real_router = _MockInner()

        recording_router = RecordingRouter(_real_router)
        r = await run_trial_group("no-clarification", "rational-evidence",
                                   output_dir, thought_writer,
                                   override_router=recording_router)
        all_results.append(r)
        llm_cache = recording_router.cache
        print(f"  📼 LLM 响应已缓存: {len(llm_cache)} 条 "
              f"（覆盖 Tick 1-{TRIAL_PARAMS['total_ticks']}）")

        # ── 第二步：用 ReplayRouter 跑澄清组，Tick < 8 完全回放 ──────────
        print(f"\n{'─'*68}\n  [2/3] 🟢 澄清组 — Rational Evidence "
              f"(Replay until T{CLARIFICATION_TICK}, then real LLM)\n{'─'*68}")
        replay_r = ReplayRouter(_real_router, llm_cache, CLARIFICATION_TICK)
        r = await run_trial_group("delay-3", "rational-evidence",
                                   output_dir, thought_writer,
                                   override_router=replay_r)
        all_results.append(r)
        if replay_r._miss_count > 0:
            print(f"  ⚠️  ReplayRouter miss count: {replay_r._miss_count}")

        print(f"\n{'─'*68}\n  [3/3] 🟠 澄清组 — Emotional Empathy "
              f"(Replay until T{CLARIFICATION_TICK}, then real LLM)\n{'─'*68}")
        replay_e = ReplayRouter(_real_router, llm_cache, CLARIFICATION_TICK)
        r = await run_trial_group("delay-3", "emotional-empathy",
                                   output_dir, thought_writer,
                                   override_router=replay_e)
        all_results.append(r)
        if replay_e._miss_count > 0:
            print(f"  ⚠️  ReplayRouter miss count: {replay_e._miss_count}")

    finally:
        thoughts_file.close()

    print(f"\n{'='*68}\n📊 仿真完成，生成输出...\n{'='*68}")

    # ── 导出 CSV ──────────────────────────────────────────────────────
    traj_path = os.path.join(output_dir, f"trial_trajectories_{timestamp}.csv")
    write_trajectories_csv(all_results, traj_path)
    print(f"📈 轨迹数据: {traj_path}")

    rec_path = os.path.join(output_dir, f"trial_agent_records_{timestamp}.csv")
    write_agent_records_csv(all_results, rec_path)
    print(f"🧬 逐Agent记录: {rec_path}")

    summary_path = os.path.join(output_dir, f"trial_summary_{timestamp}.txt")
    write_summary_txt(all_results, summary_path)
    print(f"📄 文字摘要: {summary_path}")

    # ── 基础可视化 → 输出到本次运行的 output_dir（带时间戳）────────────
    print("\n🎨 生成基础图表...")
    plot_trust_trajectories(all_results, output_dir, timestamp)
    plot_clarification_detail(all_results, output_dir, timestamp)

    # ── 增强可视化（plot_trial.py 6 张图）→ 输出到 output_dir/figures ─
    analysis_dir = os.path.join(current_dir, "analysis")
    if analysis_dir not in sys.path:
        sys.path.insert(0, analysis_dir)
    try:
        import plot_trial as _pt
        # 每次运行输出到独立子目录，历史图像不被覆盖
        figures_dir = os.path.join(output_dir, "figures")
        os.makedirs(figures_dir, exist_ok=True)
        _pt.OUT_DIR = figures_dir
        print("\n🎨 生成增强图表（plot_trial.py）...")
        df = pd.read_csv(thoughts_path)
        for col in ["trust_score", "affective_change", "trust_after_decay",
                    "shock_anchor", "importance", "quiet_ticks"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in ["is_buying", "is_posting", "hypocrisy_perceived", "is_clarification_tick"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.lower().map(
                    {"true": True, "false": False, "1": True, "0": False}
                ).fillna(False)
        _pt.plot_trust_trajectory(df)
        _pt.plot_affective_heatmap(df)
        _pt.plot_clarification_spotlight(df)
        _pt.plot_action_timeline(df)
        _pt.plot_delta_recovery_bar(df)
        _pt.plot_thought_scatter(df)
        print(f"  → 图表目录: {figures_dir}")
    except Exception as e:
        print(f"  ⚠️  增强可视化失败 ({type(e).__name__}): {e}")

    # ── 终端摘要 ──────────────────────────────────────────────────────
    print_thought_summary(all_results)

    # ── 澄清效果快速打印 ──────────────────────────────────────────────
    control = next((r for r in all_results if "No-Clr" in r["group_label"]), None)
    print(f"\n{'='*68}")
    print("📌 澄清效果量化（澄清后 5 Tick vs 对照组）")
    print(f"{'='*68}")
    for r in all_results:
        if "No-Clr" in r["group_label"]:
            continue
        ct = CLARIFICATION_TICK
        print(f"\n  {r['group_label']}:")
        for offset in range(5):
            t_idx = ct - 1 + offset
            if t_idx >= TRIAL_PARAMS["total_ticks"]:
                break
            ctrl_val = control["trust_trajectory"][t_idx] if control else 0
            clr_val  = r["trust_trajectory"][t_idx]
            delta    = clr_val - ctrl_val
            print(f"    Tick {t_idx+1:2d} (+{offset}): "
                  f"clr={clr_val:.3f}  ctrl={ctrl_val:.3f}  Δ={delta:+.3f}")

    # ── 核心指标对比 ──────────────────────────────────────────────────
    print(f"\n{'='*68}")
    print(f"{'Group':<30} {'ΔRecov':>10} {'AUC':>10} {'Speed':>10} {'Steady':>10}")
    print("─" * 62)
    for r in all_results:
        m = r["metrics"]
        print(f"{r['group_label']:<30}"
              f"{m.delta_recovery:>10.4f}"
              f"{m.auc_post_scandal:>10.4f}"
              f"{m.recovery_speed:>10.4f}"
              f"{m.steady_state_score:>10.3f}")

    print(f"\n📁 所有文件: {output_dir}")
    # ── 更新 latest/ 快照 ────────────────────────────────────────────
    import shutil as _shutil
    for fname in (
        f"trial_trajectories_{timestamp}.csv",
        f"trial_agent_records_{timestamp}.csv",
        f"trial_summary_{timestamp}.txt",
        f"trial_thoughts_{thoughts_path.split(os.sep)[-1]}",
        f"trial_trust_trajectory_{timestamp}.png",
        f"trial_clarification_detail_{timestamp}.png",
    ):
        src = os.path.join(output_dir, fname)
        if os.path.exists(src):
            _shutil.copy2(src, os.path.join(latest_trial_dir, fname))
    # figures/ 子目录整体复制
    src_figs = os.path.join(output_dir, "figures")
    dst_figs = os.path.join(latest_trial_dir, "figures")
    if os.path.exists(src_figs):
        if os.path.exists(dst_figs):
            _shutil.rmtree(dst_figs)
        _shutil.copytree(src_figs, dst_figs)
    with open(os.path.join(latest_trial_dir, "run_info.txt"), "w", encoding="utf-8") as _f:
        _f.write(f"run_id : {timestamp}\nrun_dir: {output_dir}\n")
    print(f"🔗 最新快照: {latest_trial_dir}")


if __name__ == "__main__":
    asyncio.run(main())
