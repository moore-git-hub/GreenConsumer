"""Scientific visualization pack for TASK_005 FMCG v3.2 engineering/demo runs.

This module is descriptive by design. A one-block preview is one engineering
replication over the 9 communication conditions; it is NOT a new formal
F001-F010 block. Therefore no p-values, confidence intervals, significance
stars, winner labels, or real-world population claims are produced here.
"""
from __future__ import annotations

import html
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean

import matplotlib.pyplot as plt

from experiment_config import CONTROL_EXP_ID, generate_experiment_matrix
from fmcg_scenario_v32 import ENGINEERING_PERSONAS

from .io import read_csv, write_json

CONDITION_ORDER = (
    "NoClarification-Control",
    "Rational-Hub-Immediate",
    "Rational-Hub-Delayed",
    "Rational-Random-Immediate",
    "Rational-Random-Delayed",
    "Empathy-Hub-Immediate",
    "Empathy-Hub-Delayed",
    "Empathy-Random-Immediate",
    "Empathy-Random-Delayed",
)

FACTOR_LABELS = {
    "rational-evidence": "Rational evidence",
    "emotional-empathy": "Emotional empathy",
    "hub": "Hub",
    "random": "Random",
    "immediate": "Immediate",
    "delayed": "Delayed",
}


def _num(value, default=None):
    if value in (None, ""):
        return default
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def _flag(value) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _mean(values):
    values = [value for value in values if value is not None and math.isfinite(value)]
    return fmean(values) if values else float("nan")


def _condition_map():
    return {cfg.exp_id: cfg for cfg in generate_experiment_matrix()}


def _group_conditions(rows):
    out = defaultdict(list)
    for row in rows:
        out[str(row["exp_id"])].append(row)
    return out


def _tick_mean(rows, field):
    out = defaultdict(list)
    for row in rows:
        value = _num(row.get(field))
        if value is not None:
            out[int(row["tick"])].append(value)
    return {tick: _mean(values) for tick, values in sorted(out.items())}


