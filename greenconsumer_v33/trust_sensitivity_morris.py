"""Stage-B Morris elementary-effects screening for TASK_005 v3.3.1.

This module is deliberately separated from the normal v3.3.1 pipeline. It uses
only deterministic Fake-LLM runs at the frozen T35 horizon and varies the seven
Trust-dynamics engineering parameters inside the bounds pre-specified in Stage A.

Outputs are global-screening diagnostics (mu, mu_star, sigma), not calibration,
formal inference, or external-validity evidence.
"""
from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from greenconsumer_v32.config import (
    DEFAULT_DEMAND_SEED,
    DEFAULT_LLM_SEED,
    DEFAULT_SIMULATION_SEED,
    PROJECT_ROOT,
)
from mechanism_v33 import TrustDynamicsV33Parameters

from .analysis import analyze_run
from .config import DEFAULT_TOTAL_TICKS, RunSettings
from .runner import execute
from .trust_sensitivity import PARAMETER_RANGES

SCHEMA = "task005_fmcg_v331_trust_morris1.0"
PARAMETERS = tuple(PARAMETER_RANGES)
LEVELS = 6
DELTA = LEVELS / (2.0 * (LEVELS - 1.0))  # 0.6 for p=6
TRAJECTORIES = 10
DESIGN_SEED = 2026081801

ESTIMANDS = (
    "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
    "P2_CONTENT_POST_TRUST_V33",
    "P3_TIMING_PRE_DELAY_TRUST_V33",
    "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33",
    "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    "S1_CONVERSION_SUPPORT_EXPECTED_REPEAT_CHOICE_V33",
)


def _normalized_grid() -> tuple[float, ...]:
    return tuple(round(i / (LEVELS - 1.0), 12) for i in range(LEVELS))


def _actual_value(parameter: str, normalized: float) -> float:
    low, _baseline, high = PARAMETER_RANGES[parameter]
    return float(low) + float(normalized) * (float(high) - float(low))


def _parameter_object(point: dict[str, float]) -> TrustDynamicsV33Parameters:
    values = {name: _actual_value(name, point[name]) for name in PARAMETERS}
    return TrustDynamicsV33Parameters(**values)


def generate_morris_design(
    *,
    trajectories: int = TRAJECTORIES,
    seed: int = DESIGN_SEED,
) -> pd.DataFrame:
    """Generate deterministic p=6 Morris trajectories in normalized space.

    Each parameter changes exactly once by +/- DELTA on every trajectory. Start
    coordinates are chosen from grid positions that guarantee the requested
    step stays inside [0,1].
    """

    rng = np.random.default_rng(int(seed))
    grid = np.array(_normalized_grid(), dtype=float)
    positive_starts = grid[grid <= 1.0 - DELTA + 1e-12]
    negative_starts = grid[grid >= DELTA - 1e-12]
    rows: list[dict] = []

    for trajectory in range(int(trajectories)):
        order = list(rng.permutation(len(PARAMETERS)))
        directions = {
            j: int(rng.choice(np.array([-1, 1], dtype=int)))
            for j in range(len(PARAMETERS))
        }
        current = np.zeros(len(PARAMETERS), dtype=float)
        for j in range(len(PARAMETERS)):
            pool = positive_starts if directions[j] > 0 else negative_starts
            current[j] = float(rng.choice(pool))

        def add_row(step_index: int, changed_parameter: str, direction: int):
            row = {
                "trajectory_id": f"R{trajectory + 1:02d}",
                "step_index": int(step_index),
                "changed_parameter": changed_parameter,
                "direction": int(direction),
            }
            for idx, name in enumerate(PARAMETERS):
                x = round(float(current[idx]), 12)
                row[f"x_{name}"] = x
                row[name] = _actual_value(name, x)
            rows.append(row)

        add_row(0, "", 0)
        for step_index, j in enumerate(order, start=1):
            current = current.copy()
            current[j] = round(current[j] + directions[j] * DELTA, 12)
            add_row(step_index, PARAMETERS[j], directions[j])

    design = pd.DataFrame(rows)

    # Reuse exact duplicate parameter vectors without changing the trajectory
    # design. This is safe because Fake-LLM evaluation is deterministic given
    # the fixed seeds and complete parameter vector.
    key_cols = [f"x_{name}" for name in PARAMETERS]
    keys = [tuple(float(v) for v in row) for row in design[key_cols].to_numpy()]
    unique_map: dict[tuple[float, ...], str] = {}
    evaluation_ids = []
    for key in keys:
        if key not in unique_map:
            unique_map[key] = f"U{len(unique_map) + 1:03d}"
        evaluation_ids.append(unique_map[key])
    design.insert(0, "evaluation_id", evaluation_ids)
    return design


