#!/usr/bin/env python
"""TASK_005 prospective MDE, power, and formal-design acceptance checks."""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / ".kiro" / "specs" / "task005-replication-inference"
sys.path.insert(0, str(ROOT))

from replication_config import derive_seed, read_seed_ledger_csv  # noqa: E402
from task005_formal_oc_power import (  # noqa: E402
    FAMILY_ALPHA,
    POWER_PLANNING_ALPHA,
    TARGET_POWER,
    holm_adjust,
)


PRIMARY = (
    "P1_OVERALL_CLARIFICATION_POST_TRUST",
    "P2_CONTENT_POST_TRUST",
    "P3_TIMING_EARLY_TRUST",
    "P4_CHANNEL_REACH",
    "P5_OVERALL_CLARIFICATION_PURCHASE",
)
EXPECTED_SD = {
    "P1_OVERALL_CLARIFICATION_POST_TRUST": 0.0308323595637223,
    "P2_CONTENT_POST_TRUST": 0.042312929082541625,
    "P3_TIMING_EARLY_TRUST": 0.06827275321383339,
    "P4_CHANNEL_REACH": 0.17191729277636836,
    "P5_OVERALL_CLARIFICATION_PURCHASE": 0.017430417219459902,
}
EXPECTED_LOO = {
    "P1_OVERALL_CLARIFICATION_POST_TRUST": 0.03270265366171809,
    "P2_CONTENT_POST_TRUST": 0.04487933494934203,
    "P3_TIMING_EARLY_TRUST": 0.07238721552802843,
    "P4_CHANNEL_REACH": 0.18219342590896204,
    "P5_OVERALL_CLARIFICATION_PURCHASE": 0.018487749322186296,
}


def read_json(name: str) -> dict:
    return json.loads((SPEC / name).read_text(encoding="utf-8"))


def check(name: str, ok: bool, expected="", actual="") -> None:
    if ok:
        print(f"PASS {name}")
        return
    print(f"FAIL {name}: expected={expected!r} actual={actual!r}")
    raise AssertionError(name)


def main() -> int:
    mde = read_json("managerial_mde_contract1.0.json")
    variance = read_json("formal_power_variance_input1.0.json")
    power = read_json("prospective_power_analysis1.0.json")
    design = read_json("task005_formal_design2.0.json")

    values = {name: mde["mde"][name]["value"] for name in PRIMARY}
    check("MDE exact freeze", values == {
        "P1_OVERALL_CLARIFICATION_POST_TRUST": 0.15,
        "P2_CONTENT_POST_TRUST": 0.15,
        "P3_TIMING_EARLY_TRUST": 0.15,
        "P4_CHANNEL_REACH": 0.15,
        "P5_OVERALL_CLARIFICATION_PURCHASE": 0.05,
    })
    check("trust MDEs all equal 0.15", all(values[name] == 0.15 for name in PRIMARY[:3]))
    check("P4 and P5 MDEs exact", values[PRIMARY[3]] == 0.15 and values[PRIMARY[4]] == 0.05)

    check("variance provenance", variance["variance_source"] == "task005-real-variance-pilot-v3")
    check("sample SD exact", variance["sample_sd"] == EXPECTED_SD)
    check("LOO max exact", variance["loo_sd_max"] == EXPECTED_LOO)
    q = chi2.ppf(0.10, 9)
    factor = math.sqrt(9 / q)
    for name in PRIMARY:
        expected_u90 = EXPECTED_SD[name] * factor
        check(
            f"chi-square U90 formula {name}",
            math.isclose(variance["sd_u90"][name], expected_u90, rel_tol=0, abs_tol=1e-15),
            expected_u90,
            variance["sd_u90"][name],
        )
        check("planning SD >= sample and LOO", variance["planning_sd"][name] >= EXPECTED_SD[name] and variance["planning_sd"][name] >= EXPECTED_LOO[name])

    check("Bonferroni planning alpha exact", POWER_PLANNING_ALPHA == 0.01 and power["power_planning_alpha"] == 0.01)
    check("family alpha exact", FAMILY_ALPHA == 0.05 and power["familywise_alpha"] == 0.05)
    for name in PRIMARY:
        item = power["required_n"][name]
        check(f"minimal N achieved {name}", item["achieved_power_at_N"] >= TARGET_POWER)
        check(f"minimal N previous below target {name}", item["power_at_N_minus_1"] < TARGET_POWER)
        check(f"numeric validation {name}", item["validation"]["passed"] is True and item["validation"]["max_abs_diff"] <= 1e-6)

    fixture = holm_adjust({"a": 0.001, "b": 0.012, "c": 0.021, "d": 0.20, "e": 0.80})
    check("Holm fixture rejects prefix only", [fixture[k]["holm_reject"] for k in ("a", "b", "c", "d", "e")] == [True, True, False, False, False])
    check("null FWER simulation tolerance", power["oc_results"]["SCENARIO_NULL"]["empirical_FWER"] <= 0.055)

    cov = np.array(
        [[variance["planning_covariance_matrix"][r][c] for c in PRIMARY] for r in PRIMARY],
        dtype=float,
    )
    check("planning covariance PSD", float(np.linalg.eigvalsh(cov).min()) >= -1e-12)

    ledger = read_seed_ledger_csv(ROOT / design["formal_seed_ledger_path"])
    check("formal seed ledger N", len(ledger) == design["N_ATTEMPT_BLOCKS"] == power["N_REQUIRED"])
    pilot_seed_values = {field: set() for field in ("simulation_seed", "requested_llm_seed", "python_hash_seed")}
    for path in (ROOT / "results" / "pilots").rglob("seed_ledger.csv"):
        try:
            rows = read_seed_ledger_csv(path)
        except Exception:
            with path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        for row in rows:
            for field in pilot_seed_values:
                if field in row and row[field] != "":
                    pilot_seed_values[field].add(int(row[field]))
    v2 = read_json("real_llm_variance_pilot_v2_result1.0.json")
    for idx in range(1, 11):
        pilot_seed_values["simulation_seed"].add(derive_seed(v2["master_seed"], idx, "simulation"))
        pilot_seed_values["requested_llm_seed"].add(derive_seed(v2["master_seed"], idx, "llm"))
        pilot_seed_values["python_hash_seed"].add(derive_seed(v2["master_seed"], idx, "python-hash"))
    collisions = []
    for row in ledger:
        for field, seen in pilot_seed_values.items():
            if row[field] in seen:
                collisions.append((row["replicate_id"], field, row[field]))
    check("formal seed no-overlap", collisions == [], [], collisions)

    forbidden_mde_text = (SPEC / "managerial_mde_contract1.0.json").read_text(encoding="utf-8")
    for token in ("all_block_estimands", "mean_effect", "strategy_winner"):
        check(f"MDE firewall token absent {token}", token not in forbidden_mde_text)
    power_source = (ROOT / "task005_formal_oc_power.py").read_text(encoding="utf-8")
    for token in ("all_block_estimands", "mean_effect", "observed_effect", "strategy_winner"):
        check(f"power source does not read pilot effect token {token}", token not in power_source)
    check("pilot means not used for MDE", power["observed_variance_pilot_means_used_for_mde"] is False)
    check("pilot means not used for power alternative", power["observed_variance_pilot_means_used_for_power_alternative"] is False)
    check("pilot p-values not used", power["p_values_from_pilot_used"] is False)
    check("formal execution disabled", design["execution_authorized"] is False and power["formal_execution_authorized"] is False)
    print("SUMMARY Passed: all Failed: 0 Warned: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
