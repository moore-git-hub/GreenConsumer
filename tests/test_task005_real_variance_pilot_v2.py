from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_task005_real_variance_pilot_v2 as v2


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


def expect_error(name: str, fn) -> None:
    try:
        fn()
    except Exception:
        check(name, True)
        return
    check(name, False, "expected exception")


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_contract_and_rejection() -> None:
    contract = json.loads(
        (ROOT / ".kiro/specs/task005-replication-inference/real_llm_variance_pilot_v2_contract1.0.json")
        .read_text(encoding="utf-8")
    )
    preflight = v2.preflight()
    check("v2 pilot id", contract["pilot_id"] == v2.PILOT_ID)
    check("v2 master seed", contract["master_seed"] == 2026081002)
    check("v2 10 blocks", tuple(contract["replicates"]) == tuple(f"R{i:03d}" for i in range(1, 11)))
    check("v2 9 conditions", preflight["conditions_per_block"] == 9, preflight)
    check("v2 execution unauthorized", contract["execution_authorized"] is False)
    check("v2 no p", contract["p_values"] is False)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "run_task005_real_variance_pilot_v2.py"), "--execute-real"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    check("v2 real rejected exit", proc.returncode == 2, proc.stdout)
    check("v2 real rejected label", v2.REAL_MODE_REJECTION in proc.stdout, proc.stdout)


def test_strict_semantic_validator() -> None:
    valid = {
        "valence": 0,
        "arousal": 0,
        "credibility": 1,
        "evidence_strength": 0.5,
        "topic_relevance": 0.5,
        "perceived_empathy": 0.5,
        "hypocrisy_perceived": False,
        "importance": 5,
        "reasoning": "ok",
    }
    v2.validate_raw_semantic_response(valid)
    check("valid semantic passes", True)
    missing = dict(valid)
    missing.pop("reasoning")
    expect_error("semantic missing field fails", lambda: v2.validate_raw_semantic_response(missing))
    bad_range = dict(valid, arousal=1.1)
    expect_error("semantic out of range fails", lambda: v2.validate_raw_semantic_response(bad_range))
    bad_bool = dict(valid, hypocrisy_perceived="false")
    expect_error("semantic bool type fails", lambda: v2.validate_raw_semantic_response(bad_bool))


def test_fake_production_path() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_v2_fake_") as tmp:
        root = Path(tmp)
        result = v2.run_offline_fake_production_path(root)
        check("fake path pass", result["status"] == "PASS", result)
        check("fake two blocks", result["blocks"] == 2, result)
        check("fake real calls zero", result["real_llm_calls"] == 0, result)
        for rid in ("R001", "R002"):
            block = root / rid
            summary = json.loads((block / "block_execution_summary.json").read_text(encoding="utf-8"))
            calls = rows(block / "pilot_llm_calls.csv")
            mech = rows(block / "mechanism_records.csv")
            exposure = rows(block / "clarification_exposure.csv")
            check(f"{rid} mechanism 5400", len(mech) == 5400, len(mech))
            check(f"{rid} call count equals audit", summary["real_llm_calls"] == len(calls), summary)
            check(f"{rid} agent gate", summary["agent_key_integrity"] == "PASS", summary)
            check(f"{rid} exposure gate", summary["exposure_key_integrity"] == "PASS", summary)
            check(f"{rid} pretreatment gate", summary["pretreatment_alignment"] == "PASS", summary)
            check(f"{rid} network hash gate", summary["network_identity_alignment"] == "PASS", summary)
            check(f"{rid} profile hash gate", summary["profile_identity_alignment"] == "PASS", summary)
            check(f"{rid} raw semantic gate", summary["raw_semantic_validation"] == "PASS", summary)
            control = [row for row in exposure if row["exp_id"] == "NoClarification-Control"]
            check(f"{rid} control exposure exact 20", len(control) == 20, len(control))
            check(f"{rid} control exposure unreached", sum(1 for row in control if row["reached"] == "True") == 0)
        bad = root / "R001" / "mechanism_records.csv"
        mech = rows(bad)
        mech[-1] = dict(mech[0])
        with bad.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(mech[0]))
            writer.writeheader()
            writer.writerows(mech)
        expect_error("mechanism duplicate agent fails", lambda: v2.validate_block_gates(root / "R001", "R001"))

    with tempfile.TemporaryDirectory(prefix="task005_v2_mismatch_") as tmp:
        root = Path(tmp)
        v2.run_offline_fake_production_path(root)
        path = root / "R001" / "mechanism_records.csv"
        mech = rows(path)
        mech[0]["network_identity_hash"] = "changed"
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(mech[0]))
            writer.writeheader()
            writer.writerows(mech)
        expect_error("network hash mismatch fails", lambda: v2.validate_block_gates(root / "R001", "R001"))

    with tempfile.TemporaryDirectory(prefix="task005_v2_profile_") as tmp:
        root = Path(tmp)
        v2.run_offline_fake_production_path(root)
        path = root / "R001" / "mechanism_records.csv"
        mech = rows(path)
        mech[0]["profile_identity_hash"] = "changed"
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(mech[0]))
            writer.writeheader()
            writer.writerows(mech)
        expect_error("profile hash mismatch fails", lambda: v2.validate_block_gates(root / "R001", "R001"))

    with tempfile.TemporaryDirectory(prefix="task005_v2_exposure_") as tmp:
        root = Path(tmp)
        v2.run_offline_fake_production_path(root)
        path = root / "R001" / "clarification_exposure.csv"
        exposure = rows(path)
        exposure[-1] = dict(exposure[0])
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(exposure[0]))
            writer.writeheader()
            writer.writerows(exposure)
        expect_error("strategy duplicate exposure fails", lambda: v2.validate_block_gates(root / "R001", "R001"))


def main() -> int:
    test_contract_and_rejection()
    test_strict_semantic_validator()
    test_fake_production_path()
    print("Passed:", P)
    print("Failed:", F)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
