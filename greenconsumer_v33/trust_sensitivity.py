"""Stage-A Trust parameter sensitivity for TASK_005 v3.3.1.

This suite is Fake-LLM only and uses the frozen T35 baseline horizon. It varies
only ``TrustDynamicsV33Parameters`` while holding network, treatment, demand,
semantic router and seeds fixed. The purpose is engineering/local/boundary
sensitivity, not calibration or formal inference.
"""
from __future__ import annotations

import asyncio
import dataclasses
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
from mechanism_v33 import DEFAULT_TRUST_PARAMETERS, TrustDynamicsV33Parameters

from .analysis import analyze_run
from .config import DEFAULT_TOTAL_TICKS, RunSettings
from .runner import execute

SCHEMA = "task005_fmcg_v331_trust_sensitivity1.0"

PARAMETER_RANGES = {
    "crisis_retention": (0.96, 0.98, 0.99),
    "repair_retention": (0.94, 0.96, 0.98),
    "event_adjustment": (0.60, 0.80, 1.00),
    "quiet_adjustment": (0.10, 0.18, 0.30),
    "repair_saturation": (0.00, 0.30, 0.60),
    "hypocrisy_weight": (0.00, 0.25, 0.50),
    "empathy_repair_weight": (0.25, 0.50, 0.75),
}


def _profile_rows() -> list[dict]:
    rows = [
        {
            "profile_id": "baseline",
            "profile_type": "baseline",
            "changed_parameter": "",
            "level": "baseline",
            "parameters": DEFAULT_TRUST_PARAMETERS,
        }
    ]
    for name, (low, base, high) in PARAMETER_RANGES.items():
        baseline_value = float(getattr(DEFAULT_TRUST_PARAMETERS, name))
        if abs(baseline_value - float(base)) > 1e-12:
            raise RuntimeError(
                f"sensitivity baseline mismatch for {name}: {baseline_value} != {base}"
            )
        for level, value in (("low", low), ("high", high)):
            rows.append(
                {
                    "profile_id": f"{name}_{level}",
                    "profile_type": "oat",
                    "changed_parameter": name,
                    "level": level,
                    "parameters": dataclasses.replace(
                        DEFAULT_TRUST_PARAMETERS,
                        **{name: float(value)},
                    ),
                }
            )

    rows.extend(
        [
            {
                "profile_id": "retention_symmetric_097",
                "profile_type": "structured-boundary",
                "changed_parameter": "crisis_retention+repair_retention",
                "level": "structured",
                "parameters": dataclasses.replace(
                    DEFAULT_TRUST_PARAMETERS,
                    crisis_retention=0.97,
                    repair_retention=0.97,
                ),
            },
            {
                "profile_id": "retention_reversed_096_098",
                "profile_type": "structured-boundary",
                "changed_parameter": "crisis_retention+repair_retention",
                "level": "structured",
                "parameters": dataclasses.replace(
                    DEFAULT_TRUST_PARAMETERS,
                    crisis_retention=0.96,
                    repair_retention=0.98,
                ),
            },
            {
                "profile_id": "legacy_v32_transition",
                "profile_type": "structured-boundary",
                "changed_parameter": "multiple",
                "level": "legacy-boundary",
                "parameters": TrustDynamicsV33Parameters.legacy_v32(),
            },
        ]
    )
    return rows


def profile_table() -> pd.DataFrame:
    rows = []
    for spec in _profile_rows():
        params = dataclasses.asdict(spec["parameters"])
        rows.append(
            {
                "profile_id": spec["profile_id"],
                "profile_type": spec["profile_type"],
                "changed_parameter": spec["changed_parameter"],
                "level": spec["level"],
                **params,
                "empirically_calibrated": False,
                "range_role": "engineering robustness envelope",
            }
        )
    return pd.DataFrame(rows)


def _read_estimands(run_dir: Path, profile_id: str) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "single_block_estimands.csv")
    df.insert(0, "profile_id", profile_id)
    df.insert(1, "run_id", run_dir.name)
    return df


def _network_hash(run_dir: Path) -> str:
    payload = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    return str((payload.get("network") or {}).get("network_hash", ""))


def _precrisis_signature(run_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "cognitive_records.csv")
    df["tick"] = pd.to_numeric(df["tick"], errors="raise").astype(int)
    df = df[df["tick"].between(1, 4)].copy()
    columns = [
        "exp_id",
        "tick",
        "agent_id",
        "trust_final",
        "attitude_att",
        "subjective_norm_after",
        "purchase_intention",
        "crisis_memory",
        "repair_memory",
        "semantic_valence",
        "semantic_arousal",
        "semantic_credibility",
        "semantic_evidence_strength",
        "semantic_topic_relevance",
    ]
    columns = [c for c in columns if c in df.columns]
    return df[columns].sort_values(["exp_id", "tick", "agent_id"]).reset_index(drop=True)


