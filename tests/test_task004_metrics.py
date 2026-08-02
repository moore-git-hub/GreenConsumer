#!/usr/bin/env python
"""TASK_004 metrics v4.0 frozen acceptance baseline.

This script is intentionally executable without pytest. During phase 1 the
production v4 implementation is not present yet, so functional failures are
expected. The harness itself must run to completion and report every group.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import importlib
import json
import math
import os
import py_compile
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from types import ModuleType
from types import SimpleNamespace
from pathlib import Path


os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "task004" / "metric_cases.json"

METRICS_SCHEMA_VERSION = "4.0"
MATRIX_SCHEMA_VERSION = "3.0"
LOCAL_WINDOW_TICKS = 3
EARLY_HORIZON_INTERVALS = 5
RANKING_WEIGHT_STEP = 0.1
NUM_WEIGHT_COMBINATIONS = 66
EPS = 1e-9

V4_FIELDS = [
    "final_trust_gain_vs_control",
    "post_scandal_auc_gain_vs_control",
    "local_trust_effect_did_3",
    "early_trust_auc_gain_5",
    "early_trust_gain_slope_5",
    "secondary_harm_depth",
    "negative_gain_tick_count",
]

PRIMARY_OBJECTIVES = [
    "final_trust_gain_vs_control",
    "post_scandal_auc_gain_vs_control",
    "local_trust_effect_did_3",
]

CONTROL_EMPTY_FIELDS = [
    "local_trust_effect_did_3",
    "early_trust_auc_gain_5",
    "early_trust_gain_slope_5",
    "secondary_harm_depth",
    "negative_gain_tick_count",
]

LEGACY_FIELDS = [
    "delta_recovery",
    "auc_post_scandal",
    "recovery_speed",
    "steady_state_score",
    "recovery_rate",
    "t50",
    "t80",
    "trust_min",
    "trust_min_tick",
    "baseline_trust",
    "clarification_effect",
    "trust_gain_vs_control",
]

EXACT_API = [
    "calculate_final_trust_gain_vs_control",
    "calculate_post_scandal_auc_gain_vs_control",
    "calculate_local_trust_effect_did_3",
    "calculate_early_trust_auc_gain_5",
    "calculate_early_trust_gain_slope_5",
    "calculate_secondary_harm_depth",
    "calculate_negative_gain_tick_count",
    "compute_relative_metrics_v4",
    "build_control_metrics_v4",
    "generate_weight_combinations",
    "compute_pareto_flags_v4",
    "compute_equal_weight_ranking_v4",
    "compute_ranking_sensitivity_v4",
]

EXPECTED_CASE_IDS = {
    "identical_strategy_control",
    "constant_plus_one_after_scandal",
    "immediate_local_step",
    "delayed_local_step",
    "linear_early_gain",
    "secondary_harm_case",
}

EXPECTED_FROZEN_HASHES = {
    "tests/test_task003_experiment_matrix.py": "04805fc714fb494444fc0fdcd01a4e4ea976ac2bd906864aaa0b23ff655572e1",
    "tests/fixtures/task003/pre_task003_behavior_trace.json": "5465bc6f18fcf6232294409fff0c5e5f318b750bf4863254eee6600f0a03984e",
    "experiment_config.py": "8b33b2f9032fbf44542dc4efd2d6cc947323dc2e2b8e438cb2f914ce0c9fe87d",
    "node_selector.py": "744e30edf0c097304bbe36635e53fab2afc4a05337f47a61990064c7e2e5d1a7",
    "clarification_injector.py": "1ea6eea856915bcd91b31d35d11d4f43d6eaa2390634b1c36ac0681227c00e5b",
    "generate_data.py": "e2a885e0fd83d222b51d857e2ee7fac12c0c4b32704c2d7c23ae00ef6652cb0a",
    "plugins/agent/invoke/EasyInvokePlugin.py": "991e247b635bff26c52c59c8bccc58dcfee060dbb8820749242a97705a1ea1a5",
    "plugins/agent/invoke/GreenInvokePlugin.py": "28841e45ac285f623a9ffeeb564c750de9a7923027a9015f8caece49ca817839",
    "plugins/agent/perceive/EasyPerceivePlugin.py": "2133a8ce854f756f1916383b212b29f4f7f727de424e42bf5fdaf5170b837b66",
    "plugins/agent/perceive/GreenPerceivePlugin.py": "807b3e1f0793a05b1cef4fc7711fe1dcf492af62f30b2514e3cb67271cfff0ff",
    "plugins/agent/plan/ConsumerPlanPlugin.py": "2bd69f541a9722e397f239f647cd856a77190e133e1dec664455f09910f0d2f4",
    "plugins/agent/plan/EasyPlanPlugin.py": "3825772590d5e382e6f791453fb2dfbbaeaa51c85dd034a77c2419ad70fa1282",
    "plugins/agent/profile/EasyProfilePlugin.py": "cd2c99d26aaa5f2ec93218203e447f0fe60cd4ddf8b13fa3612315cd78ce5fe4",
    "plugins/agent/profile/GreenProfilePlugin.py": "53577f0be121b20e25c25c61edceac0bbf4bf807c5687fbeb1ecb7775b684441",
    "plugins/agent/reflect/EasyReflectPlugin.py": "feb7fb2405d8e2daf8101460666313bd946afbe3ad5aa6f126433ab489bd45e2",
    "plugins/agent/reflect/GreenCognitionPlugin.py": "e8fca6927152b01c0db11d148c243eb9de63ecd5e6ddae7df6b6b25ec71be705",
    "plugins/agent/reflect/MemoryManager.py": "dcbafe4a6bdd2063488b51a9faca7b218310073e03921f9e50d5354252a82494",
    "plugins/agent/state/EasyStatePlugin.py": "3cba7af98dbf9de4e1fdb4ed4eea06581943662dd30fcc978db6b86af9c1b91f",
    "plugins/agent/state/GreenStatePlugin.py": "b4f5281f133a95638a64fb19f60cbd74c96bbb2e3457deb873fe25c55943a61c",
}


class Reporter:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str, str, str, str]] = []

    def check(self, group: str, name: str, ok: bool, expected="", actual="", note="") -> None:
        status = "PASS" if ok else "FAIL"
        self.items.append((status, group, name, str(expected), str(actual), str(note)))
        if not ok:
            print(f"FAIL {group} | {name} | expected={expected} actual={actual} {note}")

    def warn(self, group: str, name: str, note: str) -> None:
        self.items.append(("WARN", group, name, "", "", note))
        print(f"WARN {group} | {name} | {note}")

    def error(self, group: str, name: str, exc: BaseException) -> None:
        self.check(group, name, False, "no unexpected exception", f"{type(exc).__name__}: {exc}")

    def group(self, group: str, fn) -> None:
        before = len(self.items)
        try:
            fn()
        except Exception as exc:
            self.error(group, "safe-group wrapper caught exception", exc)
        if len(self.items) == before:
            self.warn(group, "no assertions", "group completed without recording an assertion")

    def summary(self) -> int:
        by_group: dict[str, dict[str, int]] = {}
        for status, group, *_ in self.items:
            by_group.setdefault(group, {"PASS": 0, "FAIL": 0, "WARN": 0})
            by_group[group][status] += 1
        print("=" * 72)
        print("TASK_004 METRICS BASELINE RESULTS")
        print("=" * 72)
        for group in sorted(by_group):
            counts = by_group[group]
            print(
                f"{group:<30} PASS={counts['PASS']:<3} "
                f"FAIL={counts['FAIL']:<3} WARN={counts['WARN']:<3}"
            )
        passed = sum(1 for item in self.items if item[0] == "PASS")
        failed = sum(1 for item in self.items if item[0] == "FAIL")
        warned = sum(1 for item in self.items if item[0] == "WARN")
        print("-" * 72)
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Warned: {warned}")
        return 1 if failed else 0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_fixture_bytes(data: dict) -> bytes:
    clone = json.loads(json.dumps(data, ensure_ascii=False))
    clone["sha256"] = None
    return (json.dumps(clone, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def load_fixture(v: Reporter | None = None) -> dict:
    try:
        with FIXTURE.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        if v is not None:
            v.error("S0-fixture", "fixture parse", exc)
        return {"cases": []}


def import_module(v: Reporter, group: str, module_name: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        v.error(group, f"import {module_name}", exc)
        return None


def install_run_experiments_import_stubs() -> None:
    if "simulation_core" in sys.modules:
        return
    stub = ModuleType("simulation_core")
    stub.ENTERPRISE_STRATEGY = {5: {"event": "Blackstone"}}
    stub.AGENT_RECORDS_FIELDS = []
    stub.AGENT_RECORDS_SCHEMA_VERSION = "test-stub"

    def _not_used(*args, **kwargs):
        raise RuntimeError("simulation_core.run_simulation_core must not run in TASK_004 summary schema tests")

    stub.run_simulation_core = _not_used
    sys.modules["simulation_core"] = stub


def require_callable(v: Reporter, group: str, module, name: str):
    obj = getattr(module, name, None) if module is not None else None
    v.check(group, f"{name} available", callable(obj), "callable", repr(obj))
    return obj if callable(obj) else None


def as_mapping(result):
    if isinstance(result, dict):
        return result
    if hasattr(result, "__dataclass_fields__"):
        return {name: getattr(result, name) for name in result.__dataclass_fields__}
    return {}


def close(a, b, tol=1e-9) -> bool:
    return isinstance(a, (int, float)) and math.isfinite(float(a)) and abs(float(a) - float(b)) <= tol


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def call_metric(fn, case):
    return fn(
        case["strategy_trust"],
        case["control_trust"],
        scandal_tick=case["scandal_tick"],
        clarification_tick=case["clarification_tick"],
        total_ticks=case["total_ticks"],
    )


def expect_value_error(v: Reporter, group: str, name: str, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except ValueError:
        v.check(group, name, True)
    except Exception as exc:
        v.check(group, name, False, "ValueError", f"{type(exc).__name__}: {exc}")
    else:
        v.check(group, name, False, "ValueError", "no exception")


def trapezoid_average(values):
    if len(values) == 1:
        return values[0]
    return sum((values[i] + values[i + 1]) / 2.0 for i in range(len(values) - 1)) / (len(values) - 1)


def reference_metrics(case):
    strategy = case["strategy_trust"]
    control = case["control_trust"]
    total = case["total_ticks"]
    scandal = case["scandal_tick"]
    clarification = case["clarification_tick"]
    gain = [s - c for s, c in zip(strategy, control)]
    post_scandal = gain[scandal - 1 : total]
    pre = gain[clarification - 4 : clarification - 1]
    post = gain[clarification - 1 : clarification + 2]
    early = gain[clarification - 1 : clarification + 5]
    xs = list(range(6))
    mean_x = sum(xs) / 6.0
    mean_y = sum(early) / 6.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, early)) / sum((x - mean_x) ** 2 for x in xs)
    tail = gain[clarification - 1 : total]
    return {
        "final_trust_gain_vs_control": gain[total - 1],
        "post_scandal_auc_gain_vs_control": trapezoid_average(post_scandal),
        "local_trust_effect_did_3": sum(post) / 3.0 - sum(pre) / 3.0,
        "early_trust_auc_gain_5": trapezoid_average(early),
        "early_trust_gain_slope_5": slope,
        "secondary_harm_depth": min(0.0, min(tail)),
        "negative_gain_tick_count": sum(1 for x in tail if x < -1e-9),
    }


def case_by_id(fixture: dict, case_id: str) -> dict:
    return {case["case_id"]: case for case in fixture.get("cases", [])}[case_id]


def valid_metadata() -> dict:
    return {
        "experiment_matrix": {
            "matrix_version": MATRIX_SCHEMA_VERSION,
            "condition_count": 9,
        },
        "metrics": {
            "schema_version": METRICS_SCHEMA_VERSION,
            "primary_objectives": PRIMARY_OBJECTIVES,
            "ranking": {
                "weight_sensitivity_step": RANKING_WEIGHT_STEP,
                "weight_combination_count": NUM_WEIGHT_COMBINATIONS,
            },
        },
    }


def expected_metrics_block() -> dict:
    return {
        "schema_version": METRICS_SCHEMA_VERSION,
        "primary_objectives": PRIMARY_OBJECTIVES,
        "post_scandal_window": {
            "start": "scandal_tick",
            "end": "total_ticks",
            "integration": "trapezoid",
            "normalization": "divide_by_interval_count",
        },
        "local_did": {
            "pre_ticks": 3,
            "post_ticks": 3,
            "post_includes_clarification_tick": True,
        },
        "early_window": {
            "horizon_intervals": 5,
            "observations": 6,
        },
        "ranking": {
            "pareto_primary": True,
            "equal_weight_supplementary": True,
            "weight_sensitivity_step": RANKING_WEIGHT_STEP,
            "weight_combination_count": NUM_WEIGHT_COMBINATIONS,
        },
    }


def frozen_signature_ok(fn) -> bool:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return False
    params = list(sig.parameters.values())
    if [p.name for p in params[:2]] != ["strategy_trust", "control_trust"]:
        return False
    if any(p.kind not in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY) for p in params[:2]):
        return False
    tail = params[2:]
    if [p.name for p in tail] != ["scandal_tick", "clarification_tick", "total_ticks"]:
        return False
    return all(p.kind is p.KEYWORD_ONLY for p in tail)


def synthetic_strategy_rows() -> list[dict]:
    rows = []
    for i in range(8):
        final = [0.0, 0.5, 1.0, 0.2, 0.7, 0.4, 0.9, 0.3][i]
        auc = [0.1, 0.8, 0.4, 1.0, 0.7, 0.2, 0.6, 0.3][i]
        local = [0.2, 0.2, 0.9, 0.6, 0.4, 1.0, 0.1, 0.7][i]
        rows.append(
            {
                "exp_id": f"Strategy-{i + 1:02d}",
                "content_factor": "rational-evidence" if i % 2 == 0 else "emotional-empathy",
                "channel_factor": "hub" if (i // 2) % 2 == 0 else "random",
                "timing_factor": "immediate" if i < 4 else "delayed",
                "is_control": False,
                "delta_recovery": 10 + i,
                "auc_post_scandal": 20 + i,
                "recovery_speed": 1 + i,
                "steady_state_score": 5 + i,
                "recovery_rate": 0.1 + i,
                "t50": 2,
                "t80": 4,
                "trust_min": 3,
                "trust_min_tick": 5,
                "baseline_trust": 6,
                "clarification_effect": 0.5 + i,
                "trust_gain_vs_control": final,
                "final_trust_gain_vs_control": final,
                "post_scandal_auc_gain_vs_control": auc,
                "local_trust_effect_did_3": local,
                "early_trust_auc_gain_5": 0.25 + i,
                "early_trust_gain_slope_5": 0.05 + i,
                "secondary_harm_depth": 0.0,
                "negative_gain_tick_count": 0,
            }
        )
    return rows


def synthetic_summary_rows() -> list[dict]:
    control = synthetic_strategy_rows()[0].copy()
    control.update(
        {
            "exp_id": "NoClarification-Control",
            "content_factor": "not-applicable",
            "channel_factor": "not-applicable",
            "timing_factor": "no-clarification",
            "is_control": True,
            "delta_recovery": 0,
            "auc_post_scandal": 0,
            "trust_gain_vs_control": 0,
            "final_trust_gain_vs_control": 0,
            "post_scandal_auc_gain_vs_control": 0,
        }
    )
    for field in CONTROL_EMPTY_FIELDS:
        control[field] = ""
    return synthetic_strategy_rows() + [control]


def official_relative_metrics(row: dict) -> dict:
    if row["exp_id"] == "NoClarification-Control":
        return {
            "final_trust_gain_vs_control": 0,
            "post_scandal_auc_gain_vs_control": 0,
            "local_trust_effect_did_3": None,
            "early_trust_auc_gain_5": None,
            "early_trust_gain_slope_5": None,
            "secondary_harm_depth": None,
            "negative_gain_tick_count": None,
        }
    return {field: row[field] for field in V4_FIELDS}


def bait_metrics_namespace(row: dict) -> SimpleNamespace:
    bait = row.copy()
    for idx, field in enumerate(V4_FIELDS, start=1):
        bait[field] = -9999.0 - idx
    return SimpleNamespace(**bait)


def write_summary(path: Path, rows: list[dict]) -> None:
    fields = ["exp_id", "content_factor", "channel_factor", "timing_factor", "is_control"] + LEGACY_FIELDS + V4_FIELDS
    write_summary_with_fields(path, rows, fields)


def write_summary_with_fields(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_metadata(path: Path, metadata: dict | None = None) -> None:
    if metadata is None:
        metadata = valid_metadata()
        metadata["metrics"] = expected_metrics_block()
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def parse_bool(value) -> bool:
    if value is True:
        return True
    if value is False:
        return False
    if isinstance(value, str) and value in ("True", "False"):
        return value == "True"
    raise ValueError(f"invalid boolean value: {value!r}")


def strategy_only(rows: list[dict]) -> list[dict]:
    return [row for row in rows if not parse_bool(row.get("is_control", False))]


def mutate_legacy(rows: list[dict]) -> list[dict]:
    mutated = [row.copy() for row in rows]
    for idx, row in enumerate(mutated):
        for field in LEGACY_FIELDS:
            row[field] = 1000000 + idx
    return mutated


def normalize_values(rows: list[dict], field: str) -> dict[str, float]:
    values = [float(row[field]) for row in rows]
    lo = min(values)
    hi = max(values)
    if abs(hi - lo) <= 1e-12:
        return {row["exp_id"]: 0.5 for row in rows}
    return {row["exp_id"]: (float(row[field]) - lo) / (hi - lo) for row in rows}


def average_ranks(items: list[tuple[str, float]], reverse: bool = True) -> dict[str, float]:
    ordered = sorted(items, key=lambda item: (-item[1] if reverse else item[1], item[0]))
    ranks: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and abs(ordered[end][1] - ordered[index][1]) <= 1e-12:
            end += 1
        avg_rank = (index + 1 + end) / 2.0
        for pos in range(index, end):
            ranks[ordered[pos][0]] = avg_rank
        index = end
    return ranks


def reference_pareto_rows(rows: list[dict]) -> list[dict]:
    strategies = sorted(strategy_only(rows), key=lambda row: row["exp_id"])
    out = []
    for row in strategies:
        dominated = False
        for other in strategies:
            if other["exp_id"] == row["exp_id"]:
                continue
            ge_all = all(float(other[field]) >= float(row[field]) - 1e-12 for field in PRIMARY_OBJECTIVES)
            gt_any = any(float(other[field]) > float(row[field]) + 1e-12 for field in PRIMARY_OBJECTIVES)
            if ge_all and gt_any:
                dominated = True
                break
        new_row = row.copy()
        new_row["is_pareto"] = not dominated
        out.append(new_row)
    return out


def reference_ranking_rows(rows: list[dict]) -> list[dict]:
    strategies = sorted(strategy_only(rows), key=lambda row: row["exp_id"])
    final_norm = normalize_values(strategies, "final_trust_gain_vs_control")
    auc_norm = normalize_values(strategies, "post_scandal_auc_gain_vs_control")
    local_norm = normalize_values(strategies, "local_trust_effect_did_3")
    ranked = []
    for row in strategies:
        exp_id = row["exp_id"]
        score = (final_norm[exp_id] + auc_norm[exp_id] + local_norm[exp_id]) / 3.0
        ranked.append(
            {
                "exp_id": exp_id,
                "final_norm": final_norm[exp_id],
                "auc_norm": auc_norm[exp_id],
                "local_norm": local_norm[exp_id],
                "score_equal": score,
                "analysis_role": "supplementary",
            }
        )
    ranks = average_ranks([(row["exp_id"], row["score_equal"]) for row in ranked], reverse=True)
    for row in ranked:
        row["rank"] = ranks[row["exp_id"]]
    return sorted(ranked, key=lambda row: (row["rank"], row["exp_id"]))


def reference_weight_combinations() -> list[tuple[float, float, float]]:
    return [(i / 10.0, j / 10.0, (10 - i - j) / 10.0) for i in range(11) for j in range(11 - i)]


def reference_ranking_sensitivity(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    strategies = sorted(strategy_only(rows), key=lambda row: row["exp_id"])
    final_norm = normalize_values(strategies, "final_trust_gain_vs_control")
    auc_norm = normalize_values(strategies, "post_scandal_auc_gain_vs_control")
    local_norm = normalize_values(strategies, "local_trust_effect_did_3")
    sensitivity = []
    for wf, wa, wl in reference_weight_combinations():
        scores = {
            row["exp_id"]: wf * final_norm[row["exp_id"]] + wa * auc_norm[row["exp_id"]] + wl * local_norm[row["exp_id"]]
            for row in strategies
        }
        ranks = average_ranks(list(scores.items()), reverse=True)
        top_score = max(scores.values())
        winners = [exp_id for exp_id, score in scores.items() if abs(score - top_score) <= 1e-12]
        ordered_ids = sorted(scores, key=lambda exp_id: (ranks[exp_id], exp_id))
        for exp_id in ordered_ids:
            sensitivity.append(
                {
                    "weight_final": wf,
                    "weight_auc": wa,
                    "weight_local": wl,
                    "exp_id": exp_id,
                    "weighted_score": scores[exp_id],
                    "rank": ranks[exp_id],
                    "top1_credit": 1.0 / len(winners) if exp_id in winners else 0.0,
                }
            )
    robustness = []
    for exp_id in [row["exp_id"] for row in strategies]:
        rows_for_exp = [row for row in sensitivity if row["exp_id"] == exp_id]
        ranks = [float(row["rank"]) for row in rows_for_exp]
        robustness.append(
            {
                "exp_id": exp_id,
                "top1_share": sum(float(row["top1_credit"]) for row in rows_for_exp) / NUM_WEIGHT_COMBINATIONS,
                "mean_rank": sum(ranks) / len(ranks),
                "median_rank": statistics.median(ranks),
                "best_rank": min(ranks),
                "worst_rank": max(ranks),
            }
        )
    return sensitivity, sorted(robustness, key=lambda row: row["exp_id"])


def check_t0(v: Reporter) -> None:
    group = "T0-syntax"
    for rel in [
        "tests/test_task004_metrics.py",
        "metrics_calculator.py",
        "run_experiments.py",
        "simulation_core.py",
        "analysis/plot_experiments.py",
        "analysis/plot_trajectories.py",
    ]:
        src = ROOT / rel
        try:
            with tempfile.NamedTemporaryFile(suffix=".pyc", delete=False) as tmp:
                output = tmp.name
            try:
                py_compile.compile(str(src), cfile=output, doraise=True)
            finally:
                try:
                    os.remove(output)
                except OSError:
                    pass
            v.check(group, f"py_compile {rel}", True)
        except Exception as exc:
            v.error(group, f"py_compile {rel}", exc)


def check_s0(v: Reporter, fixture: dict) -> None:
    group = "S0-fixture"
    v.check(group, "fixture_schema_version", fixture.get("fixture_schema_version") == "1.0", "1.0", fixture.get("fixture_schema_version"))
    v.check(group, "design_version", fixture.get("design_version") == "design0.1", "design0.1", fixture.get("design_version"))
    commit = fixture.get("generated_from_commit")
    v.check(group, "generated_from_commit format", bool(re.fullmatch(r"[0-9a-f]{40}", str(commit))), "40 lowercase hex", commit)
    case_ids = [case.get("case_id") for case in fixture.get("cases", [])]
    v.check(group, "case IDs exact", set(case_ids) == EXPECTED_CASE_IDS and len(case_ids) == len(set(case_ids)), EXPECTED_CASE_IDS, case_ids)
    actual_sha = hashlib.sha256(canonical_fixture_bytes(fixture)).hexdigest()
    v.check(group, "canonical SHA-256", fixture.get("sha256") == actual_sha, fixture.get("sha256"), actual_sha)
    v.check(group, "sha256 note mentions trailing LF", "trailing LF" in str(fixture.get("sha256_note", "")), "mentions trailing LF", fixture.get("sha256_note"))
    required = {"case_id", "scandal_tick", "clarification_tick", "total_ticks", "strategy_trust", "control_trust", "expected", "generation_note"}
    for case in fixture.get("cases", []):
        cid = str(case.get("case_id"))
        v.check(group, f"{cid} fields complete", set(case) == required, required, set(case))
        strategy = case.get("strategy_trust", [])
        control = case.get("control_trust", [])
        total = case.get("total_ticks")
        v.check(group, f"{cid} trajectory lengths", len(strategy) == len(control) == total, total, (len(strategy), len(control)))
        finite = all(finite_number(x) for x in strategy + control)
        v.check(group, f"{cid} finite trajectories", finite, "all finite", "bad value")
        tick_ok = isinstance(total, int) and total > 0 and isinstance(case.get("scandal_tick"), int) and isinstance(case.get("clarification_tick"), int) and 1 <= case["scandal_tick"] <= total and 1 <= case["clarification_tick"] <= total
        v.check(group, f"{cid} legal ticks", tick_ok, "valid ticks", (case.get("scandal_tick"), case.get("clarification_tick"), total))
        expected = case.get("expected", {})
        v.check(group, f"{cid} expected fields exact", set(expected) == set(V4_FIELDS), V4_FIELDS, sorted(expected))
        ref = reference_metrics(case)
        for field, want in ref.items():
            got = expected.get(field)
            ok = got == want if isinstance(want, int) else close(got, want)
            v.check(group, f"{cid} expected {field}", ok, want, got)


def check_s1(v: Reporter, mc) -> None:
    group = "S1-version-constants"
    for name, want in {
        "METRICS_SCHEMA_VERSION": METRICS_SCHEMA_VERSION,
        "LOCAL_WINDOW_TICKS": LOCAL_WINDOW_TICKS,
        "EARLY_HORIZON_INTERVALS": EARLY_HORIZON_INTERVALS,
        "RANKING_WEIGHT_STEP": RANKING_WEIGHT_STEP,
        "NUM_WEIGHT_COMBINATIONS": NUM_WEIGHT_COMBINATIONS,
    }.items():
        got = getattr(mc, name, None) if mc is not None else None
        v.check(group, name, got == want, repr(want), repr(got))
    for name in EXACT_API:
        fn = require_callable(v, group, mc, name)
        if fn is not None and name.startswith("calculate_"):
            v.check(group, f"{name} frozen signature", frozen_signature_ok(fn), "unified keyword-only tick signature", inspect.signature(fn))
    relative = getattr(mc, "compute_relative_metrics_v4", None) if mc is not None else None
    if callable(relative):
        v.check(group, "compute_relative_metrics_v4 frozen signature", frozen_signature_ok(relative), "unified keyword-only tick signature", inspect.signature(relative))


def check_s2(v: Reporter, mc, fixture: dict) -> None:
    group = "S2-post-scandal-auc"
    fn = require_callable(v, group, mc, "calculate_post_scandal_auc_gain_vs_control")
    if fn is None:
        return
    for cid in ["identical_strategy_control", "constant_plus_one_after_scandal"]:
        case = case_by_id(fixture, cid)
        got = call_metric(fn, case)
        v.check(group, cid, close(got, case["expected"]["post_scandal_auc_gain_vs_control"]), case["expected"]["post_scandal_auc_gain_vs_control"], got)
    a = [5.0] * 30
    b = [5.0] * 30
    s1 = a.copy()
    s2 = a.copy()
    for idx in range(4, 30):
        s1[idx] = b[idx] + 0.75
    for idx in range(4, 30):
        s2[idx] = b[idx] + 0.75
    s2[12] -= 4.0
    s2[20] += 4.0
    v.check(group, "fixed window ignores dynamic minimum", close(fn(s1, b, scandal_tick=5, clarification_tick=6, total_ticks=30), fn(s2, b, scandal_tick=5, clarification_tick=6, total_ticks=30)), "same AUC", "different AUC")
    v.check(group, "total_ticks == scandal_tick", close(fn([6.0] * 5, [5.0] * 5, scandal_tick=5, clarification_tick=3, total_ticks=5), 1.0), 1.0, "bad")
    expect_value_error(v, group, "total_ticks < scandal_tick", fn, [5.0] * 4, [5.0] * 4, scandal_tick=5, clarification_tick=3, total_ticks=4)


def check_s3(v: Reporter, mc, fixture: dict) -> None:
    group = "S3-final-gain"
    fn = require_callable(v, group, mc, "calculate_final_trust_gain_vs_control")
    if fn is None:
        return
    case = case_by_id(fixture, "delayed_local_step")
    got = call_metric(fn, case)
    v.check(group, "equals final tick difference", close(got, 3.0), 3.0, got)
    expect_value_error(v, group, "unequal lengths", fn, [1, 2], [1], scandal_tick=1, clarification_tick=1, total_ticks=2)
    expect_value_error(v, group, "length not total_ticks", fn, [1, 2], [1, 2], scandal_tick=1, clarification_tick=1, total_ticks=3)
    expect_value_error(v, group, "NaN rejected", fn, [1, math.nan], [1, 1], scandal_tick=1, clarification_tick=1, total_ticks=2)
    expect_value_error(v, group, "Inf rejected", fn, [1, math.inf], [1, 1], scandal_tick=1, clarification_tick=1, total_ticks=2)


def check_s4(v: Reporter, mc, fixture: dict) -> None:
    group = "S4-local-did"
    fn = require_callable(v, group, mc, "calculate_local_trust_effect_did_3")
    if fn is None:
        return
    for cid in ["immediate_local_step", "delayed_local_step"]:
        case = case_by_id(fixture, cid)
        got = call_metric(fn, case)
        v.check(group, cid, close(got, case["expected"]["local_trust_effect_did_3"]), case["expected"]["local_trust_effect_did_3"], got)
    s = [5.0] * 12
    c = [5.0] * 12
    s[5] = 8.0
    got = fn(s, c, scandal_tick=5, clarification_tick=6, total_ticks=12)
    v.check(group, "clarification tick enters post window", close(got, 1.0), 1.0, got)
    expect_value_error(v, group, "pre window too short", fn, [5.0] * 6, [5.0] * 6, scandal_tick=5, clarification_tick=3, total_ticks=6)
    expect_value_error(v, group, "post window too short", fn, [5.0] * 7, [5.0] * 7, scandal_tick=5, clarification_tick=6, total_ticks=7)


def check_s5(v: Reporter, mc, fixture: dict) -> None:
    group = "S5-early-auc"
    fn = require_callable(v, group, mc, "calculate_early_trust_auc_gain_5")
    if fn is None:
        return
    for cid in ["constant_plus_one_after_scandal", "linear_early_gain"]:
        case = case_by_id(fixture, cid)
        got = call_metric(fn, case)
        v.check(group, cid, close(got, case["expected"]["early_trust_auc_gain_5"]), case["expected"]["early_trust_auc_gain_5"], got)
    s = [5.0] * 11
    c = [5.0] * 11
    s[10] = 10.0
    got = fn(s, c, scandal_tick=5, clarification_tick=6, total_ticks=11)
    v.check(group, "uses c through c+5 inclusively", close(got, 0.5), 0.5, got)
    expect_value_error(v, group, "c+5 out of bounds", fn, [5.0] * 10, [5.0] * 10, scandal_tick=5, clarification_tick=6, total_ticks=10)


def check_s6(v: Reporter, mc, fixture: dict) -> None:
    group = "S6-early-slope"
    fn = require_callable(v, group, mc, "calculate_early_trust_gain_slope_5")
    if fn is None:
        return
    for cid, want in [("linear_early_gain", 0.2), ("constant_plus_one_after_scandal", 0.0)]:
        case = case_by_id(fixture, cid)
        got = call_metric(fn, case)
        v.check(group, cid, close(got, want), want, got)
    s = [5.0] * 30
    c = [5.0] * 30
    s[3] = 0.0
    for h in range(6):
        s[5 + h] = 5.0 + 0.2 * h
    got = fn(s, c, scandal_tick=5, clarification_tick=6, total_ticks=30)
    v.check(group, "does not use dynamic minimum window", close(got, 0.2), 0.2, got)


def check_s7(v: Reporter, mc) -> None:
    group = "S7-secondary-harm"
    depth_fn = require_callable(v, group, mc, "calculate_secondary_harm_depth")
    count_fn = require_callable(v, group, mc, "calculate_negative_gain_tick_count")
    if depth_fn is None or count_fn is None:
        return
    n = 12
    s = [0.0] * n
    c = [0.0] * n
    s[5] = -1e-9
    s[6] = -1.000001e-9
    s[7] = -1.25
    v.check(group, "harm depth", close(depth_fn(s, c, scandal_tick=5, clarification_tick=6, total_ticks=n), -1.25), -1.25, "bad")
    v.check(group, "-1e-9 boundary excluded and below counted", count_fn(s, c, scandal_tick=5, clarification_tick=6, total_ticks=n) == 2, 2, "bad")


def check_s8(v: Reporter, mc, fixture: dict) -> None:
    group = "S8-control-and-relative"
    control_fn = require_callable(v, group, mc, "build_control_metrics_v4")
    relative_fn = require_callable(v, group, mc, "compute_relative_metrics_v4")
    standalone = {name: getattr(mc, name, None) if mc is not None else None for name in EXACT_API if name.startswith("calculate_")}
    if control_fn is not None:
        row = control_fn()
        v.check(group, "control returns dict", isinstance(row, dict), "dict", type(row).__name__)
        v.check(group, "control exact v4 fields", set(row) == set(V4_FIELDS), V4_FIELDS, sorted(row) if isinstance(row, dict) else row)
        if isinstance(row, dict):
            v.check(group, "final gain zero", row.get("final_trust_gain_vs_control") == 0, 0, row.get("final_trust_gain_vs_control"))
            v.check(group, "post scandal AUC zero", row.get("post_scandal_auc_gain_vs_control") == 0, 0, row.get("post_scandal_auc_gain_vs_control"))
            for field in CONTROL_EMPTY_FIELDS:
                v.check(group, f"{field} None", row.get(field) is None, "None", repr(row.get(field)))
    if relative_fn is None:
        return
    for case in fixture.get("cases", []):
        result = relative_fn(
            case["strategy_trust"],
            case["control_trust"],
            scandal_tick=case["scandal_tick"],
            clarification_tick=case["clarification_tick"],
            total_ticks=case["total_ticks"],
        )
        v.check(group, f"{case['case_id']} returns dict", isinstance(result, dict), "dict", type(result).__name__)
        v.check(group, f"{case['case_id']} exact fields", set(result) == set(V4_FIELDS) if isinstance(result, dict) else False, V4_FIELDS, sorted(result) if isinstance(result, dict) else result)
        if not isinstance(result, dict):
            continue
        for field in V4_FIELDS:
            got = result.get(field)
            want = case["expected"][field]
            ok = got == want if isinstance(want, int) else close(got, want)
            v.check(group, f"{case['case_id']} {field} fixture", ok, want, got)
        pairs = {
            "final_trust_gain_vs_control": "calculate_final_trust_gain_vs_control",
            "post_scandal_auc_gain_vs_control": "calculate_post_scandal_auc_gain_vs_control",
            "local_trust_effect_did_3": "calculate_local_trust_effect_did_3",
            "early_trust_auc_gain_5": "calculate_early_trust_auc_gain_5",
            "early_trust_gain_slope_5": "calculate_early_trust_gain_slope_5",
            "secondary_harm_depth": "calculate_secondary_harm_depth",
            "negative_gain_tick_count": "calculate_negative_gain_tick_count",
        }
        for field, fn_name in pairs.items():
            fn = standalone.get(fn_name)
            if callable(fn):
                standalone_value = call_metric(fn, case)
                got = result.get(field)
                ok = got == standalone_value if isinstance(standalone_value, int) else close(got, standalone_value)
                v.check(group, f"{case['case_id']} {field} standalone agreement", ok, standalone_value, got)
    expect_value_error(v, group, "relative unequal lengths", relative_fn, [1, 2], [1], scandal_tick=1, clarification_tick=1, total_ticks=2)
    expect_value_error(v, group, "relative NaN rejected", relative_fn, [1, math.nan], [1, 1], scandal_tick=1, clarification_tick=1, total_ticks=2)
    expect_value_error(v, group, "relative Inf rejected", relative_fn, [1, math.inf], [1, 1], scandal_tick=1, clarification_tick=1, total_ticks=2)
    expect_value_error(v, group, "relative window too short", relative_fn, [1] * 7, [1] * 7, scandal_tick=5, clarification_tick=6, total_ticks=7)


def check_s9(v: Reporter) -> None:
    group = "S9-summary-schema"
    install_run_experiments_import_stubs()
    module = import_module(v, group, "run_experiments")
    fn = require_callable(v, group, module, "write_summary_csv")
    if fn is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        results = []
        for row in synthetic_summary_rows():
            results.append(
                {
                    "exp_id": row["exp_id"],
                    "config": row,
                    "metrics": bait_metrics_namespace(row),
                    "relative_metrics_v4": official_relative_metrics(row),
                    "trust_trajectory": [5.0] * 29 + [5.0 + float(row.get("final_trust_gain_vs_control") or 0)],
                }
            )
        try:
            fn(results, out / "summary.csv")
        except Exception as exc:
            v.error(group, "write_summary_csv call", exc)
            return
        summary = out / "summary.csv"
        v.check(group, "summary.csv exists", summary.is_file(), "present", "absent")
        if not summary.is_file():
            return
        with summary.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fields = reader.fieldnames or []
        v.check(group, "9 rows", len(rows) == 9, 9, len(rows))
        for field in LEGACY_FIELDS + V4_FIELDS:
            v.check(group, f"{field} column", field in fields, "present", "absent")
        for row in rows:
            is_control = row.get("exp_id") == "NoClarification-Control"
            source = next(item for item in results if item["exp_id"] == row.get("exp_id"))
            official = source["relative_metrics_v4"]
            bait = source["metrics"]
            if is_control:
                if "final_trust_gain_vs_control" in row:
                    v.check(group, "control global v4 zero final", float(row["final_trust_gain_vs_control"]) == 0.0, 0, row.get("final_trust_gain_vs_control"))
                    v.check(group, "control final read from relative_metrics_v4", close(float(row["final_trust_gain_vs_control"]), official["final_trust_gain_vs_control"]) and not close(float(row["final_trust_gain_vs_control"]), getattr(bait, "final_trust_gain_vs_control")), official["final_trust_gain_vs_control"], row["final_trust_gain_vs_control"])
                if "post_scandal_auc_gain_vs_control" in row:
                    v.check(group, "control global v4 zero AUC", float(row["post_scandal_auc_gain_vs_control"]) == 0.0, 0, row.get("post_scandal_auc_gain_vs_control"))
                    v.check(group, "control AUC read from relative_metrics_v4", close(float(row["post_scandal_auc_gain_vs_control"]), official["post_scandal_auc_gain_vs_control"]) and not close(float(row["post_scandal_auc_gain_vs_control"]), getattr(bait, "post_scandal_auc_gain_vs_control")), official["post_scandal_auc_gain_vs_control"], row["post_scandal_auc_gain_vs_control"])
                for field in CONTROL_EMPTY_FIELDS:
                    if field in row:
                        v.check(group, f"control {field} empty", row.get(field, "") == "", "empty", row.get(field))
            else:
                for field in V4_FIELDS:
                    if field in row:
                        try:
                            ok = finite_number(float(row[field]))
                        except Exception:
                            ok = False
                        v.check(group, f"strategy {row.get('exp_id')} {field} finite", ok, "finite", row.get(field))
                        if ok:
                            v.check(group, f"strategy {row.get('exp_id')} {field} read from relative_metrics_v4", close(float(row[field]), official[field]) and not close(float(row[field]), getattr(bait, field)), official[field], row[field])
            if "trust_gain_vs_control" in row and "final_trust_gain_vs_control" in row and row["final_trust_gain_vs_control"] != "":
                v.check(group, f"{row.get('exp_id')} alias equality", close(float(row["trust_gain_vs_control"]), float(row["final_trust_gain_vs_control"])), row["final_trust_gain_vs_control"], row["trust_gain_vs_control"])


def expect_load_data_failure(v: Reporter, group: str, plot_module, name: str, run_dir: Path) -> None:
    plot_module.RESULTS_DIR = run_dir
    try:
        plot_module.load_data()
    except Exception:
        v.check(group, name, True)
    else:
        v.check(group, name, False, "exception", "loaded")


def check_s10(v: Reporter) -> None:
    group = "S10-analysis-fail-closed"
    plot_module = import_module(v, group, "analysis.plot_experiments")
    if plot_module is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        rows = synthetic_summary_rows()
        missing_metadata = base / "missing_metadata"
        missing_metadata.mkdir()
        write_summary(missing_metadata / "summary.csv", rows)
        expect_load_data_failure(v, group, plot_module, "missing run_metadata fails", missing_metadata)
        cases = [
            ("missing metrics fails", {"experiment_matrix": {"matrix_version": "3.0", "condition_count": 9}}),
            ("metrics schema not 4.0 fails", {**valid_metadata(), "metrics": {"schema_version": "3.9"}}),
            ("matrix not 3.0 fails", {"experiment_matrix": {"matrix_version": "2.0", "condition_count": 9}, "metrics": {"schema_version": "4.0"}}),
            ("condition_count not 9 fails", {"experiment_matrix": {"matrix_version": "3.0", "condition_count": 8}, "metrics": {"schema_version": "4.0"}}),
        ]
        for name, metadata in cases:
            case_dir = base / name.replace(" ", "_")
            case_dir.mkdir()
            write_summary(case_dir / "summary.csv", rows)
            write_metadata(case_dir / "run_metadata.json", metadata)
            expect_load_data_failure(v, group, plot_module, name, case_dir)
        good = base / "good"
        good.mkdir()
        write_summary(good / "summary.csv", rows)
        write_metadata(good / "run_metadata.json")
        plot_module.RESULTS_DIR = good
        try:
            df = plot_module.load_data()
            v.check(group, "valid data loads", len(df) == 9, 9, len(df))
            control = df[df["exp_id"] == "NoClarification-Control"]
            v.check(group, "control empty v4 fields allowed", len(control) == 1, 1, len(control))
        except Exception as exc:
            v.error(group, "valid data loads", exc)
        missing_field = base / "missing_field"
        missing_field.mkdir()
        fields = ["exp_id", "content_factor", "channel_factor", "timing_factor", "is_control"] + LEGACY_FIELDS + [field for field in V4_FIELDS if field != "final_trust_gain_vs_control"]
        write_summary_with_fields(missing_field / "summary.csv", rows, fields)
        write_metadata(missing_field / "run_metadata.json")
        expect_load_data_failure(v, group, plot_module, "missing core field fails", missing_field)
        bad_nan = base / "bad_nan"
        bad_nan.mkdir()
        nan_rows = [row.copy() for row in rows]
        nan_rows[0]["local_trust_effect_did_3"] = "NaN"
        write_summary(bad_nan / "summary.csv", nan_rows)
        write_metadata(bad_nan / "run_metadata.json")
        expect_load_data_failure(v, group, plot_module, "strategy NaN fails", bad_nan)
        bad_empty = base / "bad_empty"
        bad_empty.mkdir()
        empty_rows = [row.copy() for row in rows]
        empty_rows[0]["early_trust_auc_gain_5"] = ""
        write_summary(bad_empty / "summary.csv", empty_rows)
        write_metadata(bad_empty / "run_metadata.json")
        expect_load_data_failure(v, group, plot_module, "strategy empty v4 fails", bad_empty)


def check_s11(v: Reporter, mc) -> None:
    group = "S11-pareto-v4"
    fn = require_callable(v, group, mc, "compute_pareto_flags_v4")
    if fn is None:
        return
    rows = synthetic_summary_rows()
    result = list(fn(rows))
    expected = reference_pareto_rows(rows)
    v.check(group, "8 output rows", len(result) == 8, 8, len(result))
    exp_ids = [row.get("exp_id") for row in result]
    v.check(group, "exp_id unique", len(exp_ids) == len(set(exp_ids)) == 8, "8 unique", exp_ids)
    v.check(group, "control excluded", "NoClarification-Control" not in exp_ids, "excluded", exp_ids)
    v.check(group, "is_pareto bool", all(isinstance(row.get("is_pareto"), bool) for row in result), "all bool", result[:2])
    v.check(group, "sorted by exp_id", exp_ids == sorted(exp_ids), "exp_id ascending", exp_ids)
    got_flags = {row["exp_id"]: row.get("is_pareto") for row in result}
    want_flags = {row["exp_id"]: row.get("is_pareto") for row in expected}
    v.check(group, "independent Pareto reference", got_flags == want_flags, want_flags, got_flags)
    mutated = mutate_legacy(rows)
    v.check(group, "legacy changes do not alter flags", list(fn(mutated)) == result, "unchanged", "changed")
    changed = [row.copy() for row in rows]
    changed[0]["final_trust_gain_vs_control"] = 10.0
    changed[0]["post_scandal_auc_gain_vs_control"] = 10.0
    changed[0]["local_trust_effect_did_3"] = 10.0
    changed_result = list(fn(changed))
    changed_flags = {row["exp_id"]: row.get("is_pareto") for row in changed_result}
    changed_expected = {row["exp_id"]: row.get("is_pareto") for row in reference_pareto_rows(changed)}
    v.check(group, "v4 objective change updates expected result", changed_flags == changed_expected and changed_flags != got_flags, changed_expected, changed_flags)


def check_s12(v: Reporter, mc) -> None:
    group = "S12-equal-ranking"
    fn = require_callable(v, group, mc, "compute_equal_weight_ranking_v4")
    if fn is None:
        return
    rows = synthetic_summary_rows()
    ranked = list(fn(rows))
    v.check(group, "8 ranked rows", len(ranked) == 8, 8, len(ranked))
    v.check(group, "control excluded", all(row.get("exp_id") != "NoClarification-Control" for row in ranked), "excluded", ranked)
    v.check(group, "supplementary role", all(str(row.get("analysis_role", "")).lower() == "supplementary" for row in ranked), "all supplementary", ranked[:1])
    v.check(group, "score formula", all(close(float(row["score_equal"]), (float(row["final_norm"]) + float(row["auc_norm"]) + float(row["local_norm"])) / 3.0) for row in ranked), "exact formula", ranked[:1])
    v.check(group, "min and max normalize to 0/1", min(float(row["final_norm"]) for row in ranked) == 0.0 and max(float(row["final_norm"]) for row in ranked) == 1.0, "0 and 1", ranked)
    exp_order = [(row.get("rank"), row.get("exp_id")) for row in ranked]
    v.check(group, "sorted by rank then exp_id", exp_order == sorted(exp_order), "rank, exp_id", exp_order)
    reference = reference_ranking_rows(rows)
    comparable = [{key: row[key] for key in ["exp_id", "final_norm", "auc_norm", "local_norm", "score_equal", "rank", "analysis_role"]} for row in ranked]
    v.check(group, "independent ranking reference", comparable == reference, reference, comparable)
    constant_rows = [row.copy() for row in rows]
    for row in constant_rows:
        if not parse_bool(row.get("is_control", False)):
            row["local_trust_effect_did_3"] = 1.0
    constant_ranked = list(fn(constant_rows))
    v.check(group, "constant metric normalized 0.5", all(close(float(row.get("local_norm")), 0.5) for row in constant_ranked), "0.5", constant_ranked[:1])
    tied = synthetic_summary_rows()
    for row in tied:
        if row["exp_id"] in ("Strategy-01", "Strategy-02"):
            row["final_trust_gain_vs_control"] = 1.0
            row["post_scandal_auc_gain_vs_control"] = 1.0
            row["local_trust_effect_did_3"] = 1.0
        elif not parse_bool(row.get("is_control", False)):
            row["final_trust_gain_vs_control"] = 0.0
            row["post_scandal_auc_gain_vs_control"] = 0.0
            row["local_trust_effect_did_3"] = 0.0
    tied_ranked = list(fn(tied))
    top = [row for row in tied_ranked if row["exp_id"] in ("Strategy-01", "Strategy-02")]
    v.check(group, "average rank for tied first", all(close(float(row["rank"]), 1.5) for row in top), "1.5", top)
    v.check(group, "same rank ordered by exp_id", [row["exp_id"] for row in top] == ["Strategy-01", "Strategy-02"], "exp_id ascending", top)
    v.check(group, "legacy changes do not alter ranking", list(fn(mutate_legacy(rows))) == ranked, "unchanged", "changed")


def check_s13(v: Reporter, mc) -> None:
    group = "S13-weight-sensitivity"
    gen = require_callable(v, group, mc, "generate_weight_combinations")
    compute = require_callable(v, group, mc, "compute_ranking_sensitivity_v4")
    if gen is None or compute is None:
        return
    weights = list(gen())
    v.check(group, "66 combinations", len(weights) == 66, 66, len(weights))
    v.check(group, "66 unique combinations", len(set(tuple(w) for w in weights)) == 66, 66, len(set(tuple(w) for w in weights)))
    v.check(group, "0.1 integer grid", all(all(close(component * 10, round(component * 10)) for component in w) for w in weights), "all grid", weights[:3])
    v.check(group, "weight sums are 1", all(close(sum(w), 1.0) for w in weights), "all", weights[:3])
    rows = synthetic_summary_rows()
    sensitivity, robustness = compute(rows)
    v.check(group, "528 sensitivity rows", len(sensitivity) == 528, 528, len(sensitivity))
    v.check(group, "8 robustness rows", len(robustness) == 8, 8, len(robustness))
    ordering = [
        (
            float(row["weight_final"]),
            float(row["weight_auc"]),
            float(row["weight_local"]),
            float(row["rank"]),
            row["exp_id"],
        )
        for row in sensitivity
    ]
    v.check(group, "sensitivity sorted by weight/rank/exp_id", ordering == sorted(ordering), "ascending", ordering[:8])
    by_weight: dict[tuple[float, float, float], list[dict]] = {}
    for row in sensitivity:
        key = (float(row["weight_final"]), float(row["weight_auc"]), float(row["weight_local"]))
        by_weight.setdefault(key, []).append(row)
    v.check(group, "66 sensitivity weight groups", len(by_weight) == 66, 66, len(by_weight))
    v.check(group, "each weight group has 8 rows", all(len(group_rows) == 8 for group_rows in by_weight.values()), "all 8", {k: len(vv) for k, vv in list(by_weight.items())[:2]})
    v.check(group, "each weight group has 8 exp_id", all(len({row["exp_id"] for row in group_rows}) == 8 for group_rows in by_weight.values()), "all unique", "bad")
    top1_by_weight: dict[tuple[float, float, float], float] = {}
    for row in sensitivity:
        key = (float(row["weight_final"]), float(row["weight_auc"]), float(row["weight_local"]))
        top1_by_weight[key] = top1_by_weight.get(key, 0.0) + float(row["top1_credit"])
    v.check(group, "top1 credit sums per weight", all(close(total, 1.0) for total in top1_by_weight.values()), "all 1", list(top1_by_weight.items())[:1])
    ref_sens, ref_robust = reference_ranking_sensitivity(rows)
    v.check(group, "independent rank reference and ordering", sensitivity == ref_sens, "reference sensitivity same order", "different")
    v.check(group, "robustness reference", robustness == ref_robust, "reference robustness", "different")
    v.check(group, "robustness sorted by exp_id", [row["exp_id"] for row in robustness] == sorted(row["exp_id"] for row in robustness), "exp_id ascending", robustness)
    tied = synthetic_summary_rows()
    for row in tied:
        if parse_bool(row.get("is_control", False)):
            continue
        if row["exp_id"] in ("Strategy-01", "Strategy-02"):
            row["final_trust_gain_vs_control"] = 1.0
            row["post_scandal_auc_gain_vs_control"] = 1.0
            row["local_trust_effect_did_3"] = 1.0
        else:
            row["final_trust_gain_vs_control"] = 0.0
            row["post_scandal_auc_gain_vs_control"] = 0.0
            row["local_trust_effect_did_3"] = 0.0
    tied_sens, _ = compute(tied)
    first_group = [row for row in tied_sens if close(float(row["weight_final"]), 0.0) and close(float(row["weight_auc"]), 0.0) and close(float(row["weight_local"]), 1.0)]
    credits = {row["exp_id"]: float(row["top1_credit"]) for row in first_group}
    v.check(group, "two-way top1 split", close(credits.get("Strategy-01"), 0.5) and close(credits.get("Strategy-02"), 0.5) and close(sum(credits.values()), 1.0), "0.5/0.5 and total 1", credits)
    sensitivity2, robustness2 = compute(rows)
    v.check(group, "repeat deterministic", sensitivity == sensitivity2 and robustness == robustness2, "identical", "different")
    v.check(group, "legacy changes do not alter sensitivity", compute(mutate_legacy(rows)) == (sensitivity, robustness), "unchanged", "changed")


def check_s14(v: Reporter, mc) -> None:
    group = "S14-plotting"
    plot_module = import_module(v, group, "analysis.plot_experiments")
    if plot_module is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        output_dir = Path(tmp) / "figures"
        run_dir.mkdir()
        output_dir.mkdir()
        write_summary(run_dir / "summary.csv", synthetic_summary_rows())
        write_metadata(run_dir / "run_metadata.json")
        plot_module.RESULTS_DIR = run_dir
        plot_module.OUTPUT_DIR = output_dir
        try:
            df = plot_module.load_data()
        except Exception as exc:
            v.error(group, "load synthetic data", exc)
            return
        entry_names = [
            "plot_main_effects",
            "plot_heatmap_interactions",
            "plot_pareto_frontier",
            "plot_strategy_ranking",
            "plot_clarification_diagnosis",
            "plot_ranking_sensitivity_v4",
        ]
        for name in entry_names:
            fn = require_callable(v, group, plot_module, name)
            if fn is None:
                continue
            try:
                fn(df)
                v.check(group, f"{name} call", True)
            except Exception as exc:
                v.error(group, f"{name} call", exc)
        for fig in [
            "fig1_main_effects.png",
            "fig2_interactions.png",
            "fig3_pareto.png",
            "fig4_ranking.png",
            "fig5_clarification_diagnosis.png",
            "fig6_ranking_sensitivity.png",
        ]:
            path = output_dir / fig
            v.check(group, f"{fig} exists and nonempty", path.is_file() and path.stat().st_size > 0, "nonempty", "missing")
        pareto = getattr(mc, "compute_pareto_flags_v4", None) if mc is not None else None
        ranking = getattr(mc, "compute_equal_weight_ranking_v4", None) if mc is not None else None
        sensitivity = getattr(mc, "compute_ranking_sensitivity_v4", None) if mc is not None else None
        if callable(pareto) and callable(ranking) and callable(sensitivity):
            rows = synthetic_summary_rows()
            before = (list(pareto(rows)), list(ranking(rows)), sensitivity(rows))
            after = (list(pareto(mutate_legacy(rows))), list(ranking(mutate_legacy(rows))), sensitivity(mutate_legacy(rows)))
            v.check(group, "legacy changes do not alter v4 analyses", before == after, "unchanged", "changed")
        else:
            v.check(group, "v4 analysis helpers available for plot invariance", False, "all helpers callable", "missing helper")


def check_s15(v: Reporter, runtime_dir: str | None) -> None:
    group = "S15-runtime-artifacts"
    if not runtime_dir:
        v.warn(group, "runtime-dir", "skipped: no --runtime-dir supplied")
        return
    run_dir = Path(runtime_dir)
    for name in ["summary.csv", "run_metadata.json", "ranking_sensitivity.csv", "ranking_robustness.csv"]:
        v.check(group, f"{name} exists", (run_dir / name).is_file(), "present", "absent")
    rows: list[dict] = []
    try:
        with (run_dir / "summary.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        v.check(group, "summary has 9 rows", len(rows) == 9, 9, len(rows))
        controls = [row for row in rows if parse_bool(row.get("is_control", "False"))]
        strategies = [row for row in rows if not parse_bool(row.get("is_control", "False"))]
        v.check(group, "one control and eight strategies", len(controls) == 1 and len(strategies) == 8, "1/8", (len(controls), len(strategies)))
        fields = set(rows[0]) if rows else set()
        for field in LEGACY_FIELDS + V4_FIELDS:
            v.check(group, f"summary field {field}", field in fields, "present", "absent")
        for row in strategies:
            for field in V4_FIELDS:
                try:
                    ok = finite_number(float(row[field]))
                except Exception:
                    ok = False
                v.check(group, f"{row.get('exp_id')} {field} finite", ok, "finite", row.get(field))
            if "trust_gain_vs_control" in row and "final_trust_gain_vs_control" in row:
                v.check(group, f"{row.get('exp_id')} alias equality", close(float(row["trust_gain_vs_control"]), float(row["final_trust_gain_vs_control"])), row["final_trust_gain_vs_control"], row["trust_gain_vs_control"])
        if controls:
            control = controls[0]
            v.check(group, "control final zero", close(float(control.get("final_trust_gain_vs_control", "nan")), 0.0), 0, control.get("final_trust_gain_vs_control"))
            v.check(group, "control AUC zero", close(float(control.get("post_scandal_auc_gain_vs_control", "nan")), 0.0), 0, control.get("post_scandal_auc_gain_vs_control"))
            for field in CONTROL_EMPTY_FIELDS:
                v.check(group, f"control {field} empty", control.get(field, "") == "", "empty", control.get(field))
            if "trust_gain_vs_control" in control and "final_trust_gain_vs_control" in control:
                v.check(group, "control alias equality", close(float(control["trust_gain_vs_control"]), float(control["final_trust_gain_vs_control"])), control["final_trust_gain_vs_control"], control["trust_gain_vs_control"])
    except Exception as exc:
        v.error(group, "summary read", exc)
    try:
        metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
        matrix = metadata.get("experiment_matrix", {})
        v.check(group, "matrix metadata 3.0/9", matrix.get("matrix_version") == "3.0" and matrix.get("condition_count") == 9, "3.0/9", matrix)
        v.check(group, "metrics metadata full object", metadata.get("metrics") == expected_metrics_block(), expected_metrics_block(), metadata.get("metrics"))
    except Exception as exc:
        v.error(group, "run_metadata read", exc)
    sensitivity: list[dict] = []
    try:
        with (run_dir / "ranking_sensitivity.csv").open(newline="", encoding="utf-8") as f:
            sensitivity = list(csv.DictReader(f))
        v.check(group, "ranking_sensitivity has 528 rows", len(sensitivity) == 528, 528, len(sensitivity))
        by_weight: dict[tuple[float, float, float], list[dict]] = {}
        finite = True
        for row in sensitivity:
            key = (float(row["weight_final"]), float(row["weight_auc"]), float(row["weight_local"]))
            by_weight.setdefault(key, []).append(row)
            for field in ["weight_final", "weight_auc", "weight_local", "weighted_score", "rank", "top1_credit"]:
                finite = finite and finite_number(float(row[field]))
        v.check(group, "66 weight groups", len(by_weight) == 66, 66, len(by_weight))
        v.check(group, "each weight group has 8 exp_id", all(len({row["exp_id"] for row in items}) == 8 for items in by_weight.values()), "all 8", "bad")
        v.check(group, "each weight sum is 1", all(close(sum(key), 1.0) for key in by_weight), "all 1", list(by_weight)[:3])
        v.check(group, "each top1 credit sum is 1", all(close(sum(float(row["top1_credit"]) for row in items), 1.0) for items in by_weight.values()), "all 1", "bad")
        v.check(group, "sensitivity numeric finite", finite, "all finite", "bad")
    except Exception as exc:
        v.error(group, "ranking_sensitivity read", exc)
    try:
        with (run_dir / "ranking_robustness.csv").open(newline="", encoding="utf-8") as f:
            robustness = list(csv.DictReader(f))
        v.check(group, "ranking_robustness has 8 rows", len(robustness) == 8, 8, len(robustness))
        strategy_ids = {row["exp_id"] for row in rows if rows and not parse_bool(row.get("is_control", "False"))}
        v.check(group, "robustness exp_id set", {row.get("exp_id") for row in robustness} == strategy_ids and len(strategy_ids) == 8, strategy_ids, robustness)
        for row in robustness:
            rows_for_exp = [item for item in sensitivity if item.get("exp_id") == row.get("exp_id")]
            if not rows_for_exp:
                v.check(group, f"{row.get('exp_id')} robustness source rows", False, "present", "missing")
                continue
            ranks = [float(item["rank"]) for item in rows_for_exp]
            expected = {
                "top1_share": sum(float(item["top1_credit"]) for item in rows_for_exp) / NUM_WEIGHT_COMBINATIONS,
                "mean_rank": sum(ranks) / len(ranks),
                "median_rank": statistics.median(ranks),
                "best_rank": min(ranks),
                "worst_rank": max(ranks),
            }
            for field, want in expected.items():
                v.check(group, f"{row.get('exp_id')} {field} recomputed", close(float(row[field]), want), want, row.get(field))
    except Exception as exc:
        v.error(group, "ranking_robustness read", exc)
    for fig in [
        "fig1_main_effects.png",
        "fig2_interactions.png",
        "fig3_pareto.png",
        "fig4_ranking.png",
        "fig5_clarification_diagnosis.png",
        "fig6_ranking_sensitivity.png",
    ]:
        path = run_dir / "figures" / fig
        v.check(group, f"run figure {fig}", path.is_file() and path.stat().st_size > 0, "nonempty", "missing")
    latest = run_dir.parent / "latest"
    for rel in [
        "summary.csv",
        "ranking_sensitivity.csv",
        "ranking_robustness.csv",
        "figures/fig1_main_effects.png",
        "figures/fig2_interactions.png",
        "figures/fig3_pareto.png",
        "figures/fig4_ranking.png",
        "figures/fig5_clarification_diagnosis.png",
        "figures/fig6_ranking_sensitivity.png",
    ]:
        src = run_dir / rel
        dst = latest / rel
        v.check(group, f"latest {rel} exists", dst.is_file(), "present", "absent")
        if src.is_file() and dst.is_file():
            v.check(group, f"latest {rel} sha matches", sha256(src) == sha256(dst), sha256(src), sha256(dst))


def check_s16(v: Reporter) -> None:
    group = "S16-behavior-invariance"
    for rel, expected in EXPECTED_FROZEN_HASHES.items():
        path = ROOT / rel
        got = sha256(path) if path.exists() else "missing"
        v.check(group, f"frozen hash {rel}", got == expected, expected, got)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    wrapper_source = f'''
import os
import py_compile
import runpy
import shutil
import sys
import tempfile

root = {str(ROOT)!r}
target = os.path.join(root, "tests", "test_task003_experiment_matrix.py")
tmp_dir = tempfile.mkdtemp(prefix="task003_pyc_")
original_compile = py_compile.compile

def compile_wrapper(file, cfile=None, *args, **kwargs):
    if cfile == os.devnull:
        safe_name = str(abs(hash((file, len(os.listdir(tmp_dir)))))) + ".pyc"
        cfile = os.path.join(tmp_dir, safe_name)
    return original_compile(file, cfile=cfile, *args, **kwargs)

try:
    py_compile.compile = compile_wrapper
    sys.argv = ["tests/test_task003_experiment_matrix.py", "--offline-only"]
    os.chdir(root)
    runpy.run_path(target, run_name="__main__")
finally:
    py_compile.compile = original_compile
    shutil.rmtree(tmp_dir, ignore_errors=True)
'''
    try:
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / "task003_offline_wrapper.py"
            wrapper.write_text(wrapper_source, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(wrapper)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
    except Exception as exc:
        v.error(group, "TASK_003 wrapper subprocess", exc)
        return
    v.check(group, "TASK_003 exit code", result.returncode == 0, 0, result.returncode)
    v.check(group, "TASK_003 Failed: 0", "Failed: 0" in result.stdout, "Failed: 0", result.stdout[-500:])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", default=None)
    args = parser.parse_args(argv)

    v = Reporter()
    fixture = load_fixture(v)
    mc = None
    v.group("T0-syntax", lambda: check_t0(v))
    v.group("S0-fixture", lambda: check_s0(v, fixture))
    v.group("S1-version-constants", lambda: check_s1(v, import_module(v, "S1-version-constants", "metrics_calculator")))
    mc = sys.modules.get("metrics_calculator")
    v.group("S2-post-scandal-auc", lambda: check_s2(v, mc, fixture))
    v.group("S3-final-gain", lambda: check_s3(v, mc, fixture))
    v.group("S4-local-did", lambda: check_s4(v, mc, fixture))
    v.group("S5-early-auc", lambda: check_s5(v, mc, fixture))
    v.group("S6-early-slope", lambda: check_s6(v, mc, fixture))
    v.group("S7-secondary-harm", lambda: check_s7(v, mc))
    v.group("S8-control-and-relative", lambda: check_s8(v, mc, fixture))
    v.group("S9-summary-schema", lambda: check_s9(v))
    v.group("S10-analysis-fail-closed", lambda: check_s10(v))
    v.group("S11-pareto-v4", lambda: check_s11(v, mc))
    v.group("S12-equal-ranking", lambda: check_s12(v, mc))
    v.group("S13-weight-sensitivity", lambda: check_s13(v, mc))
    v.group("S14-plotting", lambda: check_s14(v, mc))
    v.group("S15-runtime-artifacts", lambda: check_s15(v, args.runtime_dir))
    v.group("S16-behavior-invariance", lambda: check_s16(v))
    return v.summary()


if __name__ == "__main__":
    raise SystemExit(main())
