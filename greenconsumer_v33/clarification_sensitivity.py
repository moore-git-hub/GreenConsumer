"""Paid-reach / delivery-lag sensitivity for TASK_005 v3.3.1.

Pre-specified engineering grid:
- paid_edge_probability = 0.30 / 0.55 / 0.80
- paid_delivery_lag = 0 / 1 / 2 Ticks

The suite uses deterministic Fake LLM, frozen T35, Trust baseline, network,
budget, personas, stimuli and seeds. It is robustness analysis, not calibration
or formal inference.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from clarification_diffusion_v33 import ClarificationDiffusionV33Parameters
from greenconsumer_v32.config import (
    DEFAULT_DEMAND_SEED,
    DEFAULT_LLM_SEED,
    DEFAULT_SIMULATION_SEED,
    PROJECT_ROOT,
)
from mechanism_v33 import DEFAULT_TRUST_PARAMETERS

from .analysis import analyze_run
from .config import RunSettings
from . import runner as runner_module

SCHEMA = "task005_fmcg_v331_clarification_sensitivity1.0"
EDGE_PROBABILITIES = (0.30, 0.55, 0.80)
DELIVERY_LAGS = (0, 1, 2)
BASELINE_PROBABILITY = 0.55
BASELINE_LAG = 1
CONTROL = "NoClarification-Control"


def profile_id(probability: float, lag: int) -> str:
    return f"p{int(round(float(probability) * 100)):02d}_lag{int(lag)}"


def profile_table() -> pd.DataFrame:
    rows = []
    for probability in EDGE_PROBABILITIES:
        for lag in DELIVERY_LAGS:
            rows.append(
                {
                    "profile_id": profile_id(probability, lag),
                    "paid_edge_probability": probability,
                    "paid_delivery_lag": lag,
                    "profile_role": (
                        "frozen-baseline"
                        if probability == BASELINE_PROBABILITY and lag == BASELINE_LAG
                        else "pre-specified-sensitivity"
                    ),
                }
            )
    return pd.DataFrame(rows)


async def _execute_with_clarification_parameters(
    settings: RunSettings,
    parameters: ClarificationDiffusionV33Parameters,
) -> dict:
    """Version-scoped adapter without changing normal runner defaults.

    ``runner.execute`` resolves ``run_scenario_v33`` from its module global at
    call time. We temporarily replace only that symbol, run one profile
    sequentially, and restore it on every exit path. This keeps the ordinary
    frozen-baseline runner API unchanged while the sensitivity runtime receives
    explicit paid-reach parameters.
    """

    original = runner_module.run_scenario_v33

    async def scoped_run_scenario(
        config,
        *,
        override_router,
        trust_parameters=DEFAULT_TRUST_PARAMETERS,
    ):
        return await original(
            config,
            override_router=override_router,
            trust_parameters=trust_parameters,
            clarification_parameters=parameters,
        )

    runner_module.run_scenario_v33 = scoped_run_scenario
    try:
        return await runner_module.execute(
            settings,
            trust_parameters=DEFAULT_TRUST_PARAMETERS,
        )
    finally:
        runner_module.run_scenario_v33 = original


def _network_hash(run_dir: Path) -> str:
    payload = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    return str((payload.get("network") or {}).get("network_hash", ""))


def _sorted_frame(path: Path, *, filters=None) -> pd.DataFrame:
    df = pd.read_csv(path)
    if filters:
        for column, predicate in filters.items():
            df = df[predicate(df[column])]
    sort_cols = [c for c in ("exp_id", "tick", "agent_id", "source_agent_id", "target_agent_id") if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols)
    return df.reset_index(drop=True)


def _exact_compare(a: pd.DataFrame, b: pd.DataFrame) -> tuple[str, str]:
    common = [c for c in a.columns if c in b.columns]
    try:
        pd.testing.assert_frame_equal(
            a[common].reset_index(drop=True),
            b[common].reset_index(drop=True),
            check_dtype=False,
            check_exact=True,
        )
        return "PASS", "exact equality"
    except AssertionError as exc:
        return "FAIL", str(exc).splitlines()[0][:500]


def _read_estimands(run_dir: Path, pid: str, probability: float, lag: int) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "single_block_estimands.csv")
    df.insert(0, "profile_id", pid)
    df.insert(1, "paid_edge_probability", probability)
    df.insert(2, "paid_delivery_lag", lag)
    return df


def _read_reach(run_dir: Path, pid: str, probability: float, lag: int) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "clarification_reach_v33.csv")
    df.insert(0, "profile_id", pid)
    df.insert(1, "paid_edge_probability", probability)
    df.insert(2, "paid_delivery_lag_profile", lag)
    return df


def _invariants(run_dirs: dict[str, Path], profiles: pd.DataFrame, reach: pd.DataFrame) -> pd.DataFrame:
    baseline_id = profile_id(BASELINE_PROBABILITY, BASELINE_LAG)
    baseline_dir = run_dirs[baseline_id]
    baseline_hash = _network_hash(baseline_dir)
    baseline_targets = _sorted_frame(baseline_dir / "target_nodes.csv")
    baseline_control = _sorted_frame(
        baseline_dir / "cognitive_records.csv",
        filters={"exp_id": lambda s: s.astype(str) == CONTROL},
    )
    baseline_pre = _sorted_frame(
        baseline_dir / "cognitive_records.csv",
        filters={"tick": lambda s: pd.to_numeric(s, errors="raise") <= 5},
    )

    rows = []
    for spec in profiles.itertuples(index=False):
        pid = str(spec.profile_id)
        run_dir = run_dirs[pid]

        h = _network_hash(run_dir)
        rows.append(
            {
                "check_id": "NETWORK_HASH_INVARIANCE",
                "profile_id": pid,
                "status": "PASS" if h == baseline_hash else "FAIL",
                "observed": h,
                "criterion": f"must equal baseline hash {baseline_hash}",
            }
        )

        targets = _sorted_frame(run_dir / "target_nodes.csv")
        status, detail = _exact_compare(baseline_targets, targets)
        rows.append(
            {
                "check_id": "TARGET_NODE_ALLOCATION_INVARIANCE",
                "profile_id": pid,
                "status": status,
                "observed": detail,
                "criterion": "paid seed allocation must not depend on p or lag",
            }
        )

        control = _sorted_frame(
            run_dir / "cognitive_records.csv",
            filters={"exp_id": lambda s: s.astype(str) == CONTROL},
        )
        status, detail = _exact_compare(baseline_control, control)
        rows.append(
            {
                "check_id": "CONTROL_TRAJECTORY_INVARIANCE",
                "profile_id": pid,
                "status": status,
                "observed": detail,
                "criterion": "control T1-T35 cognitive trajectory must be identical",
            }
        )

        pre = _sorted_frame(
            run_dir / "cognitive_records.csv",
            filters={"tick": lambda s: pd.to_numeric(s, errors="raise") <= 5},
        )
        status, detail = _exact_compare(baseline_pre, pre)
        rows.append(
            {
                "check_id": "PRE_TREATMENT_T1_T5_INVARIANCE",
                "profile_id": pid,
                "status": status,
                "observed": detail,
                "criterion": "paid reach parameters must not alter T1-T5 states",
            }
        )

    # Eventual enterprise reach must depend on p but not on delivery timing.
    for probability in EDGE_PROBABILITIES:
        part = reach[np.isclose(reach["paid_edge_probability"], probability)]
        for exp_id, group in part.groupby("exp_id"):
            vals = pd.to_numeric(group["eventual_enterprise_reach"], errors="raise")
            rows.append(
                {
                    "check_id": "EVENTUAL_REACH_LAG_INVARIANCE",
                    "profile_id": f"p={probability:.2f}:{exp_id}",
                    "status": "PASS" if float(vals.max() - vals.min()) <= 1e-12 else "FAIL",
                    "observed": ";".join(f"{x:.12g}" for x in vals),
                    "criterion": "eventual direct enterprise reach must be identical for lag 0/1/2 at fixed p",
                }
            )

    # Because the same deterministic edge draws are thresholded by p, the set
    # of successful one-hop recipients must be nested as p increases.
    for lag in DELIVERY_LAGS:
        part = reach[reach["paid_delivery_lag_profile"].astype(int) == int(lag)]
        for exp_id, group in part.groupby("exp_id"):
            g = group.sort_values("paid_edge_probability")
            vals = list(pd.to_numeric(g["eventual_enterprise_reach"], errors="raise"))
            monotone = all(left <= right + 1e-12 for left, right in zip(vals[:-1], vals[1:]))
            rows.append(
                {
                    "check_id": "EVENTUAL_REACH_MONOTONE_IN_P",
                    "profile_id": f"lag={lag}:{exp_id}",
                    "status": "PASS" if monotone else "FAIL",
                    "observed": ";".join(f"{x:.12g}" for x in vals),
                    "criterion": "reach(p=.30) <= reach(p=.55) <= reach(p=.80)",
                }
            )

    return pd.DataFrame(rows)


def _plot_profile_lines(estimands: pd.DataFrame, estimand_id: str, path: Path) -> str | None:
    df = estimands[estimands["estimand_id"].astype(str) == estimand_id].copy()
    if df.empty:
        return None
    df["value"] = pd.to_numeric(df["value"], errors="raise")
    fig, ax = plt.subplots(figsize=(8, 5))
    for lag, group in df.groupby("paid_delivery_lag"):
        g = group.sort_values("paid_edge_probability")
        ax.plot(g["paid_edge_probability"], g["value"], marker="o", label=f"lag={int(lag)}")
    ax.axvline(BASELINE_PROBABILITY, linewidth=0.8, linestyle="--")
    ax.set_xticks(list(EDGE_PROBABILITIES))
    ax.set_xlabel("Paid edge delivery probability")
    ax.set_ylabel(str(df["unit"].iloc[0]))
    ax.set_title(f"Clarification diffusion sensitivity: {estimand_id}\nFake LLM, T35; baseline p=.55, lag=1")
    ax.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


async def run_clarification_sensitivity_suite(
    *,
    output_root: Path = PROJECT_ROOT / "results" / "v33_clarification_sensitivity",
    simulation_seed: int = DEFAULT_SIMULATION_SEED,
    llm_seed: int = DEFAULT_LLM_SEED,
    demand_seed: int = DEFAULT_DEMAND_SEED,
) -> dict:
    suite_id = dt.datetime.now().strftime("clarification_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)

    profiles = profile_table()
    profiles.to_csv(suite_dir / "clarification_sensitivity_profiles.csv", index=False, encoding="utf-8-sig")

    run_dirs: dict[str, Path] = {}
    estimand_frames = []
    reach_frames = []
    analysis_payloads = {}

    for spec in profiles.itertuples(index=False):
        pid = str(spec.profile_id)
        params = ClarificationDiffusionV33Parameters(
            paid_edge_probability=float(spec.paid_edge_probability),
            paid_delivery_lag=int(spec.paid_delivery_lag),
        )
        settings = RunSettings(
            llm_mode="fake",
            condition="all",
            simulation_seed=simulation_seed,
            requested_llm_seed=llm_seed,
            demand_seed=demand_seed,
            output_dir=suite_dir / "profiles" / pid,
            run_demand=True,
            support_mode="both",
            allow_real_llm=False,
            total_ticks=35,
        )
        payload = await _execute_with_clarification_parameters(settings, params)
        run_dir = Path(payload["output_dir"])
        run_dirs[pid] = run_dir
        analysis_payloads[pid] = analyze_run(run_dir)
        estimand_frames.append(
            _read_estimands(run_dir, pid, float(spec.paid_edge_probability), int(spec.paid_delivery_lag))
        )
        reach_frames.append(
            _read_reach(run_dir, pid, float(spec.paid_edge_probability), int(spec.paid_delivery_lag))
        )

    estimands = pd.concat(estimand_frames, ignore_index=True)
    reach = pd.concat(reach_frames, ignore_index=True)
    estimands.to_csv(suite_dir / "clarification_sensitivity_estimands.csv", index=False, encoding="utf-8-sig")
    reach.to_csv(suite_dir / "clarification_sensitivity_reach.csv", index=False, encoding="utf-8-sig")

    invariants = _invariants(run_dirs, profiles, reach)
    invariants.to_csv(suite_dir / "clarification_sensitivity_invariants.csv", index=False, encoding="utf-8-sig")

    figures = []
    for estimand_id in (
        "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
        "P2_CONTENT_POST_TRUST_V33",
        "P3_TIMING_PRE_DELAY_TRUST_V33",
        "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33",
        "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    ):
        output = _plot_profile_lines(
            estimands,
            estimand_id,
            suite_dir / "figures" / f"{estimand_id}.png",
        )
        if output:
            figures.append(output)

    failures = int((invariants["status"] == "FAIL").sum())
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS" if failures == 0 else "FAIL",
        "scope": "Fake-LLM paid-reach/delivery-lag engineering sensitivity; not calibration or formal inference",
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "parameter_selection_permitted": False,
        "baseline_horizon": 35,
        "edge_probabilities": list(EDGE_PROBABILITIES),
        "delivery_lags": list(DELIVERY_LAGS),
        "baseline_paid_edge_probability": BASELINE_PROBABILITY,
        "baseline_paid_delivery_lag": BASELINE_LAG,
        "profiles_run": len(profiles),
        "invariant_failures": failures,
        "simulation_seed": simulation_seed,
        "llm_seed": llm_seed,
        "demand_seed": demand_seed,
        "run_dirs": {k: str(v) for k, v in run_dirs.items()},
        "analysis": analysis_payloads,
        "figures": figures,
        "interpretation_rule": (
            "Do not retune the frozen p=.55/lag=1 baseline. Report reach/trust/choice sensitivity as structural boundary evidence."
        ),
    }
    (suite_dir / "clarification_sensitivity_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary["output_dir"] = str(suite_dir)
    return summary


def run_sync(**kwargs) -> dict:
    return asyncio.run(run_clarification_sensitivity_suite(**kwargs))
