from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from oc_calibration import (
    holm_adjust,
    student_t_confidence_intervals,
    wilson_interval,
)

EXPECTED_OC_DESIGN_SHA256 = (
    "D01AE3375CB59B27A6554DE2612469896B605FB10AA294AB77653D4C4728DF29"
)
EXPECTED_I5C0_EVIDENCE_SHA256 = (
    "106638D4C6DE9D923798CEBF4E128CE4B4F95F5B03829443D2ED19036A33179D"
)

METRICS = (
    "final_trust_gain_vs_control",
    "post_scandal_auc_gain_vs_control",
)
STRATEGIES = (
    "Empathy-Hub-Delayed",
    "Empathy-Hub-Immediate",
    "Empathy-Random-Delayed",
    "Empathy-Random-Immediate",
    "Rational-Hub-Delayed",
    "Rational-Hub-Immediate",
    "Rational-Random-Delayed",
    "Rational-Random-Immediate",
)
CONTRASTS = (
    "Content",
    "Channel",
    "Timing",
    "Content_x_Channel",
    "Content_x_Timing",
    "Channel_x_Timing",
)
CANONICAL_BLOCKS = ("P001", "P002", "P003", "P004", "P005")
FAMILY_INDICES = {
    "strategy_primary_16": np.arange(0, 16, dtype=int),
    "factorial_confirmatory_12": np.arange(16, 28, dtype=int),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def derive_cell_seed(base_seed: int, namespace: str) -> int:
    """
    Frozen seed derivation:
      SHA256(f"{base_seed}|{namespace}") -> first 8 bytes -> unsigned big-endian.
    """
    payload = f"{int(base_seed)}|{namespace}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _refuse_existing_output(output_dir: Path) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refuse overwrite existing output directory: {output_dir}")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refuse empty CSV output: {path.name}")
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _family_holm_reject(raw_p: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    adjusted = holm_adjust(raw_p)
    return adjusted <= alpha


def _vectorized_t_pvalues(samples: np.ndarray) -> np.ndarray:
    """
    samples shape = iterations x blocks x estimands.
    Return iterations x estimands two-sided p-values against 0.
    """
    if samples.ndim != 3:
        raise ValueError("samples must be 3-D")
    n = samples.shape[1]
    means = samples.mean(axis=1)
    sds = samples.std(axis=1, ddof=1)
    result = np.empty_like(means)

    zero = sds == 0.0
    result[zero & (means == 0.0)] = 1.0
    result[zero & (means != 0.0)] = 0.0

    regular = ~zero
    t_values = np.zeros_like(means)
    t_values[regular] = means[regular] / (sds[regular] / math.sqrt(n))
    result[regular] = 2.0 * stats.t.sf(np.abs(t_values[regular]), df=n - 1)
    return np.clip(result, 0.0, 1.0)


def _vectorized_ci_contains_truth(
    samples: np.ndarray,
    truth: np.ndarray,
    confidence: float = 0.95,
) -> np.ndarray:
    n = samples.shape[1]
    means = samples.mean(axis=1)
    sds = samples.std(axis=1, ddof=1)
    critical = float(stats.t.ppf(0.5 + confidence / 2.0, n - 1))
    half = critical * sds / math.sqrt(n)
    lower = means - half
    upper = means + half
    return (lower <= truth[None, :]) & (truth[None, :] <= upper)


def _holm_rejection_matrix(raw_p: np.ndarray, family_indices: np.ndarray) -> np.ndarray:
    """
    raw_p shape = iterations x all-estimands.
    Return bool matrix iterations x family-size.
    """
    family_p = raw_p[:, family_indices]
    iterations, m = family_p.shape
    order = np.argsort(family_p, axis=1, kind="stable")
    sorted_p = np.take_along_axis(family_p, order, axis=1)
    multipliers = (m - np.arange(m))[None, :]
    scaled = sorted_p * multipliers
    adjusted_sorted = np.minimum(
        1.0,
        np.maximum.accumulate(scaled, axis=1),
    )
    adjusted = np.empty_like(adjusted_sorted)
    row_idx = np.arange(iterations)[:, None]
    adjusted[row_idx, order] = adjusted_sorted
    return adjusted <= 0.05


def _draw_noise(
    residuals: np.ndarray,
    iterations: int,
    n_blocks: int,
    stress: float,
    cell_seed: int,
) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(cell_seed))
    row_indices = rng.integers(
        0,
        residuals.shape[0],
        size=(iterations, n_blocks),
    )
    sign_bits = rng.integers(
        0,
        2,
        size=(iterations, n_blocks),
    )
    signs = np.where(sign_bits == 0, -1.0, 1.0)
    return stress * residuals[row_indices] * signs[:, :, None]


