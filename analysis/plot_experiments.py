"""
analysis/plot_experiments.py - TASK_004 metrics v4.0 analysis.

Primary objectives:
  - final_trust_gain_vs_control
  - post_scandal_auc_gain_vs_control
  - local_trust_effect_did_3

Supplementary analyses:
  - equal-weight ranking
  - weight sensitivity
  - early response and secondary harm diagnostics
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from metrics_calculator import (
    METRICS_SCHEMA_VERSION,
    V4_FIELDS,
    PRIMARY_OBJECTIVES_V4,
    compute_pareto_flags_v4,
    compute_equal_weight_ranking_v4,
    compute_ranking_sensitivity_v4,
)

RESULTS_DIR = os.path.join(ROOT, "results", "experiments", "latest")
OUTPUT_DIR = os.path.join(RESULTS_DIR, "figures")

plt.rcParams["font.sans-serif"] = ["SimHei", "Arial Unicode MS", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

CONTROL_EXP_ID = "NoClarification-Control"
CONTENT_LEVELS = ("rational-evidence", "emotional-empathy")
CHANNEL_LEVELS = ("hub", "random")
TIMING_LEVELS = ("immediate", "delayed")

CONTENT_COLORS = {"rational-evidence": "#2166ac", "emotional-empathy": "#d6604d"}
CHANNEL_COLORS = {"hub": "#4dac26", "random": "#7b3294"}
TIMING_COLORS = {"immediate": "#fc8d59", "delayed": "#4575b4"}

CONTENT_LABELS = {"rational-evidence": "Rational", "emotional-empathy": "Empathy"}
CHANNEL_LABELS = {"hub": "Hub", "random": "Random"}
TIMING_LABELS = {"immediate": "Immediate", "delayed": "Delayed"}

PRIMARY_LABELS = {
    "final_trust_gain_vs_control": "Final Trust Gain vs Control",
    "post_scandal_auc_gain_vs_control": "Post-Scandal AUC Gain vs Control",
    "local_trust_effect_did_3": "Local Trust Effect DID-3",
}
LEGACY_METRICS = ("delta_recovery", "auc_post_scandal", "steady_state_score")
LEGACY_LABELS = {
    "delta_recovery": "Delta Recovery",
    "auc_post_scandal": "AUC Post-Scandal",
    "steady_state_score": "Steady-State Trust",
}
DIAGNOSTIC_LABELS = {
    "early_trust_auc_gain_5": "Early Trust AUC Gain-5",
    "early_trust_gain_slope_5": "Early Trust Gain Slope-5",
    "secondary_harm_depth": "Secondary Harm Depth (0 is best; more negative is worse)",
    "negative_gain_tick_count": "Negative Gain Tick Count (lower is better)",
}


def _has_v4_fields(df: pd.DataFrame) -> bool:
    return all(field in df.columns for field in V4_FIELDS)


def _has_any_v4_field(df: pd.DataFrame) -> bool:
    return any(field in df.columns for field in V4_FIELDS)


def _load_and_validate_metadata_v4() -> dict:
    metadata_path = os.path.join(RESULTS_DIR, "run_metadata.json")
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"run_metadata.json is required: {metadata_path}")
    with open(metadata_path, encoding="utf-8") as f:
        metadata = json.load(f)
    if not isinstance(metadata, dict):
        raise ValueError("run_metadata.json must contain a JSON object")
    matrix = metadata.get("experiment_matrix")
    if not isinstance(matrix, dict):
        raise ValueError("run_metadata experiment_matrix must be an object")
    if matrix.get("matrix_version") != "3.0":
        raise ValueError("experiment_matrix.matrix_version must be 3.0")
    if matrix.get("condition_count") != 9:
        raise ValueError("experiment_matrix.condition_count must be 9")
    metrics = metadata.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("run_metadata metrics must be an object")
    if metrics.get("schema_version") != METRICS_SCHEMA_VERSION:
        raise ValueError(f"metrics.schema_version must be {METRICS_SCHEMA_VERSION}")
    return metadata


def _parse_is_control_value(value) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str):
        if value == "True":
            return True
        if value == "False":
            return False
    raise AssertionError(f"invalid is_control value: {value!r}")


def _with_control_flags(df: pd.DataFrame) -> pd.DataFrame:
    if "is_control" not in df.columns:
        raise AssertionError("summary.csv must contain is_control")
    rows = df.copy()
    rows["_is_control_bool"] = rows["is_control"].map(_parse_is_control_value)
    return rows


def _require_finite_numeric(series: pd.Series, name: str) -> pd.Series:
    converted = pd.to_numeric(series, errors="raise")
    values = converted.to_numpy(dtype=float)
    if converted.isna().any() or not np.isfinite(values).all():
        raise AssertionError(f"{name} must contain only finite numeric values")
    return converted


def _validate_summary_structure(df: pd.DataFrame) -> pd.DataFrame:
    required = [
        "exp_id",
        "content_factor",
        "channel_factor",
        "timing_factor",
        "is_control",
        "trust_gain_vs_control",
        *V4_FIELDS,
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise AssertionError(f"summary.csv missing required columns: {missing}")
    if len(df) != 9:
        raise AssertionError(f"summary.csv must contain exactly 9 rows, found {len(df)}")
    if df["exp_id"].isna().any() or not all(isinstance(x, str) and x for x in df["exp_id"]):
        raise AssertionError("summary.csv exp_id values must be non-empty strings")
    if len(set(df["exp_id"])) != 9:
        raise AssertionError("summary.csv exp_id values must be unique")

    checked = _with_control_flags(df)
    controls = checked[checked["_is_control_bool"]]
    strategies = checked[~checked["_is_control_bool"]]
    if len(controls) != 1 or len(strategies) != 8:
        raise AssertionError("summary.csv must contain exactly 1 control and 8 strategies")

    control = controls.iloc[0]
    if control["exp_id"] != CONTROL_EXP_ID:
        raise AssertionError(f"control exp_id must be {CONTROL_EXP_ID}")
    expected_control = {
        "content_factor": "not-applicable",
        "channel_factor": "not-applicable",
        "timing_factor": "no-clarification",
    }
    for col, expected in expected_control.items():
        if control[col] != expected:
            raise AssertionError(f"control {col} must be {expected}")

    if strategies["content_factor"].isin(["not-applicable"]).any():
        raise AssertionError("strategy content_factor must not be not-applicable")
    if strategies["channel_factor"].isin(["not-applicable"]).any():
        raise AssertionError("strategy channel_factor must not be not-applicable")
    if not set(strategies["content_factor"]).issubset(set(CONTENT_LEVELS)):
        raise AssertionError("strategy content_factor contains invalid levels")
    if not set(strategies["channel_factor"]).issubset(set(CHANNEL_LEVELS)):
        raise AssertionError("strategy channel_factor contains invalid levels")
    if not set(strategies["timing_factor"]).issubset(set(TIMING_LEVELS)):
        raise AssertionError("strategy timing_factor contains invalid levels")

    checked["trust_gain_vs_control"] = _require_finite_numeric(
        checked["trust_gain_vs_control"], "trust_gain_vs_control"
    )
    for field in ("final_trust_gain_vs_control", "post_scandal_auc_gain_vs_control"):
        checked[field] = _require_finite_numeric(checked[field], field)

    control_idx = controls.index[0]
    control_final = float(checked.loc[control_idx, "final_trust_gain_vs_control"])
    control_auc = float(checked.loc[control_idx, "post_scandal_auc_gain_vs_control"])
    if abs(control_final) > 1e-12:
        raise AssertionError("control final_trust_gain_vs_control must be 0")
    if abs(control_auc) > 1e-12:
        raise AssertionError("control post_scandal_auc_gain_vs_control must be 0")

    for field in V4_FIELDS[2:]:
        control_value = checked.loc[control_idx, field]
        if not pd.isna(control_value):
            raise AssertionError(f"control {field} must be empty")
        checked.loc[strategies.index, field] = _require_finite_numeric(
            checked.loc[strategies.index, field], field
        )

    for field in V4_FIELDS:
        strategy_values = checked.loc[strategies.index, field]
        converted = pd.to_numeric(strategy_values, errors="raise")
        if converted.isna().any() or not np.isfinite(converted.to_numpy(dtype=float)).all():
            raise AssertionError(f"strategy rows contain invalid v4 values in {field}")
        checked.loc[strategies.index, field] = converted

    alias_delta = (
        checked["trust_gain_vs_control"].astype(float)
        - checked["final_trust_gain_vs_control"].astype(float)
    ).abs()
    if (alias_delta > 1e-12).any():
        raise AssertionError("trust_gain_vs_control must equal final_trust_gain_vs_control")

    return checked.drop(columns=["_is_control_bool"], errors="ignore")


def load_data(*, require_v4: bool = False) -> pd.DataFrame:
    """Load summary data.

    require_v4=False exists only for TASK_003 frozen regression compatibility.
    Formal TASK_004 entry points must pass require_v4=True.
    """
    if require_v4:
        _load_and_validate_metadata_v4()
    path = os.path.join(RESULTS_DIR, "summary.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"summary.csv is required: {path}")
    df = pd.read_csv(path)
    if require_v4:
        return _validate_summary_structure(df)
    if _has_any_v4_field(df):
        _load_and_validate_metadata_v4()
        return _validate_summary_structure(df)
    return _validate_legacy_summary_for_task003(df)


def _validate_legacy_summary_for_task003(df: pd.DataFrame) -> pd.DataFrame:
    required = [
        "exp_id",
        "content_factor",
        "channel_factor",
        "timing_factor",
        "is_control",
        "trust_gain_vs_control",
        *LEGACY_METRICS,
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise AssertionError(f"legacy summary.csv missing required columns: {missing}")
    if len(df) != 9:
        raise AssertionError(f"legacy summary.csv must contain exactly 9 rows, found {len(df)}")
    checked = _with_control_flags(df)
    controls = checked[checked["_is_control_bool"]]
    strategies = checked[~checked["_is_control_bool"]]
    if len(controls) != 1 or len(strategies) != 8:
        raise AssertionError("legacy summary.csv must contain exactly 1 control and 8 strategies")
    control = controls.iloc[0]
    if control["exp_id"] != CONTROL_EXP_ID:
        raise AssertionError(f"legacy control exp_id must be {CONTROL_EXP_ID}")
    for col, expected in {
        "content_factor": "not-applicable",
        "channel_factor": "not-applicable",
        "timing_factor": "no-clarification",
    }.items():
        if control[col] != expected:
            raise AssertionError(f"legacy control {col} must be {expected}")
    if strategies["content_factor"].isin(["not-applicable"]).any():
        raise AssertionError("not-applicable leaked into legacy strategy content_factor")
    if strategies["channel_factor"].isin(["not-applicable"]).any():
        raise AssertionError("not-applicable leaked into legacy strategy channel_factor")
    for field in (*LEGACY_METRICS, "trust_gain_vs_control"):
        checked[field] = _require_finite_numeric(checked[field], field)
    return checked.drop(columns=["_is_control_bool"], errors="ignore")


def _strategy_rows(df: pd.DataFrame) -> pd.DataFrame:
    checked = _with_control_flags(df)
    rows = checked[~checked["_is_control_bool"]].copy()
    if len(rows) != 8:
        raise AssertionError(f"expected 8 strategy rows, found {len(rows)}")
    if rows["content_factor"].isin(["not-applicable"]).any():
        raise AssertionError("not-applicable leaked into strategy content_factor")
    if rows["channel_factor"].isin(["not-applicable"]).any():
        raise AssertionError("not-applicable leaked into strategy channel_factor")
    return rows.drop(columns=["_is_control_bool"], errors="ignore")


def _control_row(df: pd.DataFrame) -> pd.Series:
    checked = _with_control_flags(df)
    controls = checked[checked["_is_control_bool"]].copy()
    if len(controls) != 1:
        raise AssertionError(f"expected 1 common control row, found {len(controls)}")
    row = controls.iloc[0]
    if row.get("exp_id") != CONTROL_EXP_ID:
        raise AssertionError(f"common control exp_id must be {CONTROL_EXP_ID}")
    return row.drop(labels=["_is_control_bool"], errors="ignore")


def _strategy_records_v4(df: pd.DataFrame) -> list[dict]:
    rows = _strategy_rows(df)
    records = []
    for _, row in rows.iterrows():
        record = {
            "exp_id": row["exp_id"],
            "is_control": False,
        }
        for field in PRIMARY_OBJECTIVES_V4:
            record[field] = float(row[field])
        records.append(record)
    if len(records) != 8:
        raise AssertionError("expected 8 v4 strategy records")
    return records


def _ensure_output_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _bar_group(ax, df: pd.DataFrame, factor_col: str, metric_col: str, labels_map: dict, colors_map: dict):
    grouped = df.groupby(factor_col, sort=False)[metric_col].agg(["mean", "std"])
    levels = list(grouped.index)
    means = [float(grouped.loc[level, "mean"]) for level in levels]
    stds = [0.0 if pd.isna(grouped.loc[level, "std"]) else float(grouped.loc[level, "std"]) for level in levels]
    bars = ax.bar(
        [labels_map.get(level, level) for level in levels],
        means,
        yerr=stds,
        color=[colors_map.get(level, "#888888") for level in levels],
        alpha=0.85,
        edgecolor="white",
        linewidth=1.2,
        capsize=4,
    )
    if max(means) != min(means):
        span = max(means) - min(means)
        ax.set_ylim(min(means) - span * 0.25, max(means) + span * 0.35)
    for bar, val in zip(bars, means):
        ylim = ax.get_ylim()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + (ylim[1] - ylim[0]) * 0.02,
            f"{val:.3f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    ax.grid(axis="y", linestyle=":", alpha=0.35)
    ax.tick_params(axis="x", labelsize=8)


def plot_main_effects(df: pd.DataFrame):
    _ensure_output_dir()
    strategy = _strategy_rows(df)
    use_v4 = _has_v4_fields(strategy)
    metrics = list(PRIMARY_OBJECTIVES_V4 if use_v4 else LEGACY_METRICS)
    factors = [
        ("content_factor", "Content", CONTENT_LABELS, CONTENT_COLORS),
        ("channel_factor", "Channel", CHANNEL_LABELS, CHANNEL_COLORS),
        ("timing_factor", "Timing", TIMING_LABELS, TIMING_COLORS),
    ]
    fig, axes = plt.subplots(3, 3, figsize=(15, 11))
    title = "Main Effects: Control-Relative v4 Metrics" if use_v4 else "Main Effects: TASK_003 Legacy Audit Metrics"
    fig.suptitle(title, fontsize=14, fontweight="bold")
    for row_idx, (factor_col, factor_label, labels_map, colors_map) in enumerate(factors):
        for col_idx, metric_col in enumerate(metrics):
            ax = axes[row_idx][col_idx]
            _bar_group(ax, strategy, factor_col, metric_col, labels_map, colors_map)
            if row_idx == 0:
                labels = PRIMARY_LABELS if use_v4 else LEGACY_LABELS
                ax.set_title(labels[metric_col], fontsize=10, fontweight="bold")
            if col_idx == 0:
                ylabel = "control-relative v4" if use_v4 else "legacy audit"
                ax.set_ylabel(f"{factor_label}\n{ylabel}", fontsize=9)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig1_main_effects.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved fig1: {out}")


def _interaction_pivot(df: pd.DataFrame, row_f: str, col_f: str, metric_col: str) -> pd.DataFrame:
    pivot = df.pivot_table(index=row_f, columns=col_f, values=metric_col, aggfunc="mean")
    expected_rows = CONTENT_LEVELS if row_f == "content_factor" else CHANNEL_LEVELS
    expected_cols = TIMING_LEVELS if col_f == "timing_factor" else CHANNEL_LEVELS
    if col_f == "content_factor":
        expected_cols = CONTENT_LEVELS
    if row_f == "timing_factor":
        expected_rows = TIMING_LEVELS
    pivot = pivot.reindex(index=expected_rows, columns=expected_cols)
    if pivot.shape != (2, 2) or pivot.isna().any().any():
        raise AssertionError(f"interaction pivot for {row_f} x {col_f} is not a complete 2x2")
    return pivot


def plot_heatmap_interactions(df: pd.DataFrame):
    _ensure_output_dir()
    strategy = _strategy_rows(df)
    use_v4 = _has_v4_fields(strategy)
    metrics = list(PRIMARY_OBJECTIVES_V4 if use_v4 else LEGACY_METRICS)
    interactions = [
        ("content_factor", "timing_factor", "Content x Timing"),
        ("channel_factor", "timing_factor", "Channel x Timing"),
        ("content_factor", "channel_factor", "Content x Channel"),
    ]
    label_maps = {
        "content_factor": CONTENT_LABELS,
        "channel_factor": CHANNEL_LABELS,
        "timing_factor": TIMING_LABELS,
    }
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    title = "Interaction Effects: Control-Relative v4 Metrics" if use_v4 else "Interaction Effects: TASK_003 Legacy Audit Metrics"
    fig.suptitle(title, fontsize=14, fontweight="bold")
    for row_idx, metric_col in enumerate(metrics):
        for col_idx, (row_f, col_f, title) in enumerate(interactions):
            ax = axes[row_idx][col_idx]
            pivot = _interaction_pivot(strategy, row_f, col_f, metric_col)
            im = ax.imshow(pivot.values.astype(float), cmap="RdYlGn", aspect="auto")
            ax.set_xticks(range(2))
            ax.set_yticks(range(2))
            ax.set_xticklabels([label_maps[col_f].get(x, x) for x in pivot.columns], fontsize=8, rotation=20, ha="right")
            ax.set_yticklabels([label_maps[row_f].get(x, x) for x in pivot.index], fontsize=8)
            labels = PRIMARY_LABELS if use_v4 else LEGACY_LABELS
            ax.set_title(f"{labels[metric_col]}\n{title}", fontsize=9, fontweight="bold")
            for i in range(2):
                for j in range(2):
                    ax.text(j, i, f"{pivot.values[i, j]:.3f}", ha="center", va="center", fontsize=9)
            plt.colorbar(im, ax=ax, shrink=0.75)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig2_interactions.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved fig2: {out}")


def plot_pareto_frontier(df: pd.DataFrame):
    _ensure_output_dir()
    strategy = _strategy_rows(df).copy()
    if not _has_v4_fields(strategy):
        strategy["is_pareto"] = False
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.scatter(strategy["delta_recovery"], strategy["auc_post_scandal"], color="#9ecae1", s=80)
        for _, row in strategy.iterrows():
            ax.annotate(row["exp_id"], (row["delta_recovery"], row["auc_post_scandal"]), fontsize=7)
        ax.set_title("TASK_003 Legacy Pareto Audit View", fontsize=12, fontweight="bold")
        ax.set_xlabel("Delta Recovery")
        ax.set_ylabel("AUC Post-Scandal")
        ax.grid(True, linestyle=":", alpha=0.35)
        out = os.path.join(OUTPUT_DIR, "fig3_pareto.png")
        plt.savefig(out, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"  saved fig3: {out}")
        return strategy
    pareto_rows = compute_pareto_flags_v4(_strategy_records_v4(df))
    pareto_flags = {row["exp_id"]: bool(row["is_pareto"]) for row in pareto_rows}
    strategy["is_pareto"] = strategy["exp_id"].map(pareto_flags)
    if strategy["is_pareto"].isna().any():
        raise AssertionError("Pareto API did not return every strategy exp_id")

    projections = [
        ("final_trust_gain_vs_control", "post_scandal_auc_gain_vs_control"),
        ("final_trust_gain_vs_control", "local_trust_effect_did_3"),
        ("post_scandal_auc_gain_vs_control", "local_trust_effect_did_3"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("Pareto Frontier: Control-Relative v4 Primary Objectives", fontsize=14, fontweight="bold")
    for ax, (x_col, y_col) in zip(axes, projections):
        x_range = max(float(strategy[x_col].max() - strategy[x_col].min()), 1e-6)
        y_range = max(float(strategy[y_col].max() - strategy[y_col].min()), 1e-6)
        for idx, (_, row) in enumerate(strategy.iterrows()):
            is_pareto = bool(row["is_pareto"])
            ax.scatter(
                row[x_col],
                row[y_col],
                c="#d62728" if is_pareto else "#9ecae1",
                s=170 if is_pareto else 75,
                edgecolors="#8B0000" if is_pareto else "none",
                linewidths=1.3,
                alpha=0.9,
                zorder=10 if is_pareto else 5,
            )
            dy = y_range * 0.05 * (1 if idx % 2 == 0 else -1)
            ax.annotate(
                row["exp_id"],
                (row[x_col], row[y_col]),
                xytext=(row[x_col] + x_range * 0.02, row[y_col] + dy),
                fontsize=6.5,
                alpha=0.9,
            )
        ax.set_xlabel(PRIMARY_LABELS[x_col], fontsize=9)
        ax.set_ylabel(PRIMARY_LABELS[y_col], fontsize=9)
        ax.grid(True, linestyle=":", alpha=0.35)
    axes[0].legend(
        handles=[
            mpatches.Patch(color="#d62728", label="Pareto"),
            mpatches.Patch(color="#9ecae1", label="Non-Pareto"),
        ],
        fontsize=9,
    )
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig3_pareto.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved fig3: {out}")

    pareto_df = strategy[strategy["is_pareto"]].sort_values("exp_id")
    print(f"\n  Pareto optimal ({len(pareto_df)}):")
    print(f"  {'exp_id':<25} {'Final':>10} {'AUC':>10} {'Local DID':>10}")
    for _, row in pareto_df.iterrows():
        print(
            f"  {row['exp_id']:<25} "
            f"{row['final_trust_gain_vs_control']:>10.4f} "
            f"{row['post_scandal_auc_gain_vs_control']:>10.4f} "
            f"{row['local_trust_effect_did_3']:>10.4f}"
        )
    return strategy


def plot_strategy_ranking(df: pd.DataFrame):
    _ensure_output_dir()
    if not _has_v4_fields(df):
        strategy = _strategy_rows(df).copy().sort_values("trust_gain_vs_control", ascending=True)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(strategy["exp_id"], strategy["trust_gain_vs_control"], color="#9ecae1", alpha=0.85)
        ax.set_title("TASK_003 Legacy Ranking Audit View", fontsize=12, fontweight="bold")
        ax.set_xlabel("Trust Gain vs Control")
        ax.grid(axis="x", linestyle=":", alpha=0.35)
        out = os.path.join(OUTPUT_DIR, "fig4_ranking.png")
        plt.savefig(out, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"  saved fig4: {out}")
        return
    ranked = compute_equal_weight_ranking_v4(_strategy_records_v4(df))
    ranked_df = pd.DataFrame(ranked)
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_title("Supplementary Equal-Weight Ranking", fontsize=13, fontweight="bold")
    bars = ax.barh(ranked_df["exp_id"], ranked_df["score_equal"], color="#4dac26", alpha=0.85, edgecolor="white")
    for bar, score, rank in zip(bars, ranked_df["score_equal"], ranked_df["rank"]):
        ax.text(
            bar.get_width() + 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{score:.3f} (rank {rank:g})",
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Equal-weight score over v4 primary objectives", fontsize=10)
    ax.set_xlim(0, max(1.0, float(ranked_df["score_equal"].max()) * 1.18))
    ax.invert_yaxis()
    ax.grid(axis="x", linestyle=":", alpha=0.35)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig4_ranking.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved fig4: {out}")


def plot_clarification_diagnosis(df: pd.DataFrame):
    _ensure_output_dir()
    strategy = _strategy_rows(df).copy().sort_values("exp_id")
    if not _has_v4_fields(strategy):
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(strategy["exp_id"], strategy["trust_gain_vs_control"], color="#9ecae1", alpha=0.85)
        ax.set_title("TASK_003 Legacy Clarification Audit View", fontsize=12, fontweight="bold")
        ax.set_ylabel("Trust Gain vs Control")
        ax.tick_params(axis="x", labelrotation=45, labelsize=7)
        ax.grid(axis="y", linestyle=":", alpha=0.35)
        out = os.path.join(OUTPUT_DIR, "fig5_clarification_diagnosis.png")
        plt.savefig(out, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"  saved fig5: {out}")
        return
    metrics = [
        "early_trust_auc_gain_5",
        "early_trust_gain_slope_5",
        "secondary_harm_depth",
        "negative_gain_tick_count",
    ]
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    fig.suptitle("v4 Clarification Diagnostics: Early Response and Secondary Harm", fontsize=14, fontweight="bold")
    for ax, metric_col in zip(axes.flat, metrics):
        values = pd.to_numeric(strategy[metric_col], errors="raise")
        color = "#2166ac" if metric_col in metrics[:2] else "#d6604d"
        ax.bar(strategy["exp_id"], values, color=color, alpha=0.85, edgecolor="white")
        ax.set_title(DIAGNOSTIC_LABELS[metric_col], fontsize=10, fontweight="bold")
        ax.tick_params(axis="x", labelrotation=45, labelsize=7)
        ax.grid(axis="y", linestyle=":", alpha=0.35)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig5_clarification_diagnosis.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved fig5: {out}")


def plot_ranking_sensitivity_v4(df: pd.DataFrame):
    _ensure_output_dir()
    if not _has_v4_fields(df):
        strategy = _strategy_rows(df).copy().sort_values("exp_id")
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(
            0.5,
            0.5,
            "TASK_003 legacy summary: v4 sensitivity not applicable",
            ha="center",
            va="center",
            fontsize=12,
        )
        ax.set_axis_off()
        out = os.path.join(OUTPUT_DIR, "fig6_ranking_sensitivity.png")
        plt.savefig(out, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"  saved fig6: {out}")
        return
    sensitivity_rows, robustness_rows = compute_ranking_sensitivity_v4(_strategy_records_v4(df))
    if len(sensitivity_rows) != 528:
        raise AssertionError(f"expected 528 sensitivity rows, got {len(sensitivity_rows)}")
    if len(robustness_rows) != 8:
        raise AssertionError(f"expected 8 robustness rows, got {len(robustness_rows)}")
    robustness = pd.DataFrame(robustness_rows).sort_values("exp_id")

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("Supplementary Sensitivity Analysis: v4 Objective Weights", fontsize=14, fontweight="bold")

    axes[0].bar(robustness["exp_id"], robustness["top1_share"], color="#2166ac", alpha=0.85)
    axes[0].set_title("Top-1 Share", fontsize=10, fontweight="bold")
    axes[0].set_ylim(0, max(1.0, float(robustness["top1_share"].max()) * 1.15))

    axes[1].bar(robustness["exp_id"], robustness["mean_rank"], color="#4dac26", alpha=0.85)
    axes[1].set_title("Mean Rank", fontsize=10, fontweight="bold")
    axes[1].invert_yaxis()

    y_pos = np.arange(len(robustness))
    axes[2].hlines(y_pos, robustness["best_rank"], robustness["worst_rank"], color="#d6604d", linewidth=3, alpha=0.8)
    axes[2].scatter(robustness["mean_rank"], y_pos, color="#000000", s=25, zorder=3)
    axes[2].set_yticks(y_pos)
    axes[2].set_yticklabels(robustness["exp_id"], fontsize=7)
    axes[2].set_title("Best-to-Worst Rank Range", fontsize=10, fontweight="bold")
    axes[2].invert_xaxis()

    for ax in axes[:2]:
        ax.tick_params(axis="x", labelrotation=45, labelsize=7)
        ax.grid(axis="y", linestyle=":", alpha=0.35)
    axes[2].grid(axis="x", linestyle=":", alpha=0.35)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig6_ranking_sensitivity.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved fig6: {out}")


def print_summary_table(df: pd.DataFrame):
    strategy = _strategy_rows(df).sort_values("exp_id")
    if not _has_v4_fields(strategy):
        print(f"\n{'=' * 100}")
        print("Experiment Summary: TASK_003 Legacy Audit Metrics")
        print(f"{'=' * 100}")
        return
    print(f"\n{'=' * 100}")
    print("Experiment Summary: TASK_004 v4 Primary Objectives")
    print(f"{'=' * 100}")
    print(f"{'Strategy':<25} {'Content':<18} {'Channel':<8} {'Timing':<10} {'Final':>10} {'AUC':>10} {'Local DID':>10}")
    print(f"{'-' * 100}")
    for _, row in strategy.iterrows():
        print(
            f"{row['exp_id']:<25} "
            f"{CONTENT_LABELS.get(row['content_factor'], row['content_factor']):<18} "
            f"{CHANNEL_LABELS.get(row['channel_factor'], row['channel_factor']):<8} "
            f"{TIMING_LABELS.get(row['timing_factor'], row['timing_factor']):<10} "
            f"{row['final_trust_gain_vs_control']:>10.4f} "
            f"{row['post_scandal_auc_gain_vs_control']:>10.4f} "
            f"{row['local_trust_effect_did_3']:>10.4f}"
        )


def main():
    print(f"loading TASK_004 v4 data: {os.path.join(RESULTS_DIR, 'summary.csv')}")
    df = load_data(require_v4=True)
    print(f"   loaded {len(df)} experiment rows")
    print_summary_table(df)
    print("\ngenerating figures...")
    plot_main_effects(df)
    plot_heatmap_interactions(df)
    plot_pareto_frontier(df)
    plot_strategy_ranking(df)
    plot_clarification_diagnosis(df)
    plot_ranking_sensitivity_v4(df)
    print(f"\nall figures saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
