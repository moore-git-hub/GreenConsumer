"""TASK_005 FMCG v3.2 专用可视化。

只读取 clean workflow 的 ``results/v32_runs/<run_id>``，不再调用历史
Oatly/Blackstone 可视化脚本。
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

from .io import read_csv


def plot_run(run_dir: Path) -> list[str]:
    """生成认知信任轨迹和 FMCG expected repeat-choice 轨迹。"""
    cognitive_path = run_dir / "cognitive_records.csv"
    if not cognitive_path.exists():
        raise FileNotFoundError(cognitive_path)

    figures = run_dir / "figures"
    figures.mkdir(exist_ok=True)

    # 图1：每个 communication condition 的 20-agent mean trust。
    rows = read_csv(cognitive_path)
    trust = defaultdict(lambda: defaultdict(list))
    for row in rows:
        trust[row["exp_id"]][int(row["tick"])].append(float(row["trust_final"]))

    fig, ax = plt.subplots(figsize=(11, 6))
    for exp_id in sorted(trust):
        xs = sorted(trust[exp_id])
        ys = [sum(trust[exp_id][tick]) / len(trust[exp_id][tick]) for tick in xs]
        ax.plot(xs, ys, label=exp_id)
    ax.axvline(5, linestyle="--", linewidth=1)
    ax.set_xlabel("Tick")
    ax.set_ylabel("Mean trust")
    ax.set_title("TASK_005 FMCG v3.2 trust trajectories")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.25)
    fig.tight_layout()

    trust_out = figures / "trust_trajectories.png"
    fig.savefig(trust_out, dpi=180)
    plt.close(fig)
    outputs = [str(trust_out)]

    # 图2：若本次包含 demand，则画累计 expected focal-brand choice share。
    curve_path = run_dir / "choice_curves.csv"
    if curve_path.exists():
        curves = read_csv(curve_path)
        grouped = defaultdict(lambda: defaultdict(list))
        for row in curves:
            key = f"{row['exp_id']} | support={row['conversion_support']}"
            value = row.get("cumulative_expected_choice_share", "")
            if value != "":
                grouped[key][int(row["tick"])].append(float(value))

        fig, ax = plt.subplots(figsize=(11, 6))
        for key in sorted(grouped):
            xs = sorted(grouped[key])
            ys = [sum(grouped[key][tick]) / len(grouped[key][tick]) for tick in xs]
            ax.plot(xs, ys, label=key)
        ax.set_xlabel("Tick")
        ax.set_ylabel("Cumulative expected focal-brand choice share")
        ax.set_title("TASK_005 FMCG v3.2 repeated-choice trajectories")
        ax.legend(fontsize=6)
        ax.grid(alpha=0.25)
        fig.tight_layout()

        out = figures / "repeat_choice_trajectories.png"
        fig.savefig(out, dpi=180)
        plt.close(fig)
        outputs.append(str(out))

    return outputs
