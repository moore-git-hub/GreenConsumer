"""Pre-registered v3.3.1 Pilot variance planning and analysis.

Normal imports and the plan/analysis paths are zero-API: this module does not
import AgentKernel, construct an LLM router, or execute a simulation.  The
Real-LLM runner is imported only inside the explicitly gated execution path.

The Pilot is an engineering design study, not part of the formal sample.  Its
means and signs are never used to select effects, mechanisms, or treatments.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2, t, wishart

from greenconsumer_v32.io import read_csv, write_json
from greenconsumer_v33.analysis import _single_block_estimands

SCHEMA = "task005_fmcg_v331_pilot_variance1.0"
EXPECTED_BRANCH = "refactor/task005-v32-clean-codebase"
CONTROL = "NoClarification-Control"
TOTAL_TICKS = 35
DELIVERY_LAG = 1
MICRO_BUYERS = 25
PILOT_LLM_MODEL = "qwen-plus-2025-12-01"

P1 = "P1_OVERALL_CLARIFICATION_POST_TRUST_V33"
P2 = "P2_CONTENT_POST_TRUST_V33"
P3 = "P3_TIMING_PRE_DELAY_TRUST_V33"
P4 = "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33"
P5 = "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33"
CONFIRMATORY_ESTIMANDS = (P1, P2, P5)
EXPLORATORY_ESTIMANDS = (P3, P4)
MDE = {P1: 0.15, P2: 0.15, P5: 0.05}

SIMULATION_SEEDS = (2026081501, 2026081502, 2026081503)
LLM_SEEDS = (2026081601, 2026081602)
DEMAND_SEEDS = (2026081701, 2026081702, 2026081703)
DEFAULT_OC_REPLICATIONS = 200_000
DEFAULT_OC_SEED = 2026081801


def profile_table() -> pd.DataFrame:
    """Return the frozen 3x2 cognitive Pilot grid in canonical order."""

    rows = []
    index = 1
    for simulation_seed in SIMULATION_SEEDS:
        for llm_seed in LLM_SEEDS:
            rows.append(
                {
                    "pilot_id": f"P{index:03d}",
                    "simulation_network_seed": simulation_seed,
                    "requested_llm_seed": llm_seed,
                    "baseline_demand_seed": DEMAND_SEEDS[0],
                    "status": "PLANNED_NOT_EXECUTED",
                }
            )
            index += 1
    return pd.DataFrame(rows)


def demand_seed_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"demand_id": f"D{i}", "demand_seed": seed}
            for i, seed in enumerate(DEMAND_SEEDS, start=1)
        ]
    )


def validate_execution_budget(
    n_max: int,
    provider_call_ceiling: int,
    max_wall_clock_hours: float,
) -> None:
    """Validate caps that must be frozen before any Pilot provider call."""

    if int(n_max) < 10:
        raise ValueError("n_max must be at least 10")
    if int(provider_call_ceiling) <= 0:
        raise ValueError("provider_call_ceiling must be positive")
    if (
        not math.isfinite(float(max_wall_clock_hours))
        or float(max_wall_clock_hours) <= 0
    ):
        raise ValueError("max_wall_clock_hours must be finite and positive")


def plan_payload(
    *,
    n_max: int | None = None,
    provider_call_ceiling: int | None = None,
    max_wall_clock_hours: float | None = None,
) -> dict:
    supplied = (
        n_max is not None,
        provider_call_ceiling is not None,
        max_wall_clock_hours is not None,
    )
    if any(supplied) and not all(supplied):
        raise ValueError(
            "n_max, provider_call_ceiling, and max_wall_clock_hours "
            "must be supplied together"
        )
    caps_frozen = n_max is not None
    if caps_frozen:
        validate_execution_budget(
            int(n_max), int(provider_call_ceiling), float(max_wall_clock_hours)
        )
    return {
        "schema_version": SCHEMA,
        "status": "PLAN_ONLY",
        "scope": "Pilot variance planning; engineering validation only",
        "real_llm_calls_started": False,
        "pilot_executed": False,
        "formal_experiment_started": False,
        "formal_inference_performed": False,
        "treatment_design": "2x2x2 Content x Channel x Timing plus one common control",
        "confirmatory_estimands": list(CONFIRMATORY_ESTIMANDS),
        "exploratory_estimands": list(EXPLORATORY_ESTIMANDS),
        "managerial_design_thresholds": MDE,
        "cognitive_profiles": profile_table().to_dict(orient="records"),
        "offline_demand_seeds": demand_seed_table().to_dict(orient="records"),
        "cognitive_blocks": 6,
        "p5_demand_realizations": 18,
        "llm_model": PILOT_LLM_MODEL,
        "n_max": int(n_max) if caps_frozen else None,
        "provider_call_ceiling": int(provider_call_ceiling) if caps_frozen else None,
        "max_wall_clock_hours": (
            float(max_wall_clock_hours) if caps_frozen else None
        ),
        "execution_caps_frozen": caps_frozen,
        "execution_authorized": False,
        "pilot_authorization_status": (
            "USER_AUTHORIZED_CONDITIONAL_ON_WINDOWS_TESTED_CLEAN_SHA"
        ),
        "minimum_oc_replications_per_scenario": DEFAULT_OC_REPLICATIONS,
        "estimated_cost_note": (
            "Six complete nine-condition Real-LLM cognitive blocks; actual provider "
            "calls are runtime-dependent and execution requires a hard user-approved cap."
        ),
    }


def _require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def _balanced_levels(frame: pd.DataFrame, columns: tuple[str, ...]) -> tuple[int, ...]:
    counts = tuple(int(frame[column].nunique()) for column in columns)
    expected = math.prod(counts)
    if len(frame) != expected or frame.duplicated(list(columns)).any():
        raise ValueError(
            f"design must have one observation per balanced cell for {columns}; "
            f"got rows={len(frame)}, expected={expected}"
        )
    return counts


def two_way_variance_components(
    frame: pd.DataFrame,
    *,
    value_col: str = "value",
) -> pd.DataFrame:
    """Method-of-moments components for the frozen 3x2 cognitive grid.

    With one observation per cell, the interaction and residual cannot be
    separated.  The returned interaction component is therefore explicitly
    labelled as interaction-plus-unresolved-runtime variation.
    """

    factors = ("simulation_network_seed", "requested_llm_seed")
    _require_columns(frame, {*factors, value_col}, "two-way frame")
    a, b = _balanced_levels(frame, factors)
    if a < 2 or b < 2:
        raise ValueError("two-way decomposition requires at least two levels per factor")

    values = pd.to_numeric(frame[value_col], errors="raise").to_numpy(float)
    grand = float(values.mean())
    s_means = frame.assign(_v=values).groupby(factors[0])["_v"].mean()
    l_means = frame.assign(_v=values).groupby(factors[1])["_v"].mean()
    ss_s = b * float(((s_means - grand) ** 2).sum())
    ss_l = a * float(((l_means - grand) ** 2).sum())
    fitted = frame[factors[0]].map(s_means) + frame[factors[1]].map(l_means) - grand
    ss_sl = float(((values - fitted.to_numpy(float)) ** 2).sum())
    ms_s = ss_s / (a - 1)
    ms_l = ss_l / (b - 1)
    ms_sl = ss_sl / ((a - 1) * (b - 1))
    raw = {
        "simulation_network": (ms_s - ms_sl) / b,
        "requested_llm_provider": (ms_l - ms_sl) / a,
        "interaction_unresolved_runtime": ms_sl,
    }
    total = sum(max(value, 0.0) for value in raw.values())
    rows = []
    for component, estimate in raw.items():
        bounded = max(float(estimate), 0.0)
        rows.append(
            {
                "component": component,
                "raw_variance_component": float(estimate),
                "bounded_variance_component": bounded,
                "share_of_bounded_total": bounded / total if total > 0 else np.nan,
                "boundary_zero": bool(estimate <= 0),
                "method": "balanced two-way random-effects method of moments",
                "warning": (
                    "3x2 small-sample estimate; interaction is confounded with "
                    "unresolved provider/runtime variation; boundary zero does not prove absence"
                ),
            }
        )
    return pd.DataFrame(rows)


def _ss_effect(array: np.ndarray, axes_kept: tuple[int, ...]) -> float:
    """Balanced ANOVA sum of squares for one main effect/interaction."""

    grand = float(array.mean())
    marginal = array.mean(axis=tuple(i for i in range(array.ndim) if i not in axes_kept))
    effect = marginal - grand
    if len(axes_kept) == 2:
        left = array.mean(axis=tuple(i for i in range(array.ndim) if i != axes_kept[0]))
        right = array.mean(axis=tuple(i for i in range(array.ndim) if i != axes_kept[1]))
        effect = marginal - np.expand_dims(left, 1) - np.expand_dims(right, 0) + grand
    elif len(axes_kept) == 3:
        s = array.mean(axis=(1, 2))[:, None, None]
        l = array.mean(axis=(0, 2))[None, :, None]
        d = array.mean(axis=(0, 1))[None, None, :]
        sl = array.mean(axis=2)[:, :, None]
        sd = array.mean(axis=1)[:, None, :]
        ld = array.mean(axis=0)[None, :, :]
        effect = array - sl - sd - ld + s + l + d - grand
    replication = math.prod(array.shape[i] for i in range(array.ndim) if i not in axes_kept)
    return float(replication * np.square(effect).sum())


def three_way_variance_components(
    frame: pd.DataFrame,
    *,
    value_col: str = "value",
) -> pd.DataFrame:
    """Method-of-moments components for the frozen 3x2x3 P5 grid."""

    factors = (
        "simulation_network_seed",
        "requested_llm_seed",
        "demand_seed",
    )
    _require_columns(frame, {*factors, value_col}, "three-way frame")
    a, b, c = _balanced_levels(frame, factors)
    if min(a, b, c) < 2:
        raise ValueError("three-way decomposition requires at least two levels per factor")

    levels = [sorted(frame[f].unique()) for f in factors]
    indexed = frame.set_index(list(factors))[value_col]
    array = np.empty((a, b, c), dtype=float)
    for i, s in enumerate(levels[0]):
        for j, l in enumerate(levels[1]):
            for k, d in enumerate(levels[2]):
                array[i, j, k] = float(indexed.loc[(s, l, d)])

    dfs = {
        "s": a - 1,
        "l": b - 1,
        "d": c - 1,
        "sl": (a - 1) * (b - 1),
        "sd": (a - 1) * (c - 1),
        "ld": (b - 1) * (c - 1),
        "sld": (a - 1) * (b - 1) * (c - 1),
    }
    ms = {
        "s": _ss_effect(array, (0,)) / dfs["s"],
        "l": _ss_effect(array, (1,)) / dfs["l"],
        "d": _ss_effect(array, (2,)) / dfs["d"],
        "sl": _ss_effect(array, (0, 1)) / dfs["sl"],
        "sd": _ss_effect(array, (0, 2)) / dfs["sd"],
        "ld": _ss_effect(array, (1, 2)) / dfs["ld"],
        "sld": _ss_effect(array, (0, 1, 2)) / dfs["sld"],
    }
    raw = {
        "simulation_network": (ms["s"] - ms["sl"] - ms["sd"] + ms["sld"]) / (b * c),
        "requested_llm_provider": (ms["l"] - ms["sl"] - ms["ld"] + ms["sld"]) / (a * c),
        "offline_demand": (ms["d"] - ms["sd"] - ms["ld"] + ms["sld"]) / (a * b),
        "simulation_x_llm": (ms["sl"] - ms["sld"]) / c,
        "simulation_x_demand": (ms["sd"] - ms["sld"]) / b,
        "llm_x_demand": (ms["ld"] - ms["sld"]) / a,
        "three_way_unresolved": ms["sld"],
    }
    total = sum(max(value, 0.0) for value in raw.values())
    rows = []
    for component, estimate in raw.items():
        bounded = max(float(estimate), 0.0)
        rows.append(
            {
                "component": component,
                "raw_variance_component": float(estimate),
                "bounded_variance_component": bounded,
                "share_of_bounded_total": bounded / total if total > 0 else np.nan,
                "boundary_zero": bool(estimate <= 0),
                "method": "balanced three-way random-effects method of moments",
                "warning": (
                    "3x2x3 small-sample estimate; components are model-dependent and "
                    "unstable; boundary zero does not prove absence"
                ),
            }
        )
    return pd.DataFrame(rows)


def variance_component_table(
    block_estimands: pd.DataFrame,
    demand_estimands: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for estimand_id in CONFIRMATORY_ESTIMANDS[:2]:
        selected = block_estimands[block_estimands["estimand_id"] == estimand_id]
        table = two_way_variance_components(selected)
        table.insert(0, "estimand_id", estimand_id)
        rows.append(table)
    selected = demand_estimands[demand_estimands["estimand_id"] == P5]
    table = three_way_variance_components(selected)
    table.insert(0, "estimand_id", P5)
    rows.append(table)
    return pd.concat(rows, ignore_index=True)


def planning_sd_table(
    block_estimands: pd.DataFrame,
    demand_estimands: pd.DataFrame,
    components: pd.DataFrame,
) -> pd.DataFrame:
    """Compute conservative planning SDs without using Pilot means or signs."""

    rows = []
    df = len(profile_table()) - 1
    upper_factor = df / float(chi2.ppf(0.20, df))
    for estimand_id in CONFIRMATORY_ESTIMANDS:
        if estimand_id == P5:
            selected = demand_estimands[
                (demand_estimands["estimand_id"] == P5)
                & (demand_estimands["demand_seed"] == DEMAND_SEEDS[0])
            ]
            component_sum = float(
                components.loc[
                    components["estimand_id"] == P5,
                    "bounded_variance_component",
                ].sum()
            )
        else:
            selected = block_estimands[block_estimands["estimand_id"] == estimand_id]
            component_sum = float("nan")
        values = pd.to_numeric(selected["value"], errors="raise")
        if len(values) != 6:
            raise ValueError(f"{estimand_id} requires six block-level values")
        raw_variance = float(values.var(ddof=1))
        base_variance = max(raw_variance, component_sum) if estimand_id == P5 else raw_variance
        planning_variance = base_variance * upper_factor
        status = "PASS" if planning_variance > 0 and math.isfinite(planning_variance) else "VARIANCE_ZERO_UNRESOLVED"
        rows.append(
            {
                "estimand_id": estimand_id,
                "pilot_n_cognitive_blocks": 6,
                "raw_block_variance": raw_variance,
                "component_sum_variance": component_sum,
                "base_variance_rule": "max(raw_D1_block_variance, bounded_component_sum)" if estimand_id == P5 else "raw_block_variance",
                "small_sample_upper_factor": upper_factor,
                "planning_variance": planning_variance,
                "planning_sd": math.sqrt(planning_variance) if planning_variance >= 0 else np.nan,
                "status": status,
                "pilot_mean_used": False,
                "warning": "80% one-sided chi-square upper variance bound with df=5; planning device, not a confidence claim about treatment effectiveness",
            }
        )
    return pd.DataFrame(rows)


def _nearest_correlation(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("estimand correlation matrix is unavailable or non-finite")
    matrix = (matrix + matrix.T) / 2.0
    values, vectors = np.linalg.eigh(matrix)
    values = np.maximum(values, 1e-8)
    psd = (vectors * values) @ vectors.T
    scale = np.sqrt(np.diag(psd))
    return psd / np.outer(scale, scale)


def estimand_correlation(
    block_estimands: pd.DataFrame,
    demand_estimands: pd.DataFrame,
) -> np.ndarray:
    base = block_estimands[block_estimands["estimand_id"].isin((P1, P2))][
        ["pilot_id", "estimand_id", "value"]
    ]
    p5 = demand_estimands[
        (demand_estimands["estimand_id"] == P5)
        & (demand_estimands["demand_seed"] == DEMAND_SEEDS[0])
    ][["pilot_id", "estimand_id", "value"]]
    wide = pd.concat([base, p5]).pivot(index="pilot_id", columns="estimand_id", values="value")
    wide = wide.loc[:, list(CONFIRMATORY_ESTIMANDS)]
    if len(wide) != 6 or wide.isna().any().any():
        raise ValueError("estimand correlation requires complete P1/P2/P5 values for six blocks")
    return _nearest_correlation(wide.corr().to_numpy(float))


def _holm_rejections(p_values: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """Vectorized Holm step-down decisions for rows of three p-values."""

    p_values = np.asarray(p_values, dtype=float)
    if p_values.ndim != 2 or p_values.shape[1] != 3:
        raise ValueError("p_values must have shape (n, 3)")
    order = np.argsort(p_values, axis=1)
    sorted_p = np.take_along_axis(p_values, order, axis=1)
    pass1 = sorted_p[:, 0] <= alpha / 3.0
    pass2 = pass1 & (sorted_p[:, 1] <= alpha / 2.0)
    pass3 = pass2 & (sorted_p[:, 2] <= alpha)
    sorted_reject = np.column_stack([pass1, pass2, pass3])
    reject = np.zeros_like(sorted_reject, dtype=bool)
    np.put_along_axis(reject, order, sorted_reject, axis=1)
    return reject


def operating_characteristics(
    planning_sd: pd.DataFrame,
    correlation: np.ndarray,
    *,
    n_max: int,
    replications: int = DEFAULT_OC_REPLICATIONS,
    random_seed: int = DEFAULT_OC_SEED,
) -> tuple[pd.DataFrame, int | None]:
    """Monte Carlo Holm operating characteristics using only MDE and planning SD."""

    if int(n_max) < 10:
        raise ValueError("n_max must be at least 10")
    if int(replications) < 1_000:
        raise ValueError("replications must be at least 1,000")
    ordered = planning_sd.set_index("estimand_id").loc[list(CONFIRMATORY_ESTIMANDS)]
    if not (ordered["status"] == "PASS").all():
        raise ValueError("all planning SD rows must PASS before OC simulation")
    sd = ordered["planning_sd"].to_numpy(float)
    if not np.isfinite(sd).all() or (sd <= 0).any():
        raise ValueError("planning SDs must be finite and positive")
    corr = _nearest_correlation(correlation)
    rng = np.random.default_rng(int(random_seed))
    scenarios = {
        "GLOBAL_NULL": np.zeros(3),
        "P1_SINGLE_MDE": np.array([MDE[P1], 0.0, 0.0]),
        "P2_SINGLE_MDE": np.array([0.0, MDE[P2], 0.0]),
        "P5_SINGLE_MDE": np.array([0.0, 0.0, MDE[P5]]),
        "ALL_AT_MDE": np.array([MDE[P1], MDE[P2], MDE[P5]]),
    }
    rows = []
    selected_n = None
    for n in range(10, int(n_max) + 1):
        # Exact joint t-statistic construction under the multivariate-normal
        # planning model: sample means and the Wishart sample covariance are
        # independent, while the three sample-variance denominators retain
        # their block-level dependence.  Common random numbers are reused
        # across design-effect scenarios at the same candidate N.
        z = rng.multivariate_normal(np.zeros(3), corr, size=int(replications))
        scatter = wishart.rvs(
            df=n - 1,
            scale=corr,
            size=int(replications),
            random_state=rng,
        )
        denominator = np.sqrt(
            np.diagonal(scatter, axis1=-2, axis2=-1) / (n - 1)
        )
        scenario_results = {}
        for scenario, effects in scenarios.items():
            numerator = z + effects * math.sqrt(n) / sd
            statistics = numerator / denominator
            p_values = 2.0 * t.sf(np.abs(statistics), df=n - 1)
            rejected = _holm_rejections(p_values)
            rates = rejected.mean(axis=0)
            any_rate = float(rejected.any(axis=1).mean())
            all_rate = float(rejected.all(axis=1).mean())
            mcse_any = math.sqrt(any_rate * (1.0 - any_rate) / replications)
            scenario_results[scenario] = (rates, any_rate, all_rate, mcse_any)
            for index, estimand_id in enumerate(CONFIRMATORY_ESTIMANDS):
                rows.append(
                    {
                        "formal_n": n,
                        "scenario": scenario,
                        "estimand_id": estimand_id,
                        "true_effect_design_value": float(effects[index]),
                        "holm_rejection_probability": float(rates[index]),
                        "probability_any_rejection": any_rate,
                        "probability_all_three_rejected": all_rate,
                        "mcse_any_rejection": mcse_any,
                        "global_null_compatibility_limit": (
                            0.05 + 2.0 * mcse_any if scenario == "GLOBAL_NULL" else np.nan
                        ),
                        "replications": int(replications),
                        "random_seed": int(random_seed),
                        "pilot_mean_used": False,
                    }
                )
        null_any, null_mcse = scenario_results["GLOBAL_NULL"][1], scenario_results["GLOBAL_NULL"][3]
        power_ok = all(
            scenario_results[name][0][index] >= 0.80
            for index, name in enumerate(("P1_SINGLE_MDE", "P2_SINGLE_MDE", "P5_SINGLE_MDE"))
        )
        fwer_compatible = null_any <= 0.05 + 2.0 * null_mcse
        if selected_n is None and power_ok and fwer_compatible:
            selected_n = n
            break
    return pd.DataFrame(rows), selected_n


def validate_completed_pilot_inputs(
    suite_dir: Path,
    block: pd.DataFrame,
    demand: pd.DataFrame,
) -> None:
    """Fail closed unless the frozen Pilot grid completed without replacement."""

    seed_path = Path(suite_dir) / "pilot_seed_ledger.csv"
    attempt_path = Path(suite_dir) / "pilot_attempt_ledger.csv"
    validity_path = Path(suite_dir) / "pilot_block_validity.csv"
    if not seed_path.exists() or not attempt_path.exists() or not validity_path.exists():
        raise FileNotFoundError("Pilot analysis requires seed, attempt, and validity ledgers")
    seeds = pd.read_csv(seed_path)
    attempts = pd.read_csv(attempt_path)
    validity = pd.read_csv(validity_path)
    frozen = profile_table()
    identity = ["pilot_id", "simulation_network_seed", "requested_llm_seed"]
    pd.testing.assert_frame_equal(
        seeds[identity].reset_index(drop=True),
        frozen[identity].reset_index(drop=True),
        check_dtype=False,
    )
    if len(attempts) != 6 or set(attempts["pilot_id"]) != set(frozen["pilot_id"]):
        raise ValueError("attempt ledger must contain exactly P001-P006")
    if not attempts["status"].eq("PASS").all():
        raise ValueError("all six pre-registered Pilot attempts must PASS")
    if "replacement_seed_used" not in attempts or not attempts["replacement_seed_used"].astype(str).str.lower().isin({"false", "0"}).all():
        raise ValueError("replacement seeds are not permitted")
    if len(validity) != 6 or set(validity["pilot_id"]) != set(frozen["pilot_id"]):
        raise ValueError("validity ledger must contain exactly P001-P006")
    if not validity["status"].eq("PASS").all():
        raise ValueError("all six Pilot blocks must pass the frozen validity contract")

    _require_columns(
        block,
        {"pilot_id", "simulation_network_seed", "requested_llm_seed", "estimand_id", "value"},
        "pilot_block_estimands",
    )
    _require_columns(
        demand,
        {"pilot_id", "simulation_network_seed", "requested_llm_seed", "demand_seed", "estimand_id", "value"},
        "pilot_demand_estimands",
    )
    for estimand_id in CONFIRMATORY_ESTIMANDS:
        source = demand if estimand_id == P5 else block
        selected = source[source["estimand_id"] == estimand_id]
        expected = 18 if estimand_id == P5 else 6
        if len(selected) != expected:
            raise ValueError(f"{estimand_id} requires {expected} Pilot values")
        if set(selected["pilot_id"]) != set(frozen["pilot_id"]):
            raise ValueError(f"{estimand_id} does not cover P001-P006")
    if set(pd.to_numeric(demand["demand_seed"], errors="raise")) != set(DEMAND_SEEDS):
        raise ValueError("P5 demand estimands must use exactly D1-D3")


def _write_frame(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(suite_dir: Path, names: list[str]) -> Path:
    rows = []
    for name in names:
        path = suite_dir / name
        if path.exists():
            rows.append({"path": name, "sha256": _sha256(path), "bytes": path.stat().st_size})
    path = suite_dir / "pilot_sha256_manifest.json"
    write_json(path, {"schema_version": SCHEMA, "files": rows})
    return path


def analyze_existing_suite(
    suite_dir: Path,
    *,
    n_max: int,
    replications: int = DEFAULT_OC_REPLICATIONS,
    random_seed: int = DEFAULT_OC_SEED,
) -> dict:
    """Analyze completed Pilot ledgers without importing or calling an LLM."""

    suite_dir = Path(suite_dir)
    block_path = suite_dir / "pilot_block_estimands.csv"
    demand_path = suite_dir / "pilot_demand_estimands.csv"
    block = pd.read_csv(block_path)
    demand = pd.read_csv(demand_path)
    validate_completed_pilot_inputs(suite_dir, block, demand)
    components = variance_component_table(block, demand)
    planning = planning_sd_table(block, demand, components)
    _write_frame(components, suite_dir / "pilot_variance_components.csv")
    _write_frame(planning, suite_dir / "pilot_planning_sd.csv")

    selected_n = None
    oc_status = "NOT_RUN_VARIANCE_UNRESOLVED"
    if (planning["status"] == "PASS").all():
        correlation = estimand_correlation(block, demand)
        oc, selected_n = operating_characteristics(
            planning,
            correlation,
            n_max=n_max,
            replications=replications,
            random_seed=random_seed,
        )
        _write_frame(oc, suite_dir / "pilot_operating_characteristics.csv")
        oc_status = "PASS" if selected_n is not None else "DESIGN_NOT_FEASIBLE_WITHIN_CAP"
    else:
        _write_frame(
            pd.DataFrame(
                [
                    {
                        "formal_n": "",
                        "scenario": "NOT_RUN_VARIANCE_UNRESOLVED",
                        "estimand_id": "",
                        "status": "VARIANCE_ZERO_UNRESOLVED",
                        "replications": 0,
                        "pilot_mean_used": False,
                    }
                ]
            ),
            suite_dir / "pilot_operating_characteristics.csv",
        )

    summary = {
        "schema_version": SCHEMA,
        "status": oc_status,
        "scope": "Pilot variance planning; engineering validation only",
        "pilot_results_are_formal_sample": False,
        "formal_inference_performed": False,
        "pilot_means_used_for_design": False,
        "n_max": int(n_max),
        "selected_formal_n": selected_n,
        "oc_replications_per_scenario": int(replications),
        "oc_random_seed": int(random_seed),
        "formal_execution_authorized": False,
        "llm_model": PILOT_LLM_MODEL,
        "interpretation": (
            "selected_formal_n is a pre-formal design recommendation only; protocol 1.1, "
            "a formal seed ledger, frozen source SHA, and explicit authorization remain required"
        ),
    }
    write_json(suite_dir / "pilot_summary.json", summary)
    names = [
        "pilot_seed_ledger.csv",
        "pilot_attempt_ledger.csv",
        "pilot_block_validity.csv",
        "pilot_block_validity_details.csv",
        "pilot_block_estimands.csv",
        "pilot_demand_estimands.csv",
        "pilot_variance_components.csv",
        "pilot_planning_sd.csv",
        "pilot_operating_characteristics.csv",
        "pilot_summary.json",
    ]
    _write_manifest(suite_dir, names)
    return {**summary, "output_dir": str(suite_dir)}


class ProviderCallBudgetExceeded(RuntimeError):
    pass


class WallClockBudgetExceeded(RuntimeError):
    pass


class _ProviderCallBudget:
    def __init__(
        self,
        ceiling: int,
        max_wall_clock_hours: float | None = None,
        *,
        clock=time.monotonic,
    ):
        self.ceiling = int(ceiling)
        self.calls_attempted = 0
        self.max_wall_clock_hours = (
            None if max_wall_clock_hours is None else float(max_wall_clock_hours)
        )
        self._clock = clock
        self._started = float(self._clock())
        self._deadline = (
            None
            if self.max_wall_clock_hours is None
            else self._started + self.max_wall_clock_hours * 3600.0
        )

    def elapsed_seconds(self) -> float:
        return max(0.0, float(self._clock()) - self._started)

    def remaining_seconds(self) -> float | None:
        if self._deadline is None:
            return None
        return max(0.0, self._deadline - float(self._clock()))

    def check_time(self) -> None:
        remaining = self.remaining_seconds()
        if remaining is not None and remaining <= 0:
            raise WallClockBudgetExceeded(
                f"wall-clock ceiling {self.max_wall_clock_hours:g} hours reached; "
                "fail-closed stop"
            )

    def reserve(self) -> None:
        self.check_time()
        if self.calls_attempted >= self.ceiling:
            raise ProviderCallBudgetExceeded(
                f"provider-call ceiling {self.ceiling} reached; fail-closed stop"
            )
        self.calls_attempted += 1


def _git_execution_preflight(project_root: Path, expected_git_head: str) -> dict:
    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", *args], cwd=project_root, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
        return proc.stdout.strip()

    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    dirty = git("status", "--porcelain", "--untracked-files=normal")
    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"wrong branch: {branch}; expected {EXPECTED_BRANCH}")
    if head != expected_git_head:
        raise RuntimeError(f"HEAD mismatch: {head}; expected {expected_git_head}")
    if dirty:
        raise RuntimeError("Pilot execution requires a clean Git worktree")
    return {"git_head": head, "git_branch": branch, "git_dirty": False}


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _validity_row(pilot_id: str, payload: dict, run_dir: Path) -> tuple[dict, pd.DataFrame]:
    from greenconsumer_v33.thesis_outputs import _load, _validation
    from greenconsumer_v33.thesis_outputs_finite_horizon import (
        _append_time_validation,
        _resolve_end_tick,
    )

    data = _load(run_dir)
    checks_frame, validation = _validation(data, run_dir)
    checks_frame, validation = _append_time_validation(
        checks_frame, validation, data, _resolve_end_tick(data)
    )
    cognitive = data["cognitive"].copy()
    unique = cognitive[["exp_id", "agent_id", "tick"]].drop_duplicates()
    condition_meta = payload.get("condition_meta") or []
    strict_check_ids = {
        "V01_AGENT_TICK_COMPLETENESS", "V02_AGENT_TICK_UNIQUENESS",
        "V03_SEMANTIC_FALLBACK", "V04_COMMON_HISTORY_REPLAY",
        "V05_LLM_AUDIT_ERRORS", "V06_SEMANTIC_RANGES",
        "V07_SN_PEER_ONLY_BOUNDARY", "V10_CONTROL_CONTAMINATION",
        "V11_PRETREATMENT_COMMON_HISTORY", "V12_DEMAND_PROBABILITY_BOUNDS",
        "V13_LOYALTY_BOUNDS", "V14_RENEWAL_FORWARD_TIME",
        "V15_NETWORK_EXPORT_CONSISTENCY", "V16_TIME_HORIZON_PROVENANCE",
    }
    strict = checks_frame[checks_frame["check_id"].isin(strict_check_ids)]
    strict_validation = (
        set(strict["check_id"]) == strict_check_ids
        and strict["status"].eq("PASS").all()
    )

    ranges = {
        "trust_final": (0.0, 10.0),
        "attitude_att": (0.0, 1.0),
        "subjective_norm_after": (0.0, 1.0),
        "pbc": (0.0, 1.0),
        "purchase_intention": (0.0, 1.0),
    }
    state_bounds = True
    for field, (lower, upper) in ranges.items():
        values = pd.to_numeric(cognitive[field], errors="coerce")
        state_bounds = state_bounds and values.notna().all() and values.between(lower, upper).all()
    for field in ("crisis_memory", "repair_memory"):
        values = pd.to_numeric(cognitive[field], errors="coerce")
        state_bounds = state_bounds and values.notna().all() and (values >= 0).all()

    estimand_ids = set(data["estimands"]["estimand_id"].astype(str))
    topology_hashes = {str(row.get("network_hash", "")) for row in condition_meta}
    checks = {
        "run_status_pass": payload.get("status") == "PASS",
        "nine_conditions": len(payload.get("conditions_run") or []) == 9,
        "agent_tick_rows_6300": len(cognitive) == 6300 and len(unique) == 6300,
        "semantic_fallback_zero": int(payload.get("semantic_fallback_events", -1)) == 0,
        "replay_miss_zero": sum(int(x.get("replay_misses", 0)) for x in condition_meta) == 0,
        "t35": int(payload.get("total_ticks", -1)) == TOTAL_TICKS,
        "dated_llm_model": payload.get("llm_model") == PILOT_LLM_MODEL,
        "strict_internal_validation": bool(strict_validation),
        "state_and_memory_bounds": bool(state_bounds),
        "p1_through_p5_reconstructable": {P1, P2, P3, P4, P5}.issubset(estimand_ids),
        "one_nonempty_topology_hash": len(topology_hashes) == 1 and "" not in topology_hashes,
        "event_timeline_persisted": (run_dir / "effective_event_timeline.json").exists(),
    }
    row = {
        "pilot_id": pilot_id,
        **checks,
        "internal_validation_hard_failures": int(validation["hard_failures"]),
        "internal_validation_warnings": int(validation["warnings"]),
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    details = checks_frame.copy()
    details.insert(0, "pilot_id", pilot_id)
    return row, details


async def run_pilot_suite(
    *,
    output_root: Path,
    allow_real_llm: bool,
    n_max: int,
    provider_call_ceiling: int,
    max_wall_clock_hours: float,
    expected_git_head: str,
) -> dict:
    """Explicitly execute P001-P006; never called by plan or analysis paths."""

    if not allow_real_llm:
        raise ValueError("Pilot execution requires explicit allow_real_llm=True")
    validate_execution_budget(
        n_max, provider_call_ceiling, max_wall_clock_hours
    )

    # Delayed imports are the central zero-API safety boundary.
    from greenconsumer_v33 import runner as runner_module
    from greenconsumer_v33.analysis import analyze_run
    from greenconsumer_v33.config import RunSettings
    from greenconsumer_v33.demand import simulate_demand

    provenance = _git_execution_preflight(runner_module.PROJECT_ROOT, expected_git_head)
    suite_id = dt.datetime.now().strftime("pilotvar_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)
    profiles = profile_table()
    seed_ledger = profiles.copy()
    seed_ledger["offline_demand_seeds"] = ";".join(str(x) for x in DEMAND_SEEDS)
    seed_ledger["llm_model"] = PILOT_LLM_MODEL
    seed_ledger["git_head"] = provenance["git_head"]
    _write_frame(seed_ledger, suite_dir / "pilot_seed_ledger.csv")

    budget = _ProviderCallBudget(
        provider_call_ceiling,
        max_wall_clock_hours=max_wall_clock_hours,
    )
    attempts: list[dict] = []
    validity: list[dict] = []
    validity_details: list[pd.DataFrame] = []
    block_frames: list[pd.DataFrame] = []
    demand_rows: list[dict] = []

    for profile in profiles.to_dict(orient="records"):
        attempt = {
            **profile,
            "started_utc": _utc_now(),
            "ended_utc": "",
            "status": "RUNNING",
            "error_type": "",
            "error_message": "",
            "provider_calls_cumulative": budget.calls_attempted,
            "replacement_seed_used": False,
        }
        attempts.append(attempt)
        _write_frame(pd.DataFrame(attempts), suite_dir / "pilot_attempt_ledger.csv")
        try:
            budget.check_time()
            settings = RunSettings(
                llm_mode="real", condition="all",
                simulation_seed=int(profile["simulation_network_seed"]),
                requested_llm_seed=int(profile["requested_llm_seed"]),
                demand_seed=DEMAND_SEEDS[0],
                output_dir=suite_dir / "blocks" / str(profile["pilot_id"]),
                run_demand=True, support_mode="absent", allow_real_llm=True,
                total_ticks=TOTAL_TICKS, prompt_profile="baseline_exact",
            )
            remaining = budget.remaining_seconds()
            try:
                payload = await asyncio.wait_for(
                    runner_module.execute(
                        settings,
                        before_provider_call=budget.reserve,
                    ),
                    timeout=remaining,
                )
            except asyncio.TimeoutError as exc:
                raise WallClockBudgetExceeded(
                    f"wall-clock ceiling {max_wall_clock_hours:g} hours reached "
                    f"during {profile['pilot_id']}; fail-closed stop"
                ) from exc
            run_dir = Path(payload["output_dir"])
            analyze_run(run_dir)
            valid, details = _validity_row(str(profile["pilot_id"]), payload, run_dir)
            validity.append(valid)
            validity_details.append(details)
            if valid["status"] != "PASS":
                raise RuntimeError(f"{profile['pilot_id']} failed block validity contract")

            block = pd.read_csv(run_dir / "single_block_estimands.csv")
            block.insert(0, "pilot_id", str(profile["pilot_id"]))
            block.insert(1, "simulation_network_seed", int(profile["simulation_network_seed"]))
            block.insert(2, "requested_llm_seed", int(profile["requested_llm_seed"]))
            block_frames.append(block)

            cognitive = read_csv(run_dir / "cognitive_records.csv")
            by_condition: dict[str, list[dict]] = {}
            for row in cognitive:
                by_condition.setdefault(str(row["exp_id"]), []).append(row)
            for demand_id, demand_seed in enumerate(DEMAND_SEEDS, start=1):
                generated = []
                for condition_rows in by_condition.values():
                    condition_demand, _ = simulate_demand(
                        condition_rows, support_present=False,
                        demand_seed=demand_seed, micro_buyers=MICRO_BUYERS,
                    )
                    generated.extend(condition_demand)
                estimands, _ = _single_block_estimands(
                    by_condition, generated, DELIVERY_LAG, end_tick=TOTAL_TICKS
                )
                p5_rows = [row for row in estimands if row["estimand_id"] == P5]
                if len(p5_rows) != 1:
                    raise RuntimeError(f"{profile['pilot_id']}: P5 not uniquely produced")
                demand_rows.append(
                    {
                        "pilot_id": str(profile["pilot_id"]),
                        "simulation_network_seed": int(profile["simulation_network_seed"]),
                        "requested_llm_seed": int(profile["requested_llm_seed"]),
                        "demand_id": f"D{demand_id}",
                        "demand_seed": demand_seed,
                        **p5_rows[0],
                    }
                )
            original_p5 = block.loc[block["estimand_id"] == P5, "value"]
            replayed_d1 = demand_rows[-len(DEMAND_SEEDS)]["value"]
            if len(original_p5) != 1 or not math.isclose(
                float(original_p5.iloc[0]), float(replayed_d1), rel_tol=0.0, abs_tol=1e-12
            ):
                raise RuntimeError(
                    f"{profile['pilot_id']}: D1 offline P5 does not reproduce runner P5"
                )
            attempt["status"] = "PASS"
            attempt["run_dir"] = str(run_dir)
        except Exception as exc:
            attempt["status"] = "FAIL_STOPPED_NO_REPLACEMENT"
            attempt["error_type"] = type(exc).__name__
            attempt["error_message"] = str(exc)
            failure_summary = {
                "schema_version": SCHEMA,
                "status": "PILOT_FAILED_STOPPED_NO_REPLACEMENT",
                "scope": "Pilot variance planning; engineering validation only",
                "failed_pilot_id": str(profile["pilot_id"]),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "provider_call_ceiling": int(provider_call_ceiling),
                "provider_calls_attempted": int(budget.calls_attempted),
                "llm_model": PILOT_LLM_MODEL,
                "max_wall_clock_hours": float(max_wall_clock_hours),
                "wall_clock_seconds_elapsed": budget.elapsed_seconds(),
                "formal_inference_performed": False,
                "formal_execution_authorized": False,
            }
            write_json(suite_dir / "pilot_summary.json", failure_summary)
            raise
        finally:
            attempt["ended_utc"] = _utc_now()
            attempt["provider_calls_cumulative"] = budget.calls_attempted
            _write_frame(pd.DataFrame(attempts), suite_dir / "pilot_attempt_ledger.csv")
            if validity:
                _write_frame(pd.DataFrame(validity), suite_dir / "pilot_block_validity.csv")
            if validity_details:
                _write_frame(
                    pd.concat(validity_details, ignore_index=True),
                    suite_dir / "pilot_block_validity_details.csv",
                )
            if block_frames:
                _write_frame(pd.concat(block_frames, ignore_index=True), suite_dir / "pilot_block_estimands.csv")
            if demand_rows:
                _write_frame(pd.DataFrame(demand_rows), suite_dir / "pilot_demand_estimands.csv")
            if attempt["status"] != "PASS" and (suite_dir / "pilot_summary.json").exists():
                _write_manifest(
                    suite_dir,
                    [
                        "pilot_seed_ledger.csv",
                        "pilot_attempt_ledger.csv",
                        "pilot_block_validity.csv",
                        "pilot_block_validity_details.csv",
                        "pilot_block_estimands.csv",
                        "pilot_demand_estimands.csv",
                        "pilot_summary.json",
                    ],
                )

    result = analyze_existing_suite(
        suite_dir, n_max=n_max,
        replications=DEFAULT_OC_REPLICATIONS, random_seed=DEFAULT_OC_SEED,
    )
    summary_path = suite_dir / "pilot_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update(
        {
            "pilot_execution_status": "PASS",
            "provider_call_ceiling": int(provider_call_ceiling),
            "provider_calls_attempted": int(budget.calls_attempted),
            "max_wall_clock_hours": float(max_wall_clock_hours),
            "wall_clock_seconds_elapsed": budget.elapsed_seconds(),
            "llm_model": PILOT_LLM_MODEL,
            "git_provenance": provenance,
        }
    )
    write_json(summary_path, summary)
    _write_manifest(
        suite_dir,
        [row["path"] for row in json.loads((suite_dir / "pilot_sha256_manifest.json").read_text(encoding="utf-8"))["files"]],
    )
    return {**summary, "output_dir": str(suite_dir)}


def run_sync(**kwargs) -> dict:
    return asyncio.run(run_pilot_suite(**kwargs))
