"""
run_quick_experiment.py — 快速实验入口

用于企业策略干预的初步探索，在正式 12 组全量实验前快速验证主效应方向。

速度优化策略：
  1. num_agents = 6（减少 40%）
  2. total_ticks = 15（仅覆盖丑闻 + 两个澄清时机窗口）
  3. 只跑 6 个代表性条件（覆盖所有因子的主效应 + 对照组）
  4. Reflect 和 Plan 的 LLM 调用并行化（asyncio.gather）
  5. 实验间顺序执行（避免 API 并发限额）

6 个代表性条件选取逻辑：
  ┌──────────────────────────────────────────────────────┐
  │  对照组   NoClr（两个渠道取一个即可）                   │
  │  内容主效  Rational vs Empathy（固定 Hub + Imm）       │
  │  渠道主效  Hub vs Random（固定 Rational + Imm）        │
  │  时机主效  Imm vs D3（固定 Rational + Hub）            │
  └──────────────────────────────────────────────────────┘

用法：
    python run_quick_experiment.py

结果输出：
    results/quick/quick_summary.csv
    results/quick/quick_chart.png
"""
import sys
import os
import asyncio
import csv
import json
import datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from experiment_config import ExperimentConfig
from simulation_core import run_simulation_core

# ══════════════════════════════════════════════════════════════════════
# 快速实验参数
# ══════════════════════════════════════════════════════════════════════
QUICK_PARAMS = dict(
    num_agents  = 6,    # 6 个 Agent（覆盖四个消费者类型，保证每类至少 1 人）
    total_ticks = 15,   # 15 Tick：覆盖丑闻 + 两个澄清时机窗口 + 足够的恢复观察期
    budget_k    = 2,    # 澄清投放 2 个节点（占 6 人的 33%，比例与全量实验相当）
    random_seed = 42,
    scandal_tick= 5,
)

# 6 个代表性实验条件
QUICK_CONDITIONS = [
    # 对照组
    ExperimentConfig(content_factor="rational-evidence", channel_factor="hub",
                     timing_factor="no-clarification", **QUICK_PARAMS),
    # 内容因子主效应（固定 Hub + Immediate）
    ExperimentConfig(content_factor="rational-evidence", channel_factor="hub",
                     timing_factor="immediate", **QUICK_PARAMS),
    # ExperimentConfig(content_factor="emotional-empathy", channel_factor="hub",
    #                  timing_factor="immediate", **QUICK_PARAMS),
    # # 渠道因子主效应（固定 Rational + Immediate）
    # ExperimentConfig(content_factor="rational-evidence", channel_factor="random",
    #                  timing_factor="immediate", **QUICK_PARAMS),
    # # 时机因子主效应（固定 Rational + Hub）
    # ExperimentConfig(content_factor="rational-evidence", channel_factor="hub",
    #                  timing_factor="delay-3", **QUICK_PARAMS),
    # # 交叉验证：情感共情 + 延迟（最感兴趣的组合之一）
    # ExperimentConfig(content_factor="emotional-empathy", channel_factor="hub",
    #                  timing_factor="delay-3", **QUICK_PARAMS),
]


