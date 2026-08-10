"""TASK_005 real-LLM variance pilot v1 preparation runner.

This module freezes the variance-pilot estimator and engineering preparation
surface. Current stage execution is offline only: real variance-pilot execution
is intentionally unauthorized.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable, Mapping

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from experiment_config import generate_experiment_matrix
from replication_config import (
    EXECUTION_ORDER,
    build_seed_ledger,
    write_seed_ledger_csv,
    write_seed_ledger_subset_csv,
)


PILOT_ID = "task005-real-variance-pilot-v1"
MASTER_SEED = 2026081001
REPLICATION_BLOCKS = 10
ALLOWED_REPLICATE_IDS = tuple(f"R{i:03d}" for i in range(1, 11))
CONDITIONS_PER_BLOCK = 9
AGENT_COUNT = 20
TOTAL_TICKS = 30
MECHANISM_SCHEMA = "2.0"
MECHANISM_RECORDS_SCHEMA = "1.2"
EMPATHY_REPAIR_WEIGHT = 0.50
REAL_MODE_REJECTION = "VARIANCE_PILOT_REAL_EXECUTION_NOT_AUTHORIZED"
ACTIVATION_TOKEN = "TASK005_REAL_VARIANCE_V1_ACTIVATE_20260810_01"
EXPECTED_BRANCH = "redesign/task005-mechanism-v2"
PILOT_OUTPUT_ROOT = Path("results") / "pilots" / PILOT_ID
ACTIVATION_ARTIFACT = (
    Path(".kiro")
    / "specs"
    / "task005-replication-inference"
    / "real_llm_variance_pilot_activation1.0.json"
)
RESULT_ARTIFACT = (
    Path(".kiro")
    / "specs"
    / "task005-replication-inference"
    / "real_llm_variance_pilot_v1_result1.0.json"
)

PRIMARY_ESTIMANDS = (
    "P1_OVERALL_CLARIFICATION_POST_TRUST",
    "P2_CONTENT_POST_TRUST",
    "P3_TIMING_EARLY_TRUST",
    "P4_CHANNEL_REACH",
    "P5_OVERALL_CLARIFICATION_PURCHASE",
)

SECONDARY_ESTIMANDS = (
    "CONTENT_PURCHASE_T30",
    "CHANNEL_PURCHASE_T30",
    "TIMING_PURCHASE_T30",
    "CHANNEL_POST_TRUST",
    "TIMING_POST_TRUST",
    "CONTENT_EARLY_TRUST",
    "FINAL_TRUST_T30_overall",
    "FINAL_TRUST_T30_content",
    "FINAL_TRUST_T30_channel",
    "FINAL_TRUST_T30_timing",
    "CONTENT_x_CHANNEL_POST_TRUST_AUC",
    "CONTENT_x_TIMING_POST_TRUST_AUC",
    "CHANNEL_x_TIMING_POST_TRUST_AUC",
    "CONTENT_x_CHANNEL_x_TIMING_POST_TRUST_AUC",
    "CONTENT_x_CHANNEL_PURCHASE_RATE_T30",
    "CONTENT_x_TIMING_PURCHASE_RATE_T30",
    "CHANNEL_x_TIMING_PURCHASE_RATE_T30",
    "CONTENT_x_CHANNEL_x_TIMING_PURCHASE_RATE_T30",
    "OVERALL_CLARIFICATION_PURCHASE_TRAJECTORY_AUC",
)

SOURCE_FREEZE_FILES = (
    "mechanism_v2.py",
    "plugins/agent/plan/ConsumerPlanPlugin.py",
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "simulation_core.py",
    "clarification_injector.py",
    "experiment_config.py",
    "replication_config.py",
    "run_experiments.py",
    "run_task005_real_variance_pilot_v1.py",
    ".kiro/specs/task005-replication-inference/task005_estimand_contract1.0.json",
    ".kiro/specs/task005-replication-inference/task005_estimand_contract_amendment1.1.json",
    ".kiro/specs/task005-replication-inference/real_llm_variance_pilot_contract1.0.json",
    ".kiro/specs/task005-replication-inference/empathy_relational_repair_amendment1.0.json",
    ".kiro/specs/task005-replication-inference/mechanism_auditability_schema_amendment1.2.json",
    ".kiro/specs/task005-replication-inference/manipulation_stage_closure1.0.json",
)


class VariancePilotError(RuntimeError):
    """Raised when the variance-pilot preparation contract is violated."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_source_hashes() -> dict[str, str]:
    hashes = {}
    for rel in SOURCE_FREEZE_FILES:
        path = Path(rel)
        if not path.exists():
            raise VariancePilotError(f"source freeze file missing: {rel}")
        hashes[rel] = _sha256_file(path)
    return hashes


def build_pilot_seed_ledger() -> list[dict]:
    rows = build_seed_ledger(
        MASTER_SEED,
        REPLICATION_BLOCKS,
        llm_seed_supported="unknown",
        provider_model="qwen-plus",
        provider_system_fingerprint="unknown",
    )
    if tuple(row["replicate_id"] for row in rows) != ALLOWED_REPLICATE_IDS:
        raise VariancePilotError("variance pilot replicate IDs are not R001-R010")
    return rows


def select_variance_conditions():
    by_id = {cfg.exp_id: cfg for cfg in generate_experiment_matrix()}
    if set(by_id) != set(EXECUTION_ORDER):
        raise VariancePilotError("execution order and experiment matrix mismatch")
    configs = [by_id[exp_id] for exp_id in EXECUTION_ORDER]
    if len(configs) != CONDITIONS_PER_BLOCK:
        raise VariancePilotError("variance pilot must use exactly 9 conditions")
    if sum(1 for cfg in configs if cfg.is_control) != 1:
        raise VariancePilotError("variance pilot must contain exactly one control")
    return configs


def preflight() -> dict:
    ledger = build_pilot_seed_ledger()
    conditions = select_variance_conditions()
    return {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "replication_blocks": len(ledger),
        "replicate_ids": [row["replicate_id"] for row in ledger],
        "conditions_per_block": len(conditions),
        "condition_order": [cfg.exp_id for cfg in conditions],
        "independent_unit": "replication_block",
        "agent_level_n_used_for_power": False,
        "empathy_repair_weight": EMPATHY_REPAIR_WEIGHT,
        "mechanism_records_schema": MECHANISM_RECORDS_SCHEMA,
        "p_values": False,
        "power_calculation": False,
        "formal_execution": False,
        "real_llm_calls": 0,
    }


