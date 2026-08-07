#!/usr/bin/env python
"""TASK_005 Stage I.5C-4C frozen replication-analysis acceptance baseline.

The harness is intentionally executable without pytest. Before
``replication_analysis.py`` exists, production-facing groups fail while the
fixture and frozen-design groups still complete. No network or real LLM is
used.
"""

from __future__ import annotations

import argparse
import ast
import copy
import csv
import importlib
import json
import math
import os
import py_compile
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DESIGN = (
    ROOT
    / ".kiro"
    / "specs"
    / "task005-replication-inference"
    / "production_analysis_scope_update_contract1.0.md"
)
CONTRACT = (
    ROOT
    / ".kiro"
    / "specs"
    / "task005-replication-inference"
    / "production_analysis_scope_update_contract1.0.json"
)
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "task005"
    / "replication_analysis_cases.json"
)
MODULE_PATH = ROOT / "replication_analysis.py"

EXPECTED_FIXTURE_SHA256 = (
    "CEED70ACBE97B543C0E0EE7B852BCE8B27AF165FBCCE76583586F3A5153D22E0"
)
EXPECTED_DESIGN_SHA256 = (
    "6A863FC35D7902005257E51E46D842A240E2047B57231275BF0D490202D05EB5"
)
EXPECTED_CONTRACT_SHA256 = (
    "0045F8B8671B25DCC68E1E00130C27660A6EAC3BE6671BCE776B07CEB6587407"
)

ANALYSIS_SCHEMA_VERSION = "1.1"
CONTROL_EXP_ID = "NoClarification-Control"
CONFIRMATORY_PRIMARY_METRICS = (
    "final_trust_gain_vs_control",
    "post_scandal_auc_gain_vs_control",
)
EXPLORATORY_MECHANISM_METRICS = (
    "local_trust_effect_did_3",
)
ALL_ANALYSIS_METRICS = (
    *CONFIRMATORY_PRIMARY_METRICS,
    *EXPLORATORY_MECHANISM_METRICS,
)
PRIMARY_METRICS = CONFIRMATORY_PRIMARY_METRICS
STRATEGY_EXP_IDS = (
    "Empathy-Hub-Delayed",
    "Empathy-Hub-Immediate",
    "Empathy-Random-Delayed",
    "Empathy-Random-Immediate",
    "Rational-Hub-Delayed",
    "Rational-Hub-Immediate",
    "Rational-Random-Delayed",
    "Rational-Random-Immediate",
)
FACTORIAL_CONTRASTS = (
    "Content",
    "Channel",
    "Timing",
    "Content_x_Channel",
    "Content_x_Timing",
    "Channel_x_Timing",
    "Content_x_Channel_x_Timing",
)
CONFIRMATORY_CONTRASTS = FACTORIAL_CONTRASTS[:6]
DEFAULT_BOOTSTRAP_ITERATIONS = 20000
PARETO_TOLERANCE = 1e-12
FORMAL_TARGET_VALID_BLOCKS = 24
ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL = (
    "P001",
    "P002",
    "P003",
    "P004",
    "P005",
)

REQUIRED_FUNCTIONS = (
    "load_valid_replication_blocks",
    "build_replicate_runs",
    "build_paired_effects",
    "compute_factorial_contrasts",
    "aggregate_strategy_estimands",
    "aggregate_factorial_estimands",
    "holm_adjust",
    "compute_formal_pareto",
    "bootstrap_rank_stability",
    "plan_precision_sample_size",
    "run_replication_analysis",
)

OUTPUT_FILES = (
    "replicate_runs.csv",
    "paired_effects.csv",
    "factorial_contrasts.csv",
    "strategy_estimates.csv",
    "factorial_estimates.csv",
    "formal_pareto.csv",
    "ranking_bootstrap.csv",
    "analysis_metadata.json",
    "analysis_validation.json",
)

GROUP_ORDER = (
    "A0-syntax-input-anchors",
    "A1-fixture-contract",
    "A2-production-api",
    "A3-block-loader",
    "A4-replicate-and-paired-effects",
    "A5-factorial-contrasts",
    "A6-strategy-factorial-estimation",
    "A7-holm-families",
    "A8-pareto",
    "A9-block-bootstrap",
    "A10-sample-size",
    "A11-formal-gates-output",
    "A12-safety-invariance",
)


class Reporter:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str, str, str, str]] = []

    def check(
        self,
        group: str,
        name: str,
        ok: bool,
        expected: Any = "",
        actual: Any = "",
        note: str = "",
    ) -> None:
        status = "PASS" if ok else "FAIL"
        self.items.append(
            (status, group, name, str(expected), str(actual), note)
        )
        if not ok:
            print(
                f"FAIL {group} | {name} | expected={expected} "
                f"actual={actual} {note}"
            )

    def warn(self, group: str, name: str, note: str) -> None:
        self.items.append(("WARN", group, name, "", "", note))
        print(f"WARN {group} | {name} | {note}")

    def error(self, group: str, name: str, exc: BaseException) -> None:
        self.check(
            group,
            name,
            False,
            "no exception",
            f"{type(exc).__name__}: {exc}",
        )

    def group(self, group: str, fn) -> None:
        before = len(self.items)
        try:
            fn()
        except Exception as exc:
            self.error(group, "safe-group wrapper caught exception", exc)
        if len(self.items) == before:
            self.warn(
                group,
                "no assertions",
                "group completed without recording assertions",
            )

    def summary(self) -> int:
        by_group = {
            group: {"PASS": 0, "FAIL": 0, "WARN": 0}
            for group in GROUP_ORDER
        }
        for status, group, *_ in self.items:
            by_group.setdefault(
                group, {"PASS": 0, "FAIL": 0, "WARN": 0}
            )
            by_group[group][status] += 1

        print("=" * 80)
        print("TASK_005 STAGE I.5C-4C REPLICATION ANALYSIS ACCEPTANCE RESULTS")
        print("=" * 80)
        for group in GROUP_ORDER:
            counts = by_group[group]
            print(
                f"{group:<39} "
                f"PASS={counts['PASS']:<3} "
                f"FAIL={counts['FAIL']:<3} "
                f"WARN={counts['WARN']:<3}"
            )
        passed = sum(item[0] == "PASS" for item in self.items)
        failed = sum(item[0] == "FAIL" for item in self.items)
        warned = sum(item[0] == "WARN" for item in self.items)
        print("-" * 80)
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Warned: {warned}")
        return 1 if failed else 0


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def import_analysis(v: Reporter, group: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module("replication_analysis")
    except Exception as exc:
        v.check(
            group,
            "import replication_analysis",
            False,
            "module import succeeds",
            f"{type(exc).__name__}: {exc}",
        )
        return None


def require_callable(v: Reporter, group: str, module, name: str):
    value = getattr(module, name, None) if module is not None else None
    v.check(group, f"{name} callable", callable(value), "callable", repr(value))
    return value if callable(value) else None


def as_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list) and all(
        isinstance(row, Mapping) for row in value
    ):
        return [dict(row) for row in value]
    if isinstance(value, tuple) and all(
        isinstance(row, Mapping) for row in value
    ):
        return [dict(row) for row in value]
    if hasattr(value, "to_dict"):
        try:
            rows = value.to_dict(orient="records")
        except TypeError:
            rows = value.to_dict("records")
        if isinstance(rows, list) and all(
            isinstance(row, Mapping) for row in rows
        ):
            return [dict(row) for row in rows]
    raise TypeError("expected row sequence or dataframe-like records")


def finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def close(a: Any, b: Any, tolerance: float = 1e-10) -> bool:
    try:
        return math.isclose(
            float(a), float(b), rel_tol=tolerance, abs_tol=tolerance
        )
    except (TypeError, ValueError):
        return False


def make_preregistration(
    replication_id: str = "task005-synthetic-formal-v1",
    target_valid_blocks: int = FORMAL_TARGET_VALID_BLOCKS,
) -> dict[str, Any]:
    return {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "formal_replication_id": replication_id,
        "target_valid_blocks": target_valid_blocks,
        "max_attempted_blocks": FORMAL_TARGET_VALID_BLOCKS,
        "primary_metrics": list(CONFIRMATORY_PRIMARY_METRICS),
        "exploratory_metrics": list(EXPLORATORY_MECHANISM_METRICS),
        "control_exp_id": CONTROL_EXP_ID,
        "strategy_exp_ids": list(STRATEGY_EXP_IDS),
        "alpha": 0.05,
        "ci_level": 0.95,
        "bootstrap_iterations": 200,
        "bootstrap_seed": 24680,
        "excluded_replication_ids": [
            "task005-real-pilot-v1",
            "task005-real-smoke-v2",
        ],
    }


def _manifest_fields() -> list[str]:
    return [
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
    ]


