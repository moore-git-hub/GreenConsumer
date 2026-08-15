"""Demand-only micro-buyer resolution robustness for TASK_005 v3.3.1.

Pre-specified design:
- source: five already-completed N20/K3 BA cognitive blocks;
- micro-buyers per cognitive Agent M = 10 / 25 / 50;
- rerun downstream demand only; never rerun AgentKernel/LLM cognition;
- baseline M=25 remains frozen regardless of result.

This is numerical-resolution engineering robustness, not formal inference.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fmcg_scenario_v32 import ENGINEERING_PERSONAS
from purchase_mechanism_v31 import DemandParameters
from purchase_mechanism_v32 import build_scenario_micro_cohort

from .analysis import _read_delivery_lag, _read_total_ticks, _single_block_estimands
from .demand import simulate_demand

SCHEMA = "task005_fmcg_v331_microbuyer_resolution1.0"
MICROBUYER_COUNTS = (10, 25, 50)
BASELINE_MICROBUYERS = 25
NETWORK_SEEDS = tuple(range(2026081501, 2026081506))
CONTROL = "NoClarification-Control"
REQUIRED_CONDITIONS = {
    CONTROL,
    "Rational-Hub-Immediate",
    "Rational-Hub-Delayed",
    "Rational-Random-Immediate",
    "Rational-Random-Delayed",
    "Empathy-Hub-Immediate",
    "Empathy-Hub-Delayed",
    "Empathy-Random-Immediate",
    "Empathy-Random-Delayed",
}
UPSTREAM_ESTIMANDS = (
    "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
    "P2_CONTENT_POST_TRUST_V33",
    "P3_TIMING_PRE_DELAY_TRUST_V33",
    "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33",
)
DOWNSTREAM_ESTIMANDS = (
    "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    "S1_CONVERSION_SUPPORT_EXPECTED_REPEAT_CHOICE_V33",
)
TOL = 1e-12


def profile_table() -> pd.DataFrame:
    rows = []
    for seed in NETWORK_SEEDS:
        for m in MICROBUYER_COUNTS:
            rows.append(
                {
                    "profile_id": f"nseed{seed}_m{m}",
                    "network_seed": int(seed),
                    "micro_buyers_per_cognitive_agent": int(m),
                    "profile_role": "frozen-baseline" if m == BASELINE_MICROBUYERS else "pre-specified-resolution-robustness",
                }
            )
    return pd.DataFrame(rows)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_source_run(source_size_dir: Path, profile_id: str, summary: dict) -> Path:
    """Resolve a source run portably, preferring an existing declared path."""

    declared = (summary.get("run_dirs") or {}).get(profile_id)
    if declared:
        candidate = Path(str(declared))
        if (candidate / "cognitive_records.csv").exists():
            return candidate

    profile_root = Path(source_size_dir) / "profiles" / profile_id
    if not profile_root.exists():
        raise FileNotFoundError(profile_root)
    matches = sorted(
        p for p in profile_root.iterdir()
        if p.is_dir() and (p / "cognitive_records.csv").exists()
    )
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one source run under {profile_root}, found {len(matches)}"
        )
    return matches[0]


def _resolve_sources(source_size_dir: Path) -> tuple[dict[int, Path], dict]:
    source_size_dir = Path(source_size_dir)
    summary_path = source_size_dir / "size_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(summary_path)
    summary = _load_json(summary_path)
    sources = {}
    for seed in NETWORK_SEEDS:
        pid = f"n20_k3_nseed{seed}"
        sources[int(seed)] = _resolve_source_run(source_size_dir, pid, summary)
    return sources, summary


def _cognitive_by_condition(run_dir: Path) -> tuple[dict[str, list[dict]], list[dict]]:
    path = run_dir / "cognitive_records.csv"
    df = pd.read_csv(path)
    records = df.to_dict(orient="records")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        grouped[str(row["exp_id"])].append(row)
    missing = REQUIRED_CONDITIONS.difference(grouped)
    if missing:
        raise ValueError(f"source cognitive run missing conditions: {sorted(missing)}")
    return dict(grouped), records


def _buyer_count_integrity(micro_buyers: int, demand_seed: int) -> tuple[bool, str]:
    params = DemandParameters(micro_buyers_per_archetype=int(micro_buyers))
    all_ids = []
    for persona in ENGINEERING_PERSONAS:
        cohort = build_scenario_micro_cohort(
            seed=int(demand_seed),
            persona=persona,
            parameters=params,
        )
        if len(cohort) != int(micro_buyers):
            return False, f"{persona.agent_id}: expected {micro_buyers}, got {len(cohort)}"
        all_ids.extend(p.buyer_id for p in cohort)
    expected = len(ENGINEERING_PERSONAS) * int(micro_buyers)
    if len(set(all_ids)) != expected:
        return False, f"unique buyer ids={len(set(all_ids))}, expected={expected}"
    return True, f"unique buyer ids={expected}"


def _source_estimand_map(run_dir: Path) -> dict[str, float]:
    df = pd.read_csv(run_dir / "single_block_estimands.csv")
    return {
        str(row.estimand_id): float(row.value)
        for row in df.itertuples(index=False)
    }


def _run_resolution(
    *,
    run_dir: Path,
    network_seed: int,
    micro_buyers: int,
    demand_seed: int,
) -> tuple[list[dict], list[dict]]:
    by_condition, cognitive_records = _cognitive_by_condition(run_dir)
    end_tick = _read_total_ticks(run_dir, cognitive_records)
    delivery_lag = _read_delivery_lag(run_dir)
    demand_rows: list[dict] = []

    for exp_id in sorted(REQUIRED_CONDITIONS):
        cognitive_rows = by_condition[exp_id]
        for support_present in (False, True):
            rows, _curves = simulate_demand(
                cognitive_rows,
                support_present=support_present,
                demand_seed=int(demand_seed),
                micro_buyers=int(micro_buyers),
                personas=tuple(ENGINEERING_PERSONAS),
            )
            demand_rows.extend(rows)

    estimands, _reach = _single_block_estimands(
        by_condition,
        demand_rows,
        int(delivery_lag),
        end_tick=int(end_tick),
    )
    estimand_rows = []
    for row in estimands:
        estimand_rows.append(
            {
                "profile_id": f"nseed{network_seed}_m{micro_buyers}",
                "network_seed": int(network_seed),
                "micro_buyers_per_cognitive_agent": int(micro_buyers),
                **row,
            }
        )

    diagnostics = []
    frame = pd.DataFrame(demand_rows)
    frame["tick"] = pd.to_numeric(frame["tick"], errors="raise")
    post = frame[(frame["tick"] >= 6) & (frame["tick"] <= int(end_tick))].copy()
    for (exp_id, support), group in post.groupby(["exp_id", "conversion_support"], sort=True):
        probs = pd.to_numeric(group["choice_probability"], errors="raise")
        chosen = group["focal_brand_chosen"].astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})
        diagnostics.append(
            {
                "profile_id": f"nseed{network_seed}_m{micro_buyers}",
                "network_seed": int(network_seed),
                "micro_buyers_per_cognitive_agent": int(micro_buyers),
                "exp_id": str(exp_id),
                "conversion_support": str(support),
                "analysis_start_tick": 6,
                "analysis_end_tick": int(end_tick),
                "opportunities": int(len(group)),
                "opportunities_per_cognitive_agent": float(len(group) / len(ENGINEERING_PERSONAS)),
                "expected_choice_share": float(probs.mean()),
                "realized_choice_share": float(chosen.mean()),
            }
        )
    return estimand_rows, diagnostics


def _family_summary(estimands: pd.DataFrame) -> pd.DataFrame:
    rows = []
    subset = estimands[estimands["estimand_id"].isin(DOWNSTREAM_ESTIMANDS)].copy()
    for (m, eid), group in subset.groupby(["micro_buyers_per_cognitive_agent", "estimand_id"], sort=True):
        vals = pd.to_numeric(group["value"], errors="raise")
        signs = ["positive" if x > 0 else "negative" if x < 0 else "zero" for x in vals]
        rows.append(
            {
                "micro_buyers_per_cognitive_agent": int(m),
                "estimand_id": str(eid),
                "network_realizations": int(len(vals)),
                "mean": float(vals.mean()),
                "min": float(vals.min()),
                "max": float(vals.max()),
                "range": float(vals.max() - vals.min()),
                "signs": ";".join(signs),
                "sign_stable_across_networks": len(set(signs)) == 1,
                "analysis_role": "demand-resolution engineering descriptive only",
            }
        )
    return pd.DataFrame(rows)


def _stability_table(estimands: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for seed in NETWORK_SEEDS:
        for eid in DOWNSTREAM_ESTIMANDS:
            part = estimands[
                (estimands["network_seed"] == int(seed))
                & (estimands["estimand_id"] == eid)
            ].set_index("micro_buyers_per_cognitive_agent")
            vals = {m: float(part.loc[m, "value"]) for m in MICROBUYER_COUNTS}
            baseline = vals[BASELINE_MICROBUYERS]
            signs = ["positive" if vals[m] > 0 else "negative" if vals[m] < 0 else "zero" for m in MICROBUYER_COUNTS]
            rows.append(
                {
                    "network_seed": int(seed),
                    "estimand_id": eid,
                    "m10": vals[10],
                    "m25_baseline": baseline,
                    "m50": vals[50],
                    "m10_minus_m25": vals[10] - baseline,
                    "m50_minus_m25": vals[50] - baseline,
                    "abs_m10_minus_m25": abs(vals[10] - baseline),
                    "abs_m50_minus_m25": abs(vals[50] - baseline),
                    "relative_m10_minus_m25": ((vals[10] - baseline) / abs(baseline)) if baseline else np.nan,
                    "relative_m50_minus_m25": ((vals[50] - baseline) / abs(baseline)) if baseline else np.nan,
                    "range_m": max(vals.values()) - min(vals.values()),
                    "signs": ";".join(signs),
                    "sign_stable_across_m": len(set(signs)) == 1,
                }
            )
    return pd.DataFrame(rows)


def _invariants(
    *,
    source_summary: dict,
    source_runs: dict[int, Path],
    estimands: pd.DataFrame,
    demand_seed: int,
) -> pd.DataFrame:
    rows = []
    source_ok = str(source_summary.get("status")) == "PASS" and int(source_summary.get("invariant_failures", -1)) == 0
    rows.append(
        {
            "check_id": "SOURCE_SIZE_SUITE_INTEGRITY",
            "profile_id": "suite",
            "status": "PASS" if source_ok else "FAIL",
            "observed": f"status={source_summary.get('status')}; invariant_failures={source_summary.get('invariant_failures')}",
            "criterion": "source size suite PASS with invariant_failures=0",
        }
    )
    rows.append(
        {
            "check_id": "SOURCE_N20_RUN_COUNT",
            "profile_id": "suite",
            "status": "PASS" if len(source_runs) == 5 else "FAIL",
            "observed": f"n={len(source_runs)}",
            "criterion": "exactly five pre-specified N20/K3 source runs",
        }
    )

    for m in MICROBUYER_COUNTS:
        ok, detail = _buyer_count_integrity(m, int(demand_seed))
        rows.append(
            {
                "check_id": "BUYER_COUNT_INTEGRITY",
                "profile_id": f"m{m}",
                "status": "PASS" if ok else "FAIL",
                "observed": detail,
                "criterion": f"20 cognitive Agents × {m} unique micro-buyers",
            }
        )

    for seed, run_dir in sorted(source_runs.items()):
        source_map = _source_estimand_map(run_dir)
        rows.append(
            {
                "check_id": "COGNITIVE_SOURCE_SHA256",
                "profile_id": f"nseed{seed}",
                "status": "PASS",
                "observed": _sha256(run_dir / "cognitive_records.csv"),
                "criterion": "provenance only; cognitive file reused without modification",
            }
        )
        for eid in DOWNSTREAM_ESTIMANDS:
            rerun = float(
                estimands[
                    (estimands["network_seed"] == int(seed))
                    & (estimands["micro_buyers_per_cognitive_agent"] == BASELINE_MICROBUYERS)
                    & (estimands["estimand_id"] == eid)
                ]["value"].iloc[0]
            )
            original = float(source_map[eid])
            diff = rerun - original
            rows.append(
                {
                    "check_id": "BASELINE_M25_REPRODUCTION",
                    "profile_id": f"nseed{seed}:{eid}",
                    "status": "PASS" if abs(diff) <= TOL else "FAIL",
                    "observed": f"rerun={rerun:.17g}; source={original:.17g}; diff={diff:.3g}",
                    "criterion": f"absolute difference <= {TOL:g}",
                }
            )

        for eid in UPSTREAM_ESTIMANDS:
            part = estimands[
                (estimands["network_seed"] == int(seed))
                & (estimands["estimand_id"] == eid)
            ].sort_values("micro_buyers_per_cognitive_agent")
            vals = pd.to_numeric(part["value"], errors="raise").to_numpy(dtype=float)
            span = float(vals.max() - vals.min()) if len(vals) else np.nan
            rows.append(
                {
                    "check_id": "UPSTREAM_ESTIMAND_INVARIANCE",
                    "profile_id": f"nseed{seed}:{eid}",
                    "status": "PASS" if len(vals) == len(MICROBUYER_COUNTS) and span <= TOL else "FAIL",
                    "observed": f"range={span:.3g}",
                    "criterion": f"P1-P4 unchanged across M; range <= {TOL:g}",
                }
            )
    return pd.DataFrame(rows)


def _plot_estimand(estimands: pd.DataFrame, eid: str, path: Path) -> str:
    df = estimands[estimands["estimand_id"] == eid].copy()
    fig, ax = plt.subplots(figsize=(8, 5))
    for seed, group in df.groupby("network_seed"):
        group = group.sort_values("micro_buyers_per_cognitive_agent")
        ax.plot(
            group["micro_buyers_per_cognitive_agent"],
            group["value"],
            marker="o",
            alpha=0.25,
        )
    means = df.groupby("micro_buyers_per_cognitive_agent")["value"].mean().sort_index()
    ax.plot(means.index, means.values, marker="o", linewidth=2.5, label="mean across 5 BA realizations")
    ax.axvline(BASELINE_MICROBUYERS, linestyle="--", linewidth=0.9, label="frozen baseline M=25")
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xticks(list(MICROBUYER_COUNTS))
    ax.set_xlabel("Micro-buyers per cognitive Agent M")
    ax.set_ylabel(str(df["unit"].iloc[0]))
    title = "P5 clarification effect on expected repeat choice" if eid.startswith("P5_") else "S1 conversion-support effect on expected repeat choice"
    ax.set_title(f"{title}\nDemand-only resolution robustness; 5 BA cognitive histories, T35")
    ax.legend(fontsize=8)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


def _plot_opportunities(diagnostics: pd.DataFrame, path: Path) -> str:
    # Use absent-support rows; opportunity timing is a demand-renewal diagnostic,
    # not a treatment-effect estimand.
    df = diagnostics[diagnostics["conversion_support"] == "absent"].copy()
    per_profile = (
        df.groupby(["network_seed", "micro_buyers_per_cognitive_agent"], as_index=False)["opportunities"]
        .sum()
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    for seed, group in per_profile.groupby("network_seed"):
        group = group.sort_values("micro_buyers_per_cognitive_agent")
        ax.plot(group["micro_buyers_per_cognitive_agent"], group["opportunities"], marker="o", alpha=0.25)
    means = per_profile.groupby("micro_buyers_per_cognitive_agent")["opportunities"].mean().sort_index()
    ax.plot(means.index, means.values, marker="o", linewidth=2.5, label="mean across 5 BA histories")
    ax.set_xticks(list(MICROBUYER_COUNTS))
    ax.set_xlabel("Micro-buyers per cognitive Agent M")
    ax.set_ylabel("T6-T35 category-purchase opportunities across 9 conditions")
    ax.set_title("Demand opportunity count under micro-buyer resolution\nAbsent conversion support; downstream diagnostic only")
    ax.legend(fontsize=8)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


def run_microbuyer_resolution_suite(
    *,
    source_size_dir: Path,
    output_root: Path | None = None,
) -> dict:
    source_size_dir = Path(source_size_dir)
    source_runs, source_summary = _resolve_sources(source_size_dir)
    demand_seed = int(source_summary.get("demand_seed", 2026081701))

    if output_root is None:
        output_root = source_size_dir.parent.parent / "v33_microbuyer_sensitivity"
    suite_id = dt.datetime.now().strftime("micro_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)

    profiles = profile_table()
    profiles.to_csv(suite_dir / "microbuyer_profiles.csv", index=False, encoding="utf-8-sig")

    estimand_rows = []
    diagnostic_rows = []
    for seed, run_dir in sorted(source_runs.items()):
        for m in MICROBUYER_COUNTS:
            e_rows, d_rows = _run_resolution(
                run_dir=run_dir,
                network_seed=int(seed),
                micro_buyers=int(m),
                demand_seed=demand_seed,
            )
            estimand_rows.extend(e_rows)
            diagnostic_rows.extend(d_rows)

    estimands = pd.DataFrame(estimand_rows)
    diagnostics = pd.DataFrame(diagnostic_rows)
    estimands.to_csv(suite_dir / "microbuyer_estimands.csv", index=False, encoding="utf-8-sig")
    diagnostics.to_csv(suite_dir / "microbuyer_demand_diagnostics.csv", index=False, encoding="utf-8-sig")

    family = _family_summary(estimands)
    family.to_csv(suite_dir / "microbuyer_family_summary.csv", index=False, encoding="utf-8-sig")
    stability = _stability_table(estimands)
    stability.to_csv(suite_dir / "microbuyer_stability.csv", index=False, encoding="utf-8-sig")
    invariants = _invariants(
        source_summary=source_summary,
        source_runs=source_runs,
        estimands=estimands,
        demand_seed=demand_seed,
    )
    invariants.to_csv(suite_dir / "microbuyer_invariants.csv", index=False, encoding="utf-8-sig")

    figures = [
        _plot_estimand(
            estimands,
            "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
            suite_dir / "figures" / "P5_MICROBUYER_RESOLUTION.png",
        ),
        _plot_estimand(
            estimands,
            "S1_CONVERSION_SUPPORT_EXPECTED_REPEAT_CHOICE_V33",
            suite_dir / "figures" / "S1_MICROBUYER_RESOLUTION.png",
        ),
        _plot_opportunities(
            diagnostics,
            suite_dir / "figures" / "OPPORTUNITIES_MICROBUYER_RESOLUTION.png",
        ),
    ]

    failures = int((invariants["status"] == "FAIL").sum())
    p5_stability = stability[stability["estimand_id"].str.startswith("P5_")]
    s1_stability = stability[stability["estimand_id"].str.startswith("S1_")]
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS" if failures == 0 else "FAIL",
        "scope": "demand-only micro-buyer numerical-resolution engineering robustness; not formal inference",
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "parameter_selection_permitted": False,
        "source_size_suite": str(source_size_dir),
        "source_size_suite_status": source_summary.get("status"),
        "network_seeds": list(NETWORK_SEEDS),
        "microbuyer_counts": list(MICROBUYER_COUNTS),
        "baseline_microbuyers": BASELINE_MICROBUYERS,
        "profiles_run": int(len(profiles)),
        "demand_seed": demand_seed,
        "invariant_failures": failures,
        "p5_sign_unstable_networks": int((~p5_stability["sign_stable_across_m"]).sum()),
        "s1_sign_unstable_networks": int((~s1_stability["sign_stable_across_m"]).sum()),
        "source_runs": {str(k): str(v) for k, v in source_runs.items()},
        "figures": figures,
        "interpretation_rule": (
            "Treat M=10/25/50 as deterministic demand-discretization resolutions, not statistical sample sizes; M=25 remains frozen regardless of outcome"
        ),
    }
    (suite_dir / "microbuyer_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary["output_dir"] = str(suite_dir)
    return summary


def run_sync(**kwargs) -> dict:
    return run_microbuyer_resolution_suite(**kwargs)