# ══════════════════════════════════════════════════════════════════════
# 结果可视化
# ══════════════════════════════════════════════════════════════════════
def plot_quick_results(results: list, output_dir: str, timestamp: str):
    """生成快速实验对比图：信任轨迹 + 三目标雷达图"""
    valid = [r for r in results if "error" not in r]
    if not valid:
        print("❌ 无有效结果，跳过绘图。")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Quick Experiment: Enterprise Strategy Intervention\n"
                 f"(n={QUICK_PARAMS['num_agents']} agents, {QUICK_PARAMS['total_ticks']} ticks)",
                 fontsize=13, fontweight="bold")

    # ── 左图：信任轨迹对比 ────────────────────────────────────────────
    ax = axes[0]
    colors = ["#e74c3c", "#2ecc71", "#27ae60", "#3498db", "#f39c12", "#9b59b6"]
    ticks = list(range(1, QUICK_PARAMS["total_ticks"] + 1))

    for i, r in enumerate(valid):
        traj = r["trust_trajectory"]
        label = r["exp_id"]
        ls = "--" if "NoClr" in label else "-"
        lw = 2.5 if "NoClr" in label else 1.8
        ax.plot(ticks, traj, label=label, color=colors[i % len(colors)],
                linestyle=ls, linewidth=lw, marker="o", markersize=3)

    # 标注关键事件
    ax.axvline(x=5, color="red",    linestyle=":", alpha=0.6, linewidth=1.2)
    ax.text(5.15, ax.get_ylim()[0] + 0.2, "Scandal\n(Tick5)", color="red",
            fontsize=7.5, va="bottom")
    ax.axvline(x=8, color="orange", linestyle=":", alpha=0.5, linewidth=1.0)
    ax.text(8.15, ax.get_ylim()[0] + 0.2, "Delay\n(Tick8)", color="orange",
            fontsize=7.5, va="bottom")

    ax.set_xlabel("Simulation Tick", fontsize=11)
    ax.set_ylabel("Average Trust Score (0–10)", fontsize=11)
    ax.set_title("Trust Trajectory by Strategy", fontsize=11)
    ax.set_ylim(0, 10)
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(True, linestyle=":", alpha=0.5)

    # ── 右图：核心三目标指标柱状图对比（高区分度版本）──────────────────
    ax2 = axes[1]
    exp_ids       = [r["exp_id"] for r in valid]
    delta_vals    = [r["metrics"].delta_recovery for r in valid]
    auc_vals      = [r["metrics"].auc_post_scandal for r in valid]
    speed_vals    = [r["metrics"].recovery_speed for r in valid]

    x = np.arange(len(exp_ids))
    w = 0.25
    bars1 = ax2.bar(x - w, delta_vals,  w, label="Δ Recovery (↑)",   color="#e74c3c", alpha=0.8)
    bars2 = ax2.bar(x,     auc_vals,    w, label="AUC Post-Scandal (↑)", color="#2ecc71", alpha=0.8)
    bars3 = ax2.bar(x + w, speed_vals,  w, label="Speed (↑)",        color="#3498db", alpha=0.8)

    for bar in list(bars1) + list(bars2) + list(bars3):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                 f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=7)

    ax2.set_xticks(x)
    ax2.set_xticklabels(exp_ids, rotation=25, ha="right", fontsize=8)
    ax2.set_title("Three-Objective Metrics (No-Censoring)", fontsize=11)
    ax2.legend(fontsize=8)
    ax2.grid(True, axis="y", linestyle=":", alpha=0.5)

    plt.tight_layout()
    chart_path = os.path.join(output_dir, f"quick_chart_{timestamp}.png")
    plt.savefig(chart_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"🖼️  图表已保存: {chart_path}")


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════
async def main():
    print("=" * 60)
    print("⚡ 快速实验模式 — 企业策略干预初探")
    print(f"   条件数: {len(QUICK_CONDITIONS)}")
    print(f"   Agents: {QUICK_PARAMS['num_agents']}  |  Ticks: {QUICK_PARAMS['total_ticks']}")
    print(f"   预计 LLM 调用: ~{len(QUICK_CONDITIONS) * QUICK_PARAMS['num_agents'] * QUICK_PARAMS['total_ticks'] * 2} 次  (≈ {len(QUICK_CONDITIONS) * QUICK_PARAMS['num_agents'] * QUICK_PARAMS['total_ticks'] * 2 // 60} min)")
    print("=" * 60)

    output_dir = os.path.join(current_dir, "results", "quick")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    results = []
    for i, config in enumerate(QUICK_CONDITIONS, 1):
        print(f"\n[{i}/{len(QUICK_CONDITIONS)}] 🚀 {config.exp_id}")
        print(f"     content={config.content_factor}  channel={config.channel_factor}  timing={config.timing_factor}")
        try:
            result = await run_simulation_core(config)
            m = result["metrics"]
            print(f"     ✅ ΔRecov={m.delta_recovery:.4f}  AUC={m.auc_post_scandal:.4f}  Speed={m.recovery_speed:.4f}")
            results.append(result)
        except Exception as e:
            print(f"     ❌ FAILED: {e}")
            results.append({"exp_id": config.exp_id, "error": str(e)})

    # 写入汇总 CSV（与 run_experiments.py 格式一致）
    summary_path = os.path.join(output_dir, f"quick_summary_{timestamp}.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "exp_id", "content_factor", "channel_factor", "timing_factor",
            "delta_recovery", "auc_post_scandal", "recovery_speed",
            "steady_state_score", "recovery_rate", "t50", "t80",
            "trust_min", "trust_min_tick", "baseline_trust", "clarification_effect",
        ])
        for r in results:
            if "error" in r:
                writer.writerow([r["exp_id"]] + ["ERROR"] * 14)
                continue
            cfg = r["config"]
            m = r["metrics"]
            writer.writerow([
                r["exp_id"], cfg["content_factor"], cfg["channel_factor"], cfg["timing_factor"],
                m.delta_recovery, m.auc_post_scandal, m.recovery_speed,
                m.steady_state_score, m.recovery_rate, m.t50, m.t80,
                m.trust_min, m.trust_min_tick, m.baseline_trust, m.clarification_effect,
            ])

    print(f"\n📄 汇总表: {summary_path}")

    # 绘图
    valid_results = [r for r in results if "error" not in r]
    if valid_results:
        plot_quick_results(results, output_dir, timestamp)

    # 控制台打印排名
    print("\n" + "=" * 70)
    print("📊 快速结果排名（按 Δ Recovery 降序）")
    print("=" * 70)
    sorted_results = sorted(valid_results, key=lambda r: r["metrics"].delta_recovery, reverse=True)
    print(f"  {'Rank':<5} {'exp_id':<25} {'ΔRecov':>8} {'AUC':>8} {'Speed':>8} {'Steady':>8}")
    print(f"  {'-'*65}")
    for rank, r in enumerate(sorted_results, 1):
        m = r["metrics"]
        marker = " ⭐" if rank == 1 else ""
        print(f"  {rank:<5} {r['exp_id']:<25} "
              f"{m.delta_recovery:>8.4f} {m.auc_post_scandal:>8.4f} "
              f"{m.recovery_speed:>8.4f} {m.steady_state_score:>8.3f}{marker}")

    # 也打印澄清效果诊断
    clr_results = [r for r in valid_results if r["config"].get("timing_factor") != "no-clarification"]
    noclr_results = [r for r in valid_results if r["config"].get("timing_factor") == "no-clarification"]
    if clr_results and noclr_results:
        clr_effect = np.mean([r["metrics"].clarification_effect for r in clr_results])
        print(f"\n📌 澄清效果 (clarification_effect 均值): {clr_effect:+.4f}")

    failed = [r for r in results if "error" in r]
    print(f"\n✅ 成功: {len(valid_results)}/{len(results)}  ❌ 失败: {len(failed)}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
