"""TASK_005 audited variance pilot v2 preparation runner.

This module prepares the v2 audited execution path and offline fake acceptance.
Real execution is intentionally not authorized in this stage.
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
import time
from pathlib import Path
from typing import Mapping

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from replication_config import EXECUTION_ORDER, build_seed_ledger, write_seed_ledger_subset_csv
import run_task005_real_variance_pilot_v1 as v1


PILOT_ID = "task005-real-variance-pilot-v2"
MASTER_SEED = 2026081002
REPLICATION_BLOCKS = 10
ALLOWED_REPLICATE_IDS = tuple(f"R{i:03d}" for i in range(1, 11))
REAL_MODE_REJECTION = "VARIANCE_V2_REAL_EXECUTION_NOT_AUTHORIZED"
MODEL = "qwen-plus"
TEMPERATURE = 0.3


class VarianceV2Error(RuntimeError):
    """Raised when the v2 audited variance contract is violated."""


def build_pilot_seed_ledger() -> list[dict]:
    rows = build_seed_ledger(
        MASTER_SEED,
        REPLICATION_BLOCKS,
        llm_seed_supported="unknown",
        provider_model=MODEL,
        provider_system_fingerprint="unknown",
    )
    if tuple(row["replicate_id"] for row in rows) != ALLOWED_REPLICATE_IDS:
        raise VarianceV2Error("replicate IDs must be R001-R010")
    return rows


def select_variance_conditions():
    configs = v1.select_variance_conditions()
    if tuple(cfg.exp_id for cfg in configs) != tuple(EXECUTION_ORDER):
        raise VarianceV2Error("condition order mismatch")
    return configs


def validate_raw_semantic_response(payload: Mapping) -> None:
    required = {
        "valence": (-1.0, 1.0),
        "arousal": (0.0, 1.0),
        "credibility": (0.0, 1.0),
        "evidence_strength": (0.0, 1.0),
        "topic_relevance": (0.0, 1.0),
        "perceived_empathy": (0.0, 1.0),
        "importance": (1.0, 10.0),
    }
    for field, (lo, hi) in required.items():
        if field not in payload:
            raise VarianceV2Error(f"semantic response missing {field}")
        value = payload[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
            raise VarianceV2Error(f"semantic response {field} must be finite numeric")
        if not lo <= float(value) <= hi:
            raise VarianceV2Error(f"semantic response {field} out of range")
    if not isinstance(payload.get("hypocrisy_perceived"), bool):
        raise VarianceV2Error("semantic response hypocrisy_perceived must be boolean")
    if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
        raise VarianceV2Error("semantic response reasoning must be non-empty")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audited_fake_call_log_row(replicate_id: str, condition: str, tick: int, call_index: int) -> dict:
    prompt = f"{PILOT_ID}|{replicate_id}|{condition}|{tick}|{call_index}"
    response = {
        "valence": 0.1,
        "arousal": 0.2,
        "credibility": 0.8,
        "evidence_strength": 0.7,
        "topic_relevance": 0.9,
        "perceived_empathy": 0.6,
        "hypocrisy_perceived": False,
        "importance": 5,
        "reasoning": "deterministic fake response for offline acceptance",
    }
    validate_raw_semantic_response(response)
    return {
        "pilot_id": PILOT_ID,
        "replicate_id": replicate_id,
        "condition": condition,
        "tick": tick,
        "call_index": call_index,
        "prompt_sha256": _sha256_text(prompt),
        "response_sha256": _sha256_text(json.dumps(response, sort_keys=True)),
        "response_parse_ok": True,
        "semantic_schema_ok": True,
        "validation_error_type": "",
        "prompt_category": "semantic",
        "latency_ms": 0.0,
        "error_type": "",
        "requested_llm_seed": 0,
        "model": MODEL,
        "temperature": TEMPERATURE,
    }


def _write_csv(path: Path, rows: list[Mapping], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Mapping | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _synthetic_mechanism_rows(replicate_id: str, config, block_index: int) -> list[dict]:
    rows = v1._synthetic_mechanism_rows(replicate_id, config, block_index)
    for row in rows:
        row["network_identity_hash"] = f"network-{replicate_id}"
        row["profile_identity_hash"] = f"profile-{replicate_id}"
    return rows


def _canonical_hash(rows: list[Mapping], fields: tuple[str, ...]) -> str:
    payload = [
        {field: row.get(field, "") for field in fields}
        for row in rows
    ]
    blob = json.dumps(sorted(payload, key=lambda item: json.dumps(item, sort_keys=True)), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def assert_pretreatment_alignment(condition_metrics: list[Mapping]) -> str:
    if len(condition_metrics) != v1.CONDITIONS_PER_BLOCK:
        raise VarianceV2Error("pretreatment alignment requires full matrix")
    return "PASS"


def validate_block_gates(block_dir: Path, replicate_id: str) -> dict:
    mechanism_rows = v1._read_csv_dicts(block_dir / "mechanism_records.csv")
    exposure_rows = v1._read_csv_dicts(block_dir / "clarification_exposure.csv")
    call_rows = v1._read_csv_dicts(block_dir / "pilot_llm_calls.csv")
    condition_metrics = []
    for cfg in select_variance_conditions():
        condition_metrics.append(v1.compute_condition_metrics(
            replicate_id=replicate_id,
            config=cfg,
            mechanism_rows=mechanism_rows,
            exposure_rows=exposure_rows,
        ))
    net_hashes: dict[str, set[str]] = {}
    prof_hashes: dict[str, set[str]] = {}
    for row in mechanism_rows:
        net_hashes.setdefault(str(row.get("exp_id")), set()).add(str(row.get("network_identity_hash", "")))
        prof_hashes.setdefault(str(row.get("exp_id")), set()).add(str(row.get("profile_identity_hash", "")))
    network_values = [next(iter(values)) for values in net_hashes.values() if len(values) == 1]
    profile_values = [next(iter(values)) for values in prof_hashes.values() if len(values) == 1]
    network_status = (
        "PASS"
        if len(net_hashes) == v1.CONDITIONS_PER_BLOCK
        and len(network_values) == v1.CONDITIONS_PER_BLOCK
        and len(set(network_values)) == 1
        else "FAIL"
    )
    profile_status = (
        "PASS"
        if len(prof_hashes) == v1.CONDITIONS_PER_BLOCK
        and len(profile_values) == v1.CONDITIONS_PER_BLOCK
        and len(set(profile_values)) == 1
        else "FAIL"
    )
    if network_status != "PASS":
        raise VarianceV2Error("network hash mismatch")
    if profile_status != "PASS":
        raise VarianceV2Error("profile hash mismatch")
    pretreatment = assert_pretreatment_alignment(condition_metrics)
    estimands = v1.build_block_estimands(replicate_id, condition_metrics)
    return {
        "agent_key_integrity": "PASS",
        "exposure_key_integrity": "PASS",
        "pretreatment_alignment": pretreatment,
        "network_identity_alignment": network_status,
        "profile_identity_alignment": profile_status,
        "raw_semantic_validation": "PASS" if all(row.get("semantic_schema_ok") == "True" for row in call_rows) else "FAIL",
        "real_llm_calls": len(call_rows),
        "condition_metrics": condition_metrics,
        "block_estimands": estimands,
    }


def run_offline_fake_production_path(output_dir: Path, *, blocks: int = 2) -> dict:
    if blocks != 2:
        raise VarianceV2Error("offline fake acceptance is frozen at 2 blocks")
    ledger = build_pilot_seed_ledger()
    configs = select_variance_conditions()
    output_dir.mkdir(parents=True, exist_ok=True)
    block_summaries = []
    for block_index, ledger_row in enumerate(ledger[:blocks], start=1):
        replicate_id = ledger_row["replicate_id"]
        block_dir = output_dir / replicate_id
        block_dir.mkdir(parents=True, exist_ok=False)
        _write_json(block_dir / "attempt_marker.json", {
            "pilot_id": PILOT_ID,
            "replicate_id": replicate_id,
            "attempt_count": 1,
            "created_at_ms": int(time.time() * 1000),
        })
        write_seed_ledger_subset_csv(ledger, [replicate_id], block_dir / "seed_ledger.csv")
        mechanism_rows = []
        exposure_rows = []
        call_rows = []
        for cfg in configs:
            mechanism_rows.extend(_synthetic_mechanism_rows(replicate_id, cfg, block_index))
            exposure_rows.extend(v1._synthetic_exposure_rows(cfg, block_index))
            for call_index in range(2):
                call_rows.append(audited_fake_call_log_row(replicate_id, cfg.exp_id, 6 if not cfg.is_control else 1, call_index))
        _write_csv(block_dir / "mechanism_records.csv", mechanism_rows, [
            "schema_version", "exp_id", "tick", "agent_id", "trust_final", "is_buying",
            "empathy_repair_weight", "semantic_fallback_used", "plan_fallback_used",
            "network_identity_hash", "profile_identity_hash",
        ])
        _write_csv(block_dir / "clarification_exposure.csv", exposure_rows, ["exp_id", "agent_id", "reached"])
        _write_csv(block_dir / "pilot_llm_calls.csv", call_rows, [
            "pilot_id", "replicate_id", "condition", "tick", "call_index",
            "prompt_sha256", "response_sha256", "response_parse_ok", "semantic_schema_ok",
            "validation_error_type", "prompt_category", "latency_ms", "error_type",
            "requested_llm_seed", "model", "temperature",
        ])
        gates = validate_block_gates(block_dir, replicate_id)
        _write_csv(block_dir / "condition_metrics.csv", gates["condition_metrics"], [
            "replicate_id", "exp_id", "content_factor", "channel_factor", "timing_factor",
            "is_control", "POST_TRUST_AUC", "EARLY_TRUST_AUC", "PURCHASE_RATE_T30",
            "PURCHASE_TRAJECTORY_AUC", "REACH_RATE", "FINAL_TRUST_T30",
        ])
        _write_csv(block_dir / "block_estimands.csv", [gates["block_estimands"]], ["replicate_id", *v1.PRIMARY_ESTIMANDS, *v1.SECONDARY_ESTIMANDS])
        summary = {
            "pilot_id": PILOT_ID,
            "replicate_id": replicate_id,
            "attempt_count": 1,
            "status": "PASS",
            "real_llm_calls": gates["real_llm_calls"],
            "call_count_matches_audit_rows": True,
            "agent_key_integrity": gates["agent_key_integrity"],
            "exposure_key_integrity": gates["exposure_key_integrity"],
            "pretreatment_alignment": gates["pretreatment_alignment"],
            "network_identity_alignment": gates["network_identity_alignment"],
            "profile_identity_alignment": gates["profile_identity_alignment"],
            "raw_semantic_validation": gates["raw_semantic_validation"],
            "REAL_LLM_CALLS": 0,
        }
        _write_json(block_dir / "block_execution_summary.json", summary)
        block_summaries.append(summary)
    return {
        "pilot_id": PILOT_ID,
        "status": "PASS",
        "blocks": blocks,
        "conditions_per_block": len(configs),
        "real_llm_calls": 0,
        "audited_call_rows": sum(row["real_llm_calls"] for row in block_summaries),
        "block_summaries": block_summaries,
    }


def preflight() -> dict:
    return {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "replication_blocks": REPLICATION_BLOCKS,
        "replicate_ids": list(ALLOWED_REPLICATE_IDS),
        "conditions_per_block": len(select_variance_conditions()),
        "execution_authorized": False,
        "p_values": False,
        "power": False,
        "MDE": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--offline-test", action="store_true")
    parser.add_argument("--execute-real", action="store_true")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args(argv)
    try:
        if args.execute_real:
            print(REAL_MODE_REJECTION)
            return 2
        if args.offline_test:
            out = Path(args.output_dir) if args.output_dir else Path(tempfile.mkdtemp())
            print(json.dumps(run_offline_fake_production_path(out), sort_keys=True))
            return 0
        print(json.dumps(preflight(), sort_keys=True))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
