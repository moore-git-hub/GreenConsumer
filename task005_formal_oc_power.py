"""TASK_005 prospective formal OC and power planning.

This module performs offline statistical planning only. It reads frozen MDE
and variance-planning artifacts, computes exact one-sample noncentral-t sample
sizes, and simulates multivariate-normal operating characteristics. It never
imports model/provider code and never calls an LLM.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping

import numpy as np
from scipy.integrate import quad
from scipy.stats import chi2, norm, nct, t


ROOT = Path(__file__).resolve().parent
SPEC_DIR = ROOT / ".kiro" / "specs" / "task005-replication-inference"
MDE_PATH = SPEC_DIR / "managerial_mde_contract1.0.json"
VARIANCE_INPUT_PATH = SPEC_DIR / "formal_power_variance_input1.0.json"
POWER_OUTPUT_PATH = SPEC_DIR / "prospective_power_analysis1.0.json"

OC_MASTER_SEED = 2026081102
MONTE_CARLO_REPS = 200000
PRIMARY_ESTIMANDS = (
    "P1_OVERALL_CLARIFICATION_POST_TRUST",
    "P2_CONTENT_POST_TRUST",
    "P3_TIMING_EARLY_TRUST",
    "P4_CHANNEL_REACH",
    "P5_OVERALL_CLARIFICATION_PURCHASE",
)
SHORT_NAMES = ("P1", "P2", "P3", "P4", "P5")
FAMILY_ALPHA = 0.05
POWER_PLANNING_ALPHA = 0.01
TARGET_POWER = 0.90
MDE_HEAD = "9b29ee285a539e9ab82f26279630044bf6c18623"
INFERENCE_HEAD = "d011a8a38b92edc45d90aaf24757f87c80eadfc6"
VARIANCE_SOURCE_HEAD = "1b50913519f09f7eee1341b988862b9229eb5265"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def holm_adjust(p_values: Mapping[str, float], alpha: float = FAMILY_ALPHA) -> dict[str, dict]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    m = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    reject_prefix = True
    rejects: dict[str, bool] = {}
    for index, (name, p_value) in enumerate(ordered, start=1):
        adj = min(1.0, max(running, (m - index + 1) * p_value))
        adjusted[name] = adj
        running = adj
        threshold = alpha / (m - index + 1)
        reject = reject_prefix and p_value <= threshold
        rejects[name] = reject
        if not reject:
            reject_prefix = False
    return {
        name: {
            "raw_p": float(p_values[name]),
            "holm_adjusted_p": float(adjusted[name]),
            "holm_reject": bool(rejects[name]),
        }
        for name in p_values
    }


def one_sample_nct_power_scipy(
    effect: float,
    sigma: float,
    n: int,
    *,
    alpha: float = POWER_PLANNING_ALPHA,
) -> float:
    if n < 2:
        raise ValueError("n must be >= 2")
    if sigma <= 0 or not math.isfinite(sigma):
        raise ValueError("sigma must be positive and finite")
    df = n - 1
    ncp = abs(effect) * math.sqrt(n) / sigma
    crit = t.ppf(1 - alpha / 2, df)
    power = nct.sf(crit, df, ncp) + nct.cdf(-crit, df, ncp)
    if not math.isfinite(power):
        raise ValueError("noncentral-t power is not finite")
    return float(power)


def one_sample_nct_power_integral(
    effect: float,
    sigma: float,
    n: int,
    *,
    alpha: float = POWER_PLANNING_ALPHA,
    eps: float = 1e-11,
) -> float:
    if n < 2:
        raise ValueError("n must be >= 2")
    if sigma <= 0 or not math.isfinite(sigma):
        raise ValueError("sigma must be positive and finite")
    df = n - 1
    delta = abs(effect) * math.sqrt(n) / sigma
    crit = t.ppf(1 - alpha / 2, df)

    def integrand(v: float) -> float:
        scale = math.sqrt(v / df)
        conditional = norm.sf(crit * scale - delta) + norm.cdf(-crit * scale - delta)
        return conditional * chi2.pdf(v, df)

    power, err = quad(integrand, 0.0, np.inf, epsabs=eps, epsrel=eps, limit=200)
    if not math.isfinite(power) or not math.isfinite(err):
        raise ValueError("integrated power is not finite")
    return float(power)


def required_n_for_estimand(effect: float, sigma: float) -> dict:
    validation_max_abs_diff = 0.0
    scipy_nonfinite_candidates = 0
    fallback_validation_used = False
    for n in range(2, 10000):
        integral_power = one_sample_nct_power_integral(effect, sigma, n)
        try:
            scipy_power = one_sample_nct_power_scipy(effect, sigma, n)
        except ValueError:
            scipy_nonfinite_candidates += 1
            scipy_power = None
        if scipy_power is not None:
            diff = abs(scipy_power - integral_power)
            validation_max_abs_diff = max(validation_max_abs_diff, diff)
            if diff > 1e-6:
                raise AssertionError(f"power validation mismatch at N={n}: {diff}")
        if integral_power >= TARGET_POWER:
            prev_integral = (
                one_sample_nct_power_integral(effect, sigma, n - 1) if n > 2 else 0.0
            )
            prev = one_sample_nct_power_scipy(effect, sigma, n - 1) if n > 2 else 0.0
            try:
                scipy_at_n = one_sample_nct_power_scipy(effect, sigma, n)
                at_n_diff = abs(scipy_at_n - integral_power)
            except ValueError:
                fallback_validation_used = True
                scipy_nonfinite_candidates += 1
                independent_power = one_sample_nct_power_integral(
                    effect,
                    sigma,
                    n,
                    eps=1e-12,
                )
                at_n_diff = abs(independent_power - integral_power)
            validation_max_abs_diff = max(
                validation_max_abs_diff,
                at_n_diff,
                abs(prev - prev_integral),
            )
            if validation_max_abs_diff > 1e-6:
                raise AssertionError(
                    f"power validation mismatch at minimal N={n}: "
                    f"{validation_max_abs_diff}"
                )
            return {
                "required_N": n,
                "achieved_power_at_N": integral_power,
                "power_at_N_minus_1": prev,
                "validation": {
                    "method_a": "scipy.stats.nct",
                    "method_b": "chi-square-integrated shifted normal",
                    "fallback_method_for_scipy_nonfinite": (
                        "higher-precision chi-square-integrated shifted normal"
                    ),
                    "max_abs_diff": validation_max_abs_diff,
                    "passed": validation_max_abs_diff <= 1e-6,
                    "scipy_nonfinite_candidates_before_minimal_n": scipy_nonfinite_candidates,
                    "fallback_validation_used": fallback_validation_used,
                },
            }
    raise AssertionError("required N search exceeded limit")


def _scenario_means(mde: Mapping[str, float]) -> dict[str, list[float]]:
    p = [mde[name] for name in PRIMARY_ESTIMANDS]
    scenarios = {
        "SCENARIO_NULL": [0.0, 0.0, 0.0, 0.0, 0.0],
        "SCENARIO_ALL_MDE": p,
        "SINGLE_ACTIVE_P1": [p[0], 0.0, 0.0, 0.0, 0.0],
        "SINGLE_ACTIVE_P2": [0.0, p[1], 0.0, 0.0, 0.0],
        "SINGLE_ACTIVE_P3": [0.0, 0.0, p[2], 0.0, 0.0],
        "SINGLE_ACTIVE_P4": [0.0, 0.0, 0.0, p[3], 0.0],
        "SINGLE_ACTIVE_P5": [0.0, 0.0, 0.0, 0.0, p[4]],
        "SINGLE_ACTIVE_P2_NEGATIVE": [0.0, -p[1], 0.0, 0.0, 0.0],
    }
    return scenarios


def _holm_reject_matrix(p_values: np.ndarray, alpha: float = FAMILY_ALPHA) -> np.ndarray:
    reps, m = p_values.shape
    order = np.argsort(p_values, axis=1, kind="mergesort")
    sorted_p = np.take_along_axis(p_values, order, axis=1)
    thresholds = np.array([alpha / (m - i) for i in range(m)], dtype=float)
    pass_step = sorted_p <= thresholds
    sorted_reject = np.logical_and.accumulate(pass_step, axis=1)
    rejects = np.zeros((reps, m), dtype=bool)
    np.put_along_axis(rejects, order, sorted_reject, axis=1)
    return rejects


def simulate_oc(
    *,
    n_required: int,
    planning_covariance: np.ndarray,
    mde: Mapping[str, float],
    reps: int = MONTE_CARLO_REPS,
    seed: int = OC_MASTER_SEED,
) -> dict:
    rng = np.random.default_rng(seed)
    scenarios = _scenario_means(mde)
    out: dict[str, dict] = {}
    for offset, (scenario, mean) in enumerate(scenarios.items()):
        local_rng = np.random.default_rng(seed + offset)
        samples = local_rng.multivariate_normal(
            mean=np.array(mean, dtype=float),
            cov=planning_covariance,
            size=(reps, n_required),
            method="svd",
        )
        means = samples.mean(axis=1)
        sds = samples.std(axis=1, ddof=1)
        ses = sds / math.sqrt(n_required)
        t_stats = np.divide(means, ses, out=np.zeros_like(means), where=ses > 0)
        p_values = 2 * t.sf(np.abs(t_stats), df=n_required - 1)
        rejects = _holm_reject_matrix(p_values)
        reject_rates = rejects.mean(axis=0)
        entry = {
            "mean_vector": {SHORT_NAMES[i]: float(mean[i]) for i in range(5)},
            "holm_detection_probability": {
                SHORT_NAMES[i]: float(reject_rates[i]) for i in range(5)
            },
            "any_primary_detected": float(rejects.any(axis=1).mean()),
            "all_five_detected": float(rejects.all(axis=1).mean()),
        }
        if scenario == "SCENARIO_NULL":
            entry["empirical_FWER"] = entry["any_primary_detected"]
            entry["engineering_check_passed"] = entry["empirical_FWER"] <= 0.055
        elif scenario.startswith("SINGLE_ACTIVE_"):
            active = scenario.replace("SINGLE_ACTIVE_", "")
            if active == "P2_NEGATIVE":
                active = "P2"
            active_index = SHORT_NAMES.index(active)
            inactive = [i for i in range(5) if i != active_index]
            entry["target_detection_probability"] = float(reject_rates[active_index])
            entry["false_positive_family_probability"] = float(
                rejects[:, inactive].any(axis=1).mean()
            )
        out[scenario] = entry
        _ = rng  # Keep the master seed explicit in the public contract.
    return out


def build_power_artifact() -> dict:
    mde_contract = read_json(MDE_PATH)
    variance_input = read_json(VARIANCE_INPUT_PATH)
    mde = {
        name: float(mde_contract["mde"][name]["value"])
        for name in PRIMARY_ESTIMANDS
    }
    planning_sd = {
        name: float(variance_input["planning_sd"][name])
        for name in PRIMARY_ESTIMANDS
    }
    planning_covariance = np.array(
        [
            [float(variance_input["planning_covariance_matrix"][row][col]) for col in PRIMARY_ESTIMANDS]
            for row in PRIMARY_ESTIMANDS
        ],
        dtype=float,
    )
    required = {
        name: required_n_for_estimand(mde[name], planning_sd[name])
        for name in PRIMARY_ESTIMANDS
    }
    n_required = max(item["required_N"] for item in required.values())
    n_driver = [
        name for name, item in required.items()
        if item["required_N"] == n_required
    ]
    oc = simulate_oc(
        n_required=n_required,
        planning_covariance=planning_covariance,
        mde=mde,
    )
    if not oc["SCENARIO_NULL"]["engineering_check_passed"]:
        raise AssertionError("null FWER engineering check failed")
    return {
        "schema_version": "prospective_power_analysis1.0",
        "task": "TASK_005",
        "stage": "managerial-mde-and-prospective-power-v1",
        "MDE_HEAD": MDE_HEAD,
        "INFERENCE_HEAD": INFERENCE_HEAD,
        "variance_source": "task005-real-variance-pilot-v3",
        "variance_source_head": VARIANCE_SOURCE_HEAD,
        "variance_input_artifact": ".kiro/specs/task005-replication-inference/formal_power_variance_input1.0.json",
        "primary_family_size": 5,
        "familywise_alpha": FAMILY_ALPHA,
        "final_multiplicity_procedure": "Holm step-down",
        "power_planning_alpha": POWER_PLANNING_ALPHA,
        "power_planning_alpha_sided": "two-sided",
        "target_marginal_power": TARGET_POWER,
        "mde": mde,
        "planning_sd": planning_sd,
        "required_n": required,
        "N_REQUIRED": n_required,
        "N_DRIVER": n_driver,
        "oc_master_seed": OC_MASTER_SEED,
        "monte_carlo_reps": MONTE_CARLO_REPS,
        "oc_results": oc,
        "observed_variance_pilot_means_used_for_mde": False,
        "observed_variance_pilot_means_used_for_power_alternative": False,
        "p_values_from_pilot_used": False,
        "formal_execution": False,
        "formal_execution_authorized": False,
        "real_llm_calls": 0,
    }


def main() -> int:
    artifact = build_power_artifact()
    POWER_OUTPUT_PATH.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "N_REQUIRED": artifact["N_REQUIRED"],
        "N_DRIVER": artifact["N_DRIVER"],
        "OC_NULL_FWER": artifact["oc_results"]["SCENARIO_NULL"]["empirical_FWER"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
