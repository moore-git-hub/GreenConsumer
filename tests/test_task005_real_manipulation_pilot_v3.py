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
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import run_task005_real_manipulation_pilot_v3 as pilot


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


def test_identity_contract() -> None:
    ledger = pilot.build_pilot_seed_ledger()
    check("pilot id v3", pilot.PILOT_ID == "task005-real-manipulation-pilot-v3", pilot.PILOT_ID)
    check("master seed v3", pilot.MASTER_SEED == 2026080904, pilot.MASTER_SEED)
    check("replicates exact", tuple(row["replicate_id"] for row in ledger) == ("R001", "R002"), ledger)
    check("conditions exact", tuple(cfg.exp_id for cfg in pilot.select_pilot_conditions()) == pilot.PILOT_CONDITION_IDS)
    contract = (
        ROOT
        / ".kiro/specs/task005-replication-inference/"
        / "real_llm_manipulation_check_pilot_v3_contract1.0.json"
    ).read_text(encoding="utf-8")
    check("contract primary evidence", '"D_evidence"' in contract)
    check("contract arousal descriptive", '"D_arousal_descriptive"' in contract)


def test_primary_gate_only() -> None:
    rational = [
        _row("A1", 0.90, 0.88, 0.20, 0.90, 0.90),
        _row("A2", 0.86, 0.80, 0.25, 0.80, 0.80),
    ]
    empathy = [
        _row("A1", 0.50, 0.58, 0.86, 0.20, -0.90),
        _row("A2", 0.55, 0.60, 0.82, 0.10, -0.80),
    ]
    pairs = []
    for replicate_id in pilot.ALLOWED_REPLICATE_IDS:
        pairs.extend(pilot.compute_manipulation_pairs(replicate_id, rational, empathy))
    check("arousal negative descriptive", all(row["D_arousal_descriptive"] < 0 for row in pairs), pairs)
    check("valence negative descriptive", all(row["D_valence_descriptive"] < 0 for row in pairs), pairs)
    summary = pilot.summarize_manipulation_by_block(pairs)
    check("negative arousal does not fail", summary["DIRECTION_GATE"] == "PASS", summary)
    check("negative valence does not fail", summary["MANIPULATION_STRENGTH"] == "PASS", summary)

    bad = []
    bad_r = [_row("A1", 0.9, 0.8, 0.70, 0.5, 0.0)]
    bad_e = [_row("A1", 0.5, 0.6, 0.60, 0.5, 0.0)]
    for replicate_id in pilot.ALLOWED_REPLICATE_IDS:
        bad.extend(pilot.compute_manipulation_pairs(replicate_id, bad_r, bad_e))
    bad_summary = pilot.summarize_manipulation_by_block(bad)
    check("negative empathy fails direction", bad_summary["DIRECTION_GATE"] == "FAIL", bad_summary)


def test_floor_boundary() -> None:
    weak_pairs = [
        {"replicate_id": rid, "agent_id": f"{rid}-A", "D_evidence": 0.06, "D_credibility": 0.06, "D_empathy": 0.049,
         "D_arousal_descriptive": -0.9, "D_valence_descriptive": -0.9,
         "rational_topic_relevance": 0.8, "empathy_topic_relevance": 0.8,
         "rational_hypocrisy_perceived": False, "empathy_hypocrisy_perceived": False}
        for rid in pilot.ALLOWED_REPLICATE_IDS
    ]
    pass_pairs = [dict(row, D_empathy=0.05) for row in weak_pairs]
    check("pooled empathy 0.049 weak", pilot.summarize_manipulation_by_block(weak_pairs)["MANIPULATION_STRENGTH"] == "WEAK")
    check("pooled empathy 0.050 pass", pilot.summarize_manipulation_by_block(pass_pairs)["MANIPULATION_STRENGTH"] == "PASS")


def test_raw_semantic_validation() -> None:
    invalid = json.loads(_semantic_response())
    invalid.pop("perceived_empathy")
    try:
        pilot.validate_raw_semantic_response(json.dumps(invalid))
    except pilot.PilotSemanticValidationError:
        check("missing perceived empathy fails", True)
    else:
        check("missing perceived empathy fails", False)
    valid = _semantic_response(perceived_empathy=0.42)
    with tempfile.TemporaryDirectory(prefix="task005_v3_router_") as tmp:
        router = pilot.ValidatedAuditedRealRouter(
            _FakeInnerRouter(valid),
            pilot_id=pilot.PILOT_ID,
            replicate_id="R001",
            requested_llm_seed=123,
            call_log_path=Path(tmp) / "calls.jsonl",
        )
        check("valid response unchanged", asyncio.run(router.chat(_reflect_prompt())) == valid)


def test_seed_serialization_gate() -> None:
    ledger = {row["replicate_id"]: row for row in pilot.build_pilot_seed_ledger()}
    with tempfile.TemporaryDirectory(prefix="task005_v3_seed_gate_") as tmp:
        root = Path(tmp)
        old_hash = os.environ.get("PYTHONHASHSEED")
        try:
            for rid in ("R001", "R002"):
                os.environ["PYTHONHASHSEED"] = str(ledger[rid]["python_hash_seed"])

                def raises(_seed):
                    raise RuntimeError("stop-after-seed")

                summary = asyncio.run(
                    pilot._execute_replicate_block(root, ledger[rid], router_builder=raises)
                )
                block = root / rid
                lifecycle = (block / "replicate_lifecycle.jsonl").read_text(encoding="utf-8")
                check(f"{rid} reached seed ledger", "SEED_LEDGER_WRITTEN" in lifecycle, lifecycle)
                with (block / "seed_ledger.csv").open(encoding="utf-8", newline="") as f:
                    rows = list(csv.DictReader(f))
                check(f"{rid} seed CSV one row", len(rows) == 1, rows)
                check(f"{rid} index exact", int(rows[0]["replicate_index"]) == ledger[rid]["replicate_index"], rows)
                check(f"{rid} id exact", rows[0]["replicate_id"] == rid, rows)
                for field in ("simulation_seed", "requested_llm_seed", "python_hash_seed"):
                    check(f"{rid} {field} exact", int(rows[0][field]) == ledger[rid][field], rows)
                check(f"{rid} incomplete after fake build", summary["status"] == "INCOMPLETE", summary)
        finally:
            if old_hash is None:
                os.environ.pop("PYTHONHASHSEED", None)
            else:
                os.environ["PYTHONHASHSEED"] = old_hash


def test_offline_import_network_tripwire() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_pilot_v3_tripwire_") as tmp:
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
            [sys.executable, "-X", "utf8", "run_task005_real_manipulation_pilot_v3.py", "--offline-test"],
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
    test_identity_contract()
    test_primary_gate_only()
    test_floor_boundary()
    test_raw_semantic_validation()
    test_seed_serialization_gate()
    test_offline_import_network_tripwire()
    print("Passed:", P)
    print("Failed:", F)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
