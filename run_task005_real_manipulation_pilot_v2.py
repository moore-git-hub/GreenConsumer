"""TASK_005 real-LLM manipulation-check pilot v2 runner.

Pilot v2 freezes the perceived-empathy construct amendment, strict raw semantic
response validation, record/replay execution boundary, activation gates, and
engineering-only manipulation checks. Real LLM calls are authorized only after
the frozen activation artifact, token, source hashes, clean tree, credential,
and output-directory gates all pass.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable, Mapping

# The pilot runner must protect its own import path from HuggingFace /
# Transformers metadata lookups. Use assignment, not setdefault, so parent
# env values such as HF_HUB_OFFLINE=0 cannot weaken offline preparation tests.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import yaml

from experiment_config import generate_experiment_matrix
from replication_config import (
    build_seed_ledger,
    write_seed_ledger_csv,
)
from run_experiments import (
    RecordingRouter,
    ReplicationStartupError,
    ReplayRouter,
    TASK005_LLM_API_KEY_ENV,
    TASK005_LLM_API_KEY_PLACEHOLDER,
    _build_real_router,
    _close_router_resource,
    _is_placeholder_secret,
    _run_with_patch,
    write_agent_records_csv,
    write_clarification_exposure_csv,
    write_mechanism_records_csv,
    write_trajectories_csv,
)
from simulation_core import MECHANISM_RECORDS_FIELDS


PILOT_ID = "task005-real-manipulation-pilot-v2"
MASTER_SEED = 2026080903
PILOT_REPLICATION_BLOCKS = 2
ALLOWED_REPLICATE_IDS = ("R001", "R002")
PILOT_CONDITION_IDS = (
    "NoClarification-Control",
    "Rational-Hub-Immediate",
    "Empathy-Hub-Immediate",
)
PROVIDER = "OpenAIProvider"
MODEL = "qwen-plus"
TEMPERATURE = 0.3
ENGINEERING_SEPARATION_FLOOR = 0.05
TOPIC_RELEVANCE_WARNING_THRESHOLD = 0.10
REAL_MODE_REJECTION = "PILOT_V2_REAL_EXECUTION_NOT_AUTHORIZED"
ACTIVATION_TOKEN = "TASK005_REAL_MANIPULATION_V2_ACTIVATE_20260809_01"
EXPECTED_BRANCH = "redesign/task005-mechanism-v2"
PILOT_OUTPUT_ROOT = Path("results") / "pilots" / PILOT_ID
ACTIVATION_ARTIFACT = (
    Path(".kiro")
    / "specs"
    / "task005-replication-inference"
    / "real_llm_manipulation_pilot_v2_activation1.0.json"
)
SOURCE_FREEZE_FILES = (
    "run_task005_real_manipulation_pilot_v2.py",
    "run_experiments.py",
    "simulation_core.py",
    "mechanism_v2.py",
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "clarification_injector.py",
    "experiment_config.py",
    "replication_config.py",
    ".kiro/specs/task005-replication-inference/manipulation_construct_validity_amendment2.0.json",
    ".kiro/specs/task005-replication-inference/mechanism_auditability_schema_amendment1.1.json",
    ".kiro/specs/task005-replication-inference/real_llm_manipulation_check_pilot_v2_contract1.0.json",
)

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


class PilotContractError(RuntimeError):
    """Raised when the pilot preparation contract is violated."""


class PilotSemanticValidationError(PilotContractError):
    """Raised when a raw real semantic response violates the v2 schema."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_stdout(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise PilotContractError(f"git command failed: {' '.join(args)}")
    return proc.stdout.strip()


def _assert_clean_tree() -> None:
    if _git_stdout(["branch", "--show-current"]) != EXPECTED_BRANCH:
        raise PilotContractError("branch mismatch")
    if _git_stdout(["diff", "--name-only"]):
        raise PilotContractError("tracked diff must be clean")
    if _git_stdout(["diff", "--cached", "--name-only"]):
        raise PilotContractError("staged diff must be clean")


def _assert_no_pilot_python_process() -> None:
    current_pid = os.getpid()
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { "
                    "($_.Name -match '^python') -and "
                    "($_.CommandLine -match 'task005-real-manipulation-pilot-v2|run_experiments.py') "
                    "} | "
                    "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
                ),
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
    except Exception:
        return
    if proc.returncode != 0 or not proc.stdout.strip():
        return
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        return
    rows = payload if isinstance(payload, list) else [payload]
    for row in rows:
        pid = int(row.get("ProcessId", -1))
        if pid != current_pid:
            raise PilotContractError("existing pilot or real-mode Python process detected")


def current_source_hashes() -> dict[str, str]:
    hashes = {}
    for rel in SOURCE_FREEZE_FILES:
        path = Path(rel)
        if not path.exists():
            raise PilotContractError(f"source freeze file missing: {rel}")
        hashes[rel] = _sha256_file(path)
    return hashes


