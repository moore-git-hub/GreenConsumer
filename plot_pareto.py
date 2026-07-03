"""
plot_pareto.py — 帕累托前沿分析（新三目标：delta_recovery / auc_post_scandal / recovery_speed）

所有目标均越大越好，无 censoring 问题。
"""
import os
import csv
import numpy as np
import matplotlib.pyplot as plt
from typing import List

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


def is_dominated(a_metrics, b_metrics) -> bool:
    """
    判断 a 是否被 b 支配（三目标均越大越好）。
    b 支配 a 当且仅当：b 在所有目标上 ≥ a，且至少一个严格 >。
    """
    better_or_equal = (
        b_metrics.delta_recovery   >= a_metrics.delta_recovery   and
        b_metrics.auc_post_scandal >= a_metrics.auc_post_scandal and
        b_metrics.recovery_speed   >= a_metrics.recovery_speed
    )
    strictly_better = (
        b_metrics.delta_recovery   > a_metrics.delta_recovery   or
        b_metrics.auc_post_scandal > a_metrics.auc_post_scandal or
        b_metrics.recovery_speed   > a_metrics.recovery_speed
    )
    return better_or_equal and strictly_better


def find_pareto_front(results: list) -> List[int]:
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
    comparison_dir = os.path.join(output_dir, "comparison")
    os.makedirs(comparison_dir, exist_ok=True)

    exp_ids   = [r["exp_id"] for r in results]
    deltas    = [r["metrics"].delta_recovery for r in results]
    aucs      = [r["metrics"].auc_post_scandal for r in results]
    speeds    = [r["metrics"].recovery_speed for r in results]

    pareto_indices = find_pareto_front(results)
    is_pareto = [i in pareto_indices for i in range(len(results))]

    print(f"\n🏆 帕累托前沿（{len(pareto_indices)} 个非支配解）:")
    for idx in pareto_indices:
        r = results[idx]
        m = r["metrics"]
        print(f"   ⭐ {r['exp_id']:25s} | Δ={m.delta_recovery:.4f} | AUC={m.auc_post_scandal:.4f} | Speed={m.recovery_speed:.4f}")

    # ── 三个二维投影图 ────────────────────────────────────────────────
    projections = [
        ("Δ Recovery (↑)", "AUC Post-Scandal (↑)", deltas, aucs,   "pareto_delta_vs_auc.png"),
        ("Δ Recovery (↑)", "Recovery Speed (↑)",   deltas, speeds, "pareto_delta_vs_speed.png"),
        ("AUC (↑)",        "Recovery Speed (↑)",   aucs,   speeds, "pareto_auc_vs_speed.png"),
    ]

    for xlabel, ylabel, xdata, ydata, filename in projections:
        fig, ax = plt.subplots(figsize=(10, 7))
        x_rng = max(xdata) - min(xdata) if max(xdata) != min(xdata) else 1e-6
        y_rng = max(ydata) - min(ydata) if max(ydata) != min(ydata) else 1e-6

        for i in range(len(results)):
            color  = '#d62728' if is_pareto[i] else '#aec7e8'
            size   = 150 if is_pareto[i] else 80
            zorder = 10 if is_pareto[i] else 5
            edge   = '#8B0000' if is_pareto[i] else 'none'
            ax.scatter(xdata[i], ydata[i], c=color, s=size, alpha=0.9, zorder=zorder,
                       edgecolors=edge, linewidths=1.5)
            dy = y_rng * 0.04 * (1 if i % 2 == 0 else -1.5)
            ax.annotate(exp_ids[i], (xdata[i], ydata[i]),
                        xytext=(xdata[i] + x_rng*0.02, ydata[i] + dy),
                        fontsize=6.5, alpha=0.85, ha='left')

        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(f'Pareto: {xlabel.split("(")[0].strip()} vs {ylabel.split("(")[0].strip()}',
                     fontsize=13, fontweight='bold')
        ax.grid(True, linestyle=':', alpha=0.5)
        import matplotlib.patches as mpatches
        ax.legend(handles=[
            mpatches.Patch(color='#d62728', label='Pareto Optimal'),
            mpatches.Patch(color='#aec7e8', label='Dominated'),
        ], fontsize=10)
        plt.tight_layout()
        plt.savefig(os.path.join(comparison_dir, filename), dpi=300)
        plt.close()

    # ── 策略排名 CSV ─────────────────────────────────────────────────
    ranking_path = os.path.join(comparison_dir, "strategy_ranking.csv")
    with open(ranking_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["exp_id", "Rank_Delta", "Rank_AUC", "Rank_Speed",
                         "delta_recovery", "auc_post_scandal", "recovery_speed", "Is_Pareto"])
        rank_d = {idx: r+1 for r, idx in enumerate(sorted(range(len(results)), key=lambda i: -deltas[i]))}
        rank_a = {idx: r+1 for r, idx in enumerate(sorted(range(len(results)), key=lambda i: -aucs[i]))}
        rank_s = {idx: r+1 for r, idx in enumerate(sorted(range(len(results)), key=lambda i: -speeds[i]))}
        for i in range(len(results)):
            writer.writerow([exp_ids[i], rank_d[i], rank_a[i], rank_s[i],
                             round(deltas[i], 4), round(aucs[i], 4), round(speeds[i], 4),
                             "YES" if is_pareto[i] else "NO"])

    print(f"📊 帕累托分析完成 → {comparison_dir}/")


if __name__ == "__main__":
    import pandas as pd
    from metrics_calculator import SimulationMetrics

    results_dir = os.path.join(os.path.dirname(__file__), "results", "experiments")
    summary_path = os.path.join(results_dir, "summary.csv")

    if not os.path.exists(summary_path):
        print("❌ 未找到 summary.csv，请先运行 run_experiments.py")
    else:
        df = pd.read_csv(summary_path)
        results = []
        for _, row in df.iterrows():
            if str(row.get("delta_recovery", "")) == "ERROR":
                continue
            try:
                metrics = SimulationMetrics(
                    delta_recovery=float(row["delta_recovery"]),
                    auc_post_scandal=float(row["auc_post_scandal"]),
                    recovery_speed=float(row["recovery_speed"]),
                    t80=int(row.get("t80", 30)),
                    t50=int(row.get("t50", 30)),
                    steady_state_score=float(row["steady_state_score"]),
                    recovery_rate=float(row["recovery_rate"]),
                    trust_min=float(row["trust_min"]),
                    trust_min_tick=int(row["trust_min_tick"]),
                    baseline_trust=float(row["baseline_trust"]),
                    clarification_effect=float(row.get("clarification_effect", 0.0)),
                )
                results.append({"exp_id": row["exp_id"], "metrics": metrics})
            except (KeyError, ValueError) as e:
                print(f"⚠️ 跳过行 {row.get('exp_id', '?')}: {e}")

        if results:
            analyze_and_plot_pareto(results, results_dir)
        else:
            print("❌ summary.csv 中无有效数据（可能是旧格式，请重跑 run_experiments.py）")