def write_synthetic_batch(
    fixture: dict[str, Any],
    root: Path,
    *,
    mutation: str | None = None,
    replication_id: str | None = None,
    engineering_replicate_id: str | None = None,
    metadata_replicate_id_override: str | None = None,
    extra_valid_blocks: int = 0,
) -> Path:
    case = copy.deepcopy(fixture["canonical_case"])
    if extra_valid_blocks < 0:
        raise ValueError("extra_valid_blocks must be nonnegative")
    for offset in range(extra_valid_blocks):
        block = copy.deepcopy(case["blocks"][offset % len(case["blocks"])])
        block["replicate_index"] = len(case["blocks"]) + 1
        block["replicate_id"] = f"R{block['replicate_index']:03d}"
        case["blocks"].append(block)
    batch_id = replication_id or case["replication_id"]
    batch_root = root / batch_id
    blocks_root = batch_root / "blocks"
    blocks_root.mkdir(parents=True)

    if mutation == "pilot_contamination":
        batch_id = "task005-real-pilot-v1"
        batch_root = root / batch_id
        blocks_root = batch_root / "blocks"
        blocks_root.mkdir(parents=True, exist_ok=True)
    elif mutation == "smoke_contamination":
        batch_id = "task005-real-smoke-v2"
        batch_root = root / batch_id
        blocks_root = batch_root / "blocks"
        blocks_root.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, Any]] = []

    for block_number, block in enumerate(case["blocks"], start=1):
        rid = block["replicate_id"]
        if block_number == 1 and engineering_replicate_id is not None:
            rid = engineering_replicate_id
        rows = copy.deepcopy(block["conditions"])

        if mutation == "missing_strategy" and rid == "R002":
            rows = [
                row
                for row in rows
                if row["exp_id"] != "Empathy-Hub-Delayed"
            ]
        elif mutation == "duplicate_condition" and rid == "R003":
            duplicate = next(
                row
                for row in rows
                if row["exp_id"] == "Rational-Random-Immediate"
            )
            rows.append(copy.deepcopy(duplicate))
        elif mutation == "two_controls" and rid == "R001":
            next(
                row
                for row in rows
                if row["exp_id"] == "Empathy-Hub-Delayed"
            )["is_control"] = True
        elif mutation == "control_local_did_nonblank" and rid == "R001":
            next(
                row for row in rows if row["exp_id"] == CONTROL_EXP_ID
            )["local_trust_effect_did_3"] = 0.0
        elif mutation == "strategy_metric_blank" and rid == "R004":
            next(
                row
                for row in rows
                if row["exp_id"] == "Empathy-Hub-Delayed"
            )["final_trust_gain_vs_control"] = None
        elif mutation == "strategy_metric_nan" and rid == "R004":
            next(
                row
                for row in rows
                if row["exp_id"] == "Empathy-Hub-Delayed"
            )["post_scandal_auc_gain_vs_control"] = "NaN"
        elif mutation == "row_order_permuted" and rid == "R002":
            rows = list(reversed(rows))

        block_dir = blocks_root / rid
        block_dir.mkdir(parents=True)
        summary_path = block_dir / "summary.csv"
        fields = [
            "exp_id",
            "is_control",
            "content",
            "channel",
            "timing",
            *ALL_ANALYSIS_METRICS,
        ]
        with summary_path.open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                output = {field: row.get(field, "") for field in fields}
                writer.writerow(output)

        metadata = {
            "replication": {
                "replication_id": batch_id,
                "replicate_id": (
                    metadata_replicate_id_override
                    if block_number == 1
                    and metadata_replicate_id_override is not None
                    else rid
                ),
                "replicate_index": block["replicate_index"],
                "attempt_index": 1,
            },
            "experiment_matrix": {
                "matrix_version": "3.0",
                "condition_count": 9,
            },
            "metrics": {"schema_version": "4.0"},
            "batch_exit_code": 0,
            "run_completed": True,
            "replay_alignment_violated": False,
            "network": {"status": "consistent"},
        }
        (block_dir / "run_metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )

        manifest_rows.append(
            {
                "replication_id": batch_id,
                "replicate_id": rid,
                "replicate_index": block["replicate_index"],
                "simulation_seed": 1000 + block["replicate_index"],
                "requested_llm_seed": 2000 + block["replicate_index"],
                "llm_seed_supported": "unknown",
                "python_hash_seed": 3000 + block["replicate_index"],
                "status": "succeeded",
                "attempt_count": 1,
                "block_dir": f"blocks/{rid}",
                "started_at": "2026-01-01T00:00:00Z",
                "finished_at": "2026-01-01T01:00:00Z",
                "subprocess_exit_code": 0,
                "condition_success_count": 9,
                "condition_error_count": 0,
                "postprocess_error_count": 0,
                "replay_alignment_violated": "false",
                "network_status": "consistent",
                "validation_passed": "true",
                "failure_stage": "",
                "failure_type": "",
                "failure_message": "",
            }
        )

    with (batch_root / "replicate_manifest.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=_manifest_fields())
        writer.writeheader()
        writer.writerows(manifest_rows)

    (batch_root / "replication_metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "replication_id": batch_id,
                "num_replicates": FORMAL_TARGET_VALID_BLOCKS,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return batch_root


def get_loader_parts(value: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise TypeError("loader result must be a mapping")
    valid = as_rows(value.get("valid_blocks", []))
    excluded = as_rows(value.get("excluded_blocks", []))
    counts = value.get("counts", {})
    if not isinstance(counts, Mapping):
        raise TypeError("loader counts must be a mapping")
    return valid, excluded, dict(counts)


def check_a0(v: Reporter) -> None:
    group = "A0-syntax-input-anchors"
    with tempfile.TemporaryDirectory() as temp:
        py_compile.compile(
            str(Path(__file__).resolve()),
            cfile=str(Path(temp) / "analysis_test.pyc"),
            doraise=True,
        )
    v.check(group, "test script compiles", True)
    v.check(group, "design exists", DESIGN.is_file(), True, DESIGN)
    v.check(group, "contract exists", CONTRACT.is_file(), True, CONTRACT)
    v.check(group, "fixture exists", FIXTURE.is_file(), True, FIXTURE)
    if DESIGN.is_file():
        v.check(
            group,
            "design SHA256 frozen",
            sha256_file(DESIGN) == EXPECTED_DESIGN_SHA256,
            EXPECTED_DESIGN_SHA256,
            sha256_file(DESIGN),
        )
    if CONTRACT.is_file():
        v.check(
            group,
            "contract SHA256 frozen",
            sha256_file(CONTRACT) == EXPECTED_CONTRACT_SHA256,
            EXPECTED_CONTRACT_SHA256,
            sha256_file(CONTRACT),
        )
    if FIXTURE.is_file():
        v.check(
            group,
            "fixture SHA256 frozen",
            sha256_file(FIXTURE) == EXPECTED_FIXTURE_SHA256,
            EXPECTED_FIXTURE_SHA256,
            sha256_file(FIXTURE),
        )
    if MODULE_PATH.exists():
        with tempfile.TemporaryDirectory() as temp:
            try:
                py_compile.compile(
                    str(MODULE_PATH),
                    cfile=str(Path(temp) / "replication_analysis.pyc"),
                    doraise=True,
                )
                v.check(group, "production module compiles", True)
            except Exception as exc:
                v.error(group, "production module compiles", exc)
    else:
        v.check(
            group,
            "production module absent in preimplementation baseline",
            True,
            "missing allowed",
            "missing",
        )


def check_a1(v: Reporter, fixture: dict[str, Any]) -> None:
    group = "A1-fixture-contract"
    v.check(
        group,
        "fixture schema",
        fixture.get("fixture_schema_version") == "1.0",
        "1.0",
        fixture.get("fixture_schema_version"),
    )
    v.check(
        group,
        "analysis schema",
        fixture.get("analysis_schema_version") == ANALYSIS_SCHEMA_VERSION,
        ANALYSIS_SCHEMA_VERSION,
        fixture.get("analysis_schema_version"),
    )
    v.check(
        group,
        "control exact",
        fixture.get("control_exp_id") == CONTROL_EXP_ID,
        CONTROL_EXP_ID,
        fixture.get("control_exp_id"),
    )
    v.check(
        group,
        "primary metrics exact",
        tuple(fixture.get("primary_metrics", []))
        == CONFIRMATORY_PRIMARY_METRICS,
        CONFIRMATORY_PRIMARY_METRICS,
        fixture.get("primary_metrics"),
    )
    v.check(
        group,
        "exploratory metrics exact",
        tuple(fixture.get("exploratory_metrics", []))
        == EXPLORATORY_MECHANISM_METRICS,
        EXPLORATORY_MECHANISM_METRICS,
        fixture.get("exploratory_metrics"),
    )
    v.check(
        group,
        "strategy order exact",
        tuple(fixture.get("strategy_order", [])) == STRATEGY_EXP_IDS,
        STRATEGY_EXP_IDS,
        fixture.get("strategy_order"),
    )
    v.check(
        group,
        "contrast order exact",
        tuple(fixture.get("contrast_order", [])) == FACTORIAL_CONTRASTS,
        FACTORIAL_CONTRASTS,
        fixture.get("contrast_order"),
    )

    case = fixture.get("canonical_case", {})
    blocks = case.get("blocks", [])
    v.check(
        group,
        "24 canonical blocks",
        len(blocks) == FORMAL_TARGET_VALID_BLOCKS,
        FORMAL_TARGET_VALID_BLOCKS,
        len(blocks),
    )
    for block in blocks:
        rid = block.get("replicate_id")
        rows = block.get("conditions", [])
        controls = [row for row in rows if row.get("is_control") is True]
        strategies = [row for row in rows if row.get("is_control") is False]
        v.check(group, f"{rid} has 9 rows", len(rows) == 9, 9, len(rows))
        v.check(
            group,
            f"{rid} has one control",
            len(controls) == 1,
            1,
            len(controls),
        )
        v.check(
            group,
            f"{rid} has eight strategies",
            len(strategies) == 8,
            8,
            len(strategies),
        )
        if controls:
            control = controls[0]
            v.check(
                group,
                f"{rid} control local DID structural blank",
                control.get("local_trust_effect_did_3") is None,
                None,
                control.get("local_trust_effect_did_3"),
            )
        finite_ok = all(
            finite_number(row.get(metric))
            for row in strategies
            for metric in ALL_ANALYSIS_METRICS
        )
        v.check(
            group,
            f"{rid} strategy metrics finite",
            finite_ok,
            True,
            finite_ok,
        )

    expected_contrasts = case.get("expected_factorial_contrasts", [])
    v.check(
        group,
        "504 expected factorial rows",
        len(expected_contrasts) == 504,
        504,
        len(expected_contrasts),
    )
    expected_descriptives = case.get(
        "expected_strategy_descriptives", []
    )
    v.check(
        group,
        "24 expected strategy descriptive rows",
        len(expected_descriptives) == 24,
        24,
        len(expected_descriptives),
    )
    v.check(
        group,
        "three Holm cases",
        len(fixture.get("holm_cases", [])) == 3,
        3,
        len(fixture.get("holm_cases", [])),
    )
    v.check(
        group,
        "two Pareto cases",
        len(fixture.get("pareto_cases", [])) == 2,
        2,
        len(fixture.get("pareto_cases", [])),
    )
    v.check(
        group,
        "three sample-size cases",
        len(fixture.get("sample_size_cases", [])) == 3,
        3,
        len(fixture.get("sample_size_cases", [])),
    )
    v.check(
        group,
        "nine invalid cases",
        len(fixture.get("invalid_cases", [])) == 9,
        9,
        len(fixture.get("invalid_cases", [])),
    )


def check_a2(v: Reporter, module) -> None:
    group = "A2-production-api"
    if module is None:
        v.check(
            group,
            "production module available",
            False,
            "module available",
            "missing",
        )
        return

    constants = {
        "ANALYSIS_SCHEMA_VERSION": ANALYSIS_SCHEMA_VERSION,
        "CONFIRMATORY_PRIMARY_METRICS": CONFIRMATORY_PRIMARY_METRICS,
        "EXPLORATORY_MECHANISM_METRICS": EXPLORATORY_MECHANISM_METRICS,
        "ALL_ANALYSIS_METRICS": ALL_ANALYSIS_METRICS,
        "PRIMARY_METRICS": PRIMARY_METRICS,
        "CONTROL_EXP_ID": CONTROL_EXP_ID,
        "STRATEGY_EXP_IDS": STRATEGY_EXP_IDS,
        "FACTORIAL_CONTRASTS": FACTORIAL_CONTRASTS,
        "CONFIRMATORY_CONTRASTS": CONFIRMATORY_CONTRASTS,
        "DEFAULT_BOOTSTRAP_ITERATIONS": DEFAULT_BOOTSTRAP_ITERATIONS,
        "PARETO_TOLERANCE": PARETO_TOLERANCE,
        "FORMAL_TARGET_VALID_BLOCKS": FORMAL_TARGET_VALID_BLOCKS,
        "ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL":
            ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL,
    }
    for name, expected in constants.items():
        actual = getattr(module, name, None)
        if isinstance(expected, tuple) and actual is not None:
            try:
                actual = tuple(actual)
            except TypeError:
                pass
        v.check(group, f"{name} exact", actual == expected, expected, actual)
    for name in REQUIRED_FUNCTIONS:
        require_callable(v, group, module, name)


def check_a3(v: Reporter, module, fixture: dict[str, Any]) -> None:
    group = "A3-block-loader"
    fn = getattr(module, "load_valid_replication_blocks", None) if module else None
    if not callable(fn):
        v.check(group, "loader available", False, "callable", repr(fn))
        return

    with tempfile.TemporaryDirectory() as temp:
        temp_root = Path(temp)
        batch = write_synthetic_batch(fixture, temp_root)
        bad_schema = make_preregistration()
        bad_schema["analysis_schema_version"] = "1.0"
        try:
            fn(batch, bad_schema)
        except ValueError:
            v.check(group, "old schema 1.0 preregistration rejected", True)
        except Exception as exc:
            v.check(
                group,
                "old schema 1.0 preregistration rejected",
                False,
                "ValueError",
                f"{type(exc).__name__}: {exc}",
            )
        else:
            v.check(
                group,
                "old schema 1.0 preregistration rejected",
                False,
                "ValueError",
                "no exception",
            )
        bad_target = make_preregistration()
        bad_target["target_valid_blocks"] = 23
        try:
            fn(batch, bad_target)
        except ValueError:
            v.check(group, "target_valid_blocks not 24 rejected", True)
        except Exception as exc:
            v.check(
                group,
                "target_valid_blocks not 24 rejected",
                False,
                "ValueError",
                f"{type(exc).__name__}: {exc}",
            )
        else:
            v.check(
                group,
                "target_valid_blocks not 24 rejected",
                False,
                "ValueError",
                "no exception",
            )
        result = fn(batch, make_preregistration())
        valid, excluded, counts = get_loader_parts(result)
        v.check(group, "canonical valid blocks", len(valid) == 24, 24, len(valid))
        v.check(group, "canonical excluded blocks", len(excluded) == 0, 0, len(excluded))
        v.check(group, "canonical valid count", int(counts.get("valid", -1)) == 24, 24, counts)
        v.check(
            group,
            "canonical formal complete",
            result.get("formal_complete") is True,
            True,
            result.get("formal_complete"),
        )
        v.check(
            group,
            "canonical exact sample status",
            result.get("formal_sample_status") == "exact_complete"
            and result.get("surplus_valid_blocks") == 0,
            "exact_complete / surplus 0",
            {
                "formal_sample_status": result.get("formal_sample_status"),
                "surplus_valid_blocks": result.get("surplus_valid_blocks"),
            },
        )
        ids = [row.get("replicate_id") for row in valid]
        expected_ids = [f"R{index:03d}" for index in range(1, 25)]
        v.check(group, "valid IDs ordered", ids == expected_ids, expected_ids, ids)

    mutations = (
        "missing_strategy",
        "duplicate_condition",
        "two_controls",
        "control_local_did_nonblank",
        "strategy_metric_blank",
        "strategy_metric_nan",
    )
    for mutation in mutations:
        with tempfile.TemporaryDirectory() as temp:
            batch = write_synthetic_batch(
                fixture, Path(temp), mutation=mutation
            )
            result = fn(batch, make_preregistration())
            valid, excluded, counts = get_loader_parts(result)
            v.check(
                group,
                f"{mutation} excludes exactly one block",
                len(valid) == 23 and len(excluded) == 1,
                "23 valid / 1 excluded",
                f"{len(valid)} valid / {len(excluded)} excluded",
            )
            v.check(
                group,
                f"{mutation} formal incomplete",
                result.get("formal_complete") is False,
                False,
                result.get("formal_complete"),
            )
            v.check(
                group,
                f"{mutation} sample status incomplete",
                result.get("formal_sample_status") == "incomplete"
                and result.get("formal_inference_permitted") is False,
                "incomplete / inference false",
                {
                    "formal_sample_status": result.get("formal_sample_status"),
                    "formal_inference_permitted":
                        result.get("formal_inference_permitted"),
                },
            )

    with tempfile.TemporaryDirectory() as temp:
        batch = write_synthetic_batch(
            fixture,
            Path(temp),
            extra_valid_blocks=1,
        )
        result = fn(batch, make_preregistration())
        valid, excluded, counts = get_loader_parts(result)
        v.check(
            group,
            "25 valid blocks are overcomplete",
            len(valid) == 25
            and len(excluded) == 0
            and result.get("formal_sample_status") == "overcomplete"
            and result.get("surplus_valid_blocks") == 1,
            "25 valid / overcomplete / surplus 1",
            {
                "valid": len(valid),
                "excluded": len(excluded),
                "counts": counts,
                "formal_sample_status": result.get("formal_sample_status"),
                "surplus_valid_blocks": result.get("surplus_valid_blocks"),
            },
        )
        v.check(
            group,
            "25 valid blocks prohibit inference",
            result.get("formal_complete") is False
            and result.get("formal_inference_permitted") is False,
            "formal_complete=false and inference=false",
            {
                "formal_complete": result.get("formal_complete"),
                "formal_inference_permitted":
                    result.get("formal_inference_permitted"),
            },
        )

    with tempfile.TemporaryDirectory() as temp:
        batch = write_synthetic_batch(
            fixture, Path(temp), mutation="row_order_permuted"
        )
        result = fn(batch, make_preregistration())
        valid, excluded, _counts = get_loader_parts(result)
        v.check(
            group,
            "row order permutation remains valid",
            len(valid) == 24 and len(excluded) == 0,
            "24 valid / 0 excluded",
            f"{len(valid)} valid / {len(excluded)} excluded",
        )

    for mutation, batch_id in (
        ("pilot_contamination", "task005-real-pilot-v1"),
        ("smoke_contamination", "task005-real-smoke-v2"),
    ):
        with tempfile.TemporaryDirectory() as temp:
            batch = write_synthetic_batch(
                fixture, Path(temp), mutation=mutation
            )
            try:
                result = fn(
                    batch,
                    make_preregistration(replication_id=batch_id),
                )
            except ValueError:
                v.check(group, f"{mutation} rejected", True)
            else:
                valid, excluded, _counts = get_loader_parts(result)
                v.check(
                    group,
                    f"{mutation} rejected",
                    len(valid) == 0 and len(excluded) >= 1,
                    "no valid blocks",
                    f"{len(valid)} valid / {len(excluded)} excluded",
                )

    for batch_id in ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL:
        with tempfile.TemporaryDirectory() as temp:
            batch = write_synthetic_batch(
                fixture, Path(temp), replication_id=batch_id
            )
            try:
                fn(batch, make_preregistration(replication_id=batch_id))
            except ValueError:
                v.check(group, f"{batch_id} hard-forbidden as formal", True)
            except Exception as exc:
                v.check(
                    group,
                    f"{batch_id} hard-forbidden as formal",
                    False,
                    "ValueError",
                    f"{type(exc).__name__}: {exc}",
                )
            else:
                v.check(
                    group,
                    f"{batch_id} hard-forbidden as formal",
                    False,
                    "ValueError",
                    "no exception",
                )

    for engineering_id in ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL:
        with tempfile.TemporaryDirectory() as temp:
            batch = write_synthetic_batch(
                fixture,
                Path(temp),
                engineering_replicate_id=engineering_id,
            )
            result = fn(batch, make_preregistration())
            valid, excluded, counts = get_loader_parts(result)
            v.check(
                group,
                f"{engineering_id} block excluded from valid formal blocks",
                len(valid) == 23 and len(excluded) == 1,
                "23 valid / 1 excluded",
                f"{len(valid)} valid / {len(excluded)} excluded",
            )
            v.check(
                group,
                f"{engineering_id} block makes formal incomplete",
                result.get("formal_complete") is False
                and result.get("formal_inference_permitted") is False,
                "formal_complete=false and inference=false",
                {
                    "formal_complete": result.get("formal_complete"),
                    "formal_inference_permitted":
                        result.get("formal_inference_permitted"),
                    "counts": counts,
                },
            )
            v.check(
                group,
                f"{engineering_id} excluded reason names hard gate",
                engineering_id in str(excluded[0].get("reason", "")),
                engineering_id,
                excluded,
            )

    with tempfile.TemporaryDirectory() as temp:
        batch = write_synthetic_batch(
            fixture,
            Path(temp),
            metadata_replicate_id_override="P001",
        )
        result = fn(batch, make_preregistration())
        valid, excluded, _counts = get_loader_parts(result)
        v.check(
            group,
            "run_metadata engineering replicate_id excluded",
            len(valid) == 23 and len(excluded) == 1,
            "23 valid / 1 excluded",
            f"{len(valid)} valid / {len(excluded)} excluded",
        )
        v.check(
            group,
            "run_metadata engineering replicate_id reason explicit",
            "P001" in str(excluded[0].get("reason", "")),
            "P001 in reason",
            excluded,
        )


def _canonical_pipeline(module, fixture: dict[str, Any]):
    with tempfile.TemporaryDirectory() as temp:
        batch = write_synthetic_batch(fixture, Path(temp))
        loaded = module.load_valid_replication_blocks(
            batch, make_preregistration()
        )
        valid, _excluded, _counts = get_loader_parts(loaded)
        runs = module.build_replicate_runs(valid)
        paired = module.build_paired_effects(runs)
        contrasts = module.compute_factorial_contrasts(paired)
        return as_rows(runs), as_rows(paired), as_rows(contrasts)


def check_a4(v: Reporter, module, fixture: dict[str, Any]) -> None:
    group = "A4-replicate-and-paired-effects"
    required = [
        getattr(module, "build_replicate_runs", None) if module else None,
        getattr(module, "build_paired_effects", None) if module else None,
        getattr(module, "load_valid_replication_blocks", None) if module else None,
    ]
    if not all(callable(item) for item in required):
        v.check(group, "pipeline APIs available", False, "all callable", required)
        return

    runs, paired, _contrasts = _canonical_pipeline(module, fixture)
    v.check(group, "replicate runs row count", len(runs) == 216, 216, len(runs))
    v.check(group, "paired effects row count", len(paired) == 192, 192, len(paired))
    run_keys = [(row.get("replicate_id"), row.get("exp_id")) for row in runs]
    paired_keys = [(row.get("replicate_id"), row.get("exp_id")) for row in paired]
    v.check(group, "replicate run keys unique", len(run_keys) == len(set(run_keys)), "unique", len(run_keys) - len(set(run_keys)))
    v.check(group, "paired keys unique", len(paired_keys) == len(set(paired_keys)), "unique", len(paired_keys) - len(set(paired_keys)))
    v.check(
        group,
        "paired effects exclude control",
        all(row.get("exp_id") != CONTROL_EXP_ID for row in paired),
        True,
        {row.get("exp_id") for row in paired if row.get("exp_id") == CONTROL_EXP_ID},
    )
    finite_ok = all(
        finite_number(row.get(metric))
        for row in paired
        for metric in ALL_ANALYSIS_METRICS
    )
    v.check(group, "paired primary metrics finite", finite_ok, True, finite_ok)

    # Re-run from a row-permuted batch and require exp_id-keyed invariance.
    with tempfile.TemporaryDirectory() as temp:
        batch = write_synthetic_batch(
            fixture, Path(temp), mutation="row_order_permuted"
        )
        loaded = module.load_valid_replication_blocks(
            batch, make_preregistration()
        )
        valid, _excluded, _counts = get_loader_parts(loaded)
        runs2 = as_rows(module.build_replicate_runs(valid))
        paired2 = as_rows(module.build_paired_effects(runs2))
    def canonical(rows):
        return sorted(
            (
                row["replicate_id"],
                row["exp_id"],
                *[float(row[m]) for m in ALL_ANALYSIS_METRICS],
            )
            for row in rows
        )
    v.check(
        group,
        "row-order invariant paired effects",
        canonical(paired2) == canonical(paired),
        canonical(paired),
        canonical(paired2),
    )


def check_a5(v: Reporter, module, fixture: dict[str, Any]) -> None:
    group = "A5-factorial-contrasts"
    required = [
        getattr(module, "compute_factorial_contrasts", None) if module else None,
        getattr(module, "build_paired_effects", None) if module else None,
        getattr(module, "build_replicate_runs", None) if module else None,
        getattr(module, "load_valid_replication_blocks", None) if module else None,
    ]
    if not all(callable(item) for item in required):
        v.check(group, "contrast pipeline APIs available", False, "all callable", required)
        return

    _runs, _paired, contrasts = _canonical_pipeline(module, fixture)
    v.check(group, "factorial contrast row count", len(contrasts) == 504, 504, len(contrasts))
    keys = [
        (row.get("replicate_id"), row.get("metric"), row.get("contrast_name"))
        for row in contrasts
    ]
    v.check(group, "factorial keys unique", len(keys) == len(set(keys)), "unique", len(keys) - len(set(keys)))

    actual = {
        (row.get("replicate_id"), row.get("metric"), row.get("contrast_name")):
        row.get("contrast_value")
        for row in contrasts
    }
    expected_rows = fixture["canonical_case"]["expected_factorial_contrasts"]
    mismatches = []
    for row in expected_rows:
        key = (
            row["replicate_id"],
            row["metric"],
            row["contrast_name"],
        )
        if key not in actual or not close(actual[key], row["contrast_value"]):
            mismatches.append((key, row["contrast_value"], actual.get(key)))
    v.check(group, "all 504 contrast values exact", not mismatches, "no mismatches", mismatches[:5])

    confirmatory_ok = all(
        bool(row.get("confirmatory"))
        == (
            row.get("metric") in CONFIRMATORY_PRIMARY_METRICS
            and row.get("contrast_name") in CONFIRMATORY_CONTRASTS
        )
        for row in contrasts
    )
    v.check(group, "confirmatory flags exact", confirmatory_ok, True, confirmatory_ok)


def check_a6(v: Reporter, module, fixture: dict[str, Any]) -> None:
    group = "A6-strategy-factorial-estimation"
    required_names = (
        "aggregate_strategy_estimands",
        "aggregate_factorial_estimands",
        "compute_factorial_contrasts",
        "build_paired_effects",
        "build_replicate_runs",
        "load_valid_replication_blocks",
    )
    if not all(callable(getattr(module, name, None)) for name in required_names) if module else True:
        v.check(group, "estimation pipeline APIs available", False, "all callable", module)
        return

    _runs, paired, contrasts = _canonical_pipeline(module, fixture)
    config = make_preregistration()
    strategy = as_rows(module.aggregate_strategy_estimands(paired, config))
    factorial = as_rows(module.aggregate_factorial_estimands(contrasts, config))

    v.check(group, "strategy estimate row count", len(strategy) == 24, 24, len(strategy))
    v.check(group, "factorial estimate row count", len(factorial) == 21, 21, len(factorial))

    strategy_by_key = {
        (row.get("exp_id"), row.get("metric")): row
        for row in strategy
    }
    mismatches = []
    for expected in fixture["canonical_case"]["expected_strategy_descriptives"]:
        key = (expected["exp_id"], expected["metric"])
        row = strategy_by_key.get(key)
        if row is None:
            mismatches.append((key, "missing"))
            continue
        for field in ("mean", "sample_sd", "median", "min", "max"):
            if not close(row.get(field), expected[field]):
                mismatches.append(
                    (key, field, expected[field], row.get(field))
                )
        if int(row.get("n_valid_blocks", -1)) != 24:
            mismatches.append((key, "n_valid_blocks", 24, row.get("n_valid_blocks")))
    v.check(group, "strategy descriptives exact", not mismatches, "no mismatches", mismatches[:5])

    required_fields = {
        "n_valid_blocks",
        "mean",
        "sample_sd",
        "standard_error",
        "ci_low",
        "ci_high",
        "median",
        "q1",
        "q3",
        "iqr",
        "min",
        "max",
        "raw_p_value",
        "holm_p_value",
        "multiplicity_family",
        "analysis_tier",
        "confirmatory",
        "p_value_reporting_permitted",
        "estimand_status",
    }
    fields_ok = all(required_fields <= set(row) for row in strategy)
    v.check(group, "strategy output fields present", fields_ok, required_fields, set(strategy[0]) if strategy else set())

    confirmatory_strategy = [
        row
        for row in strategy
        if row.get("metric") in CONFIRMATORY_PRIMARY_METRICS
    ]
    local_strategy = [
        row
        for row in strategy
        if row.get("metric") in EXPLORATORY_MECHANISM_METRICS
    ]
    family_ok = (
        len(confirmatory_strategy) == 16
        and all(
            row.get("multiplicity_family") == "strategy_primary_16"
            and row.get("analysis_tier") == "confirmatory_primary"
            and row.get("confirmatory") is True
            and row.get("p_value_reporting_permitted") is True
            and row.get("raw_p_value") is not None
            and row.get("holm_p_value") is not None
            for row in confirmatory_strategy
        )
        and len(local_strategy) == 8
        and all(
            row.get("multiplicity_family") in {None, ""}
            and row.get("analysis_tier") == "exploratory_mechanistic"
            and row.get("confirmatory") is False
            and row.get("p_value_reporting_permitted") is False
            and row.get("raw_p_value") is None
            and row.get("holm_p_value") is None
            for row in local_strategy
        )
    )
    v.check(group, "strategy Holm family exact", family_ok, "16 confirmatory / 8 exploratory", {row.get("multiplicity_family") for row in strategy})

    confirmatory_factorial = [
        row
        for row in factorial
        if row.get("metric") in CONFIRMATORY_PRIMARY_METRICS
        and row.get("contrast_name") in CONFIRMATORY_CONTRASTS
    ]
    three_way_factorial = [
        row
        for row in factorial
        if row.get("metric") in CONFIRMATORY_PRIMARY_METRICS
        and row.get("contrast_name") == "Content_x_Channel_x_Timing"
    ]
    local_factorial = [
        row
        for row in factorial
        if row.get("metric") in EXPLORATORY_MECHANISM_METRICS
    ]
    factorial_family_ok = (
        len(confirmatory_factorial) == 12
        and all(
            row.get("multiplicity_family") == "factorial_confirmatory_12"
            and row.get("analysis_tier") == "confirmatory_primary"
            and row.get("confirmatory") is True
            and row.get("p_value_reporting_permitted") is True
            and row.get("raw_p_value") is not None
            and row.get("holm_p_value") is not None
            for row in confirmatory_factorial
        )
        and len(three_way_factorial) == 2
        and all(
            row.get("multiplicity_family") == "factorial_three_way_2"
            and row.get("analysis_tier") == "exploratory_secondary"
            and row.get("confirmatory") is False
            and row.get("p_value_reporting_permitted") is True
            and row.get("raw_p_value") is not None
            and row.get("holm_p_value") is not None
            for row in three_way_factorial
        )
        and len(local_factorial) == 7
        and all(
            row.get("multiplicity_family") in {None, ""}
            and row.get("analysis_tier") == "exploratory_mechanistic"
            and row.get("confirmatory") is False
            and row.get("p_value_reporting_permitted") is False
            and row.get("raw_p_value") is None
            and row.get("holm_p_value") is None
            for row in local_factorial
        )
    )
    v.check(group, "factorial family labels exact", factorial_family_ok, True, factorial_family_ok)

    # One CI identity check for n=24 (t_0.975,23).
    row = strategy_by_key[
        ("Empathy-Hub-Delayed", "final_trust_gain_vs_control")
    ]
    tcrit_df23 = 2.0686576104190406
    expected_half = tcrit_df23 * float(row["sample_sd"]) / math.sqrt(24.0)
    ci_ok = close(row["ci_low"], float(row["mean"]) - expected_half) and close(
        row["ci_high"], float(row["mean"]) + expected_half
    )
    v.check(group, "Student-t CI for n=24", ci_ok, expected_half, (row.get("ci_low"), row.get("ci_high")))


def check_a7(v: Reporter, module, fixture: dict[str, Any]) -> None:
    group = "A7-holm-families"
    fn = getattr(module, "holm_adjust", None) if module else None
    if not callable(fn):
        v.check(group, "holm_adjust available", False, "callable", repr(fn))
        return
    for case in fixture["holm_cases"]:
        original = copy.deepcopy(case["p_values"])
        result = list(fn(case["p_values"]))
        ok = len(result) == len(case["expected"]) and all(
            close(a, b) for a, b in zip(result, case["expected"])
        )
        v.check(
            group,
            f"{case['case_id']} exact",
            ok,
            case["expected"],
            result,
        )
        v.check(
            group,
            f"{case['case_id']} input not mutated",
            case["p_values"] == original,
            original,
            case["p_values"],
        )

    invalid_values = (
        [],
        [0.1, -0.1],
        [1.1],
        [float("nan")],
        [True],
    )
    for values in invalid_values:
        try:
            fn(values)
        except ValueError:
            v.check(group, f"invalid p-values rejected: {values}", True)
        except Exception as exc:
            v.check(group, f"invalid p-values rejected: {values}", False, "ValueError", f"{type(exc).__name__}: {exc}")
        else:
            v.check(group, f"invalid p-values rejected: {values}", False, "ValueError", "no exception")


def pareto_input(case: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for exp_id, values in case["strategy_means"].items():
        for metric, value in zip(ALL_ANALYSIS_METRICS, values):
            rows.append(
                {
                    "exp_id": exp_id,
                    "metric": metric,
                    "mean": value,
                }
            )
    return rows


def check_a8(v: Reporter, module, fixture: dict[str, Any]) -> None:
    group = "A8-pareto"
    fn = getattr(module, "compute_formal_pareto", None) if module else None
    if not callable(fn):
        v.check(group, "compute_formal_pareto available", False, "callable", repr(fn))
        return
    for case in fixture["pareto_cases"]:
        tolerance = case.get("tolerance", PARETO_TOLERANCE)
        result = as_rows(fn(pareto_input(case), tolerance=tolerance))
        got = sorted(
            row.get("exp_id")
            for row in result
            if bool(row.get("is_pareto"))
        )
        v.check(
            group,
            f"{case['case_id']} Pareto set",
            got == sorted(case["expected_pareto"]),
            sorted(case["expected_pareto"]),
            got,
        )
        v.check(
            group,
            f"{case['case_id']} one row per strategy",
            len(result) == len(case["strategy_means"]),
            len(case["strategy_means"]),
            len(result),
        )
        local_absent = all(
            "local_trust_effect_did_3" not in row
            and row.get("metric_basis") == ",".join(CONFIRMATORY_PRIMARY_METRICS)
            and row.get("analysis_tier") == "exploratory_secondary"
            for row in result
        )
        v.check(
            group,
            f"{case['case_id']} Pareto excludes local DID",
            local_absent,
            True,
            result,
        )


def tie_case_paired(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    case = fixture["bootstrap_tie_case"]
    for index, block in enumerate(case["blocks"], start=1):
        for exp_id, values in block["strategies"].items():
            row = {
                "replicate_id": block["replicate_id"],
                "replicate_index": index,
                "exp_id": exp_id,
            }
            row.update(dict(zip(ALL_ANALYSIS_METRICS, values)))
            rows.append(row)
    return rows


def check_a9(v: Reporter, module, fixture: dict[str, Any]) -> None:
    group = "A9-block-bootstrap"
    fn = getattr(module, "bootstrap_rank_stability", None) if module else None
    if not callable(fn):
        v.check(group, "bootstrap_rank_stability available", False, "callable", repr(fn))
        return
    case = fixture["bootstrap_tie_case"]
    config = {
        "bootstrap_iterations": case["iterations"],
        "bootstrap_seed": case["seed"],
        "primary_metrics": list(CONFIRMATORY_PRIMARY_METRICS),
        "exploratory_metrics": list(EXPLORATORY_MECHANISM_METRICS),
        "pareto_tolerance": PARETO_TOLERANCE,
    }
    input_rows = tie_case_paired(fixture)
    first = as_rows(fn(copy.deepcopy(input_rows), copy.deepcopy(config)))
    second = as_rows(fn(copy.deepcopy(input_rows), copy.deepcopy(config)))
    v.check(group, "bootstrap deterministic with fixed seed", first == second, first, second)
    v.check(group, "bootstrap one row per strategy", len(first) == 3, 3, len(first))
    by_id = {row.get("exp_id"): row for row in first}
    mismatches = []
    for exp_id, expected in case["expected"].items():
        row = by_id.get(exp_id)
        if row is None:
            mismatches.append((exp_id, "missing"))
            continue
        for field, value in expected.items():
            if not close(row.get(field), value):
                mismatches.append((exp_id, field, value, row.get(field)))
        if int(row.get("bootstrap_iterations", -1)) != case["iterations"]:
            mismatches.append((exp_id, "iterations", case["iterations"], row.get("bootstrap_iterations")))
    v.check(group, "tie-credit and ranks exact", not mismatches, "no mismatches", mismatches)

    required_fields = {
        "exp_id",
        "pareto_probability",
        "top1_probability",
        "mean_rank",
        "median_rank",
        "rank_interval_low",
        "rank_interval_high",
        "top1_credit_sum",
        "bootstrap_iterations",
        "analysis_tier",
        "metric_basis",
    }
    fields_ok = all(required_fields <= set(row) for row in first)
    v.check(group, "bootstrap output fields present", fields_ok, required_fields, set(first[0]) if first else set())
    basis_ok = all(
        row.get("analysis_tier") == "exploratory_secondary"
        and row.get("metric_basis") == ",".join(CONFIRMATORY_PRIMARY_METRICS)
        for row in first
    )
    v.check(group, "bootstrap excludes local DID basis", basis_ok, True, first)


def check_a10(v: Reporter, module, fixture: dict[str, Any]) -> None:
    group = "A10-sample-size"
    fn = getattr(module, "plan_precision_sample_size", None) if module else None
    if not callable(fn):
        v.check(group, "plan_precision_sample_size available", False, "callable", repr(fn))
        return

    effects = [
        {
            "metric": case["case_id"],
            "pilot_sd": case["pilot_sd"],
        }
        for case in fixture["sample_size_cases"]
    ]
    config = {
        "ci_level": 0.95,
        "half_widths": {
            case["case_id"]: case["half_width"]
            for case in fixture["sample_size_cases"]
        },
        "n_min": 2,
        "n_max": 10000,
    }
    result = as_rows(fn(effects, config))
    by_metric = {row.get("metric"): row for row in result}
    mismatches = []
    for case in fixture["sample_size_cases"]:
        row = by_metric.get(case["case_id"])
        if row is None:
            mismatches.append((case["case_id"], "missing"))
        elif int(row.get("required_n", -1)) != case["expected_required_n"]:
            mismatches.append(
                (
                    case["case_id"],
                    case["expected_required_n"],
                    row.get("required_n"),
                )
            )
    v.check(group, "exact Student-t required N", not mismatches, "no mismatches", mismatches)

    for bad_effects, bad_config in (
        ([{"metric": "x", "pilot_sd": -1}], {"half_widths": {"x": 0.1}, "ci_level": 0.95, "n_min": 2, "n_max": 10}),
        ([{"metric": "x", "pilot_sd": 1}], {"half_widths": {"x": 0}, "ci_level": 0.95, "n_min": 2, "n_max": 10}),
        ([{"metric": "x", "pilot_sd": True}], {"half_widths": {"x": 0.1}, "ci_level": 0.95, "n_min": 2, "n_max": 10}),
    ):
        try:
            fn(bad_effects, bad_config)
        except ValueError:
            v.check(group, f"invalid sample-size input rejected: {bad_effects}", True)
        except Exception as exc:
            v.check(group, f"invalid sample-size input rejected: {bad_effects}", False, "ValueError", f"{type(exc).__name__}: {exc}")
        else:
            v.check(group, f"invalid sample-size input rejected: {bad_effects}", False, "ValueError", "no exception")


def check_a11(v: Reporter, module, fixture: dict[str, Any]) -> None:
    group = "A11-formal-gates-output"
    fn = getattr(module, "run_replication_analysis", None) if module else None
    if not callable(fn):
        v.check(group, "run_replication_analysis available", False, "callable", repr(fn))
        return

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        batch = write_synthetic_batch(fixture, root)
        output = root / "analysis-output"
        latest = root / "results" / "experiments" / "latest"
        latest.mkdir(parents=True)
        sentinel = latest / "sentinel.txt"
        sentinel.write_text("unchanged\n", encoding="utf-8")
        before = sentinel.read_bytes()

        result = fn(batch, output, make_preregistration())
        v.check(group, "analysis output directory created", output.is_dir(), True, output)
        missing = [name for name in OUTPUT_FILES if not (output / name).is_file()]
        v.check(group, "all nine output files", not missing, [], missing)
        v.check(group, "latest sentinel unchanged", sentinel.read_bytes() == before, before, sentinel.read_bytes())

        validation = json.loads(
            (output / "analysis_validation.json").read_text(encoding="utf-8")
        )
        metadata = json.loads(
            (output / "analysis_metadata.json").read_text(encoding="utf-8")
        )
        v.check(group, "formal complete true", validation.get("formal_complete") is True, True, validation.get("formal_complete"))
        v.check(group, "valid block count 24", int(validation.get("valid_blocks", -1)) == 24, 24, validation.get("valid_blocks"))
        v.check(
            group,
            "validation exact sample status",
            validation.get("formal_sample_status") == "exact_complete"
            and int(validation.get("surplus_valid_blocks", -1)) == 0
            and validation.get("formal_inference_permitted") is True,
            "exact_complete / surplus 0 / inference true",
            validation,
        )
        v.check(group, "metadata excludes pilot", metadata.get("pilot_included") is False, False, metadata.get("pilot_included"))
        v.check(group, "metadata excludes smoke", metadata.get("smoke_included") is False, False, metadata.get("smoke_included"))
        v.check(group, "metadata schema 1.1", metadata.get("analysis_schema_version") == "1.1", "1.1", metadata.get("analysis_schema_version"))
        v.check(group, "metadata formal N 24", int(metadata.get("formal_target_valid_blocks", -1)) == 24, 24, metadata.get("formal_target_valid_blocks"))
        v.check(
            group,
            "metadata local DID exploratory",
            metadata.get("local_did_confirmatory") is False
            and metadata.get("pareto_ranking_metric_basis")
            == list(CONFIRMATORY_PRIMARY_METRICS),
            "local_did_confirmatory false and Pareto basis confirmatory",
            metadata,
        )
        rows = list(
            csv.DictReader(
                (output / "strategy_estimates.csv").open(
                    "r", encoding="utf-8-sig", newline=""
                )
            )
        )
        confirmatory_rows = [
            row for row in rows if row.get("metric") in CONFIRMATORY_PRIMARY_METRICS
        ]
        v.check(
            group,
            "N24 confirmatory p-values present",
            len(confirmatory_rows) == 16
            and all(row.get("raw_p_value") for row in confirmatory_rows)
            and all(row.get("holm_p_value") for row in confirmatory_rows),
            "16 rows with raw/Holm p",
            confirmatory_rows[:2],
        )

        try:
            fn(batch, output, make_preregistration())
        except (FileExistsError, ValueError):
            v.check(group, "existing output refused", True)
        except Exception as exc:
            v.check(group, "existing output refused", False, "FileExistsError or ValueError", f"{type(exc).__name__}: {exc}")
        else:
            v.check(group, "existing output refused", False, "exception", "no exception")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        batch = write_synthetic_batch(
            fixture, root, mutation="missing_strategy"
        )
        output = root / "incomplete-output"
        result = fn(batch, output, make_preregistration())
        validation = json.loads(
            (output / "analysis_validation.json").read_text(encoding="utf-8")
        )
        v.check(group, "formal incomplete gate false", validation.get("formal_complete") is False, False, validation.get("formal_complete"))
        v.check(group, "formal inference prohibited", validation.get("formal_inference_permitted") is False, False, validation.get("formal_inference_permitted"))
        rows = list(
            csv.DictReader(
                (output / "strategy_estimates.csv").open(
                    "r", encoding="utf-8-sig", newline=""
                )
            )
        )
        statuses = {row.get("estimand_status") for row in rows}
        v.check(group, "incomplete statuses explicit", statuses == {"formal_incomplete"}, {"formal_incomplete"}, statuses)
        confirmatory_rows = [
            row for row in rows if row.get("metric") in CONFIRMATORY_PRIMARY_METRICS
        ]
        v.check(
            group,
            "N23 confirmatory p-values blank",
            len(confirmatory_rows) == 16
            and all(row.get("raw_p_value", "") == "" for row in confirmatory_rows)
            and all(row.get("holm_p_value", "") == "" for row in confirmatory_rows),
            "16 rows with blank raw/Holm p",
            confirmatory_rows[:2],
        )

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        batch = write_synthetic_batch(
            fixture,
            root,
            extra_valid_blocks=1,
        )
        output = root / "overcomplete-output"
        result = fn(batch, output, make_preregistration())
        validation = json.loads(
            (output / "analysis_validation.json").read_text(encoding="utf-8")
        )
        v.check(
            group,
            "formal overcomplete gate false",
            validation.get("formal_sample_status") == "overcomplete"
            and validation.get("formal_complete") is False
            and validation.get("formal_inference_permitted") is False
            and int(validation.get("surplus_valid_blocks", -1)) == 1,
            "overcomplete / surplus 1 / inference false",
            validation,
        )
        rows = list(
            csv.DictReader(
                (output / "strategy_estimates.csv").open(
                    "r", encoding="utf-8-sig", newline=""
                )
            )
        )
        statuses = {row.get("estimand_status") for row in rows}
        confirmatory_rows = [
            row for row in rows if row.get("metric") in CONFIRMATORY_PRIMARY_METRICS
        ]
        v.check(
            group,
            "N25 not truncated to N24",
            {row.get("n_valid_blocks") for row in rows} == {"25"},
            {"25"},
            {row.get("n_valid_blocks") for row in rows},
        )
        v.check(
            group,
            "overcomplete statuses explicit",
            statuses == {"formal_overcomplete"},
            {"formal_overcomplete"},
            statuses,
        )
        v.check(
            group,
            "N25 confirmatory p-values blank",
            len(confirmatory_rows) == 16
            and all(row.get("raw_p_value", "") == "" for row in confirmatory_rows)
            and all(row.get("holm_p_value", "") == "" for row in confirmatory_rows),
            "16 rows with blank raw/Holm p",
            confirmatory_rows[:2],
        )


def check_a12(v: Reporter, module) -> None:
    group = "A12-safety-invariance"
    if module is None or not MODULE_PATH.is_file():
        v.check(group, "production source available for safety scan", False, "present", MODULE_PATH)
        return

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    forbidden_roots = {
        "requests",
        "httpx",
        "openai",
        "aiohttp",
        "urllib",
    }
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden_found = sorted(imported & forbidden_roots)
    v.check(group, "no network client imports", not forbidden_found, [], forbidden_found)

    text = MODULE_PATH.read_text(encoding="utf-8")
    forbidden_tokens = (
        "AsyncModelRouter",
        "qwen-plus",
        "api_key",
        "sync_latest_snapshot",
        "results/experiments/latest",
    )
    found = [token for token in forbidden_tokens if token in text]
    v.check(group, "no LLM/latest coupling tokens", not found, [], found)
    v.check(
        group,
        "no eval or exec calls",
        not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec"}
            for node in ast.walk(tree)
        ),
        True,
        False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-production",
        action="store_true",
        help="Treat missing replication_analysis.py as the expected failing baseline.",
    )
    args = parser.parse_args()

    reporter = Reporter()
    fixture: dict[str, Any] = {}
    try:
        fixture = load_fixture()
    except Exception as exc:
        reporter.error("A1-fixture-contract", "fixture parse", exc)

    module = import_analysis(reporter, "A2-production-api")

    reporter.group("A0-syntax-input-anchors", lambda: check_a0(reporter))
    if fixture:
        reporter.group(
            "A1-fixture-contract",
            lambda: check_a1(reporter, fixture),
        )
    else:
        reporter.check(
            "A1-fixture-contract",
            "fixture available",
            False,
            "parsed fixture",
            fixture,
        )
    reporter.group(
        "A2-production-api",
        lambda: check_a2(reporter, module),
    )

    production_groups = [
        ("A3-block-loader", check_a3),
        ("A4-replicate-and-paired-effects", check_a4),
        ("A5-factorial-contrasts", check_a5),
        ("A6-strategy-factorial-estimation", check_a6),
        ("A7-holm-families", check_a7),
        ("A8-pareto", check_a8),
        ("A9-block-bootstrap", check_a9),
        ("A10-sample-size", check_a10),
        ("A11-formal-gates-output", check_a11),
    ]
    for group, function in production_groups:
        reporter.group(
            group,
            lambda group=group, function=function: function(
                reporter, module, fixture
            ),
        )
    reporter.group(
        "A12-safety-invariance",
        lambda: check_a12(reporter, module),
    )

    return reporter.summary()


if __name__ == "__main__":
    raise SystemExit(main())