def _estimate_with_wilson(successes: int, trials: int) -> dict[str, float | int]:
    point = successes / trials
    lower, upper = wilson_interval(successes, trials, 0.95)
    return {
        "successes": int(successes),
        "trials": int(trials),
        "point": float(point),
        "wilson95_lower": float(lower),
        "wilson95_upper": float(upper),
    }


def _input_matrix_rows(
    residuals: np.ndarray,
    labels: list[dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for j, label in enumerate(labels):
        row = dict(label)
        for i, block in enumerate(CANONICAL_BLOCKS):
            row[block] = float(residuals[i, j])
        row["sample_sd"] = float(residuals[:, j].std(ddof=1))
        rows.append(row)
    return rows


def load_synthetic_fixture(fixture_path: Path) -> tuple[np.ndarray, list[dict[str, str]]]:
    data = json.loads(fixture_path.read_text(encoding="utf-8-sig"))
    matrix = np.asarray(data["centered_residual_matrix"], dtype=float)
    if matrix.shape != (5, 28):
        raise ValueError(f"fixture shape mismatch: {matrix.shape}")
    labels = [
        {
            "estimand_id": str(row["estimand_id"]),
            "metric": str(row["metric"]),
            "family": str(row["family"]),
            "estimand_family": str(row["kind"]),
            "estimand_label": str(row["label"]),
        }
        for row in data["estimands"]
    ]
    if len(labels) != 28:
        raise ValueError("fixture estimand count mismatch")
    return matrix, labels


def load_i5c0_matrix(evidence_zip: Path) -> tuple[np.ndarray, list[dict[str, str]]]:
    if sha256_file(evidence_zip) != EXPECTED_I5C0_EVIDENCE_SHA256:
        raise ValueError("I5C0 evidence SHA256 mismatch")

    with zipfile.ZipFile(evidence_zip) as archive:
        if archive.testzip() is not None:
            raise ValueError("I5C0 evidence ZIP CRC failure")
        name = "five_block_estimand_sd_inventory.csv"
        if name not in archive.namelist():
            raise ValueError(f"I5C0 evidence missing {name}")
        text = archive.read(name).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))

    if len(rows) != 42:
        raise ValueError(f"expected 42 I5C0 inventory rows, got {len(rows)}")

    by_key = {
        (row["metric"], row["estimand_family"], row["estimand_id"]): row
        for row in rows
    }

    ordered: list[dict[str, str]] = []
    values: list[list[float]] = []

    for metric in METRICS:
        for strategy in STRATEGIES:
            key = (metric, "strategy_primary", strategy)
            if key not in by_key:
                raise ValueError(f"missing I5C0 estimand {key}")
            row = by_key[key]
            ordered.append(
                {
                    "estimand_id": f"{metric}::{strategy}",
                    "metric": metric,
                    "family": "strategy_primary_16",
                    "estimand_family": "strategy_primary",
                    "estimand_label": strategy,
                }
            )
            values.append([float(row[f"value_{block}"]) for block in CANONICAL_BLOCKS])

    for metric in METRICS:
        for contrast in CONTRASTS:
            key = (metric, "factorial_confirmatory", contrast)
            if key not in by_key:
                raise ValueError(f"missing I5C0 estimand {key}")
            row = by_key[key]
            ordered.append(
                {
                    "estimand_id": f"{metric}::{contrast}",
                    "metric": metric,
                    "family": "factorial_confirmatory_12",
                    "estimand_family": "factorial_confirmatory",
                    "estimand_label": contrast,
                }
            )
            values.append([float(row[f"value_{block}"]) for block in CANONICAL_BLOCKS])

    matrix = np.asarray(values, dtype=float).T
    if matrix.shape != (5, 28) or not np.isfinite(matrix).all():
        raise ValueError("reconstructed I5C0 matrix invalid")

    centered = matrix - matrix.mean(axis=0, keepdims=True)
    centered = centered - centered.mean(axis=0, keepdims=True)
    if np.any(centered.std(axis=0, ddof=1) <= 0.0):
        raise ValueError("reconstructed residual SD must be positive")
    return centered, ordered


