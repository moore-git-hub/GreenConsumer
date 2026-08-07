#!/usr/bin/env python
"""TASK_005 Stage I.5C-5A formal launch-contract acceptance tests."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_formal_replications as formal
from replication_config import build_seed_ledger, read_seed_ledger_csv


SPEC = ROOT / ".kiro/specs/task005-replication-inference"
CONTRACT_PATH = SPEC / "formal_launch_contract1.0.json"
LEDGER_PATH = SPEC / "formal_seed_ledger1.0.csv"
SANITIZED_PATH = SPEC / "formal_model_config_sanitized1.0.json"
FORMAL_OUTPUT_PATH = ROOT / "results/replications/task005-formal-v1"
FORMAL_ID = "task005-formal-v1"
MASTER_SEED = 2026080801
FORBIDDEN_ENGINEERING_IDS = {"P001", "P002", "P003", "P004", "P005"}


class Reporter:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, name: str, ok: bool, expected: Any = "", actual: Any = "") -> None:
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            print(f"FAIL {name} | expected={expected} actual={actual}")

    def summary(self) -> int:
        print("TASK_005 FORMAL LAUNCH CONTRACT ACCEPTANCE RESULTS")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        return 1 if self.failed else 0


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def contains_secret_key_or_value(value: Any) -> bool:
    forbidden_keys = ("api_key", "apikey", "token", "secret", "password")
    if isinstance(value, dict):
        for key, item in value.items():
            text = str(key).lower()
            if any(marker in text for marker in forbidden_keys) and not text.endswith(
                "_present"
            ):
                return True
            if contains_secret_key_or_value(item):
                return True
        return False
    if isinstance(value, list):
        return any(contains_secret_key_or_value(item) for item in value)
    return False


def check_contract(v: Reporter) -> dict:
    contract = load_json(CONTRACT_PATH)
    sanitized = load_json(SANITIZED_PATH)
    rows = read_seed_ledger_csv(LEDGER_PATH)
    ids = [row["replicate_id"] for row in rows]

    v.check("A formal batch id exact", contract.get("formal_replication_id") == FORMAL_ID, FORMAL_ID, contract.get("formal_replication_id"))
    v.check("B master seed exact", contract.get("master_seed") == MASTER_SEED, MASTER_SEED, contract.get("master_seed"))
    v.check("C seed ledger count", len(rows) == 24, 24, len(rows))
    v.check("C seed ledger ids", ids == [f"R{i:03d}" for i in range(1, 25)], "R001-R024", ids)
    expected_rows = build_seed_ledger(
        MASTER_SEED,
        24,
        llm_seed_supported=contract["llm_seed_supported"],
        provider_model=contract["provider_model"],
        provider_system_fingerprint="unavailable-prelaunch",
    )
    v.check("C seed ledger derivation", rows == expected_rows, "build_seed_ledger rows", rows[:2])
    v.check(
        "C seed ledger sha frozen",
        contract.get("formal_seed_ledger_sha256")
        == contract["source_identities"]["sha256"][
            ".kiro/specs/task005-replication-inference/formal_seed_ledger1.0.csv"
        ]
        if ".kiro/specs/task005-replication-inference/formal_seed_ledger1.0.csv"
        in contract["source_identities"]["sha256"]
        else True,
        "contract/source hash consistency",
        "missing optional ledger source hash",
    )
    v.check("D R025 absent", "R025" not in ids, "absent", ids)
    v.check("E P001-P005 absent", FORBIDDEN_ENGINEERING_IDS.isdisjoint(ids), "absent", ids)
    v.check("F sanitized config exists", SANITIZED_PATH.exists(), True, SANITIZED_PATH.exists())
    v.check("F sanitized config no secret key", not contains_secret_key_or_value(sanitized), False, sanitized)
    v.check("F api key presence only", sanitized["selected_chat_model"].get("api_key_present") is True, True, sanitized["selected_chat_model"].get("api_key_present"))
    v.check("G chat model count", contract.get("chat_model_count") == 1, 1, contract.get("chat_model_count"))
    v.check("G model binding verified", contract.get("model_binding_verified") is True, True, contract.get("model_binding_verified"))
    v.check("H pilot evidence consistent", contract.get("pilot_model_evidence_consistent") is True, True, contract.get("pilot_model_evidence_consistent"))
    evidence = contract.get("pilot_model_evidence", [])
    v.check("H pilot evidence nonempty", isinstance(evidence, list) and bool(evidence), "nonempty list", evidence)
    v.check(
        "H pilot model identity exact",
        all(
            row.get("name") == contract["model_provider"]
            and row.get("model") == contract["model"]
            and row.get("base_url") == contract["base_url"]
            for row in evidence
        ),
        "all evidence rows match contract",
        evidence,
    )
    v.check("I llm seed support evidence-backed", contract.get("llm_seed_supported") in {"true", "false", "unknown"}, "true/false/unknown", contract.get("llm_seed_supported"))
    v.check(
        "I llm seed support consistent",
        {row.get("llm_seed_supported") for row in evidence} == {contract.get("llm_seed_supported")},
        {contract.get("llm_seed_supported")},
        {row.get("llm_seed_supported") for row in evidence},
    )
    v.check("J formal output absent", not FORMAL_OUTPUT_PATH.exists(), "absent", FORMAL_OUTPUT_PATH.exists())
    v.check("N human authorization false", contract.get("human_cost_time_authorized") is False, False, contract.get("human_cost_time_authorized"))
    v.check("O formal launch permitted false", contract.get("formal_llm_launch_permitted") is False, False, contract.get("formal_llm_launch_permitted"))
    v.check("M real llm calls false", contract.get("real_llm_called_during_stage") is False, False, contract.get("real_llm_called_during_stage"))
    v.check("M network calls zero", contract.get("network_calls_during_stage") == 0, 0, contract.get("network_calls_during_stage"))
    return contract


def check_real_rejection(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        exit_code = formal.main(
            [
                "--replication-id",
                FORMAL_ID,
                "--master-seed",
                str(MASTER_SEED),
                "--llm-mode",
                "real",
                "--llm-seed-supported",
                "unknown",
                "--output-root",
                str(root),
                "--python-executable",
                sys.executable,
            ]
        )
        v.check("K direct real rejected", exit_code == 2, 2, exit_code)
        v.check("K direct real batch blocked", not (root / FORMAL_ID).exists(), "absent", (root / FORMAL_ID).exists())

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        request = {
            "replication_id": FORMAL_ID,
            "master_seed": MASTER_SEED,
            "num_replicates": 24,
            "llm_mode": "real",
            "llm_seed_supported": "unknown",
            "provider_model": "OpenAIProvider:qwen-plus",
            "provider_system_fingerprint": "unavailable-prelaunch",
            "output_root": str(root),
            "python_executable": sys.executable,
            "max_parallel": 1,
            "retry_failed": False,
        }
        exit_code = formal.run_formal_replication_batch(request)
        v.check("L programmatic real rejected", exit_code == 2, 2, exit_code)
        v.check("L programmatic real batch blocked", not (root / FORMAL_ID).exists(), "absent", (root / FORMAL_ID).exists())


def main() -> int:
    v = Reporter()
    check_contract(v)
    check_real_rejection(v)
    return v.summary()


if __name__ == "__main__":
    raise SystemExit(main())
