from __future__ import annotations

import asyncio
import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import run_task005_real_manipulation_pilot_v2 as pilot
import simulation_core


P = 0
F = 0


def check(name: str, condition: bool, actual=None) -> None:
    global P, F
    if condition:
        P += 1
        print("PASS", name)
    else:
        F += 1
        print("FAIL", name, actual)


def _row(agent_id, evidence, credibility, empathy, arousal, valence, topic=0.9):
    return {
        "agent_id": agent_id,
        "clarification_detected_by_plan": True,
        "semantic_evidence_strength": evidence,
        "semantic_credibility": credibility,
        "semantic_perceived_empathy": empathy,
        "semantic_arousal": arousal,
        "semantic_valence": valence,
        "semantic_topic_relevance": topic,
        "semantic_hypocrisy_perceived": False,
    }


def _semantic_response(**overrides):
    payload = {
        "valence": 0.1,
        "arousal": 0.4,
        "credibility": 0.7,
        "evidence_strength": 0.8,
        "topic_relevance": 0.9,
        "perceived_empathy": 0.6,
        "hypocrisy_perceived": False,
        "importance": 5,
        "reasoning": "The statement is relevant and understandable.",
    }
    payload.update(overrides)
    return json.dumps(payload)


def _reflect_prompt():
    return (
        "Return JSON only. Do NOT decide buying or posting: "
        '{"valence": <float>, "arousal": <float>, "credibility": <float>, '
        '"evidence_strength": <float>, "topic_relevance": <float>, '
        '"perceived_empathy": <float>, "hypocrisy_perceived": <boolean>, '
        '"importance": <float>, "reasoning": <string>}'
    )


class _FakeInnerRouter:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    async def chat(self, prompt):
        self.calls += 1
        return self.response


def test_identity_and_contract() -> None:
    ledger = pilot.build_pilot_seed_ledger()
    check("pilot id v2", pilot.PILOT_ID == "task005-real-manipulation-pilot-v2", pilot.PILOT_ID)
    check("master seed v2", pilot.MASTER_SEED == 2026080903, pilot.MASTER_SEED)
    check("replicates exact", tuple(row["replicate_id"] for row in ledger) == ("R001", "R002"), ledger)
    check("conditions exact", tuple(cfg.exp_id for cfg in pilot.select_pilot_conditions()) == pilot.PILOT_CONDITION_IDS)
    check("schema 1.2", simulation_core.MECHANISM_RECORDS_SCHEMA_VERSION == "1.2")
    check("perceived empathy persisted", "semantic_perceived_empathy" in simulation_core.MECHANISM_RECORDS_FIELDS)
    contract = (
        ROOT
        / ".kiro/specs/task005-replication-inference/"
        / "real_llm_manipulation_check_pilot_v2_contract1.0.json"
    ).read_text(encoding="utf-8")
    check("contract no real calls", '"real_llm_calls_in_this_stage": false' in contract)
    check("contract valence descriptive", '"semantic_valence_role": "descriptive_only"' in contract)


def test_v2_manipulation_gates() -> None:
    rational = [
        _row("A1", 0.90, 0.88, 0.20, 0.30, -0.80),
        _row("A2", 0.86, 0.80, 0.25, 0.35, 0.10),
    ]
    empathy = [
        _row("A1", 0.50, 0.58, 0.86, 0.75, -0.95),
        _row("A2", 0.55, 0.60, 0.82, 0.70, -0.20),
    ]
    pairs = []
    for replicate_id in pilot.ALLOWED_REPLICATE_IDS:
        pairs.extend(pilot.compute_manipulation_pairs(replicate_id, rational, empathy))
    check("matched pairs", len(pairs) == 4, pairs)
    check("evidence direction", all(row["D_evidence"] > 0 for row in pairs), pairs)
    check("credibility direction", all(row["D_credibility"] > 0 for row in pairs), pairs)
    check("empathy direction", all(row["D_empathy"] > 0 for row in pairs), pairs)
    check("arousal direction", all(row["D_arousal"] > 0 for row in pairs), pairs)
    check("valence may be negative", any(row["D_valence_descriptive"] < 0 for row in pairs), pairs)
    summary = pilot.summarize_manipulation_by_block(pairs)
    check("direction gate pass", summary["DIRECTION_GATE"] == "PASS", summary)
    check("floor pass", summary["MANIPULATION_STRENGTH"] == "PASS", summary)
    check("valence descriptive in summary", summary["semantic_valence_role"] == "descriptive_only", summary)


