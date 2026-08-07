#!/usr/bin/env python
"""TASK_005 formal fixed-cohort runner acceptance tests."""

from __future__ import annotations

import csv
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
import run_replications as runner
from replication_config import read_seed_ledger_csv


FORMAL_ID = "task005-formal-readiness-v1"
PYTHON = sys.executable


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
        print("TASK_005 FORMAL RUNNER ACCEPTANCE RESULTS")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        return 1 if self.failed else 0


class FakeCompleted:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.stdout = "fake child stdout\n"
        self.stderr = ""


def make_request(root: Path, *, retry_failed: bool = False) -> dict:
    return formal.build_formal_request(
        SimpleNamespace(
            replication_id=FORMAL_ID,
            master_seed=20260807,
            llm_mode="deterministic-mock",
            llm_seed_supported="unknown",
            provider_model="",
            provider_system_fingerprint="",
            output_root=str(root),
            python_executable=PYTHON,
            retry_failed=retry_failed,
        )
    )


def success_result() -> dict:
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


def failed_result() -> dict:
    return {
        "validation_passed": False,
        "status": "failed",
        "condition_success_count": 0,
        "condition_error_count": 0,
        "postprocess_error_count": 0,
        "replay_alignment_violated": False,
        "network_status": "",
        "failure_stage": "subprocess",
        "failure_type": "SyntheticFailure",
        "failure_message": "synthetic failure",
    }