def validate_morris_design(design: pd.DataFrame) -> pd.DataFrame:
    """Return hard validity checks for the pre-specified Morris design."""

    checks = []
    expected_points = len(PARAMETERS) + 1
    grid = np.array(_normalized_grid(), dtype=float)

    for trajectory_id, group in design.groupby("trajectory_id", sort=True):
        g = group.sort_values("step_index").reset_index(drop=True)
        checks.append(
            {
                "check_id": "TRAJECTORY_POINT_COUNT",
                "trajectory_id": trajectory_id,
                "status": "PASS" if len(g) == expected_points else "FAIL",
                "observed": len(g),
                "criterion": expected_points,
            }
        )
        changed = list(g.loc[g["step_index"] > 0, "changed_parameter"].astype(str))
        checks.append(
            {
                "check_id": "EACH_PARAMETER_CHANGED_ONCE",
                "trajectory_id": trajectory_id,
                "status": "PASS" if sorted(changed) == sorted(PARAMETERS) else "FAIL",
                "observed": ";".join(changed),
                "criterion": ";".join(PARAMETERS),
            }
        )

        step_ok = True
        grid_ok = True
        bounds_ok = True
        for i in range(1, len(g)):
            parameter = str(g.loc[i, "changed_parameter"])
            prev = float(g.loc[i - 1, f"x_{parameter}"])
            curr = float(g.loc[i, f"x_{parameter}"])
            if abs(abs(curr - prev) - DELTA) > 1e-12:
                step_ok = False
        for name in PARAMETERS:
            xs = pd.to_numeric(g[f"x_{name}"], errors="coerce").to_numpy(dtype=float)
            if np.any(xs < -1e-12) or np.any(xs > 1.0 + 1e-12):
                bounds_ok = False
            for x in xs:
                if np.min(np.abs(grid - x)) > 1e-12:
                    grid_ok = False
            low, _base, high = PARAMETER_RANGES[name]
            vals = pd.to_numeric(g[name], errors="coerce").to_numpy(dtype=float)
            if np.any(vals < float(low) - 1e-12) or np.any(vals > float(high) + 1e-12):
                bounds_ok = False

        checks.extend(
            [
                {
                    "check_id": "NORMALIZED_STEP_IS_DELTA",
                    "trajectory_id": trajectory_id,
                    "status": "PASS" if step_ok else "FAIL",
                    "observed": DELTA,
                    "criterion": DELTA,
                },
                {
                    "check_id": "POINTS_ON_P_LEVEL_GRID",
                    "trajectory_id": trajectory_id,
                    "status": "PASS" if grid_ok else "FAIL",
                    "observed": LEVELS,
                    "criterion": LEVELS,
                },
                {
                    "check_id": "PARAMETERS_WITHIN_PRE_SPECIFIED_BOUNDS",
                    "trajectory_id": trajectory_id,
                    "status": "PASS" if bounds_ok else "FAIL",
                    "observed": "normalized and actual bounds checked",
                    "criterion": "all points valid",
                },
            ]
        )

    return pd.DataFrame(checks)