def _compare_precrisis(baseline_dir: Path, candidate_dir: Path, profile_id: str) -> dict:
    a = _precrisis_signature(baseline_dir)
    b = _precrisis_signature(candidate_dir)
    try:
        pd.testing.assert_frame_equal(a, b, check_dtype=False, check_exact=True)
        status = "PASS"
        detail = "T1-T4 key cognitive states exactly identical"
    except AssertionError as exc:
        status = "FAIL"
        detail = str(exc).splitlines()[0][:500]
    return {
        "check_id": "PRECRISIS_INVARIANCE",
        "profile_id": profile_id,
        "status": status,
        "observed": detail,
        "criterion": "Trust parameter profile must not alter T1-T4 states",
    }


def _reach_value(estimands: pd.DataFrame, profile_id: str) -> float:
    part = estimands[
        (estimands["profile_id"].astype(str) == profile_id)
        & (estimands["estimand_id"].astype(str) == "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33")
    ]
    if len(part) != 1:
        raise ValueError(f"missing/duplicate P4 for {profile_id}")
    return float(part["value"].iloc[0])


def _local_effects(estimands: pd.DataFrame) -> pd.DataFrame:
    baseline = estimands[estimands["profile_id"].astype(str) == "baseline"]
    baseline_map = dict(zip(baseline["estimand_id"].astype(str), pd.to_numeric(baseline["value"], errors="coerce")))
    rows = []
    for parameter, (low, base, high) in PARAMETER_RANGES.items():
        low_id = f"{parameter}_low"
        high_id = f"{parameter}_high"
        for estimand_id, base_value in baseline_map.items():
            lo = estimands[(estimands["profile_id"] == low_id) & (estimands["estimand_id"] == estimand_id)]
            hi = estimands[(estimands["profile_id"] == high_id) & (estimands["estimand_id"] == estimand_id)]
            if len(lo) != 1 or len(hi) != 1:
                continue
            lo_val = float(lo["value"].iloc[0])
            hi_val = float(hi["value"].iloc[0])
            slope = (hi_val - lo_val) / float(high - low)
            signs = {
                "negative" if x < 0 else "positive" if x > 0 else "zero"
                for x in (lo_val, float(base_value), hi_val)
            }
            rows.append(
                {
                    "parameter": parameter,
                    "estimand_id": estimand_id,
                    "low_parameter": low,
                    "baseline_parameter": base,
                    "high_parameter": high,
                    "low_value": lo_val,
                    "baseline_value": float(base_value),
                    "high_value": hi_val,
                    "low_delta_from_baseline": lo_val - float(base_value),
                    "high_delta_from_baseline": hi_val - float(base_value),
                    "low_high_span": max(lo_val, float(base_value), hi_val) - min(lo_val, float(base_value), hi_val),
                    "local_secant_slope": slope,
                    "sign_stable": len(signs) == 1,
                    "interpretation": "Stage-A local/boundary sensitivity only; not a global importance index",
                }
            )
    return pd.DataFrame(rows)


def _plot_effects(local: pd.DataFrame, estimand_id: str, path: Path) -> str | None:
    df = local[local["estimand_id"].astype(str) == estimand_id].copy()
    if df.empty:
        return None
    df["max_abs_delta"] = df[["low_delta_from_baseline", "high_delta_from_baseline"]].abs().max(axis=1)
    df = df.sort_values("max_abs_delta")
    fig, ax = plt.subplots(figsize=(9, 5.5))
    y = range(len(df))
    ax.hlines(y, df["low_delta_from_baseline"], df["high_delta_from_baseline"], linewidth=2)
    ax.scatter(df["low_delta_from_baseline"], y, label="low − baseline")
    ax.scatter(df["high_delta_from_baseline"], y, label="high − baseline")
    ax.axvline(0.0, linewidth=0.8)
    ax.set_yticks(list(y))
    ax.set_yticklabels(df["parameter"])
    ax.set_xlabel("Absolute change in estimand relative to baseline profile")
    ax.set_title(f"Stage-A Trust parameter sensitivity: {estimand_id}")
    ax.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


