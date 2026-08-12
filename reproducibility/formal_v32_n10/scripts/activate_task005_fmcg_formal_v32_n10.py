"""TASK_005 FMCG v3.2 N=10 activation gate.

Before separate user execution authorization exists:
    python activate_task005_fmcg_formal_v32_n10.py --check-only

This performs zero LLM/API calls and returns READY_BUT_NOT_AUTHORIZED.

After a later, separate authorization turn, an authorization JSON and a one-time
runtime token must be supplied. Only then can --execute invoke the frozen runner.
The current package intentionally contains neither an authorized JSON nor token.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED_BRANCH = "redesign/task005-mechanism-v2"
EXPECTED_HEAD = "ef6567adaafcafcf3b9f6884295f509a05ed727e"
BATCH_ID = "task005-fmcg-v32-formal-n10"
FORMAL_N = 10

SPEC = ROOT / ".kiro" / "specs" / "task005-replication-inference"
RUNTIME_CONTRACT = SPEC / "task005_fmcg_v32_formal_runtime_contract1.0.json"
AUTHORIZATION = SPEC / "task005_fmcg_v32_formal_execution_authorization1.0.json"
RUNNER = ROOT / "run_task005_fmcg_formal_v32_n10.py"
DEFAULT_OUTPUT = ROOT / "results" / "formal" / BATCH_ID


class GateError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"{path} must contain JSON object")
    return value


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GateError(f"git {' '.join(args)} failed")
    return (proc.stdout or "").strip()


def validate_static() -> dict:
    if git("branch", "--show-current") != EXPECTED_BRANCH:
        raise GateError("branch mismatch")
    if git("rev-parse", "HEAD") != EXPECTED_HEAD:
        raise GateError("HEAD mismatch")
    if git("status", "--short", "--untracked-files=no"):
        raise GateError("tracked working tree is not clean")
    if git("diff", "--cached", "--name-only"):
        raise GateError("staged index is not clean")

    runtime = read_json(RUNTIME_CONTRACT)
    if runtime.get("formal_batch_id") != BATCH_ID:
        raise GateError("runtime contract batch mismatch")
    if runtime.get("source_head") != EXPECTED_HEAD:
        raise GateError("runtime contract source head mismatch")

    hashes = runtime.get("frozen_file_sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise GateError("runtime contract hashes missing")
    for rel, expected in hashes.items():
        path = ROOT / rel
        if not path.exists():
            raise GateError(f"missing frozen file: {rel}")
        if sha(path).lower() != str(expected).lower():
            raise GateError(f"SHA mismatch: {rel}")

    ledger_rel = ".kiro/specs/task005-replication-inference/task005_fmcg_v32_formal_seed_ledger1.0.csv"
    ledger = ROOT / ledger_rel
    with ledger.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != FORMAL_N:
        raise GateError("formal ledger must contain exactly 10 rows")
    if [row["formal_block_id"] for row in rows] != [
        f"F{i:03d}" for i in range(1, FORMAL_N + 1)
    ]:
        raise GateError("formal block identities mismatch")

    config = (ROOT / "configs" / "models_config.yaml").read_text(encoding="utf-8-sig")
    for token in (
        "model: qwen-plus",
        "temperature: 0.3",
        'api_key: "__FROM_ENV_DASHSCOPE_API_KEY__"',
    ):
        if token not in config:
            raise GateError(f"model config mismatch: {token!r}")

    return runtime


def validate_authorization(runtime: dict, token: str) -> dict:
    if not AUTHORIZATION.exists():
        raise GateError("execution authorization artifact absent")
    authorization = read_json(AUTHORIZATION)
    if authorization.get("formal_execution_authorized") is not True:
        raise GateError("formal_execution_authorized != true")
    if authorization.get("formal_batch_id") != BATCH_ID:
        raise GateError("authorization batch mismatch")
    if authorization.get("source_head") != EXPECTED_HEAD:
        raise GateError("authorization source head mismatch")
    if authorization.get("maximum_attempt_blocks") != FORMAL_N:
        raise GateError("authorization maximum block count mismatch")
    if authorization.get("replacement_allowed") is not False:
        raise GateError("replacement must remain forbidden")
    if authorization.get("optional_stopping_allowed") is not False:
        raise GateError("optional stopping must remain forbidden")
    if authorization.get("bound_artifact_sha256") != runtime.get(
        "authorization_bindings"
    ):
        raise GateError("authorization artifact bindings mismatch")
    if str(authorization.get("runtime_contract_sha256", "")).lower() != sha(
        RUNTIME_CONTRACT
    ).lower():
        raise GateError("authorization runtime-contract SHA mismatch")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if digest.lower() != str(authorization.get("runtime_token_sha256", "")).lower():
        raise GateError("runtime token mismatch")
    return authorization


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--activate")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    runtime = validate_static()

    if args.check_only:
        authorized = False
        auth_status = "ABSENT"
        if AUTHORIZATION.exists():
            auth = read_json(AUTHORIZATION)
            authorized = auth.get("formal_execution_authorized") is True
            auth_status = (
                "AUTHORIZED_ARTIFACT_PRESENT"
                if authorized
                else "PRESENT_NOT_AUTHORIZED"
            )
        result = {
            "schema_version": "task005_fmcg_v32_activation_gate_check1.0",
            "status": (
                "READY_FOR_EXECUTION_TOKEN"
                if authorized
                else "READY_BUT_NOT_AUTHORIZED"
            ),
            "formal_batch_id": BATCH_ID,
            "attempt_blocks": FORMAL_N,
            "source_head": EXPECTED_HEAD,
            "runtime_files_verified": True,
            "authorization_status": auth_status,
            "real_llm_calls": 0,
            "external_api_calls": 0,
            "execution_started": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 0

    token = args.activate or ""
    if not token:
        raise GateError("--execute requires --activate with the later-issued token")
    validate_authorization(runtime, token)

    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise GateError("formal output directory already non-empty")

    env = os.environ.copy()
    env["TASK005_FMCG_V32_FORMAL_RUNTIME_TOKEN"] = token
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--execute-batch",
            "--output-dir",
            str(args.output_dir.resolve()),
        ],
        cwd=ROOT,
        env=env,
        check=False,
    )
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