def _network_hash(run_dir: Path) -> str:
    payload = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    return str((payload.get("network") or {}).get("network_hash", ""))


def _precrisis_signature(run_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "cognitive_records.csv")
    df["tick"] = pd.to_numeric(df["tick"], errors="raise").astype(int)
    df = df[df["tick"].between(1, 4)].copy()
    cols = [
        "exp_id", "tick", "agent_id", "trust_final", "attitude_att",
        "subjective_norm_after", "purchase_intention", "crisis_memory",
        "repair_memory", "semantic_valence", "semantic_arousal",
        "semantic_credibility", "semantic_evidence_strength",
        "semantic_topic_relevance",
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].sort_values(["exp_id", "tick", "agent_id"]).reset_index(drop=True)


def _read_estimands(run_dir: Path) -> dict[str, float]:
    df = pd.read_csv(run_dir / "single_block_estimands.csv")
    return {
        str(row.estimand_id): float(row.value)
        for row in df.itertuples(index=False)
        if str(row.estimand_id) in ESTIMANDS
    }


def elementary_effects(
    design: pd.DataFrame,
    evaluation_outputs: pd.DataFrame,
) -> pd.DataFrame:
    """Compute signed elementary effects using normalized parameter steps."""

    output_map = {
        str(row.evaluation_id): {
            estimand: float(getattr(row, estimand))
            for estimand in ESTIMANDS
        }
        for row in evaluation_outputs.itertuples(index=False)
    }
    rows = []
    for trajectory_id, group in design.groupby("trajectory_id", sort=True):
        g = group.sort_values("step_index").reset_index(drop=True)
        for i in range(1, len(g)):
            previous = g.loc[i - 1]
            current = g.loc[i]
            parameter = str(current["changed_parameter"])
            x_prev = float(previous[f"x_{parameter}"])
            x_curr = float(current[f"x_{parameter}"])
            dx = x_curr - x_prev
            if abs(abs(dx) - DELTA) > 1e-12:
                raise ValueError(
                    f"{trajectory_id} step {i}: invalid Morris normalized step {dx}"
                )
            y_prev = output_map[str(previous["evaluation_id"])]
            y_curr = output_map[str(current["evaluation_id"])]
            for estimand in ESTIMANDS:
                ee = (y_curr[estimand] - y_prev[estimand]) / dx
                rows.append(
                    {
                        "trajectory_id": trajectory_id,
                        "step_index": int(current["step_index"]),
                        "parameter": parameter,
                        "direction": int(current["direction"]),
                        "normalized_step": dx,
                        "estimand_id": estimand,
                        "y_before": y_prev[estimand],
                        "y_after": y_curr[estimand],
                        "elementary_effect": ee,
                        "abs_elementary_effect": abs(ee),
                    }
                )
    return pd.DataFrame(rows)