def test_range_validation_and_no_zip_truncation() -> None:
    rational = [_row("A1", 0.9, 0.8, 0.2, 0.3, 0.0)]
    empathy = [_row("A1", 0.5, 0.6, 1.5, 0.7, 0.0)]
    try:
        pilot.compute_manipulation_pairs("R001", rational, empathy)
    except pilot.PilotContractError:
        check("perceived empathy range fails", True)
    else:
        check("perceived empathy range fails", False)
    try:
        pilot.compute_manipulation_pairs("R001", rational, [])
    except pilot.PilotContractError:
        check("matched reach mismatch fails", True)
    else:
        check("matched reach mismatch fails", False)


def test_raw_semantic_validator() -> None:
    invalid_cases = []
    missing = json.loads(_semantic_response())
    missing.pop("perceived_empathy")
    invalid_cases.append(("missing perceived_empathy", json.dumps(missing)))
    invalid_cases.extend(
        [
            ("perceived empathy high", _semantic_response(perceived_empathy=1.5)),
            ("perceived empathy low", _semantic_response(perceived_empathy=-0.1)),
            ("nan fails", _semantic_response(perceived_empathy=float("nan"))),
            ("infinity fails", _semantic_response(arousal=float("inf"))),
            ("hypocrisy string fails", _semantic_response(hypocrisy_perceived="false")),
            ("importance high fails", _semantic_response(importance=11)),
        ]
    )
    for label, response in invalid_cases:
        try:
            pilot.validate_raw_semantic_response(response)
        except pilot.PilotSemanticValidationError:
            check(label, True)
        else:
            check(label, False)

    valid = _semantic_response(perceived_empathy=0.333333, importance=10)
    parsed = pilot.validate_raw_semantic_response(valid)
    check("valid raw semantic passes", parsed["perceived_empathy"] == 0.333333, parsed)


def test_validated_router_raw_response_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_pilot_v2_router_") as tmp:
        call_log = Path(tmp) / "calls.jsonl"
        lifecycle = Path(tmp) / "lifecycle.jsonl"
        response = _semantic_response(perceived_empathy=0.42)
        router = pilot.ValidatedAuditedRealRouter(
            _FakeInnerRouter(response),
            pilot_id=pilot.PILOT_ID,
            replicate_id="R001",
            requested_llm_seed=123,
            call_log_path=call_log,
            lifecycle_path=lifecycle,
        )
        returned = asyncio.run(router.chat(_reflect_prompt()))
        check("valid response unchanged", returned == response, returned)
        rows = [json.loads(line) for line in call_log.read_text(encoding="utf-8").splitlines()]
        check("audit semantic ok", rows[0]["semantic_schema_ok"] is True, rows)
        check("first chat lifecycle", "FIRST_CHAT_STARTED" in lifecycle.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="task005_pilot_v2_router_bad_") as tmp:
        call_log = Path(tmp) / "calls.jsonl"
        router = pilot.ValidatedAuditedRealRouter(
            _FakeInnerRouter(_semantic_response(perceived_empathy=1.5)),
            pilot_id=pilot.PILOT_ID,
            replicate_id="R001",
            requested_llm_seed=123,
            call_log_path=call_log,
        )
        try:
            asyncio.run(router.chat(_reflect_prompt()))
        except pilot.PilotSemanticValidationError:
            check("invalid router raises", True)
        else:
            check("invalid router raises", False)
        rows = [json.loads(line) for line in call_log.read_text(encoding="utf-8").splitlines()]
        check("audit semantic fail", rows[0]["semantic_schema_ok"] is False, rows)
        check("audit validation error type", rows[0]["validation_error_type"] == "PilotSemanticValidationError", rows)


