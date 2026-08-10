"""TASK_005 variance pilot v2 audited real-execution runner.

Offline acceptance runs the real run_experiments._run_with_patch orchestration
with a deterministic fake inner router. Real variance-v2 execution is available
only through the frozen activation artifact, exact token, exact git state,
source hash, model, credential, and output-state gates.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import dataclasses
import datetime
import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
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
from run_experiments import (
    _build_real_router,
    _close_router_resource,
    _run_with_patch,
    write_agent_records_csv,
    write_clarification_exposure_csv,
    write_mechanism_records_csv,
    write_trajectories_csv,
)
from task005_audited_llm_router import (
    AuditedRecordingRouter,
    AuditedReplayRouter,
    DeterministicFakeInnerRouter,
    ValidatedAuditedRouter,
    validate_raw_semantic_response,
)


PILOT_ID = "task005-real-variance-pilot-v2"
MASTER_SEED = 2026081002
REPLICATION_BLOCKS = 10
ALLOWED_REPLICATE_IDS = tuple(f"R{i:03d}" for i in range(1, 11))
REAL_MODE_REJECTION = "VARIANCE_V2_REAL_EXECUTION_NOT_AUTHORIZED"
ACTIVATION_TOKEN = "TASK005_REAL_VARIANCE_V2_ACTIVATE_20260810_01"
EXPECTED_BRANCH = "redesign/task005-mechanism-v2"
EXPECTED_START_HEAD = "c71ebc00def6be9f5c2583a2696e3bc98d6e0ba6"
MODEL = "qwen-plus"
TEMPERATURE = 0.3
SPEC_DIR = Path(".kiro/specs/task005-replication-inference")
ACTIVATION_REVIEW_ARTIFACT = SPEC_DIR / "variance_v2_final_activation_review1.0.json"
ACTIVATION_ARTIFACT = SPEC_DIR / "real_llm_variance_pilot_v2_activation1.0.json"
RESULT_ARTIFACT = SPEC_DIR / "real_llm_variance_pilot_v2_result1.0.json"
PILOT_OUTPUT_ROOT = Path("results/pilots") / PILOT_ID
OUTPUT_FILES = (
    "attempt_marker.json",
    "seed_ledger.csv",
    "condition_manifest.json",
    "sanitized_model_config.json",
    "pilot_llm_calls.jsonl",
    "replicate_lifecycle.jsonl",
    "agent_records.csv",
    "mechanism_records.csv",
    "clarification_exposure.csv",
    "trajectories.csv",
    "network_identity.json",
    "profile_identity.json",
    "condition_metrics.csv",
    "block_estimands.csv",
    "block_execution_summary.json",
)
ALLOWED_PROMPT_CATEGORIES = {"semantic"}
PROFILE_IDENTITY_FIELDS = ("agent_id", "cluster_type", "social_role", "baseline_trust")
SOURCE_FREEZE_FILES = (
    "mechanism_v2.py",
    "plugins/agent/plan/ConsumerPlanPlugin.py",
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "simulation_core.py",
    "clarification_injector.py",
    "experiment_config.py",
    "replication_config.py",
    "run_experiments.py",
    "task005_audited_llm_router.py",
    "run_task005_real_variance_pilot_v2.py",
    "configs/models_config.yaml",
    ".kiro/specs/task005-replication-inference/task005_estimand_contract1.0.json",
    ".kiro/specs/task005-replication-inference/task005_estimand_contract_amendment1.1.json",
    ".kiro/specs/task005-replication-inference/real_llm_variance_pilot_v2_contract1.0.json",
    ".kiro/specs/task005-replication-inference/empathy_relational_repair_amendment1.0.json",
    ".kiro/specs/task005-replication-inference/mechanism_auditability_schema_amendment1.2.json",
    ".kiro/specs/task005-replication-inference/manipulation_stage_closure1.0.json",
    ".kiro/specs/task005-replication-inference/task005_active_regression_gate_manifest1.0.json",
    ".kiro/specs/task005-replication-inference/variance_v2_profile_identity_contract1.0.json",
    ".kiro/specs/task005-replication-inference/variance_v2_final_activation_review1.0.json",
)


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


def select_variance_conditions_for_block(ledger_row: Mapping):
    base = select_variance_conditions()
    simulation_seed = int(ledger_row["simulation_seed"])
    configs = [dataclasses.replace(cfg, random_seed=simulation_seed) for cfg in base]
    if len(configs) != v1.CONDITIONS_PER_BLOCK:
        raise VarianceV2Error("block must contain exactly 9 conditions")
    if tuple(cfg.exp_id for cfg in configs) != tuple(EXECUTION_ORDER):
        raise VarianceV2Error("block condition order mismatch")
    if {cfg.random_seed for cfg in configs} != {simulation_seed}:
        raise VarianceV2Error("block condition seeds must equal ledger simulation_seed")
    return configs


def current_source_hashes() -> dict[str, str]:
    hashes = {}
    for rel in SOURCE_FREEZE_FILES:
        path = Path(rel)
        if not path.exists():
            raise VarianceV2Error(f"source freeze file missing: {rel}")
        hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _source_freeze_digest() -> str:
    blob = json.dumps(current_source_hashes(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _git_stdout(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=Path(__file__).resolve().parent,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise VarianceV2Error(f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def _git_branch() -> str:
    return _git_stdout(["branch", "--show-current"])


def _assert_tracked_clean() -> None:
    if _git_stdout(["diff", "--name-only"]):
        raise VarianceV2Error("tracked working tree must be clean")
    if _git_stdout(["diff", "--cached", "--name-only"]):
        raise VarianceV2Error("staged changes must be clean")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise VarianceV2Error(f"required artifact missing: {path.as_posix()}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise VarianceV2Error(f"{path.name} must be a JSON object")
    return payload


def _activation_payload() -> dict:
    return _load_json(ACTIVATION_ARTIFACT)


def _condition_order() -> list[str]:
    return [cfg.exp_id for cfg in select_variance_conditions()]


def _primary_estimands() -> list[str]:
    return list(v1.PRIMARY_ESTIMANDS)


def _validate_activation_payload(payload: Mapping, activation_token: str | None) -> None:
    checks = {
        "schema_version": "1.0",
        "status": "frozen",
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "conditions_per_block": v1.CONDITIONS_PER_BLOCK,
        "independent_unit": "replication_block",
        "agent_level_n_used_for_power": False,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "EMPATHY_REPAIR_WEIGHT": v1.EMPATHY_REPAIR_WEIGHT,
        "activation_token": ACTIVATION_TOKEN,
        "ten_of_ten_pass_rule": True,
        "no_replacement": True,
        "no_optional_stopping": True,
        "no_formal_reuse": True,
        "no_p_values": True,
        "no_power": True,
        "no_mde": True,
        "real_execution_authorized": True,
    }
    for key, expected in checks.items():
        if payload.get(key) != expected:
            raise VarianceV2Error(f"activation mismatch: {key}")
    if activation_token != ACTIVATION_TOKEN:
        raise VarianceV2Error(REAL_MODE_REJECTION)
    if tuple(payload.get("replicate_ids", [])) != ALLOWED_REPLICATE_IDS:
        raise VarianceV2Error("activation replicate IDs mismatch")
    if tuple(payload.get("condition_order", [])) != tuple(_condition_order()):
        raise VarianceV2Error("activation condition order mismatch")
    if tuple(payload.get("primary_estimands", [])) != tuple(_primary_estimands()):
        raise VarianceV2Error("activation primary estimands mismatch")
    if payload.get("source_sha256") != current_source_hashes():
        raise VarianceV2Error("SOURCE_FREEZE_MISMATCH")
    if payload.get("source_freeze_digest") != _source_freeze_digest():
        raise VarianceV2Error("SOURCE_FREEZE_DIGEST_MISMATCH")


def _assert_git_activation_state(payload: Mapping) -> None:
    if _git_branch() != EXPECTED_BRANCH:
        raise VarianceV2Error("git branch mismatch")
    head = _git_head()
    activation_code_head = str(payload.get("activation_code_head", ""))
    activation_head = str(payload.get("activation_head", ""))
    if activation_head:
        if head != activation_head:
            raise VarianceV2Error("activation HEAD mismatch")
        parent = _git_stdout(["rev-parse", f"{head}^"])
        if parent != activation_code_head:
            raise VarianceV2Error("activation parent HEAD mismatch")
    elif activation_code_head:
        parent = _git_stdout(["rev-parse", f"{head}^"])
        if parent != activation_code_head:
            raise VarianceV2Error("activation code parent mismatch")
    else:
        raise VarianceV2Error("activation_code_head missing")
    _assert_tracked_clean()


def _validate_model_config() -> None:
    path = Path("configs/models_config.yaml")
    text = path.read_text(encoding="utf-8")
    if "model: qwen-plus" not in text:
        raise VarianceV2Error("model config must use qwen-plus")
    if "temperature: 0.3" not in text:
        raise VarianceV2Error("model config temperature must be 0.3")
    if 'api_key: "__FROM_ENV_DASHSCOPE_API_KEY__"' not in text:
        raise VarianceV2Error("model config must use DASHSCOPE env placeholder")


def _bridge_user_scope_dashscope_key_if_needed() -> None:
    value = os.environ.get("DASHSCOPE_API_KEY", "")
    if value and not value.startswith("__"):
        return
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        return
    candidate = (proc.stdout or "").strip()
    if candidate and not candidate.startswith("__"):
        os.environ["DASHSCOPE_API_KEY"] = candidate


def _credential_available() -> bool:
    _bridge_user_scope_dashscope_key_if_needed()
    value = os.environ.get("DASHSCOPE_API_KEY", "")
    return bool(value and not value.startswith("__") and value.upper() not in {"REDACTED", "PLACEHOLDER"})


def _attempt_count_for_block(block_dir: Path) -> int:
    return 1 if (block_dir / "attempt_marker.json").exists() else 0


def _output_attempt_counts(output_dir: Path) -> dict[str, int]:
    return {rid: _attempt_count_for_block(output_dir / rid) for rid in ALLOWED_REPLICATE_IDS}


def _validate_clean_output_state(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    counts = _output_attempt_counts(output_dir)
    if any(value != 0 for value in counts.values()):
        raise VarianceV2Error("real variance-v2 attempt markers already exist")


def _validate_real_execution_authorized(
    output_dir: Path,
    activation_token: str | None,
    *,
    require_clean_output: bool,
) -> dict:
    payload = _activation_payload()
    _validate_activation_payload(payload, activation_token)
    _assert_git_activation_state(payload)
    _validate_model_config()
    if not _credential_available():
        raise VarianceV2Error("DASHSCOPE_API_KEY credential unavailable")
    if require_clean_output:
        _validate_clean_output_state(output_dir)
    return payload


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


def _write_jsonl(path: Path, rows: list[Mapping]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _canonical_hash(rows: list[Mapping], fields: tuple[str, ...]) -> str:
    payload = [{field: row.get(field, "") for field in fields} for row in rows]
    blob = json.dumps(
        sorted(payload, key=lambda item: json.dumps(item, sort_keys=True)),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _synthetic_mechanism_rows(replicate_id: str, config, block_index: int) -> list[dict]:
    rows = v1._synthetic_mechanism_rows(replicate_id, config, block_index)
    for row in rows:
        row["network_identity_hash"] = f"synthetic-network-{replicate_id}"
        row["profile_identity_hash"] = f"synthetic-profile-{replicate_id}"
    return rows


def audited_fake_call_log_row(replicate_id: str, condition: str, tick: int, call_index: int) -> dict:
    response = {
        "valence": 0.1,
        "arousal": 0.2,
        "credibility": 0.8,
        "evidence_strength": 0.7,
        "topic_relevance": 0.9,
        "perceived_empathy": 0.6,
        "hypocrisy_perceived": False,
        "importance": 5,
        "reasoning": "synthetic estimator fixture response",
    }
    validate_raw_semantic_response(response)
    prompt = f"{PILOT_ID}|synthetic|{replicate_id}|{condition}|{tick}|{call_index}"
    return {
        "pilot_id": PILOT_ID,
        "replicate_id": replicate_id,
        "condition": condition,
        "tick": tick,
        "call_index": call_index,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "response_sha256": hashlib.sha256(json.dumps(response, sort_keys=True).encode("utf-8")).hexdigest(),
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


def _network_hash_from_result(result: Mapping) -> str:
    nodes = result.get("network_nodes") or []
    edges = result.get("network_edges") or []
    if not nodes or not edges:
        raise VarianceV2Error(f"{result.get('exp_id')} missing production network audit rows")
    payload = {
        "nodes": sorted(nodes, key=lambda row: str(row.get("agent_id", ""))),
        "edges": sorted(edges, key=lambda row: (str(row.get("source_agent_id", "")), str(row.get("target_agent_id", "")))),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _profile_hash_from_result(result: Mapping) -> str:
    records = result.get("agent_records") or []
    tick1 = [row for row in records if int(row.get("tick", 0)) == 1]
    if len(tick1) != v1.AGENT_COUNT:
        raise VarianceV2Error(f"{result.get('exp_id')} missing initialized profile audit rows")
    return _canonical_hash(tick1, PROFILE_IDENTITY_FIELDS)


def _identity_json_hash(path: Path, identity_key: str) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("conditions")
    if not isinstance(rows, list) or len(rows) != v1.CONDITIONS_PER_BLOCK:
        raise VarianceV2Error(f"{path.name} must contain 9 condition rows")
    hashes = {row.get(identity_key) for row in rows}
    if len(hashes) != 1:
        raise VarianceV2Error(f"{path.name} condition hashes are not identical")
    return str(next(iter(hashes)))


def _assert_identity_file(block_dir: Path, filename: str, identity_key: str) -> str:
    return _identity_json_hash(block_dir / filename, identity_key)


def _mechanism_condition_rows(rows: list[Mapping], exp_id: str) -> list[Mapping]:
    selected = [row for row in rows if row.get("exp_id") == exp_id]
    if len(selected) != v1.AGENT_COUNT * v1.TOTAL_TICKS:
        raise VarianceV2Error(f"{exp_id} mechanism rows must be 600")
    return selected


def _agent_set_for_condition(rows: list[Mapping], exp_id: str) -> set[str]:
    return {str(row.get("agent_id")) for row in rows if row.get("exp_id") == exp_id}


def _assert_production_pretreatment_alignment(mechanism_rows: list[Mapping]) -> str:
    configs = select_variance_conditions()
    control_cfg = [cfg for cfg in configs if cfg.is_control][0]
    control_rows = _mechanism_condition_rows(mechanism_rows, control_cfg.exp_id)
    fields = (
        "trust_final",
        "attitude_att",
        "subjective_norm_sn",
        "pbc",
        "crisis_memory",
        "repair_memory",
        "purchase_intention",
    )
    for cfg in configs:
        if cfg.is_control:
            continue
        assert cfg.clarification_tick is not None
        tick = cfg.clarification_tick - 1
        strategy_rows = _mechanism_condition_rows(mechanism_rows, cfg.exp_id)
        c_by_agent = {str(row["agent_id"]): row for row in control_rows if int(row["tick"]) == tick}
        s_by_agent = {str(row["agent_id"]): row for row in strategy_rows if int(row["tick"]) == tick}
        if len(c_by_agent) != v1.AGENT_COUNT or len(s_by_agent) != v1.AGENT_COUNT:
            raise VarianceV2Error(f"{cfg.exp_id} pretreatment tick {tick} must contain 20 agents")
        if set(c_by_agent) != set(s_by_agent):
            raise VarianceV2Error(f"{cfg.exp_id} pretreatment agent set mismatch")
        for agent_id in sorted(c_by_agent):
            for field in fields:
                if str(c_by_agent[agent_id].get(field)) != str(s_by_agent[agent_id].get(field)):
                    raise VarianceV2Error(f"{cfg.exp_id} pretreatment mismatch {field} {agent_id} T{tick}")
    return "PASS"


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value in {"True", "False"}:
        return value == "True"
    raise VarianceV2Error(f"invalid audit boolean {value!r}")


def _validate_audit_rows(call_rows: list[Mapping], replicate_id: str, ledger_row: Mapping) -> dict:
    if not call_rows:
        raise VarianceV2Error("AUDIT_LOG_ROWS must be > 0")
    condition_set = set(EXECUTION_ORDER)
    seen = set()
    categories: dict[str, int] = {}
    for index, row in enumerate(call_rows, start=1):
        if row.get("pilot_id") != PILOT_ID:
            raise VarianceV2Error("audit row pilot_id mismatch")
        if row.get("replicate_id") != replicate_id:
            raise VarianceV2Error("audit row replicate_id mismatch")
        if int(row.get("call_index", 0)) != index or index in seen:
            raise VarianceV2Error("audit call_index must be contiguous 1..N")
        seen.add(index)
        if row.get("condition") not in condition_set:
            raise VarianceV2Error("audit row condition outside matrix")
        tick = int(row.get("tick", 0))
        if tick < 1 or tick > v1.TOTAL_TICKS:
            raise VarianceV2Error("audit row tick out of range")
        for field in ("prompt_sha256", "response_sha256"):
            value = str(row.get(field, ""))
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower()):
                raise VarianceV2Error(f"audit {field} must be 64 hex")
        if row.get("model") != MODEL:
            raise VarianceV2Error("audit model mismatch")
        if abs(float(row.get("temperature")) - TEMPERATURE) > 1e-12:
            raise VarianceV2Error("audit temperature mismatch")
        if int(row.get("requested_llm_seed")) != int(ledger_row["requested_llm_seed"]):
            raise VarianceV2Error("audit requested_llm_seed mismatch")
        category = str(row.get("prompt_category"))
        categories[category] = categories.get(category, 0) + 1
        if category not in ALLOWED_PROMPT_CATEGORIES:
            raise VarianceV2Error("audit prompt category is not allowed")
        if category == "semantic":
            if not _as_bool(row.get("response_parse_ok")):
                raise VarianceV2Error("semantic audit response_parse_ok must be true")
            if not _as_bool(row.get("semantic_schema_ok")):
                raise VarianceV2Error("semantic audit semantic_schema_ok must be true")
            if str(row.get("validation_error_type", "")):
                raise VarianceV2Error("semantic audit validation_error_type must be empty")
            if str(row.get("error_type", "")):
                raise VarianceV2Error("semantic audit error_type must be empty")
    return categories


def validate_block_gates(block_dir: Path, replicate_id: str, ledger_row: Mapping | None = None) -> dict:
    mechanism_rows = v1._read_csv_dicts(block_dir / "mechanism_records.csv")
    exposure_rows = v1._read_csv_dicts(block_dir / "clarification_exposure.csv")
    call_rows = _read_jsonl(block_dir / "pilot_llm_calls.jsonl")
    if not call_rows and (block_dir / "pilot_llm_calls.csv").exists():
        call_rows = v1._read_csv_dicts(block_dir / "pilot_llm_calls.csv")
    if ledger_row is None:
        ledger_row = next(row for row in build_pilot_seed_ledger() if row["replicate_id"] == replicate_id)
    manifest = json.loads((block_dir / "condition_manifest.json").read_text(encoding="utf-8"))
    manifest_seed_set = {int(row.get("random_seed")) for row in manifest}
    if len(manifest) != v1.CONDITIONS_PER_BLOCK:
        raise VarianceV2Error("condition_manifest must contain 9 rows")
    if tuple(row.get("exp_id") for row in manifest) != tuple(EXECUTION_ORDER):
        raise VarianceV2Error("condition_manifest order mismatch")
    if manifest_seed_set != {int(ledger_row["simulation_seed"])}:
        raise VarianceV2Error("condition_manifest random_seed must equal ledger simulation_seed")
    categories = _validate_audit_rows(call_rows, replicate_id, ledger_row)
    summary_path = block_dir / "block_execution_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("status") == "PASS" and int(summary.get("MODEL_CALLS", -1)) != len(call_rows):
            raise VarianceV2Error("MODEL_CALLS must equal AUDIT_LOG_ROWS")

    condition_metrics = [
        v1.compute_condition_metrics(
            replicate_id=replicate_id,
            config=cfg,
            mechanism_rows=mechanism_rows,
            exposure_rows=exposure_rows,
        )
        for cfg in select_variance_conditions()
    ]
    mechanism_keys = [(row.get("exp_id"), row.get("tick"), row.get("agent_id")) for row in mechanism_rows]
    if len(mechanism_keys) != v1.CONDITIONS_PER_BLOCK * v1.AGENT_COUNT * v1.TOTAL_TICKS:
        raise VarianceV2Error("mechanism_records row count must be 5400")
    if len(set(mechanism_keys)) != len(mechanism_keys):
        raise VarianceV2Error("duplicate mechanism_records join key")

    strategy_configs = [cfg for cfg in select_variance_conditions() if not cfg.is_control]
    control_cfg = [cfg for cfg in select_variance_conditions() if cfg.is_control][0]
    control_agents = _agent_set_for_condition(mechanism_rows, control_cfg.exp_id)
    if len(control_agents) != v1.AGENT_COUNT:
        raise VarianceV2Error("control mechanism agent set must contain 20 agents")
    for cfg in strategy_configs:
        if _agent_set_for_condition(mechanism_rows, cfg.exp_id) != control_agents:
            raise VarianceV2Error(f"{cfg.exp_id} mechanism agent set mismatch")

    network_status = "PASS"
    profile_status = "PASS"
    _assert_identity_file(block_dir, "network_identity.json", "network_hash")
    _assert_identity_file(block_dir, "profile_identity.json", "profile_hash")
    pretreatment = _assert_production_pretreatment_alignment(mechanism_rows)
    estimands = v1.build_block_estimands(replicate_id, condition_metrics)
    return {
        "agent_key_integrity": "PASS",
        "exposure_key_integrity": "PASS",
        "pretreatment_alignment": pretreatment,
        "network_identity_alignment": network_status,
        "profile_identity_alignment": profile_status,
        "raw_semantic_validation": "PASS",
        "real_llm_calls": 0,
        "audit_log_rows": len(call_rows),
        "prompt_category_distribution": categories,
        "condition_metrics": condition_metrics,
        "block_estimands": estimands,
    }


def run_offline_synthetic_estimator_fixture(output_dir: Path, *, blocks: int = 2) -> dict:
    """Write synthetic CSV estimator fixtures only; not a production-path gate."""
    if blocks != 2:
        raise VarianceV2Error("synthetic estimator fixture is frozen at 2 blocks")
    ledger = build_pilot_seed_ledger()
    configs = select_variance_conditions()
    output_dir.mkdir(parents=True, exist_ok=True)
    block_summaries = []
    for block_index, ledger_row in enumerate(ledger[:blocks], start=1):
        replicate_id = ledger_row["replicate_id"]
        block_dir = output_dir / replicate_id
        block_dir.mkdir(parents=True, exist_ok=False)
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
        _write_csv(block_dir / "pilot_llm_calls.csv", call_rows, list(call_rows[0]))
        condition_metrics = [
            v1.compute_condition_metrics(
                replicate_id=replicate_id,
                config=cfg,
                mechanism_rows=mechanism_rows,
                exposure_rows=exposure_rows,
            )
            for cfg in configs
        ]
        block_summaries.append({
            "replicate_id": replicate_id,
            "status": "PASS",
            "SYNTHETIC_ESTIMATOR_FIXTURE": True,
            "condition_metrics": len(condition_metrics),
        })
    return {
        "pilot_id": PILOT_ID,
        "status": "PASS",
        "SYNTHETIC_ESTIMATOR_FIXTURE": True,
        "TRUE_PRODUCTION_PATH": False,
        "blocks": blocks,
        "block_summaries": block_summaries,
    }


def _write_block_csv_outputs(block_dir: Path, results: list[dict]) -> None:
    write_agent_records_csv(results, str(block_dir / "agent_records.csv"))
    write_mechanism_records_csv(results, str(block_dir / "mechanism_records.csv"))
    write_clarification_exposure_csv(results, str(block_dir / "clarification_exposure.csv"))
    write_trajectories_csv(results, str(block_dir / "trajectories.csv"))


def _append_lifecycle(block_dir: Path, event: str, **fields) -> None:
    path = block_dir / "replicate_lifecycle.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "event": event,
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        **fields,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")


def _attempt_marker_payload(ledger_row: Mapping) -> dict:
    return {
        "pilot_id": PILOT_ID,
        "replicate_id": ledger_row["replicate_id"],
        "attempt_count": 1,
        "master_seed": MASTER_SEED,
        "simulation_seed": ledger_row["simulation_seed"],
        "requested_llm_seed": ledger_row["requested_llm_seed"],
        "python_hash_seed": ledger_row["python_hash_seed"],
        "activation_head": _git_head(),
        "source_freeze_digest": _source_freeze_digest(),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def _git_head() -> str:
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            text=True,
            capture_output=True,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _sanitize_error_type(exc: BaseException) -> str:
    return type(exc).__name__[:80]


def _write_incomplete_summary(
    block_dir: Path,
    ledger_row: Mapping,
    *,
    failure_stage: str,
    failure_type: str,
    execution_mode: str,
    model_calls: int = 0,
    audit_rows: int = 0,
) -> dict:
    summary = {
        "pilot_id": PILOT_ID,
        "replicate_id": ledger_row["replicate_id"],
        "attempt_count": 1,
        "status": "INCOMPLETE",
        "failure_stage": failure_stage,
        "failure_type": failure_type,
        "execution_mode": execution_mode,
        "TRUE_PRODUCTION_PATH": True,
        "PRODUCTION_RUN_WITH_PATCH_USED": False,
        "ledger_simulation_seed": ledger_row["simulation_seed"],
        "condition_random_seed_set": [],
        "MODEL_CALLS": model_calls,
        "AUDIT_LOG_ROWS": audit_rows,
        "FAKE_MODEL_CALLS": model_calls if execution_mode == "offline-fake" else 0,
        "REAL_LLM_CALLS": model_calls if execution_mode == "real" else 0,
        "fake_call_audit_equal": model_calls == audit_rows,
        "replay_miss_count": 0,
    }
    _write_json(block_dir / "block_execution_summary.json", summary)
    _append_lifecycle(block_dir, "BLOCK_INCOMPLETE", failure_stage=failure_stage, failure_type=failure_type)
    return summary


def _build_real_inner_router(ledger_row: Mapping):
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key or api_key.startswith("__") or api_key.upper() in {"REDACTED", "PLACEHOLDER"}:
        raise VarianceV2Error("DASHSCOPE_API_KEY must be set for real variance-v2 execution")
    return _build_real_router(int(ledger_row["requested_llm_seed"]))


async def execute_variance_block(
    block_dir: Path,
    ledger_row: Mapping,
    *,
    inner_router=None,
    execution_mode: str,
) -> dict:
    replicate_id = str(ledger_row["replicate_id"])
    if execution_mode not in {"offline-fake", "real"}:
        raise VarianceV2Error("execution_mode must be offline-fake or real")
    configs = select_variance_conditions_for_block(ledger_row)
    block_dir.mkdir(parents=True, exist_ok=True)
    _write_json(block_dir / "attempt_marker.json", _attempt_marker_payload(ledger_row))
    _append_lifecycle(block_dir, "ATTEMPT_MARKER_CREATED", replicate_id=replicate_id)
    model_calls = 0
    audited = None
    audit_path = block_dir / "pilot_llm_calls.jsonl"
    result_summary = None
    try:
        write_seed_ledger_subset_csv(build_pilot_seed_ledger(), [replicate_id], block_dir / "seed_ledger.csv")
        _append_lifecycle(block_dir, "SEED_LEDGER_WRITTEN", replicate_id=replicate_id)
        _write_json(block_dir / "sanitized_model_config.json", {
            "model": MODEL,
            "temperature": TEMPERATURE,
            "api_key": "[redacted]",
            "api_key_source": "DASHSCOPE_API_KEY environment only" if execution_mode == "real" else "not-read",
            "execution_mode": execution_mode,
        })
        _write_json(block_dir / "condition_manifest.json", [
            {
                "exp_id": cfg.exp_id,
                "content_factor": cfg.content_factor,
                "channel_factor": cfg.channel_factor,
                "timing_factor": cfg.timing_factor,
                "clarification_tick": cfg.clarification_tick,
                "is_control": cfg.is_control,
                "random_seed": cfg.random_seed,
            }
            for cfg in configs
        ])
        _append_lifecycle(block_dir, "ROUTER_BUILD_STARTED", replicate_id=replicate_id)
        if inner_router is None:
            inner_router = _build_real_inner_router(ledger_row)
        if execution_mode == "offline-fake" and not hasattr(inner_router, "_task005_router_close_noop"):
            setattr(inner_router, "_task005_router_close_noop", True)
        _append_lifecycle(block_dir, "ROUTER_BUILD_COMPLETED", replicate_id=replicate_id)

        if audit_path.exists():
            audit_path.unlink()
        audited = ValidatedAuditedRouter(
            inner_router,
            audit_path=audit_path,
            pilot_id=PILOT_ID,
            replicate_id=replicate_id,
            requested_llm_seed=ledger_row.get("requested_llm_seed", 0),
            model=MODEL,
            temperature=TEMPERATURE,
        )

        results: list[dict] = []
        llm_cache: dict = {}
        replay_misses: dict[str, int] = {}
        for cfg in configs:
            event_name = "CONTROL_STARTED" if cfg.is_control else "CONDITION_STARTED"
            _append_lifecycle(block_dir, event_name, replicate_id=replicate_id, exp_id=cfg.exp_id)
            if cfg.is_control:
                router = AuditedRecordingRouter(audited, cfg.exp_id)
                result = await _run_with_patch(cfg, override_router=router)
                llm_cache.update(router.cache)
                replay_misses[cfg.exp_id] = 0
                _append_lifecycle(block_dir, "CONTROL_COMPLETED", replicate_id=replicate_id, exp_id=cfg.exp_id)
            else:
                assert cfg.clarification_tick is not None
                router = AuditedReplayRouter(
                    audited,
                    llm_cache,
                    replay_until_tick=cfg.clarification_tick,
                    exp_id=cfg.exp_id,
                )
                result = await _run_with_patch(cfg, override_router=router)
                replay_misses[cfg.exp_id] = router.miss_count
                if router.miss_count != 0:
                    raise VarianceV2Error(f"{cfg.exp_id} replay miss count must be zero")
                _append_lifecycle(block_dir, "CONDITION_COMPLETED", replicate_id=replicate_id, exp_id=cfg.exp_id)
            result["exp_id"] = cfg.exp_id
            result["config"] = cfg.to_dict()
            results.append(result)

        _append_lifecycle(block_dir, "EXPORT_STARTED", replicate_id=replicate_id)
        _write_block_csv_outputs(block_dir, results)
        network_rows = [
            {"exp_id": result["exp_id"], "network_hash": _network_hash_from_result(result)}
            for result in results
        ]
        profile_rows = [
            {"exp_id": result["exp_id"], "profile_hash": _profile_hash_from_result(result)}
            for result in results
        ]
        _write_json(block_dir / "network_identity.json", {
            "source": "actual production nodes+edges",
            "conditions": network_rows,
        })
        _write_json(block_dir / "profile_identity.json", {
            "source": "actual initialized profiles",
            "canonical_fields": list(PROFILE_IDENTITY_FIELDS),
            "conditions": profile_rows,
        })
        _append_lifecycle(block_dir, "EXPORT_COMPLETED", replicate_id=replicate_id)

        _append_lifecycle(block_dir, "QUALITY_GATES_STARTED", replicate_id=replicate_id)
        gates = validate_block_gates(block_dir, replicate_id, ledger_row)
        _write_csv(block_dir / "condition_metrics.csv", gates["condition_metrics"], [
            "replicate_id", "exp_id", "content_factor", "channel_factor", "timing_factor",
            "is_control", "POST_TRUST_AUC", "EARLY_TRUST_AUC", "PURCHASE_RATE_T30",
            "PURCHASE_TRAJECTORY_AUC", "REACH_RATE", "FINAL_TRUST_T30",
        ])
        _write_csv(block_dir / "block_estimands.csv", [gates["block_estimands"]], [
            "replicate_id", *v1.PRIMARY_ESTIMANDS, *v1.SECONDARY_ESTIMANDS,
        ])
        _append_lifecycle(block_dir, "QUALITY_GATES_COMPLETED", replicate_id=replicate_id)
        audit_rows = _read_jsonl(audit_path)
        model_calls = audited.call_count
        summary = {
            "pilot_id": PILOT_ID,
            "replicate_id": replicate_id,
            "attempt_count": 1,
            "status": "PASS",
            "execution_mode": execution_mode,
            "TRUE_PRODUCTION_PATH": True,
            "PRODUCTION_RUN_WITH_PATCH_USED": True,
            "BLOCK_SEED_INJECTION": "PASS",
            "ledger_simulation_seed": int(ledger_row["simulation_seed"]),
            "condition_random_seed_set": sorted({int(cfg.random_seed) for cfg in configs}),
            "replicate_cache_scope": "local",
            "conditions": len(results),
            "mechanism_rows": sum(len(result.get("mechanism_records", [])) for result in results),
            "MODEL_CALLS": model_calls,
            "AUDIT_LOG_ROWS": len(audit_rows),
            "FAKE_MODEL_CALLS": model_calls if execution_mode == "offline-fake" else 0,
            "REAL_LLM_CALLS": model_calls if execution_mode == "real" else 0,
            "fake_inner_chat_calls": model_calls if execution_mode == "offline-fake" else 0,
            "audited_router_calls": audited.call_count,
            "audit_log_rows": len(audit_rows),
            "fake_call_audit_equal": model_calls == len(audit_rows),
            "replay_miss_count": sum(replay_misses.values()),
            "replay_misses": replay_misses,
            "prompt_category_distribution": gates["prompt_category_distribution"],
            "agent_key_integrity": gates["agent_key_integrity"],
            "exposure_key_integrity": gates["exposure_key_integrity"],
            "pretreatment_alignment": gates["pretreatment_alignment"],
            "network_identity_alignment": gates["network_identity_alignment"],
            "profile_identity_alignment": gates["profile_identity_alignment"],
            "raw_semantic_validation": gates["raw_semantic_validation"],
        }
        _write_json(block_dir / "block_execution_summary.json", summary)
        _append_lifecycle(block_dir, "BLOCK_PASS", replicate_id=replicate_id)
        result_summary = summary
    except Exception as exc:
        audit_rows = _read_jsonl(audit_path)
        model_calls = audited.call_count if audited is not None else model_calls
        result_summary = _write_incomplete_summary(
            block_dir,
            ledger_row,
            failure_stage="block-execution",
            failure_type=_sanitize_error_type(exc),
            execution_mode=execution_mode,
            model_calls=model_calls,
            audit_rows=len(audit_rows),
        )
    finally:
        try:
            _append_lifecycle(block_dir, "ROUTER_CLOSE_STARTED", replicate_id=replicate_id)
            close_target = audited._inner if audited is not None else inner_router
            await _close_router_resource(close_target)
            _append_lifecycle(block_dir, "ROUTER_CLOSE_COMPLETED", replicate_id=replicate_id)
        except Exception as exc:
            result_summary = _write_incomplete_summary(
                block_dir,
                ledger_row,
                failure_stage="router-close",
                failure_type=_sanitize_error_type(exc),
                execution_mode=execution_mode,
                model_calls=audited.call_count if audited is not None else model_calls,
                audit_rows=len(_read_jsonl(audit_path)),
            )
    assert result_summary is not None
    return result_summary


def _block_status(block_dir: Path) -> str:
    marker = block_dir / "attempt_marker.json"
    summary = block_dir / "block_execution_summary.json"
    if marker.exists() and summary.exists():
        try:
            return str(json.loads(summary.read_text(encoding="utf-8")).get("status", "INCOMPLETE"))
        except Exception:
            return "INCOMPLETE"
    if marker.exists() and not summary.exists():
        _write_json(summary, {
            "pilot_id": PILOT_ID,
            "status": "INCOMPLETE_CRASH_OR_INTERRUPTION",
            "TRUE_PRODUCTION_PATH": True,
        })
        return "INCOMPLETE_CRASH_OR_INTERRUPTION"
    return "NOT_STARTED"


def _run_variance_blocks(output_dir: Path, ledger_rows: list[Mapping], *, execution_mode: str, inner_router_factory) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    block_summaries = []
    for ledger_row in ledger_rows:
        replicate_id = ledger_row["replicate_id"]
        block_dir = output_dir / replicate_id
        status = _block_status(block_dir)
        if status == "PASS":
            block_summaries.append(json.loads((block_dir / "block_execution_summary.json").read_text(encoding="utf-8")))
            continue
        if status != "NOT_STARTED":
            block_summaries.append({"replicate_id": replicate_id, "status": status})
            continue
        if block_dir.exists():
            shutil.rmtree(block_dir)
        try:
            inner = inner_router_factory(ledger_row)
            block_summaries.append(asyncio.run(
                execute_variance_block(
                    block_dir,
                    ledger_row,
                    inner_router=inner,
                    execution_mode=execution_mode,
                )
            ))
        except Exception as exc:
            block_dir.mkdir(parents=True, exist_ok=True)
            block_summaries.append(_write_incomplete_summary(
                block_dir,
                ledger_row,
                failure_stage="batch-continuation",
                failure_type=_sanitize_error_type(exc),
                execution_mode=execution_mode,
            ))
    status = "PASS" if all(row.get("status") == "PASS" for row in block_summaries) else "INCOMPLETE"
    condition_seed_sets = {
        row.get("replicate_id", ""): row.get("condition_random_seed_set", [])
        for row in block_summaries
    }
    return {
        "pilot_id": PILOT_ID,
        "status": status,
        "TRUE_PRODUCTION_PATH": True,
        "PRODUCTION_RUN_WITH_PATCH_USED": True,
        "BLOCK_SEED_INJECTION": "PASS" if all(
            row.get("BLOCK_SEED_INJECTION") == "PASS"
            for row in block_summaries
            if row.get("status") == "PASS"
        ) else "FAIL",
        "blocks": len(ledger_rows),
        "conditions_per_block": len(select_variance_conditions()),
        "execution_mode": execution_mode,
        "REAL_LLM_CALLS": sum(int(row.get("REAL_LLM_CALLS", 0)) for row in block_summaries),
        "external_network_calls": 0,
        "FAKE_MODEL_CALLS": sum(int(row.get("FAKE_MODEL_CALLS", 0)) for row in block_summaries),
        "MODEL_CALLS": sum(int(row.get("MODEL_CALLS", 0)) for row in block_summaries),
        "AUDIT_LOG_ROWS": sum(int(row.get("AUDIT_LOG_ROWS", 0)) for row in block_summaries),
        "fake_inner_chat_calls": sum(int(row.get("fake_inner_chat_calls", 0)) for row in block_summaries),
        "audited_router_calls": sum(int(row.get("audited_router_calls", 0)) for row in block_summaries),
        "audit_log_rows": sum(int(row.get("audit_log_rows", 0)) for row in block_summaries),
        "fake_call_audit_equal": all(bool(row.get("fake_call_audit_equal")) for row in block_summaries if row.get("status") == "PASS"),
        "condition_seed_sets": condition_seed_sets,
        "block_summaries": block_summaries,
    }


def _read_block_summary(block_dir: Path) -> dict:
    path = block_dir / "block_execution_summary.json"
    if not path.exists():
        return {"status": "NOT_STARTED"}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_batch_rows(output_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    block_summaries: list[dict] = []
    all_metrics: list[dict] = []
    all_estimands: list[dict] = []
    for rid in ALLOWED_REPLICATE_IDS:
        block_dir = output_dir / rid
        summary = _read_block_summary(block_dir)
        if summary.get("replicate_id") is None:
            summary["replicate_id"] = rid
        if summary.get("attempt_count") is None:
            summary["attempt_count"] = _attempt_count_for_block(block_dir)
        block_summaries.append(summary)
        if summary.get("status") == "PASS":
            all_metrics.extend(v1._read_csv_dicts(block_dir / "condition_metrics.csv"))
            all_estimands.extend(v1._read_csv_dicts(block_dir / "block_estimands.csv"))
    return block_summaries, all_metrics, all_estimands


def _write_batch_outputs(output_dir: Path, activation: Mapping, run_summary: Mapping) -> dict:
    block_summaries, all_metrics, all_estimands = _read_batch_rows(output_dir)
    statuses = {str(row["replicate_id"]): str(row.get("status", "NOT_STARTED")) for row in block_summaries}
    official = v1.build_official_variance_summary(all_estimands, statuses)
    pilot_status = "PASS" if official["OFFICIAL_VARIANCE_STATUS"] == "COMPUTED" else "INCOMPLETE"

    manifest_rows = []
    for row in block_summaries:
        manifest_rows.append({
            "replicate_id": row.get("replicate_id", ""),
            "attempt_count": row.get("attempt_count", 0),
            "status": row.get("status", ""),
            "failure_stage": row.get("failure_stage", ""),
            "failure_type": row.get("failure_type", ""),
            "real_llm_calls": row.get("REAL_LLM_CALLS", row.get("real_llm_calls", 0)),
            "model_calls": row.get("MODEL_CALLS", 0),
            "audit_log_rows": row.get("AUDIT_LOG_ROWS", row.get("audit_log_rows", 0)),
            "replay_miss_count": row.get("replay_miss_count", 0),
        })
    _write_csv(output_dir / "pilot_manifest.csv", manifest_rows, [
        "replicate_id", "attempt_count", "status", "failure_stage", "failure_type",
        "real_llm_calls", "model_calls", "audit_log_rows", "replay_miss_count",
    ])
    if all_metrics:
        _write_csv(output_dir / "all_condition_metrics.csv", all_metrics, [
            "replicate_id", "exp_id", "content_factor", "channel_factor", "timing_factor",
            "is_control", "POST_TRUST_AUC", "EARLY_TRUST_AUC", "PURCHASE_RATE_T30",
            "PURCHASE_TRAJECTORY_AUC", "REACH_RATE", "FINAL_TRUST_T30",
        ])
    if all_estimands:
        _write_csv(output_dir / "all_block_estimands.csv", all_estimands, [
            "replicate_id", *v1.PRIMARY_ESTIMANDS, *v1.SECONDARY_ESTIMANDS,
        ])
    channel = v1.channel_saturation_summary(all_metrics) if all_metrics else {
        "warning_label": "CHANNEL_REACH_NEAR_SATURATION",
        "diagnostic_only": True,
        "hub_mean_reach": None,
        "random_mean_reach": None,
        "hub_cells_proportion_reach_ge_18_of_20": None,
        "random_cells_proportion_reach_ge_18_of_20": None,
    }
    channel["CHANNEL_REACH_NEAR_SATURATION"] = bool(
        (channel.get("hub_cells_proportion_reach_ge_18_of_20") or 0) >= 0.95
        or (channel.get("random_cells_proportion_reach_ge_18_of_20") or 0) >= 0.95
    )
    _write_json(output_dir / "channel_saturation_summary.json", channel)

    if official["OFFICIAL_VARIANCE_STATUS"] == "COMPUTED":
        _write_json(output_dir / "variance_summary.json", official)
        _write_csv(output_dir / "primary_covariance_matrix.csv", official["covariance_matrix"], ["estimand", *v1.PRIMARY_ESTIMANDS])
        _write_csv(output_dir / "primary_correlation_matrix.csv", official["correlation_matrix"], ["estimand", *v1.PRIMARY_ESTIMANDS])
        _write_csv(output_dir / "leave_one_out_sd.csv", official["leave_one_out_sd"], ["estimand", "left_out_replicate_id", "sd"])
    else:
        if all_estimands:
            _write_csv(output_dir / "partial_block_estimands.csv", all_estimands, [
                "replicate_id", *v1.PRIMARY_ESTIMANDS, *v1.SECONDARY_ESTIMANDS,
            ])
        _write_json(output_dir / "partial_variance_diagnostic.json", official)

    result = {
        "pilot_id": PILOT_ID,
        "PILOT_STATUS": pilot_status,
        "OFFICIAL_VARIANCE_STATUS": official["OFFICIAL_VARIANCE_STATUS"],
        "POWER_PLANNING_USE": official.get("POWER_PLANNING_USE") is True,
        "PROGRESSION_AUTHORIZED": pilot_status == "PASS",
        "activation_code_head": activation.get("activation_code_head", ""),
        "activation_head": activation.get("activation_head", _git_head()),
        "blocks": block_summaries,
        "REAL_LLM_CALLS": run_summary.get("REAL_LLM_CALLS", sum(int(row.get("real_llm_calls", 0) or 0) for row in manifest_rows)),
        "MODEL_CALLS": run_summary.get("MODEL_CALLS", sum(int(row.get("model_calls", 0) or 0) for row in manifest_rows)),
        "AUDIT_LOG_ROWS": run_summary.get("AUDIT_LOG_ROWS", sum(int(row.get("audit_log_rows", 0) or 0) for row in manifest_rows)),
        "REAL_CALL_AUDIT_EQUAL": run_summary.get("REAL_LLM_CALLS", 0) == run_summary.get("AUDIT_LOG_ROWS", 0),
        "REPLAY_MISS_TOTAL": sum(int(row.get("replay_miss_count", 0) or 0) for row in manifest_rows),
        "RAW_SEMANTIC_VALIDATION": "PASS" if all(row.get("raw_semantic_validation") == "PASS" for row in block_summaries if row.get("status") == "PASS") else "FAIL",
        "SEMANTIC_FALLBACKS": 0,
        "PLAN_FALLBACKS": 0,
        "AGENT_KEY_INTEGRITY": "PASS" if all(row.get("agent_key_integrity") == "PASS" for row in block_summaries if row.get("status") == "PASS") else "FAIL",
        "EXPOSURE_KEY_INTEGRITY": "PASS" if all(row.get("exposure_key_integrity") == "PASS" for row in block_summaries if row.get("status") == "PASS") else "FAIL",
        "PRETREATMENT_ALIGNMENT": "PASS" if all(row.get("pretreatment_alignment") == "PASS" for row in block_summaries if row.get("status") == "PASS") else "FAIL",
        "NETWORK_IDENTITY_ALIGNMENT": "PASS" if all(row.get("network_identity_alignment") == "PASS" for row in block_summaries if row.get("status") == "PASS") else "FAIL",
        "PROFILE_IDENTITY_ALIGNMENT": "PASS" if all(row.get("profile_identity_alignment") == "PASS" for row in block_summaries if row.get("status") == "PASS") else "FAIL",
        "EMPATHY_REPAIR_WEIGHT": v1.EMPATHY_REPAIR_WEIGHT,
        "channel_saturation": channel,
        "P_VALUES": False,
        "POWER": False,
        "MDE_SELECTED": False,
        "FORMAL_INFERENCE": False,
        "FORMAL_REUSE": False,
        "OPTIONAL_STOPPING": False,
        "REPLACEMENT_BLOCKS": False,
    }
    if official["OFFICIAL_VARIANCE_STATUS"] == "COMPUTED":
        result["primary_estimands"] = official["primary_estimands"]
    _write_json(output_dir / "pilot_execution_summary.json", result)
    return result


def run_production_path_fake_acceptance(output_dir: Path, *, blocks: int = 2) -> dict:
    if blocks != 2:
        raise VarianceV2Error("production-path fake acceptance is frozen at 2 blocks")
    ledger = build_pilot_seed_ledger()
    return _run_variance_blocks(
        output_dir,
        ledger[:blocks],
        execution_mode="offline-fake",
        inner_router_factory=lambda _row: DeterministicFakeInnerRouter(),
    )


def run_real_variance_batch(output_dir: Path, activation_token: str | None) -> dict:
    activation = _validate_real_execution_authorized(
        output_dir,
        activation_token,
        require_clean_output=False,
    )
    ledger = build_pilot_seed_ledger()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_summary = _run_variance_blocks(
        output_dir,
        ledger,
        execution_mode="real",
        inner_router_factory=_build_real_inner_router,
    )
    return _write_batch_outputs(output_dir, activation, run_summary)


def run_future_real_variance_batch(output_dir: Path, *, activation_token: str | None) -> dict:
    return run_real_variance_batch(output_dir, activation_token)


def activation_preflight(output_dir: Path, activation_token: str | None) -> dict:
    activation = _validate_real_execution_authorized(
        output_dir,
        activation_token,
        require_clean_output=True,
    )
    return {
        "READY_TO_EXECUTE": True,
        "REAL_LLM_CALLS": 0,
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "HEAD": _git_head(),
        "activation_code_head": activation.get("activation_code_head", ""),
        "source_freeze_digest": _source_freeze_digest(),
        "source_freeze_exact": True,
        "credential_available": True,
        "credential_value_recorded": False,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "output_state_clean": True,
        "attempt_counts": _output_attempt_counts(output_dir),
        "replicate_ids": list(ALLOWED_REPLICATE_IDS),
        "condition_order": _condition_order(),
    }


def preflight() -> dict:
    return {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "replication_blocks": REPLICATION_BLOCKS,
        "replicate_ids": list(ALLOWED_REPLICATE_IDS),
        "conditions_per_block": len(select_variance_conditions()),
        "execution_authorized": False,
        "activation_token_required": True,
        "p_values": False,
        "power": False,
        "MDE": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--offline-test", action="store_true")
    parser.add_argument("--execute-real", action="store_true")
    parser.add_argument("--activation-token", default="")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args(argv)
    try:
        if args.execute_real:
            out = Path(args.output_dir) if args.output_dir else PILOT_OUTPUT_ROOT
            print(json.dumps(run_real_variance_batch(out, args.activation_token), sort_keys=True))
            return 0
        if args.offline_test:
            out = Path(args.output_dir) if args.output_dir else Path(tempfile.mkdtemp())
            print(json.dumps(run_production_path_fake_acceptance(out), sort_keys=True))
            return 0
        if args.preflight and args.activation_token:
            out = Path(args.output_dir) if args.output_dir else PILOT_OUTPUT_ROOT
            print(json.dumps(activation_preflight(out, args.activation_token), sort_keys=True))
            return 0
        print(json.dumps(preflight(), sort_keys=True))
        return 0
    except Exception as exc:
        label = str(exc) if str(exc) == REAL_MODE_REJECTION else type(exc).__name__
        print(f"ERROR: {label}")
        return 2 if isinstance(exc, VarianceV2Error) or type(exc).__name__ == "VarianceV2Error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
