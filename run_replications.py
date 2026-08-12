"""TASK_005 serial replication parent runner and artifact validation.

Provides deterministic seed-ledger orchestration, serial child subprocess
execution, resume/failure evidence management, and read-only block artifact
validation.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from replication_config import (
    BLOCK_FAILURE_POLICY,
    CACHE_SCOPE,
    CONDITION_COUNT,
    CONTROL_EXP_ID,
    EXECUTION_MODE,
    EXECUTION_ORDER,
    LEDGER_FIELDS,
    LLM_SEED_SUPPORTED_VALUES,
    LATEST_POLICY,
    MATRIX_VERSION,
    MAX_PARALLEL_BLOCKS,
    METRICS_SCHEMA_VERSION,
    REPLICATION_SCHEMA_VERSION,
    SEED_DERIVATION_VERSION,
    SEED_MAX,
    build_seed_ledger,
    read_seed_ledger_csv,
    write_seed_ledger_csv,
)


BLOCK_STATES = (
    "planned",
    "running",
    "succeeded",
    "failed",
    "invalid",
    "interrupted",
)

ALLOWED_TRANSITIONS = frozenset(
    {
        ("planned", "running"),
        ("running", "succeeded"),
        ("running", "failed"),
        ("running", "invalid"),
        ("running", "interrupted"),
        ("failed", "running"),
        ("invalid", "running"),
        ("interrupted", "running"),
    }
)

MANIFEST_FIELDS = (
    "replication_id",
    "replicate_id",
    "replicate_index",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "python_hash_seed",
    "status",
    "attempt_count",
    "block_dir",
    "started_at",
    "finished_at",
    "subprocess_exit_code",
    "condition_success_count",
    "condition_error_count",
    "postprocess_error_count",
    "replay_alignment_violated",
    "network_status",
    "validation_passed",
    "failure_stage",
    "failure_type",
    "failure_message",
)

REPLICATION_METADATA_FIELDS = (
    "schema_version",
    "replication_id",
    "replicate_id",
    "replicate_index",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "python_hash_seed",
    "cache_scope",
    "execution_mode",
    "latest_policy",
    "engineering_acceptance_only",
)

SUBPROCESS_ENV_CONTRACT = (
    "PYTHONUTF8=1",
    "PYTHONIOENCODING=utf-8",
    "PYTHONHASHSEED=<ledger python_hash_seed>",
    "MPLBACKEND=Agg",
    "TOKENIZERS_PARALLELISM=false",
)

DETERMINISTIC_MOCK_ENV_CONTRACT = (
    "HF_HUB_OFFLINE=1",
    "TRANSFORMERS_OFFLINE=1",
    "HF_DATASETS_OFFLINE=1",
    "HF_HUB_DISABLE_TELEMETRY=1",
)

RUN_EXPERIMENTS_ARGS = (
    "--replication-id",
    "--replicate-id",
    "--replicate-index",
    "--simulation-seed",
    "--requested-llm-seed",
    "--llm-seed-supported",
    "--python-hash-seed",
    "--output-dir",
    "--no-latest",
    "--llm-mode",
)

LLM_MODES = ("real", "deterministic-mock")

V4_FIELDS = (
    "final_trust_gain_vs_control",
    "post_scandal_auc_gain_vs_control",
    "local_trust_effect_did_3",
    "early_trust_auc_gain_5",
    "early_trust_gain_slope_5",
    "secondary_harm_depth",
    "negative_gain_tick_count",
)

SUMMARY_REQUIRED_FIELDS = (
    "exp_id",
    "content_factor",
    "channel_factor",
    "timing_factor",
    "is_control",
    "trust_gain_vs_control",
    *V4_FIELDS,
)

RANKING_SENSITIVITY_FIELDS = (
    "weight_final",
    "weight_auc",
    "weight_local",
    "exp_id",
    "weighted_score",
    "rank",
    "top1_credit",
)

RANKING_ROBUSTNESS_FIELDS = (
    "exp_id",
    "top1_share",
    "mean_rank",
    "median_rank",
    "best_rank",
    "worst_rank",
)

FIGURE_FILES = (
    "fig1_main_effects.png",
    "fig2_interactions.png",
    "fig3_pareto.png",
    "fig4_ranking.png",
    "fig5_clarification_diagnosis.png",
    "fig6_ranking_sensitivity.png",
)

BATCH_METADATA_FIELDS = (
    "schema_version",
    "replication_id",
    "created_at",
    "updated_at",
    "master_seed",
    "num_replicates",
    "llm_mode",
    "llm_seed_supported",
    "provider_model",
    "provider_system_fingerprint",
    "seed_derivation_version",
    "matrix_version",
    "metrics_schema_version",
    "condition_count",
    "control_exp_id",
    "cache_scope",
    "execution_mode",
    "max_parallel_blocks",
    "latest_policy",
    "block_failure_policy",
    "engineering_acceptance_only",
)

FAILURE_FIELDS = (
    "replication_id",
    "replicate_id",
    "replicate_index",
    "attempt_index",
    "status",
    "subprocess_exit_code",
    "failure_stage",
    "failure_type",
    "failure_message",
    "failure_dir",
    "recorded_at",
)

OFFLINE_ENV_KEYS = (
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "HF_DATASETS_OFFLINE",
    "HF_HUB_DISABLE_TELEMETRY",
)

PROJECT_ROOT = Path(__file__).resolve().parent


class RunnerStartupError(ValueError):
    """Raised for parent-runner CLI, path, ledger, or resume contract errors."""


class RunnerRuntimeError(RuntimeError):
    """Raised for runtime artifact movement or write failures."""


def parse_runner_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--replication-id", required=True)
    parser.add_argument("--master-seed", required=True, type=int)
    parser.add_argument("--num-replicates", required=True, type=int)
    parser.add_argument("--llm-mode", required=True, choices=LLM_MODES)
    parser.add_argument(
        "--llm-seed-supported",
        required=True,
        choices=LLM_SEED_SUPPORTED_VALUES,
    )
    parser.add_argument("--provider-model", default="")
    parser.add_argument("--provider-system-fingerprint", default="")
    parser.add_argument("--output-root", default="results/replications")
    parser.add_argument("--python-executable", required=True)
    parser.add_argument("--max-parallel", type=int, default=1)
    parser.add_argument("--retry-failed", action="store_true", default=False)
    return parser.parse_args(argv)


def build_runner_request(args) -> dict:
    return _build_runner_request(args, allow_formal_real=False)


def _build_runner_request(args, *, allow_formal_real: bool) -> dict:
    replication_id = _validate_replication_id(args.replication_id)
    master_seed = _require_non_bool_int("master_seed", args.master_seed, minimum=0)
    num_replicates = _require_non_bool_int(
        "num_replicates",
        args.num_replicates,
        minimum=1,
    )
    max_parallel = _require_non_bool_int("max_parallel", args.max_parallel)
    if max_parallel != 1:
        raise RunnerStartupError("max_parallel must be exactly 1")
    if args.llm_mode not in LLM_MODES:
        raise RunnerStartupError("llm_mode is invalid")
    if (
        replication_id.startswith("task005-formal-")
        and args.llm_mode == "real"
        and not allow_formal_real
    ):
        raise RunnerStartupError(
            "formal real execution requires dedicated authorized launcher"
        )
    if args.llm_seed_supported not in LLM_SEED_SUPPORTED_VALUES:
        raise RunnerStartupError("llm_seed_supported is invalid")
    if not isinstance(args.provider_model, str):
        raise RunnerStartupError("provider_model must be a string")
    if not isinstance(args.provider_system_fingerprint, str):
        raise RunnerStartupError("provider_system_fingerprint must be a string")

    python_executable = Path(_require_non_empty_string(
        "python_executable",
        args.python_executable,
    ))
    if not python_executable.is_file():
        raise RunnerStartupError("python_executable must point to an existing file")

    output_root_raw = _require_non_empty_string("output_root", args.output_root)
    output_root = Path(output_root_raw)
    if not output_root.is_absolute():
        output_root = PROJECT_ROOT / output_root

    return {
        "replication_id": replication_id,
        "master_seed": master_seed,
        "num_replicates": num_replicates,
        "llm_mode": args.llm_mode,
        "llm_seed_supported": args.llm_seed_supported,
        "provider_model": args.provider_model,
        "provider_system_fingerprint": args.provider_system_fingerprint,
        "output_root": str(output_root.resolve()),
        "python_executable": str(python_executable.resolve()),
        "max_parallel": max_parallel,
        "retry_failed": bool(args.retry_failed),
        "project_root": str(PROJECT_ROOT),
    }


def build_child_argv(
    *,
    python_executable,
    project_root,
    replication_id,
    ledger_row,
    output_dir,
    llm_mode,
) -> list[str]:
    script = Path(project_root) / "run_experiments.py"
    return [
        str(python_executable),
        "-X",
        "utf8",
        str(script),
        "--replication-id",
        str(replication_id),
        "--replicate-id",
        str(ledger_row["replicate_id"]),
        "--replicate-index",
        str(ledger_row["replicate_index"]),
        "--simulation-seed",
        str(ledger_row["simulation_seed"]),
        "--requested-llm-seed",
        str(ledger_row["requested_llm_seed"]),
        "--llm-seed-supported",
        str(ledger_row["llm_seed_supported"]),
        "--python-hash-seed",
        str(ledger_row["python_hash_seed"]),
        "--output-dir",
        str(output_dir),
        "--no-latest",
        "--llm-mode",
        str(llm_mode),
    ]


def build_child_env(
    ledger_row,
    *,
    llm_mode,
    base_env=None,
    formal_activation_context: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONHASHSEED": str(ledger_row["python_hash_seed"]),
        "MPLBACKEND": "Agg",
        "TOKENIZERS_PARALLELISM": "false",
    })
    if llm_mode == "deterministic-mock":
        env.update({
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        })
    elif llm_mode == "real":
        for key in OFFLINE_ENV_KEYS:
            env.pop(key, None)
        if formal_activation_context is not None:
            env["TASK005_FORMAL_AUTHORIZATION_SHA256"] = str(
                formal_activation_context["authorization_artifact_sha256"]
            )
            env["TASK005_FORMAL_ACTIVATION_CODE_HEAD"] = str(
                formal_activation_context["activation_code_head"]
            )
            env["TASK005_FORMAL_AUTHORIZATION_PATH"] = str(
                formal_activation_context["authorization_artifact_path"]
            )
            env["TASK005_FORMAL_LAUNCH_CONTRACT_SHA256"] = str(
                formal_activation_context["launch_contract_sha256"]
            )
    else:
        raise RunnerStartupError("llm_mode is invalid")
    return env


def run_replication_batch(
    request: dict,
    *,
    before_child_start=None,
    child_runner=None,
    block_validator=None,
    formal_activation_context: Mapping[str, Any] | None = None,
) -> int:
    try:
        req = _validate_runner_request_dict(
            request,
            allow_formal_real=formal_activation_context is not None,
        )
        if before_child_start is not None:
            req["_before_child_start"] = before_child_start
        if child_runner is not None:
            req["_child_runner"] = child_runner
        if block_validator is not None:
            req["_block_validator"] = block_validator
        if formal_activation_context is not None:
            req["_formal_activation_context"] = dict(formal_activation_context)
        batch_dir = Path(req["output_root"]) / req["replication_id"]
        state = _load_or_initialize_batch(req, batch_dir)
        return _run_batch_state(req, state)
    except RunnerStartupError as exc:
        print(f"ERROR: {_sanitize_text(str(exc))}")
        return 2
    except Exception as exc:
        print(f"ERROR: {_sanitize_text(type(exc).__name__)}")
        return 1


def main(argv=None) -> int:
    try:
        args = parse_runner_args(argv)
        request = build_runner_request(args)
    except SystemExit:
        raise
    except RunnerStartupError as exc:
        print(f"ERROR: {_sanitize_text(str(exc))}")
        return 2
    except Exception as exc:
        print(f"ERROR: {_sanitize_text(str(exc))}")
        return 2
    return run_replication_batch(request)


def _validate_replication_id(value) -> str:
    text = _require_non_empty_string("replication_id", value).strip()
    if not text:
        raise RunnerStartupError("replication_id must be non-empty")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", text):
        raise RunnerStartupError("replication_id contains invalid characters")
    if text == "." or ".." in text or Path(text).is_absolute():
        raise RunnerStartupError("replication_id must not contain path semantics")
    return text


def _require_non_empty_string(name: str, value) -> str:
    if not isinstance(value, str) or not value:
        raise RunnerStartupError(f"{name} must be a non-empty string")
    return value


def _require_non_bool_int(name: str, value, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RunnerStartupError(f"{name} must be a non-boolean integer")
    if minimum is not None and value < minimum:
        raise RunnerStartupError(f"{name} must be >= {minimum}")
    return value


def _validate_runner_request_dict(
    request: Mapping[str, Any],
    *,
    allow_formal_real: bool = False,
) -> dict:
    if not isinstance(request, Mapping):
        raise RunnerStartupError("request must be a mapping")
    args = argparse.Namespace(**dict(request))
    for name in (
        "replication_id", "master_seed", "num_replicates", "llm_mode",
        "llm_seed_supported", "provider_model", "provider_system_fingerprint",
        "output_root", "python_executable", "max_parallel",
    ):
        if not hasattr(args, name):
            raise RunnerStartupError(f"request missing {name}")
    if not hasattr(args, "retry_failed"):
        args.retry_failed = False
    return _build_runner_request(args, allow_formal_real=allow_formal_real)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _batch_metadata_for_request(request: Mapping[str, Any], *, created_at: str) -> dict:
    values = {
        "schema_version": REPLICATION_SCHEMA_VERSION,
        "replication_id": request["replication_id"],
        "created_at": created_at,
        "updated_at": _utc_now(),
        "master_seed": request["master_seed"],
        "num_replicates": request["num_replicates"],
        "llm_mode": request["llm_mode"],
        "llm_seed_supported": request["llm_seed_supported"],
        "provider_model": request["provider_model"],
        "provider_system_fingerprint": request["provider_system_fingerprint"],
        "seed_derivation_version": SEED_DERIVATION_VERSION,
        "matrix_version": MATRIX_VERSION,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "condition_count": CONDITION_COUNT,
        "control_exp_id": CONTROL_EXP_ID,
        "cache_scope": CACHE_SCOPE,
        "execution_mode": EXECUTION_MODE,
        "max_parallel_blocks": MAX_PARALLEL_BLOCKS,
        "latest_policy": LATEST_POLICY,
        "block_failure_policy": BLOCK_FAILURE_POLICY,
        "engineering_acceptance_only": request["llm_mode"] == "deterministic-mock",
    }
    return {field: values[field] for field in BATCH_METADATA_FIELDS}


def _load_or_initialize_batch(request: dict, batch_dir: Path) -> dict:
    if batch_dir.exists():
        return _load_existing_batch(request, batch_dir)
    batch_dir.mkdir(parents=True, exist_ok=False)
    for name in ("blocks", "work", "failures"):
        (batch_dir / name).mkdir()
    rows = build_seed_ledger(
        request["master_seed"],
        request["num_replicates"],
        llm_seed_supported=request["llm_seed_supported"],
        provider_model=request["provider_model"],
        provider_system_fingerprint=request["provider_system_fingerprint"],
    )
    write_seed_ledger_csv(rows, batch_dir / "seed_ledger.csv")
    metadata = _batch_metadata_for_request(request, created_at=_utc_now())
    _atomic_write_json_object(batch_dir / "replication_metadata.json", metadata)
    manifest = [_planned_manifest_row(request["replication_id"], row) for row in rows]
    _atomic_write_csv(batch_dir / "replicate_manifest.csv", MANIFEST_FIELDS, manifest)
    _atomic_write_csv(batch_dir / "replication_failures.csv", FAILURE_FIELDS, [])
    return {
        "batch_dir": batch_dir,
        "ledger": rows,
        "metadata": metadata,
        "manifest": manifest,
        "failures": [],
    }


def _load_existing_batch(request: dict, batch_dir: Path) -> dict:
    if not batch_dir.is_dir():
        raise RunnerStartupError("batch path exists but is not a directory")
    for rel in (
        "seed_ledger.csv",
        "replicate_manifest.csv",
        "replication_metadata.json",
        "replication_failures.csv",
    ):
        if not (batch_dir / rel).is_file():
            raise RunnerStartupError(f"existing batch missing {rel}")
    for rel in ("blocks", "work", "failures"):
        if not (batch_dir / rel).is_dir():
            raise RunnerStartupError(f"existing batch missing {rel}/")
    ledger = read_seed_ledger_csv(batch_dir / "seed_ledger.csv")
    _verify_ledger_matches_request(ledger, request)
    metadata = _read_json_file(batch_dir / "replication_metadata.json")
    _verify_batch_metadata_matches_request(metadata, request)
    manifest = _read_csv_file(batch_dir / "replicate_manifest.csv", MANIFEST_FIELDS)
    failures_path = batch_dir / "replication_failures.csv"
    failures = _read_csv_file(failures_path, FAILURE_FIELDS)
    return {
        "batch_dir": batch_dir,
        "ledger": ledger,
        "metadata": metadata,
        "manifest": manifest,
        "failures": failures,
    }


def _planned_manifest_row(replication_id: str, ledger_row: Mapping[str, Any]) -> dict:
    return {
        "replication_id": replication_id,
        "replicate_id": ledger_row["replicate_id"],
        "replicate_index": ledger_row["replicate_index"],
        "simulation_seed": ledger_row["simulation_seed"],
        "requested_llm_seed": ledger_row["requested_llm_seed"],
        "llm_seed_supported": ledger_row["llm_seed_supported"],
        "python_hash_seed": ledger_row["python_hash_seed"],
        "status": "planned",
        "attempt_count": 0,
        "block_dir": f"blocks/{ledger_row['replicate_id']}",
        "started_at": "",
        "finished_at": "",
        "subprocess_exit_code": "",
        "condition_success_count": 0,
        "condition_error_count": 0,
        "postprocess_error_count": 0,
        "replay_alignment_violated": False,
        "network_status": "",
        "validation_passed": False,
        "failure_stage": "",
        "failure_type": "",
        "failure_message": "",
    }


def _run_batch_state(request: Mapping[str, Any], state: Mapping[str, Any]) -> int:
    batch_dir = Path(state["batch_dir"])
    ledger_rows = list(state["ledger"])
    manifest_rows = list(state["manifest"])
    failures = list(state["failures"])
    metadata = dict(state["metadata"])
    row_by_id = _validate_manifest_against_ledger(manifest_rows, ledger_rows, request)

    exit_code = 0
    for ledger_row in ledger_rows:
        replicate_id = str(ledger_row["replicate_id"])
        manifest_row = row_by_id[replicate_id]
        try:
            status = str(manifest_row.get("status", ""))
            if status == "succeeded":
                if _handle_succeeded_resume(
                    request,
                    batch_dir,
                    manifest_rows,
                    manifest_row,
                    ledger_row,
                    failures,
                ):
                    exit_code = 1
                continue
            if status == "running":
                _handle_interrupted_resume(batch_dir, manifest_rows, manifest_row, failures)
                if not request.get("retry_failed", False):
                    exit_code = 1
                    continue
            elif status in ("failed", "invalid", "interrupted"):
                if not request.get("retry_failed", False):
                    exit_code = 1
                    continue
            elif status != "planned":
                raise RunnerStartupError(f"invalid manifest status for {replicate_id}")

            before_child_start = request.get("_before_child_start")
            if before_child_start is not None:
                try:
                    before_child_start(
                        request=request,
                        batch_dir=batch_dir,
                        manifest_row=manifest_row,
                        ledger_row=ledger_row,
                    )
                except RunnerStartupError:
                    raise
                except Exception as exc:
                    raise RunnerStartupError(
                        "before_child_start gate failed: "
                        f"{type(exc).__name__}"
                    ) from exc

            result_status = _run_one_attempt(
                request,
                batch_dir,
                manifest_rows,
                manifest_row,
                ledger_row,
                failures,
            )
            if result_status != "succeeded":
                exit_code = 1
        except RunnerStartupError:
            raise
        except Exception as exc:
            _record_runtime_failure(
                batch_dir,
                manifest_rows,
                manifest_row,
                failures,
                exc,
            )
            exit_code = 1

    metadata["updated_at"] = _utc_now()
    _atomic_write_json_object(batch_dir / "replication_metadata.json", metadata)
    return exit_code


def _handle_succeeded_resume(
    request: Mapping[str, Any],
    batch_dir: Path,
    manifest_rows: list[dict],
    manifest_row: dict,
    ledger_row: Mapping[str, Any],
    failures: list[dict],
) -> bool:
    block_dir = batch_dir / str(manifest_row["block_dir"])
    attempt_index = _parse_manifest_int(manifest_row, "attempt_count")
    if attempt_index <= 0:
        raise RunnerStartupError("manifest attempt_count must be positive for succeeded blocks")
    exit_code = _parse_manifest_int(manifest_row, "subprocess_exit_code")
    if exit_code != 0:
        raise RunnerStartupError("succeeded block subprocess_exit_code must be 0")
    block_validator = request.get("_block_validator", validate_block_artifacts)
    validation = block_validator(
        block_dir,
        ledger_row,
        subprocess_exit_code=exit_code,
    )
    if validation.get("validation_passed") is True and validation.get("status") == "succeeded":
        _apply_validation_to_manifest(manifest_row, validation, exit_code)
        _atomic_write_csv(batch_dir / "replicate_manifest.csv", MANIFEST_FIELDS, manifest_rows)
        return False

    _apply_validation_to_manifest(manifest_row, validation, exit_code)
    manifest_row["finished_at"] = _utc_now()
    failure_dir = _preserve_failure_attempt(
        batch_dir,
        str(ledger_row["replicate_id"]),
        attempt_index,
        source_dir=block_dir if block_dir.exists() else None,
        message=str(validation.get("failure_message", "")),
    )
    _append_failure(
        batch_dir,
        failures,
        manifest_row,
        attempt_index=attempt_index,
        failure_dir=failure_dir,
    )
    _atomic_write_csv(batch_dir / "replicate_manifest.csv", MANIFEST_FIELDS, manifest_rows)
    if request.get("retry_failed", False):
        return _run_one_attempt(
            request,
            batch_dir,
            manifest_rows,
            manifest_row,
            ledger_row,
            failures,
        ) != "succeeded"

    return True


def _handle_interrupted_resume(
    batch_dir: Path,
    manifest_rows: list[dict],
    manifest_row: dict,
    failures: list[dict],
) -> None:
    attempt_index = _parse_manifest_int(manifest_row, "attempt_count")
    if attempt_index <= 0:
        raise RunnerStartupError("manifest attempt_count must be positive for running blocks")
    replicate_id = manifest_row["replicate_id"]
    work_dir = _work_attempt_dir(batch_dir, replicate_id, attempt_index)
    failure_dir = _preserve_failure_attempt(
        batch_dir,
        str(replicate_id),
        attempt_index,
        source_dir=work_dir if work_dir.exists() else None,
        message="previous running attempt was interrupted",
    )
    manifest_row["status"] = "interrupted"
    manifest_row["finished_at"] = _utc_now()
    manifest_row["validation_passed"] = False
    manifest_row["failure_stage"] = "subprocess"
    manifest_row["failure_type"] = "Interrupted"
    manifest_row["failure_message"] = "previous running attempt was interrupted"
    _append_failure(
        batch_dir,
        failures,
        manifest_row,
        attempt_index=attempt_index,
        failure_dir=failure_dir,
    )
    _atomic_write_csv(batch_dir / "replicate_manifest.csv", MANIFEST_FIELDS, manifest_rows)


def _run_one_attempt(
    request: Mapping[str, Any],
    batch_dir: Path,
    manifest_rows: list[dict],
    manifest_row: dict,
    ledger_row: Mapping[str, Any],
    failures: list[dict],
) -> str:
    attempt_index = _parse_manifest_int(manifest_row, "attempt_count", default=0) + 1
    replicate_id = str(ledger_row["replicate_id"])
    work_dir = _work_attempt_dir(batch_dir, replicate_id, attempt_index)
    failure_dir = _failure_attempt_dir(batch_dir, replicate_id, attempt_index)
    if work_dir.exists() or failure_dir.exists():
        raise RunnerStartupError(f"attempt directory already exists for {replicate_id} attempt {attempt_index}")

    manifest_row["status"] = "running"
    manifest_row["attempt_count"] = attempt_index
    manifest_row["started_at"] = _utc_now()
    manifest_row["finished_at"] = ""
    manifest_row["subprocess_exit_code"] = ""
    manifest_row["condition_success_count"] = 0
    manifest_row["condition_error_count"] = 0
    manifest_row["postprocess_error_count"] = 0
    manifest_row["replay_alignment_violated"] = False
    manifest_row["network_status"] = ""
    manifest_row["validation_passed"] = False
    manifest_row["failure_stage"] = ""
    manifest_row["failure_type"] = ""
    manifest_row["failure_message"] = ""
    _atomic_write_csv(batch_dir / "replicate_manifest.csv", MANIFEST_FIELDS, manifest_rows)

    argv = build_child_argv(
        python_executable=request["python_executable"],
        project_root=request["project_root"],
        replication_id=request["replication_id"],
        ledger_row=ledger_row,
        output_dir=work_dir,
        llm_mode=request["llm_mode"],
    )
    env = build_child_env(
        ledger_row,
        llm_mode=request["llm_mode"],
        formal_activation_context=request.get("_formal_activation_context"),
    )
    child_runner = request.get("_child_runner", subprocess.run)
    completed = child_runner(
        argv,
        cwd=str(request["project_root"]),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    _write_text_file(work_dir / "child_stdout.log", _sanitize_text(completed.stdout, limit=None))
    _write_text_file(work_dir / "child_stderr.log", _sanitize_text(completed.stderr, limit=None))

    block_validator = request.get("_block_validator", validate_block_artifacts)
    validation = block_validator(
        work_dir,
        ledger_row,
        subprocess_exit_code=completed.returncode,
    )
    _apply_validation_to_manifest(manifest_row, validation, completed.returncode)
    manifest_row["finished_at"] = _utc_now()

    if validation.get("validation_passed") is True and validation.get("status") == "succeeded":
        block_dir = batch_dir / str(manifest_row["block_dir"])
        if block_dir.exists():
            raise RunnerStartupError(f"block directory already exists: {block_dir}")
        block_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(work_dir), str(block_dir))
    else:
        failure_dir = _preserve_failure_attempt(
            batch_dir,
            replicate_id,
            attempt_index,
            source_dir=work_dir if work_dir.exists() else None,
            message=str(validation.get("failure_message", "")),
        )
        _append_failure(
            batch_dir,
            failures,
            manifest_row,
            attempt_index=attempt_index,
            failure_dir=failure_dir,
        )

    _atomic_write_csv(batch_dir / "replicate_manifest.csv", MANIFEST_FIELDS, manifest_rows)
    return str(manifest_row["status"])


def _record_runtime_failure(
    batch_dir: Path,
    manifest_rows: list[dict],
    manifest_row: dict,
    failures: list[dict],
    exc: Exception,
) -> None:
    attempt_index = _parse_manifest_int(manifest_row, "attempt_count", default=0)
    if attempt_index <= 0:
        attempt_index = 1
        manifest_row["attempt_count"] = attempt_index
    replicate_id = str(manifest_row.get("replicate_id", ""))
    work_dir = _work_attempt_dir(batch_dir, replicate_id, attempt_index)
    failure_dir = _preserve_failure_attempt(
        batch_dir,
        replicate_id,
        attempt_index,
        source_dir=work_dir if work_dir.exists() else None,
        message=str(exc),
    )
    manifest_row["status"] = "failed"
    manifest_row["finished_at"] = _utc_now()
    manifest_row["validation_passed"] = False
    manifest_row["failure_stage"] = "parent-runner"
    manifest_row["failure_type"] = type(exc).__name__
    manifest_row["failure_message"] = _sanitize_text(str(exc))
    _append_failure(
        batch_dir,
        failures,
        manifest_row,
        attempt_index=attempt_index,
        failure_dir=failure_dir,
    )
    _atomic_write_csv(batch_dir / "replicate_manifest.csv", MANIFEST_FIELDS, manifest_rows)


def _validate_manifest_against_ledger(
    manifest_rows: list[dict],
    ledger_rows: list[Mapping[str, Any]],
    request: Mapping[str, Any],
) -> dict[str, dict]:
    if len(manifest_rows) != len(ledger_rows):
        raise RunnerStartupError("manifest row count must match seed ledger")
    manifest_replicate_ids = [str(row.get("replicate_id", "")) for row in manifest_rows]
    ledger_replicate_ids = [str(row["replicate_id"]) for row in ledger_rows]
    if manifest_replicate_ids != ledger_replicate_ids:
        raise RunnerStartupError("manifest replicate_id order must match seed ledger")
    ledger_by_id = {str(row["replicate_id"]): row for row in ledger_rows}
    if len(ledger_by_id) != len(ledger_rows):
        raise RunnerStartupError("seed ledger replicate_id values must be unique")
    row_by_id: dict[str, dict] = {}
    for position, row in enumerate(manifest_rows, start=1):
        if tuple(row.keys()) != MANIFEST_FIELDS:
            raise RunnerStartupError("manifest header mismatch")
        replicate_id = str(row.get("replicate_id", ""))
        if replicate_id not in ledger_by_id or replicate_id in row_by_id:
            raise RunnerStartupError("manifest replicate_id mismatch")
        ledger = ledger_by_id[replicate_id]
        if str(row.get("replicate_index")) != str(position):
            raise RunnerStartupError("manifest replicate_index order mismatch")
        if str(row.get("replicate_index")) != str(ledger["replicate_index"]):
            raise RunnerStartupError("manifest replicate_index mismatch")
        expected = _planned_manifest_row(str(request["replication_id"]), ledger)
        for field in (
            "replication_id",
            "replicate_id",
            "replicate_index",
            "simulation_seed",
            "requested_llm_seed",
            "llm_seed_supported",
            "python_hash_seed",
            "block_dir",
        ):
            if str(row.get(field)) != str(expected[field]):
                raise RunnerStartupError(f"manifest {field} mismatch")
        if row.get("status") not in BLOCK_STATES:
            raise RunnerStartupError("manifest status is invalid")
        row_by_id[replicate_id] = row
    return row_by_id


def _verify_ledger_matches_request(
    ledger: list[Mapping[str, Any]],
    request: Mapping[str, Any],
) -> None:
    if len(ledger) != request["num_replicates"]:
        raise RunnerStartupError("seed ledger replicate count mismatch")
    for index, row in enumerate(ledger, start=1):
        expected_replicate_id = f"R{index:03d}"
        expected_pairs = {
            "replicate_id": expected_replicate_id,
            "replicate_index": index,
            "master_seed": request["master_seed"],
            "llm_seed_supported": request["llm_seed_supported"],
            "provider_model": request["provider_model"],
            "provider_system_fingerprint": request["provider_system_fingerprint"],
            "seed_derivation_version": SEED_DERIVATION_VERSION,
            "matrix_version": MATRIX_VERSION,
            "metrics_schema_version": METRICS_SCHEMA_VERSION,
            "condition_count": CONDITION_COUNT,
            "control_exp_id": CONTROL_EXP_ID,
            "cache_scope": CACHE_SCOPE,
        }
        for field, expected in expected_pairs.items():
            if row.get(field) != expected:
                raise RunnerStartupError(f"seed ledger {field} mismatch")


def _verify_batch_metadata_matches_request(
    metadata: Mapping[str, Any],
    request: Mapping[str, Any],
) -> None:
    if tuple(metadata.keys()) != BATCH_METADATA_FIELDS:
        raise RunnerStartupError("replication metadata fields mismatch")
    expected = _batch_metadata_for_request(
        request,
        created_at=str(metadata.get("created_at", "")),
    )
    for field in BATCH_METADATA_FIELDS:
        if field in ("created_at", "updated_at"):
            if not isinstance(metadata.get(field), str) or not metadata.get(field):
                raise RunnerStartupError(f"replication metadata {field} invalid")
        elif metadata.get(field) != expected[field]:
            raise RunnerStartupError(f"replication metadata {field} mismatch")


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RunnerStartupError(f"{path.name} is invalid JSON") from exc
    if not isinstance(data, dict):
        raise RunnerStartupError(f"{path.name} must be a JSON object")
    return data


def _read_csv_file(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if tuple(reader.fieldnames or ()) != fields:
                raise RunnerStartupError(f"{path.name} header mismatch")
            rows = list(reader)
    except RunnerStartupError:
        raise
    except Exception as exc:
        raise RunnerStartupError(f"{path.name} is invalid CSV") from exc
    if any(None in row for row in rows):
        raise RunnerStartupError(f"{path.name} contains extra columns")
    return rows


def _atomic_write_csv(path: Path, fields: tuple[str, ...], rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fields})
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _atomic_write_json_object(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            json.dump(dict(data), f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _apply_validation_to_manifest(
    manifest_row: dict,
    validation: Mapping[str, Any],
    subprocess_exit_code: int,
) -> None:
    manifest_row["status"] = validation.get("status", "invalid")
    manifest_row["subprocess_exit_code"] = subprocess_exit_code
    for field in (
        "condition_success_count",
        "condition_error_count",
        "postprocess_error_count",
        "replay_alignment_violated",
        "network_status",
        "validation_passed",
        "failure_stage",
        "failure_type",
        "failure_message",
    ):
        manifest_row[field] = validation.get(field, "")


def _append_failure(
    batch_dir: Path,
    failures: list[dict],
    manifest_row: Mapping[str, Any],
    *,
    attempt_index: int,
    failure_dir: Path,
) -> None:
    failure_row = {
        "replication_id": manifest_row.get("replication_id", ""),
        "replicate_id": manifest_row.get("replicate_id", ""),
        "replicate_index": manifest_row.get("replicate_index", ""),
        "attempt_index": attempt_index,
        "status": manifest_row.get("status", ""),
        "subprocess_exit_code": manifest_row.get("subprocess_exit_code", ""),
        "failure_stage": manifest_row.get("failure_stage", ""),
        "failure_type": manifest_row.get("failure_type", ""),
        "failure_message": _sanitize_text(str(manifest_row.get("failure_message", ""))),
        "failure_dir": _relative_to_batch(batch_dir, failure_dir),
        "recorded_at": _utc_now(),
    }
    failures.append(failure_row)
    _atomic_write_csv(batch_dir / "replication_failures.csv", FAILURE_FIELDS, failures)


def _parse_manifest_int(
    row: Mapping[str, Any],
    field: str,
    *,
    default: int | None = None,
) -> int:
    value = row.get(field, "")
    if value == "" and default is not None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RunnerStartupError(f"manifest {field} must be an integer") from exc
    if isinstance(parsed, bool):
        raise RunnerStartupError(f"manifest {field} must be a non-boolean integer")
    return parsed


def _preserve_failure_attempt(
    batch_dir: Path,
    replicate_id: str,
    attempt_index: int,
    *,
    source_dir: Path | None = None,
    message: str = "",
) -> Path:
    if not isinstance(attempt_index, int) or isinstance(attempt_index, bool) or attempt_index <= 0:
        raise RunnerStartupError("attempt_index must be a positive integer")
    failure_dir = _failure_attempt_dir(batch_dir, str(replicate_id), attempt_index)
    if failure_dir.exists():
        raise RunnerStartupError(f"failure attempt already exists: {failure_dir}")
    failure_dir.parent.mkdir(parents=True, exist_ok=True)
    if source_dir is not None and source_dir.exists():
        os.replace(str(source_dir), str(failure_dir))
    else:
        failure_dir.mkdir()
    if message:
        _write_text_file(
            failure_dir / "parent_runner_error.log",
            _sanitize_text(message, limit=None),
        )
    return failure_dir


def _work_attempt_dir(batch_dir: Path, replicate_id: str, attempt_index: int) -> Path:
    return batch_dir / "work" / f"{replicate_id}.attempt_{attempt_index:03d}"


def _failure_attempt_dir(batch_dir: Path, replicate_id: str, attempt_index: int) -> Path:
    return batch_dir / "failures" / replicate_id / f"attempt_{attempt_index:03d}"


def _relative_to_batch(batch_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(batch_dir.resolve()).as_posix()
    except ValueError:
        return str(path)


def _sanitize_text(text: Any, *, limit: int | None = 240) -> str:
    value = str(text)
    value = re.sub(r"sk-[A-Za-z0-9_-]+", "<redacted>", value)
    value = re.sub(r"(?i)Bearer\s+[^,\s;]+", "Bearer <redacted>", value)
    value = re.sub(
        r"(?i)\b(api[_-]?key|api-key|password|token|secret)\s*[:=]\s*[^,\s;]+",
        lambda match: f"{match.group(1)}=<redacted>",
        value,
    )
    if limit is not None:
        return value[:limit]
    return value


def validate_block_artifacts(
    block_dir,
    ledger_row,
    *,
    subprocess_exit_code: int,
) -> dict:
    """Validate one completed replicate block without mutating inputs."""
    if not isinstance(ledger_row, Mapping):
        raise ValueError("ledger_row must be a mapping")
    if not isinstance(subprocess_exit_code, int) or isinstance(
        subprocess_exit_code, bool
    ):
        raise ValueError("subprocess_exit_code must be an integer")
    missing = [field for field in LEDGER_FIELDS if field not in ledger_row]
    if missing:
        raise ValueError("ledger_row missing required fields")

    ledger = dict(ledger_row)
    block_path = Path(block_dir)
    if subprocess_exit_code != 0:
        return _failed_exit_code(subprocess_exit_code)
    if not block_path.is_dir():
        return _invalid(
            "block-directory",
            "BlockDirectoryMissing",
            "block directory is missing",
        )

    forbidden = _validate_forbidden_artifacts(block_path)
    if forbidden is not None:
        return forbidden

    metadata_result, metadata = _load_json_object(
        block_path / "run_metadata.json",
        "run-metadata",
        "RunMetadata",
    )
    if metadata_result is not None:
        return metadata_result

    result = _validate_run_metadata(metadata, ledger)
    if result is not None:
        return result
    result, strategy_ids = _validate_summary(block_path / "summary.csv")
    if result is not None:
        return result
    result = _validate_ranking_sensitivity(
        block_path / "ranking_sensitivity.csv",
        strategy_ids,
    )
    if result is not None:
        return result
    result = _validate_ranking_robustness(
        block_path / "ranking_robustness.csv",
        strategy_ids,
    )
    if result is not None:
        return result
    result = _validate_figures(block_path)
    if result is not None:
        return result

    return {
        "validation_passed": True,
        "status": "succeeded",
        "condition_success_count": 9,
        "condition_error_count": 0,
        "postprocess_error_count": 0,
        "replay_alignment_violated": False,
        "network_status": "consistent",
        "failure_stage": "",
        "failure_type": "",
        "failure_message": "",
    }


def _base_result(
    *,
    validation_passed: bool,
    status: str,
    failure_stage: str,
    failure_type: str,
    failure_message: str,
    condition_success_count: int = 0,
    condition_error_count: int = 0,
    postprocess_error_count: int = 0,
    replay_alignment_violated: bool = False,
    network_status: str = "",
) -> dict:
    return {
        "validation_passed": validation_passed,
        "status": status,
        "condition_success_count": condition_success_count,
        "condition_error_count": condition_error_count,
        "postprocess_error_count": postprocess_error_count,
        "replay_alignment_violated": replay_alignment_violated,
        "network_status": network_status,
        "failure_stage": failure_stage,
        "failure_type": failure_type,
        "failure_message": _sanitize_failure_message(failure_message),
    }


def _failed_exit_code(exit_code: int) -> dict:
    return _base_result(
        validation_passed=False,
        status="failed",
        failure_stage="subprocess",
        failure_type="SubprocessExitCode",
        failure_message=f"subprocess exited with code {exit_code}",
    )


def _invalid(stage: str, failure_type: str, message: str) -> dict:
    return _base_result(
        validation_passed=False,
        status="invalid",
        failure_stage=stage,
        failure_type=failure_type,
        failure_message=message,
    )


def _sanitize_failure_message(message: str) -> str:
    return _sanitize_text(message, limit=240)


def _load_json_object(
    path: Path,
    stage: str,
    failure_prefix: str,
) -> tuple[dict | None, dict[str, Any]]:
    if not path.is_file():
        return (
            _invalid(stage, f"{failure_prefix}Missing", f"{path.name} is missing"),
            {},
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return (
            _invalid(stage, f"{failure_prefix}InvalidJson", f"{path.name} is invalid JSON"),
            {},
        )
    if not isinstance(data, dict):
        return (
            _invalid(stage, f"{failure_prefix}NotObject", f"{path.name} must be a JSON object"),
            {},
        )
    return None, data


def _validate_run_metadata(metadata: Mapping[str, Any], ledger: Mapping[str, Any]) -> dict | None:
    if metadata.get("batch_exit_code") != 0:
        return _invalid("run-metadata", "BatchExitCode", "batch_exit_code must be 0")
    if metadata.get("run_completed") is not True:
        return _invalid("run-metadata", "RunIncomplete", "run_completed must be true")

    matrix = metadata.get("experiment_matrix")
    if not isinstance(matrix, Mapping):
        return _invalid("experiment-matrix", "ExperimentMatrixMissing", "experiment_matrix must be an object")
    if matrix.get("matrix_version") != MATRIX_VERSION:
        return _invalid("experiment-matrix", "MatrixVersionMismatch", "matrix_version must be 3.0")
    if matrix.get("condition_count") != CONDITION_COUNT:
        return _invalid("experiment-matrix", "ConditionCountMismatch", "condition_count must be 9")
    if matrix.get("control_exp_id") != CONTROL_EXP_ID:
        return _invalid("experiment-matrix", "ControlExpIdMismatch", "control exp_id mismatch")
    if matrix.get("replay_alignment_violated") is not False:
        return _invalid("experiment-matrix", "ReplayAlignmentViolation", "replay alignment must be false")

    metrics = metadata.get("metrics")
    if not isinstance(metrics, Mapping):
        return _invalid("metrics", "MetricsMissing", "metrics must be an object")
    if metrics.get("schema_version") != METRICS_SCHEMA_VERSION:
        return _invalid("metrics", "MetricsSchemaMismatch", "metrics schema_version must be 4.0")

    network = metadata.get("network_consistency")
    if not isinstance(network, Mapping):
        return _invalid("network", "NetworkConsistencyMissing", "network_consistency must be an object")
    if network.get("status") != "consistent":
        return _invalid("network", "NetworkInconsistent", "network status must be consistent")

    replication = metadata.get("replication")
    if not isinstance(replication, Mapping):
        return _invalid("replication-metadata", "ReplicationMetadataMissing", "replication must be an object")
    if not set(REPLICATION_METADATA_FIELDS) <= set(replication):
        return _invalid("replication-metadata", "ReplicationMetadataFields", "replication metadata fields missing")

    replicate_index = replication.get("replicate_index")
    if not isinstance(replicate_index, int) or isinstance(replicate_index, bool):
        return _invalid(
            "replication-metadata",
            "ReplicateIndexInvalid",
            "replicate_index must be a non-boolean integer",
        )

    engineering_flag = replication.get("engineering_acceptance_only")
    if not isinstance(engineering_flag, bool):
        return _invalid(
            "replication-metadata",
            "EngineeringAcceptanceFlag",
            "engineering_acceptance_only must be boolean",
        )

    expected_pairs = {
        "schema_version": REPLICATION_SCHEMA_VERSION,
        "replicate_id": ledger["replicate_id"],
        "replicate_index": ledger["replicate_index"],
        "simulation_seed": ledger["simulation_seed"],
        "requested_llm_seed": ledger["requested_llm_seed"],
        "llm_seed_supported": ledger["llm_seed_supported"],
        "python_hash_seed": ledger["python_hash_seed"],
        "cache_scope": CACHE_SCOPE,
        "execution_mode": EXECUTION_MODE,
        "latest_policy": LATEST_POLICY,
    }
    if not isinstance(replication.get("replication_id"), str) or not replication.get("replication_id"):
        return _invalid("replication-metadata", "ReplicationIdInvalid", "replication_id must be non-empty")
    for key, expected in expected_pairs.items():
        if replication.get(key) != expected:
            return _invalid("replication-metadata", "ReplicationMetadataMismatch", f"replication {key} mismatch")
    if replication.get("cache_scope") != ledger["cache_scope"]:
        return _invalid("replication-metadata", "ReplicationCacheScopeMismatch", "cache_scope must match ledger")
    return None


def _validate_summary(path: Path) -> tuple[dict | None, set[str]]:
    rows_result, rows = _read_csv_rows(path, "summary", "summary.csv")
    if rows_result is not None:
        return rows_result, set()
    header = set(rows[0].keys()) if rows else set()
    if not set(SUMMARY_REQUIRED_FIELDS) <= header:
        return _invalid("summary", "SummaryFieldsMissing", "summary required fields missing"), set()
    if len(rows) != CONDITION_COUNT:
        return _invalid("summary", "SummaryRowCount", "summary must contain 9 rows"), set()

    exp_ids = [row.get("exp_id", "") for row in rows]
    if any(not exp_id for exp_id in exp_ids) or len(set(exp_ids)) != len(exp_ids):
        return _invalid("summary", "SummaryExpIdInvalid", "summary exp_id values must be unique"), set()
    if set(exp_ids) != set(EXECUTION_ORDER):
        return _invalid("summary", "SummaryExecutionOrderMismatch", "summary exp_id set mismatch"), set()

    control_rows = []
    strategy_rows = []
    combos = set()
    for row in rows:
        is_control = _parse_bool(row.get("is_control"))
        if is_control is None:
            return _invalid("summary", "SummaryControlFlagInvalid", "is_control must be explicit boolean"), set()
        if is_control:
            control_rows.append(row)
        else:
            strategy_rows.append(row)
            combo = (
                row.get("content_factor"),
                row.get("channel_factor"),
                row.get("timing_factor"),
            )
            combos.add(combo)

        trust_gain = _parse_finite(row.get("trust_gain_vs_control"))
        final_gain = _parse_finite(row.get("final_trust_gain_vs_control"))
        auc_gain = _parse_finite(row.get("post_scandal_auc_gain_vs_control"))
        if trust_gain is None or final_gain is None or auc_gain is None:
            return _invalid("summary", "SummaryNumericInvalid", "global summary metrics must be finite"), set()
        if abs(trust_gain - final_gain) > 1e-12:
            return _invalid("summary", "SummaryAliasMismatch", "trust gain aliases must match"), set()

        if is_control:
            if abs(trust_gain) > 1e-12 or abs(final_gain) > 1e-12 or abs(auc_gain) > 1e-12:
                return _invalid("summary", "SummaryControlGlobalMetrics", "control global metrics must be 0"), set()
            for field in V4_FIELDS[2:]:
                if not _is_empty(row.get(field)):
                    return _invalid("summary", "SummaryControlTimeMetrics", "control time metrics must be empty"), set()
        else:
            for field in V4_FIELDS:
                if _parse_finite(row.get(field)) is None:
                    return _invalid("summary", "SummaryStrategyMetricInvalid", "strategy v4 metrics must be finite"), set()

    if len(control_rows) != 1 or control_rows[0].get("exp_id") != CONTROL_EXP_ID:
        return _invalid("summary", "SummaryControlCount", "summary must contain one control row"), set()
    control = control_rows[0]
    if (
        control.get("content_factor") != "not-applicable"
        or control.get("channel_factor") != "not-applicable"
        or control.get("timing_factor") != "no-clarification"
    ):
        return _invalid("summary", "SummaryControlFactors", "control factors mismatch"), set()
    expected_combos = {
        (content, channel, timing)
        for content in ("rational-evidence", "emotional-empathy")
        for channel in ("hub", "random")
        for timing in ("immediate", "delayed")
    }
    if combos != expected_combos or len(strategy_rows) != 8:
        return _invalid("summary", "SummaryStrategyFactorMatrix", "strategies must form full 2x2x2 matrix"), set()
    return None, {row["exp_id"] for row in strategy_rows}


def _read_csv_rows(path: Path, stage: str, name: str) -> tuple[dict | None, list[dict[str, str]]]:
    if not path.is_file():
        return _invalid(stage, f"{stage.title().replace('-', '')}Missing", f"{name} is missing"), []
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception:
        return _invalid(stage, f"{stage.title().replace('-', '')}InvalidCsv", f"{name} is invalid CSV"), []
    if reader.fieldnames is None:
        return _invalid(stage, f"{stage.title().replace('-', '')}HeaderMissing", f"{name} header is missing"), []
    if any(None in row for row in rows):
        return _invalid(stage, f"{stage.title().replace('-', '')}ExtraColumns", f"{name} contains extra columns"), []
    return None, rows


def _validate_ranking_sensitivity(path: Path, strategy_ids: set[str]) -> dict | None:
    result, rows = _read_csv_rows(path, "ranking-sensitivity", "ranking_sensitivity.csv")
    if result is not None:
        return result
    header = tuple(rows[0].keys()) if rows else tuple()
    if header != RANKING_SENSITIVITY_FIELDS:
        return _invalid("ranking-sensitivity", "RankingSensitivityHeader", "ranking_sensitivity header mismatch")
    if len(rows) != 528:
        return _invalid("ranking-sensitivity", "RankingSensitivityRowCount", "ranking_sensitivity must contain 528 rows")

    groups: dict[tuple[float, float, float], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("exp_id") not in strategy_ids:
            return _invalid("ranking-sensitivity", "RankingSensitivityExpId", "ranking_sensitivity exp_id mismatch")
        numbers = {
            field: _parse_finite(row.get(field))
            for field in (
                "weight_final",
                "weight_auc",
                "weight_local",
                "weighted_score",
                "rank",
                "top1_credit",
            )
        }
        if any(value is None for value in numbers.values()):
            return _invalid("ranking-sensitivity", "RankingSensitivityNumeric", "ranking_sensitivity values must be finite")
        weights = (
            numbers["weight_final"],
            numbers["weight_auc"],
            numbers["weight_local"],
        )
        if abs(sum(weights) - 1.0) > 1e-12:
            return _invalid("ranking-sensitivity", "RankingSensitivityWeights", "weights must sum to 1")
        groups[weights].append(row)

    if len(groups) != 66:
        return _invalid("ranking-sensitivity", "RankingSensitivityWeightCount", "ranking_sensitivity must contain 66 weight groups")
    for group_rows in groups.values():
        ids = {row["exp_id"] for row in group_rows}
        if ids != strategy_ids or len(group_rows) != 8:
            return _invalid("ranking-sensitivity", "RankingSensitivityGroup", "each weight group must contain 8 strategies")
        top1_sum = sum(_parse_finite(row.get("top1_credit")) or 0.0 for row in group_rows)
        if abs(top1_sum - 1.0) > 1e-12:
            return _invalid("ranking-sensitivity", "RankingSensitivityTop1Credit", "top1_credit must sum to 1")
    return None


def _validate_ranking_robustness(path: Path, strategy_ids: set[str]) -> dict | None:
    result, rows = _read_csv_rows(path, "ranking-robustness", "ranking_robustness.csv")
    if result is not None:
        return result
    header = tuple(rows[0].keys()) if rows else tuple()
    if header != RANKING_ROBUSTNESS_FIELDS:
        return _invalid("ranking-robustness", "RankingRobustnessHeader", "ranking_robustness header mismatch")
    if len(rows) != 8:
        return _invalid("ranking-robustness", "RankingRobustnessRowCount", "ranking_robustness must contain 8 rows")
    ids = [row.get("exp_id") for row in rows]
    if set(ids) != strategy_ids or len(set(ids)) != 8:
        return _invalid("ranking-robustness", "RankingRobustnessExpId", "ranking_robustness exp_id mismatch")
    for row in rows:
        for field in RANKING_ROBUSTNESS_FIELDS[1:]:
            if _parse_finite(row.get(field)) is None:
                return _invalid("ranking-robustness", "RankingRobustnessNumeric", "ranking_robustness values must be finite")
    return None


def _validate_figures(block_path: Path) -> dict | None:
    figures_dir = block_path / "figures"
    for name in FIGURE_FILES:
        path = figures_dir / name
        if not path.is_file() or path.stat().st_size <= 0:
            return _invalid("figures", "FigureMissing", f"{name} is missing or empty")
    return None


def _validate_forbidden_artifacts(block_path: Path) -> dict | None:
    if (block_path / "errors.log").exists():
        return _invalid("forbidden-artifacts", "ErrorsLogPresent", "errors.log must not exist")
    if (block_path / "network_inconsistency_report.json").exists():
        return _invalid(
            "forbidden-artifacts",
            "NetworkInconsistencyReportPresent",
            "network inconsistency report must not exist",
        )
    return None


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if value in (0, 1):
            return bool(value)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized in ("True", "true", "1"):
            return True
        if normalized in ("False", "false", "0"):
            return False
    return None


def _parse_finite(value: Any) -> float | None:
    if isinstance(value, bool) or _is_empty(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


if __name__ == "__main__":
    raise SystemExit(main())