def load_activation_artifact() -> dict:
    if not ACTIVATION_ARTIFACT.exists():
        raise PilotContractError("activation artifact missing")
    try:
        artifact = json.loads(ACTIVATION_ARTIFACT.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PilotContractError("activation artifact is invalid JSON") from exc
    if not isinstance(artifact, dict):
        raise PilotContractError("activation artifact must be an object")
    return artifact


def validate_activation_artifact(artifact: Mapping) -> None:
    if artifact.get("pilot_id") != PILOT_ID:
        raise PilotContractError("activation pilot_id mismatch")
    if artifact.get("activation_token") != ACTIVATION_TOKEN:
        raise PilotContractError("activation token artifact mismatch")
    if artifact.get("master_seed") != MASTER_SEED:
        raise PilotContractError("activation master_seed mismatch")
    if tuple(artifact.get("replicates", [])) != ALLOWED_REPLICATE_IDS:
        raise PilotContractError("activation replicate set mismatch")
    if tuple(artifact.get("conditions", [])) != PILOT_CONDITION_IDS:
        raise PilotContractError("activation condition set mismatch")
    if artifact.get("model") != MODEL or artifact.get("temperature") != TEMPERATURE:
        raise PilotContractError("activation model configuration mismatch")
    if artifact.get("formal_inference") is not False or artifact.get("p_values") is not False:
        raise PilotContractError("activation scientific flags mismatch")
    expected_hashes = artifact.get("source_sha256")
    if not isinstance(expected_hashes, dict):
        raise PilotContractError("activation source hashes missing")
    if current_source_hashes() != expected_hashes:
        raise PilotContractError("SOURCE_FREEZE_MISMATCH")


def assert_output_dir_available(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise PilotContractError("pilot output directory exists and is non-empty")
    if output_dir == PILOT_OUTPUT_ROOT and output_dir.exists():
        raise PilotContractError("current pilot output directory already exists")


def assert_activation_ready(token: str | None, output_dir: Path) -> dict:
    if token != ACTIVATION_TOKEN:
        raise PilotContractError(REAL_MODE_REJECTION)
    _assert_clean_tree()
    _assert_no_pilot_python_process()
    require_pilot_credential()
    assert_output_dir_available(output_dir)
    artifact = load_activation_artifact()
    validate_activation_artifact(artifact)
    return {
        "REAL_LLM_CALLS": 0,
        "READY_TO_EXECUTE": True,
        "pilot_id": PILOT_ID,
        "output_dir": str(output_dir),
    }


def require_pilot_credential() -> str:
    value = os.environ.get(TASK005_LLM_API_KEY_ENV, "")
    if _is_placeholder_secret(value):
        raise PilotContractError("missing credential for real pilot preflight")
    return value


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
    configs = []
    for exp_id in PILOT_CONDITION_IDS:
        if exp_id not in by_id:
            raise PilotContractError(f"missing pilot condition {exp_id}")
        configs.append(by_id[exp_id])
    return configs


def build_pilot_manifest_rows(ledger_rows: list[dict]) -> list[dict]:
    configs = select_pilot_conditions()
    rows: list[dict] = []
    for ledger in ledger_rows:
        for order, cfg in enumerate(configs, start=1):
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


def sanitized_model_config() -> dict:
    config_path = Path("configs") / "models_config.yaml"
    conf = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    entries = conf if isinstance(conf, list) else [conf]
    entry = next(
        (
            item
            for item in entries
            if isinstance(item, dict) and "chat" in (item.get("capabilities") or [])
        ),
        entries[0] if entries else {},
    )
    safe = {
        "provider": entry.get("name"),
        "model": entry.get("model"),
        "base_url": entry.get("base_url"),
        "capabilities": list(entry.get("capabilities") or []),
        "temperature": entry.get("temperature"),
        "requested_seed": "from pilot seed ledger",
        "api_key": "<REDACTED>",
    }
    if safe["provider"] != PROVIDER or safe["model"] != MODEL or safe["temperature"] != TEMPERATURE:
        raise PilotContractError("scientific model configuration changed")
    return safe


def write_offline_dry_run_artifacts(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = build_pilot_seed_ledger()
    manifest = build_pilot_manifest_rows(ledger)
    write_seed_ledger_csv(ledger, output_dir / "seed_ledger.csv")
    _write_csv(output_dir / "pilot_manifest.csv", manifest)
    (output_dir / "sanitized_model_config.json").write_text(
        json.dumps(sanitized_model_config(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "replication_blocks": PILOT_REPLICATION_BLOCKS,
        "replicate_ids": list(ALLOWED_REPLICATE_IDS),
        "conditions_per_block": len(PILOT_CONDITION_IDS),
        "condition_ids": list(PILOT_CONDITION_IDS),
        "FORMAL_INFERENCE": False,
        "P_VALUES_COMPUTED": False,
        "PILOT_ONLY": True,
        "REAL_LLM_CALLS": False,
    }
    (output_dir / "manipulation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _write_csv(path: Path, rows: list[Mapping]) -> None:
    if not rows:
        raise PilotContractError(f"cannot write empty CSV {path}")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _secret_patterns() -> list[str]:
    values = [os.environ.get(TASK005_LLM_API_KEY_ENV, "")]
    return [value for value in values if value]


def sanitize_text(text: str) -> str:
    safe = str(text)
    for secret in _secret_patterns():
        safe = safe.replace(secret, "<REDACTED>")
    safe = re.sub(
        r"Authorization\s*:\s*Bearer\s+\S+",
        "Authorization: Bearer <REDACTED>",
        safe,
        flags=re.I,
    )
    return safe


def _write_block_summary(path: Path, summary: Mapping) -> None:
    path.write_text(
        json.dumps(dict(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


SEMANTIC_RESPONSE_FIELDS = (
    "valence",
    "arousal",
    "credibility",
    "evidence_strength",
    "topic_relevance",
    "perceived_empathy",
    "hypocrisy_perceived",
    "importance",
    "reasoning",
)


def _semantic_number(payload: Mapping, field: str, low: float, high: float) -> float:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PilotSemanticValidationError(f"{field}: wrong type")
    number = float(value)
    if not math.isfinite(number):
        raise PilotSemanticValidationError(f"{field}: non-finite")
    if number < low or number > high:
        raise PilotSemanticValidationError(f"{field}: out of range")
    return number


def validate_raw_semantic_response(response: str) -> dict:
    try:
        payload = json.loads(response)
    except Exception as exc:
        raise PilotSemanticValidationError("response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise PilotSemanticValidationError("response JSON must be an object")
    missing = [field for field in SEMANTIC_RESPONSE_FIELDS if field not in payload]
    if missing:
        raise PilotSemanticValidationError(f"missing semantic fields: {missing}")
    _semantic_number(payload, "valence", -1.0, 1.0)
    for field in (
        "arousal",
        "credibility",
        "evidence_strength",
        "topic_relevance",
        "perceived_empathy",
    ):
        _semantic_number(payload, field, 0.0, 1.0)
    if not isinstance(payload.get("hypocrisy_perceived"), bool):
        raise PilotSemanticValidationError("hypocrisy_perceived: wrong type")
    _semantic_number(payload, "importance", 1.0, 10.0)
    if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
        raise PilotSemanticValidationError("reasoning: empty")
    return payload


def _is_reflect_semantic_prompt(prompt: str) -> bool:
    text = prompt.lower()
    return (
        "return json" in text
        and "valence" in text
        and "arousal" in text
        and "credibility" in text
    )


class ValidatedAuditedRealRouter:
    def __init__(
        self,
        inner,
        *,
        pilot_id: str,
        replicate_id: str,
        requested_llm_seed: int,
        call_log_path: Path,
        lifecycle_path: Path | None = None,
    ):
        self._inner = inner
        self._pilot_id = pilot_id
        self._replicate_id = replicate_id
        self._requested_llm_seed = requested_llm_seed
        self._call_log_path = call_log_path
        self._lifecycle_path = lifecycle_path
        self._condition = ""
        self._tick = -1
        self.call_count = 0
        self._first_chat_started = False
        self._first_chat_completed = False

    def set_context(self, *, condition: str, tick: int) -> None:
        self._condition = condition
        self._tick = tick

    async def chat(self, prompt: str) -> str:
        self.call_count += 1
        call_index = self.call_count
        started = time.perf_counter()
        response = ""
        error_type = ""
        parse_ok = False
        semantic_ok = False
        validation_error_type = ""
        try:
            if not self._first_chat_started and self._lifecycle_path is not None:
                _append_lifecycle(
                    self._lifecycle_path,
                    self._replicate_id,
                    "FIRST_CHAT_STARTED",
                    "ok",
                )
                self._first_chat_started = True
            response = await self._inner.chat(prompt)
            parse_ok = _looks_like_json_object(response)
            if not self._first_chat_completed and self._lifecycle_path is not None:
                _append_lifecycle(
                    self._lifecycle_path,
                    self._replicate_id,
                    "FIRST_CHAT_COMPLETED",
                    "ok",
                )
                self._first_chat_completed = True
            if _is_reflect_semantic_prompt(prompt):
                validate_raw_semantic_response(response)
                semantic_ok = True
            return response
        except PilotSemanticValidationError as exc:
            error_type = type(exc).__name__
            validation_error_type = type(exc).__name__
            raise
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            row = {
                "pilot_id": self._pilot_id,
                "replicate_id": self._replicate_id,
                "condition": self._condition,
                "tick": self._tick,
                "call_index": call_index,
                "prompt_sha256": _sha256_text(prompt),
                "response_sha256": _sha256_text(response),
                "response_parse_ok": parse_ok,
                "semantic_schema_ok": semantic_ok,
                "validation_error_type": validation_error_type,
                "prompt_category": _prompt_category(prompt),
                "latency_ms": latency_ms,
                "error_type": error_type,
                "requested_llm_seed": self._requested_llm_seed,
                "model": MODEL,
                "temperature": TEMPERATURE,
            }
            with self._call_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")


class PilotRecordingRouter(RecordingRouter):
    def __init__(self, inner_router: ValidatedAuditedRealRouter, condition: str):
        super().__init__(inner_router)
        self._audited_inner = inner_router
        self._condition = condition

    def set_tick(self, tick: int):
        self._audited_inner.set_context(condition=self._condition, tick=tick)
        super().set_tick(tick)


class PilotReplayRouter(ReplayRouter):
    def __init__(
        self,
        inner_router: ValidatedAuditedRealRouter,
        cache: dict,
        replay_until_tick: int,
        exp_id: str,
    ):
        super().__init__(inner_router, cache, replay_until_tick, exp_id=exp_id)
        self._audited_inner = inner_router
        self._condition = exp_id

    def set_tick(self, tick: int):
        self._audited_inner.set_context(condition=self._condition, tick=tick)
        super().set_tick(tick)


def _looks_like_json_object(response: str) -> bool:
    try:
        return isinstance(json.loads(response), dict)
    except Exception:
        return False


def _prompt_category(prompt: str) -> str:
    text = prompt.lower()
    if "breaking news" in text or "controversy" in text:
        return "crisis"
    if "structured evidence" in text or "evidence" in text:
        return "rational"
    if "responsibility" in text or "relationship" in text or "empathy" in text:
        return "empathy"
    if "social" in text or "post" in text:
        return "social"
    return "unknown"


def validate_record_replay_order(manifest_rows: list[Mapping]) -> bool:
    by_rep: dict[str, list[Mapping]] = {}
    for row in manifest_rows:
        by_rep.setdefault(str(row["replicate_id"]), []).append(row)
    for replicate_id in ALLOWED_REPLICATE_IDS:
        rows = sorted(by_rep.get(replicate_id, []), key=lambda row: int(row["condition_order"]))
        if [row["exp_id"] for row in rows] != list(PILOT_CONDITION_IDS):
            return False
        if [row["router_role"] for row in rows] != ["recording", "replay", "replay"]:
            return False
    return True


def assert_no_replay_miss(rows: Iterable[Mapping]) -> None:
    for row in rows:
        if int(row.get("replay_miss_count", 0) or 0) != 0:
            raise PilotContractError("replay miss count must be zero")


def assert_mechanism_schema_alignment() -> None:
    missing = set(REQUIRED_SEMANTIC_SOURCE_FIELDS) - set(MECHANISM_RECORDS_FIELDS)
    if missing:
        raise PilotContractError(f"mechanism schema missing semantic fields: {sorted(missing)}")


def _detected_rows(rows: list[Mapping], label: str) -> list[Mapping]:
    seen: set[str] = set()
    detected = []
    for row in rows:
        agent_id = str(row.get("agent_id", ""))
        if not agent_id:
            raise PilotContractError(f"{label} row missing agent_id")
        if agent_id in seen:
            raise PilotContractError(f"duplicate agent_id in {label}: {agent_id}")
        seen.add(agent_id)
        if _truthy(row.get("clarification_detected_by_plan")):
            for field in REQUIRED_SEMANTIC_SOURCE_FIELDS:
                if field not in row:
                    raise PilotContractError(f"{label} row missing {field}")
                if field == "semantic_hypocrisy_perceived":
                    if not isinstance(row[field], bool):
                        raise PilotContractError(f"{label} {field} must be boolean")
                    continue
                value = _float(row[field])
                if field == "semantic_valence":
                    if value < -1.0 or value > 1.0:
                        raise PilotContractError(f"{label} {field} out of range")
                elif value < 0.0 or value > 1.0:
                    raise PilotContractError(f"{label} {field} out of range")
            detected.append(row)
    return detected


def matched_agent_ids(rational_rows: list[Mapping], empathy_rows: list[Mapping]) -> list[str]:
    rational_ids = {str(row["agent_id"]) for row in _detected_rows(rational_rows, "rational")}
    empathy_ids = {str(row["agent_id"]) for row in _detected_rows(empathy_rows, "empathy")}
    if rational_ids != empathy_ids:
        raise PilotContractError("matched Rational/Empathy reach sets differ")
    return sorted(rational_ids)


def compute_manipulation_pairs(
    replicate_id: str,
    rational_rows: list[Mapping],
    empathy_rows: list[Mapping],
) -> list[dict]:
    assert_mechanism_schema_alignment()
    if replicate_id not in ALLOWED_REPLICATE_IDS:
        raise PilotContractError("replicate_id must be R001 or R002")
    agent_ids = matched_agent_ids(rational_rows, empathy_rows)
    r_by_id = {str(row["agent_id"]): row for row in _detected_rows(rational_rows, "rational")}
    e_by_id = {str(row["agent_id"]): row for row in _detected_rows(empathy_rows, "empathy")}
    pairs: list[dict] = []
    for agent_id in agent_ids:
        r = r_by_id[agent_id]
        e = e_by_id[agent_id]
        pairs.append(
            {
                "replicate_id": replicate_id,
                "agent_id": agent_id,
                "D_evidence": (
                    _float(r["semantic_evidence_strength"])
                    - _float(e["semantic_evidence_strength"])
                ),
                "D_credibility": (
                    _float(r["semantic_credibility"])
                    - _float(e["semantic_credibility"])
                ),
                "D_empathy": (
                    _float(e["semantic_perceived_empathy"])
                    - _float(r["semantic_perceived_empathy"])
                ),
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
    by_rep: dict[str, list[Mapping]] = {}
    for row in pairs:
        by_rep.setdefault(str(row.get("replicate_id", "")), []).append(row)
    if set(by_rep) != set(ALLOWED_REPLICATE_IDS):
        raise PilotContractError("manipulation pairs must contain exactly R001 and R002")

    per_replicate: dict[str, dict] = {}
    all_blocks_direction_pass = True
    for replicate_id in ALLOWED_REPLICATE_IDS:
        rows = by_rep[replicate_id]
        dims = {}
        for dim in PRIMARY_FIELDS:
            values = [_float(row[dim]) for row in rows]
            mean_value = statistics.fmean(values)
            dims[dim] = {"mean": mean_value, "passes_direction": mean_value > 0}
            if mean_value <= 0:
                all_blocks_direction_pass = False
        per_replicate[replicate_id] = {"dimensions": dims}

    pooled = _summarize_pooled_pairs(pairs)
    pooled["per_replicate"] = per_replicate
    pooled["all_blocks_direction_pass"] = all_blocks_direction_pass
    pooled["DIRECTION_GATE"] = "PASS" if all_blocks_direction_pass else "FAIL"
    return pooled


def _summarize_pooled_pairs(pairs: list[Mapping]) -> dict:
    summary = {
        "pilot_id": PILOT_ID,
        "FORMAL_INFERENCE": False,
        "P_VALUES_COMPUTED": False,
        "PILOT_ONLY": True,
        "semantic_valence_role": "descriptive_only",
        "threshold_type": "engineering_construct_separation_floor",
        "engineering_floor": ENGINEERING_SEPARATION_FLOOR,
        "literature_derived": False,
        "statistical_significance_threshold": False,
        "dimensions": {},
    }
    weak = []
    for dim in PRIMARY_FIELDS:
        values = [_float(row[dim]) for row in pairs]
        expected_positive = [value > 0 for value in values]
        mean_value = statistics.fmean(values)
        summary["dimensions"][dim] = {
            "mean": mean_value,
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "expected_direction_proportion": sum(expected_positive) / len(values),
            "passes_direction": mean_value > 0,
            "passes_engineering_floor": mean_value >= ENGINEERING_SEPARATION_FLOOR,
        }
        if mean_value < ENGINEERING_SEPARATION_FLOOR:
            weak.append(dim)
    rational_topic_mean = statistics.fmean(
        _float(row["rational_topic_relevance"]) for row in pairs
    )
    empathy_topic_mean = statistics.fmean(
        _float(row["empathy_topic_relevance"]) for row in pairs
    )
    topic_group_mean_diff = abs(rational_topic_mean - empathy_topic_mean)
    summary["rational_topic_relevance_mean"] = rational_topic_mean
    summary["empathy_topic_relevance_mean"] = empathy_topic_mean
    summary["topic_relevance_group_mean_abs_diff"] = topic_group_mean_diff
    summary["topic_relevance_paired_abs_mean_diff_supplementary"] = statistics.fmean(
        abs(_float(row["rational_topic_relevance"]) - _float(row["empathy_topic_relevance"]))
        for row in pairs
    )
    summary["topic_relevance_warning"] = (
        "TOPIC_RELEVANCE_IMBALANCE"
        if topic_group_mean_diff > TOPIC_RELEVANCE_WARNING_THRESHOLD
        else ""
    )
    summary["rational_hypocrisy_perceived_rate"] = statistics.fmean(
        1.0 if row["rational_hypocrisy_perceived"] else 0.0 for row in pairs
    )
    summary["empathy_hypocrisy_perceived_rate"] = statistics.fmean(
        1.0 if row["empathy_hypocrisy_perceived"] else 0.0 for row in pairs
    )
    summary["MANIPULATION_STRENGTH"] = "WEAK" if weak else "PASS"
    summary["weak_dimensions"] = weak
    return summary


def fallback_counts_pass(rows: Iterable[Mapping]) -> bool:
    for row in rows:
        if int(row.get("semantic_fallback_used", 0) or 0) != 0:
            return False
        if int(row.get("plan_fallback_used", 0) or 0) != 0:
            return False
        if int(row.get("json_parse_failure", 0) or 0) != 0:
            return False
    return True


async def execute_real_pilot(output_dir: Path, activation_token: str | None) -> dict:
    readiness = assert_activation_ready(activation_token, output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    ledger = build_pilot_seed_ledger()
    manifest_rows = build_pilot_manifest_rows(ledger)
    write_seed_ledger_csv(ledger, output_dir / "seed_ledger.csv")
    _write_csv(output_dir / "pilot_manifest.csv", manifest_rows)
    (output_dir / "sanitized_model_config.json").write_text(
        json.dumps(sanitized_model_config(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    all_pairs: list[dict] = []
    replicate_summaries = []
    total_calls = 0
    status = "PASS"
    for ledger_row in ledger:
        block_summary = _execute_replicate_child(output_dir, ledger_row, activation_token)
        total_calls += int(block_summary.get("real_llm_calls", 0))
        replicate_summaries.append(block_summary)
        if block_summary["status"] != "PASS":
            status = "INCOMPLETE"
        pairs_path = output_dir / str(ledger_row["replicate_id"]) / "manipulation_pairs.csv"
        if block_summary["status"] == "PASS":
            all_pairs.extend(_read_csv_dicts(pairs_path))

    result = {
        "pilot_id": PILOT_ID,
        "REAL_LLM_CALLS": total_calls,
        "PILOT_STATUS": status,
        "FORMAL_INFERENCE": False,
        "P_VALUES_COMPUTED": False,
        "PILOT_ONLY": True,
        "OPTIONAL_STOPPING": False,
        "REPLACEMENT_REPLICATES": False,
        "replicates": replicate_summaries,
        "readiness": readiness,
    }
    if status == "PASS":
        summary = summarize_manipulation_by_block(all_pairs)
        _write_csv(output_dir / "manipulation_pairs.csv", all_pairs)
        (output_dir / "manipulation_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result["manipulation_summary"] = summary
        result["PROGRESSION_AUTHORIZED"] = (
            summary["DIRECTION_GATE"] == "PASS"
            and summary["MANIPULATION_STRENGTH"] == "PASS"
        )
    else:
        result["PROGRESSION_AUTHORIZED"] = False

    (output_dir / "pilot_execution_summary.json").write_text(
        json.dumps(_small_result_summary(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def _execute_replicate_child(
    output_dir: Path,
    ledger_row: Mapping,
    activation_token: str | None,
) -> dict:
    replicate_id = str(ledger_row["replicate_id"])
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(ledger_row["python_hash_seed"])
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(Path(__file__).resolve()),
        "--_run-replicate",
        replicate_id,
        "--output-dir",
        str(output_dir),
        "--activation-token",
        activation_token or "",
    ]
    proc = subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    block_dir = output_dir / replicate_id
    block_dir.mkdir(parents=True, exist_ok=True)
    (block_dir / "child_stdout_sanitized.log").write_text(
        sanitize_text(proc.stdout),
        encoding="utf-8",
    )
    (block_dir / "child_stderr_sanitized.log").write_text(
        sanitize_text(proc.stderr),
        encoding="utf-8",
    )
    summary_path = block_dir / "block_execution_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if not isinstance(summary, dict):
            raise PilotContractError(f"{replicate_id} block summary invalid")
        return summary
    return {
        "replicate_id": replicate_id,
        "attempt_count": 1,
        "status": "INCOMPLETE",
        "failure_message": f"child_exit_{proc.returncode}",
        "real_llm_calls": 0,
        "replay_miss_count": 0,
        "matched_agents": 0,
    }


def _read_csv_dicts(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


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
    lifecycle = block_dir / "replicate_lifecycle.jsonl"
    call_log = block_dir / "pilot_llm_calls.jsonl"
    summary_path = block_dir / "block_execution_summary.json"
    stdout_path = block_dir / "child_stdout_sanitized.log"
    stderr_path = block_dir / "child_stderr_sanitized.log"
    real_router = None
    audited: ValidatedAuditedRealRouter | None = None
    results: list[Mapping] = []
    pairs: list[dict] = []
    replay_miss_by_condition: dict[str, int] = {}
    status = "PASS"
    failure_message = ""

    try:
        block_dir.mkdir(parents=False, exist_ok=False)
        _append_lifecycle(lifecycle, replicate_id, "BLOCK_DIR_CREATED", "ok")
        call_log.write_text("", encoding="utf-8")
        _append_lifecycle(lifecycle, replicate_id, "CALL_LOG_CREATED", "ok")
        write_seed_ledger_csv([dict(ledger_row)], block_dir / "seed_ledger.csv")
        _append_lifecycle(lifecycle, replicate_id, "SEED_LEDGER_WRITTEN", "ok")
        (block_dir / "sanitized_model_config.json").write_text(
            json.dumps(sanitized_model_config(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _append_lifecycle(lifecycle, replicate_id, "MODEL_CONFIG_WRITTEN", "ok")
        configs = select_pilot_conditions()
        (block_dir / "pilot_condition_manifest.json").write_text(
            json.dumps(
                [
                    row
                    for row in build_pilot_manifest_rows([dict(ledger_row)])
                    if row["replicate_id"] == replicate_id
                ],
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _append_lifecycle(lifecycle, replicate_id, "CONDITION_MANIFEST_WRITTEN", "ok")
        if os.environ.get("PYTHONHASHSEED") != str(ledger_row["python_hash_seed"]):
            raise PilotContractError("PYTHONHASHSEED does not match ledger")
        _append_lifecycle(lifecycle, replicate_id, "PYTHONHASHSEED_CHECKED", "ok")
        _append_lifecycle(lifecycle, replicate_id, "REAL_ROUTER_BUILD_STARTED", "ok")
        real_router = router_builder(int(ledger_row["requested_llm_seed"]))
        _append_lifecycle(lifecycle, replicate_id, "REAL_ROUTER_BUILD_COMPLETED", "ok")
        audited = ValidatedAuditedRealRouter(
            real_router,
            pilot_id=PILOT_ID,
            replicate_id=replicate_id,
            requested_llm_seed=int(ledger_row["requested_llm_seed"]),
            call_log_path=call_log,
            lifecycle_path=lifecycle,
        )

        cache: dict = {}
        for config in configs:
            if config.is_control:
                router = PilotRecordingRouter(audited, config.exp_id)
                result = await _run_with_patch(config, override_router=router)
                cache.update(router.cache)
                result["run_audit"] = {
                    "router_role": "recording",
                    "recording_cache_size": len(router.cache),
                    "replay_miss_count": "",
                }
            else:
                router = PilotReplayRouter(
                    audited,
                    cache,
                    replay_until_tick=6,
                    exp_id=config.exp_id,
                )
                result = await _run_with_patch(config, override_router=router)
                if router.miss_count != 0:
                    raise PilotContractError("replay miss count must be zero")
                result["run_audit"] = {
                    "router_role": "replay",
                    "recording_cache_size": len(cache),
                    "replay_miss_count": router.miss_count,
                }
                replay_miss_by_condition[config.exp_id] = router.miss_count
            results.append(result)

        _validate_block_outputs(results, replicate_id)
        _validate_preclarification_alignment(results)
        write_agent_records_csv(results, str(block_dir / "agent_records.csv"))
        write_mechanism_records_csv(results, str(block_dir / "mechanism_records.csv"))
        write_clarification_exposure_csv(results, str(block_dir / "clarification_exposure.csv"))
        write_trajectories_csv(results, str(block_dir / "trajectories.csv"))
        pairs = _pairs_from_results(replicate_id, results)
        _write_csv(block_dir / "manipulation_pairs.csv", pairs)
    except Exception as exc:
        status = "INCOMPLETE"
        failure_message = type(exc).__name__
        if block_dir.exists():
            stderr_path.write_text(sanitize_text(type(exc).__name__) + "\n", encoding="utf-8")
    finally:
        if real_router is not None:
            try:
                await _close_router_resource(real_router)
            except Exception as exc:
                status = "INCOMPLETE"
                failure_message = type(exc).__name__
                if block_dir.exists():
                    stderr_path.write_text(sanitize_text(type(exc).__name__) + "\n", encoding="utf-8")

    if block_dir.exists():
        if not stdout_path.exists():
            stdout_path.write_text("", encoding="utf-8")
        if not stderr_path.exists():
            stderr_path.write_text("", encoding="utf-8")
        summary = {
            "pilot_id": PILOT_ID,
            "replicate_id": replicate_id,
            "attempt_count": 1,
            "status": status,
            "failure_message": failure_message,
            "real_llm_calls": audited.call_count if audited is not None else 0,
            "replay_miss_count": sum(replay_miss_by_condition.values()),
            "matched_agents": len({row["agent_id"] for row in pairs}),
            "FORMAL_INFERENCE": False,
            "P_VALUES_COMPUTED": False,
            "PILOT_ONLY": True,
            "manipulation_pairs": pairs,
        }
        public_summary = dict(summary)
        public_summary.pop("manipulation_pairs", None)
        _write_block_summary(summary_path, public_summary)
        return summary

    return {
        "pilot_id": PILOT_ID,
        "replicate_id": replicate_id,
        "attempt_count": 1,
        "status": "INCOMPLETE",
        "failure_message": failure_message or "BlockDirectoryNotCreated",
        "real_llm_calls": 0,
        "replay_miss_count": 0,
        "matched_agents": 0,
        "FORMAL_INFERENCE": False,
        "P_VALUES_COMPUTED": False,
        "PILOT_ONLY": True,
    }

def _validate_block_outputs(results: list[Mapping], replicate_id: str) -> None:
    if len(results) != len(PILOT_CONDITION_IDS):
        raise PilotContractError(f"{replicate_id} missing pilot condition results")
    if [row.get("exp_id") for row in results] != list(PILOT_CONDITION_IDS):
        raise PilotContractError(f"{replicate_id} condition order mismatch")
    total_mechanism = sum(len(row.get("mechanism_records", [])) for row in results)
    if total_mechanism != 1800:
        raise PilotContractError(f"{replicate_id} mechanism row count mismatch: {total_mechanism}")
    for result in results:
        if len(result.get("mechanism_records", [])) != 600:
            raise PilotContractError(f"{result.get('exp_id')} mechanism rows != 600")
        if not fallback_counts_pass(result.get("mechanism_records", [])):
            raise PilotContractError(f"{result.get('exp_id')} fallback gate failed")


def _validate_preclarification_alignment(results: list[Mapping]) -> None:
    by_id = {row["exp_id"]: row for row in results}
    rational = by_id["Rational-Hub-Immediate"]["mechanism_records"]
    empathy = by_id["Empathy-Hub-Immediate"]["mechanism_records"]
    fields = (
        "trust_final",
        "attitude_att",
        "subjective_norm_sn",
        "pbc",
        "crisis_memory",
        "repair_memory",
        "purchase_intention",
    )
    r_keyed = {
        (int(row["tick"]), row["agent_id"]): row
        for row in rational
        if int(row["tick"]) == 5
    }
    e_keyed = {
        (int(row["tick"]), row["agent_id"]): row
        for row in empathy
        if int(row["tick"]) == 5
    }
    if set(r_keyed) != set(e_keyed):
        raise PilotContractError("PRECLARIFICATION_ALIGNMENT_FAILURE")
    for key, r_row in r_keyed.items():
        e_row = e_keyed[key]
        for field in fields:
            if r_row.get(field) != e_row.get(field):
                raise PilotContractError("PRECLARIFICATION_ALIGNMENT_FAILURE")


def _pairs_from_results(replicate_id: str, results: list[Mapping]) -> list[dict]:
    by_id = {row["exp_id"]: row for row in results}
    rational_rows = [
        row
        for row in by_id["Rational-Hub-Immediate"]["mechanism_records"]
        if int(row["tick"]) == 6
    ]
    empathy_rows = [
        row
        for row in by_id["Empathy-Hub-Immediate"]["mechanism_records"]
        if int(row["tick"]) == 6
    ]
    return compute_manipulation_pairs(replicate_id, rational_rows, empathy_rows)


def _small_result_summary(result: Mapping) -> dict:
    summary = {
        "pilot_id": PILOT_ID,
        "PILOT_STATUS": result.get("PILOT_STATUS"),
        "REAL_LLM_CALLS": result.get("REAL_LLM_CALLS"),
        "FORMAL_INFERENCE": False,
        "P_VALUES_COMPUTED": False,
        "PILOT_ONLY": True,
        "PROGRESSION_AUTHORIZED": result.get("PROGRESSION_AUTHORIZED", False),
        "replicates": [
            {
                "replicate_id": row.get("replicate_id"),
                "attempt_count": row.get("attempt_count"),
                "status": row.get("status"),
                "real_llm_calls": row.get("real_llm_calls"),
                "replay_miss_count": row.get("replay_miss_count"),
                "matched_agents": row.get("matched_agents"),
            }
            for row in result.get("replicates", [])
        ],
    }
    if "manipulation_summary" in result:
        summary["manipulation_summary"] = result["manipulation_summary"]
    return summary


def _truthy(value) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _float(value) -> float:
    try:
        number = float(value)
    except Exception as exc:
        raise PilotContractError(f"non-numeric manipulation value: {type(exc).__name__}") from exc
    if not math.isfinite(number):
        raise PilotContractError("non-finite manipulation value")
    return number


def assert_real_execution_authorized(args) -> None:
    if getattr(args, "execute_real", False) and getattr(args, "activation_token", "") != ACTIVATION_TOKEN:
        raise PilotContractError(REAL_MODE_REJECTION)
    if getattr(args, "_run_replicate", "") and getattr(args, "activation_token", "") != ACTIVATION_TOKEN:
        raise PilotContractError(REAL_MODE_REJECTION)


def preflight() -> dict:
    require_pilot_credential()
    ledger = build_pilot_seed_ledger()
    manifest = build_pilot_manifest_rows(ledger)
    if not validate_record_replay_order(manifest):
        raise PilotContractError("record/replay order invalid")
    return {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "replicate_ids": list(ALLOWED_REPLICATE_IDS),
        "condition_ids": list(PILOT_CONDITION_IDS),
        "sanitized_model_config": sanitized_model_config(),
        "REAL_LLM_CALLS": False,
    }


def run_offline_self_test() -> dict:
    ledger = build_pilot_seed_ledger()
    manifest = build_pilot_manifest_rows(ledger)
    if len(ledger) != 2 or tuple(row["replicate_id"] for row in ledger) != ALLOWED_REPLICATE_IDS:
        raise PilotContractError("ledger identity mismatch")
    if len(manifest) != 6 or not validate_record_replay_order(manifest):
        raise PilotContractError("pilot manifest mismatch")
    rational = [
        _semantic_input_row("A001", 0.80, 0.75, 0.20, 0.25, -0.20, 0.91, False),
        _semantic_input_row("A002", 0.70, 0.65, 0.30, 0.20, 0.10, 0.88, True),
    ]
    empathy = [
        _semantic_input_row("A001", 0.45, 0.50, 0.70, 0.62, -0.40, 0.86, True),
        _semantic_input_row("A002", 0.50, 0.48, 0.66, 0.58, 0.20, 0.84, True),
    ]
    pairs = []
    for replicate_id in ALLOWED_REPLICATE_IDS:
        pairs.extend(compute_manipulation_pairs(replicate_id, rational, empathy))
    summary = summarize_manipulation_by_block(pairs)
    if summary["MANIPULATION_STRENGTH"] != "PASS":
        raise PilotContractError("offline manipulation self-test should pass")
    if summary["DIRECTION_GATE"] != "PASS":
        raise PilotContractError("offline direction gate should pass")
    if not fallback_counts_pass(
        [
            {"semantic_fallback_used": 0, "plan_fallback_used": 0, "json_parse_failure": 0},
            {"semantic_fallback_used": 0, "plan_fallback_used": 0, "json_parse_failure": 0},
        ]
    ):
        raise PilotContractError("fallback count logic failed")
    return summary


def _semantic_input_row(
    agent_id: str,
    evidence: float,
    credibility: float,
    perceived_empathy: float,
    arousal: float,
    valence: float,
    topic: float,
    hypocrisy: bool,
) -> dict:
    return {
        "agent_id": agent_id,
        "clarification_detected_by_plan": True,
        "semantic_evidence_strength": evidence,
        "semantic_credibility": credibility,
        "semantic_perceived_empathy": perceived_empathy,
        "semantic_valence": valence,
        "semantic_arousal": arousal,
        "semantic_topic_relevance": topic,
        "semantic_hypocrisy_perceived": hypocrisy,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--preflight-real", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline-test", action="store_true")
    parser.add_argument("--execute-real", action="store_true")
    parser.add_argument("--activation-token", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--_run-replicate", default="")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        assert_real_execution_authorized(args)
        output_dir = Path(args.output_dir) if args.output_dir else PILOT_OUTPUT_ROOT
        if args.preflight_real:
            print(json.dumps(assert_activation_ready(args.activation_token, output_dir), sort_keys=True))
            return 0
        if args._run_replicate:
            ledger = {
                row["replicate_id"]: row
                for row in build_pilot_seed_ledger()
            }
            if args._run_replicate not in ledger:
                raise PilotContractError("replicate_id must be R001 or R002")
            summary = asyncio.run(_execute_replicate_block(output_dir, ledger[args._run_replicate]))
            return 0 if summary["status"] == "PASS" else 1
        if args.execute_real:
            result = asyncio.run(execute_real_pilot(output_dir, args.activation_token))
            print(json.dumps(_small_result_summary(result), sort_keys=True))
            return 0 if result["PILOT_STATUS"] == "PASS" else 1
        if args.preflight:
            print(json.dumps(preflight(), sort_keys=True))
            return 0
        if args.dry_run:
            output_dir = Path(args.output_dir) if args.output_dir else Path(tempfile.mkdtemp())
            print(json.dumps(write_offline_dry_run_artifacts(output_dir), sort_keys=True))
            return 0
        if args.offline_test:
            print(json.dumps(run_offline_self_test(), sort_keys=True))
            return 0
        raise PilotContractError(REAL_MODE_REJECTION)
    except (PilotContractError, ReplicationStartupError) as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
