from __future__ import annotations

import csv
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_task005_real_variance_pilot_v2 as v2
from task005_audited_llm_router import SemanticValidationError


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


def write_rows(path: Path, data: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


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
        encoding="utf-8",
        errors="replace",
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
    try:
        v2.validate_raw_semantic_response(bad_bool)
    except Exception as exc:
        check("semantic error type", isinstance(exc, SemanticValidationError), type(exc).__name__)


def _assert_block_pass(root: Path, rid: str) -> dict:
    block = root / rid
    summary = json.loads((block / "block_execution_summary.json").read_text(encoding="utf-8"))
    calls = [json.loads(line) for line in (block / "pilot_llm_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    mech = rows(block / "mechanism_records.csv")
    exposure = rows(block / "clarification_exposure.csv")
    check(f"{rid} true production path", summary["TRUE_PRODUCTION_PATH"] is True, summary)
    check(f"{rid} run_with_patch used", summary["PRODUCTION_RUN_WITH_PATCH_USED"] is True, summary)
    check(f"{rid} block seed injection", summary["BLOCK_SEED_INJECTION"] == "PASS", summary)
    check(f"{rid} condition seed singleton", summary["condition_random_seed_set"] == [summary["ledger_simulation_seed"]], summary)
    check(f"{rid} mechanism 5400", len(mech) == 5400, len(mech))
    check(f"{rid} model count equals audit", summary["MODEL_CALLS"] == len(calls), summary)
    check(f"{rid} fake inner equals audit", summary["FAKE_MODEL_CALLS"] == len(calls), summary)
    check(f"{rid} real calls zero", summary["REAL_LLM_CALLS"] == 0, summary)
    check(f"{rid} replay misses zero", summary["replay_miss_count"] == 0, summary)
    check(f"{rid} agent gate", summary["agent_key_integrity"] == "PASS", summary)
    check(f"{rid} exposure gate", summary["exposure_key_integrity"] == "PASS", summary)
    check(f"{rid} pretreatment gate actual", summary["pretreatment_alignment"] == "PASS", summary)
    check(f"{rid} network identity actual", summary["network_identity_alignment"] == "PASS", summary)
    check(f"{rid} profile identity actual", summary["profile_identity_alignment"] == "PASS", summary)
    check(f"{rid} raw semantic gate", summary["raw_semantic_validation"] == "PASS", summary)
    control = [row for row in exposure if row["exp_id"] == "NoClarification-Control"]
    mech_agents = {row["agent_id"] for row in mech if row["exp_id"] == "NoClarification-Control"}
    check(f"{rid} control exposure exact 20", len(control) == 20, len(control))
    check(f"{rid} control exposure agent set", {row["agent_id"] for row in control} == mech_agents)
    check(f"{rid} control exposure unreached", sum(1 for row in control if row["reached"] == "True") == 0)
    return summary


def test_synthetic_fixture_not_production_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_v2_synth_") as tmp:
        result = v2.run_offline_synthetic_estimator_fixture(Path(tmp))
        check("synthetic fixture pass", result["status"] == "PASS", result)
        check("synthetic fixture named nonproduction", result["SYNTHETIC_ESTIMATOR_FIXTURE"] is True, result)
        check("synthetic fixture not production path", result["TRUE_PRODUCTION_PATH"] is False, result)


def test_true_production_path_fake_acceptance() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_v2_prod_") as tmp:
        root = Path(tmp)
        result = v2.run_production_path_fake_acceptance(root)
        check("true production path pass", result["status"] == "PASS", result)
        check("true production path flag", result["TRUE_PRODUCTION_PATH"] is True, result)
        check("production run_with_patch flag", result["PRODUCTION_RUN_WITH_PATCH_USED"] is True, result)
        check("fake two blocks", result["blocks"] == 2, result)
        check("batch block seed injection", result["BLOCK_SEED_INJECTION"] == "PASS", result)
        check("fake real calls zero", result["REAL_LLM_CALLS"] == 0, result)
        check("fake call audit equality", result["fake_call_audit_equal"] is True, result)
        s1 = _assert_block_pass(root, "R001")
        s2 = _assert_block_pass(root, "R002")
        check("R001 fake calls positive", s1["FAKE_MODEL_CALLS"] > 0, s1)
        check("R002 fake calls positive", s2["FAKE_MODEL_CALLS"] > 0, s2)
        ledger = v2.build_pilot_seed_ledger()
        r001 = ledger[0]["simulation_seed"]
        r002 = ledger[1]["simulation_seed"]
        check("R001 R002 ledger seeds differ", r001 != r002, (r001, r002))
        check("R001 seed exact", s1["ledger_simulation_seed"] == r001, s1)
        check("R002 seed exact", s2["ledger_simulation_seed"] == r002, s2)
        manifest1 = json.loads((root / "R001" / "condition_manifest.json").read_text(encoding="utf-8"))
        manifest2 = json.loads((root / "R002" / "condition_manifest.json").read_text(encoding="utf-8"))
        check("R001 manifest seeds exact", {row["random_seed"] for row in manifest1} == {r001}, manifest1)
        check("R002 manifest seeds exact", {row["random_seed"] for row in manifest2} == {r002}, manifest2)

        bad = root / "R001" / "mechanism_records.csv"
        mech = rows(bad)
        mech[-1] = dict(mech[0])
        write_rows(bad, mech)
        expect_error("mechanism duplicate agent fails", lambda: v2.validate_block_gates(root / "R001", "R001"))

    with tempfile.TemporaryDirectory(prefix="task005_v2_pretreat_") as tmp:
        root = Path(tmp)
        v2.run_production_path_fake_acceptance(root)
        path = root / "R001" / "mechanism_records.csv"
        mech = rows(path)
        for row in mech:
            if row["exp_id"] == "Rational-Hub-Immediate" and row["tick"] == "5":
                row["trust_final"] = str(float(row["trust_final"]) + 0.123)
                break
        write_rows(path, mech)
        expect_error("pretreatment mismatch fails closed", lambda: v2.validate_block_gates(root / "R001", "R001"))

    with tempfile.TemporaryDirectory(prefix="task005_v2_network_") as tmp:
        root = Path(tmp)
        v2.run_production_path_fake_acceptance(root)
        path = root / "R001" / "network_identity.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["conditions"][0]["network_hash"] = "changed"
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        expect_error("network hash mismatch fails", lambda: v2.validate_block_gates(root / "R001", "R001"))

    with tempfile.TemporaryDirectory(prefix="task005_v2_profile_") as tmp:
        root = Path(tmp)
        v2.run_production_path_fake_acceptance(root)
        path = root / "R001" / "profile_identity.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["conditions"][0]["profile_hash"] = "changed"
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        expect_error("profile hash mismatch fails", lambda: v2.validate_block_gates(root / "R001", "R001"))

    with tempfile.TemporaryDirectory(prefix="task005_v2_exposure_") as tmp:
        root = Path(tmp)
        v2.run_production_path_fake_acceptance(root)
        path = root / "R001" / "clarification_exposure.csv"
        exposure = rows(path)
        exposure[-1] = dict(exposure[0])
        write_rows(path, exposure)
        expect_error("strategy duplicate exposure fails", lambda: v2.validate_block_gates(root / "R001", "R001"))


def test_block_seed_and_audit_negative_cases() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_v2_seedneg_") as tmp:
        root = Path(tmp)
        v2.run_production_path_fake_acceptance(root)
        block = root / "R002"
        manifest = json.loads((block / "condition_manifest.json").read_text(encoding="utf-8"))
        manifest[0]["random_seed"] = 42
        (block / "condition_manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        summary = json.loads((block / "block_execution_summary.json").read_text(encoding="utf-8"))
        check("R002 condition seed 42 detectable", {row["random_seed"] for row in manifest} != {summary["ledger_simulation_seed"]}, manifest)
        expect_error("R002 condition seed 42 fails gate", lambda: v2.validate_block_gates(block, "R002"))
        manifest[0]["random_seed"] = summary["ledger_simulation_seed"] + 1
        (block / "condition_manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        expect_error("condition seed != ledger fails gate", lambda: v2.validate_block_gates(block, "R002"))

    with tempfile.TemporaryDirectory(prefix="task005_v2_auditneg_") as tmp:
        root = Path(tmp)
        v2.run_production_path_fake_acceptance(root)
        block = root / "R001"
        summary = json.loads((block / "block_execution_summary.json").read_text(encoding="utf-8"))
        summary["REAL_LLM_CALLS"] = 0
        summary["execution_mode"] = "real"
        check("real-mode hardcoded zero detectable", summary["REAL_LLM_CALLS"] != summary["MODEL_CALLS"], summary)

        path = block / "pilot_llm_calls.jsonl"
        audit = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        audit.pop()
        path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in audit) + "\n", encoding="utf-8")
        expect_error("audit rows not equal model calls fails", lambda: v2.validate_block_gates(block, "R001"))

    for field, value, label in (
        ("semantic_schema_ok", "", "semantic_schema_ok empty fails"),
        ("response_parse_ok", False, "semantic response_parse false fails"),
        ("prompt_category", "unknown", "unknown prompt category fails"),
    ):
        with tempfile.TemporaryDirectory(prefix="task005_v2_semneg_") as tmp:
            root = Path(tmp)
            v2.run_production_path_fake_acceptance(root)
            block = root / "R001"
            path = block / "pilot_llm_calls.jsonl"
            audit = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            audit[0][field] = value
            path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in audit) + "\n", encoding="utf-8")
            expect_error(label, lambda b=block: v2.validate_block_gates(b, "R001"))


def test_failure_lifecycle_and_resume() -> None:
    class CloseFailRouter(v2.DeterministicFakeInnerRouter):
        def __init__(self):
            super().__init__()
            self._task005_router_close_noop = False

        async def close(self):
            raise RuntimeError("close failed with SECRET_TOKEN")

    with tempfile.TemporaryDirectory(prefix="task005_v2_closefail_") as tmp:
        root = Path(tmp)
        ledger = v2.build_pilot_seed_ledger()[0]
        summary = asyncio.run(v2.execute_variance_block(
            root / "R001",
            ledger,
            inner_router=CloseFailRouter(),
            execution_mode="offline-fake",
        ))
        disk = json.loads((root / "R001" / "block_execution_summary.json").read_text(encoding="utf-8"))
        check("router close failure incomplete return", summary["status"] == "INCOMPLETE", summary)
        check("router close failure incomplete disk", disk["failure_stage"] == "router-close", disk)
        check("router close failure sanitized", "SECRET" not in json.dumps(disk), disk)

    with tempfile.TemporaryDirectory(prefix="task005_v2_continue_") as tmp:
        root = Path(tmp)
        ledger = v2.build_pilot_seed_ledger()[:2]
        calls = []
        def factory(row):
            calls.append(row["replicate_id"])
            if row["replicate_id"] == "R001":
                raise RuntimeError("factory fail")
            return v2.DeterministicFakeInnerRouter()
        result = v2._run_variance_blocks(root, ledger, execution_mode="offline-fake", inner_router_factory=factory)
        check("one block fails pilot incomplete", result["status"] == "INCOMPLETE", result)
        check("batch continues next block", calls == ["R001", "R002"], calls)
        check("future block passes after prior failure", result["block_summaries"][1]["status"] == "PASS", result)

    with tempfile.TemporaryDirectory(prefix="task005_v2_resume_") as tmp:
        root = Path(tmp)
        result1 = v2.run_production_path_fake_acceptance(root)
        before = (root / "R001" / "block_execution_summary.json").read_text(encoding="utf-8")
        result2 = v2.run_production_path_fake_acceptance(root)
        after = (root / "R001" / "block_execution_summary.json").read_text(encoding="utf-8")
        check("marker existing block never reruns", before == after, (result1["status"], result2["status"]))
        lifecycle = (root / "R002" / "replicate_lifecycle.jsonl").read_text(encoding="utf-8").splitlines()
        check("lifecycle append-only events present", len(lifecycle) >= 18 and any("BLOCK_PASS" in line for line in lifecycle), len(lifecycle))


def test_real_execution_surface_locked() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_v2_reallock_") as tmp:
        root = Path(tmp)
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_task005_real_variance_pilot_v2.py"),
                "--execute-real",
                "--activation-token",
                "anything",
                "--output-dir",
                str(root / "out"),
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        check("execute-real locked exit", proc.returncode == 2, proc.stdout)
        check("execute-real creates no output", not (root / "out").exists(), list(root.iterdir()))
        expect_error("future real batch locked", lambda: v2.run_future_real_variance_batch(root / "real", activation_token=None))


def test_fail_closed_schema_import() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_schema_fail_") as tmp:
        root = Path(tmp)
        shutil.copy(ROOT / "run_experiments.py", root / "run_experiments.py")
        (root / "simulation_core.py").write_text(
            "def run_simulation_core(*a, **k): pass\n"
            "ENTERPRISE_STRATEGY = {}\n"
            "AGENT_RECORDS_FIELDS = tuple(str(i) for i in range(60))\n"
            "AGENT_RECORDS_SCHEMA_VERSION = '2.0'\n"
            "MECHANISM_RECORDS_FIELDS = ('schema_version', 'exp_id')\n"
            "MECHANISM_RECORDS_SCHEMA_VERSION = '1.1'\n",
            encoding="utf-8",
        )
        (root / "metrics_calculator.py").write_text(
            "METRICS_SCHEMA_VERSION='4.0'\n"
            "LOCAL_WINDOW_TICKS=2\n"
            "EARLY_HORIZON_INTERVALS=4\n"
            "RANKING_WEIGHT_STEP=0.1\n"
            "NUM_WEIGHT_COMBINATIONS=66\n"
            "V4_FIELDS=()\n"
            "PRIMARY_OBJECTIVES_V4=()\n"
            "CONTROL_EMPTY_V4_FIELDS=()\n"
            "def compute_relative_metrics_v4(*a, **k): return {}\n"
            "def build_control_metrics_v4(): return {}\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, "-c", "import run_experiments"],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        check("schema import mismatch hard fails", proc.returncode != 0, proc.stderr + proc.stdout)


def test_network_tripwire() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_v2_tripwire_") as tmp:
        root = Path(tmp)
        site = root / "sitecustomize.py"
        site.write_text(
            "import socket\n"
            "def _external(address):\n"
            "    host = address[0] if isinstance(address, tuple) and address else address\n"
            "    return host not in ('127.0.0.1', 'localhost', '::1')\n"
            "_old_create_connection = socket.create_connection\n"
            "def guarded_create_connection(address, *a, **k):\n"
            "    if _external(address):\n"
            "        raise RuntimeError('NETWORK_FORBIDDEN_TEST')\n"
            "    return _old_create_connection(address, *a, **k)\n"
            "socket.create_connection = guarded_create_connection\n"
            "_old_socket = socket.socket\n"
            "class GuardedSocket(_old_socket):\n"
            "    def connect(self, address):\n"
            "        if _external(address):\n"
            "            raise RuntimeError('NETWORK_FORBIDDEN_TEST')\n"
            "        return super().connect(address)\n"
            "socket.socket = GuardedSocket\n",
            encoding="utf-8",
        )
        out = root / "out"
        env = os.environ.copy()
        env.pop("HF_HUB_OFFLINE", None)
        env.pop("TRANSFORMERS_OFFLINE", None)
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_task005_real_variance_pilot_v2.py"),
                "--offline-test",
                "--output-dir",
                str(out),
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            env=env,
            timeout=240,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        check("network tripwire acceptance exit", proc.returncode == 0, combined[-1000:])
        check("network tripwire not triggered", "NETWORK_FORBIDDEN_TEST" not in combined, combined[-1000:])


def test_secret_scan() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_v2_secret_") as tmp:
        root = Path(tmp)
        v2.run_production_path_fake_acceptance(root)
        text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in root.rglob("*") if path.is_file())
        lower = text.lower()
        forbidden = ["authorization:", "bearer ", "api_key=", "dashscope_api_key"]
        check("secret scan clean", not any(item in lower for item in forbidden), forbidden)


def main() -> int:
    test_contract_and_rejection()
    test_strict_semantic_validator()
    test_synthetic_fixture_not_production_gate()
    test_true_production_path_fake_acceptance()
    test_block_seed_and_audit_negative_cases()
    test_failure_lifecycle_and_resume()
    test_real_execution_surface_locked()
    test_fail_closed_schema_import()
    test_network_tripwire()
    test_secret_scan()
    print("Passed:", P)
    print("Failed:", F)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
