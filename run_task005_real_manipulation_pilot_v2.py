"""TASK_005 real manipulation pilot v2 preparation runner.

Pilot v2 is a new namespace for the perceived-empathy construct amendment. This
module provides offline contract checks, v2 manipulation calculations, and
fail-closed child lifecycle artifacts. It does not authorize real LLM execution
in this stage.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Mapping

from experiment_config import generate_experiment_matrix
from replication_config import build_seed_ledger, write_seed_ledger_csv
from run_experiments import (
    TASK005_LLM_API_KEY_ENV,
    _build_real_router,
    _close_router_resource,
)
from run_task005_real_manipulation_pilot_v1 import (
    PILOT_CONDITION_IDS,
    PROVIDER,
    MODEL,
    TEMPERATURE,
    PilotContractError,
    _write_csv,
    sanitized_model_config,
)


PILOT_ID = "task005-real-manipulation-pilot-v2"
MASTER_SEED = 2026080903
PILOT_REPLICATION_BLOCKS = 2
ALLOWED_REPLICATE_IDS = ("R001", "R002")
ENGINEERING_SEPARATION_FLOOR = 0.05
TOPIC_RELEVANCE_WARNING_THRESHOLD = 0.10
REAL_MODE_REJECTION = "PILOT_V2_REAL_EXECUTION_NOT_AUTHORIZED"
PILOT_OUTPUT_ROOT = Path("results") / "pilots" / PILOT_ID

PRIMARY_FIELDS = (
    "D_evidence",
    "D_credibility",
    "D_empathy",
    "D_arousal",
)
REQUIRED_SEMANTIC_SOURCE_FIELDS = (
    "semantic_evidence_strength",
    "semantic_credibility",
    "semantic_perceived_empathy",
    "semantic_arousal",
    "semantic_valence",
    "semantic_topic_relevance",
    "semantic_hypocrisy_perceived",
)


def build_pilot_seed_ledger() -> list[dict]:
    rows = build_seed_ledger(
        MASTER_SEED,
        PILOT_REPLICATION_BLOCKS,
        llm_seed_supported="unknown",
        provider_model=MODEL,
        provider_system_fingerprint="unknown",
    )
    if tuple(row["replicate_id"] for row in rows) != ALLOWED_REPLICATE_IDS:
        raise PilotContractError("pilot-v2 replicate IDs are not exactly R001-R002")
    return rows


def select_pilot_conditions():
    by_id = {cfg.exp_id: cfg for cfg in generate_experiment_matrix()}
    return [by_id[exp_id] for exp_id in PILOT_CONDITION_IDS]


def build_pilot_manifest_rows(ledger_rows: list[dict]) -> list[dict]:
    rows = []
    for ledger in ledger_rows:
        for order, cfg in enumerate(select_pilot_conditions(), start=1):
            rows.append(
                {
                    "pilot_id": PILOT_ID,
                    "replicate_id": ledger["replicate_id"],
                    "replicate_index": ledger["replicate_index"],
                    "condition_order": order,
                    "exp_id": cfg.exp_id,
                    "content_factor": cfg.content_factor,
                    "channel_factor": cfg.channel_factor,
                    "timing_factor": cfg.timing_factor,
                    "clarification_tick": cfg.clarification_tick,
                    "router_role": "recording" if cfg.is_control else "replay",
                    "simulation_seed": ledger["simulation_seed"],
                    "requested_llm_seed": ledger["requested_llm_seed"],
                    "python_hash_seed": ledger["python_hash_seed"],
                    "PILOT_ONLY": True,
                    "FORMAL_INFERENCE": False,
                    "P_VALUES_COMPUTED": False,
                }
            )
    return rows


def _truthy(value) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _float(value) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise PilotContractError("non-finite semantic value")
    return number


def _detected_rows(rows: list[Mapping], label: str) -> list[Mapping]:
    seen = set()
    detected = []
    for row in rows:
        agent_id = str(row.get("agent_id", ""))
        if not agent_id or agent_id in seen:
            raise PilotContractError(f"{label} agent identity invalid")
        seen.add(agent_id)
        if _truthy(row.get("clarification_detected_by_plan")):
            for field in REQUIRED_SEMANTIC_SOURCE_FIELDS:
                if field not in row:
                    raise PilotContractError(f"{label} missing {field}")
                if field != "semantic_hypocrisy_perceived":
                    value = _float(row[field])
                    if field == "semantic_valence":
                        if value < -1.0 or value > 1.0:
                            raise PilotContractError(f"{field} out of range")
                    elif value < 0.0 or value > 1.0:
                        raise PilotContractError(f"{field} out of range")
            detected.append(row)
    return detected


def compute_manipulation_pairs(
    replicate_id: str,
    rational_rows: list[Mapping],
    empathy_rows: list[Mapping],
) -> list[dict]:
    if replicate_id not in ALLOWED_REPLICATE_IDS:
        raise PilotContractError("replicate_id must be R001 or R002")
    rational = _detected_rows(rational_rows, "rational")
    empathy = _detected_rows(empathy_rows, "empathy")
    r_ids = {str(row["agent_id"]) for row in rational}
    e_ids = {str(row["agent_id"]) for row in empathy}
    if r_ids != e_ids:
        raise PilotContractError("matched Rational/Empathy reach sets differ")
    r_by_id = {str(row["agent_id"]): row for row in rational}
    e_by_id = {str(row["agent_id"]): row for row in empathy}
    pairs = []
    for agent_id in sorted(r_ids):
        r = r_by_id[agent_id]
        e = e_by_id[agent_id]
        pairs.append(
            {
                "replicate_id": replicate_id,
                "agent_id": agent_id,
                "D_evidence": _float(r["semantic_evidence_strength"]) - _float(e["semantic_evidence_strength"]),
                "D_credibility": _float(r["semantic_credibility"]) - _float(e["semantic_credibility"]),
                "D_empathy": _float(e["semantic_perceived_empathy"]) - _float(r["semantic_perceived_empathy"]),
                "D_arousal": _float(e["semantic_arousal"]) - _float(r["semantic_arousal"]),
                "D_valence_descriptive": _float(e["semantic_valence"]) - _float(r["semantic_valence"]),
                "rational_topic_relevance": _float(r["semantic_topic_relevance"]),
                "empathy_topic_relevance": _float(e["semantic_topic_relevance"]),
                "rational_hypocrisy_perceived": bool(r["semantic_hypocrisy_perceived"]),
                "empathy_hypocrisy_perceived": bool(e["semantic_hypocrisy_perceived"]),
            }
        )
    return pairs


def summarize_manipulation_by_block(pairs: list[Mapping]) -> dict:
    if not pairs:
        raise PilotContractError("no matched manipulation pairs")
    by_rep = {replicate_id: [] for replicate_id in ALLOWED_REPLICATE_IDS}
    for row in pairs:
        by_rep.setdefault(str(row["replicate_id"]), []).append(row)
    if set(by_rep) != set(ALLOWED_REPLICATE_IDS) or any(not by_rep[rid] for rid in ALLOWED_REPLICATE_IDS):
        raise PilotContractError("manipulation pairs must contain exactly R001 and R002")
    per_replicate = {}
    all_blocks_direction_pass = True
    for replicate_id in ALLOWED_REPLICATE_IDS:
        dimensions = {}
        for field in PRIMARY_FIELDS:
            values = [_float(row[field]) for row in by_rep[replicate_id]]
            mean_value = sum(values) / len(values)
            dimensions[field] = {"mean": mean_value, "passes_direction": mean_value > 0}
            if mean_value <= 0:
                all_blocks_direction_pass = False
        per_replicate[replicate_id] = {"dimensions": dimensions}
    pooled_dimensions = {}
    weak = []
    for field in PRIMARY_FIELDS:
        values = [_float(row[field]) for row in pairs]
        mean_value = sum(values) / len(values)
        pooled_dimensions[field] = {
            "mean": mean_value,
            "min": min(values),
            "max": max(values),
            "expected_direction_proportion": sum(value > 0 for value in values) / len(values),
            "passes_engineering_floor": mean_value >= ENGINEERING_SEPARATION_FLOOR,
        }
        if mean_value < ENGINEERING_SEPARATION_FLOOR:
            weak.append(field)
    topic_diff = abs(
        sum(_float(row["rational_topic_relevance"]) for row in pairs) / len(pairs)
        - sum(_float(row["empathy_topic_relevance"]) for row in pairs) / len(pairs)
    )
    return {
        "pilot_id": PILOT_ID,
        "FORMAL_INFERENCE": False,
        "P_VALUES_COMPUTED": False,
        "PILOT_ONLY": True,
        "semantic_valence_role": "descriptive_only",
        "per_replicate": per_replicate,
        "dimensions": pooled_dimensions,
        "all_blocks_direction_pass": all_blocks_direction_pass,
        "DIRECTION_GATE": "PASS" if all_blocks_direction_pass else "FAIL",
        "MANIPULATION_STRENGTH": "WEAK" if weak else "PASS",
        "weak_dimensions": weak,
        "topic_relevance_group_mean_abs_diff": topic_diff,
        "topic_relevance_warning": "TOPIC_RELEVANCE_IMBALANCE" if topic_diff > TOPIC_RELEVANCE_WARNING_THRESHOLD else "",
        "rational_hypocrisy_perceived_rate": sum(bool(row["rational_hypocrisy_perceived"]) for row in pairs) / len(pairs),
        "empathy_hypocrisy_perceived_rate": sum(bool(row["empathy_hypocrisy_perceived"]) for row in pairs) / len(pairs),
    }


def _append_lifecycle(path: Path, replicate_id: str, stage: str, status: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "replicate_id": replicate_id,
        "stage": stage,
        "status": status,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _secret_patterns() -> list[str]:
    values = [os.environ.get(TASK005_LLM_API_KEY_ENV, "")]
    return [value for value in values if value]


def sanitize_text(text: str) -> str:
    safe = str(text)
    for secret in _secret_patterns():
        safe = safe.replace(secret, "<REDACTED>")
    safe = re.sub(r"Authorization\s*:\s*Bearer\s+\S+", "Authorization: Bearer <REDACTED>", safe, flags=re.I)
    return safe


def _write_block_summary(path: Path, summary: Mapping) -> None:
    path.write_text(json.dumps(dict(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def _execute_replicate_block(
    output_dir: Path,
    ledger_row: Mapping,
    *,
    router_builder=_build_real_router,
) -> dict:
    replicate_id = str(ledger_row["replicate_id"])
    if replicate_id not in ALLOWED_REPLICATE_IDS:
        raise PilotContractError("replicate_id must be R001 or R002")
    block_dir = output_dir / replicate_id
    block_dir.mkdir(parents=True, exist_ok=False)
    lifecycle = block_dir / "replicate_lifecycle.jsonl"
    call_log = block_dir / "pilot_llm_calls.jsonl"
    summary_path = block_dir / "block_execution_summary.json"
    stdout_path = block_dir / "child_stdout_sanitized.log"
    stderr_path = block_dir / "child_stderr_sanitized.log"
    real_router = None
    real_calls = 0
    _append_lifecycle(lifecycle, replicate_id, "BLOCK_DIR_CREATED", "ok")
    try:
        call_log.write_text("", encoding="utf-8")
        _append_lifecycle(lifecycle, replicate_id, "CALL_LOG_CREATED", "ok")
        write_seed_ledger_csv([dict(ledger_row)], block_dir / "seed_ledger.csv")
        _append_lifecycle(lifecycle, replicate_id, "SEED_LEDGER_WRITTEN", "ok")
        (block_dir / "sanitized_model_config.json").write_text(
            json.dumps(sanitized_model_config(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _append_lifecycle(lifecycle, replicate_id, "MODEL_CONFIG_WRITTEN", "ok")
        (block_dir / "pilot_condition_manifest.json").write_text(
            json.dumps(build_pilot_manifest_rows([dict(ledger_row)]), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _append_lifecycle(lifecycle, replicate_id, "CONDITION_MANIFEST_WRITTEN", "ok")
        if os.environ.get("PYTHONHASHSEED") != str(ledger_row["python_hash_seed"]):
            raise PilotContractError("PYTHONHASHSEED does not match ledger")
        _append_lifecycle(lifecycle, replicate_id, "PYTHONHASHSEED_CHECKED", "ok")
        _append_lifecycle(lifecycle, replicate_id, "REAL_ROUTER_BUILD_STARTED", "ok")
        real_router = router_builder(int(ledger_row["requested_llm_seed"]))
        _append_lifecycle(lifecycle, replicate_id, "REAL_ROUTER_BUILD_COMPLETED", "ok")
        raise PilotContractError(REAL_MODE_REJECTION)
    except Exception as exc:
        _append_lifecycle(lifecycle, replicate_id, "BLOCK_EXECUTION_SUMMARY_WRITTEN", "incomplete")
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(sanitize_text(type(exc).__name__) + "\n", encoding="utf-8")
        summary = {
            "pilot_id": PILOT_ID,
            "replicate_id": replicate_id,
            "attempt_count": 1,
            "status": "INCOMPLETE",
            "failure_message": sanitize_text(type(exc).__name__),
            "real_llm_calls": real_calls,
            "replay_miss_count": 0,
            "matched_agents": 0,
            "FORMAL_INFERENCE": False,
            "P_VALUES_COMPUTED": False,
            "PILOT_ONLY": True,
        }
        _write_block_summary(summary_path, summary)
        return summary
    finally:
        if real_router is not None:
            await _close_router_resource(real_router)


def write_offline_dry_run_artifacts(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = build_pilot_seed_ledger()
    write_seed_ledger_csv(ledger, output_dir / "seed_ledger.csv")
    _write_csv(output_dir / "pilot_manifest.csv", build_pilot_manifest_rows(ledger))
    summary = {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "replicate_ids": list(ALLOWED_REPLICATE_IDS),
        "condition_ids": list(PILOT_CONDITION_IDS),
        "primary_dimensions": list(PRIMARY_FIELDS),
        "semantic_valence_role": "descriptive_only",
        "REAL_LLM_CALLS": 0,
        "FORMAL_INFERENCE": False,
        "P_VALUES_COMPUTED": False,
    }
    (output_dir / "pilot_v2_preparation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def run_offline_self_test() -> dict:
    rational = [
        _row("A001", 0.90, 0.88, 0.20, 0.20, -0.30, 0.90, False),
        _row("A002", 0.82, 0.80, 0.25, 0.30, 0.10, 0.88, False),
    ]
    empathy = [
        _row("A001", 0.45, 0.55, 0.82, 0.72, -0.60, 0.87, True),
        _row("A002", 0.50, 0.58, 0.86, 0.70, 0.20, 0.84, True),
    ]
    pairs = []
    for replicate_id in ALLOWED_REPLICATE_IDS:
        pairs.extend(compute_manipulation_pairs(replicate_id, rational, empathy))
    summary = summarize_manipulation_by_block(pairs)
    if summary["DIRECTION_GATE"] != "PASS":
        raise PilotContractError("offline v2 direction gate should pass")
    if summary["MANIPULATION_STRENGTH"] != "PASS":
        raise PilotContractError("offline v2 floor should pass")
    return summary


def _row(agent_id, evidence, credibility, empathy, arousal, valence, topic, hypocrisy):
    return {
        "agent_id": agent_id,
        "clarification_detected_by_plan": True,
        "semantic_evidence_strength": evidence,
        "semantic_credibility": credibility,
        "semantic_perceived_empathy": empathy,
        "semantic_arousal": arousal,
        "semantic_valence": valence,
        "semantic_topic_relevance": topic,
        "semantic_hypocrisy_perceived": hypocrisy,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline-test", action="store_true")
    parser.add_argument("--execute-real", action="store_true")
    parser.add_argument("--output-dir", default="")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.execute_real:
            raise PilotContractError(REAL_MODE_REJECTION)
        if args.dry_run:
            output_dir = Path(args.output_dir) if args.output_dir else Path(tempfile.mkdtemp())
            print(json.dumps(write_offline_dry_run_artifacts(output_dir), sort_keys=True))
            return 0
        if args.offline_test:
            print(json.dumps(run_offline_self_test(), sort_keys=True))
            return 0
        raise PilotContractError(REAL_MODE_REJECTION)
    except PilotContractError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
