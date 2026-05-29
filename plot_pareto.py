"""
plot_pareto.py — 帕累托前沿分析与可视化

从实验结果中识别非支配解集（Pareto Front），生成三目标空间的散点图和二维投影。
输出策略排名表，帮助管理者识别最优策略组合。
"""
import os
import csv
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from typing import List

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


def is_dominated(a_metrics, b_metrics) -> bool:
    """
    判断 a 是否被 b 支配。

    目标方向：
      - T80: 越小越好（恢复越快）
      - Steady_State_Score: 越大越好
      - Recovery_Rate: 越大越好

    b 支配 a 当且仅当：b 在所有目标上不差于 a，且至少一个严格更好。
    """
    better_or_equal = (
        b_metrics.t80 <= a_metrics.t80 and
        b_metrics.steady_state_score >= a_metrics.steady_state_score and
        b_metrics.recovery_rate >= a_metrics.recovery_rate
    )
    strictly_better = (
        b_metrics.t80 < a_metrics.t80 or
        b_metrics.steady_state_score > a_metrics.steady_state_score or
        b_metrics.recovery_rate > a_metrics.recovery_rate
    )
    return better_or_equal and strictly_better


def find_pareto_front(results: list) -> List[int]:
    """
    找到帕累托前沿（非支配解集）的索引。

    Returns:
        帕累托最优解在 results 列表中的索引列表
    """
    n = len(results)
    is_pareto = [True] * n

    for i in range(n):
        if not is_pareto[i]:
            continue
        for j in range(n):
            if i == j:
                continue
            if is_dominated(results[i]["metrics"], results[j]["metrics"]):
                is_pareto[i] = False
                break

    return [i for i in range(n) if is_pareto[i]]