async def run_trust_sensitivity_suite(
    *,
    output_root: Path = PROJECT_ROOT / "results" / "v33_trust_sensitivity",
    simulation_seed: int = DEFAULT_SIMULATION_SEED,
    llm_seed: int = DEFAULT_LLM_SEED,
    demand_seed: int = DEFAULT_DEMAND_SEED,
) -> dict:
    if int(DEFAULT_TOTAL_TICKS) != 35:
        raise RuntimeError("Stage-A Trust sensitivity is pre-specified for T35 baseline only")

    suite_id = dt.datetime.now().strftime("trust_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)

    profile_specs = _profile_rows()
    profiles = profile_table()
    profiles.to_csv(suite_dir / "trust_sensitivity_profiles.csv", index=False, encoding="utf-8-sig")

    run_dirs: dict[str, Path] = {}
    estimand_frames = []
    summaries = {}

    for spec in profile_specs:
        profile_id = str(spec["profile_id"])
        settings = RunSettings(
            llm_mode="fake",
            condition="all",
            simulation_seed=simulation_seed,
            requested_llm_seed=llm_seed,
            demand_seed=demand_seed,
            output_dir=suite_dir / "profiles" / profile_id,
            run_demand=True,
            support_mode="both",
            allow_real_llm=False,
            total_ticks=35,
        )
        payload = await execute(settings, trust_parameters=spec["parameters"])
        run_dir = Path(payload["output_dir"])
        run_dirs[profile_id] = run_dir
        summaries[profile_id] = analyze_run(run_dir)
        estimand_frames.append(_read_estimands(run_dir, profile_id))

    estimands = pd.concat(estimand_frames, ignore_index=True)
    estimands.to_csv(suite_dir / "trust_sensitivity_estimands.csv", index=False, encoding="utf-8-sig")
    local = _local_effects(estimands)
    local.to_csv(suite_dir / "trust_sensitivity_local_effects.csv", index=False, encoding="utf-8-sig")

    baseline_dir = run_dirs["baseline"]
    baseline_hash = _network_hash(baseline_dir)
    baseline_p4 = _reach_value(estimands, "baseline")
    invariant_rows = []
    for spec in profile_specs:
        profile_id = str(spec["profile_id"])
        candidate = run_dirs[profile_id]
        invariant_rows.append(_compare_precrisis(baseline_dir, candidate, profile_id))
        candidate_hash = _network_hash(candidate)
        invariant_rows.append(
            {
                "check_id": "NETWORK_HASH_INVARIANCE",
                "profile_id": profile_id,
                "status": "PASS" if candidate_hash == baseline_hash else "FAIL",
                "observed": candidate_hash,
                "criterion": f"must equal baseline network hash {baseline_hash}",
            }
        )
        p4 = _reach_value(estimands, profile_id)
        invariant_rows.append(
            {
                "check_id": "P4_DIRECT_REACH_INVARIANCE",
                "profile_id": profile_id,
                "status": "PASS" if abs(p4 - baseline_p4) <= 1e-12 else "FAIL",
                "observed": p4,
                "criterion": f"must equal baseline P4={baseline_p4}; Trust cannot alter direct enterprise reach",
            }
        )
    invariants = pd.DataFrame(invariant_rows)
    invariants.to_csv(suite_dir / "trust_sensitivity_invariants.csv", index=False, encoding="utf-8-sig")

    figures = []
    for estimand_id in (
        "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
        "P2_CONTENT_POST_TRUST_V33",
        "P3_TIMING_PRE_DELAY_TRUST_V33",
        "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    ):
        output = _plot_effects(local, estimand_id, suite_dir / "figures" / f"{estimand_id}.png")
        if output:
            figures.append(output)

    hard_failures = int((invariants["status"] == "FAIL").sum())
    sign_unstable = local[~local["sign_stable"]].copy()
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS" if hard_failures == 0 else "FAIL",
        "scope": "Stage-A Fake-LLM local/boundary Trust parameter sensitivity; not calibration or formal inference",
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "parameter_selection_permitted": False,
        "baseline_horizon": 35,
        "profiles_run": len(profile_specs),
        "oat_parameters": list(PARAMETER_RANGES),
        "structured_profiles": [
            spec["profile_id"] for spec in profile_specs if spec["profile_type"] == "structured-boundary"
        ],
        "simulation_seed": simulation_seed,
        "llm_seed": llm_seed,
        "demand_seed": demand_seed,
        "invariant_failures": hard_failures,
        "sign_unstable_parameter_estimand_pairs": sign_unstable[["parameter", "estimand_id"]].to_dict(orient="records"),
        "run_dirs": {k: str(v) for k, v in run_dirs.items()},
        "analysis": summaries,
        "figures": figures,
        "interpretation_rule": (
            "Do not tune the frozen baseline to obtain favorable effects. Stage-A identifies local/boundary sensitivity only; "
            "global parameter importance requires the pre-planned Stage-B analysis."
        ),
    }
    (suite_dir / "trust_sensitivity_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary["output_dir"] = str(suite_dir)
    return summary


def run_sync(**kwargs) -> dict:
    return asyncio.run(run_trust_sensitivity_suite(**kwargs))
