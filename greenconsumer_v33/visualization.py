"""Focused scientific diagnostics for TASK_005 FMCG v3.3.1 engineering runs.

No smoothing or interpolation is used. One engineering block is descriptive
only: figures contain no p-values, confidence intervals or winner labels.
The realized finite horizon is read from run provenance rather than hard-coded.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np

from greenconsumer_v32.io import read_csv, write_json
from .analysis import _read_total_ticks

CONTROL = "NoClarification-Control"


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else float("nan")


def _tick_mean(rows, field):
    grouped = defaultdict(list)
    for row in rows:
        value = row.get(field, "")
        if value in ("", None):
            continue
        grouped[int(row["tick"])].append(float(value))
    return {tick: _mean(vals) for tick, vals in sorted(grouped.items())}


def _group_by_condition(rows):
    out = defaultdict(list)
    for row in rows:
        out[str(row["exp_id"])].append(row)
    return dict(out)


def _save(fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_run(run_dir: Path) -> list[str]:
    cognitive_path = run_dir / "cognitive_records.csv"
    curves_path = run_dir / "choice_curves.csv"
    reach_path = run_dir / "clarification_reach_v33.csv"
    if not cognitive_path.exists():
        raise FileNotFoundError(cognitive_path)

    cognitive = read_csv(cognitive_path)
    end_tick = _read_total_ticks(run_dir, cognitive)
    by_condition = _group_by_condition(cognitive)
    if CONTROL not in by_condition:
        raise ValueError("v3.3.1 plots require the common control condition")

    figures_dir = run_dir / "figures_v33"
    figures_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    control = _tick_mean(by_condition[CONTROL], "trust_final")
    strategy_ids = sorted(x for x in by_condition if x != CONTROL)
    strategy_series = {
        exp_id: _tick_mean(by_condition[exp_id], "trust_final")
        for exp_id in strategy_ids
    }
    ticks = sorted(control)
    strategy_mean = [
        _mean(strategy_series[x][tick] for x in strategy_ids)
        for tick in ticks
    ]
    strategy_min = [min(strategy_series[x][tick] for x in strategy_ids) for tick in ticks]
    strategy_max = [max(strategy_series[x][tick] for x in strategy_ids) for tick in ticks]

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(ticks, [control[t] for t in ticks], marker="o", markersize=3, label="Control")
    ax.plot(ticks, strategy_mean, marker="o", markersize=3, label="8-strategy mean")
    ax.fill_between(ticks, strategy_min, strategy_max, alpha=0.15, label="strategy range (not CI)")
    for x, label in ((5, "Crisis"), (6, "Immediate"), (10, "Delayed")):
        ax.axvline(x, linestyle=":" if x != 5 else "--", linewidth=1)
        ax.text(x + 0.1, ax.get_ylim()[1], label, va="top", fontsize=8)
    ax.set_xlim(min(ticks), max(ticks))
    ax.set_title(
        f"v3.3.1 Trust dynamics through T{end_tick} — actual Tick observations; no smoothing/interpolation"
    )
    ax.set_xlabel("Tick")
    ax.set_ylabel("Mean Trust")
    ax.legend()
    path = figures_dir / "01_trust_dynamics_v33.png"
    _save(fig, path)
    outputs.append(str(path))

    matrix = np.array(
        [
            [strategy_series[exp_id][tick] - control[tick] for tick in ticks]
            for exp_id in strategy_ids
        ]
    )
    vmax = max(abs(float(np.nanmin(matrix))), abs(float(np.nanmax(matrix))), 1e-9)
    fig, ax = plt.subplots(figsize=(13, 5.5))
    im = ax.imshow(matrix, aspect="auto", cmap="coolwarm", vmin=-vmax, vmax=vmax)
    ax.set_yticks(range(len(strategy_ids)))
    ax.set_yticklabels(strategy_ids, fontsize=8)
    ax.set_xticks(range(0, len(ticks), 2))
    ax.set_xticklabels([ticks[i] for i in range(0, len(ticks), 2)])
    ax.set_xlabel("Tick")
    ax.set_title(f"v3.3.1 Treatment − contemporaneous control Trust through T{end_tick}")
    fig.colorbar(im, ax=ax, label="Δ Trust")
    path = figures_dir / "02_trust_delta_heatmap_v33.png"
    _save(fig, path)
    outputs.append(str(path))

    if reach_path.exists():
        reach = read_csv(reach_path)
        labels = [row["exp_id"] for row in reach]
        direct = [float(row["direct_reach_t0"]) for row in reach]
        eventual = [float(row["eventual_enterprise_reach"]) for row in reach]
        delivery_lag = int(float(reach[0].get("delivery_lag", 1))) if reach else 1
        y = np.arange(len(labels))
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.scatter(direct, y, label="direct at t0", s=45)
        ax.scatter(
            eventual,
            y,
            label=f"eventual direct enterprise reach (t0∪t0+{delivery_lag})",
            s=45,
        )
        for i, (a, b) in enumerate(zip(direct, eventual)):
            ax.plot([a, b], [i, i], linewidth=1)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlim(0, 1.05)
        ax.set_xlabel("Fraction of cognitive Agents")
        ax.set_title("v3.3.1 clarification reach — lag-aware; reach ≠ persuasion or purchase")
        ax.legend()
        path = figures_dir / "03_clarification_reach_v33.png"
        _save(fig, path)
        outputs.append(str(path))

    curves = read_csv(curves_path) if curves_path.exists() else []
    if curves:
        by_tick = defaultdict(list)
        for row in curves:
            if str(row.get("conversion_support")) != "absent":
                continue
            if str(row["exp_id"]) == CONTROL:
                continue
            by_tick[int(row["tick"])].append(float(row["opportunities"]))
        xs = sorted(by_tick)
        ys = [_mean(by_tick[t]) for t in xs]
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(xs, ys, marker="o", markersize=3)
        ax.set_xlim(min(xs), max(xs))
        ax.set_xlabel("Tick")
        ax.set_ylabel("Mean category-purchase opportunities")
        ax.set_title(
            f"v3.3.1 renewal purchase opportunities through T{end_tick} — common demand schedule, no fixed permanent interval"
        )
        path = figures_dir / "04_renewal_opportunities_v33.png"
        _save(fig, path)
        outputs.append(str(path))

        curve_map = {
            (str(row["exp_id"]), str(row["conversion_support"]), int(row["tick"])): row
            for row in curves
        }
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
        for ax, support in zip(axes, ("absent", "present")):
            for exp_id in strategy_ids:
                xvals, yvals = [], []
                for tick in range(1, end_tick + 1):
                    tr = curve_map.get((exp_id, support, tick))
                    ct = curve_map.get((CONTROL, support, tick))
                    if not tr or not ct:
                        continue
                    a = tr.get("cumulative_expected_choice_share", "")
                    b = ct.get("cumulative_expected_choice_share", "")
                    if a in ("", None) or b in ("", None):
                        continue
                    xvals.append(tick)
                    yvals.append(float(a) - float(b))
                ax.plot(xvals, yvals, marker="o", markersize=2, linewidth=1, label=exp_id)
            ax.axhline(0.0, linewidth=0.8)
            ax.set_xlim(1, end_tick)
            ax.set_title(f"Conversion support: {support}")
            ax.set_xlabel("Tick")
        axes[0].set_ylabel("Cumulative expected focal-brand choice Δ vs control")
        axes[1].legend(fontsize=6, loc="best")
        fig.suptitle(
            f"v3.3.1 clarification effect on repeat choice through T{end_tick}, stratified by conversion support"
        )
        path = figures_dir / "05_repeat_choice_delta_v33.png"
        _save(fig, path)
        outputs.append(str(path))

    manifest = {
        "schema_version": "task005_fmcg_v331_visualization1.1",
        "scope": "single engineering/demo block; descriptive only",
        "total_ticks": end_tick,
        "smoothing_used": False,
        "interpolation_used": False,
        "confidence_intervals_computed": False,
        "p_values_computed": False,
        "winner_selected": False,
        "figures": outputs,
    }
    write_json(run_dir / "visualization_manifest_v33.json", manifest)
    return outputs
