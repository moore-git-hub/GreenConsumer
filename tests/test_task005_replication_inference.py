#!/usr/bin/env python
"""TASK_005 Phase 1 frozen acceptance baseline.

This script intentionally runs without pytest. In Phase 1 the production
replication modules are not implemented, so S2-S11 may fail for missing future
APIs. The harness itself must still run to completion and print a full summary.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib
import json
import os
import py_compile
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / ".kiro" / "specs" / "task005-replication-inference" / "design0.1.md"
FIXTURE = ROOT / "tests" / "fixtures" / "task005" / "seed_ledger_cases.json"

REPLICATION_SCHEMA_VERSION = "1.0"
SEED_DERIVATION_VERSION = "sha256-v1"
SEED_NAMESPACE_PREFIX = "task005"
CACHE_SCOPE = "replicate-block-only"
EXECUTION_MODE = "serial-subprocess"
MAX_PARALLEL_BLOCKS = 1
LATEST_POLICY = "disabled"
BLOCK_FAILURE_POLICY = "fail-closed-complete-9"
SEED_MIN = 1
SEED_MAX = 2**32 - 1
MATRIX_VERSION = "3.0"
METRICS_SCHEMA_VERSION = "4.0"
CONDITION_COUNT = 9
CONTROL_EXP_ID = "NoClarification-Control"

EXECUTION_ORDER = (
    "NoClarification-Control",
    "Empathy-Hub-Delayed",
    "Empathy-Hub-Immediate",
    "Empathy-Random-Delayed",
    "Empathy-Random-Immediate",
    "Rational-Hub-Delayed",
    "Rational-Hub-Immediate",
    "Rational-Random-Delayed",
    "Rational-Random-Immediate",
)

LEDGER_FIELDS = (
    "replication_schema_version",
    "seed_derivation_version",
    "master_seed",
    "replicate_index",
    "replicate_id",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "matrix_version",
    "metrics_schema_version",
    "condition_count",
    "control_exp_id",
    "execution_order",
    "cache_scope",
    "profile_seed",
    "network_seed",
    "target_seed",
    "python_hash_seed",
    "provider_model",
    "provider_system_fingerprint",
)

MANIFEST_FIELDS = (
    "replication_id",
    "replicate_id",
    "replicate_index",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "python_hash_seed",
    "status",
    "attempt_count",
    "block_dir",
    "started_at",
    "finished_at",
    "subprocess_exit_code",
    "condition_success_count",
    "condition_error_count",
    "postprocess_error_count",
    "replay_alignment_violated",
    "network_status",
    "validation_passed",
    "failure_stage",
    "failure_type",
    "failure_message",
)

STATES = ("planned", "running", "succeeded", "failed", "invalid", "interrupted")
ALLOWED_TRANSITIONS = {
    ("planned", "running"),
    ("running", "succeeded"),
    ("running", "failed"),
    ("running", "invalid"),
    ("running", "interrupted"),
    ("failed", "running"),
    ("invalid", "running"),
    ("interrupted", "running"),
}
ENV_REQUIRED = (
    "PYTHONUTF8=1",
    "PYTHONIOENCODING=utf-8",
    "PYTHONHASHSEED=<ledger python_hash_seed>",
    "MPLBACKEND=Agg",
    "TOKENIZERS_PARALLELISM=false",
)
MOCK_ENV_REQUIRED = (
    "HF_HUB_OFFLINE=1",
    "TRANSFORMERS_OFFLINE=1",
    "HF_DATASETS_OFFLINE=1",
    "HF_HUB_DISABLE_TELEMETRY=1",
)
RUN_EXPERIMENTS_ARGS = (
    "--replication-id",
    "--replicate-id",
    "--replicate-index",
    "--simulation-seed",
    "--requested-llm-seed",
    "--llm-seed-supported",
    "--python-hash-seed",
    "--output-dir",
    "--no-latest",
    "--llm-mode",
)
LLM_MODES = ("real", "deterministic-mock")
LLM_SEED_SUPPORTED_VALUES = ("true", "false", "unknown")
REPLICATION_METADATA_FIELDS = (
    "schema_version",
    "replication_id",
    "replicate_id",
    "replicate_index",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "python_hash_seed",
    "cache_scope",
    "execution_mode",
    "latest_policy",
    "engineering_acceptance_only",
)
GROUP_ORDER = (
    "T0-syntax",
    "S0-fixture",
    "S1-design-contract",
    "S2-version-constants",
    "S3-seed-derivation",
    "S4-ledger-build-validation",
    "S5-ledger-csv-roundtrip",
    "S6-execution-order-cache-scope",
    "S7-block-state-resume",
    "S8-subprocess-spec",
    "S9-block-artifact-contract",
    "S10-failure-policy",
    "S11-provenance-secret-safety",
    "S12-task003-task004-invariance",
    "S13-runtime-pilot",
)


class Reporter:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str, str, str, str]] = []

    def check(self, group: str, name: str, ok: bool, expected: Any = "", actual: Any = "", note: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        self.items.append((status, group, name, str(expected), str(actual), note))
        if not ok:
            print(f"FAIL {group} | {name} | expected={expected} actual={actual} {note}")

    def warn(self, group: str, name: str, note: str) -> None:
        self.items.append(("WARN", group, name, "", "", note))
        print(f"WARN {group} | {name} | {note}")

    def error(self, group: str, name: str, exc: BaseException) -> None:
        self.check(group, name, False, "no exception", f"{type(exc).__name__}: {exc}")

    def group(self, group: str, fn) -> None:
        before = len(self.items)
        try:
            fn()
        except Exception as exc:
            self.error(group, "safe-group wrapper caught exception", exc)
        if len(self.items) == before:
            self.warn(group, "no assertions", "group completed without recording assertions")

    def summary(self) -> int:
        by_group = {group: {"PASS": 0, "FAIL": 0, "WARN": 0} for group in GROUP_ORDER}
        for status, group, *_ in self.items:
            by_group.setdefault(group, {"PASS": 0, "FAIL": 0, "WARN": 0})
            by_group[group][status] += 1
        print("=" * 72)
        print("TASK_005 REPLICATION INFERENCE PHASE 1 BASELINE RESULTS")
        print("=" * 72)
        for group in GROUP_ORDER:
            counts = by_group[group]
            print(f"{group:<34} PASS={counts['PASS']:<3} FAIL={counts['FAIL']:<3} WARN={counts['WARN']:<3}")
        passed = sum(1 for item in self.items if item[0] == "PASS")
        failed = sum(1 for item in self.items if item[0] == "FAIL")
        warned = sum(1 for item in self.items if item[0] == "WARN")
        print("-" * 72)
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Warned: {warned}")
        return 1 if failed else 0


def ref_derive_seed(master_seed: int, replicate_index: int, namespace: str) -> int:
    if not isinstance(master_seed, int) or isinstance(master_seed, bool) or master_seed < 0:
        raise ValueError("master_seed must be a non-negative integer")
    if not isinstance(replicate_index, int) or isinstance(replicate_index, bool) or replicate_index < 1:
        raise ValueError("replicate_index must be an integer >= 1")
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace must be a non-empty string")
    payload = f"task005|{master_seed}|{replicate_index}|{namespace}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return 1 + int.from_bytes(digest[:8], "big") % (2**32 - 1)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_fixture_sha(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_fixture(v: Reporter | None = None) -> dict:
    try:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))
    except Exception as exc:
        if v:
            v.error("S0-fixture", "fixture parse", exc)
        return {}


def import_replication_config(v: Reporter, group: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module("replication_config")
    except Exception as exc:
        v.check(group, "import replication_config", False, "module import succeeds", f"{type(exc).__name__}: {exc}")
        return None


def import_run_replications(v: Reporter, group: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module("run_replications")
    except Exception as exc:
        v.check(group, "import run_replications", False, "module import succeeds", f"{type(exc).__name__}: {exc}")
        return None


def require_callable(v: Reporter, group: str, module, name: str):
    obj = getattr(module, name, None) if module is not None else None
    v.check(group, f"{name} callable", callable(obj), "callable", repr(obj))
    return obj if callable(obj) else None


def expect_value_error(v: Reporter, group: str, name: str, fn, *args, **kwargs) -> None:
    expect_exception(v, group, name, ValueError, fn, *args, **kwargs)


def expect_exception(v: Reporter, group: str, name: str, expected_exception, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except expected_exception:
        v.check(group, name, True)
    except Exception as exc:
        v.check(group, name, False, expected_exception.__name__, f"{type(exc).__name__}: {exc}")
    else:
        v.check(group, name, False, expected_exception.__name__, "no exception")


def expected_row(index: int, master_seed: int = 20260802) -> dict:
    sim = ref_derive_seed(master_seed, index, "simulation")
    llm = ref_derive_seed(master_seed, index, "llm")
    pyhash = ref_derive_seed(master_seed, index, "python-hash")
    return {
        "replication_schema_version": REPLICATION_SCHEMA_VERSION,
        "seed_derivation_version": SEED_DERIVATION_VERSION,
        "master_seed": master_seed,
        "replicate_index": index,
        "replicate_id": f"R{index:03d}",
        "simulation_seed": sim,
        "requested_llm_seed": llm,
        "llm_seed_supported": "unknown",
        "matrix_version": MATRIX_VERSION,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "condition_count": CONDITION_COUNT,
        "control_exp_id": CONTROL_EXP_ID,
        "execution_order": EXECUTION_ORDER,
        "cache_scope": CACHE_SCOPE,
        "profile_seed": sim,
        "network_seed": sim,
        "target_seed": sim,
        "python_hash_seed": pyhash,
        "provider_model": "",
        "provider_system_fingerprint": "",
    }


def make_bad_rows(case_id: str) -> list[dict]:
    rows = [expected_row(1), expected_row(2)]
    if case_id == "rows_not_list":
        return "not-a-list"  # type: ignore[return-value]
    if case_id == "empty_ledger":
        return []
    if case_id == "row_not_mapping":
        return [expected_row(1), "not-a-mapping"]  # type: ignore[list-item]
    if case_id == "duplicate_replicate_id":
        rows[1]["replicate_id"] = rows[0]["replicate_id"]
    elif case_id == "duplicate_replicate_index":
        rows[1]["replicate_index"] = rows[0]["replicate_index"]
    elif case_id == "duplicate_simulation_seed":
        rows[1]["simulation_seed"] = rows[0]["simulation_seed"]
    elif case_id == "duplicate_requested_llm_seed":
        rows[1]["requested_llm_seed"] = rows[0]["requested_llm_seed"]
    elif case_id == "duplicate_python_hash_seed":
        rows[1]["python_hash_seed"] = rows[0]["python_hash_seed"]
    elif case_id == "wrong_derived_seed":
        rows[0]["requested_llm_seed"] += 1
    elif case_id == "missing_ledger_field":
        rows[0].pop("provider_model")
    elif case_id == "extra_ledger_field":
        rows[0]["extra"] = "bad"
    elif case_id == "wrong_execution_order":
        rows[0]["execution_order"] = tuple(reversed(EXECUTION_ORDER))
    elif case_id == "wrong_cache_scope":
        rows[0]["cache_scope"] = "global"
    elif case_id == "profile_seed_not_simulation_seed":
        rows[0]["profile_seed"] += 1
    elif case_id == "network_seed_not_simulation_seed":
        rows[0]["network_seed"] += 1
    elif case_id == "target_seed_not_simulation_seed":
        rows[0]["target_seed"] += 1
    elif case_id == "seed_out_of_range":
        rows[0]["python_hash_seed"] = SEED_MAX + 1
    elif case_id == "bool_seed":
        rows[0]["simulation_seed"] = True
    elif case_id == "bool_replicate_index":
        rows[0]["replicate_index"] = True
    elif case_id == "mixed_master_seed":
        rows[1]["master_seed"] = rows[0]["master_seed"] + 1
    elif case_id == "replicate_index_gap":
        rows[1]["replicate_index"] = 3
        rows[1]["replicate_id"] = "R003"
    elif case_id == "replicate_id_index_mismatch":
        rows[0]["replicate_id"] = "R002"
    elif case_id == "provider_model_not_string":
        rows[0]["provider_model"] = 123
    elif case_id == "provider_system_fingerprint_not_string":
        rows[0]["provider_system_fingerprint"] = 123
    elif case_id == "invalid_llm_seed_supported":
        rows[0]["llm_seed_supported"] = "yes"
    elif case_id == "wrong_matrix_version":
        rows[0]["matrix_version"] = "2.0"
    elif case_id == "wrong_metrics_version":
        rows[0]["metrics_schema_version"] = "3.0"
    elif case_id == "condition_count_not_9":
        rows[0]["condition_count"] = 8
    elif case_id == "wrong_control_exp_id":
        rows[0]["control_exp_id"] = "Control"
    return rows


def check_t0(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cfile = Path(tmp) / "task005.pyc"
        py_compile.compile(str(Path(__file__).resolve()), cfile=str(cfile), doraise=True)
    v.check("T0-syntax", "test script compiles with tempfile cfile", True)
    v.check("T0-syntax", "design exists", DESIGN.is_file(), "present", DESIGN)
    v.check("T0-syntax", "fixture exists", FIXTURE.is_file(), "present", FIXTURE)
    optional_modules = ["replication_config.py", "run_replications.py", "replication_analysis.py"]
    for rel in optional_modules:
        path = ROOT / rel
        if not path.exists():
            v.check("T0-syntax", f"{rel} optional production module not yet implemented", True, "missing allowed", "missing")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            cfile = Path(tmp) / (Path(rel).stem + ".pyc")
            try:
                py_compile.compile(str(path), cfile=str(cfile), doraise=True)
                v.check("T0-syntax", f"{rel} optional production module compiles", True, "compiles", "compiles")
            except Exception as exc:
                v.check("T0-syntax", f"{rel} optional production module compiles", False, "compiles", f"{type(exc).__name__}: {exc}")


def check_s0(v: Reporter, fixture: dict) -> None:
    group = "S0-fixture"
    v.check(group, "fixture_schema_version", fixture.get("fixture_schema_version") == "1.0", "1.0", fixture.get("fixture_schema_version"))
    case = fixture.get("canonical_case", {})
    v.check(group, "master_seed", case.get("master_seed") == 20260802, 20260802, case.get("master_seed"))
    v.check(group, "num_replicates", case.get("num_replicates") == 3, 3, case.get("num_replicates"))
    reps = case.get("replicates", [])
    v.check(group, "three replicates", len(reps) == 3, 3, len(reps))
    for row in reps:
        idx = row.get("replicate_index")
        if isinstance(idx, int):
            v.check(group, f"{row.get('replicate_id')} simulation_seed", row.get("simulation_seed") == ref_derive_seed(20260802, idx, "simulation"), ref_derive_seed(20260802, idx, "simulation"), row.get("simulation_seed"))
            v.check(group, f"{row.get('replicate_id')} requested_llm_seed", row.get("requested_llm_seed") == ref_derive_seed(20260802, idx, "llm"), ref_derive_seed(20260802, idx, "llm"), row.get("requested_llm_seed"))
            v.check(group, f"{row.get('replicate_id')} python_hash_seed", row.get("python_hash_seed") == ref_derive_seed(20260802, idx, "python-hash"), ref_derive_seed(20260802, idx, "python-hash"), row.get("python_hash_seed"))
    v.check(group, "execution_order exact", tuple(fixture.get("execution_order", [])) == EXECUTION_ORDER, EXECUTION_ORDER, fixture.get("execution_order"))
    required_invalid = {
        "bool_master_seed", "negative_master_seed", "replicate_index_zero", "empty_namespace",
        "num_replicates_zero", "duplicate_replicate_id", "duplicate_simulation_seed",
        "wrong_derived_seed", "missing_ledger_field", "extra_ledger_field",
        "wrong_execution_order", "wrong_cache_scope", "profile_seed_not_simulation_seed",
        "seed_out_of_range", "bool_seed", "invalid_llm_seed_supported",
        "wrong_matrix_version", "wrong_metrics_version", "condition_count_not_9",
        "wrong_control_exp_id", "rows_not_list", "empty_ledger", "row_not_mapping",
        "mixed_master_seed", "replicate_index_gap", "replicate_id_index_mismatch",
        "duplicate_requested_llm_seed", "duplicate_python_hash_seed",
        "network_seed_not_simulation_seed", "target_seed_not_simulation_seed",
        "provider_model_not_string", "provider_system_fingerprint_not_string",
        "bool_replicate_index", "bool_num_replicates", "duplicate_replicate_index",
    }
    invalid_cases = fixture.get("invalid_cases", [])
    v.check(group, "invalid_cases has exactly 35 items", isinstance(invalid_cases, list) and len(invalid_cases) == 35, 35, len(invalid_cases) if isinstance(invalid_cases, list) else type(invalid_cases).__name__)
    v.check(group, "each invalid case is dict", all(isinstance(item, dict) for item in invalid_cases), "all dict", invalid_cases)
    case_ids = [item.get("case_id") if isinstance(item, dict) else None for item in invalid_cases]
    v.check(group, "each case_id is non-empty string", all(isinstance(case_id, str) and case_id for case_id in case_ids), "all non-empty strings", case_ids)
    v.check(group, "case_id values unique", len(case_ids) == len(set(case_ids)), "unique", case_ids)
    got_invalid = set(case_ids)
    v.check(group, "invalid case set exact", got_invalid == required_invalid, sorted(required_invalid), sorted(got_invalid))
    categories = [item.get("category") if isinstance(item, dict) else None for item in invalid_cases]
    allowed_categories = {"derive_seed", "build_seed_ledger", "validate_seed_ledger"}
    v.check(group, "each category is non-empty string", all(isinstance(category, str) and category for category in categories), "all non-empty strings", categories)
    v.check(group, "category values allowed", set(categories) <= allowed_categories, sorted(allowed_categories), sorted(set(categories)))
    for case_id in sorted(required_invalid):
        v.check(group, f"invalid case present: {case_id}", case_id in got_invalid, "present", "absent")
    text = FIXTURE.read_text(encoding="utf-8")
    v.check(group, "no API key marker", "api_key" not in text.lower() and "sk-" not in text, "no secrets", "secret-like text found")


def check_s1(v: Reporter) -> None:
    group = "S1-design-contract"
    text = DESIGN.read_text(encoding="utf-8")
    for token in [
        'REPLICATION_SCHEMA_VERSION = "1.0"',
        'SEED_DERIVATION_VERSION = "sha256-v1"',
        'SEED_NAMESPACE_PREFIX = "task005"',
        'CACHE_SCOPE = "replicate-block-only"',
        'EXECUTION_MODE = "serial-subprocess"',
        'MAX_PARALLEL_BLOCKS = 1',
        'LATEST_POLICY = "disabled"',
        'BLOCK_FAILURE_POLICY = "fail-closed-complete-9"',
        'SEED_MIN = 1',
        'SEED_MAX = 2**32 - 1',
        'MATRIX_VERSION = "3.0"',
        'METRICS_SCHEMA_VERSION = "4.0"',
        'CONDITION_COUNT = 9',
        'CONTROL_EXP_ID = "NoClarification-Control"',
        "replication_config.py is responsible for",
        "run_replications.py is responsible for",
        "v1.0 exact ordered CSV schema",
        "REPLICATION_METADATA_FIELDS",
        "validate_block_artifacts(",
        "subprocess_exit_code: int",
        "argv list",
        "derive_seed(",
        "build_seed_ledger(",
        "validate_seed_ledger(rows)",
        "write_seed_ledger_csv(",
        "read_seed_ledger_csv(",
        "planned", "running", "succeeded", "failed", "invalid", "interrupted",
        "formal concrete block count",
        "real LLM seed support conclusion",
        "bootstrap iteration count",
    ]:
        v.check(group, f"design contains {token}", token in text, "present", "absent")
    for field in LEDGER_FIELDS:
        v.check(group, f"LEDGER field {field}", f"`{field}`" in text, "present", "absent")
    for exp_id in EXECUTION_ORDER:
        v.check(group, f"execution order {exp_id}", f"`{exp_id}`" in text, "present", "absent")


def check_s2(v: Reporter, rc) -> None:
    group = "S2-version-constants"
    rc = rc or import_replication_config(v, group)
    if rc is None:
        return
    expected = {
        "REPLICATION_SCHEMA_VERSION": REPLICATION_SCHEMA_VERSION,
        "SEED_DERIVATION_VERSION": SEED_DERIVATION_VERSION,
        "SEED_NAMESPACE_PREFIX": SEED_NAMESPACE_PREFIX,
        "CACHE_SCOPE": CACHE_SCOPE,
        "EXECUTION_MODE": EXECUTION_MODE,
        "MAX_PARALLEL_BLOCKS": MAX_PARALLEL_BLOCKS,
        "LATEST_POLICY": LATEST_POLICY,
        "BLOCK_FAILURE_POLICY": BLOCK_FAILURE_POLICY,
        "SEED_MIN": SEED_MIN,
        "SEED_MAX": SEED_MAX,
        "MATRIX_VERSION": MATRIX_VERSION,
        "METRICS_SCHEMA_VERSION": METRICS_SCHEMA_VERSION,
        "CONDITION_COUNT": CONDITION_COUNT,
        "CONTROL_EXP_ID": CONTROL_EXP_ID,
    }
    for name, want in expected.items():
        v.check(group, name, getattr(rc, name, None) == want, want, getattr(rc, name, None))
    v.check(group, "LEDGER_FIELDS exact", tuple(getattr(rc, "LEDGER_FIELDS", ())) == LEDGER_FIELDS, LEDGER_FIELDS, getattr(rc, "LEDGER_FIELDS", None))
    v.check(group, "EXECUTION_ORDER exact", tuple(getattr(rc, "EXECUTION_ORDER", ())) == EXECUTION_ORDER, EXECUTION_ORDER, getattr(rc, "EXECUTION_ORDER", None))
    v.check(group, "LLM_SEED_SUPPORTED_VALUES exact", tuple(getattr(rc, "LLM_SEED_SUPPORTED_VALUES", ())) == LLM_SEED_SUPPORTED_VALUES, LLM_SEED_SUPPORTED_VALUES, getattr(rc, "LLM_SEED_SUPPORTED_VALUES", None))


def check_s3(v: Reporter, rc) -> None:
    group = "S3-seed-derivation"
    rc = rc or import_replication_config(v, group)
    fn = require_callable(v, group, rc, "derive_seed")
    if fn is None:
        return
    fixture = load_fixture()
    for row in fixture.get("canonical_case", {}).get("replicates", []):
        idx = row["replicate_index"]
        v.check(group, f"R{idx:03d} simulation", fn(20260802, idx, "simulation") == row["simulation_seed"], row["simulation_seed"], fn(20260802, idx, "simulation"))
        v.check(group, f"R{idx:03d} llm", fn(20260802, idx, "llm") == row["requested_llm_seed"], row["requested_llm_seed"], fn(20260802, idx, "llm"))
        v.check(group, f"R{idx:03d} python-hash", fn(20260802, idx, "python-hash") == row["python_hash_seed"], row["python_hash_seed"], fn(20260802, idx, "python-hash"))
    expect_value_error(v, group, "bool master_seed", fn, True, 1, "simulation")
    expect_value_error(v, group, "negative master_seed", fn, -1, 1, "simulation")
    expect_value_error(v, group, "replicate_index zero", fn, 1, 0, "simulation")
    expect_value_error(v, group, "empty namespace", fn, 1, 1, "")


def check_s4(v: Reporter, rc) -> None:
    group = "S4-ledger-build-validation"
    rc = rc or import_replication_config(v, group)
    build = require_callable(v, group, rc, "build_seed_ledger")
    validate = require_callable(v, group, rc, "validate_seed_ledger")
    if build is None or validate is None:
        return
    rows = build(20260802, 3)
    v.check(group, "build returns 3 rows", isinstance(rows, list) and len(rows) == 3, 3, rows)
    v.check(group, "indexes continuous 1..N", [r.get("replicate_index") for r in rows] == [1, 2, 3], [1, 2, 3], rows)
    v.check(group, "replicate_id matches index", [r.get("replicate_id") for r in rows] == ["R001", "R002", "R003"], "R001..R003", rows)
    v.check(group, "simulation seeds unique", len({r.get("simulation_seed") for r in rows}) == len(rows), "unique", rows)
    v.check(group, "requested llm seeds unique", len({r.get("requested_llm_seed") for r in rows}) == len(rows), "unique", rows)
    v.check(group, "python hash seeds unique", len({r.get("python_hash_seed") for r in rows}) == len(rows), "unique", rows)
    v.check(group, "profile/network/target equal simulation", all(r["profile_seed"] == r["simulation_seed"] and r["network_seed"] == r["simulation_seed"] and r["target_seed"] == r["simulation_seed"] for r in rows), "all coupled", rows)
    provider_rows = build(20260802, 1, llm_seed_supported="false", provider_model="model-x", provider_system_fingerprint="fp-x")
    v.check(group, "provider args propagated", provider_rows[0]["llm_seed_supported"] == "false" and provider_rows[0]["provider_model"] == "model-x" and provider_rows[0]["provider_system_fingerprint"] == "fp-x", "propagated", provider_rows)
    v.check(group, "llm_seed_supported default unknown", rows[0].get("llm_seed_supported") == "unknown", "unknown", rows[0].get("llm_seed_supported"))
    before_rows = copy.deepcopy(rows)
    validated = validate(rows)
    v.check(group, "validate does not mutate original rows", rows == before_rows, before_rows, rows)
    v.check(group, "validate returns sorted rows", validated == sorted(validated, key=lambda r: r["replicate_index"]), "sorted", "bad")
    v.check(group, "validate returns new list", validated is not rows, "new list", "same")
    v.check(group, "validate returns new row objects", all(a is not b for a, b in zip(validated, rows)), "new rows", "shared row")
    v.check(group, "execution_order is immutable or non-shared", all(r["execution_order"] is not rows[i]["execution_order"] or not hasattr(r["execution_order"], "append") for i, r in enumerate(validated)), "not shared mutable", "shared mutable")
    for case_id in [item["case_id"] for item in load_fixture().get("invalid_cases", []) if item["category"] == "validate_seed_ledger"]:
        expect_value_error(v, group, case_id, validate, make_bad_rows(case_id))
    expect_value_error(v, group, "num_replicates zero", build, 20260802, 0)
    expect_value_error(v, group, "bool num_replicates", build, 20260802, True)
    expect_value_error(v, group, "bool master_seed", build, True, 1)


def check_s5(v: Reporter, rc) -> None:
    group = "S5-ledger-csv-roundtrip"
    rc = rc or import_replication_config(v, group)
    build = require_callable(v, group, rc, "build_seed_ledger")
    validate = require_callable(v, group, rc, "validate_seed_ledger")
    write_csv = require_callable(v, group, rc, "write_seed_ledger_csv")
    read_csv = require_callable(v, group, rc, "read_seed_ledger_csv")
    if build is None or validate is None or write_csv is None or read_csv is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "seed_ledger.csv"
        rows = build(20260802, 3)
        before = json.dumps(rows, default=list, sort_keys=True)
        write_csv(rows, path)
        after = json.dumps(rows, default=list, sort_keys=True)
        v.check(group, "write does not mutate input rows", before == after, before, after)
        v.check(group, "csv exists", path.is_file(), "present", "absent")
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            first_data = next(reader)
        v.check(group, "header exact", tuple(header) == LEDGER_FIELDS, LEDGER_FIELDS, header)
        raw_order = first_data[header.index("execution_order")]
        v.check(group, "execution_order compact JSON cell", raw_order == json.dumps(list(EXECUTION_ORDER), separators=(",", ":")), "compact JSON", raw_order)
        reread = read_csv(path)
        v.check(group, "integer fields restored as int not bool", all(isinstance(row[field], int) and not isinstance(row[field], bool) for row in reread for field in ["master_seed", "replicate_index", "simulation_seed", "requested_llm_seed", "condition_count", "profile_seed", "network_seed", "target_seed", "python_hash_seed"]), "all int", reread)
        v.check(group, "roundtrip equals validated rows", reread == validate(rows), "validate(rows)", reread)
        v.check(group, "read does not mutate source rows", json.dumps(rows, default=list, sort_keys=True) == after, after, rows)
        bad_target = path.with_name("bad_target.csv")
        expect_value_error(v, group, "invalid ledger write rejected", write_csv, make_bad_rows("wrong_cache_scope"), bad_target)
        v.check(group, "failed invalid write leaves no target", not bad_target.exists(), "absent", "present")
        missing = path.with_name("missing.csv")
        expect_exception(v, group, "missing file", FileNotFoundError, read_csv, missing)
        bad_header = path.with_name("bad_header.csv")
        bad_header.write_text("wrong,header\n1,2\n", encoding="utf-8")
        expect_exception(v, group, "bad header", ValueError, read_csv, bad_header)


def check_s6(v: Reporter, rc) -> None:
    group = "S6-execution-order-cache-scope"
    rc = rc or import_replication_config(v, group)
    if rc is None:
        return
    v.check(group, "EXECUTION_ORDER exact", tuple(getattr(rc, "EXECUTION_ORDER", ())) == EXECUTION_ORDER, EXECUTION_ORDER, getattr(rc, "EXECUTION_ORDER", None))
    v.check(group, "CACHE_SCOPE exact", getattr(rc, "CACHE_SCOPE", None) == CACHE_SCOPE, CACHE_SCOPE, getattr(rc, "CACHE_SCOPE", None))
    build = require_callable(v, group, rc, "build_seed_ledger")
    if build:
        rows = build(20260802, 3)
        v.check(group, "all rows share frozen order", all(tuple(r["execution_order"]) == EXECUTION_ORDER for r in rows), "all exact", rows)
        v.check(group, "all rows block-only cache", all(r["cache_scope"] == CACHE_SCOPE for r in rows), CACHE_SCOPE, rows)


def check_s7(v: Reporter, rc) -> None:
    group = "S7-block-state-resume"
    rr = import_run_replications(v, group)
    if rr is None:
        return
    v.check(group, "BLOCK_STATES exact", tuple(getattr(rr, "BLOCK_STATES", ())) == STATES, STATES, getattr(rr, "BLOCK_STATES", None))
    v.check(group, "ALLOWED_TRANSITIONS exact", set(getattr(rr, "ALLOWED_TRANSITIONS", ())) == ALLOWED_TRANSITIONS, ALLOWED_TRANSITIONS, getattr(rr, "ALLOWED_TRANSITIONS", None))
    v.check(group, "succeeded not rerunnable", ("succeeded", "running") not in set(getattr(rr, "ALLOWED_TRANSITIONS", ())), "forbidden", "allowed")


def check_s8(v: Reporter, rc) -> None:
    group = "S8-subprocess-spec"
    rr = import_run_replications(v, group)
    if rr is None:
        return
    for item in ENV_REQUIRED:
        v.check(group, f"env {item}", item in tuple(getattr(rr, "SUBPROCESS_ENV_CONTRACT", ())), "present", getattr(rr, "SUBPROCESS_ENV_CONTRACT", None))
    for item in MOCK_ENV_REQUIRED:
        v.check(group, f"mock env {item}", item in tuple(getattr(rr, "DETERMINISTIC_MOCK_ENV_CONTRACT", ())), "present", getattr(rr, "DETERMINISTIC_MOCK_ENV_CONTRACT", None))
    v.check(group, "run_experiments args exact", tuple(getattr(rr, "RUN_EXPERIMENTS_ARGS", ())) == RUN_EXPERIMENTS_ARGS, RUN_EXPERIMENTS_ARGS, getattr(rr, "RUN_EXPERIMENTS_ARGS", None))
    v.check(group, "llm modes exact", tuple(getattr(rr, "LLM_MODES", ())) == LLM_MODES, LLM_MODES, getattr(rr, "LLM_MODES", None))
    v.check(group, "serial max parallel", getattr(rr, "MAX_PARALLEL_BLOCKS", None) == 1, 1, getattr(rr, "MAX_PARALLEL_BLOCKS", None))


def check_s9(v: Reporter, rc) -> None:
    group = "S9-block-artifact-contract"
    rr = import_run_replications(v, group)
    if rr is None:
        return
    fields = tuple(getattr(rr, "MANIFEST_FIELDS", ()))
    v.check(group, "MANIFEST_FIELDS exact", fields == MANIFEST_FIELDS, MANIFEST_FIELDS, fields)
    validator = require_callable(v, group, rr, "validate_block_artifacts")
    if validator:
        import inspect
        sig = inspect.signature(validator)
        params = list(sig.parameters.values())
        names = [p.name for p in params]
        v.check(group, "validate_block_artifacts parameter order", names == ["block_dir", "ledger_row", "subprocess_exit_code"], "block_dir, ledger_row, subprocess_exit_code", sig)
        v.check(group, "subprocess_exit_code keyword-only", len(params) == 3 and params[2].kind is inspect.Parameter.KEYWORD_ONLY, "KEYWORD_ONLY", sig)
        v.check(group, "no *args", not any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params), "no VAR_POSITIONAL", sig)
        v.check(group, "no **kwargs", not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params), "no VAR_KEYWORD", sig)


def check_s10(v: Reporter, rc) -> None:
    group = "S10-failure-policy"
    rr = import_run_replications(v, group)
    if rr is None:
        return
    v.check(group, "BLOCK_FAILURE_POLICY exact", getattr(rr, "BLOCK_FAILURE_POLICY", None) == BLOCK_FAILURE_POLICY, BLOCK_FAILURE_POLICY, getattr(rr, "BLOCK_FAILURE_POLICY", None))
    invalid_statuses = {"failed", "invalid", "interrupted"}
    v.check(group, "failure states exist", invalid_statuses <= set(getattr(rr, "BLOCK_STATES", ())), invalid_statuses, getattr(rr, "BLOCK_STATES", None))
    v.check(group, "complete-9 fail closed semantics", "complete-9" in str(getattr(rr, "BLOCK_FAILURE_POLICY", "")) and "fail-closed" in str(getattr(rr, "BLOCK_FAILURE_POLICY", "")), BLOCK_FAILURE_POLICY, getattr(rr, "BLOCK_FAILURE_POLICY", None))


def check_s11(v: Reporter, rc) -> None:
    group = "S11-provenance-secret-safety"
    rr = import_run_replications(v, group)
    if rr is None:
        return
    metadata_fields = tuple(getattr(rr, "REPLICATION_METADATA_FIELDS", ()))
    v.check(group, "REPLICATION_METADATA_FIELDS exact", metadata_fields == REPLICATION_METADATA_FIELDS, REPLICATION_METADATA_FIELDS, metadata_fields)
    all_fields = list(MANIFEST_FIELDS) + list(REPLICATION_METADATA_FIELDS) + list(LEDGER_FIELDS)
    forbidden = ("secret", "token", "password", "api_key")
    v.check(group, "field names contain no secret markers", not any(any(marker in field.lower() for marker in forbidden) for field in all_fields), "no secret markers", all_fields)


def run_freeze_script(script: Path, argv: list[str], timeout: int = 240) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_DATASETS_OFFLINE"] = "1"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    wrapper_source = f'''
import os
import py_compile
import runpy
import shutil
import sys
import tempfile

root = {str(ROOT)!r}
target = os.path.join(root, {str(script.relative_to(ROOT))!r})
argv = {argv!r}
tmp_dir = tempfile.mkdtemp(prefix="task005_pyc_")
original_compile = py_compile.compile

def compile_wrapper(file, cfile=None, *args, **kwargs):
    if cfile == os.devnull:
        safe_name = "compiled_" + str(len(os.listdir(tmp_dir))) + ".pyc"
        cfile = os.path.join(tmp_dir, safe_name)
    return original_compile(file, cfile=cfile, *args, **kwargs)

try:
    py_compile.compile = compile_wrapper
    sys.argv = argv
    os.chdir(root)
    runpy.run_path(target, run_name="__main__")
finally:
    py_compile.compile = original_compile
    shutil.rmtree(tmp_dir, ignore_errors=True)
'''
    with tempfile.TemporaryDirectory() as tmp:
        wrapper = Path(tmp) / "freeze_wrapper.py"
        wrapper.write_text(wrapper_source, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(wrapper)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    return result.returncode, result.stdout, result.stderr


def check_s12(v: Reporter) -> None:
    group = "S12-task003-task004-invariance"
    code3, out3, err3 = run_freeze_script(
        ROOT / "tests" / "test_task003_experiment_matrix.py",
        ["tests/test_task003_experiment_matrix.py", "--offline-only"],
    )
    v.check(group, "TASK_003 exit code", code3 == 0, 0, code3)
    v.check(group, "TASK_003 Failed: 0", "Failed: 0" in out3, "Failed: 0", out3[-500:])
    v.check(
        group,
        "TASK_003 wrapper no exception",
        "Traceback" not in err3 and "safe wrapper caught exception" not in err3,
        "no traceback/wrapper exception",
        err3[-500:],
    )
    code4, out4, err4 = run_freeze_script(
        ROOT / "tests" / "test_task004_metrics.py",
        ["tests/test_task004_metrics.py"],
    )
    v.check(group, "TASK_004 exit code", code4 == 0, 0, code4)
    v.check(group, "TASK_004 Failed: 0 present", "Failed: 0" in out4, "Failed: 0", out4[-500:])
    v.check(
        group,
        "TASK_004 wrapper no exception",
        "Traceback" not in err4 and "safe wrapper caught exception" not in err4,
        "no traceback/wrapper exception",
        err4[-500:],
    )


def check_s13(v: Reporter, runtime_root: str | None) -> None:
    group = "S13-runtime-pilot"
    if not runtime_root:
        v.warn(group, "runtime-root", "skipped: no --runtime-root supplied")
        return
    root = Path(runtime_root)
    rc = import_replication_config(v, group)
    rr = import_run_replications(v, group)
    v.check(group, "runtime root exists", root.is_dir(), "directory", root)
    for rel in ["seed_ledger.csv", "replicate_manifest.csv", "replication_metadata.json", "replication_failures.csv"]:
        v.check(group, f"{rel} exists", (root / rel).is_file(), "present", "absent")
    for rel in ["blocks", "work", "failures"]:
        v.check(group, f"{rel}/ directory exists", (root / rel).is_dir(), "present", "absent")
    if rc and hasattr(rc, "read_seed_ledger_csv"):
        ledger = rc.read_seed_ledger_csv(root / "seed_ledger.csv")
        expected = load_fixture().get("canonical_case", {}).get("replicates", [])
        v.check(group, "ledger has 3 rows", len(ledger) == 3, 3, len(ledger))
        v.check(group, "ledger ids R001-R003", [r["replicate_id"] for r in ledger] == ["R001", "R002", "R003"], "R001..R003", ledger)
        for row, fixture_row in zip(ledger, expected):
            v.check(group, f"{row['replicate_id']} seeds match fixture", row["simulation_seed"] == fixture_row["simulation_seed"] and row["requested_llm_seed"] == fixture_row["requested_llm_seed"] and row["python_hash_seed"] == fixture_row["python_hash_seed"], fixture_row, row)
    else:
        ledger = []
    batch_replication_id = ""
    metadata_path = root / "replication_metadata.json"
    if metadata_path.is_file():
        try:
            batch_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            batch_metadata = None
            v.check(group, "replication_metadata parse", False, "JSON object", f"{type(exc).__name__}: {exc}")
        v.check(group, "replication_metadata is object", isinstance(batch_metadata, dict), "object", type(batch_metadata).__name__ if batch_metadata is not None else "invalid")
        if isinstance(batch_metadata, dict):
            batch_replication_id = batch_metadata.get("replication_id", "")
            v.check(group, "batch replication_id non-empty", isinstance(batch_replication_id, str) and bool(batch_replication_id), "non-empty string", batch_replication_id)
    manifest_path = root / "replicate_manifest.csv"
    if manifest_path.is_file():
        with manifest_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            v.check(group, "manifest header exact", tuple(reader.fieldnames or ()) == MANIFEST_FIELDS, MANIFEST_FIELDS, reader.fieldnames)
            manifest = list(reader)
        v.check(group, "manifest has 3 rows", len(manifest) == 3, 3, len(manifest))
        manifest_ids = [r.get("replicate_id") for r in manifest]
        ledger_ids = {r.get("replicate_id") for r in ledger}
        v.check(group, "manifest ids exact R001-R003", manifest_ids == ["R001", "R002", "R003"], "R001,R002,R003", manifest_ids)
        v.check(group, "manifest primary key unique", len(set(manifest_ids)) == len(manifest), "unique", manifest)
        v.check(group, "manifest ids equal ledger ids", set(manifest_ids) == ledger_ids, ledger_ids, manifest_ids)
        if batch_replication_id:
            v.check(group, "manifest replication_id matches batch", all(r.get("replication_id") == batch_replication_id for r in manifest), batch_replication_id, manifest)
        v.check(group, "all manifest rows succeeded", all(r.get("status") == "succeeded" for r in manifest), "succeeded", manifest)
        v.check(group, "all validation_passed true", all(str(r.get("validation_passed")).lower() == "true" for r in manifest), "true", manifest)
        v.check(group, "all condition_success_count 9", all(str(r.get("condition_success_count")) == "9" for r in manifest), "9", manifest)
        v.check(group, "all error counts zero", all(str(r.get("condition_error_count")) == "0" and str(r.get("postprocess_error_count")) == "0" for r in manifest), "0/0", manifest)
        v.check(group, "all replay false and network consistent", all(str(r.get("replay_alignment_violated")).lower() == "false" and r.get("network_status") == "consistent" for r in manifest), "false/consistent", manifest)
        v.check(group, "all subprocess exit code zero", all(str(r.get("subprocess_exit_code")) == "0" for r in manifest), "0", manifest)
        v.check(group, "all attempt_count positive", all(str(r.get("attempt_count", "")).isdigit() and int(r.get("attempt_count", "0")) > 0 for r in manifest), "positive int", manifest)
        block_dir_matches = []
        for row in manifest:
            replicate_id = row.get("replicate_id", "")
            expected_block_dir = (root / "blocks" / replicate_id).resolve()
            actual_block_dir = Path(row.get("block_dir", ""))
            if actual_block_dir.is_absolute():
                actual_block_dir = actual_block_dir.resolve()
            else:
                actual_block_dir = (root / actual_block_dir).resolve()
            block_dir_matches.append(actual_block_dir == expected_block_dir)
        v.check(group, "block_dir resolves exactly to blocks/Rxxx", all(block_dir_matches), "exact resolved paths", manifest)
    blocks_dir = root / "blocks"
    if blocks_dir.is_dir():
        block_ids = sorted(p.name for p in blocks_dir.iterdir() if p.is_dir())
        v.check(group, "no extra or missing blocks", block_ids == ["R001", "R002", "R003"], "R001,R002,R003", block_ids)
    failures_csv = root / "replication_failures.csv"
    if failures_csv.is_file():
        lines = [line for line in failures_csv.read_text(encoding="utf-8").splitlines() if line.strip()]
        v.check(group, "replication_failures empty or header only", len(lines) <= 1, "empty/header only", lines[:3])
    if rr and hasattr(rr, "validate_block_artifacts"):
        ledger_by_id = {r["replicate_id"]: r for r in ledger}
        for rid in ("R001", "R002", "R003"):
            block_dir = root / "blocks" / rid
            v.check(group, f"{rid} block exists", block_dir.is_dir(), "present", "absent")
            if block_dir.is_dir() and rid in ledger_by_id:
                result = rr.validate_block_artifacts(block_dir, ledger_by_id[rid], subprocess_exit_code=0)
                v.check(group, f"{rid} validation passed", result.get("validation_passed") is True, True, result)
                v.check(group, f"{rid} status succeeded", result.get("status") == "succeeded", "succeeded", result)
                v.check(group, f"{rid} condition_success_count 9", result.get("condition_success_count") == 9, 9, result)
                v.check(group, f"{rid} condition_error_count 0", result.get("condition_error_count") == 0, 0, result)
                v.check(group, f"{rid} postprocess_error_count 0", result.get("postprocess_error_count") == 0, 0, result)
                v.check(group, f"{rid} replay false", result.get("replay_alignment_violated") is False, False, result)
                v.check(group, f"{rid} network consistent", result.get("network_status") == "consistent", "consistent", result)
                v.check(group, f"{rid} failure fields empty", result.get("failure_stage") in ("", None) and result.get("failure_type") in ("", None) and result.get("failure_message") in ("", None), "empty failure fields", result)
                metadata_path = block_dir / "run_metadata.json"
                if metadata_path.is_file():
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    replication = metadata.get("replication", {})
                    v.check(group, f"{rid} replication keys cover schema", set(replication.keys()) >= set(REPLICATION_METADATA_FIELDS), sorted(REPLICATION_METADATA_FIELDS), sorted(replication.keys()))
                    if batch_replication_id:
                        v.check(group, f"{rid} replication_id matches batch", replication.get("replication_id") == batch_replication_id, batch_replication_id, replication.get("replication_id"))
                    expected_pairs = {
                        "schema_version": REPLICATION_SCHEMA_VERSION,
                        "replicate_id": rid,
                        "replicate_index": ledger_by_id[rid]["replicate_index"],
                        "simulation_seed": ledger_by_id[rid]["simulation_seed"],
                        "requested_llm_seed": ledger_by_id[rid]["requested_llm_seed"],
                        "llm_seed_supported": ledger_by_id[rid]["llm_seed_supported"],
                        "python_hash_seed": ledger_by_id[rid]["python_hash_seed"],
                        "cache_scope": CACHE_SCOPE,
                        "execution_mode": EXECUTION_MODE,
                        "latest_policy": LATEST_POLICY,
                        "engineering_acceptance_only": True,
                    }
                    for key, want in expected_pairs.items():
                        v.check(group, f"{rid} replication {key}", replication.get(key) == want, want, replication.get(key))
                v.check(group, f"{rid} no errors.log", not (block_dir / "errors.log").exists(), "absent", "present")
                v.check(group, f"{rid} no network inconsistency", not (block_dir / "network_inconsistency_report.json").exists(), "absent", "present")
    for name in ("work", "failures"):
        path = root / name
        leftovers = [p for p in path.iterdir()] if path.is_dir() else ["missing"]
        v.check(group, f"{name} has no leftover attempts", len(leftovers) == 0, "empty", leftovers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", default=None)
    args = parser.parse_args(argv)
    v = Reporter()
    fixture = load_fixture(v)
    rc = None
    v.group("T0-syntax", lambda: check_t0(v))
    v.group("S0-fixture", lambda: check_s0(v, fixture))
    v.group("S1-design-contract", lambda: check_s1(v))
    v.group("S2-version-constants", lambda: check_s2(v, rc))
    rc = sys.modules.get("replication_config")
    v.group("S3-seed-derivation", lambda: check_s3(v, rc))
    rc = sys.modules.get("replication_config")
    v.group("S4-ledger-build-validation", lambda: check_s4(v, rc))
    rc = sys.modules.get("replication_config")
    v.group("S5-ledger-csv-roundtrip", lambda: check_s5(v, rc))
    rc = sys.modules.get("replication_config")
    v.group("S6-execution-order-cache-scope", lambda: check_s6(v, rc))
    rc = sys.modules.get("replication_config")
    v.group("S7-block-state-resume", lambda: check_s7(v, rc))
    v.group("S8-subprocess-spec", lambda: check_s8(v, rc))
    v.group("S9-block-artifact-contract", lambda: check_s9(v, rc))
    v.group("S10-failure-policy", lambda: check_s10(v, rc))
    v.group("S11-provenance-secret-safety", lambda: check_s11(v, rc))
    v.group("S12-task003-task004-invariance", lambda: check_s12(v))
    v.group("S13-runtime-pilot", lambda: check_s13(v, args.runtime_root))
    return v.summary()


if __name__ == "__main__":
    raise SystemExit(main())