def _save(fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def _events(ax):
    ax.axvline(5, linestyle="--", linewidth=1, alpha=0.75)
    ax.axvline(6, linestyle=":", linewidth=1, alpha=0.75)
    ax.axvline(10, linestyle=":", linewidth=1, alpha=0.75)


def _factor_trust(rows_by_condition, factor, level):
    configs = _condition_map()
    by_tick = defaultdict(list)
    for exp_id, cfg in configs.items():
        if cfg.is_control or getattr(cfg, factor) != level or exp_id not in rows_by_condition:
            continue
        for tick, value in _tick_mean(rows_by_condition[exp_id], "trust_final").items():
            by_tick[tick].append(value)
    return {tick: _mean(values) for tick, values in sorted(by_tick.items())}


def _plot_01_trust_overview(rows_by_condition, figures):
    control = _tick_mean(rows_by_condition[CONTROL_EXP_ID], "trust_final")
    by_tick = defaultdict(list)
    for exp_id, rows in rows_by_condition.items():
        if exp_id == CONTROL_EXP_ID:
            continue
        for tick, value in _tick_mean(rows, "trust_final").items():
            by_tick[tick].append(value)
    strategy = {tick: _mean(values) for tick, values in sorted(by_tick.items())}
    ticks = sorted(set(control) & set(strategy))

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    ax.plot(ticks, [control[t] for t in ticks], label="No-clarification control", linewidth=2.2)
    ax.plot(ticks, [strategy[t] for t in ticks], label="Mean of 8 clarification strategies", linewidth=2.2)
    _events(ax)
    ax.set_xlabel("Tick")
    ax.set_ylabel("Mean brand trust (0–10)")
    ax.set_title("Trust trajectory: control versus average clarification strategy")
    ax.grid(alpha=0.22)
    ax.legend()
    ax.text(
        0.01, 0.02,
        "T5 crisis · T6 immediate clarification · T10 delayed clarification",
        transform=ax.transAxes, fontsize=8, alpha=0.75,
    )
    return _save(fig, figures / "01_trust_overview.png")


def _plot_02_factor_trust(rows_by_condition, figures):
    control = _tick_mean(rows_by_condition[CONTROL_EXP_ID], "trust_final")
    panels = (
        ("content_factor", ("rational-evidence", "emotional-empathy"), "Content"),
        ("timing_factor", ("immediate", "delayed"), "Timing"),
        ("channel_factor", ("hub", "random"), "Channel"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(15.8, 4.9), sharey=True)
    for ax, (factor, levels, title) in zip(axes, panels):
        ticks = sorted(control)
        ax.plot(ticks, [control[t] for t in ticks], label="Control", linewidth=1.7, alpha=0.8)
        for level in levels:
            trajectory = _factor_trust(rows_by_condition, factor, level)
            common = sorted(set(control) & set(trajectory))
            ax.plot(common, [trajectory[t] for t in common], label=FACTOR_LABELS[level], linewidth=2)
        _events(ax)
        ax.set_title(title)
        ax.set_xlabel("Tick")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Mean brand trust (0–10)")
    fig.suptitle("Factor-level trust trajectories (equal-weighted across remaining factors)", y=1.02)
    return _save(fig, figures / "02_factor_trust_trajectories.png")


def _plot_03_delta_heatmap(rows_by_condition, figures):
    control = _tick_mean(rows_by_condition[CONTROL_EXP_ID], "trust_final")
    treatments = [
        exp_id for exp_id in CONDITION_ORDER
        if exp_id != CONTROL_EXP_ID and exp_id in rows_by_condition
    ]
    ticks = sorted(control)
    matrix = []
    for exp_id in treatments:
        trajectory = _tick_mean(rows_by_condition[exp_id], "trust_final")
        matrix.append([trajectory.get(tick, float("nan")) - control[tick] for tick in ticks])

    max_abs = max([abs(value) for row in matrix for value in row if math.isfinite(value)] or [0.05])
    max_abs = max(max_abs, 0.05)
    fig, ax = plt.subplots(figsize=(12.0, 5.8))
    im = ax.imshow(
        matrix, aspect="auto", interpolation="nearest",
        cmap="coolwarm", vmin=-max_abs, vmax=max_abs,
    )
    ax.set_yticks(range(len(treatments)))
    ax.set_yticklabels(treatments, fontsize=8)
    tick_positions = [i for i, tick in enumerate(ticks) if tick in {1, 5, 6, 10, 15, 20, 25, 30}]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([ticks[i] for i in tick_positions])
    ax.set_xlabel("Tick")
    ax.set_title("Treatment-minus-control trust difference")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Δ mean trust")
    return _save(fig, figures / "03_trust_delta_heatmap.png")


def _plot_04_semantics(rows_by_condition, figures):
    fields = (
        ("semantic_valence", "Valence"),
        ("semantic_credibility", "Credibility"),
        ("semantic_evidence_strength", "Evidence"),
        ("semantic_topic_relevance", "Relevance"),
        ("semantic_perceived_empathy", "Empathy"),
    )
    available = [
        item for item in fields
        if any(_num(row.get(item[0])) is not None for rows in rows_by_condition.values() for row in rows)
    ]
    if not available:
        return None

    conditions = [exp_id for exp_id in CONDITION_ORDER if exp_id in rows_by_condition]
    matrix = []
    for exp_id in conditions:
        rows = rows_by_condition[exp_id]
        observed = [
            row for row in rows
            if _flag(row.get("semantic_observation_present"))
            or any(abs(_num(row.get(field), 0.0)) > 1e-12 for field, _ in available)
        ]
        basis = observed or rows
        matrix.append([_mean(_num(row.get(field)) for row in basis) for field, _ in available])

    fig, ax = plt.subplots(figsize=(10.6, 6.2))
    im = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="viridis")
    ax.set_yticks(range(len(conditions)))
    ax.set_yticklabels(conditions, fontsize=8)
    ax.set_xticks(range(len(available)))
    ax.set_xticklabels([label for _, label in available], rotation=20, ha="right")
    ax.set_title("Mean semantic appraisal by communication condition")
    fig.colorbar(im, ax=ax, label="Mean semantic score")
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if math.isfinite(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7)
    return _save(fig, figures / "04_semantic_appraisal_heatmap.png")


def _plot_05_segments(rows_by_condition, figures):
    segment = {persona.agent_id: persona.green_orientation for persona in ENGINEERING_PERSONAS}
    selected = [
        exp_id for exp_id in (
            CONTROL_EXP_ID, "Rational-Hub-Immediate", "Empathy-Hub-Immediate"
        ) if exp_id in rows_by_condition
    ]
    if not selected:
        return None

    fig, axes = plt.subplots(1, len(selected), figsize=(5.1 * len(selected), 4.8), sharey=True)
    axes = [axes] if len(selected) == 1 else axes
    segments = sorted(set(segment.values()))

    for ax, exp_id in zip(axes, selected):
        grouped = defaultdict(list)
        for row in rows_by_condition[exp_id]:
            seg = segment.get(str(row.get("agent_id")))
            value = _num(row.get("trust_final"))
            if seg and value is not None:
                grouped[(seg, int(row["tick"]))].append(value)
        for seg in segments:
            ticks = sorted(tick for (name, tick) in grouped if name == seg)
            if ticks:
                ax.plot(ticks, [_mean(grouped[(seg, tick)]) for tick in ticks], label=seg, linewidth=1.8)
        _events(ax)
        ax.set_title(exp_id)
        ax.set_xlabel("Tick")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
    axes[0].set_ylabel("Mean trust within engineering segment")
    fig.suptitle("Consumer heterogeneity: illustrative segment trajectories", y=1.02)
    return _save(fig, figures / "05_segment_heterogeneity.png")


def _curve_lookup(curves):
    out = defaultdict(dict)
    for row in curves:
        value = _num(row.get("cumulative_expected_choice_share"))
        if value is not None:
            out[(str(row["exp_id"]), str(row["conversion_support"]))][int(row["tick"])] = value
    return out


def _plot_06_repeat_choice(curves, figures):
    if not curves:
        return None
    data = _curve_lookup(curves)
    selected = (
        CONTROL_EXP_ID,
        "Rational-Hub-Immediate",
        "Rational-Random-Delayed",
        "Empathy-Hub-Immediate",
        "Empathy-Random-Delayed",
    )
    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.0), sharey=True)
    plotted = False
    for ax, support in zip(axes, ("absent", "present")):
        for exp_id in selected:
            points = data.get((exp_id, support), {})
            if not points:
                continue
            plotted = True
            ticks = sorted(points)
            ax.plot(ticks, [points[t] for t in ticks], label=exp_id, linewidth=1.8)
        _events(ax)
        ax.set_title(f"Conversion support: {support}")
        ax.set_xlabel("Tick")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
    axes[0].set_ylabel("Cumulative expected focal-brand choice share")
    fig.suptitle("Repeated brand-choice trajectories at category-purchase opportunities", y=1.02)
    if not plotted:
        plt.close(fig)
        return None
    return _save(fig, figures / "06_repeat_choice_trajectories.png")