def analyze_and_plot_pareto(results: list, output_dir: str):
    """
    执行帕累托分析并生成可视化图表。

    Args:
        results: run_simulation_core 返回的结果列表
        output_dir: 输出目录
    """
    comparison_dir = os.path.join(output_dir, "comparison")
    os.makedirs(comparison_dir, exist_ok=True)

    # 提取数据
    exp_ids = [r["exp_id"] for r in results]
    t80s = [r["metrics"].t80 for r in results]
    steadys = [r["metrics"].steady_state_score for r in results]
    recoveries = [r["metrics"].recovery_rate for r in results]

    # 找帕累托前沿
    pareto_indices = find_pareto_front(results)
    is_pareto = [i in pareto_indices for i in range(len(results))]

    print(f"\n🏆 帕累托前沿（{len(pareto_indices)} 个非支配解）:")
    for idx in pareto_indices:
        r = results[idx]
        m = r["metrics"]
        print(f"   ⭐ {r['exp_id']:25s} | T80={m.t80:2d} | Steady={m.steady_state_score:.2f} | Recovery={m.recovery_rate:.2f}")

    # ── 1. 3D 散点图 ────────────────────────────────────────────────
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    for i in range(len(results)):
        color = 'red' if is_pareto[i] else 'steelblue'
        marker = '★' if is_pareto[i] else 'o'
        size = 120 if is_pareto[i] else 60
        ax.scatter(t80s[i], steadys[i], recoveries[i], c=color, s=size, alpha=0.8)
        ax.text(t80s[i], steadys[i], recoveries[i], f"  {exp_ids[i]}", fontsize=6)

    ax.set_xlabel('T80 (Recovery Speed, ↓ better)')
    ax.set_ylabel('Steady-State Trust (↑ better)')
    ax.set_zlabel('Recovery Rate (↑ better)')
    ax.set_title('Pareto Front: Strategy Combinations in 3-Objective Space', fontsize=12, fontweight='bold')

    plt.savefig(os.path.join(comparison_dir, "pareto_3d.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # ── 2. 三个 2D 投影图 ────────────────────────────────────────────
    projections = [
        ("T80 (↓ better)", "Steady-State Trust (↑ better)", t80s, steadys, "pareto_t80_vs_steady.png"),
        ("T80 (↓ better)", "Recovery Rate (↑ better)", t80s, recoveries, "pareto_t80_vs_recovery.png"),
        ("Steady-State Trust (↑ better)", "Recovery Rate (↑ better)", steadys, recoveries, "pareto_steady_vs_recovery.png"),
    ]

    for xlabel, ylabel, xdata, ydata, filename in projections:
        fig, ax = plt.subplots(figsize=(10, 7))

        for i in range(len(results)):
            color = 'red' if is_pareto[i] else 'steelblue'
            size = 150 if is_pareto[i] else 80
            zorder = 10 if is_pareto[i] else 5
            ax.scatter(xdata[i], ydata[i], c=color, s=size, alpha=0.8, zorder=zorder,
                       edgecolors='darkred' if is_pareto[i] else 'none', linewidths=2)
            ax.annotate(exp_ids[i], (xdata[i], ydata[i]),
                        textcoords="offset points", xytext=(5, 5), fontsize=7, alpha=0.8)

        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(f'Pareto Analysis: {xlabel.split("(")[0].strip()} vs {ylabel.split("(")[0].strip()}',
                     fontsize=13, fontweight='bold')
        ax.grid(True, linestyle=':', alpha=0.5)

        # 图例
        ax.scatter([], [], c='red', s=100, label='Pareto Optimal', edgecolors='darkred', linewidths=2)
        ax.scatter([], [], c='steelblue', s=60, label='Dominated')
        ax.legend(loc='best', fontsize=10)

        plt.tight_layout()
        plt.savefig(os.path.join(comparison_dir, filename), dpi=300)
        plt.close()

    # ── 3. 策略排名表 ────────────────────────────────────────────────
    ranking_path = os.path.join(comparison_dir, "strategy_ranking.csv")
    with open(ranking_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Rank_T80", "Rank_Steady", "Rank_Recovery",
            "exp_id", "T80", "Steady_State", "Recovery_Rate", "Is_Pareto_Optimal"
        ])

        # 按 T80 排序
        sorted_by_t80 = sorted(range(len(results)), key=lambda i: t80s[i])
        # 按 Steady 排序（降序）
        sorted_by_steady = sorted(range(len(results)), key=lambda i: -steadys[i])
        # 按 Recovery 排序（降序）
        sorted_by_recovery = sorted(range(len(results)), key=lambda i: -recoveries[i])

        rank_t80 = {idx: rank + 1 for rank, idx in enumerate(sorted_by_t80)}
        rank_steady = {idx: rank + 1 for rank, idx in enumerate(sorted_by_steady)}
        rank_recovery = {idx: rank + 1 for rank, idx in enumerate(sorted_by_recovery)}

        for i in range(len(results)):
            writer.writerow([
                rank_t80[i], rank_steady[i], rank_recovery[i],
                exp_ids[i], t80s[i], steadys[i], recoveries[i],
                "YES" if is_pareto[i] else "NO"
            ])

    print(f"\n📊 帕累托分析完成，图表已保存至: {comparison_dir}/")
    print(f"   - pareto_3d.png")
    print(f"   - pareto_t80_vs_steady.png")
    print(f"   - pareto_t80_vs_recovery.png")
    print(f"   - pareto_steady_vs_recovery.png")
    print(f"   - strategy_ranking.csv")


if __name__ == "__main__":
    # 独立运行：从 summary.csv 读取数据
    import pandas as pd
    from metrics_calculator import SimulationMetrics

    results_dir = os.path.join(os.path.dirname(__file__), "results", "experiments")
    summary_path = os.path.join(results_dir, "summary.csv")

    if not os.path.exists(summary_path):
        print("❌ 未找到 results/experiments/summary.csv，请先运行 run_experiments.py")
    else:
        df = pd.read_csv(summary_path)
        results = []
        for _, row in df.iterrows():
            if row.get("t80") == "ERROR":
                continue
            metrics = SimulationMetrics(
                t80=int(row["t80"]),
                steady_state_score=float(row["steady_state_score"]),
                recovery_rate=float(row["recovery_rate"]),
                trust_min=float(row["trust_min"]),
                trust_min_tick=int(row["trust_min_tick"]),
                baseline_trust=float(row["baseline_trust"]),
            )
            results.append({"exp_id": row["exp_id"], "metrics": metrics})

        if results:
            analyze_and_plot_pareto(results, results_dir)
        else:
            print("❌ summary.csv 中无有效数据。")