def test_child_pre_chat_failure_artifacts() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_pilot_v2_") as tmp:
        root = Path(tmp)
        ledger = pilot.build_pilot_seed_ledger()[0]
        old_hash = os.environ.get("PYTHONHASHSEED")
        os.environ["PYTHONHASHSEED"] = str(ledger["python_hash_seed"])

        def raises(_seed):
            raise RuntimeError("router-build-secret-free")

        try:
            summary = asyncio.run(
                pilot._execute_replicate_block(root, ledger, router_builder=raises)
            )
        finally:
            if old_hash is None:
                os.environ.pop("PYTHONHASHSEED", None)
            else:
                os.environ["PYTHONHASHSEED"] = old_hash
        block = root / "R001"
        check("summary incomplete", summary["status"] == "INCOMPLETE", summary)
        check("attempt count one", summary["attempt_count"] == 1, summary)
        check("real calls zero", summary["real_llm_calls"] == 0, summary)
        check("block summary exists", (block / "block_execution_summary.json").exists())
        check("lifecycle exists", (block / "replicate_lifecycle.jsonl").exists())
        check("stdout audit exists", (block / "child_stdout_sanitized.log").exists())
        check("stderr audit exists", (block / "child_stderr_sanitized.log").exists())
        check("call log exists", (block / "pilot_llm_calls.jsonl").exists())
        lifecycle = (block / "replicate_lifecycle.jsonl").read_text(encoding="utf-8")
        check("router build started marked", "REAL_ROUTER_BUILD_STARTED" in lifecycle, lifecycle)
        check("first chat not started", "FIRST_CHAT_STARTED" not in lifecycle, lifecycle)


def test_cli_no_real_and_dry_run() -> None:
    env = dict(os.environ)
    env.pop(pilot.TASK005_LLM_API_KEY_ENV, None)
    cmd = [sys.executable, "-X", "utf8", "run_task005_real_manipulation_pilot_v2.py", "--execute-real"]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
    check("cli real rejected", proc.returncode == 2 and pilot.REAL_MODE_REJECTION in proc.stdout, proc.stdout)
    with tempfile.TemporaryDirectory(prefix="task005_pilot_v2_dry_") as tmp:
        cmd = [
            sys.executable,
            "-X",
            "utf8",
            "run_task005_real_manipulation_pilot_v2.py",
            "--dry-run",
            "--output-dir",
            tmp,
        ]
        proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
        check("dry run passes", proc.returncode == 0, proc.stdout + proc.stderr)
        rows = list(csv.DictReader((Path(tmp) / "pilot_manifest.csv").open(encoding="utf-8")))
        check("dry manifest 2x3", len(rows) == 6, len(rows))


def test_offline_import_network_tripwire() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_pilot_v2_tripwire_") as tmp:
        tripwire = Path(tmp) / "sitecustomize.py"
        tripwire.write_text(
            "import socket\n"
            "def _fail(*args, **kwargs):\n"
            "    raise RuntimeError('NETWORK_TRIPWIRE')\n"
            "socket.socket.connect = _fail\n"
            "socket.create_connection = _fail\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
            env.pop(key, None)
        env["PYTHONPATH"] = tmp + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "run_task005_real_manipulation_pilot_v2.py",
                "--offline-test",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        combined = proc.stdout + proc.stderr
        check("network tripwire passes", proc.returncode == 0, combined)
        check("network tripwire no attempt", "NETWORK_TRIPWIRE" not in combined, combined)


def main() -> int:
    test_identity_and_contract()
    test_v2_manipulation_gates()
    test_range_validation_and_no_zip_truncation()
    test_raw_semantic_validator()
    test_validated_router_raw_response_contract()
    test_child_pre_chat_failure_artifacts()
    test_cli_no_real_and_dry_run()
    test_offline_import_network_tripwire()
    print("Passed:", P)
    print("Failed:", F)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
