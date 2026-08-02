"""Trajectory visualizations for the TASK_003 v3.0 experiment matrix."""

import os
import sys
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results", "experiments", "latest")
OUTPUT_DIR = os.path.join(RESULTS_DIR, "figures")

plt.rcParams["font.sans-serif"] = ["SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

TIMING_STYLE = {
    "immediate": {"color": "#d62728", "ls": "-", "lw": 2.5, "label": "Immediate"},
    "delayed": {"color": "#ff7f0e", "ls": "--", "lw": 2.2, "label": "Delayed"},
}
CONTROL_STYLE = {
    "color": "#1f77b4",
    "ls": ":",
    "lw": 2.0,
    "label": "Common control",
}
CONTENT_STYLE = {
    "rational-evidence": {"color": "#2166ac", "ls": "-", "lw": 2.5, "label": "Rational"},
    "emotional-empathy": {"color": "#d6604d", "ls": "--", "lw": 2.5, "label": "Empathy"},
}
CHANNEL_STYLE = {
    "hub": {"color": "#4dac26", "ls": "-", "lw": 2.5, "label": "Hub"},
    "random": {"color": "#984ea3", "ls": "--", "lw": 2.2, "label": "Random"},
}

CONTROL_EXP_ID = "NoClarification-Control"
EVENTS = {5: "Blackstone"}


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
        raise AssertionError("trajectories.csv must contain is_control")
    rows = df.copy()
    rows["_is_control_bool"] = rows["is_control"].map(_parse_is_control_value)
    return rows


def _assert_v3_metadata() -> None:
    metadata_path = os.path.join(RESULTS_DIR, "run_metadata.json")
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"run_metadata.json is required: {metadata_path}")
    with open(metadata_path, encoding="utf-8") as f:
        meta = json.load(f)
    matrix = meta.get("experiment_matrix", {})
    if matrix.get("matrix_version") != "3.0" or matrix.get("condition_count") != 9:
        raise ValueError("legacy experiment_matrix metadata cannot be analyzed as v3.0")


def _strategy_rows(df: pd.DataFrame) -> pd.DataFrame:
    checked = _with_control_flags(df)
    rows = checked[~checked["_is_control_bool"]].copy()
    for col in ("content_factor", "channel_factor"):
        if "not-applicable" in set(rows[col]):
            raise AssertionError(
                "'not-applicable' leaked into strategy rows via %s: is_control filter failed"
                % col
            )
    return rows.drop(columns=["_is_control_bool"], errors="ignore")


def _control_rows(df: pd.DataFrame) -> pd.DataFrame:
    checked = _with_control_flags(df)
    rows = checked[checked["_is_control_bool"]].copy()
    exp_ids = set(rows["exp_id"].dropna())
    if exp_ids != {CONTROL_EXP_ID}:
        raise AssertionError(f"control trajectories must belong only to {CONTROL_EXP_ID}")
    for col, expected in (
        ("content_factor", "not-applicable"),
        ("channel_factor", "not-applicable"),
        ("timing_factor", "no-clarification"),
    ):
        values = set(rows[col].dropna())
        if values != {expected}:
            raise AssertionError(f"control {col} must be {expected}, got {sorted(values)}")
    return rows.drop(columns=["_is_control_bool"], errors="ignore")


def load_trajectories() -> pd.DataFrame:
    path = os.path.join(RESULTS_DIR, "trajectories.csv")
    _assert_v3_metadata()
    if not os.path.exists(path):
        print(f"missing trajectories.csv: {path}")
        sys.exit(1)
    df = pd.read_csv(path)
    _with_control_flags(df)
    print(f"loaded trajectories: {len(df)} rows, {df['exp_id'].nunique()} conditions")
    return df


def _add_events(ax, max_tick: int):
    ymin, ymax = ax.get_ylim()
    for tick, label in EVENTS.items():
        if tick <= max_tick:
            ax.axvline(x=tick, color="gray", linestyle="--", alpha=0.35, linewidth=0.8)
            ax.text(tick + 0.15, ymin + (ymax - ymin) * 0.03, label,
                    fontsize=7, color="dimgray", rotation=90, va="bottom")


def _add_clarification_markers(ax, max_tick: int):
    ymin, ymax = ax.get_ylim()
    for tick, label in ((6, "Immediate clarification"), (10, "Delayed clarification")):
        if tick <= max_tick:
            ax.axvline(x=tick, color="green", linestyle="-", alpha=0.35, linewidth=1.0)
            ax.text(tick + 0.15, ymin + (ymax - ymin) * 0.12, label,
                    fontsize=7, color="darkgreen", rotation=90, va="bottom")


def _add_relative_clarification_markers(ax):
    ymin, ymax = ax.get_ylim()
    for relative, label in ((1, "Immediate clarification"), (5, "Delayed clarification")):
        ax.axvline(x=relative, color="green", linestyle="-", alpha=0.35, linewidth=1.0)
        ax.text(relative + 0.1, ymin + (ymax - ymin) * 0.12, label,
                fontsize=7, color="darkgreen", rotation=90, va="bottom")