def _plot_07_support_delta(curves, figures):
    if not curves:
        return None
    data = _curve_lookup(curves)
    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    count = 0
    for exp_id in CONDITION_ORDER:
        absent = data.get((exp_id, "absent"), {})
        present = data.get((exp_id, "present"), {})
        ticks = sorted(set(absent) & set(present))
        if not ticks:
            continue
        count += 1
        ax.plot(ticks, [present[t] - absent[t] for t in ticks], label=exp_id, linewidth=1.3)
    if not count:
        plt.close(fig)
        return None
    ax.axhline(0.0, linewidth=1)
    ax.axvline(6, linestyle=":", linewidth=1)
    ax.axvline(19, linestyle=":", linewidth=1)
    ax.set_xlabel("Tick")
    ax.set_ylabel("Expected choice share: support present − absent")
    ax.set_title("Conversion-support effect on repeated choice (descriptive)")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=6, ncol=2)
    return _save(fig, figures / "07_conversion_support_delta.png")


def _auc(trajectory, start, end):
    ticks = list(range(start, end + 1))
    if not all(tick in trajectory for tick in ticks):
        return float("nan")
    values = [trajectory[tick] for tick in ticks]
    if len(values) == 1:
        return values[0]
    return sum((values[i] + values[i + 1]) / 2 for i in range(len(values) - 1)) / (len(values) - 1)