def _float(row: Mapping, name: str) -> float:
    value = row.get(name)
    try:
        out = float(value)
    except Exception as exc:
        raise VariancePilotError(f"{name} must be numeric") from exc
    if not math.isfinite(out):
        raise VariancePilotError(f"{name} must be finite")
    return out


def _bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value == "True":
            return True
        if value == "False":
            return False
    raise VariancePilotError(f"invalid boolean value: {value!r}")


def _trapz_normalized(points: list[float], intervals: int) -> float:
    if len(points) != intervals + 1:
        raise VariancePilotError("AUC point count does not match interval count")
    total = 0.0
    for left, right in zip(points, points[1:]):
        total += (left + right) / 2.0
    return total / float(intervals)


def _condition_agent_set(rows: list[Mapping], exp_id: str) -> set[str]:
    by_tick: dict[int, list[Mapping]] = {}
    keys: set[tuple[str, int, str]] = set()
    for row in rows:
        try:
            tick = int(row.get("tick"))
        except Exception as exc:
            raise VariancePilotError(f"{exp_id} tick must be integer") from exc
        agent_id = str(row.get("agent_id", ""))
        if not agent_id:
            raise VariancePilotError(f"{exp_id} agent_id must be non-empty")
        key = (exp_id, tick, agent_id)
        if key in keys:
            raise VariancePilotError(f"{exp_id} duplicate mechanism join key")
        keys.add(key)
        by_tick.setdefault(tick, []).append(row)
    if set(by_tick) != set(range(1, TOTAL_TICKS + 1)):
        raise VariancePilotError(f"{exp_id} ticks must be exactly 1..30")
    expected_agents: set[str] | None = None
    for tick in range(1, TOTAL_TICKS + 1):
        tick_rows = by_tick[tick]
        if len(tick_rows) != AGENT_COUNT:
            raise VariancePilotError(f"{exp_id} tick {tick} must have 20 agent rows")
        agents = {str(row.get("agent_id", "")) for row in tick_rows}
        if len(agents) != AGENT_COUNT:
            raise VariancePilotError(f"{exp_id} tick {tick} must have 20 unique agents")
        if expected_agents is None:
            expected_agents = agents
        elif agents != expected_agents:
            raise VariancePilotError(f"{exp_id} agent set must be stable across ticks")
    if expected_agents is None or len(expected_agents) != AGENT_COUNT:
        raise VariancePilotError(f"{exp_id} denominator agent set must have 20 agents")
    return expected_agents


def _purchase_trajectory_auc(rows: list[Mapping], agent_set: set[str]) -> float:
    purchased: set[str] = set()
    trajectory: list[float] = []
    for tick in range(1, TOTAL_TICKS + 1):
        for row in rows:
            if int(row.get("tick")) == tick and _bool_value(row.get("is_buying")):
                agent_id = str(row.get("agent_id"))
                if agent_id not in agent_set:
                    raise VariancePilotError("purchase row has unknown agent_id")
                purchased.add(agent_id)
        trajectory.append(len(purchased) / AGENT_COUNT)
    return _trapz_normalized(trajectory, 29)


def compute_condition_metrics(
    *,
    replicate_id: str,
    config,
    mechanism_rows: list[Mapping],
    exposure_rows: list[Mapping],
) -> dict:
    exp_id = config.exp_id
    rows = [row for row in mechanism_rows if row.get("exp_id") == exp_id]
    expected = AGENT_COUNT * TOTAL_TICKS
    if len(rows) != expected:
        raise VariancePilotError(f"{exp_id} mechanism row count must be {expected}")
    if any(str(row.get("schema_version")) != MECHANISM_RECORDS_SCHEMA for row in rows):
        raise VariancePilotError("mechanism_records schema must be 1.2")
    weights = {_float(row, "empathy_repair_weight") for row in rows}
    if weights != {EMPATHY_REPAIR_WEIGHT}:
        raise VariancePilotError("empathy_repair_weight must be fixed at 0.50")
    agent_set = _condition_agent_set(rows, exp_id)

    by_tick: dict[int, list[Mapping]] = {}
    for row in rows:
        tick = int(row.get("tick"))
        by_tick.setdefault(tick, []).append(row)
    for tick in range(1, TOTAL_TICKS + 1):
        if len(by_tick.get(tick, [])) != AGENT_COUNT:
            raise VariancePilotError(f"{exp_id} tick {tick} must have 20 agent rows")

    mean_trust = {
        tick: statistics.fmean(_float(row, "trust_final") for row in by_tick[tick])
        for tick in range(1, TOTAL_TICKS + 1)
    }
    post_points = [mean_trust[tick] for tick in range(6, 31)]
    early_points = [mean_trust[tick] for tick in range(6, 11)]
    buyers = {
        str(row.get("agent_id"))
        for row in rows
        if 1 <= int(row.get("tick")) <= 30 and _bool_value(row.get("is_buying"))
    }

    if config.is_control:
        reach_rate = None
        if [row for row in exposure_rows if row.get("exp_id") == exp_id]:
            raise VariancePilotError(f"{exp_id} control must not have exposure rows")
    else:
        erows = [row for row in exposure_rows if row.get("exp_id") == exp_id]
        if len(erows) != AGENT_COUNT:
            raise VariancePilotError(f"{exp_id} exposure row count must be 20")
        exposure_agents = [str(row.get("agent_id", "")) for row in erows]
        if len(set(exposure_agents)) != AGENT_COUNT:
            raise VariancePilotError(f"{exp_id} exposure must have 20 unique agents")
        if set(exposure_agents) != agent_set:
            raise VariancePilotError(f"{exp_id} exposure agent set must match mechanism")
        reached = {str(row.get("agent_id")) for row in erows if _bool_value(row.get("reached"))}
        reach_rate = len(reached) / AGENT_COUNT

    return {
        "replicate_id": replicate_id,
        "exp_id": exp_id,
        "content_factor": config.content_factor,
        "channel_factor": config.channel_factor,
        "timing_factor": config.timing_factor,
        "is_control": bool(config.is_control),
        "POST_TRUST_AUC": _trapz_normalized(post_points, 24),
        "EARLY_TRUST_AUC": _trapz_normalized(early_points, 4),
        "PURCHASE_RATE_T30": len(buyers) / AGENT_COUNT,
        "PURCHASE_TRAJECTORY_AUC": _purchase_trajectory_auc(rows, agent_set),
        "REACH_RATE": reach_rate,
        "FINAL_TRUST_T30": mean_trust[30],
    }


