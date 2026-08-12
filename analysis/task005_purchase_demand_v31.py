"""Offline structural replay for TASK_005 FMCG purchase-demand v3.1.

This analysis consumes the frozen variance-v3 psychological trajectories.  It
does not call an LLM, compute p-values, select a winner, estimate a formal effect
or modify any production-path parameter.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import purchase_mechanism_v31 as p31


EXPECTED_REPLICATES = tuple(f"R{i:03d}" for i in range(1, 11))
CONTROL_ID = "NoClarification-Control"
FACILITATION_LEVELS = {"absent": False, "present": True}
PSYCHOLOGICAL_FIELDS = (
    "attitude_att",
    "subjective_norm_sn",
    "pbc",
    "trust_final",
    "purchase_intention",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("mean requires at least one value")
    return statistics.fmean(values)


def _range_sums(cell: dict[int, dict[str, float]], start: int, end: int) -> dict[str, float]:
    output = {"opportunities": 0.0, "expected": 0.0, "realized": 0.0}
    for tick in range(int(start), int(end) + 1):
        row = cell[tick]
        output["opportunities"] += row["opportunities"]
        output["expected"] += row["expected"]
        output["realized"] += row["realized"]
    return output


def _share(sums: dict[str, float], field: str) -> float:
    if sums["opportunities"] <= 0:
        raise ValueError("share requires positive opportunities")
    return sums[field] / sums["opportunities"]


def _load_profiles(path: Path) -> dict[str, str]:
    clusters: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            clusters[str(row["id"])] = str(row["psychology"]["cluster_type"])
    if len(clusters) != 20:
        raise ValueError(f"expected 20 profile rows, found {len(clusters)}")
    return clusters


def _load_block(
    root: Path,
    replicate_id: str,
) -> tuple[int, tuple[str, ...], dict[str, dict[tuple[str, int], dict[str, float]]]]:
    block = root / replicate_id
    ledger = _read_csv(block / "seed_ledger.csv")
    if len(ledger) != 1:
        raise ValueError(f"{replicate_id}: seed_ledger.csv must contain one row")
    seed = int(ledger[0]["simulation_seed"])
    by_condition: dict[str, dict[tuple[str, int], dict[str, float]]] = defaultdict(dict)
    agents: set[str] = set()
    for raw in _read_csv(block / "mechanism_records.csv"):
        exp_id = str(raw["exp_id"])
        agent_id = str(raw["agent_id"])
        tick = int(raw["tick"])
        agents.add(agent_id)
        key = (agent_id, tick)
        if key in by_condition[exp_id]:
            raise ValueError(f"{replicate_id}/{exp_id}: duplicate {key}")
        by_condition[exp_id][key] = {
            field: float(raw[field]) for field in PSYCHOLOGICAL_FIELDS
        }
    if CONTROL_ID not in by_condition or len(by_condition) != 9:
        raise ValueError(f"{replicate_id}: expected one control and eight strategies")
    if len(agents) != 20:
        raise ValueError(f"{replicate_id}: expected 20 agents, found {len(agents)}")
    expected_keys = {(agent_id, tick) for agent_id in agents for tick in range(1, 31)}
    for exp_id, rows in by_condition.items():
        if set(rows) != expected_keys:
            raise ValueError(f"{replicate_id}/{exp_id}: incomplete agent-by-tick panel")
    return seed, tuple(sorted(agents)), dict(by_condition)


def _empty_tick_cells() -> dict[int, dict[str, float]]:
    return {
        tick: {
            "opportunities": 0.0,
            "expected": 0.0,
            "realized": 0.0,
            "pbc": 0.0,
            "intention": 0.0,
        }
        for tick in range(1, 31)
    }


def _simulate_block(
    *,
    variance_root: Path,
    replicate_id: str,
    clusters: dict[str, str],
    parameters: p31.DemandParameters,
) -> dict[str, Any]:
    seed, agents, psychology = _load_block(variance_root, replicate_id)
    cohorts: dict[str, tuple[p31.MicroBuyerProfile, ...]] = {}
    for agent_id in agents:
        archetype_pbc = psychology[CONTROL_ID][(agent_id, 1)]["pbc"]
        cohorts[agent_id] = p31.build_micro_cohort(
            seed=seed,
            archetype_id=agent_id,
            archetype_pbc=archetype_pbc,
            parameters=parameters,
        )
    profile_identity = {
        profile.buyer_id: (
            profile.opportunity_interval,
            profile.opportunity_phase,
            profile.preference_offset,
            profile.baseline_pbc,
            profile.initial_loyalty,
        )
        for cohort in cohorts.values()
        for profile in cohort
    }

    cells: dict[tuple[str, str], dict[int, dict[str, float]]] = {}
    segment_totals: dict[tuple[str, str, str], dict[str, float]] = {}
    opportunity_signatures: dict[tuple[str, str], tuple[int, ...]] = {}
    for exp_id in sorted(psychology):
        for facilitation_label, facilitation_present in FACILITATION_LEVELS.items():
            tick_cells = _empty_tick_cells()
            segment_cells: dict[str, dict[str, float]] = defaultdict(
                lambda: {"opportunities": 0.0, "expected": 0.0, "realized": 0.0}
            )
            states: dict[str, p31.DemandState] = {
                profile.buyer_id: p31.DemandState(loyalty=profile.initial_loyalty)
                for cohort in cohorts.values()
                for profile in cohort
            }
            signature: list[int] = []
            for tick in range(1, 31):
                for agent_id in agents:
                    psych = psychology[exp_id][(agent_id, tick)]
                    cluster = clusters[agent_id]
                    for profile in cohorts[agent_id]:
                        result, next_state = p31.purchase_step(
                            seed=seed,
                            tick=tick,
                            attitude_att=psych["attitude_att"],
                            subjective_norm_sn=psych["subjective_norm_sn"],
                            trust=psych["trust_final"],
                            profile=profile,
                            state=states[profile.buyer_id],
                            facilitation_present=facilitation_present,
                            parameters=parameters,
                        )
                        states[profile.buyer_id] = next_state
                        if not result.opportunity:
                            continue
                        if result.choice_probability is None:
                            raise AssertionError("opportunity missing choice probability")
                        signature.append(tick)
                        bucket = tick_cells[tick]
                        bucket["opportunities"] += 1.0
                        bucket["expected"] += result.choice_probability
                        bucket["realized"] += float(result.focal_brand_chosen)
                        bucket["pbc"] += result.pbc
                        bucket["intention"] += result.purchase_intention
                        if tick >= 6:
                            segment = segment_cells[cluster]
                            segment["opportunities"] += 1.0
                            segment["expected"] += result.choice_probability
                            segment["realized"] += float(result.focal_brand_chosen)
            cells[(exp_id, facilitation_label)] = tick_cells
            opportunity_signatures[(exp_id, facilitation_label)] = tuple(signature)
            for cluster, totals in segment_cells.items():
                segment_totals[(exp_id, facilitation_label, cluster)] = totals

    signatures = set(opportunity_signatures.values())
    if len(signatures) != 1:
        raise ValueError(f"{replicate_id}: opportunity schedules differ across conditions")
    return {
        "replicate_id": replicate_id,
        "seed": seed,
        "agents": agents,
        "micro_population": len(profile_identity),
        "profile_identity": profile_identity,
        "cells": cells,
        "segments": segment_totals,
        "opportunity_signature": next(iter(signatures)),
        "condition_invariant_opportunity_schedule": True,
    }


def _recovery_tick(cell: dict[int, dict[str, float]]) -> int | None:
    baseline = _share(_range_sums(cell, 1, 4), "expected")
    crisis = _share(_range_sums(cell, 5, 5), "expected")
    loss = baseline - crisis
    if loss <= 0:
        return None
    threshold = baseline - 0.10 * loss
    for tick in range(6, 31):
        start = max(1, tick - 2)
        if _share(_range_sums(cell, start, tick), "expected") >= threshold:
            return tick
    return None


def _reference_outputs(blocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    conditions = sorted({key[0] for block in blocks for key in block["cells"]})
    curves: list[dict[str, Any]] = []
    condition_metrics: list[dict[str, Any]] = []
    segment_metrics: list[dict[str, Any]] = []

    for exp_id in conditions:
        for facilitation_label in FACILITATION_LEVELS:
            block_cells = [block["cells"][(exp_id, facilitation_label)] for block in blocks]
            for tick in range(1, 31):
                expected_values = []
                realized_values = []
                rolling_expected_values = []
                rolling_realized_values = []
                opportunity_values = []
                for cell in block_cells:
                    day = _range_sums(cell, tick, tick)
                    rolling = _range_sums(cell, max(1, tick - 6), tick)
                    expected_values.append(_share(day, "expected"))
                    realized_values.append(_share(day, "realized"))
                    rolling_expected_values.append(_share(rolling, "expected"))
                    rolling_realized_values.append(_share(rolling, "realized"))
                    opportunity_values.append(day["opportunities"])
                curves.append(
                    {
                        "exp_id": exp_id,
                        "facilitation": facilitation_label,
                        "tick": tick,
                        "mean_daily_opportunities": _mean(opportunity_values),
                        "expected_choice_share": _mean(expected_values),
                        "realized_choice_share": _mean(realized_values),
                        "rolling7_expected_choice_share": _mean(rolling_expected_values),
                        "rolling7_realized_choice_share": _mean(rolling_realized_values),
                    }
                )

            control_cells = [
                block["cells"][(CONTROL_ID, facilitation_label)] for block in blocks
            ]
            expected_post = []
            realized_post = []
            expected_active = []
            realized_active = []
            incremental_expected = []
            incremental_realized = []
            recovery_ticks: list[int] = []
            unresolved_recovery = 0
            for cell, control_cell in zip(block_cells, control_cells):
                post = _range_sums(cell, 6, 30)
                active = _range_sums(cell, 6, 19)
                control_post = _range_sums(control_cell, 6, 30)
                expected_post.append(_share(post, "expected"))
                realized_post.append(_share(post, "realized"))
                expected_active.append(_share(active, "expected"))
                realized_active.append(_share(active, "realized"))
                incremental_expected.append(
                    1000.0 * (_share(post, "expected") - _share(control_post, "expected"))
                )
                incremental_realized.append(
                    1000.0 * (_share(post, "realized") - _share(control_post, "realized"))
                )
                recovery = _recovery_tick(cell)
                if recovery is None:
                    unresolved_recovery += 1
                else:
                    recovery_ticks.append(recovery)
            condition_metrics.append(
                {
                    "exp_id": exp_id,
                    "facilitation": facilitation_label,
                    "post_expected_choice_share": _mean(expected_post),
                    "post_realized_choice_share": _mean(realized_post),
                    "active_expected_choice_share": _mean(expected_active),
                    "active_realized_choice_share": _mean(realized_active),
                    "incremental_expected_choices_per_1000_vs_matched_control": _mean(incremental_expected),
                    "incremental_realized_choices_per_1000_vs_matched_control": _mean(incremental_realized),
                    "mean_recovery_tick_when_resolved": _mean(recovery_ticks) if recovery_ticks else None,
                    "unresolved_recovery_blocks": unresolved_recovery,
                }
            )

            clusters = sorted(
                {
                    key[2]
                    for block in blocks
                    for key in block["segments"]
                    if key[0] == exp_id and key[1] == facilitation_label
                }
            )
            for cluster in clusters:
                expected_values = []
                realized_values = []
                for block in blocks:
                    totals = block["segments"][(exp_id, facilitation_label, cluster)]
                    expected_values.append(_share(totals, "expected"))
                    realized_values.append(_share(totals, "realized"))
                segment_metrics.append(
                    {
                        "exp_id": exp_id,
                        "facilitation": facilitation_label,
                        "cluster_type": cluster,
                        "post_expected_choice_share": _mean(expected_values),
                        "post_realized_choice_share": _mean(realized_values),
                    }
                )

    by_key = {(row["exp_id"], row["facilitation"]): row for row in condition_metrics}
    strategy_ids = [exp_id for exp_id in conditions if exp_id != CONTROL_ID]
    decomposition_rows = []
    for exp_id in strategy_ids:
        strategy_absent = by_key[(exp_id, "absent")]["post_expected_choice_share"]
        strategy_present = by_key[(exp_id, "present")]["post_expected_choice_share"]
        control_absent = by_key[(CONTROL_ID, "absent")]["post_expected_choice_share"]
        control_present = by_key[(CONTROL_ID, "present")]["post_expected_choice_share"]
        decomposition_rows.append(
            {
                "exp_id": exp_id,
                "communication_only_per_1000": 1000.0 * (strategy_absent - control_absent),
                "facilitation_only_per_1000": 1000.0 * (control_present - control_absent),
                "combined_total_per_1000": 1000.0 * (strategy_present - control_absent),
                "interaction_per_1000": 1000.0
                * ((strategy_present - strategy_absent) - (control_present - control_absent)),
            }
        )
    decomposition = {
        "by_strategy": decomposition_rows,
        "average_across_eight_strategies": {
            field: _mean([float(row[field]) for row in decomposition_rows])
            for field in (
                "communication_only_per_1000",
                "facilitation_only_per_1000",
                "combined_total_per_1000",
                "interaction_per_1000",
            )
        },
    }
    return curves, condition_metrics, segment_metrics, decomposition


def _summary_from_blocks(blocks: list[dict[str, Any]]) -> dict[str, float]:
    _, metrics, _, decomposition = _reference_outputs(blocks)
    by_key = {(row["exp_id"], row["facilitation"]): row for row in metrics}
    control = by_key[(CONTROL_ID, "absent")]
    average = decomposition["average_across_eight_strategies"]
    first_cell = blocks[0]["cells"][(CONTROL_ID, "absent")]
    baseline = _share(_range_sums(first_cell, 1, 4), "expected")
    crisis = _share(_range_sums(first_cell, 5, 5), "expected")
    return {
        "crisis_drop_reference_block": crisis - baseline,
        "control_post_expected_choice_share": control["post_expected_choice_share"],
        "communication_only_per_1000": average["communication_only_per_1000"],
        "facilitation_only_per_1000": average["facilitation_only_per_1000"],
        "combined_total_per_1000": average["combined_total_per_1000"],
        "interaction_per_1000": average["interaction_per_1000"],
    }


def _summary_for_parameters(
    *,
    variance_root: Path,
    clusters: dict[str, str],
    parameters: p31.DemandParameters,
) -> dict[str, float]:
    blocks = [
        _simulate_block(
            variance_root=variance_root,
            replicate_id=replicate_id,
            clusters=clusters,
            parameters=parameters,
        )
        for replicate_id in EXPECTED_REPLICATES
    ]
    return _summary_from_blocks(blocks)


def _sensitivity_worker(
    variance_root: Path,
    clusters: dict[str, str],
    scenario: str,
    parameters: p31.DemandParameters,
) -> tuple[str, p31.DemandParameters, dict[str, float]]:
    return (
        scenario,
        parameters,
        _summary_for_parameters(
            variance_root=variance_root,
            clusters=clusters,
            parameters=parameters,
        ),
    )


def _sensitivity_scenarios(reference: p31.DemandParameters) -> list[tuple[str, p31.DemandParameters]]:
    return [
        ("reference", reference),
        ("preference_sd_0.00", replace(reference, preference_sd=0.0)),
        ("preference_sd_1.00", replace(reference, preference_sd=1.0)),
        ("baseline_pbc_sd_0.00", replace(reference, baseline_pbc_sd=0.0)),
        ("baseline_pbc_sd_0.80", replace(reference, baseline_pbc_sd=0.8)),
        ("initial_loyalty_sd_0.00", replace(reference, initial_loyalty_sd=0.0)),
        ("initial_loyalty_sd_1.00", replace(reference, initial_loyalty_sd=1.0)),
        ("pbc_behavior_weight_0.00", replace(reference, pbc_behavior_weight=0.0)),
        ("pbc_behavior_weight_1.50", replace(reference, pbc_behavior_weight=1.5)),
        ("loyalty_weight_0.00", replace(reference, loyalty_weight=0.0)),
        ("loyalty_weight_1.00", replace(reference, loyalty_weight=1.0)),
        ("facilitation_signal_0.20", replace(reference, facilitation_signal=0.2)),
        ("facilitation_signal_0.50", replace(reference, facilitation_signal=0.5)),
    ]


def _legacy_diagnostics(variance_root: Path) -> dict[str, Any]:
    pbc_values: set[float] = set()
    post_intention_by_condition: dict[str, list[float]] = defaultdict(list)
    post_opportunities = []
    for replicate_id in EXPECTED_REPLICATES:
        seed, agents, psychology = _load_block(variance_root, replicate_id)
        del seed, agents
        for exp_id, rows in psychology.items():
            for (_, tick), values in rows.items():
                pbc_values.add(values["pbc"])
                if tick >= 6:
                    post_intention_by_condition[exp_id].append(values["purchase_intention"])
        diagnosis_path = ROOT / ".kiro/specs/task005-replication-inference/task005_purchase_construct_diagnosis1.0.json"
        if diagnosis_path.exists():
            diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
            post_opportunities = [
                int(row["v3_opportunities_per_condition"])
                for row in diagnosis["block_diagnostics"]
            ]
    control_mean = _mean(post_intention_by_condition[CONTROL_ID])
    condition_contrasts = {
        exp_id: _mean(values) - control_mean
        for exp_id, values in sorted(post_intention_by_condition.items())
        if exp_id != CONTROL_ID
    }
    return {
        "cognitive_agents_per_condition": 20,
        "unique_recorded_pbc_values": sorted(pbc_values),
        "pbc_is_constant": len(pbc_values) == 1,
        "subjective_norm_update_code_fact": (
            "mechanism_v2.py updates SN toward the combined message valence when at "
            "least one social observation exists; it does not measure perceived peer approval"
        ),
        "mean_old_v3_post_crisis_opportunities_per_condition": _mean(post_opportunities),
        "post_crisis_intention_contrast_vs_control_by_strategy": condition_contrasts,
        "min_strategy_intention_contrast": min(condition_contrasts.values()),
        "max_strategy_intention_contrast": max(condition_contrasts.values()),
    }


def build_report(
    *,
    variance_root: Path,
    profiles_path: Path,
    contract_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    clusters = _load_profiles(profiles_path)
    reference = p31.DemandParameters()
    reference_blocks = [
        _simulate_block(
            variance_root=variance_root,
            replicate_id=replicate_id,
            clusters=clusters,
            parameters=reference,
        )
        for replicate_id in EXPECTED_REPLICATES
    ]
    curves, metrics, segments, decomposition = _reference_outputs(reference_blocks)

    opportunity_signatures_equal = all(
        bool(block["condition_invariant_opportunity_schedule"])
        for block in reference_blocks
    )
    pre_treatment_differences = []
    for block in reference_blocks:
        baseline = block["cells"][(CONTROL_ID, "absent")]
        baseline_values = [
            _share(_range_sums(baseline, tick, tick), "expected") for tick in range(1, 5)
        ]
        for key, cell in block["cells"].items():
            values = [_share(_range_sums(cell, tick, tick), "expected") for tick in range(1, 5)]
            pre_treatment_differences.extend(
                abs(value - base) for value, base in zip(values, baseline_values)
            )
    pre_crisis_values = []
    crisis_values = []
    for block in reference_blocks:
        control_cell = block["cells"][(CONTROL_ID, "absent")]
        pre_crisis_values.append(_share(_range_sums(control_cell, 1, 4), "expected"))
        crisis_values.append(_share(_range_sums(control_cell, 5, 5), "expected"))
    pre_crisis = _mean(pre_crisis_values)
    crisis = _mean(crisis_values)

    no_effect = p31.no_effect_parameters(micro_buyers_per_archetype=1)
    no_effect_profile = p31.build_micro_profile(
        seed=1,
        archetype_id="structural-gate",
        micro_index=0,
        archetype_pbc=0.5,
        parameters=no_effect,
    )
    no_effect_intention, no_effect_probability = p31.focal_choice_probability(
        attitude_att=0.63,
        subjective_norm_sn=0.48,
        pbc=0.5,
        trust=6.2,
        profile=no_effect_profile,
        state=p31.DemandState(loyalty=0.0),
        parameters=no_effect,
    )

    sensitivity_design = _sensitivity_scenarios(reference)
    sensitivity_results: dict[str, tuple[p31.DemandParameters, dict[str, float]]] = {
        "reference": (reference, _summary_from_blocks(reference_blocks))
    }
    non_reference = [row for row in sensitivity_design if row[0] != "reference"]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(
                _sensitivity_worker,
                variance_root,
                clusters,
                scenario,
                parameters,
            )
            for scenario, parameters in non_reference
        ]
        for future in concurrent.futures.as_completed(futures):
            scenario, parameters, summary = future.result()
            sensitivity_results[scenario] = (parameters, summary)
    sensitivity_rows = []
    for scenario, _ in sensitivity_design:
        parameters, summary = sensitivity_results[scenario]
        sensitivity_rows.append(
            {"scenario": scenario, **asdict(parameters), **summary}
        )

    legacy = _legacy_diagnostics(variance_root)
    old_opportunities = float(legacy["mean_old_v3_post_crisis_opportunities_per_condition"])
    new_opportunities = _mean(
        [
            _range_sums(block["cells"][(CONTROL_ID, "absent")], 6, 30)["opportunities"]
            for block in reference_blocks
        ]
    )

    curve_path = output_dir / "task005_purchase_demand_v31_curves1.0.csv"
    metric_path = output_dir / "task005_purchase_demand_v31_condition_metrics1.0.csv"
    segment_path = output_dir / "task005_purchase_demand_v31_segment_metrics1.0.csv"
    sensitivity_path = output_dir / "task005_purchase_demand_v31_sensitivity1.0.csv"
    decomposition_path = output_dir / "task005_purchase_demand_v31_decomposition1.0.csv"
    _write_csv(curve_path, curves, list(curves[0]))
    _write_csv(metric_path, metrics, list(metrics[0]))
    _write_csv(segment_path, segments, list(segments[0]))
    _write_csv(sensitivity_path, sensitivity_rows, list(sensitivity_rows[0]))
    _write_csv(
        decomposition_path,
        decomposition["by_strategy"],
        list(decomposition["by_strategy"][0]),
    )

    gates = {
        "condition_invariant_opportunity_schedule": opportunity_signatures_equal,
        "pre_treatment_max_absolute_curve_difference": max(pre_treatment_differences),
        "pre_treatment_curves_identical": max(pre_treatment_differences) <= 1e-12,
        "reference_crisis_reduces_expected_choice": crisis < pre_crisis,
        "no_effect_probability_minus_intention": (
            no_effect_probability - no_effect_intention
        ),
        "no_effect_setting_collapses_to_intention": abs(
            no_effect_probability - no_effect_intention
        ) <= 1e-12,
        "communication_directly_changes_pbc": False,
        "facilitation_changes_trust_att_sn": False,
        "p_values_computed": False,
        "real_llm_calls_added": 0,
    }
    gates["all_required_gates_pass"] = all(
        (
            gates["condition_invariant_opportunity_schedule"],
            gates["pre_treatment_curves_identical"],
            gates["reference_crisis_reduces_expected_choice"],
            gates["no_effect_setting_collapses_to_intention"],
            not gates["communication_directly_changes_pbc"],
            not gates["facilitation_changes_trust_att_sn"],
            not gates["p_values_computed"],
            gates["real_llm_calls_added"] == 0,
        )
    )

    report = {
        "schema_version": "task005_purchase_demand_v31_replay1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "offline_structural_replay_not_formal_inference",
        "source": {
            "pilot_id": "task005-real-variance-pilot-v3",
            "replication_blocks": len(EXPECTED_REPLICATES),
            "contract_path": str(contract_path.relative_to(ROOT)),
            "contract_sha256": _sha256(contract_path),
            "all_block_estimands_sha256": _sha256(variance_root / "all_block_estimands.csv"),
        },
        "firewall": {
            "real_llm_calls_added": 0,
            "p_values": False,
            "formal_inference": False,
            "winner_selection": False,
            "coefficient_tuning": False,
            "v2_rows_reusable_for_v31_formal": False,
        },
        "legacy_structure_audit": legacy,
        "v31_reference_parameters": asdict(reference),
        "structural_gates": gates,
        "event_resolution": {
            "old_v3_mean_post_crisis_opportunities_per_condition": old_opportunities,
            "v31_mean_post_crisis_opportunities_per_condition": new_opportunities,
            "opportunity_count_multiplier": new_opportunities / old_opportunities,
            "old_full_period_event_resolution_percentage_points": 100.0 / old_opportunities,
            "v31_full_period_event_resolution_percentage_points": 100.0 / new_opportunities,
            "interpretation": (
                "Resolution changes the granularity and Monte Carlo noise of realized curves; "
                "it does not enlarge the expected treatment effect."
            ),
        },
        "reference_decomposition_per_1000_opportunities": decomposition,
        "sensitivity_scenarios": sensitivity_rows,
        "files": {
            "curves": str(curve_path.relative_to(ROOT)),
            "condition_metrics": str(metric_path.relative_to(ROOT)),
            "segment_metrics": str(segment_path.relative_to(ROOT)),
            "sensitivity": str(sensitivity_path.relative_to(ROOT)),
            "decomposition": str(decomposition_path.relative_to(ROOT)),
        },
        "decision": {
            "production_promotion": "NOT_AUTHORIZED",
            "real_llm_pilot": "NOT_AUTHORIZED",
            "formal_v2": "REMAINS_PAUSED",
            "next_required_work": [
                "correct subjective-norm measurement in the cognitive production path",
                "obtain empirical calibration or retain a prospectively frozen sensitivity design",
                "add v3.1 audit fields and run Windows-Kernel regression tests",
                "only then design a new independent engineering pilot"
            ]
        }
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variance_root", type=Path)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(
        variance_root=args.variance_root.resolve(),
        profiles_path=args.profiles.resolve(),
        contract_path=args.contract.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
