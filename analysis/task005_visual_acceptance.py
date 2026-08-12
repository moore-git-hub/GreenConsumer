"""Descriptive visual-acceptance audit for the completed TASK_005 pilot-v3.

This module deliberately computes no p-values and makes no formal inference.
It checks whether the frozen mechanism produces auditable, temporally coherent,
non-degenerate trajectories before the separate formal-v2 release chain is
completed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any, Iterable


PRIMARY_ESTIMANDS = (
    "P1_OVERALL_CLARIFICATION_POST_TRUST",
    "P2_CONTENT_POST_TRUST",
    "P3_TIMING_EARLY_TRUST",
    "P4_CHANNEL_REACH",
    "P5_OVERALL_CLARIFICATION_PURCHASE",
)

MANAGERIAL_MDE = {
    "P1_OVERALL_CLARIFICATION_POST_TRUST": 0.15,
    "P2_CONTENT_POST_TRUST": 0.15,
    "P3_TIMING_EARLY_TRUST": 0.15,
    "P4_CHANNEL_REACH": 0.15,
    "P5_OVERALL_CLARIFICATION_PURCHASE": 0.05,
}

EXPECTED_REPLICATES = tuple(f"R{i:03d}" for i in range(1, 11))
EXPECTED_CONDITIONS = 9
EXPECTED_STRATEGY_CELLS = 80


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(rows: Iterable[dict[str, Any]], field: str) -> float:
    return statistics.fmean(float(row[field]) for row in rows)


def _numeric_summary(values: list[float], mde: float | None = None) -> dict[str, Any]:
    if not values:
        raise ValueError("numeric summary requires values")
    result: dict[str, Any] = {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "sd": statistics.stdev(values) if len(values) > 1 else None,
        "min": min(values),
        "max": max(values),
        "positive": sum(value > 0 for value in values),
        "zero": sum(abs(value) < 1e-12 for value in values),
        "negative": sum(value < 0 for value in values),
        "unique_values": len(set(values)),
        "values": values,
    }
    if mde is not None:
        result["mde"] = mde
        result["descriptive_mean_over_mde"] = result["mean"] / mde
        result["blocks_abs_ge_mde"] = sum(abs(value) >= mde for value in values)
    return result


def _parse_condition_metrics(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in _read_csv(path):
        row: dict[str, Any] = dict(raw)
        row["is_control"] = str(raw["is_control"]).lower() == "true"
        for field in (
            "POST_TRUST_AUC",
            "EARLY_TRUST_AUC",
            "PURCHASE_RATE_T30",
            "PURCHASE_TRAJECTORY_AUC",
            "FINAL_TRUST_T30",
        ):
            row[field] = float(raw[field])
        row["REACH_RATE"] = None if raw["REACH_RATE"] == "" else float(raw["REACH_RATE"])
        rows.append(row)
    return rows


def _trajectory_groups(root: Path) -> tuple[dict[str, list[dict[str, float]]], dict[str, float]]:
    rows: list[dict[str, Any]] = []
    pretreatment_ranges: list[float] = []
    for replicate_id in EXPECTED_REPLICATES:
        block_rows: list[dict[str, Any]] = []
        for raw in _read_csv(root / replicate_id / "trajectories.csv"):
            exp_id = raw["exp_id"]
            row = {
                "replicate_id": replicate_id,
                "exp_id": exp_id,
                "tick": int(raw["tick"]),
                "avg_trust": float(raw["avg_trust"]),
                "purchase": float(raw["conversion_rate"]),
                "is_control": exp_id == "NoClarification-Control",
                "content": (
                    "rational" if exp_id.startswith("Rational")
                    else "empathy" if exp_id.startswith("Empathy")
                    else "control"
                ),
                "timing": (
                    "immediate" if exp_id.endswith("Immediate")
                    else "delayed" if exp_id.endswith("Delayed")
                    else "control"
                ),
                "channel": (
                    "hub" if "-Hub-" in exp_id
                    else "random" if "-Random-" in exp_id
                    else "control"
                ),
            }
            block_rows.append(row)
            rows.append(row)
        for tick in range(1, 6):
            values = [row["avg_trust"] for row in block_rows if row["tick"] == tick]
            pretreatment_ranges.append(max(values) - min(values))

    def selected(row: dict[str, Any], name: str) -> bool:
        if name == "control":
            return bool(row["is_control"])
        if name == "strategies":
            return not bool(row["is_control"])
        if name in {"rational", "empathy"}:
            return row["content"] == name
        if name in {"immediate", "delayed"}:
            return row["timing"] == name
        if name in {"hub", "random"}:
            return row["channel"] == name
        raise ValueError(f"unknown trajectory group: {name}")

    groups: dict[str, list[dict[str, float]]] = {}
    for name in ("control", "strategies", "rational", "empathy", "immediate", "delayed", "hub", "random"):
        series: list[dict[str, float]] = []
        for tick in range(1, 31):
            tick_rows = [row for row in rows if row["tick"] == tick and selected(row, name)]
            series.append(
                {
                    "tick": tick,
                    "trust": _mean(tick_rows, "avg_trust"),
                    "purchase": _mean(tick_rows, "purchase"),
                }
            )
        groups[name] = series

    all_trust = [float(row["avg_trust"]) for row in rows]
    dynamic = {
        "pretreatment_max_within_block_condition_range": max(pretreatment_ranges),
        "control_tick4_to_tick5": groups["control"][4]["trust"] - groups["control"][3]["trust"],
        "strategy_tick4_to_tick5": groups["strategies"][4]["trust"] - groups["strategies"][3]["trust"],
        "overall_clarification_minus_control_tick30": groups["strategies"][29]["trust"] - groups["control"][29]["trust"],
        "rational_minus_empathy_tick30": groups["rational"][29]["trust"] - groups["empathy"][29]["trust"],
        "immediate_minus_delayed_tick6": groups["immediate"][5]["trust"] - groups["delayed"][5]["trust"],
        "immediate_minus_delayed_tick10": groups["immediate"][9]["trust"] - groups["delayed"][9]["trust"],
        "immediate_minus_delayed_tick30": groups["immediate"][29]["trust"] - groups["delayed"][29]["trust"],
        "purchase_strategy_minus_control_tick30": groups["strategies"][29]["purchase"] - groups["control"][29]["purchase"],
        "trust_min": min(all_trust),
        "trust_max": max(all_trust),
    }
    return groups, dynamic


def build_report(variance_root: Path, manipulation_result_path: Path | None = None) -> dict[str, Any]:
    summary = _read_json(variance_root / "pilot_execution_summary.json")
    estimand_rows = _read_csv(variance_root / "all_block_estimands.csv")
    condition_rows = _parse_condition_metrics(variance_root / "all_condition_metrics.csv")
    trajectories, dynamic = _trajectory_groups(variance_root)

    primary: dict[str, Any] = {}
    for field in PRIMARY_ESTIMANDS:
        primary[field] = _numeric_summary(
            [float(row[field]) for row in estimand_rows],
            MANAGERIAL_MDE[field],
        )

    controls = {row["replicate_id"]: row for row in condition_rows if row["is_control"]}
    strategies = [row for row in condition_rows if not row["is_control"]]
    equal_purchase_cells = sum(
        abs(float(row["PURCHASE_RATE_T30"]) - float(controls[row["replicate_id"]]["PURCHASE_RATE_T30"])) < 1e-12
        for row in strategies
    )

    hub = [row for row in strategies if row["channel_factor"] == "hub"]
    random = [row for row in strategies if row["channel_factor"] == "random"]
    secondary = {
        "CHANNEL_POST_TRUST_mean": statistics.fmean(float(row["CHANNEL_POST_TRUST"]) for row in estimand_rows),
        "CHANNEL_PURCHASE_T30_mean": statistics.fmean(float(row["CHANNEL_PURCHASE_T30"]) for row in estimand_rows),
        "hub_reach_mean": _mean(hub, "REACH_RATE"),
        "random_reach_mean": _mean(random, "REACH_RATE"),
        "strategy_purchase_cells_equal_matched_control": equal_purchase_cells,
        "strategy_purchase_cells_total": EXPECTED_STRATEGY_CELLS,
        "strategy_purchase_equal_share": equal_purchase_cells / EXPECTED_STRATEGY_CELLS,
    }

    integrity_pass = all(
        (
            summary.get("PILOT_STATUS") == "PASS",
            summary.get("REAL_LLM_CALLS") == summary.get("AUDIT_LOG_ROWS") == 1896,
            summary.get("PLAN_FALLBACKS") == 0,
            summary.get("SEMANTIC_FALLBACKS") == 0,
            summary.get("REPLAY_MISS_TOTAL") == 0,
            len(estimand_rows) == len(EXPECTED_REPLICATES),
            len(condition_rows) == len(EXPECTED_REPLICATES) * EXPECTED_CONDITIONS,
        )
    )
    temporal_pass = (
        dynamic["pretreatment_max_within_block_condition_range"] <= 1e-12
        and dynamic["control_tick4_to_tick5"] < 0
        and dynamic["strategy_tick4_to_tick5"] < 0
        and dynamic["immediate_minus_delayed_tick6"] != 0
    )
    bounds_pass = 0 <= dynamic["trust_min"] <= dynamic["trust_max"] <= 10
    p5_values = primary["P5_OVERALL_CLARIFICATION_PURCHASE"]["values"]
    p5_nondegenerate = len(set(p5_values)) > 1 and any(abs(value) > 1e-12 for value in p5_values)

    manipulation = None
    hypocrisy_warning = False
    if manipulation_result_path is not None:
        manipulation = _read_json(manipulation_result_path)
        hypocrisy_warning = (
            manipulation.get("rational_hypocrisy_perceived_rate") == 1.0
            and manipulation.get("empathy_hypocrisy_perceived_rate") == 1.0
        )

    critical_pass = integrity_pass and temporal_pass and bounds_pass and p5_nondegenerate
    return {
        "schema_version": "task005_visual_acceptance_result1.0",
        "task": "TASK_005",
        "source": {
            "pilot_id": summary.get("pilot_id"),
            "pilot_blocks": len(EXPECTED_REPLICATES),
            "conditions_per_block": EXPECTED_CONDITIONS,
            "real_llm_calls_in_source": summary.get("REAL_LLM_CALLS"),
            "real_llm_calls_added": 0,
            "all_block_estimands_sha256": _sha256(variance_root / "all_block_estimands.csv"),
            "all_condition_metrics_sha256": _sha256(variance_root / "all_condition_metrics.csv"),
        },
        "firewall": {
            "descriptive_only": True,
            "formal_inference": False,
            "p_values": False,
            "strategy_winner_selection": False,
            "pilot_effect_used_to_change_mde_or_n": False,
            "mechanism_or_stimulus_tuning_from_desired_direction": False,
            "formal_reuse": False,
        },
        "gates": {
            "audit_integrity": "PASS" if integrity_pass else "FAIL",
            "temporal_onset_and_pretreatment_alignment": "PASS" if temporal_pass else "FAIL",
            "trust_bounds_and_finiteness": "PASS" if bounds_pass else "FAIL",
            "purchase_endpoint_resolution": "PASS_WITH_LOW_RESPONSE" if p5_nondegenerate else "FAIL_DEGENERATE",
            "visual_acceptance": "PASS_WITH_SCOPE_LOCK" if critical_pass else "HOLD",
        },
        "primary_descriptives": primary,
        "secondary_descriptives": secondary,
        "trajectory_groups": trajectories,
        "dynamic_checks": dynamic,
        "construct_warning": {
            "universal_hypocrisy_flag": hypocrisy_warning,
            "interpretation": (
                "Hypocrisy is saturated in both content conditions and cannot support a differential mediator claim."
                if hypocrisy_warning else "No universal hypocrisy saturation detected."
            ),
        },
        "scope_locks": [
            "P5 may be unsupported; a weak or null purchase result is not a licence to retune the frozen model.",
            "P4 identifies reach, not downstream trust or purchase conversion.",
            "Universal hypocrisy saturation forbids a differential hypocrisy-mediation claim in the present design.",
            "Pilot means and signs remain non-inferential and cannot alter the frozen MDEs, N=46, or P1-P5 family.",
        ],
        "manipulation_result": manipulation,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variance_root", type=Path)
    parser.add_argument("--manipulation-result", type=Path)
    args = parser.parse_args()
    report = build_report(args.variance_root, args.manipulation_result)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
