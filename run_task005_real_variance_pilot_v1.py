"""TASK_005 real-LLM variance pilot v1 preparation runner.

This module freezes the variance-pilot estimator and engineering preparation
surface. Current stage execution is offline only: real variance-pilot execution
is intentionally unauthorized.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import tempfile
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
PILOT_OUTPUT_ROOT = Path("results") / "pilots" / PILOT_ID

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
    else:
        erows = [row for row in exposure_rows if row.get("exp_id") == exp_id]
        reached = {str(row.get("agent_id")) for row in erows if _bool_value(row.get("reached"))}
        if len(erows) != AGENT_COUNT:
            raise VariancePilotError(f"{exp_id} exposure row count must be 20")
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
            "PURCHASE_RATE_T30", "REACH_RATE", "FINAL_TRUST_T30",
        ])
        _write_csv(block_dir / "block_estimands.csv", [block_estimands], ["replicate_id", *PRIMARY_ESTIMANDS])
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
        "PURCHASE_RATE_T30", "REACH_RATE", "FINAL_TRUST_T30",
    ])
    _write_csv(output_dir / "all_block_estimands.csv", all_block_estimands, ["replicate_id", *PRIMARY_ESTIMANDS])
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
    parser.add_argument("--execute-real", action="store_true")
    parser.add_argument("--output-dir", default="")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.execute_real:
            print(REAL_MODE_REJECTION)
            return 2
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
        print(f"ERROR: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