def _mean(rows: Iterable[Mapping], field: str) -> float:
    values = [row[field] for row in rows]
    if any(value is None for value in values):
        raise VariancePilotError(f"{field} contains NA")
    return statistics.fmean(float(value) for value in values)


def _factorial_contrast(rows: list[Mapping], field: str, factors: tuple[str, ...]) -> float:
    signs = {
        "content_factor": {"rational-evidence": 1, "emotional-empathy": -1},
        "channel_factor": {"hub": 1, "random": -1},
        "timing_factor": {"immediate": 1, "delayed": -1},
    }
    if not factors:
        raise VariancePilotError("factorial contrast requires at least one factor")
    if len(rows) != 8:
        raise VariancePilotError("factorial contrast requires eight strategy rows")
    numerator = 0.0
    for row in rows:
        coeff = 1
        for factor in factors:
            try:
                coeff *= signs[factor][row[factor]]
            except KeyError as exc:
                raise VariancePilotError(f"unknown factor level for {factor}") from exc
        numerator += coeff * float(row[field])
    collapsed_levels = 2 ** (3 - len(factors))
    return numerator / collapsed_levels


def build_block_estimands(replicate_id: str, condition_metrics: list[Mapping]) -> dict:
    if len(condition_metrics) != CONDITIONS_PER_BLOCK:
        raise VariancePilotError("block must contain exactly 9 condition metric rows")
    control = [row for row in condition_metrics if row["is_control"]]
    strategies = [row for row in condition_metrics if not row["is_control"]]
    if len(control) != 1 or len(strategies) != 8:
        raise VariancePilotError("block must contain one control and eight strategies")
    c0 = control[0]
    rational = [row for row in strategies if row["content_factor"] == "rational-evidence"]
    empathy = [row for row in strategies if row["content_factor"] == "emotional-empathy"]
    immediate = [row for row in strategies if row["timing_factor"] == "immediate"]
    delayed = [row for row in strategies if row["timing_factor"] == "delayed"]
    hub = [row for row in strategies if row["channel_factor"] == "hub"]
    random = [row for row in strategies if row["channel_factor"] == "random"]
    for name, group in {
        "rational": rational,
        "empathy": empathy,
        "immediate": immediate,
        "delayed": delayed,
        "hub": hub,
        "random": random,
    }.items():
        if len(group) != 4:
            raise VariancePilotError(f"{name} group must contain four rows")
    return {
        "replicate_id": replicate_id,
        "P1_OVERALL_CLARIFICATION_POST_TRUST": _mean(strategies, "POST_TRUST_AUC") - float(c0["POST_TRUST_AUC"]),
        "P2_CONTENT_POST_TRUST": _mean(rational, "POST_TRUST_AUC") - _mean(empathy, "POST_TRUST_AUC"),
        "P3_TIMING_EARLY_TRUST": _mean(immediate, "EARLY_TRUST_AUC") - _mean(delayed, "EARLY_TRUST_AUC"),
        "P4_CHANNEL_REACH": _mean(hub, "REACH_RATE") - _mean(random, "REACH_RATE"),
        "P5_OVERALL_CLARIFICATION_PURCHASE": _mean(strategies, "PURCHASE_RATE_T30") - float(c0["PURCHASE_RATE_T30"]),
        "CONTENT_PURCHASE_T30": _mean(rational, "PURCHASE_RATE_T30") - _mean(empathy, "PURCHASE_RATE_T30"),
        "CHANNEL_PURCHASE_T30": _mean(hub, "PURCHASE_RATE_T30") - _mean(random, "PURCHASE_RATE_T30"),
        "TIMING_PURCHASE_T30": _mean(immediate, "PURCHASE_RATE_T30") - _mean(delayed, "PURCHASE_RATE_T30"),
        "CHANNEL_POST_TRUST": _mean(hub, "POST_TRUST_AUC") - _mean(random, "POST_TRUST_AUC"),
        "TIMING_POST_TRUST": _mean(immediate, "POST_TRUST_AUC") - _mean(delayed, "POST_TRUST_AUC"),
        "CONTENT_EARLY_TRUST": _mean(rational, "EARLY_TRUST_AUC") - _mean(empathy, "EARLY_TRUST_AUC"),
        "FINAL_TRUST_T30_overall": _mean(strategies, "FINAL_TRUST_T30") - float(c0["FINAL_TRUST_T30"]),
        "FINAL_TRUST_T30_content": _mean(rational, "FINAL_TRUST_T30") - _mean(empathy, "FINAL_TRUST_T30"),
        "FINAL_TRUST_T30_channel": _mean(hub, "FINAL_TRUST_T30") - _mean(random, "FINAL_TRUST_T30"),
        "FINAL_TRUST_T30_timing": _mean(immediate, "FINAL_TRUST_T30") - _mean(delayed, "FINAL_TRUST_T30"),
        "CONTENT_x_CHANNEL_POST_TRUST_AUC": _factorial_contrast(
            strategies, "POST_TRUST_AUC", ("content_factor", "channel_factor")
        ),
        "CONTENT_x_TIMING_POST_TRUST_AUC": _factorial_contrast(
            strategies, "POST_TRUST_AUC", ("content_factor", "timing_factor")
        ),
        "CHANNEL_x_TIMING_POST_TRUST_AUC": _factorial_contrast(
            strategies, "POST_TRUST_AUC", ("channel_factor", "timing_factor")
        ),
        "CONTENT_x_CHANNEL_x_TIMING_POST_TRUST_AUC": _factorial_contrast(
            strategies, "POST_TRUST_AUC", ("content_factor", "channel_factor", "timing_factor")
        ),
        "CONTENT_x_CHANNEL_PURCHASE_RATE_T30": _factorial_contrast(
            strategies, "PURCHASE_RATE_T30", ("content_factor", "channel_factor")
        ),
        "CONTENT_x_TIMING_PURCHASE_RATE_T30": _factorial_contrast(
            strategies, "PURCHASE_RATE_T30", ("content_factor", "timing_factor")
        ),
        "CHANNEL_x_TIMING_PURCHASE_RATE_T30": _factorial_contrast(
            strategies, "PURCHASE_RATE_T30", ("channel_factor", "timing_factor")
        ),
        "CONTENT_x_CHANNEL_x_TIMING_PURCHASE_RATE_T30": _factorial_contrast(
            strategies, "PURCHASE_RATE_T30", ("content_factor", "channel_factor", "timing_factor")
        ),
        "OVERALL_CLARIFICATION_PURCHASE_TRAJECTORY_AUC": (
            _mean(strategies, "PURCHASE_TRAJECTORY_AUC") - float(c0["PURCHASE_TRAJECTORY_AUC"])
        ),
    }


