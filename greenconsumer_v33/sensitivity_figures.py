"""Thesis-safe post-processing figures for v3.3.1 sensitivity suites.

This module never runs the GABM and never changes parameters.  It regenerates
figures from already persisted Stage-A or Morris CSV outputs, allowing figure
labels/layout to be corrected without rerunning sensitivity experiments.

Important correction
--------------------
The first Stage-A plotting function displayed signed ``low-baseline`` and
``high-baseline`` deviations but labelled the x-axis "Absolute change".  The
underlying CSV values were correct; only that axis label was incorrect.  This
post-processor uses the scientifically correct label "Signed change" and keeps
all original result files untouched for provenance.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

# This module only writes files; forcing a non-GUI backend avoids Tk/Tcl
# dependencies in Windows Kernel and headless reproducibility environments.
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import pandas as pd

SCHEMA = "task005_fmcg_v331_sensitivity_figures1.0"

DISPLAY = {
    "P1_OVERALL_CLARIFICATION_POST_TRUST_V33": (
        "P1 Overall clarification effect on post-crisis Trust",
        "Trust points",
    ),
    "P2_CONTENT_POST_TRUST_V33": (
        "P2 Rational minus Empathy effect on post-crisis Trust",
        "Trust points",
    ),
    "P3_TIMING_PRE_DELAY_TRUST_V33": (
        "P3 Immediate minus Delayed early Trust effect (T6–T9)",
        "Trust points",
    ),
    "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33": (
        "P4 Hub minus Random direct enterprise reach",
        "Proportion",
    ),
    "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33": (
        "P5 Overall clarification effect on expected repeat choice",
        "Expected focal-brand choice share",
    ),
    "S1_CONVERSION_SUPPORT_EXPECTED_REPEAT_CHOICE_V33": (
        "S1 Conversion-support effect on expected repeat choice",
        "Expected focal-brand choice share",
    ),
}

PRIMARY = (
    "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
    "P2_CONTENT_POST_TRUST_V33",
    "P3_TIMING_PRE_DELAY_TRUST_V33",
    "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
)


def _label(estimand_id: str) -> tuple[str, str]:
    return DISPLAY.get(str(estimand_id), (str(estimand_id), "Estimand units"))


def _plot_stage_a(local: pd.DataFrame, estimand_id: str, output: Path) -> str:
    df = local[local["estimand_id"].astype(str) == str(estimand_id)].copy()
    if df.empty:
        raise ValueError(f"Stage-A estimand not found: {estimand_id}")
    df["max_abs_delta"] = df[
        ["low_delta_from_baseline", "high_delta_from_baseline"]
    ].abs().max(axis=1)
    df = df.sort_values("max_abs_delta", ascending=True)

    title, unit = _label(estimand_id)
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    y = list(range(len(df)))
    ax.hlines(
        y,
        df["low_delta_from_baseline"],
        df["high_delta_from_baseline"],
        linewidth=2,
    )
    ax.scatter(df["low_delta_from_baseline"], y, label="Low − baseline")
    ax.scatter(df["high_delta_from_baseline"], y, label="High − baseline")
    ax.axvline(0.0, linewidth=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(df["parameter"])
    ax.set_xlabel(f"Signed change relative to frozen baseline ({unit})")
    ax.set_title(title + "\nStage-A OAT sensitivity; Fake LLM, T35")
    ax.legend(loc="best")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return str(output)


def _plot_morris(stats: pd.DataFrame, estimand_id: str, output: Path) -> str:
    df = stats[stats["estimand_id"].astype(str) == str(estimand_id)].copy()
    if df.empty:
        raise ValueError(f"Morris estimand not found: {estimand_id}")
    df = df.sort_values(["rank_mu_star", "parameter"])
    title, unit = _label(estimand_id)

    fig, ax = plt.subplots(figsize=(8.5, 6.2))
    ax.scatter(df["mu_star"], df["sigma"], s=58)
    for row in df.itertuples(index=False):
        ax.annotate(
            str(row.parameter),
            (float(row.mu_star), float(row.sigma)),
            fontsize=8,
            xytext=(5, 4),
            textcoords="offset points",
        )
    ax.set_xlabel(f"μ* — mean absolute elementary effect ({unit})")
    ax.set_ylabel(f"σ — SD of elementary effects ({unit})")
    ax.set_title(title + "\nMorris global screening; Fake LLM, T35")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return str(output)


def replot_sensitivity_suite(suite_dir: Path) -> dict:
    """Regenerate thesis-safe figures from an existing Stage-A or Morris suite."""

    suite_dir = Path(suite_dir).resolve()
    stage_a_path = suite_dir / "trust_sensitivity_local_effects.csv"
    morris_path = suite_dir / "morris_statistics.csv"
    out_dir = suite_dir / "figures_thesis"
    outputs: list[str] = []

    if stage_a_path.exists() and morris_path.exists():
        raise ValueError(
            "suite contains both Stage-A and Morris statistics; use separate suite directories"
        )
    if stage_a_path.exists():
        mode = "stage-a-oat"
        local = pd.read_csv(stage_a_path)
        for estimand_id in PRIMARY:
            outputs.append(
                _plot_stage_a(local, estimand_id, out_dir / f"{estimand_id}.png")
            )
    elif morris_path.exists():
        mode = "stage-b-morris"
        stats = pd.read_csv(morris_path)
        for estimand_id in PRIMARY:
            outputs.append(
                _plot_morris(stats, estimand_id, out_dir / f"{estimand_id}.png")
            )
    else:
        raise FileNotFoundError(
            "expected trust_sensitivity_local_effects.csv or morris_statistics.csv "
            f"under {suite_dir}"
        )

    manifest = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "mode": mode,
        "source_suite": str(suite_dir),
        "post_processing_only": True,
        "model_rerun_performed": False,
        "formal_inference_performed": False,
        "figure_correction": (
            "Stage-A signed low/high deviations are labelled as signed changes; "
            "human-readable estimand titles replace raw IDs"
        ),
        "figures": outputs,
    }
    manifest_path = out_dir / "sensitivity_figure_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest["manifest"] = str(manifest_path)
    return manifest