def _single_block_contrasts(rows_by_condition, demand):
    configs = _condition_map()
    trust = {exp_id: _tick_mean(rows, "trust_final") for exp_id, rows in rows_by_condition.items()}
    control_auc = _auc(trust[CONTROL_EXP_ID], 6, 30)

    p1 = _mean(
        _auc(trajectory, 6, 30)
        for exp_id, trajectory in trust.items() if exp_id != CONTROL_EXP_ID
    ) - control_auc

    rational = [
        _auc(trust[exp_id], 6, 30) for exp_id, cfg in configs.items()
        if exp_id in trust and not cfg.is_control and cfg.content_factor == "rational-evidence"
    ]
    empathy = [
        _auc(trust[exp_id], 6, 30) for exp_id, cfg in configs.items()
        if exp_id in trust and not cfg.is_control and cfg.content_factor == "emotional-empathy"
    ]
    p2 = _mean(rational) - _mean(empathy)

    immediate = [
        _auc(trust[exp_id], 6, 9) for exp_id, cfg in configs.items()
        if exp_id in trust and not cfg.is_control and cfg.timing_factor == "immediate"
    ]
    delayed = [
        _auc(trust[exp_id], 6, 9) for exp_id, cfg in configs.items()
        if exp_id in trust and not cfg.is_control and cfg.timing_factor == "delayed"
    ]
    p3 = _mean(immediate) - _mean(delayed)

    reach = defaultdict(list)
    for exp_id, rows in rows_by_condition.items():
        cfg = configs.get(exp_id)
        if cfg is None or cfg.is_control or cfg.clarification_tick is None:
            continue
        values = [
            1.0 if _flag(row.get("enterprise_clarification_observed")) else 0.0
            for row in rows if int(row["tick"]) == int(cfg.clarification_tick)
        ]
        if values:
            reach[cfg.channel_factor].append(_mean(values))
    p4 = _mean(reach["hub"]) - _mean(reach["random"]) if reach["hub"] and reach["random"] else float("nan")

    choice = defaultdict(list)
    for row in demand:
        if str(row.get("conversion_support")) != "absent" or not (6 <= int(row["tick"]) <= 30):
            continue
        value = _num(row.get("choice_probability"))
        if value is not None:
            choice[str(row["exp_id"])].append(value)
    p5 = float("nan")
    if choice.get(CONTROL_EXP_ID):
        control_choice = _mean(choice[CONTROL_EXP_ID])
        strategy_choice = _mean(_mean(values) for exp_id, values in choice.items() if exp_id != CONTROL_EXP_ID)
        p5 = strategy_choice - control_choice

    return {
        "P1_overall_clarification_post_trust": p1,
        "P2_rational_minus_empathy_post_trust": p2,
        "P3_immediate_minus_delayed_early_trust": p3,
        "P4_hub_minus_random_reach": p4,
        "P5_overall_clarification_expected_repeat_choice": p5,
    }


def _plot_08_contrasts(contrasts, figures):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    trust_items = (
        ("P1 clarification − control", contrasts["P1_overall_clarification_post_trust"]),
        ("P2 rational − empathy", contrasts["P2_rational_minus_empathy_post_trust"]),
        ("P3 immediate − delayed\n(exploratory)", contrasts["P3_immediate_minus_delayed_early_trust"]),
    )
    axes[0].barh([x[0] for x in trust_items], [x[1] for x in trust_items])
    axes[0].axvline(0, linewidth=1)
    axes[0].set_xlabel("Trust-point contrast")
    axes[0].set_title("Trust contrasts")
    axes[0].grid(axis="x", alpha=0.2)

    other = (
        ("P4 Hub − Random reach\n(exploratory)", contrasts["P4_hub_minus_random_reach"]),
        ("P5 clarification − control\nexpected repeat choice", contrasts["P5_overall_clarification_expected_repeat_choice"]),
    )
    valid = [(label, value) for label, value in other if math.isfinite(value)]
    if valid:
        axes[1].barh([x[0] for x in valid], [x[1] for x in valid])
        axes[1].axvline(0, linewidth=1)
        axes[1].set_xlabel("Proportion / expected-choice-share contrast")
        axes[1].grid(axis="x", alpha=0.2)
    else:
        axes[1].text(0.5, 0.5, "P4/P5 unavailable", ha="center", va="center")
        axes[1].set_axis_off()
    axes[1].set_title("Reach and repeated-choice contrasts")
    fig.suptitle("Single engineering block — descriptive only; no CI or p-value", y=1.02)
    return _save(fig, figures / "08_single_block_contrasts.png")


