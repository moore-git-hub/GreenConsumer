"""TASK_005 formal launch preauthorization gate.

This module provides formal launch gates. Real formal execution requires a
separate frozen authorization artifact plus the exact runtime intent token.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

import run_replications
from replication_config import build_seed_ledger, read_seed_ledger_csv


STAGE = "I.5C-5B-0"
ACTIVATION_STAGE = "I.5C-5B-1A"
FORMAL_BATCH_ID = "task005-formal-v1"
FORMAL_N = 24
MASTER_SEED = 2026080801
LLM_SEED_SUPPORTED = "unknown"
RUNTIME_TOKEN = "I5C5B1_TASK005_FORMAL_V1_INITIAL_N24_2026080801"
FORMAL_OUTPUT_PATH = Path("results/replications/task005-formal-v1")
CONTRACT_PATH = Path(
    ".kiro/specs/task005-replication-inference/formal_launch_contract1.0.json"
)
SEED_LEDGER_PATH = Path(
    ".kiro/specs/task005-replication-inference/formal_seed_ledger1.0.csv"
)
MODEL_SANITIZED_PATH = Path(
    ".kiro/specs/task005-replication-inference/"
    "formal_model_config_sanitized1.0.json"
)
ACTIVATION_CONTRACT_PATH = Path(
    ".kiro/specs/task005-replication-inference/"
    "formal_activation_gate_contract1.0.json"
)
AUTHORIZATION_PATH = Path(
    ".kiro/specs/task005-replication-inference/"
    "formal_execution_authorization1.0.json"
)
MODELS_CONFIG_PATH = Path("configs/models_config.yaml")
EXPECTED_LAUNCH_CONTRACT_SHA = (
    "fd9d8cb57c714a962d3476c4d07f0850d05f9f80c11eea9809578f32a471c8f6"
)
EXPECTED_SEED_LEDGER_SHA = (
    "44dd7e0381a2fbe7ea4525fad8748b5d9d8b0bdfb6fdd8ed9aa85e50140cc38e"
)
EXPECTED_MODEL_SANITIZED_SHA = (
    "8311d2f5758009e1620d3cc10f588cb789fe2d0c801878854d19a79bf0900a61"
)
EXPECTED_FORMAL_CONTRACTS = (
    ".kiro/specs/task005-replication-inference/formal_n_freeze1.0.json",
    ".kiro/specs/task005-replication-inference/"
    "formal_runner_exact_cohort_contract1.0.json",
    ".kiro/specs/task005-replication-inference/formal_launch_readiness1.2.json",
)
FORBIDDEN_ENGINEERING_IDS = {"P001", "P002", "P003", "P004", "P005"}
REQUIRED_BRANCH = "refactor/task005-replication-inference"
AUTHORIZATION_DIFF_ALLOWLIST = (
    ".kiro/specs/task005-replication-inference/"
    "formal_execution_authorization1.0.json",
    ".kiro/specs/task005-replication-inference/"
    "formal_execution_authorization1.0.md",
)


class FormalLaunchGateError(RuntimeError):
    """Raised when a formal preauthorization gate fails closed."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json_object(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise FormalLaunchGateError(f"{path} must contain a JSON object")
    return value


def _assert_sha(path: Path, expected: str) -> None:
    actual = _sha256_file(path)
    if actual.lower() != expected.lower():
        raise FormalLaunchGateError(f"{path} SHA mismatch")


def _load_contracts(root: Path) -> tuple[dict, dict]:
    launch_path = root / CONTRACT_PATH
    sanitized_path = root / MODEL_SANITIZED_PATH
    ledger_path = root / SEED_LEDGER_PATH
    _assert_sha(launch_path, EXPECTED_LAUNCH_CONTRACT_SHA)
    _assert_sha(ledger_path, EXPECTED_SEED_LEDGER_SHA)
    _assert_sha(sanitized_path, EXPECTED_MODEL_SANITIZED_SHA)

    launch_contract = _read_json_object(launch_path)
    sanitized_contract = _read_json_object(sanitized_path)
    source_hashes = launch_contract.get("source_identities", {}).get("sha256", {})
    if not isinstance(source_hashes, dict):
        raise FormalLaunchGateError("launch contract source identities missing")
    for rel in EXPECTED_FORMAL_CONTRACTS:
        path = root / rel
        if not path.exists():
            raise FormalLaunchGateError(f"{rel} missing")
        expected = source_hashes.get(rel) or launch_contract.get("parent_contracts", {}).get(
            Path(rel).name
        )
        if not expected:
            raise FormalLaunchGateError(f"{rel} frozen SHA missing")
        _assert_sha(path, str(expected))
    return launch_contract, sanitized_contract


