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


def test_identity_and_contract() -> None:
    ledger = pilot.build_pilot_seed_ledger()
    check("pilot id v2", pilot.PILOT_ID == "task005-real-manipulation-pilot-v2", pilot.PILOT_ID)
    check("master seed v2", pilot.MASTER_SEED == 2026080903, pilot.MASTER_SEED)
    check("replicates exact", tuple(row["replicate_id"] for row in ledger) == ("R001", "R002"), ledger)
    check("conditions exact", tuple(cfg.exp_id for cfg in pilot.select_pilot_conditions()) == pilot.PILOT_CONDITION_IDS)
    check("schema 1.1", simulation_core.MECHANISM_RECORDS_SCHEMA_VERSION == "1.1")
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


def main() -> int:
    test_identity_and_contract()
    test_v2_manipulation_gates()
    test_range_validation_and_no_zip_truncation()
    test_child_pre_chat_failure_artifacts()
    test_cli_no_real_and_dry_run()
    print("Passed:", P)
    print("Failed:", F)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