def morris_statistics(effects: pd.DataFrame) -> pd.DataFrame:
    """Compute Morris mu, mu_star and sample sigma for every parameter/output."""

    rows = []
    for (parameter, estimand), group in effects.groupby(
        ["parameter", "estimand_id"], sort=True
    ):
        ee = pd.to_numeric(group["elementary_effect"], errors="raise")
        mu = float(ee.mean())
        mu_star = float(ee.abs().mean())
        sigma = float(ee.std(ddof=1)) if len(ee) > 1 else 0.0
        rows.append(
            {
                "parameter": parameter,
                "estimand_id": estimand,
                "n_elementary_effects": len(ee),
                "mu": mu,
                "mu_star": mu_star,
                "sigma": sigma,
                "sigma_over_mu_star": sigma / mu_star if mu_star > 0 else 0.0,
                "interpretation": (
                    "global screening only; sigma indicates nonlinearity and/or interaction, not a unique decomposition"
                ),
            }
        )
    out = pd.DataFrame(rows)
    out["rank_mu_star"] = (
        out.groupby("estimand_id")["mu_star"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    return out.sort_values(["estimand_id", "rank_mu_star", "parameter"]).reset_index(drop=True)


def _plot_morris(stats: pd.DataFrame, estimand: str, path: Path) -> str | None:
    df = stats[stats["estimand_id"].astype(str) == str(estimand)].copy()
    if df.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(df["mu_star"], df["sigma"], s=55)
    for row in df.itertuples(index=False):
        ax.annotate(row.parameter, (row.mu_star, row.sigma), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("mu* — mean absolute elementary effect")
    ax.set_ylabel("sigma — SD of elementary effects")
    ax.set_title(f"Morris global screening: {estimand}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


async def run_morris_suite(
    *,
    output_root: Path = PROJECT_ROOT / "results" / "v33_trust_morris",
    simulation_seed: int = DEFAULT_SIMULATION_SEED,
    llm_seed: int = DEFAULT_LLM_SEED,
    demand_seed: int = DEFAULT_DEMAND_SEED,
) -> dict:
    """Execute the pre-specified Stage-B Morris screening suite."""

    if int(DEFAULT_TOTAL_TICKS) != 35:
        raise RuntimeError("Morris Stage B is pre-specified for the frozen T35 baseline")

    suite_id = dt.datetime.now().strftime("morris_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)

    design = generate_morris_design()
    design_checks = validate_morris_design(design)
    design.to_csv(suite_dir / "morris_design.csv", index=False, encoding="utf-8-sig")
    design_checks.to_csv(
        suite_dir / "morris_design_validation.csv", index=False, encoding="utf-8-sig"
    )
    if (design_checks["status"] == "FAIL").any():
        raise RuntimeError("pre-specified Morris design failed validation")

    unique = design.drop_duplicates("evaluation_id").sort_values("evaluation_id")
    evaluation_rows = []
    run_dirs: dict[str, Path] = {}

    for row in unique.itertuples(index=False):
        point = {name: float(getattr(row, f"x_{name}")) for name in PARAMETERS}
        params = _parameter_object(point)
        settings = RunSettings(
            llm_mode="fake",
            condition="all",
            simulation_seed=simulation_seed,
            requested_llm_seed=llm_seed,
            demand_seed=demand_seed,
            output_dir=suite_dir / "evaluations" / str(row.evaluation_id),
            run_demand=True,
            support_mode="both",
            allow_real_llm=False,
            total_ticks=35,
        )
        payload = await execute(settings, trust_parameters=params)
        run_dir = Path(payload["output_dir"])
        analyze_run(run_dir)
        run_dirs[str(row.evaluation_id)] = run_dir
        outputs = _read_estimands(run_dir)
        evaluation_rows.append(
            {
                "evaluation_id": str(row.evaluation_id),
                "run_id": run_dir.name,
                **{name: getattr(params, name) for name in PARAMETERS},
                **outputs,
            }
        )

    evaluation_outputs = pd.DataFrame(evaluation_rows)
    evaluation_outputs.to_csv(
        suite_dir / "morris_evaluation_outputs.csv", index=False, encoding="utf-8-sig"
    )

    effects = elementary_effects(design, evaluation_outputs)
    effects.to_csv(
        suite_dir / "morris_elementary_effects.csv", index=False, encoding="utf-8-sig"
    )
    stats = morris_statistics(effects)
    stats.to_csv(suite_dir / "morris_statistics.csv", index=False, encoding="utf-8-sig")

    # Hard implementation invariants across all unique evaluations.
    first_id = str(unique.iloc[0]["evaluation_id"])
    reference_dir = run_dirs[first_id]
    reference_pre = _precrisis_signature(reference_dir)
    reference_hash = _network_hash(reference_dir)
    reference_p4 = float(
        evaluation_outputs.loc[
            evaluation_outputs["evaluation_id"] == first_id,
            "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33",
        ].iloc[0]
    )
    invariant_rows = []
    for evaluation_id, run_dir in run_dirs.items():
        candidate_pre = _precrisis_signature(run_dir)
        try:
            pd.testing.assert_frame_equal(
                reference_pre, candidate_pre, check_dtype=False, check_exact=True
            )
            pre_status = "PASS"
            pre_observed = "T1-T4 key states exactly identical"
        except AssertionError as exc:
            pre_status = "FAIL"
            pre_observed = str(exc).splitlines()[0][:500]
        invariant_rows.append(
            {
                "check_id": "PRECRISIS_INVARIANCE",
                "evaluation_id": evaluation_id,
                "status": pre_status,
                "observed": pre_observed,
                "criterion": "all Trust parameter vectors must share T1-T4 key states",
            }
        )

        h = _network_hash(run_dir)
        invariant_rows.append(
            {
                "check_id": "NETWORK_HASH_INVARIANCE",
                "evaluation_id": evaluation_id,
                "status": "PASS" if h == reference_hash else "FAIL",
                "observed": h,
                "criterion": f"must equal reference network hash {reference_hash}",
            }
        )

        p4 = float(
            evaluation_outputs.loc[
                evaluation_outputs["evaluation_id"] == evaluation_id,
                "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33",
            ].iloc[0]
        )
        invariant_rows.append(
            {
                "check_id": "P4_DIRECT_REACH_INVARIANCE",
                "evaluation_id": evaluation_id,
                "status": "PASS" if abs(p4 - reference_p4) <= 1e-12 else "FAIL",
                "observed": p4,
                "criterion": f"must equal reference P4={reference_p4}",
            }
        )

    invariants = pd.DataFrame(invariant_rows)
    invariants.to_csv(
        suite_dir / "morris_invariants.csv", index=False, encoding="utf-8-sig"
    )

    figures = []
    for estimand in (
        "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
        "P2_CONTENT_POST_TRUST_V33",
        "P3_TIMING_PRE_DELAY_TRUST_V33",
        "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    ):
        output = _plot_morris(
            stats,
            estimand,
            suite_dir / "figures" / f"{estimand}.png",
        )
        if output:
            figures.append(output)

    hard_failures = int((invariants["status"] == "FAIL").sum())
    design_failures = int((design_checks["status"] == "FAIL").sum())
    p4_stats = stats[
        stats["estimand_id"].astype(str) == "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33"
    ]
    p4_nonzero = int((p4_stats["mu_star"].abs() > 1e-12).sum()) if len(p4_stats) else 1

    summary = {
        "schema_version": SCHEMA,
        "status": "PASS" if hard_failures == 0 and design_failures == 0 and p4_nonzero == 0 else "FAIL",
        "scope": "Stage-B Fake-LLM Morris global screening; not calibration or formal inference",
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "parameter_selection_permitted": False,
        "baseline_horizon": 35,
        "parameters": list(PARAMETERS),
        "levels": LEVELS,
        "delta": DELTA,
        "trajectories": TRAJECTORIES,
        "design_seed": DESIGN_SEED,
        "trajectory_points": int(len(design)),
        "unique_model_evaluations": int(design["evaluation_id"].nunique()),
        "elementary_effects_per_parameter_per_estimand": TRAJECTORIES,
        "design_validation_failures": design_failures,
        "implementation_invariant_failures": hard_failures,
        "p4_nonzero_mu_star_parameters": p4_nonzero,
        "simulation_seed": simulation_seed,
        "llm_seed": llm_seed,
        "demand_seed": demand_seed,
        "figures": figures,
        "run_dirs": {k: str(v) for k, v in run_dirs.items()},
        "interpretation_rule": (
            "Rank parameters within each estimand by mu_star. Treat sigma as evidence of nonlinearity and/or interactions, "
            "not a unique interaction measure. Do not retune the frozen baseline."
        ),
    }
    (suite_dir / "morris_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary["output_dir"] = str(suite_dir)
    return summary


def run_sync(**kwargs) -> dict:
    return asyncio.run(run_morris_suite(**kwargs))