def _dashboard(run_dir, pngs, contrasts):
    path = run_dir / "preview_dashboard.html"
    rows = "".join(
        f"<tr><td>{html.escape(key)}</td><td>{'NA' if not math.isfinite(value) else f'{value:.6f}'}</td></tr>"
        for key, value in contrasts.items()
    )
    figures = "".join(
        f'<section><h2>{html.escape(Path(item).stem.replace("_", " ").title())}</h2>'
        f'<img src="{html.escape(Path(item).relative_to(run_dir).as_posix())}" '
        f'alt="{html.escape(Path(item).stem)}"></section>'
        for item in pngs
    )
    path.write_text(
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>TASK_005 FMCG v3.2 preview</title><style>
body{font-family:Arial,sans-serif;margin:28px;max-width:1200px;color:#222}
.note{background:#f4f4f4;padding:12px 14px;border-left:4px solid #777}
section{margin:28px 0}img{max-width:100%;height:auto;border:1px solid #ddd}
table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:7px 10px;text-align:left}
</style></head><body><h1>TASK_005 FMCG v3.2 — engineering preview</h1>
<p class="note"><strong>Scope:</strong> descriptive engineering/demo only. This is not
a new formal F001-F010 replication. No p-values, confidence intervals, significance
stars, winner selection, or real-world population inference are produced.</p>
<h2>Single-block descriptive contrasts</h2>
<table><tr><th>Contrast</th><th>Value</th></tr>"""
        + rows + "</table>" + figures + "</body></html>",
        encoding="utf-8",
    )
    return str(path)


def plot_run(run_dir: Path) -> list[str]:
    """Generate the complete v3.2 descriptive visualization pack."""
    run_dir = Path(run_dir).resolve()
    cognitive_path = run_dir / "cognitive_records.csv"
    if not cognitive_path.exists():
        raise FileNotFoundError(cognitive_path)

    figures = run_dir / "figures"
    figures.mkdir(exist_ok=True)
    cognitive = read_csv(cognitive_path)
    rows_by_condition = _group_conditions(cognitive)
    curves = read_csv(run_dir / "choice_curves.csv") if (run_dir / "choice_curves.csv").exists() else []
    demand = read_csv(run_dir / "demand_opportunities.csv") if (run_dir / "demand_opportunities.csv").exists() else []

    full_matrix = CONTROL_EXP_ID in rows_by_condition and len(rows_by_condition) > 1
    outputs = []
    contrasts = {}

    if full_matrix:
        outputs.extend(
            [
                _plot_01_trust_overview(rows_by_condition, figures),
                _plot_02_factor_trust(rows_by_condition, figures),
                _plot_03_delta_heatmap(rows_by_condition, figures),
            ]
        )
    else:
        # Preserve low-cost single-condition real-LLM demos.
        fig, ax = plt.subplots(figsize=(10.5, 5.8))
        for exp_id, rows in sorted(rows_by_condition.items()):
            trajectory = _tick_mean(rows, "trust_final")
            ticks = sorted(trajectory)
            ax.plot(ticks, [trajectory[t] for t in ticks], label=exp_id, linewidth=2.2)
        _events(ax)
        ax.set_xlabel("Tick")
        ax.set_ylabel("Mean brand trust (0–10)")
        ax.set_title("Single-condition trust trajectory")
        ax.grid(alpha=0.22)
        ax.legend()
        outputs.append(_save(fig, figures / "01_single_condition_trust.png"))

    for output in (
        _plot_04_semantics(rows_by_condition, figures),
        _plot_05_segments(rows_by_condition, figures),
        _plot_06_repeat_choice(curves, figures),
        _plot_07_support_delta(curves, figures),
    ):
        if output:
            outputs.append(output)

    if full_matrix:
        contrasts = _single_block_contrasts(rows_by_condition, demand)
        outputs.append(_plot_08_contrasts(contrasts, figures))
    dashboard = _dashboard(run_dir, outputs, contrasts)
    outputs.append(dashboard)

    write_json(
        run_dir / "visualization_manifest.json",
        {
            "schema_version": "task005_fmcg_v32_visualization2.0",
            "status": "PASS",
            "scope": "descriptive engineering/demo visualization only",
            "formal_inference_performed": False,
            "p_values_computed": False,
            "confidence_intervals_computed": False,
            "winner_selected": False,
            "single_block_descriptive_contrasts": contrasts,
            "figures": [str(Path(item).relative_to(run_dir)) for item in outputs if item.endswith(".png")],
            "dashboard": str(Path(dashboard).relative_to(run_dir)),
            "interpretation_locks": {
                "P3": "exploratory timing mechanism only",
                "P4": "reach only; not persuasion or purchase",
                "P5": "expected repeat focal-brand choice conditional on category-purchase opportunities",
            },
        },
    )
    return outputs
