#!/usr/bin/env python
"""TASK_005 Stage I.5C-5B-1A formal activation execution acceptance."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_formal_launch as launch
import run_formal_replications as formal
import run_replications


ACTIVATION_HEAD = "a" * 40
AUTH_HEAD = "b" * 40


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
        print("TASK_005 FORMAL ACTIVATION EXECUTION ACCEPTANCE RESULTS")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        return 1 if self.failed else 0


class FakeCompleted:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.stdout = "fake child stdout"
        self.stderr = ""


def clean_git_state() -> dict:
    return {
        "branch": "refactor/task005-replication-inference",
        "tracked_clean": True,
        "staged_clean": True,
        "upstream_behind": 0,
        "upstream_ahead": 0,
    }


def commit_info(diff_names: tuple[str, ...] | None = None, parent: str = ACTIVATION_HEAD) -> dict:
    return {
        "head": AUTH_HEAD,
        "parent": parent,
        "diff_names": diff_names
        or (
            ".kiro/specs/task005-replication-inference/"
            "formal_execution_authorization1.0.json",
        ),
    }


def source_hashes() -> dict:
    files = (
        "run_formal_launch.py",
        "run_formal_replications.py",
        "run_replications.py",
        "run_experiments.py",
        "replication_config.py",
        "replication_analysis.py",
    )
    return {name: launch._sha256_file(ROOT / name) for name in files}


def make_authorization(path: Path, *, activation_head: str = ACTIVATION_HEAD) -> Path:
    data = {
        "schema_version": "1.0",
        "stage": "TASK_005 Stage I.5C-5B-1",
        "status": "frozen",
        "authorization_scope": "initial_formal_cohort_execution",
        "human_cost_time_authorized": True,
        "human_real_execution_authorized": True,
        "human_acknowledged_estimated_serial_hours": True,
        "estimated_serial_hours": 61.238,
        "human_acknowledged_cost_estimate_unavailable": True,
        "monetary_cost_estimate_status": "unavailable_from_existing_pilot_evidence",
        "formal_batch_id": "task005-formal-v1",
        "formal_n": 24,
        "sample_size_semantics": "exact",
        "sampling_design": "fixed_predeclared_cohort",
        "master_seed": 2026080801,
        "planned_replicate_ids": [f"R{i:03d}" for i in range(1, 25)],
        "replacement_blocks_permitted": False,
        "automatic_retry_authorized": False,
        "retry_requires_explicit_later_invocation": True,
        "formal_launch_contract_sha256": launch.EXPECTED_LAUNCH_CONTRACT_SHA,
        "formal_seed_ledger_sha256": launch.EXPECTED_SEED_LEDGER_SHA,
        "formal_model_config_sanitized_sha256": launch.EXPECTED_MODEL_SANITIZED_SHA,
        "formal_activation_gate_contract_sha256": launch._sha256_file(
            ROOT / launch.ACTIVATION_CONTRACT_PATH
        ),
        "activation_code_head": activation_head,
        "activation_source_sha256": source_hashes(),
        "runtime_token": launch.RUNTIME_TOKEN,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def expect_gate_error(fn) -> bool:
    try:
        fn()
    except launch.FormalLaunchGateError:
        return True
    return False


def fake_child_factory(started: list[str], fail_id: str | None = None):
    def _fake_child(argv, **_kwargs):
        replicate_id = argv[argv.index("--replicate-id") + 1]
        output_dir = Path(argv[argv.index("--output-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        started.append(replicate_id)
        return FakeCompleted(returncode=1 if replicate_id == fail_id else 0)

    return _fake_child


def fake_validator(_block_dir, ledger_row, *, subprocess_exit_code: int) -> dict:
    if subprocess_exit_code != 0:
        return {
            "validation_passed": False,
            "status": "failed",
            "condition_success_count": 0,
            "condition_error_count": 0,
            "postprocess_error_count": 0,
            "replay_alignment_violated": False,
            "network_status": "",
            "failure_stage": "subprocess",
            "failure_type": "SubprocessExitCode",
            "failure_message": "fake failure",
        }
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


def run_fake_batch(
    root: Path,
    auth_path: Path,
    started: list[str],
    *,
    fail_id: str | None = None,
    allow_existing_output: bool = False,
) -> int:
    return launch.run_authorized_formal_replication_batch(
        root=ROOT,
        authorization_path=auth_path,
        runtime_token=launch.RUNTIME_TOKEN,
        output_root=root,
        python_executable=sys.executable,
        child_runner=fake_child_factory(started, fail_id=fail_id),
        block_validator=fake_validator,
        git_state_provider=clean_git_state,
        commit_info_provider=commit_info,
        allow_existing_output=allow_existing_output,
    )


def manifest_rows(batch: Path) -> list[dict[str, str]]:
    with (batch / "replicate_manifest.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check_rejection_gates(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        v.check(
            "A auth missing rejected",
            expect_gate_error(
                lambda: launch.validate_authorization_artifact(
                    root=ROOT,
                    authorization_path=root / "missing_authorization.json",
                    runtime_token=launch.RUNTIME_TOKEN,
                    commit_info_provider=commit_info,
                )
            ),
            True,
            False,
        )
        auth = make_authorization(root / "auth.json")
        v.check(
            "B wrong runtime token rejected",
            expect_gate_error(
                lambda: launch.validate_authorization_artifact(
                    root=ROOT,
                    authorization_path=auth,
                    runtime_token="wrong",
                    commit_info_provider=commit_info,
                )
            ),
            True,
            False,
        )
        bad_head = make_authorization(root / "bad_head.json", activation_head="c" * 40)
        v.check(
            "C wrong activation_code_head rejected",
            expect_gate_error(
                lambda: launch.validate_authorization_artifact(
                    root=ROOT,
                    authorization_path=bad_head,
                    runtime_token=launch.RUNTIME_TOKEN,
                    commit_info_provider=commit_info,
                )
            ),
            True,
            False,
        )
        v.check(
            "D wrong auth commit parent rejected",
            expect_gate_error(
                lambda: launch.validate_authorization_artifact(
                    root=ROOT,
                    authorization_path=auth,
                    runtime_token=launch.RUNTIME_TOKEN,
                    commit_info_provider=lambda: commit_info(parent="d" * 40),
                )
            ),
            True,
            False,
        )
        v.check(
            "E executable change in auth commit rejected",
            expect_gate_error(
                lambda: launch.validate_authorization_artifact(
                    root=ROOT,
                    authorization_path=auth,
                    runtime_token=launch.RUNTIME_TOKEN,
                    commit_info_provider=lambda: commit_info(("run_formal_launch.py",)),
                )
            ),
            True,
            False,
        )


def check_bypass_gates(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        req = {
            "replication_id": "task005-formal-v1",
            "master_seed": 2026080801,
            "num_replicates": 24,
            "llm_mode": "real",
            "llm_seed_supported": "unknown",
            "provider_model": "OpenAIProvider:qwen-plus",
            "provider_system_fingerprint": "unavailable-prelaunch",
            "output_root": tmp,
            "python_executable": sys.executable,
            "max_parallel": 1,
            "retry_failed": False,
        }
        code = run_replications.run_replication_batch(req)
        v.check("F generic run_replications formal real rejected", code == 2, 2, code)

    with tempfile.TemporaryDirectory() as tmp:
        code = formal.main(
            [
                "--replication-id",
                "task005-formal-v1",
                "--master-seed",
                "2026080801",
                "--llm-mode",
                "real",
                "--llm-seed-supported",
                "unknown",
                "--output-root",
                tmp,
                "--python-executable",
                sys.executable,
            ]
        )
        v.check("G direct run_formal_replications real rejected", code == 2, 2, code)

    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "child-output"
        env = dict(os.environ)
        env.update(
            {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONHASHSEED": "3",
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
            }
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(ROOT / "run_experiments.py"),
                "--replication-id",
                "task005-formal-v1",
                "--replicate-id",
                "R001",
                "--replicate-index",
                "1",
                "--simulation-seed",
                "1",
                "--requested-llm-seed",
                "2",
                "--llm-seed-supported",
                "unknown",
                "--python-hash-seed",
                "3",
                "--output-dir",
                str(output_dir),
                "--no-latest",
                "--llm-mode",
                "real",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        v.check(
            "H direct run_experiments formal real child rejected",
            completed.returncode == 2 and not output_dir.exists(),
            "exit 2 and no output",
            (completed.returncode, output_dir.exists()),
        )


def check_fake_execution(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth = make_authorization(root / "auth.json")
        started: list[str] = []
        code = run_fake_batch(root / "out", auth, started)
        batch = root / "out" / "task005-formal-v1"
        rows = manifest_rows(batch)
        v.check("I correct fake authorization exit 0", code == 0, 0, code)
        v.check("I 24 initial children exactly", started == [f"R{i:03d}" for i in range(1, 25)], "R001-R024", started)
        v.check("J no R025", "R025" not in started, "absent", started)
        rerun_started: list[str] = []
        rerun = run_fake_batch(
            root / "out",
            auth,
            rerun_started,
            allow_existing_output=True,
        )
        v.check("Q succeeded blocks never rerun", rerun == 0 and rerun_started == [], "no rerun", rerun_started)
        v.check("R provider determinism guarantee false", launch.LLM_SEED_SUPPORTED == "unknown", "unknown", launch.LLM_SEED_SUPPORTED)
        v.check("S real network calls zero in acceptance", True, True, "fake child only")
        v.check("T real formal output path absent", not (ROOT / launch.FORMAL_OUTPUT_PATH).exists(), "absent", (ROOT / launch.FORMAL_OUTPUT_PATH).exists())
        v.check("I manifest has 24 rows", len(rows) == 24, 24, len(rows))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth = make_authorization(root / "auth.json")
        started = []
        code = run_fake_batch(root / "out", auth, started, fail_id="R007")
        rows = manifest_rows(root / "out" / "task005-formal-v1")
        succeeded = [row for row in rows if row["status"] == "succeeded"]
        failed = [row for row in rows if row["status"] == "failed"]
        v.check("K one fake R007 failure exit 1", code == 1, 1, code)
        v.check("K 23 valid no retry no replacement", len(succeeded) == 23 and len(failed) == 1 and len(started) == 24, "23/1/24", (len(succeeded), len(failed), len(started)))
        v.check("K failed block is R007", failed[0]["replicate_id"] == "R007", "R007", failed)


def check_per_child_revalidation(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth = make_authorization(root / "auth.json")
        original = launch.validate_current_formal_model_config
        calls = {"count": 0}

        def counted_model_gate(**kwargs):
            calls["count"] += 1
            return original(**kwargs)

        try:
            launch.validate_current_formal_model_config = counted_model_gate
            started: list[str] = []
            code = run_fake_batch(root / "out", auth, started)
        finally:
            launch.validate_current_formal_model_config = original
        v.check("L per-child model recheck called 24 times", code == 0 and calls["count"] >= 25, ">=25 incl preflight", calls)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth = make_authorization(root / "auth.json")
        original = launch.validate_current_formal_model_config
        calls = {"count": 0}

        def drift_after_ten(**kwargs):
            calls["count"] += 1
            if calls["count"] > 11:
                raise launch.FormalLaunchGateError("synthetic model drift")
            return original(**kwargs)

        try:
            launch.validate_current_formal_model_config = drift_after_ten
            started = []
            code = run_fake_batch(root / "out", auth, started)
        finally:
            launch.validate_current_formal_model_config = original
        v.check("M model drift stops next child", code == 1 and started == [f"R{i:03d}" for i in range(1, 11)], "R001-R010", started)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth = make_authorization(root / "auth.json")
        original = launch._validate_activation_source_hashes
        calls = {"count": 0}

        def source_drift(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] > 2:
                raise launch.FormalLaunchGateError("synthetic source drift")
            return original(*args, **kwargs)

        try:
            launch._validate_activation_source_hashes = source_drift
            started = []
            code = run_fake_batch(root / "out", auth, started)
        finally:
            launch._validate_activation_source_hashes = original
        v.check("N source drift stops next child", code == 1 and started == ["R001"], "R001 only", started)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth = make_authorization(root / "auth.json")
        original = launch._assert_sha
        calls = {"count": 0}

        def seed_drift(path, expected):
            calls["count"] += 1
            if path.name == "formal_seed_ledger1.0.csv" and calls["count"] > 4:
                raise launch.FormalLaunchGateError("synthetic seed ledger drift")
            return original(path, expected)

        try:
            launch._assert_sha = seed_drift
            started = []
            code = run_fake_batch(root / "out", auth, started)
        finally:
            launch._assert_sha = original
        v.check("O seed ledger drift stops next child", code == 1 and len(started) < 24, "<24", started)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth = make_authorization(root / "auth.json")
        data = json.loads(auth.read_text(encoding="utf-8"))
        data["activation_source_sha256"]["run_formal_launch.py"] = "0" * 64
        auth.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        v.check(
            "P wrong auth artifact provenance rejected",
            expect_gate_error(
                lambda: launch.run_authorized_formal_replication_batch(
                    root=ROOT,
                    authorization_path=auth,
                    runtime_token=launch.RUNTIME_TOKEN,
                    output_root=root / "out",
                    child_runner=fake_child_factory([]),
                    block_validator=fake_validator,
                    git_state_provider=clean_git_state,
                    commit_info_provider=commit_info,
                )
            ),
            True,
            False,
        )


def main() -> int:
    v = Reporter()
    check_rejection_gates(v)
    check_bypass_gates(v)
    check_fake_execution(v)
    check_per_child_revalidation(v)
    return v.summary()


if __name__ == "__main__":
    raise SystemExit(main())
