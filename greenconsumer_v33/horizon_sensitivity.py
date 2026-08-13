"""Pre-specified finite-horizon robustness suite for TASK_005 v3.3.1.

This suite is deliberately Fake-LLM only.  It evaluates whether the 30/35/40
observation horizons alter descriptive conclusions and verifies a stronger
implementation invariant: extending the run horizon must not change any earlier
cognitive trajectory when seeds and mechanisms are unchanged.

No p-values, confidence intervals, model tuning, or formal inference are
performed here.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from greenconsumer_v32.config import (
    DEFAULT_DEMAND_SEED,
    DEFAULT_LLM_SEED,
    DEFAULT_SIMULATION_SEED,
    PROJECT_ROOT,
)

from .analysis import analyze_run
from .config import HORIZON_ROBUSTNESS_TICKS, RunSettings
from .runner import execute
from .visualization import plot_run

SUITE_SCHEMA = "task005_fmcg_v331_horizon_sensitivity1.0"


def _read_sorted_cognitive(run_dir: Path, max_tick: int) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "cognitive_records.csv")
    df["tick"] = pd.to_numeric(df["tick"], errors="raise").astype(int)
    df = df[df["tick"] <= int(max_tick)].copy()
    keys = [c for c in ["exp_id", "tick", "agent_id"] if c in df.columns]
    return df.sort_values(keys).reset_index(drop=True)


def _prefix_compare(left_dir: Path, right_dir: Path, max_tick: int) -> dict:
    left = _read_sorted_cognitive(left_dir, max_tick)
    right = _read_sorted_cognitive(right_dir, max_tick)
    common = [c for c in left.columns if c in right.columns]
    left = left[common]
    right = right[common]
    try:
        pd.testing.assert_frame_equal(
            left,
            right,
            check_dtype=False,
            check_exact=True,
        )
        status = "PASS"
        detail = "exact equality"
    except AssertionError as exc:
        status = "FAIL"
        detail = str(exc).splitlines()[0][:500]
    return {
        "left_run": left_dir.name,
        "right_run": right_dir.name,
        "prefix_end_tick": int(max_tick),
        "rows_left": len(left),
        "rows_right": len(right),
        "common_columns": len(common),
        "status": status,
        "detail": detail,
    }


def _read_estimands(run_dir: Path, horizon: int) -> pd.DataFrame:
    path = run_dir / "single_block_estimands.csv"
    df = pd.read_csv(path)
    df.insert(0, "horizon_tick", int(horizon))
    df.insert(1, "horizon_role", "baseline-primary-horizon" if int(horizon) == 35 else "horizon-robustness")
    df.insert(2, "run_id", run_dir.name)
    return df


def _plot_estimand(df: pd.DataFrame, estimand_id: str, output: Path) -> str | None:
    part = df[df["estimand_id"].astype(str) == estimand_id].copy()
    if part.empty:
        return None
    part["horizon_tick"] = pd.to_numeric(part["horizon_tick"], errors="raise")
    part["value"] = pd.to_numeric(part["value"], errors="raise")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(part["horizon_tick"], part["value"], marker="o")
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xticks(list(HORIZON_ROBUSTNESS_TICKS))
    ax.set_xlabel("Pre-specified total Tick horizon")
    ax.set_ylabel(str(part["unit"].iloc[0]))
    ax.set_title(f"Horizon robustness: {estimand_id}")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return str(output)


def _sign_label(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def _stability_table(estimands: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for estimand_id, group in estimands.groupby("estimand_id"):
        g = group.sort_values("horizon_tick").copy()
        values = pd.to_numeric(g["value"], errors="coerce")
        signs = [_sign_label(float(v)) for v in values]
        rows.append({
            "estimand_id": estimand_id,
            "horizons": ";".join(str(int(x)) for x in g["horizon_tick"]),
            "values": ";".join(f"{float(x):.12g}" for x in values),
            "signs": ";".join(signs),
            "sign_stable": len(set(signs)) == 1,
            "min_value": values.min(),
            "max_value": values.max(),
            "range": values.max() - values.min(),
            "interpretation": (
                "descriptive horizon stability only; sign changes are boundary evidence, not a reason to select another endpoint"
            ),
        })
    return pd.DataFrame(rows)


async def run_horizon_suite(
    *,
    output_root: Path = PROJECT_ROOT / "results" / "v33_horizon_sensitivity",
    simulation_seed: int = DEFAULT_SIMULATION_SEED,
    llm_seed: int = DEFAULT_LLM_SEED,
    demand_seed: int = DEFAULT_DEMAND_SEED,
) -> dict:
    """Run the pre-specified 30/35/40 Fake-LLM horizon suite."""

    suite_id = dt.datetime.now().strftime("horizon_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)

    run_dirs: dict[int, Path] = {}
    analysis_payloads = {}
    estimand_frames = []

    for horizon in HORIZON_ROBUSTNESS_TICKS:
        settings = RunSettings(
            llm_mode="fake",
            condition="all",
            simulation_seed=simulation_seed,
            requested_llm_seed=llm_seed,
            demand_seed=demand_seed,
            output_dir=suite_dir / f"T{horizon}",
            run_demand=True,
            support_mode="both",
            allow_real_llm=False,
            total_ticks=int(horizon),
        )
        payload = await execute(settings)
        run_dir = Path(payload["output_dir"])
        run_dirs[int(horizon)] = run_dir
        analysis_payloads[str(horizon)] = analyze_run(run_dir)
        plot_run(run_dir)
        estimand_frames.append(_read_estimands(run_dir, horizon))

    comparisons = [
        _prefix_compare(run_dirs[30], run_dirs[35], 30),
        _prefix_compare(run_dirs[30], run_dirs[40], 30),
        _prefix_compare(run_dirs[35], run_dirs[40], 35),
    ]
    prefix = pd.DataFrame(comparisons)
    prefix.to_csv(suite_dir / "prefix_invariance.csv", index=False, encoding="utf-8-sig")

    estimands = pd.concat(estimand_frames, ignore_index=True)
    estimands.to_csv(suite_dir / "horizon_estimands.csv", index=False, encoding="utf-8-sig")
    stability = _stability_table(estimands)
    stability.to_csv(suite_dir / "horizon_stability.csv", index=False, encoding="utf-8-sig")

    figure_outputs = []
    for estimand_id in (
        "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
        "P2_CONTENT_POST_TRUST_V33",
        "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    ):
        path = _plot_estimand(
            estimands,
            estimand_id,
            suite_dir / "figures" / f"{estimand_id}.png",
        )
        if path:
            figure_outputs.append(path)

    hard_failures = int((prefix["status"] == "FAIL").sum())
    summary = {
        "schema_version": SUITE_SCHEMA,
        "status": "PASS" if hard_failures == 0 else "FAIL",
        "scope": "Fake-LLM finite-horizon engineering robustness only",
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "endpoint_selection_permitted": False,
        "pre_specified_horizons": list(HORIZON_ROBUSTNESS_TICKS),
        "baseline_horizon": 35,
        "simulation_seed": simulation_seed,
        "llm_seed": llm_seed,
        "demand_seed": demand_seed,
        "prefix_invariance_failures": hard_failures,
        "run_dirs": {str(k): str(v) for k, v in run_dirs.items()},
        "analysis": analysis_payloads,
        "figures": figure_outputs,
        "interpretation_rule": (
            "T35 remains the primary endpoint regardless of which horizon yields the largest effect; "
            "T30/T40 are boundary-condition checks only"
        ),
    }
    (suite_dir / "horizon_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary["output_dir"] = str(suite_dir)
    return summary


def run_sync(**kwargs) -> dict:
    return asyncio.run(run_horizon_suite(**kwargs))