def plot_timing_comparison(df: pd.DataFrame):
    strategy = _strategy_rows(df)
    max_tick = int(df["tick"].max())
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Timing Main Effect", fontsize=13, fontweight="bold")
    for ax, metric, ylabel in (
        (axes[0], "avg_trust", "Average trust"),
        (axes[1], "conversion_rate", "Conversion rate"),
    ):
        for timing, style in TIMING_STYLE.items():
            raw = strategy[strategy["timing_factor"] == timing].groupby("tick")[metric].mean()
            ax.plot(raw.index, raw.values, color=style["color"], linestyle=style["ls"],
                    linewidth=style["lw"], label=style["label"])
        _add_events(ax, max_tick)
        _add_clarification_markers(ax, max_tick)
        ax.set_xlim(1, max_tick)
        ax.set_xlabel("Tick")
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle=":", alpha=0.4)
        ax.legend()
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "line_timing_effect.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


def plot_content_channel_comparison(df: pd.DataFrame):
    strategy = _strategy_rows(df)
    control = _control_rows(df)
    max_tick = int(df["tick"].max())
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Content And Channel Effects", fontsize=13, fontweight="bold")
    comparisons = [
        (axes[0, 0], "content_factor", CONTENT_STYLE, "avg_trust", "Content / trust"),
        (axes[0, 1], "content_factor", CONTENT_STYLE, "conversion_rate", "Content / conversion"),
        (axes[1, 0], "channel_factor", CHANNEL_STYLE, "avg_trust", "Channel / trust"),
        (axes[1, 1], "channel_factor", CHANNEL_STYLE, "conversion_rate", "Channel / conversion"),
    ]
    for ax, factor_col, style_map, metric, title in comparisons:
        ctrl = control.groupby("tick")[metric].mean()
        if not ctrl.empty:
            ax.plot(ctrl.index, ctrl.values, color=CONTROL_STYLE["color"],
                    linestyle=CONTROL_STYLE["ls"], linewidth=CONTROL_STYLE["lw"],
                    label=CONTROL_STYLE["label"])
        for level, style in style_map.items():
            raw = strategy[strategy[factor_col] == level].groupby("tick")[metric].mean()
            ax.plot(raw.index, raw.values, color=style["color"], linestyle=style["ls"],
                    linewidth=style["lw"], label=style["label"])
        _add_events(ax, max_tick)
        _add_clarification_markers(ax, max_tick)
        ax.set_xlim(1, max_tick)
        ax.set_title(title)
        ax.set_xlabel("Tick")
        ax.grid(True, linestyle=":", alpha=0.4)
        ax.legend(fontsize=9)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "line_content_channel.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


def plot_all_9_conditions(df: pd.DataFrame):
    max_tick = int(df["tick"].max())
    fig, ax = plt.subplots(figsize=(13, 7))
    for exp_id, sub in df.groupby("exp_id"):
        is_control = _parse_is_control_value(sub["is_control"].iloc[0])
        if is_control:
            style = CONTROL_STYLE
        else:
            style = TIMING_STYLE.get(sub["timing_factor"].iloc[0], CONTROL_STYLE)
        ax.plot(sub["tick"], sub["avg_trust"], linestyle=style["ls"],
                linewidth=style["lw"] if is_control else 1.8,
                color=style["color"], alpha=0.9, label=exp_id)
    _add_events(ax, max_tick)
    _add_clarification_markers(ax, max_tick)
    ax.set_xlim(1, max_tick)
    ax.set_ylim(0, 10)
    ax.set_xlabel("Tick")
    ax.set_ylabel("Average trust")
    ax.grid(True, linestyle=":", alpha=0.35)
    ax.legend(fontsize=7, ncol=2)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "line_all_9_conditions.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


def plot_trust_recovery_zoom(df: pd.DataFrame):
    strategy = _strategy_rows(df)
    control = _control_rows(df)
    scandal_tick = 5
    fig, ax = plt.subplots(figsize=(12, 6))
    post_strategy = strategy[strategy["tick"] >= scandal_tick].copy()
    post_strategy["relative_tick"] = post_strategy["tick"] - scandal_tick
    post_control = control[control["tick"] >= scandal_tick].copy()
    post_control["relative_tick"] = post_control["tick"] - scandal_tick
    ctrl = post_control.groupby("relative_tick")["avg_trust"].mean()
    if not ctrl.empty:
        ax.plot(ctrl.index, ctrl.values, color=CONTROL_STYLE["color"],
                linestyle=CONTROL_STYLE["ls"], linewidth=CONTROL_STYLE["lw"],
                label=CONTROL_STYLE["label"])
    for timing, style in (("delayed", TIMING_STYLE["delayed"]),
                          ("immediate", TIMING_STYLE["immediate"])):
        raw = post_strategy[post_strategy["timing_factor"] == timing].groupby(
            "relative_tick"
        )["avg_trust"].mean()
        ax.plot(raw.index, raw.values, color=style["color"], linestyle=style["ls"],
                linewidth=style["lw"], label=style["label"])
    ax.axvline(x=0, color="#8B0000", linestyle="-", linewidth=1.5, alpha=0.75)
    _add_relative_clarification_markers(ax)
    ax.set_xlabel("Ticks after scandal")
    ax.set_ylabel("Average trust")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend()
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "line_recovery_zoom.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = load_trajectories()
    plot_timing_comparison(df)
    plot_content_channel_comparison(df)
    plot_all_9_conditions(df)
    plot_trust_recovery_zoom(df)
    print(f"all trajectory figures saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