def validate_design_hash(design_path: Path) -> None:
    if sha256_file(design_path) != EXPECTED_OC_DESIGN_SHA256:
        raise ValueError("OC design SHA256 mismatch")


def _primary_cell(
    residuals: np.ndarray,
    baseline_sd: np.ndarray,
    labels: list[dict[str, str]],
    n_blocks: int,
    stress: float,
    stream: str,
    base_seed: int,
    iterations: int,
    profile: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    namespace = f"{profile}|{stream}|{n_blocks}|{stress:.1f}|primary"
    seed = derive_cell_seed(base_seed, namespace)
    noise = _draw_noise(
        residuals,
        iterations,
        n_blocks,
        stress,
        seed,
    )

    # Global null.
    null_p = _vectorized_t_pvalues(noise)
    ci_contains = _vectorized_ci_contains_truth(
        noise,
        np.zeros(28, dtype=float),
        0.95,
    )

    family_stats: dict[str, dict[str, Any]] = {}
    for family_name, indices in FAMILY_INDICES.items():
        rej = _holm_rejection_matrix(null_p, indices)
        any_rej = rej.any(axis=1)
        family_stats[family_name] = _estimate_with_wilson(
            int(any_rej.sum()),
            iterations,
        )

    coverage_counts = ci_contains.sum(axis=0)
    coverage = coverage_counts / iterations

    primary_row: dict[str, Any] = {
        "profile": profile,
        "stream": stream,
        "candidate_n": n_blocks,
        "variance_multiplier": stress,
        "iterations": iterations,
        "cell_seed": seed,
        "strategy_fwer_successes": family_stats["strategy_primary_16"]["successes"],
        "strategy_fwer_point": family_stats["strategy_primary_16"]["point"],
        "strategy_fwer_wilson95_lower": family_stats["strategy_primary_16"]["wilson95_lower"],
        "strategy_fwer_wilson95_upper": family_stats["strategy_primary_16"]["wilson95_upper"],
        "factorial_fwer_successes": family_stats["factorial_confirmatory_12"]["successes"],
        "factorial_fwer_point": family_stats["factorial_confirmatory_12"]["point"],
        "factorial_fwer_wilson95_lower": family_stats["factorial_confirmatory_12"]["wilson95_lower"],
        "factorial_fwer_wilson95_upper": family_stats["factorial_confirmatory_12"]["wilson95_upper"],
        "mean_ci_coverage": float(coverage.mean()),
        "minimum_ci_coverage": float(coverage.min()),
    }

    power_rows: list[dict[str, Any]] = []
    for d in (0.50, 0.80):
        for active in range(28):
            truth = np.zeros(28, dtype=float)
            truth[active] = d * baseline_sd[active]
            sample = noise + truth[None, None, :]
            raw_p = _vectorized_t_pvalues(sample)
            family_name = labels[active]["family"]
            indices = FAMILY_INDICES[family_name]
            family_rej = _holm_rejection_matrix(raw_p, indices)
            local_position = int(np.where(indices == active)[0][0])
            active_rej = family_rej[:, local_position]
            inactive_mask = np.ones(indices.size, dtype=bool)
            inactive_mask[local_position] = False
            inactive_any = (
                family_rej[:, inactive_mask].any(axis=1)
                if inactive_mask.any()
                else np.zeros(iterations, dtype=bool)
            )
            active_ci = _estimate_with_wilson(
                int(active_rej.sum()),
                iterations,
            )
            inactive_ci = _estimate_with_wilson(
                int(inactive_any.sum()),
                iterations,
            )
            power_rows.append(
                {
                    "profile": profile,
                    "stream": stream,
                    "candidate_n": n_blocks,
                    "variance_multiplier": stress,
                    "iterations": iterations,
                    "standardized_effect_d": d,
                    "active_estimand_index": active,
                    "active_estimand_id": labels[active]["estimand_id"],
                    "family": family_name,
                    "active_rejection_successes": active_ci["successes"],
                    "active_rejection_point": active_ci["point"],
                    "active_rejection_wilson95_lower": active_ci["wilson95_lower"],
                    "active_rejection_wilson95_upper": active_ci["wilson95_upper"],
                    "inactive_family_false_rejection_successes": inactive_ci["successes"],
                    "inactive_family_false_rejection_point": inactive_ci["point"],
                }
            )

    dense_truth = 0.50 * baseline_sd
    dense_sample = noise + dense_truth[None, None, :]
    dense_p = _vectorized_t_pvalues(dense_sample)
    dense_rows: list[dict[str, Any]] = []
    for family_name, indices in FAMILY_INDICES.items():
        family_rej = _holm_rejection_matrix(dense_p, indices)
        probabilities = family_rej.mean(axis=0)
        dense_rows.append(
            {
                "profile": profile,
                "stream": stream,
                "candidate_n": n_blocks,
                "variance_multiplier": stress,
                "iterations": iterations,
                "family": family_name,
                "standardized_effect_d": 0.50,
                "mean_discovery_probability": float(probabilities.mean()),
                "minimum_discovery_probability": float(probabilities.min()),
            }
        )

    return primary_row, power_rows, dense_rows


def run_calibration(
    *,
    residuals: np.ndarray,
    labels: list[dict[str, str]],
    output_dir: Path,
    profile: str,
    candidate_ns: list[int],
    variance_multipliers: list[float],
    iterations: int,
    streams: dict[str, int],
    selection_enabled: bool,
) -> dict[str, Any]:
    _refuse_existing_output(output_dir)
    output_dir.mkdir(parents=True)

    baseline_sd = residuals.std(axis=0, ddof=1)
    if residuals.shape != (5, 28):
        raise ValueError(f"residual matrix shape mismatch: {residuals.shape}")
    if np.any(baseline_sd <= 0.0):
        raise ValueError("all baseline SDs must be positive")

    primary_rows: list[dict[str, Any]] = []
    power_rows: list[dict[str, Any]] = []
    dense_rows: list[dict[str, Any]] = []

    for stream, base_seed in streams.items():
        for n_blocks in candidate_ns:
            for stress in variance_multipliers:
                primary, power, dense = _primary_cell(
                    residuals=residuals,
                    baseline_sd=baseline_sd,
                    labels=labels,
                    n_blocks=n_blocks,
                    stress=stress,
                    stream=stream,
                    base_seed=base_seed,
                    iterations=iterations,
                    profile=profile,
                )
                primary_rows.append(primary)
                power_rows.extend(power)
                dense_rows.extend(dense)

    input_rows = _input_matrix_rows(residuals, labels)
    gate_rows: list[dict[str, Any]] = []
    selected = None

    if selection_enabled:
        # Full hard-gate summarization is intentionally deterministic.
        for n_blocks in candidate_ns:
            n_primary = [
                row for row in primary_rows if row["candidate_n"] == n_blocks
            ]
            baseline_power = [
                row for row in power_rows
                if row["candidate_n"] == n_blocks
                and row["variance_multiplier"] == 1.0
                and row["standardized_effect_d"] == 0.80
            ]
            pass_fwer = all(
                row["strategy_fwer_point"] <= 0.055
                and row["strategy_fwer_wilson95_upper"] <= 0.060
                and row["factorial_fwer_point"] <= 0.055
                and row["factorial_fwer_wilson95_upper"] <= 0.060
                for row in n_primary
            )
            pass_cov = all(
                row["mean_ci_coverage"] >= 0.945
                and row["minimum_ci_coverage"] >= 0.930
                for row in n_primary
            )
            pass_power = bool(baseline_power) and all(
                row["active_rejection_point"] >= 0.800
                and row["active_rejection_wilson95_lower"] >= 0.780
                for row in baseline_power
            )

            # Stream stability summary.
            stream_rows = {}
            for stream in streams:
                stream_primary = [
                    row for row in n_primary if row["stream"] == stream
                ]
                stream_power = [
                    row for row in baseline_power if row["stream"] == stream
                ]
                stream_rows[stream] = {
                    "max_fwer": max(
                        max(row["strategy_fwer_point"], row["factorial_fwer_point"])
                        for row in stream_primary
                    ),
                    "mean_coverage": float(np.mean(
                        [row["mean_ci_coverage"] for row in stream_primary]
                    )),
                    "min_power": min(
                        row["active_rejection_point"] for row in stream_power
                    ),
                }
            if set(stream_rows) == {"A", "B"}:
                stability = (
                    abs(stream_rows["A"]["max_fwer"] - stream_rows["B"]["max_fwer"]) <= 0.015
                    and abs(stream_rows["A"]["mean_coverage"] - stream_rows["B"]["mean_coverage"]) <= 0.015
                    and abs(stream_rows["A"]["min_power"] - stream_rows["B"]["min_power"]) <= 0.020
                )
            else:
                stability = False

            passed = pass_fwer and pass_cov and pass_power and stability
            gate_rows.append(
                {
                    "candidate_n": n_blocks,
                    "pass_null_fwer": pass_fwer,
                    "pass_ci_coverage": pass_cov,
                    "pass_single_signal_d0_80_power": pass_power,
                    "pass_stream_stability": stability,
                    "passes_all_hard_gates": passed,
                }
            )
        passing = [row["candidate_n"] for row in gate_rows if row["passes_all_hard_gates"]]
        selected = min(passing) if passing else None
    else:
        gate_rows = [
            {
                "candidate_n": n,
                "selection_enabled": False,
                "passes_all_hard_gates": False,
            }
            for n in candidate_ns
        ]

    # Smoke profile does not use LOO. Full LOO is added in the full executor.
    loo_rows = [
        {
            "profile": profile,
            "loo_executed": False,
            "reason": "smoke_profile" if profile == "smoke" else "full_executor_pending",
        }
    ]

    _write_csv(output_dir / "oc_input_matrix.csv", input_rows)
    _write_csv(output_dir / "oc_primary_cells.csv", primary_rows)
    _write_csv(output_dir / "oc_single_signal_power.csv", power_rows)
    _write_csv(output_dir / "oc_dense_power.csv", dense_rows)
    _write_csv(output_dir / "oc_loo_sensitivity.csv", loo_rows)
    _write_csv(output_dir / "oc_candidate_gate_summary.csv", gate_rows)

    summary = {
        "stage": "TASK_005 Stage I.5C-3C-1",
        "status": "passed",
        "profile": profile,
        "candidate_n": candidate_ns,
        "variance_multipliers": variance_multipliers,
        "iterations_per_cell_per_stream": iterations,
        "streams": streams,
        "confirmatory_estimands": 28,
        "diagnostic_selected_candidate_n": selected,
        "selection_enabled": selection_enabled,
        "formal_target_n_frozen": False,
        "formal_llm_launch_permitted": False,
        "real_llm_calls_used": False,
        "network_access_used": False,
        "formal_inference_performed": False,
    }
    _write_json(output_dir / "oc_summary.json", summary)

    manifest_rows = []
    for path in sorted(output_dir.iterdir(), key=lambda p: p.name):
        if path.is_file():
            manifest_rows.append(
                {
                    "path": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    _write_json(
        output_dir / "evidence_manifest.json",
        {
            "schema_version": "1.0",
            "file_count": len(manifest_rows),
            "files": manifest_rows,
        },
    )
    return summary


def run_smoke(
    fixture_path: Path,
    runner_contract_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    contract = json.loads(
        runner_contract_path.read_text(encoding="utf-8-sig")
    )
    profile = contract["profiles"]["smoke"]
    residuals, labels = load_synthetic_fixture(fixture_path)
    return run_calibration(
        residuals=residuals,
        labels=labels,
        output_dir=output_dir,
        profile="smoke",
        candidate_ns=[int(x) for x in profile["candidate_n"]],
        variance_multipliers=[
            float(x) for x in profile["variance_multipliers"]
        ],
        iterations=int(profile["iterations_per_cell_per_stream"]),
        streams={
            "A": int(contract["rng_contract"]["primary_stream_base_seeds"]["A"]),
            "B": int(contract["rng_contract"]["primary_stream_base_seeds"]["B"]),
        },
        selection_enabled=False,
    )


def prepare_full(
    design_path: Path,
    i5c0_evidence: Path,
) -> tuple[np.ndarray, list[dict[str, str]]]:
    validate_design_hash(design_path)
    return load_i5c0_matrix(i5c0_evidence)