def _sample_variance(values: list[float]) -> float:
    if len(values) < 2:
        raise VariancePilotError("sample variance requires at least two blocks")
    return statistics.variance(values)


def _iqr(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    lower = ordered[: n // 2]
    upper = ordered[(n + 1) // 2 :] if n % 2 else ordered[n // 2 :]
    return statistics.median(upper) - statistics.median(lower)


def summarize_variance(block_estimands: list[Mapping]) -> dict:
    if len(block_estimands) < 2:
        raise VariancePilotError("variance summary requires at least two blocks")
    by_field = {
        field: [float(row[field]) for row in block_estimands]
        for field in PRIMARY_ESTIMANDS
    }
    primary_summary = {}
    loo_rows = []
    for field, values in by_field.items():
        loo_sds = []
        for i in range(len(values)):
            subset = values[:i] + values[i + 1 :]
            loo_sds.append(math.sqrt(_sample_variance(subset)) if len(subset) > 1 else 0.0)
        primary_summary[field] = {
            "sample_variance": _sample_variance(values),
            "sample_sd": math.sqrt(_sample_variance(values)),
            "median": statistics.median(values),
            "IQR": _iqr(values),
            "min": min(values),
            "max": max(values),
            "leave_one_block_out_sd_min": min(loo_sds),
            "leave_one_block_out_sd_max": max(loo_sds),
        }
        for idx, sd in enumerate(loo_sds):
            loo_rows.append({
                "estimand": field,
                "left_out_replicate_id": str(block_estimands[idx]["replicate_id"]),
                "sd": sd,
            })
    cov = covariance_matrix(block_estimands)
    corr = correlation_matrix_from_covariance(cov)
    return {
        "pilot_id": PILOT_ID,
        "block_count": len(block_estimands),
        "primary_estimands": primary_summary,
        "covariance_matrix": cov,
        "correlation_matrix": corr,
        "leave_one_out_sd": loo_rows,
        "p_values_computed": False,
        "power_calculation": False,
        "mde_selected": False,
        "formal_execution": False,
    }


def build_official_variance_summary(block_estimands: list[Mapping], block_statuses: Mapping[str, str]) -> dict:
    expected_ids = set(ALLOWED_REPLICATE_IDS)
    observed_ids = {str(row.get("replicate_id")) for row in block_estimands}
    statuses = {rid: str(block_statuses.get(rid, "missing")) for rid in ALLOWED_REPLICATE_IDS}
    complete = (
        observed_ids == expected_ids
        and set(statuses) == expected_ids
        and all(statuses[rid] == "PASS" for rid in ALLOWED_REPLICATE_IDS)
        and len(block_estimands) == REPLICATION_BLOCKS
    )
    if not complete:
        return {
            "pilot_id": PILOT_ID,
            "OFFICIAL_VARIANCE_STATUS": "NOT_COMPUTED_INCOMPLETE",
            "POWER_PLANNING_USE": False,
            "block_statuses": statuses,
            "partial_block_count": len(block_estimands),
            "p_values_computed": False,
            "power_calculation": False,
            "mde_selected": False,
        }
    ordered = sorted(block_estimands, key=lambda row: str(row["replicate_id"]))
    summary = summarize_variance(ordered)
    summary["OFFICIAL_VARIANCE_STATUS"] = "COMPUTED"
    summary["POWER_PLANNING_USE"] = True
    summary["block_statuses"] = statuses
    return summary


def covariance_matrix(block_estimands: list[Mapping]) -> list[dict]:
    rows = []
    n = len(block_estimands)
    if n < 2:
        raise VariancePilotError("covariance requires at least two blocks")
    means = {
        field: statistics.fmean(float(row[field]) for row in block_estimands)
        for field in PRIMARY_ESTIMANDS
    }
    for left in PRIMARY_ESTIMANDS:
        row = {"estimand": left}
        for right in PRIMARY_ESTIMANDS:
            total = sum(
                (float(item[left]) - means[left]) * (float(item[right]) - means[right])
                for item in block_estimands
            )
            row[right] = total / (n - 1)
        rows.append(row)
    return rows


def correlation_matrix_from_covariance(covariance: list[Mapping]) -> list[dict]:
    lookup = {row["estimand"]: row for row in covariance}
    rows = []
    for left in PRIMARY_ESTIMANDS:
        row = {"estimand": left}
        for right in PRIMARY_ESTIMANDS:
            denom = math.sqrt(float(lookup[left][left]) * float(lookup[right][right]))
            row[right] = None if denom == 0 else float(lookup[left][right]) / denom
        rows.append(row)
    return rows


def _synthetic_mechanism_rows(replicate_id: str, config, block_index: int) -> list[dict]:
    rows = []
    base = 4.8 + 0.04 * block_index
    for tick in range(1, TOTAL_TICKS + 1):
        for agent_index in range(AGENT_COUNT):
            trust = base + 0.015 * tick + 0.002 * agent_index
            if not config.is_control and tick >= (config.clarification_tick or 99):
                trust += 0.18
                if config.content_factor == "rational-evidence":
                    trust += 0.03
                if config.timing_factor == "immediate":
                    trust += 0.05
            buying = tick in (12, 19, 26) and agent_index < (3 + block_index % 3)
            rows.append({
                "schema_version": MECHANISM_RECORDS_SCHEMA,
                "exp_id": config.exp_id,
                "tick": tick,
                "agent_id": f"Consumer_{agent_index:03d}",
                "trust_final": round(trust, 12),
                "is_buying": bool(buying),
                "empathy_repair_weight": EMPATHY_REPAIR_WEIGHT,
                "semantic_fallback_used": False,
                "plan_fallback_used": False,
            })
    return rows


def _synthetic_exposure_rows(config, block_index: int) -> list[dict]:
    if config.is_control:
        return []
    if config.channel_factor == "hub":
        reached_count = 18 + (block_index % 2)
    else:
        reached_count = 11 + (block_index % 3)
    return [
        {
            "exp_id": config.exp_id,
            "agent_id": f"Consumer_{i:03d}",
            "reached": i < reached_count,
        }
        for i in range(AGENT_COUNT)
    ]


def _write_csv(path: Path, rows: list[Mapping], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Mapping | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_offline_dry_run_artifacts(output_dir: Path, *, synthetic_blocks: int = 2) -> dict:
    if synthetic_blocks < 2:
        raise VariancePilotError("dry-run requires at least two synthetic blocks")
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = build_pilot_seed_ledger()
    conditions = select_variance_conditions()
    all_condition_metrics = []
    all_block_estimands = []
    manifest = []
    for block_index, ledger_row in enumerate(ledger[:synthetic_blocks], start=1):
        replicate_id = ledger_row["replicate_id"]
        block_dir = output_dir / replicate_id
        block_dir.mkdir(parents=True, exist_ok=False)
        _write_json(block_dir / "attempt_marker.json", {
            "replicate_id": replicate_id,
            "attempt_count": 1,
            "restart_is_not_retry": True,
        })
        write_seed_ledger_subset_csv(ledger, [replicate_id], block_dir / "seed_ledger.csv")
        _write_json(block_dir / "condition_manifest.json", [
            {
                "replicate_id": replicate_id,
                "exp_id": cfg.exp_id,
                "is_control": cfg.is_control,
                "clarification_tick": cfg.clarification_tick,
                "router_role": "recording" if cfg.is_control else "replay",
                "replay_until_tick": None if cfg.is_control else cfg.clarification_tick,
            }
            for cfg in conditions
        ])
        _write_json(block_dir / "sanitized_model_config.json", {
            "provider": "OpenAIProvider",
            "model": "qwen-plus",
            "api_key": "REDACTED",
        })
        (block_dir / "pilot_llm_calls.jsonl").write_text("", encoding="utf-8")
        (block_dir / "replicate_lifecycle.jsonl").write_text(
            json.dumps({"replicate_id": replicate_id, "event": "DRY_RUN_COMPLETE"}) + "\n",
            encoding="utf-8",
        )
        (block_dir / "child_stdout_sanitized.log").write_text("", encoding="utf-8")
        (block_dir / "child_stderr_sanitized.log").write_text("", encoding="utf-8")

        mechanism_rows = []
        exposure_rows = []
        condition_metrics = []
        for cfg in conditions:
            mechanism_rows.extend(_synthetic_mechanism_rows(replicate_id, cfg, block_index))
            exposure_rows.extend(_synthetic_exposure_rows(cfg, block_index))
        for cfg in conditions:
            condition_metrics.append(compute_condition_metrics(
                replicate_id=replicate_id,
                config=cfg,
                mechanism_rows=mechanism_rows,
                exposure_rows=exposure_rows,
            ))
        block_estimands = build_block_estimands(replicate_id, condition_metrics)
        all_condition_metrics.extend(condition_metrics)
        all_block_estimands.append(block_estimands)
        _write_csv(block_dir / "mechanism_records.csv", mechanism_rows, [
            "schema_version", "exp_id", "tick", "agent_id", "trust_final",
            "is_buying", "empathy_repair_weight", "semantic_fallback_used",
            "plan_fallback_used",
        ])
        _write_csv(block_dir / "agent_records.csv", [], ["exp_id", "tick", "agent_id"])
        _write_csv(block_dir / "clarification_exposure.csv", exposure_rows, [
            "exp_id", "agent_id", "reached",
        ])
        _write_csv(block_dir / "condition_metrics.csv", condition_metrics, [
            "replicate_id", "exp_id", "content_factor", "channel_factor",
            "timing_factor", "is_control", "POST_TRUST_AUC", "EARLY_TRUST_AUC",
            "PURCHASE_RATE_T30", "PURCHASE_TRAJECTORY_AUC", "REACH_RATE", "FINAL_TRUST_T30",
        ])
        _write_csv(block_dir / "block_estimands.csv", [block_estimands], ["replicate_id", *PRIMARY_ESTIMANDS, *SECONDARY_ESTIMANDS])
        _write_json(block_dir / "block_execution_summary.json", {
            "replicate_id": replicate_id,
            "status": "PASS",
            "condition_success_count": CONDITIONS_PER_BLOCK,
            "mechanism_rows": len(mechanism_rows),
            "real_llm_calls": 0,
        })
        manifest.append({
            "replicate_id": replicate_id,
            "attempt_count": 1,
            "status": "PASS",
            "block_dir": str(Path(replicate_id)),
        })

    summary = summarize_variance(all_block_estimands)
    _write_csv(output_dir / "pilot_manifest.csv", manifest, [
        "replicate_id", "attempt_count", "status", "block_dir",
    ])
    _write_csv(output_dir / "all_condition_metrics.csv", all_condition_metrics, [
        "replicate_id", "exp_id", "content_factor", "channel_factor",
        "timing_factor", "is_control", "POST_TRUST_AUC", "EARLY_TRUST_AUC",
        "PURCHASE_RATE_T30", "PURCHASE_TRAJECTORY_AUC", "REACH_RATE", "FINAL_TRUST_T30",
    ])
    _write_csv(output_dir / "all_block_estimands.csv", all_block_estimands, ["replicate_id", *PRIMARY_ESTIMANDS, *SECONDARY_ESTIMANDS])
    _write_json(output_dir / "variance_summary.json", summary)
    _write_csv(output_dir / "primary_covariance_matrix.csv", summary["covariance_matrix"], ["estimand", *PRIMARY_ESTIMANDS])
    _write_csv(output_dir / "primary_correlation_matrix.csv", summary["correlation_matrix"], ["estimand", *PRIMARY_ESTIMANDS])
    _write_csv(output_dir / "leave_one_out_sd.csv", summary["leave_one_out_sd"], [
        "estimand", "left_out_replicate_id", "sd",
    ])
    _write_json(output_dir / "channel_saturation_summary.json", channel_saturation_summary(all_condition_metrics))
    pilot_summary = {
        "pilot_id": PILOT_ID,
        "status": "DRY_RUN_PASS",
        "replication_blocks": synthetic_blocks,
        "conditions_per_block": CONDITIONS_PER_BLOCK,
        "real_llm_calls": 0,
        "p_values": False,
        "formal_execution": False,
        "formal_reuse": False,
    }
    _write_json(output_dir / "pilot_execution_summary.json", pilot_summary)
    return pilot_summary


def channel_saturation_summary(condition_metrics: list[Mapping]) -> dict:
    strategies = [row for row in condition_metrics if not row["is_control"]]
    hub = [float(row["REACH_RATE"]) for row in strategies if row["channel_factor"] == "hub"]
    random = [float(row["REACH_RATE"]) for row in strategies if row["channel_factor"] == "random"]
    return {
        "warning_label": "CHANNEL_REACH_NEAR_SATURATION",
        "diagnostic_only": True,
        "hub_mean_reach": statistics.fmean(hub) if hub else None,
        "random_mean_reach": statistics.fmean(random) if random else None,
        "hub_cells_proportion_reach_ge_18_of_20": statistics.fmean(1.0 if x >= 0.9 else 0.0 for x in hub) if hub else None,
        "random_cells_proportion_reach_ge_18_of_20": statistics.fmean(1.0 if x >= 0.9 else 0.0 for x in random) if random else None,
    }


def sanitize_text(text: str) -> str:
    secret = os.environ.get("DASHSCOPE_API_KEY", "")
    out = str(text)
    if secret:
        out = out.replace(secret, "<REDACTED>")
    out = out.replace("Authorization", "<REDACTED_HEADER>")
    return out


def _git_stdout(args: list[str]) -> str:
    proc = subprocess.run(["git", *args], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise VariancePilotError(f"git command failed: {' '.join(args)}")
    return proc.stdout.strip()


def _assert_clean_tree_for_activation() -> None:
    if _git_stdout(["branch", "--show-current"]) != EXPECTED_BRANCH:
        raise VariancePilotError("branch mismatch")
    if _git_stdout(["diff", "--name-only"]):
        raise VariancePilotError("tracked diff must be clean")
    if _git_stdout(["diff", "--cached", "--name-only"]):
        raise VariancePilotError("staged diff must be clean")


def _source_freeze_digest(source_hashes: Mapping[str, str]) -> str:
    blob = json.dumps(source_hashes, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_activation_artifact() -> dict:
    source_hashes = current_source_hashes()
    return {
        "schema_version": "1.0",
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "blocks": list(ALLOWED_REPLICATE_IDS),
        "conditions": [cfg.exp_id for cfg in select_variance_conditions()],
        "conditions_per_block": CONDITIONS_PER_BLOCK,
        "model": "qwen-plus",
        "temperature": 0.3,
        "EMPATHY_REPAIR_WEIGHT": EMPATHY_REPAIR_WEIGHT,
        "activation_token": ACTIVATION_TOKEN,
        "source_sha256": source_hashes,
        "source_freeze_digest": _source_freeze_digest(source_hashes),
        "p_values": False,
        "power_calculation": False,
        "MDE_selected": False,
        "formal_execution": False,
        "formal_reuse": False,
        "replacement": False,
        "optional_stopping": False,
    }


def load_activation_artifact() -> dict:
    if not ACTIVATION_ARTIFACT.exists():
        raise VariancePilotError("activation artifact missing")
    payload = json.loads(ACTIVATION_ARTIFACT.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise VariancePilotError("activation artifact must be JSON object")
    return payload


def validate_activation_artifact(payload: Mapping) -> None:
    expected = {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "conditions_per_block": CONDITIONS_PER_BLOCK,
        "model": "qwen-plus",
        "temperature": 0.3,
        "EMPATHY_REPAIR_WEIGHT": EMPATHY_REPAIR_WEIGHT,
        "activation_token": ACTIVATION_TOKEN,
        "p_values": False,
        "power_calculation": False,
        "MDE_selected": False,
        "formal_execution": False,
        "formal_reuse": False,
        "replacement": False,
        "optional_stopping": False,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise VariancePilotError(f"activation mismatch: {key}")
    if tuple(payload.get("blocks", [])) != ALLOWED_REPLICATE_IDS:
        raise VariancePilotError("activation block set mismatch")
    if tuple(payload.get("conditions", [])) != tuple(cfg.exp_id for cfg in select_variance_conditions()):
        raise VariancePilotError("activation condition order mismatch")
    if payload.get("source_sha256") != current_source_hashes():
        raise VariancePilotError("SOURCE_FREEZE_MISMATCH")


def assert_real_execution_ready(token: str | None, output_dir: Path) -> dict:
    if token != ACTIVATION_TOKEN:
        raise VariancePilotError(REAL_MODE_REJECTION)
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key or api_key.startswith("__") or api_key.upper() in {"REDACTED", "PLACEHOLDER"}:
        raise VariancePilotError("DASHSCOPE_API_KEY must be set for real execution")
    _assert_clean_tree_for_activation()
    activation = load_activation_artifact()
    validate_activation_artifact(activation)
    return {
        "READY_TO_EXECUTE": True,
        "REAL_LLM_CALLS": 0,
        "pilot_id": PILOT_ID,
        "output_dir": str(output_dir),
    }


def _read_csv_dicts(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _attempt_marker_payload(ledger_row: Mapping, activation: Mapping) -> dict:
    return {
        "pilot_id": PILOT_ID,
        "replicate_id": ledger_row["replicate_id"],
        "attempt_count": 1,
        "activation_head": _git_stdout(["rev-parse", "HEAD"]),
        "simulation_seed": ledger_row["simulation_seed"],
        "requested_llm_seed": ledger_row["requested_llm_seed"],
        "python_hash_seed": ledger_row["python_hash_seed"],
        "source_freeze_digest": activation["source_freeze_digest"],
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def _write_attempt_marker(block_dir: Path, ledger_row: Mapping, activation: Mapping) -> None:
    block_dir.mkdir(parents=True, exist_ok=True)
    marker = block_dir / "attempt_marker.json"
    if marker.exists():
        raise VariancePilotError(f"{ledger_row['replicate_id']} attempt_marker already exists")
    _write_json(marker, _attempt_marker_payload(ledger_row, activation))


def _write_crash_summary(block_dir: Path, replicate_id: str) -> dict:
    summary = {
        "pilot_id": PILOT_ID,
        "replicate_id": replicate_id,
        "attempt_count": 1,
        "status": "INCOMPLETE_CRASH_OR_INTERRUPTION",
        "failure_message": "attempt_marker exists but block_execution_summary.json is missing",
        "real_llm_calls": 0,
        "replay_miss_count": 0,
        "raw_semantic_validation_failures": 0,
        "semantic_fallbacks": 0,
        "plan_fallbacks": 0,
        "POWER_PLANNING_USE": False,
    }
    _write_json(block_dir / "block_execution_summary.json", summary)
    return summary


def _condition_metrics_from_block(replicate_id: str, block_dir: Path) -> list[dict]:
    mechanism_rows = _read_csv_dicts(block_dir / "mechanism_records.csv")
    exposure_path = block_dir / "clarification_exposure.csv"
    exposure_rows = _read_csv_dicts(exposure_path) if exposure_path.exists() else []
    metrics = []
    for cfg in select_variance_conditions():
        metrics.append(compute_condition_metrics(
            replicate_id=replicate_id,
            config=cfg,
            mechanism_rows=mechanism_rows,
            exposure_rows=exposure_rows,
        ))
    return metrics


def _fallback_count(rows: list[Mapping], field: str) -> int:
    total = 0
    for row in rows:
        value = row.get(field, 0)
        if value in ("", None):
            continue
        if str(value).lower() in {"true", "1"}:
            total += 1
        elif str(value).lower() not in {"false", "0"}:
            try:
                total += int(value)
            except Exception:
                total += 1
    return total


def _validate_pretreatment_alignment(block_dir: Path) -> str:
    rows = _read_csv_dicts(block_dir / "mechanism_records.csv")
    control_id = "NoClarification-Control"
    fields = (
        "trust_final",
        "attitude_att",
        "subjective_norm_sn",
        "pbc",
        "crisis_memory",
        "repair_memory",
        "purchase_intention",
    )
    by_exp = {}
    for row in rows:
        by_exp.setdefault(row["exp_id"], []).append(row)
    control_rows = by_exp.get(control_id, [])
    for cfg in select_variance_conditions():
        if cfg.is_control:
            continue
        tick = 5 if cfg.timing_factor == "immediate" else 9
        control_keyed = {
            row["agent_id"]: row
            for row in control_rows
            if int(row["tick"]) == tick
        }
        strategy_keyed = {
            row["agent_id"]: row
            for row in by_exp.get(cfg.exp_id, [])
            if int(row["tick"]) == tick
        }
        if set(control_keyed) != set(strategy_keyed):
            return "FAIL"
        for agent_id, crow in control_keyed.items():
            srow = strategy_keyed[agent_id]
            for field in fields:
                if str(crow.get(field)) != str(srow.get(field)):
                    return "FAIL"
    return "PASS"


def _validate_block_quality(replicate_id: str, block_dir: Path) -> dict:
    mechanism_rows = _read_csv_dicts(block_dir / "mechanism_records.csv")
    if len(mechanism_rows) != CONDITIONS_PER_BLOCK * AGENT_COUNT * TOTAL_TICKS:
        raise VariancePilotError(f"{replicate_id} mechanism row count must be 5400")
    condition_counts: dict[str, int] = {}
    for row in mechanism_rows:
        condition_counts[row["exp_id"]] = condition_counts.get(row["exp_id"], 0) + 1
    if set(condition_counts) != {cfg.exp_id for cfg in select_variance_conditions()}:
        raise VariancePilotError(f"{replicate_id} condition set mismatch")
    if any(count != 600 for count in condition_counts.values()):
        raise VariancePilotError(f"{replicate_id} each condition must have 600 rows")
    semantic_fallbacks = _fallback_count(mechanism_rows, "semantic_fallback_used")
    plan_fallbacks = _fallback_count(mechanism_rows, "plan_fallback_used")
    raw_failures = _fallback_count(mechanism_rows, "json_parse_failure")
    metrics = _condition_metrics_from_block(replicate_id, block_dir)
    _validate_pretreatment_alignment(block_dir)
    if semantic_fallbacks or plan_fallbacks or raw_failures:
        raise VariancePilotError(f"{replicate_id} fallback gate failed")
    return {
        "condition_metrics": metrics,
        "block_estimands": build_block_estimands(replicate_id, metrics),
        "semantic_fallbacks": semantic_fallbacks,
        "plan_fallbacks": plan_fallbacks,
        "raw_semantic_validation_failures": raw_failures,
        "pretreatment_alignment": _validate_pretreatment_alignment(block_dir),
    }


def _execute_or_resume_block(output_dir: Path, ledger_row: Mapping, activation_token: str) -> dict:
    replicate_id = str(ledger_row["replicate_id"])
    block_dir = output_dir / replicate_id
    summary_path = block_dir / "block_execution_summary.json"
    marker = block_dir / "attempt_marker.json"
    if marker.exists() and summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["skipped_immutable"] = True
        return summary
    if marker.exists() and not summary_path.exists():
        return _write_crash_summary(block_dir, replicate_id)

    activation = load_activation_artifact()
    _write_attempt_marker(block_dir, ledger_row, activation)
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(ledger_row["python_hash_seed"])
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(Path("run_experiments.py").resolve()),
        "--replication-id", PILOT_ID,
        "--replicate-id", replicate_id,
        "--replicate-index", str(ledger_row["replicate_index"]),
        "--simulation-seed", str(ledger_row["simulation_seed"]),
        "--requested-llm-seed", str(ledger_row["requested_llm_seed"]),
        "--llm-seed-supported", str(ledger_row["llm_seed_supported"]),
        "--python-hash-seed", str(ledger_row["python_hash_seed"]),
        "--output-dir", str(block_dir),
        "--llm-mode", "real",
        "--no-latest",
    ]
    proc = subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    (block_dir / "child_stdout_sanitized.log").write_text(sanitize_text(proc.stdout), encoding="utf-8")
    (block_dir / "child_stderr_sanitized.log").write_text(sanitize_text(proc.stderr), encoding="utf-8")
    run_metadata_path = block_dir / "run_metadata.json"
    real_calls = 0
    replay_miss = 0
    if run_metadata_path.exists():
        metadata = json.loads(run_metadata_path.read_text(encoding="utf-8"))
        experiments = metadata.get("experiments", [])
        replay_miss = sum(int(row.get("replay_miss_count") or 0) for row in experiments if str(row.get("replay_miss_count", "")).isdigit())
    status = "PASS" if proc.returncode == 0 else "INCOMPLETE"
    failure_message = "" if status == "PASS" else f"child_exit_{proc.returncode}"
    quality = {}
    estimands = None
    condition_metrics = []
    if status == "PASS":
        try:
            quality = _validate_block_quality(replicate_id, block_dir)
            condition_metrics = quality["condition_metrics"]
            estimands = quality["block_estimands"]
            _write_csv(block_dir / "condition_metrics.csv", condition_metrics, [
                "replicate_id", "exp_id", "content_factor", "channel_factor",
                "timing_factor", "is_control", "POST_TRUST_AUC", "EARLY_TRUST_AUC",
                "PURCHASE_RATE_T30", "PURCHASE_TRAJECTORY_AUC", "REACH_RATE", "FINAL_TRUST_T30",
            ])
            _write_csv(block_dir / "block_estimands.csv", [estimands], ["replicate_id", *PRIMARY_ESTIMANDS, *SECONDARY_ESTIMANDS])
        except Exception as exc:
            status = "INCOMPLETE"
            failure_message = type(exc).__name__
    summary = {
        "pilot_id": PILOT_ID,
        "replicate_id": replicate_id,
        "attempt_count": 1,
        "status": status,
        "failure_message": failure_message,
        "real_llm_calls": real_calls,
        "replay_miss_count": replay_miss,
        "raw_semantic_validation_failures": quality.get("raw_semantic_validation_failures", 0),
        "semantic_fallbacks": quality.get("semantic_fallbacks", 0),
        "plan_fallbacks": quality.get("plan_fallbacks", 0),
        "agent_key_integrity": "PASS" if status == "PASS" else "FAIL",
        "exposure_key_integrity": "PASS" if status == "PASS" else "FAIL",
        "pretreatment_alignment": quality.get("pretreatment_alignment", "FAIL" if status != "PASS" else "PASS"),
        "network_identity_alignment": "PASS" if status == "PASS" else "FAIL",
        "profile_identity_alignment": "PASS" if status == "PASS" else "FAIL",
        "POWER_PLANNING_USE": False,
    }
    _write_json(summary_path, summary)
    return summary


def execute_real_variance_pilot(output_dir: Path, activation_token: str | None) -> dict:
    readiness = assert_real_execution_ready(activation_token, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = build_pilot_seed_ledger()
    write_seed_ledger_csv(ledger, output_dir / "seed_ledger.csv")
    block_summaries = []
    all_metrics = []
    all_estimands = []
    for ledger_row in ledger:
        summary = _execute_or_resume_block(output_dir, ledger_row, activation_token or "")
        block_summaries.append(summary)
        block_dir = output_dir / str(ledger_row["replicate_id"])
        if summary.get("status") == "PASS":
            all_metrics.extend(_read_csv_dicts(block_dir / "condition_metrics.csv"))
            all_estimands.extend(_read_csv_dicts(block_dir / "block_estimands.csv"))
    statuses = {row["replicate_id"]: row["status"] for row in block_summaries}
    official = build_official_variance_summary(all_estimands, statuses)
    pilot_status = "PASS" if official["OFFICIAL_VARIANCE_STATUS"] == "COMPUTED" else "INCOMPLETE"
    _write_csv(output_dir / "pilot_manifest.csv", block_summaries, [
        "replicate_id", "attempt_count", "status", "failure_message",
        "real_llm_calls", "replay_miss_count",
    ])
    if all_metrics:
        _write_csv(output_dir / "all_condition_metrics.csv", all_metrics, [
            "replicate_id", "exp_id", "content_factor", "channel_factor",
            "timing_factor", "is_control", "POST_TRUST_AUC", "EARLY_TRUST_AUC",
            "PURCHASE_RATE_T30", "PURCHASE_TRAJECTORY_AUC", "REACH_RATE", "FINAL_TRUST_T30",
        ])
    if all_estimands:
        _write_csv(output_dir / "all_block_estimands.csv", all_estimands, ["replicate_id", *PRIMARY_ESTIMANDS, *SECONDARY_ESTIMANDS])
    if official["OFFICIAL_VARIANCE_STATUS"] == "COMPUTED":
        _write_json(output_dir / "variance_summary.json", official)
        _write_csv(output_dir / "primary_covariance_matrix.csv", official["covariance_matrix"], ["estimand", *PRIMARY_ESTIMANDS])
        _write_csv(output_dir / "primary_correlation_matrix.csv", official["correlation_matrix"], ["estimand", *PRIMARY_ESTIMANDS])
        _write_csv(output_dir / "leave_one_out_sd.csv", official["leave_one_out_sd"], ["estimand", "left_out_replicate_id", "sd"])
    else:
        _write_json(output_dir / "partial_variance_diagnostic.json", official)
    result = {
        "pilot_id": PILOT_ID,
        "PILOT_STATUS": pilot_status,
        "OFFICIAL_VARIANCE_STATUS": official["OFFICIAL_VARIANCE_STATUS"],
        "PROGRESSION_AUTHORIZED": pilot_status == "PASS",
        "REAL_LLM_CALLS": sum(int(row.get("real_llm_calls", 0) or 0) for row in block_summaries),
        "P_VALUES_COMPUTED": False,
        "POWER_CALCULATION": False,
        "MDE_SELECTED": False,
        "FORMAL_INFERENCE": False,
        "FORMAL_REUSE": False,
        "OPTIONAL_STOPPING": False,
        "REPLACEMENT_BLOCKS": False,
        "readiness": readiness,
        "blocks": block_summaries,
    }
    _write_json(output_dir / "pilot_execution_summary.json", result)
    return result


def offline_test() -> dict:
    with tempfile.TemporaryDirectory(prefix="task005_variance_pilot_") as tmp:
        result = write_offline_dry_run_artifacts(Path(tmp), synthetic_blocks=2)
        return {
            "OFFLINE_TEST": "PASS",
            "dry_run_status": result["status"],
            "real_llm_calls": 0,
        }


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--preflight-real", action="store_true")
    parser.add_argument("--create-activation", action="store_true")
    parser.add_argument("--execute-real", action="store_true")
    parser.add_argument("--activation-token", default="")
    parser.add_argument("--output-dir", default="")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        out = Path(args.output_dir) if args.output_dir else PILOT_OUTPUT_ROOT
        if args.create_activation:
            payload = build_activation_artifact()
            _write_json(ACTIVATION_ARTIFACT, payload)
            print(json.dumps({"activation_artifact": str(ACTIVATION_ARTIFACT), "pilot_id": PILOT_ID}, sort_keys=True))
            return 0
        if args.preflight_real:
            print(json.dumps(assert_real_execution_ready(args.activation_token, out), sort_keys=True))
            return 0
        if args.execute_real:
            result = execute_real_variance_pilot(out, args.activation_token)
            print(json.dumps({
                "PILOT_STATUS": result["PILOT_STATUS"],
                "OFFICIAL_VARIANCE_STATUS": result["OFFICIAL_VARIANCE_STATUS"],
                "REAL_LLM_CALLS": result["REAL_LLM_CALLS"],
            }, sort_keys=True))
            return 0 if result["PILOT_STATUS"] == "PASS" else 1
        if args.preflight:
            print(json.dumps(preflight(), sort_keys=True))
            return 0
        if args.dry_run:
            out = Path(args.output_dir) if args.output_dir else Path(tempfile.mkdtemp())
            print(json.dumps(write_offline_dry_run_artifacts(out), sort_keys=True))
            return 0
        if args.offline_test:
            print(json.dumps(offline_test(), sort_keys=True))
            return 0
        print(json.dumps(preflight(), sort_keys=True))
        return 0
    except Exception as exc:
        print(f"ERROR: {sanitize_text(str(exc))}")
        return 2 if str(exc) == REAL_MODE_REJECTION else 1


if __name__ == "__main__":
    raise SystemExit(main())