def _is_chat_capable(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    capabilities = entry.get("capabilities")
    if not isinstance(capabilities, (list, tuple, set)):
        return False
    return "chat" in capabilities


def _config_entries(config: Any) -> list[dict]:
    entries = config if isinstance(config, list) else [config]
    return [entry for entry in entries if isinstance(entry, dict)]


def _execution_identity(entry: Mapping[str, Any]) -> dict:
    identity: dict[str, Any] = {}
    for key, value in entry.items():
        text = str(key).lower()
        if any(marker in text for marker in ("api_key", "token", "secret", "password")):
            identity["api_key_present" if text == "api_key" else f"{key}_present"] = bool(
                value
            )
        else:
            identity[str(key)] = copy.deepcopy(value)
    return identity


def _identity_without_credentials(identity: Mapping[str, Any]) -> dict:
    return {
        key: value
        for key, value in identity.items()
        if not str(key).lower().endswith("_present")
    }


def validate_current_formal_model_config(
    *,
    root: Path | str = Path("."),
    config_path: Path | str | None = None,
    frozen_sanitized_path: Path | str | None = None,
) -> dict:
    """Validate current non-secret model execution identity against 5A freeze."""
    base = Path(root)
    cfg_path = base / (Path(config_path) if config_path is not None else MODELS_CONFIG_PATH)
    frozen_path = base / (
        Path(frozen_sanitized_path)
        if frozen_sanitized_path is not None
        else MODEL_SANITIZED_PATH
    )
    with cfg_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    entries = _config_entries(config)
    chat_entries = [entry for entry in entries if _is_chat_capable(entry)]
    if len(chat_entries) != 1:
        raise FormalLaunchGateError(
            f"expected exactly one chat-capable model, found {len(chat_entries)}"
        )
    runtime_identity = _execution_identity(chat_entries[0])
    frozen = _read_json_object(frozen_path)
    frozen_identity = frozen.get("selected_chat_model")
    if not isinstance(frozen_identity, dict):
        raise FormalLaunchGateError("frozen selected_chat_model missing")
    if _identity_without_credentials(runtime_identity) != _identity_without_credentials(
        frozen_identity
    ):
        raise FormalLaunchGateError("runtime model execution identity mismatch")
    return {
        "chat_model_count": len(chat_entries),
        "model_binding_verified": True,
        "runtime_identity": runtime_identity,
        "frozen_identity": frozen_identity,
    }


def _validate_formal_seed_ledger(root: Path, launch_contract: Mapping[str, Any]) -> None:
    rows = read_seed_ledger_csv(root / SEED_LEDGER_PATH)
    expected_ids = [f"R{index:03d}" for index in range(1, FORMAL_N + 1)]
    ids = [row["replicate_id"] for row in rows]
    if len(rows) != FORMAL_N:
        raise FormalLaunchGateError("formal seed ledger must contain exactly 24 rows")
    if [row["replicate_index"] for row in rows] != list(range(1, FORMAL_N + 1)):
        raise FormalLaunchGateError("formal replicate_index must be 1..24")
    if ids != expected_ids:
        raise FormalLaunchGateError("formal replicate_id must be R001-R024")
    if any(rep_id in FORBIDDEN_ENGINEERING_IDS for rep_id in ids):
        raise FormalLaunchGateError("engineering block ID in formal seed ledger")
    if any(rep_id.startswith("R") and int(rep_id[1:]) > FORMAL_N for rep_id in ids):
        raise FormalLaunchGateError("R025+ not permitted")
    provider_model = str(launch_contract.get("provider_model", ""))
    rebuilt = build_seed_ledger(
        MASTER_SEED,
        FORMAL_N,
        llm_seed_supported=LLM_SEED_SUPPORTED,
        provider_model=provider_model,
        provider_system_fingerprint="unavailable-prelaunch",
    )
    if rows != rebuilt:
        raise FormalLaunchGateError("formal seed ledger reconstruction mismatch")


def validate_per_block_requested_seed_override(
    *,
    root: Path | str = Path("."),
    config_path: Path | str | None = None,
) -> dict:
    """Validate that each formal block's requested seed overrides base seed."""
    base = Path(root)
    cfg_path = base / (Path(config_path) if config_path is not None else MODELS_CONFIG_PATH)
    with cfg_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    rows = read_seed_ledger_csv(base / SEED_LEDGER_PATH)
    results: dict[str, int] = {}
    for row in rows:
        requested = row["requested_llm_seed"]
        conf = copy.deepcopy(config)
        updated = 0
        for entry in _config_entries(conf):
            if _is_chat_capable(entry):
                entry["seed"] = requested
                updated += 1
        if updated != 1:
            raise FormalLaunchGateError("requested seed override did not bind exactly once")
        chat_entry = [entry for entry in _config_entries(conf) if _is_chat_capable(entry)][0]
        if chat_entry.get("seed") != requested:
            raise FormalLaunchGateError("requested seed override mismatch")
        results[row["replicate_id"]] = requested
    return results


def _git(args: list[str], *, root: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(root),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise FormalLaunchGateError("git gate command failed")
    return result.stdout.strip()


def current_git_state(root: Path | str = Path(".")) -> dict:
    base = Path(root)
    upstream = _git(["rev-list", "--left-right", "--count", "@{upstream}...HEAD"], root=base)
    behind, ahead = [int(part) for part in upstream.split()]
    return {
        "branch": _git(["branch", "--show-current"], root=base),
        "tracked_clean": _git(["status", "--short", "--untracked-files=no"], root=base)
        == "",
        "staged_clean": _git(["diff", "--cached", "--name-only"], root=base) == "",
        "upstream_behind": behind,
        "upstream_ahead": ahead,
    }


def validate_git_gate(
    state_provider: Callable[[], Mapping[str, Any]] | None = None,
) -> dict:
    state = dict(state_provider() if state_provider else current_git_state())
    if state.get("branch") != REQUIRED_BRANCH:
        raise FormalLaunchGateError("branch mismatch")
    if state.get("tracked_clean") is not True:
        raise FormalLaunchGateError("tracked working tree is not clean")
    if state.get("staged_clean") is not True:
        raise FormalLaunchGateError("staged index is not clean")
    if state.get("upstream_behind") != 0 or state.get("upstream_ahead") != 0:
        raise FormalLaunchGateError("HEAD/upstream must be 0 0")
    return state


def _validate_source_hashes(root: Path, launch_contract: Mapping[str, Any]) -> None:
    hashes = launch_contract.get("source_identities", {}).get("sha256", {})
    if not isinstance(hashes, dict):
        raise FormalLaunchGateError("frozen source hashes missing")
    for rel, expected in hashes.items():
        if rel in {
            ".kiro/specs/task005-replication-inference/formal_model_config_sanitized1.0.json",
            "configs/models_config.yaml",
        }:
            continue
        path = root / rel
        if not path.exists():
            raise FormalLaunchGateError(f"frozen source missing: {rel}")
        if _sha256_file(path).lower() != str(expected).lower():
            raise FormalLaunchGateError(f"frozen source SHA mismatch: {rel}")


def _validate_activation_source_hashes(
    root: Path,
    authorization: Mapping[str, Any],
) -> None:
    hashes = authorization.get("activation_source_sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise FormalLaunchGateError("authorization activation source hashes missing")
    for rel, expected in hashes.items():
        path = root / rel
        if not path.exists():
            raise FormalLaunchGateError(f"activation source missing: {rel}")
        if _sha256_file(path).lower() != str(expected).lower():
            raise FormalLaunchGateError(f"activation source SHA mismatch: {rel}")


def current_commit_info(root: Path | str = Path(".")) -> dict:
    base = Path(root)
    head = _git(["rev-parse", "HEAD"], root=base)
    parent = _git(["rev-parse", "HEAD^"], root=base)
    diff_names = _git(["diff", "--name-only", f"{parent}..{head}"], root=base)
    return {
        "head": head,
        "parent": parent,
        "diff_names": tuple(
            line.strip().replace("\\", "/")
            for line in diff_names.splitlines()
            if line.strip()
        ),
    }


def _validate_authorization_commit_structure(
    authorization: Mapping[str, Any],
    *,
    commit_info_provider: Callable[[], Mapping[str, Any]] | None = None,
) -> dict:
    info = dict(commit_info_provider() if commit_info_provider else current_commit_info())
    activation_head = authorization.get("activation_code_head")
    if info.get("parent") != activation_head:
        raise FormalLaunchGateError("authorization commit parent mismatch")
    diff_names = tuple(str(item).replace("\\", "/") for item in info.get("diff_names", ()))
    if not diff_names or any(name not in AUTHORIZATION_DIFF_ALLOWLIST for name in diff_names):
        raise FormalLaunchGateError("authorization commit contains non-authorization changes")
    return info


def validate_authorization_artifact(
    *,
    root: Path | str = Path("."),
    authorization_path: Path | str = AUTHORIZATION_PATH,
    runtime_token: str | None,
    commit_info_provider: Callable[[], Mapping[str, Any]] | None = None,
) -> dict:
    base = Path(root)
    if runtime_token != RUNTIME_TOKEN:
        raise FormalLaunchGateError("runtime authorization token mismatch")
    path = base / Path(authorization_path)
    if not path.exists():
        raise FormalLaunchGateError("human authorization artifact missing")
    authorization = _read_json_object(path)
    expected_pairs = {
        "schema_version": "1.0",
        "status": "frozen",
        "authorization_scope": "initial_formal_cohort_execution",
        "human_cost_time_authorized": True,
        "human_real_execution_authorized": True,
        "formal_batch_id": FORMAL_BATCH_ID,
        "formal_n": FORMAL_N,
        "sample_size_semantics": "exact",
        "sampling_design": "fixed_predeclared_cohort",
        "master_seed": MASTER_SEED,
        "replacement_blocks_permitted": False,
        "automatic_retry_authorized": False,
        "retry_requires_explicit_later_invocation": True,
        "formal_launch_contract_sha256": EXPECTED_LAUNCH_CONTRACT_SHA,
        "formal_seed_ledger_sha256": EXPECTED_SEED_LEDGER_SHA,
        "formal_model_config_sanitized_sha256": EXPECTED_MODEL_SANITIZED_SHA,
        "runtime_token": RUNTIME_TOKEN,
    }
    for key, expected in expected_pairs.items():
        if authorization.get(key) != expected:
            raise FormalLaunchGateError(f"authorization {key} mismatch")
    planned = authorization.get("planned_replicate_ids")
    if planned != [f"R{index:03d}" for index in range(1, FORMAL_N + 1)]:
        raise FormalLaunchGateError("authorization planned replicate IDs mismatch")
    activation_head = authorization.get("activation_code_head")
    if not isinstance(activation_head, str) or len(activation_head) != 40:
        raise FormalLaunchGateError("authorization activation_code_head invalid")
    activation_contract_sha = authorization.get("formal_activation_gate_contract_sha256")
    if activation_contract_sha != _sha256_file(base / ACTIVATION_CONTRACT_PATH):
        raise FormalLaunchGateError("authorization activation contract SHA mismatch")
    auth_sha = _sha256_file(path)
    commit_info = _validate_authorization_commit_structure(
        authorization,
        commit_info_provider=commit_info_provider,
    )
    _validate_activation_source_hashes(base, authorization)
    return {
        "authorization": authorization,
        "authorization_artifact_sha256": auth_sha,
        "authorization_path": str(path),
        "activation_code_head": activation_head,
        "commit_info": commit_info,
    }


def run_preauthorization_preflight(
    *,
    root: Path | str = Path("."),
    output_path: Path | str = FORMAL_OUTPUT_PATH,
    enforce_git: bool = True,
    git_state_provider: Callable[[], Mapping[str, Any]] | None = None,
) -> dict:
    base = Path(root)
    launch_contract, _ = _load_contracts(base)
    _validate_formal_seed_ledger(base, launch_contract)
    model_result = validate_current_formal_model_config(root=base)
    seed_overrides = validate_per_block_requested_seed_override(root=base)
    target = base / Path(output_path)
    if target.exists():
        raise FormalLaunchGateError("formal output path already exists")
    git_state = None
    if enforce_git:
        git_state = validate_git_gate(git_state_provider)
    if launch_contract.get("human_cost_time_authorized") is not False:
        raise FormalLaunchGateError("5A human authorization field must remain false")
    if launch_contract.get("formal_llm_launch_permitted") is not False:
        raise FormalLaunchGateError("5A formal LLM launch must remain disabled")
    return {
        "stage": STAGE,
        "formal_batch_id": FORMAL_BATCH_ID,
        "formal_n": FORMAL_N,
        "runtime_model_gate": True,
        "per_child_model_recheck_required": True,
        "per_block_requested_seed_override": len(seed_overrides) == FORMAL_N,
        "llm_seed_supported": LLM_SEED_SUPPORTED,
        "provider_determinism_guaranteed": False,
        "formal_output_absent": True,
        "human_authorization_present": False,
        "real_execution_activated": False,
        "formal_llm_launch_permitted": False,
        "real_llm_calls": False,
        "network_calls": 0,
        "model": model_result,
        "git": git_state,
    }


def _formal_request(output_root: Path, python_executable: str) -> dict:
    return {
        "replication_id": FORMAL_BATCH_ID,
        "master_seed": MASTER_SEED,
        "num_replicates": FORMAL_N,
        "llm_mode": "real",
        "llm_seed_supported": LLM_SEED_SUPPORTED,
        "provider_model": "OpenAIProvider:qwen-plus",
        "provider_system_fingerprint": "unavailable-prelaunch",
        "output_root": str(output_root),
        "python_executable": python_executable,
        "max_parallel": 1,
        "retry_failed": False,
    }


def _child_revalidation_gate(
    *,
    root: Path,
    authorization_path: Path,
    authorization_artifact_sha256: str,
    authorization: Mapping[str, Any],
    git_state_provider: Callable[[], Mapping[str, Any]] | None,
):
    def _gate(**_kwargs) -> None:
        validate_current_formal_model_config(root=root)
        _validate_activation_source_hashes(root, authorization)
        validate_git_gate(git_state_provider)
        _assert_sha(root / SEED_LEDGER_PATH, EXPECTED_SEED_LEDGER_SHA)
        if _sha256_file(authorization_path) != authorization_artifact_sha256:
            raise FormalLaunchGateError("authorization artifact SHA changed")

    return _gate


def run_authorized_formal_replication_batch(
    *,
    root: Path | str = Path("."),
    authorization_path: Path | str = AUTHORIZATION_PATH,
    runtime_token: str | None,
    output_root: Path | str = Path("results/replications"),
    python_executable: str = sys.executable,
    child_runner=None,
    block_validator=None,
    git_state_provider: Callable[[], Mapping[str, Any]] | None = None,
    commit_info_provider: Callable[[], Mapping[str, Any]] | None = None,
    allow_existing_output: bool = False,
) -> int:
    base = Path(root)
    launch_contract, _ = _load_contracts(base)
    auth = validate_authorization_artifact(
        root=base,
        authorization_path=authorization_path,
        runtime_token=runtime_token,
        commit_info_provider=commit_info_provider,
    )
    _validate_formal_seed_ledger(base, launch_contract)
    validate_current_formal_model_config(root=base)
    validate_per_block_requested_seed_override(root=base)
    validate_git_gate(git_state_provider)
    target = base / Path(output_root) / FORMAL_BATCH_ID
    if target.exists() and not allow_existing_output:
        raise FormalLaunchGateError("formal output path already exists")
    before_child_start = _child_revalidation_gate(
        root=base,
        authorization_path=base / Path(authorization_path),
        authorization_artifact_sha256=auth["authorization_artifact_sha256"],
        authorization=auth["authorization"],
        git_state_provider=git_state_provider,
    )
    request = _formal_request(base / Path(output_root), python_executable)
    return run_replications.run_replication_batch(
        request,
        before_child_start=before_child_start,
        child_runner=child_runner,
        block_validator=block_validator,
        formal_activation_context={
            "authorization_artifact_sha256": auth["authorization_artifact_sha256"],
            "activation_code_head": auth["activation_code_head"],
            "launch_contract_sha256": EXPECTED_LAUNCH_CONTRACT_SHA,
            "seed_ledger_sha256": EXPECTED_SEED_LEDGER_SHA,
            "runtime_token_validated": True,
        },
    )


def run_execute_request(*, root: Path | str = Path("."), runtime_token: str | None = None) -> int:
    """Run the formal launcher only after all authorization gates pass."""
    try:
        base = Path(root)
        return run_authorized_formal_replication_batch(
            root=base,
            authorization_path=AUTHORIZATION_PATH,
            runtime_token=runtime_token,
            output_root=Path("results/replications"),
            python_executable=sys.executable,
        )
    except FormalLaunchGateError as exc:
        print(f"ERROR: {str(exc)}")
        return 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--root", default=".")
    preflight.add_argument("--skip-git-check", action="store_true", default=False)
    execute = sub.add_parser("execute")
    execute.add_argument("--root", default=".")
    execute.add_argument("--runtime-token", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "preflight":
            result = run_preauthorization_preflight(
                root=args.root,
                enforce_git=not bool(args.skip_git_check),
            )
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            return 0
        if args.command == "execute":
            return run_execute_request(root=args.root, runtime_token=args.runtime_token)
        raise FormalLaunchGateError("unknown command")
    except FormalLaunchGateError as exc:
        print(f"ERROR: {str(exc)}")
        return 2
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
