"""TASK_005 formal fixed-cohort replication wrapper.

This is the formal-only entry point.  It fixes the cohort at R001-R024,
delegates child execution to the generic serial runner, and keeps real formal
launch permission outside this stage.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Mapping

import run_replications as _runner


FORMAL_N = 24
FORMAL_REPLICATE_IDS = tuple(f"R{index:03d}" for index in range(1, FORMAL_N + 1))
FORMAL_REPLICATION_ID_PREFIX = "task005-formal-"
FORMAL_LLM_LAUNCH_PERMITTED = False
_FORBIDDEN_ID_MARKERS = (
    "pilot",
    "smoke",
    "extension",
    "calibration",
    "P001",
    "P002",
    "P003",
    "P004",
    "P005",
)


class FormalRunnerError(ValueError):
    """Raised when a formal fixed-cohort contract is violated."""


def parse_formal_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--replication-id", required=True)
    parser.add_argument("--master-seed", required=True, type=int)
    parser.add_argument("--llm-mode", required=True, choices=_runner.LLM_MODES)
    parser.add_argument(
        "--llm-seed-supported",
        required=True,
        choices=_runner.LLM_SEED_SUPPORTED_VALUES,
    )
    parser.add_argument("--provider-model", default="")
    parser.add_argument("--provider-system-fingerprint", default="")
    parser.add_argument("--output-root", default="results/replications")
    parser.add_argument("--python-executable", required=True)
    parser.add_argument("--retry-failed", action="store_true", default=False)
    return parser.parse_args(argv)


def build_formal_request(args) -> dict:
    replication_id = _validate_formal_replication_id(args.replication_id)
    _reject_real_llm_mode(args.llm_mode)
    request = _runner.build_runner_request(
        argparse.Namespace(
            replication_id=replication_id,
            master_seed=args.master_seed,
            num_replicates=FORMAL_N,
            llm_mode=args.llm_mode,
            llm_seed_supported=args.llm_seed_supported,
            provider_model=args.provider_model,
            provider_system_fingerprint=args.provider_system_fingerprint,
            output_root=args.output_root,
            python_executable=args.python_executable,
            max_parallel=1,
            retry_failed=bool(args.retry_failed),
        )
    )
    _assert_formal_request(request)
    return request


def run_formal_replication_batch(request: Mapping[str, Any]) -> int:
    try:
        req = _validate_formal_request_dict(request)
        batch_dir = Path(req["output_root"]) / req["replication_id"]
        state = _runner._load_or_initialize_batch(req, batch_dir)
        _assert_formal_state(state, req)
        return _runner._run_batch_state(req, state)
    except (_runner.RunnerStartupError, FormalRunnerError, ValueError) as exc:
        print(f"ERROR: {_runner._sanitize_text(str(exc))}")
        return 2
    except Exception as exc:
        print(f"ERROR: {_runner._sanitize_text(type(exc).__name__)}")
        return 1


def _validate_formal_request_dict(request: Mapping[str, Any]) -> dict:
    if not isinstance(request, Mapping):
        raise FormalRunnerError("request must be a mapping")
    req = _runner._validate_runner_request_dict(request)
    req["replication_id"] = _validate_formal_replication_id(
        req["replication_id"]
    )
    _assert_formal_request(req)
    _reject_real_llm_mode(req["llm_mode"])
    return req


def _validate_formal_replication_id(value: Any) -> str:
    text = _runner._validate_replication_id(value)
    if not text.startswith(FORMAL_REPLICATION_ID_PREFIX):
        raise FormalRunnerError(
            f"formal replication_id must start with {FORMAL_REPLICATION_ID_PREFIX}"
        )
    lowered = text.lower()
    for marker in _FORBIDDEN_ID_MARKERS:
        if marker.lower() in lowered or marker in text:
            raise FormalRunnerError(
                "formal replication_id must not use engineering namespace"
            )
    if not re.fullmatch(r"[A-Za-z0-9._-]+", text):
        raise FormalRunnerError("formal replication_id contains invalid characters")
    return text


def _assert_formal_request(request: Mapping[str, Any]) -> None:
    if request.get("num_replicates") != FORMAL_N:
        raise FormalRunnerError("formal num_replicates must be exactly 24")
    if request.get("max_parallel") != 1:
        raise FormalRunnerError("formal max_parallel must be exactly 1")


def _reject_real_llm_mode(llm_mode: Any) -> None:
    if llm_mode == "real":
        raise FormalRunnerError(
            "real formal LLM execution is not authorized; "
            "formal launch contract is not active"
        )


def _assert_formal_state(state: Mapping[str, Any], request: Mapping[str, Any]) -> None:
    ledger = list(state.get("ledger", ()))
    manifest = list(state.get("manifest", ()))
    if len(ledger) != FORMAL_N:
        raise FormalRunnerError("formal seed ledger must contain exactly 24 rows")
    if len(manifest) != FORMAL_N:
        raise FormalRunnerError("formal manifest must contain exactly 24 rows")
    ids = [str(row.get("replicate_id", "")) for row in ledger]
    if tuple(ids) != FORMAL_REPLICATE_IDS:
        raise FormalRunnerError("formal seed ledger must be R001-R024")
    manifest_ids = [str(row.get("replicate_id", "")) for row in manifest]
    if tuple(manifest_ids) != FORMAL_REPLICATE_IDS:
        raise FormalRunnerError("formal manifest must be R001-R024")
    if any(_is_forbidden_replicate_id(item) for item in ids + manifest_ids):
        raise FormalRunnerError("formal cohort contains engineering replicate_id")
    if any(_is_r025_or_later(item) for item in ids + manifest_ids):
        raise FormalRunnerError("formal cohort must not contain R025 or later")
    if str(state.get("metadata", {}).get("replication_id", "")) != str(
        request["replication_id"]
    ):
        raise FormalRunnerError("formal batch metadata replication_id mismatch")
    _runner._validate_manifest_against_ledger(manifest, ledger, request)


def _is_forbidden_replicate_id(value: str) -> bool:
    return value in {"P001", "P002", "P003", "P004", "P005"}


def _is_r025_or_later(value: str) -> bool:
    if not re.fullmatch(r"R\d{3,}", value):
        return False
    return int(value[1:]) > FORMAL_N


def main(argv=None) -> int:
    try:
        args = parse_formal_args(argv)
        request = build_formal_request(args)
        return run_formal_replication_batch(request)
    except (_runner.RunnerStartupError, FormalRunnerError, ValueError) as exc:
        print(f"ERROR: {_runner._sanitize_text(str(exc))}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