def manifest_rows(batch: Path) -> list[dict[str, str]]:
    with (batch / "replicate_manifest.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        return list(csv.DictReader(handle))


def valid_count(batch: Path) -> int:
    return sum(
        row["status"] == "succeeded"
        and row["validation_passed"].lower() == "true"
        for row in manifest_rows(batch)
    )


class PatchRunner:
    def __init__(self, *, fail_first_r007: bool = False) -> None:
        self.fail_first_r007 = fail_first_r007
        self.calls: list[dict[str, Any]] = []
        self._old_run = runner.subprocess.run
        self._old_validate = runner.validate_block_artifacts

    def __enter__(self):
        def fake_run(argv, **kwargs):
            self.calls.append(
                {
                    "argv": list(argv),
                    "env": dict(kwargs.get("env", {})),
                }
            )
            return FakeCompleted()

        def fake_validate(block_dir, ledger_row, *, subprocess_exit_code: int):
            rid = str(ledger_row["replicate_id"])
            attempt = Path(block_dir).name
            if (
                self.fail_first_r007
                and rid == "R007"
                and attempt.endswith("attempt_001")
            ):
                return failed_result()
            return success_result()

        runner.subprocess.run = fake_run
        runner.validate_block_artifacts = fake_validate
        return self

    def __exit__(self, *_exc):
        runner.subprocess.run = self._old_run
        runner.validate_block_artifacts = self._old_validate


def check_exact_plan(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        req = make_request(root)
        state = runner._load_or_initialize_batch(
            req, root / req["replication_id"]
        )
        formal._assert_formal_state(state, req)
        ids = [row["replicate_id"] for row in state["ledger"]]
        v.check("CASE A ledger rows 24", len(ids) == 24, 24, len(ids))
        v.check("CASE A ids exact", ids == list(formal.FORMAL_REPLICATE_IDS), "R001-R024", ids)
        v.check("CASE A max_parallel 1", req["max_parallel"] == 1, 1, req["max_parallel"])
        v.check("CASE A no R025", "R025" not in ids, "absent", ids[-3:])


def check_24_success(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        with PatchRunner() as patched:
            exit_code = formal.run_formal_replication_batch(make_request(root))
        batch = root / FORMAL_ID
        ids = [row["replicate_id"] for row in manifest_rows(batch)]
        v.check("CASE B exit 0", exit_code == 0, 0, exit_code)
        v.check("CASE B 24 child starts", len(patched.calls) == 24, 24, len(patched.calls))
        v.check("CASE B valid 24", valid_count(batch) == 24, 24, valid_count(batch))
        v.check("CASE B no R025", ids == list(formal.FORMAL_REPLICATE_IDS), "R001-R024", ids)


def check_failure_and_retry(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        with PatchRunner(fail_first_r007=True) as patched:
            exit_code = formal.run_formal_replication_batch(make_request(root))
        batch = root / FORMAL_ID
        rows = manifest_rows(batch)
        r007 = next(row for row in rows if row["replicate_id"] == "R007")
        v.check("CASE C exit nonzero", exit_code == 1, 1, exit_code)
        v.check("CASE C 23 valid", valid_count(batch) == 23, 23, valid_count(batch))
        v.check("CASE C R007 failed", r007["status"] == "failed", "failed", r007)
        v.check("CASE C no replacement", len(rows) == 24 and not (batch / "blocks" / "R025").exists(), "24 rows/no R025", rows[-1])
        v.check("CASE C failure evidence", (batch / "failures" / "R007" / "attempt_001").is_dir(), "present", "absent")
        v.check("CASE C ran whole cohort once", len(patched.calls) == 24, 24, len(patched.calls))

        ledger = {row["replicate_id"]: row for row in read_seed_ledger_csv(batch / "seed_ledger.csv")}
        expected = ledger["R007"]
        with PatchRunner() as retry_patch:
            retry_exit = formal.run_formal_replication_batch(
                make_request(root, retry_failed=True)
            )
        retry_rows = manifest_rows(batch)
        retry_r007 = next(row for row in retry_rows if row["replicate_id"] == "R007")
        v.check("CASE D retry exit 0", retry_exit == 0, 0, retry_exit)
        v.check("CASE D only R007 rerun", len(retry_patch.calls) == 1 and "--replicate-id" in retry_patch.calls[0]["argv"] and retry_patch.calls[0]["argv"][retry_patch.calls[0]["argv"].index("--replicate-id") + 1] == "R007", "one R007 call", retry_patch.calls)
        v.check("CASE D attempt 2", retry_r007["attempt_count"] == "2", "2", retry_r007)
        v.check("CASE D valid 24", valid_count(batch) == 24, 24, valid_count(batch))
        argv = retry_patch.calls[0]["argv"]
        seed_checks = {
            "--simulation-seed": expected["simulation_seed"],
            "--requested-llm-seed": expected["requested_llm_seed"],
            "--python-hash-seed": expected["python_hash_seed"],
        }
        seed_ok = all(
            argv[argv.index(flag) + 1] == str(value)
            for flag, value in seed_checks.items()
        )
        v.check("CASE D retry seeds identical", seed_ok, seed_checks, argv)

        with PatchRunner() as resume_patch:
            resume_exit = formal.run_formal_replication_batch(make_request(root))
        v.check("CASE H succeeded resume exit 0", resume_exit == 0, 0, resume_exit)
        v.check("CASE H succeeded blocks not rerun", len(resume_patch.calls) == 0, 0, len(resume_patch.calls))


def check_attacks(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        req25 = dict(make_request(root))
        req25["num_replicates"] = 25
        state = runner._load_or_initialize_batch(req25, root / FORMAL_ID)
        v.check("CASE E attack fixture has 25", len(state["ledger"]) == 25, 25, len(state["ledger"]))
        with PatchRunner() as patched:
            exit_code = formal.run_formal_replication_batch(make_request(root))
        v.check("CASE E 25 ledger rejected", exit_code == 2, 2, exit_code)
        v.check("CASE E no child starts", len(patched.calls) == 0, 0, len(patched.calls))

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        req = make_request(root)
        runner._load_or_initialize_batch(req, root / FORMAL_ID)
        ledger_path = root / FORMAL_ID / "seed_ledger.csv"
        rows = list(csv.DictReader(ledger_path.open(newline="", encoding="utf-8")))
        rows[6]["simulation_seed"] = str(int(rows[6]["simulation_seed"]) + 1)
        with ledger_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        with PatchRunner() as patched:
            exit_code = formal.run_formal_replication_batch(make_request(root))
        v.check("CASE F seed mutation rejected", exit_code == 2, 2, exit_code)
        v.check("CASE F no child starts", len(patched.calls) == 0, 0, len(patched.calls))

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        req = make_request(root)
        runner._load_or_initialize_batch(req, root / FORMAL_ID)
        manifest_path = root / FORMAL_ID / "replicate_manifest.csv"
        rows = list(csv.DictReader(manifest_path.open(newline="", encoding="utf-8")))
        rows[0]["replicate_id"] = "P001"
        with manifest_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        with PatchRunner() as patched:
            exit_code = formal.run_formal_replication_batch(make_request(root))
        v.check("CASE G engineering manifest rejected", exit_code == 2, 2, exit_code)
        v.check("CASE G no child starts", len(patched.calls) == 0, 0, len(patched.calls))


def main() -> int:
    v = Reporter()
    check_exact_plan(v)
    check_24_success(v)
    check_failure_and_retry(v)
    check_attacks(v)
    return v.summary()


if __name__ == "__main__":
    raise SystemExit(main())
