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
EXPECTED_RUNNER_CONTRACT_SHA256 = (
    "3864F36F46BF1151A8C22F2F7398327B772C24FD5F8B1ADE009B80FF1DAEC3A5"
)
EXPECTED_FULL_EXECUTOR_CONTRACT_SHA256 = (
    "39783E56E989BA4E2864C6C9B80977C4D195DF24AC0B39B11A209316E058EA52"
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

# ============================================================================
# Stage I.5C-3C-2 full executor
# ============================================================================

def _validate_contract_hash(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(f"{label} SHA256 mismatch: {actual}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _pvalues_from_mean_sd(
    means: np.ndarray,
    sds: np.ndarray,
    n_blocks: int,
) -> np.ndarray:
    means = np.asarray(means, dtype=float)
    sds = np.asarray(sds, dtype=float)
    if means.shape != sds.shape:
        raise ValueError("means/sds shape mismatch")
    result = np.empty_like(means, dtype=float)

    zero = sds == 0.0
    result[zero & (means == 0.0)] = 1.0
    result[zero & (means != 0.0)] = 0.0

    regular = ~zero
    if np.any(regular):
        t_values = means[regular] / (sds[regular] / math.sqrt(n_blocks))
        result[regular] = 2.0 * stats.t.sf(
            np.abs(t_values),
            df=n_blocks - 1,
        )
    return np.clip(result, 0.0, 1.0)


def _full_cell_statistics(
    *,
    residuals: np.ndarray,
    baseline_sd: np.ndarray,
    labels: list[dict[str, str]],
    n_blocks: int,
    stress: float,
    stream: str,
    base_seed: int,
    iterations: int,
    profile: str,
    chunk_size: int = 500,
) -> dict[str, Any]:
    """
    Memory-bounded implementation of one primary OC cell.

    The complete RNG index array is drawn first, then the complete sign-bit array,
    exactly preserving the frozen draw order. Chunks only process those frozen
    arrays and do not consume additional RNG state.
    """
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    namespace = f"{profile}|{stream}|{n_blocks}|{stress:.1f}|primary"
    seed = derive_cell_seed(base_seed, namespace)
    rng = np.random.Generator(np.random.PCG64(seed))

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

    fwer_successes = {
        "strategy_primary_16": 0,
        "factorial_confirmatory_12": 0,
    }
    coverage_successes = np.zeros(28, dtype=np.int64)
    active_successes = {
        0.50: np.zeros(28, dtype=np.int64),
        0.80: np.zeros(28, dtype=np.int64),
    }
    inactive_false_successes = {
        0.50: np.zeros(28, dtype=np.int64),
        0.80: np.zeros(28, dtype=np.int64),
    }
    dense_successes = np.zeros(28, dtype=np.int64)

    critical = float(stats.t.ppf(0.975, n_blocks - 1))

    for start in range(0, iterations, chunk_size):
        stop = min(iterations, start + chunk_size)
        idx = row_indices[start:stop]
        bits = sign_bits[start:stop]
        signs = np.where(bits == 0, -1.0, 1.0)

        noise = stress * residuals[idx] * signs[:, :, None]
        means = noise.mean(axis=1)
        sds = noise.std(axis=1, ddof=1)
        null_p = _pvalues_from_mean_sd(means, sds, n_blocks)

        for family_name, indices in FAMILY_INDICES.items():
            family_rej = _holm_rejection_matrix(null_p, indices)
            fwer_successes[family_name] += int(family_rej.any(axis=1).sum())

        half = critical * sds / math.sqrt(n_blocks)
        coverage_successes += (
            ((means - half) <= 0.0) & (0.0 <= (means + half))
        ).sum(axis=0).astype(np.int64)

        # Exactly one active signal. Inactive raw p-values are the null p-values;
        # the constant signal changes only the active coordinate's mean.
        for d in (0.50, 0.80):
            for active in range(28):
                family_name = labels[active]["family"]
                indices = FAMILY_INDICES[family_name]
                local_position = int(np.where(indices == active)[0][0])

                family_p = null_p[:, indices].copy()
                shifted_mean = means[:, active] + d * baseline_sd[active]
                shifted_p = _pvalues_from_mean_sd(
                    shifted_mean,
                    sds[:, active],
                    n_blocks,
                )
                family_p[:, local_position] = shifted_p

                family_rej = _holm_rejection_matrix(
                    family_p,
                    np.arange(indices.size, dtype=int),
                )
                active_successes[d][active] += int(
                    family_rej[:, local_position].sum()
                )

                inactive_mask = np.ones(indices.size, dtype=bool)
                inactive_mask[local_position] = False
                inactive_false_successes[d][active] += int(
                    family_rej[:, inactive_mask].any(axis=1).sum()
                )

        # Dense d=0.50: all means shift, SDs stay unchanged.
        dense_means = means + 0.50 * baseline_sd[None, :]
        dense_p = _pvalues_from_mean_sd(dense_means, sds, n_blocks)
        for family_name, indices in FAMILY_INDICES.items():
            dense_rej = _holm_rejection_matrix(dense_p, indices)
            dense_successes[indices] += dense_rej.sum(axis=0).astype(np.int64)

    return {
        "profile": profile,
        "stream": stream,
        "candidate_n": int(n_blocks),
        "variance_multiplier": float(stress),
        "iterations": int(iterations),
        "cell_seed": int(seed),
        "fwer_successes": fwer_successes,
        "coverage_successes": coverage_successes,
        "active_successes": active_successes,
        "inactive_false_successes": inactive_false_successes,
        "dense_successes": dense_successes,
    }


def _full_cell_rows(
    cell: dict[str, Any],
    labels: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    iterations = int(cell["iterations"])

    fwer_stats = {
        name: _estimate_with_wilson(int(successes), iterations)
        for name, successes in cell["fwer_successes"].items()
    }

    primary_rows: list[dict[str, Any]] = []
    coverage_points: list[float] = []
    for j, label in enumerate(labels):
        coverage = _estimate_with_wilson(
            int(cell["coverage_successes"][j]),
            iterations,
        )
        coverage_points.append(float(coverage["point"]))
        primary_rows.append(
            {
                "profile": cell["profile"],
                "stream": cell["stream"],
                "candidate_n": cell["candidate_n"],
                "variance_multiplier": cell["variance_multiplier"],
                "iterations": iterations,
                "cell_seed": cell["cell_seed"],
                "estimand_index": j,
                "estimand_id": label["estimand_id"],
                "family": label["family"],
                "coverage_successes": coverage["successes"],
                "coverage_trials": coverage["trials"],
                "coverage_point": coverage["point"],
                "coverage_wilson95_lower": coverage["wilson95_lower"],
                "coverage_wilson95_upper": coverage["wilson95_upper"],
                "strategy_fwer_successes": fwer_stats["strategy_primary_16"]["successes"],
                "strategy_fwer_point": fwer_stats["strategy_primary_16"]["point"],
                "strategy_fwer_wilson95_upper": fwer_stats["strategy_primary_16"]["wilson95_upper"],
                "factorial_fwer_successes": fwer_stats["factorial_confirmatory_12"]["successes"],
                "factorial_fwer_point": fwer_stats["factorial_confirmatory_12"]["point"],
                "factorial_fwer_wilson95_upper": fwer_stats["factorial_confirmatory_12"]["wilson95_upper"],
                "cell_mean_ci_coverage": float(np.mean(coverage_points))
                if len(coverage_points) == 28 else "",
                "cell_minimum_ci_coverage": float(np.min(coverage_points))
                if len(coverage_points) == 28 else "",
            }
        )

    # Fill cell-level coverage summaries on every row after all 28 are known.
    mean_cov = float(np.mean(coverage_points))
    min_cov = float(np.min(coverage_points))
    for row in primary_rows:
        row["cell_mean_ci_coverage"] = mean_cov
        row["cell_minimum_ci_coverage"] = min_cov

    power_rows: list[dict[str, Any]] = []
    for d in (0.50, 0.80):
        for j, label in enumerate(labels):
            active = _estimate_with_wilson(
                int(cell["active_successes"][d][j]),
                iterations,
            )
            inactive = _estimate_with_wilson(
                int(cell["inactive_false_successes"][d][j]),
                iterations,
            )
            power_rows.append(
                {
                    "profile": cell["profile"],
                    "stream": cell["stream"],
                    "candidate_n": cell["candidate_n"],
                    "variance_multiplier": cell["variance_multiplier"],
                    "iterations": iterations,
                    "standardized_effect_d": d,
                    "active_estimand_index": j,
                    "active_estimand_id": label["estimand_id"],
                    "family": label["family"],
                    "active_rejection_successes": active["successes"],
                    "active_rejection_trials": active["trials"],
                    "active_rejection_point": active["point"],
                    "active_rejection_wilson95_lower": active["wilson95_lower"],
                    "active_rejection_wilson95_upper": active["wilson95_upper"],
                    "inactive_family_false_rejection_successes": inactive["successes"],
                    "inactive_family_false_rejection_point": inactive["point"],
                }
            )

    dense_points = cell["dense_successes"] / iterations
    dense_rows: list[dict[str, Any]] = []
    for family_name, indices in FAMILY_INDICES.items():
        family_points = dense_points[indices]
        family_mean = float(np.mean(family_points))
        family_min = float(np.min(family_points))
        for j in indices:
            stat = _estimate_with_wilson(
                int(cell["dense_successes"][j]),
                iterations,
            )
            dense_rows.append(
                {
                    "profile": cell["profile"],
                    "stream": cell["stream"],
                    "candidate_n": cell["candidate_n"],
                    "variance_multiplier": cell["variance_multiplier"],
                    "iterations": iterations,
                    "standardized_effect_d": 0.50,
                    "estimand_index": int(j),
                    "estimand_id": labels[int(j)]["estimand_id"],
                    "family": family_name,
                    "rejection_successes": stat["successes"],
                    "rejection_trials": stat["trials"],
                    "rejection_point": stat["point"],
                    "rejection_wilson95_lower": stat["wilson95_lower"],
                    "rejection_wilson95_upper": stat["wilson95_upper"],
                    "family_mean_discovery_probability": family_mean,
                    "family_minimum_discovery_probability": family_min,
                }
            )

    return primary_rows, power_rows, dense_rows


def _cell_summary_for_gates(cell: dict[str, Any]) -> dict[str, Any]:
    iterations = int(cell["iterations"])
    fwer = {
        family: _estimate_with_wilson(int(successes), iterations)
        for family, successes in cell["fwer_successes"].items()
    }
    coverage_points = cell["coverage_successes"] / iterations
    power_points = cell["active_successes"][0.80] / iterations
    power_wilson_lower = np.asarray(
        [
            wilson_interval(
                int(cell["active_successes"][0.80][j]),
                iterations,
                0.95,
            )[0]
            for j in range(28)
        ],
        dtype=float,
    )
    return {
        "stream": cell["stream"],
        "candidate_n": cell["candidate_n"],
        "variance_multiplier": cell["variance_multiplier"],
        "iterations": iterations,
        "fwer": fwer,
        "coverage_successes": cell["coverage_successes"],
        "mean_coverage": float(coverage_points.mean()),
        "min_coverage": float(coverage_points.min()),
        "d080_successes": cell["active_successes"][0.80],
        "min_d080_power": float(power_points.min()),
        "min_d080_wilson_lower": float(power_wilson_lower.min()),
    }


def _candidate_gate_rows(
    cells: list[dict[str, Any]],
    candidate_ns: list[int],
    selection_enabled: bool,
) -> tuple[list[dict[str, Any]], int | None]:
    summaries = [_cell_summary_for_gates(cell) for cell in cells]
    rows: list[dict[str, Any]] = []

    for n_blocks in candidate_ns:
        by_stream = {
            stream: [
                row
                for row in summaries
                if row["candidate_n"] == n_blocks
                and row["stream"] == stream
            ]
            for stream in ("A", "B")
        }

        stream_pass: dict[str, bool] = {}
        for stream, stream_rows in by_stream.items():
            if len(stream_rows) != 3:
                stream_pass[stream] = False
                continue

            pass_fwer = all(
                stat["point"] <= 0.055
                and stat["wilson95_upper"] <= 0.060
                for row in stream_rows
                for stat in row["fwer"].values()
            )
            pass_coverage = all(
                row["mean_coverage"] >= 0.945
                and row["min_coverage"] >= 0.930
                for row in stream_rows
            )
            baseline = [
                row for row in stream_rows
                if row["variance_multiplier"] == 1.0
            ]
            pass_power = (
                len(baseline) == 1
                and baseline[0]["min_d080_power"] >= 0.800
                and baseline[0]["min_d080_wilson_lower"] >= 0.780
            )
            stream_pass[stream] = pass_fwer and pass_coverage and pass_power

        # Combined stream pooled counts for matching stress.
        combined_pass_fwer = True
        combined_pass_coverage = True
        for stress in (1.0, 1.5, 2.0):
            pair = [
                row for row in summaries
                if row["candidate_n"] == n_blocks
                and row["variance_multiplier"] == stress
            ]
            if len(pair) != 2:
                combined_pass_fwer = False
                combined_pass_coverage = False
                continue

            total_trials = sum(int(row["iterations"]) for row in pair)
            for family in FAMILY_INDICES:
                successes = sum(
                    int(row["fwer"][family]["successes"])
                    for row in pair
                )
                pooled = _estimate_with_wilson(successes, total_trials)
                combined_pass_fwer &= (
                    pooled["point"] <= 0.055
                    and pooled["wilson95_upper"] <= 0.060
                )

            pooled_cov = (
                np.asarray(pair[0]["coverage_successes"], dtype=np.int64)
                + np.asarray(pair[1]["coverage_successes"], dtype=np.int64)
            ) / total_trials
            combined_pass_coverage &= (
                float(pooled_cov.mean()) >= 0.945
                and float(pooled_cov.min()) >= 0.930
            )

        baseline_pair = [
            row for row in summaries
            if row["candidate_n"] == n_blocks
            and row["variance_multiplier"] == 1.0
        ]
        combined_pass_power = False
        if len(baseline_pair) == 2:
            total_trials = sum(int(row["iterations"]) for row in baseline_pair)
            successes = (
                np.asarray(baseline_pair[0]["d080_successes"], dtype=np.int64)
                + np.asarray(baseline_pair[1]["d080_successes"], dtype=np.int64)
            )
            pooled_points = successes / total_trials
            pooled_lowers = np.asarray(
                [
                    wilson_interval(int(s), total_trials, 0.95)[0]
                    for s in successes
                ]
            )
            combined_pass_power = (
                float(pooled_points.min()) >= 0.800
                and float(pooled_lowers.min()) >= 0.780
            )

        # Frozen matched stream-stability checks.
        max_fwer_diff = 0.0
        max_mean_cov_diff = 0.0
        stability_complete = True
        for stress in (1.0, 1.5, 2.0):
            a = [
                row for row in by_stream["A"]
                if row["variance_multiplier"] == stress
            ]
            b = [
                row for row in by_stream["B"]
                if row["variance_multiplier"] == stress
            ]
            if len(a) != 1 or len(b) != 1:
                stability_complete = False
                continue
            a = a[0]
            b = b[0]
            for family in FAMILY_INDICES:
                max_fwer_diff = max(
                    max_fwer_diff,
                    abs(
                        float(a["fwer"][family]["point"])
                        - float(b["fwer"][family]["point"])
                    ),
                )
            max_mean_cov_diff = max(
                max_mean_cov_diff,
                abs(float(a["mean_coverage"]) - float(b["mean_coverage"])),
            )

        min_power_a = [
            row["min_d080_power"]
            for row in by_stream["A"]
            if row["variance_multiplier"] == 1.0
        ]
        min_power_b = [
            row["min_d080_power"]
            for row in by_stream["B"]
            if row["variance_multiplier"] == 1.0
        ]
        if len(min_power_a) != 1 or len(min_power_b) != 1:
            stability_complete = False
            min_power_diff = float("inf")
        else:
            min_power_diff = abs(float(min_power_a[0]) - float(min_power_b[0]))

        pass_stability = (
            stability_complete
            and max_fwer_diff <= 0.015
            and max_mean_cov_diff <= 0.015
            and min_power_diff <= 0.020
        )

        combined_pass = (
            combined_pass_fwer
            and combined_pass_coverage
            and combined_pass_power
        )
        passes_all = (
            bool(stream_pass.get("A"))
            and bool(stream_pass.get("B"))
            and combined_pass
            and pass_stability
        )

        rows.append(
            {
                "candidate_n": n_blocks,
                "stream_A_pass": bool(stream_pass.get("A")),
                "stream_B_pass": bool(stream_pass.get("B")),
                "combined_fwer_pass": bool(combined_pass_fwer),
                "combined_coverage_pass": bool(combined_pass_coverage),
                "combined_d080_power_pass": bool(combined_pass_power),
                "stream_stability_pass": bool(pass_stability),
                "max_stream_fwer_difference": max_fwer_diff,
                "max_stream_mean_coverage_difference": max_mean_cov_diff,
                "minimum_d080_power_stream_difference": min_power_diff,
                "passes_all_hard_gates": bool(passes_all),
                "selection_enabled": bool(selection_enabled),
                "eligible_for_selection": bool(selection_enabled and passes_all),
                "dry_run_nonbinding": not bool(selection_enabled),
            }
        )

    selected = None
    if selection_enabled:
        passing = [
            int(row["candidate_n"])
            for row in rows
            if row["eligible_for_selection"]
        ]
        if passing:
            selected = min(passing)

    return rows, selected


def _loo_rows(
    *,
    residuals: np.ndarray,
    baseline_sd_full5: np.ndarray,
    labels: list[dict[str, str]],
    candidate_ns: list[int],
    iterations: int,
    chunk_size: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for omit_index, omit_block in enumerate(CANONICAL_BLOCKS):
        keep = [i for i in range(5) if i != omit_index]
        library = residuals[keep].copy()
        library -= library.mean(axis=0, keepdims=True)
        library -= library.mean(axis=0, keepdims=True)

        if library.shape != (4, 28):
            raise AssertionError("LOO library shape mismatch")
        if np.any(library.std(axis=0, ddof=1) <= 0.0):
            raise ValueError(
                f"LOO library contains zero-SD estimand after omitting {omit_block}"
            )

        for n_blocks in candidate_ns:
            namespace = f"full|LOO|{omit_block}|{n_blocks}|1.0|primary"
            seed = derive_cell_seed(202608170, namespace)
            rng = np.random.Generator(np.random.PCG64(seed))
            row_indices = rng.integers(
                0,
                library.shape[0],
                size=(iterations, n_blocks),
            )
            sign_bits = rng.integers(
                0,
                2,
                size=(iterations, n_blocks),
            )

            fwer_successes = {
                "strategy_primary_16": 0,
                "factorial_confirmatory_12": 0,
            }
            coverage_successes = np.zeros(28, dtype=np.int64)
            power_successes = np.zeros(28, dtype=np.int64)
            critical = float(stats.t.ppf(0.975, n_blocks - 1))

            for start in range(0, iterations, chunk_size):
                stop = min(iterations, start + chunk_size)
                idx = row_indices[start:stop]
                bits = sign_bits[start:stop]
                signs = np.where(bits == 0, -1.0, 1.0)
                noise = library[idx] * signs[:, :, None]
                means = noise.mean(axis=1)
                sds = noise.std(axis=1, ddof=1)
                null_p = _pvalues_from_mean_sd(means, sds, n_blocks)

                for family_name, indices in FAMILY_INDICES.items():
                    family_rej = _holm_rejection_matrix(null_p, indices)
                    fwer_successes[family_name] += int(
                        family_rej.any(axis=1).sum()
                    )

                half = critical * sds / math.sqrt(n_blocks)
                coverage_successes += (
                    ((means - half) <= 0.0)
                    & (0.0 <= (means + half))
                ).sum(axis=0).astype(np.int64)

                # d=0.80 uses full-five-block SD anchor by frozen contract.
                for active in range(28):
                    family_name = labels[active]["family"]
                    indices = FAMILY_INDICES[family_name]
                    local_position = int(np.where(indices == active)[0][0])
                    family_p = null_p[:, indices].copy()
                    shifted_p = _pvalues_from_mean_sd(
                        means[:, active] + 0.80 * baseline_sd_full5[active],
                        sds[:, active],
                        n_blocks,
                    )
                    family_p[:, local_position] = shifted_p
                    family_rej = _holm_rejection_matrix(
                        family_p,
                        np.arange(indices.size, dtype=int),
                    )
                    power_successes[active] += int(
                        family_rej[:, local_position].sum()
                    )

            strategy_fwer = _estimate_with_wilson(
                fwer_successes["strategy_primary_16"],
                iterations,
            )
            factorial_fwer = _estimate_with_wilson(
                fwer_successes["factorial_confirmatory_12"],
                iterations,
            )
            coverage_points = coverage_successes / iterations
            power_points = power_successes / iterations

            rows.append(
                {
                    "omitted_block": omit_block,
                    "candidate_n": n_blocks,
                    "variance_multiplier": 1.0,
                    "iterations": iterations,
                    "cell_seed": seed,
                    "strategy_fwer_point": strategy_fwer["point"],
                    "strategy_fwer_wilson95_upper": strategy_fwer["wilson95_upper"],
                    "factorial_fwer_point": factorial_fwer["point"],
                    "factorial_fwer_wilson95_upper": factorial_fwer["wilson95_upper"],
                    "mean_ci_coverage": float(coverage_points.mean()),
                    "minimum_ci_coverage": float(coverage_points.min()),
                    "minimum_single_signal_d080_power": float(power_points.min()),
                    "effect_anchor": "full_five_block_sample_sd",
                    "hard_gate": False,
                }
            )
    return rows


def _deterministic_evidence_zip(
    output_dir: Path,
    zip_path: Path,
    payload_names: list[str],
) -> None:
    if zip_path.exists():
        raise FileExistsError(f"refuse overwrite existing evidence ZIP: {zip_path}")

    with zipfile.ZipFile(
        zip_path,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for name in sorted(payload_names):
            path = output_dir / name
            if not path.is_file():
                raise FileNotFoundError(path)
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def _write_full_outputs(
    *,
    output_dir: Path,
    zip_path: Path,
    residuals: np.ndarray,
    labels: list[dict[str, str]],
    cells: list[dict[str, Any]],
    loo_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    selected: int | None,
    profile: str,
    primary_iterations: int,
    loo_iterations: int,
    selection_enabled: bool,
) -> dict[str, Any]:
    primary_rows: list[dict[str, Any]] = []
    power_rows: list[dict[str, Any]] = []
    dense_rows: list[dict[str, Any]] = []
    for cell in cells:
        primary, power, dense = _full_cell_rows(cell, labels)
        primary_rows.extend(primary)
        power_rows.extend(power)
        dense_rows.extend(dense)

    _write_csv(output_dir / "oc_input_matrix.csv", _input_matrix_rows(residuals, labels))
    _write_csv(output_dir / "oc_primary_cells.csv", primary_rows)
    _write_csv(output_dir / "oc_single_signal_power.csv", power_rows)
    _write_csv(output_dir / "oc_dense_power.csv", dense_rows)
    _write_csv(output_dir / "oc_loo_sensitivity.csv", loo_rows)
    _write_csv(output_dir / "oc_candidate_gate_summary.csv", gate_rows)

    summary = {
        "stage": "TASK_005 Stage I.5C-3C-2",
        "status": "passed",
        "profile": profile,
        "primary_iterations_per_cell_per_stream": primary_iterations,
        "loo_iterations_per_cell": loo_iterations,
        "candidate_n": [12, 16, 20, 24, 30, 40],
        "variance_multipliers": [1.0, 1.5, 2.0],
        "streams": {"A": 202608071, "B": 202608072},
        "confirmatory_estimands": 28,
        "diagnostic_selected_candidate_n": selected,
        "selection_enabled": selection_enabled,
        "dry_run_nonbinding": not selection_enabled,
        "n40_feasibility_decision_required": bool(selected == 40),
        "formal_target_n_frozen": False,
        "formal_llm_launch_permitted": False,
        "real_llm_calls_used": False,
        "network_access_used": False,
        "formal_inference_performed": False,
        "full_frozen_20000_5000_profile_executed": bool(
            selection_enabled
            and primary_iterations == 20000
            and loo_iterations == 5000
        ),
    }
    _write_json(output_dir / "oc_summary.json", summary)

    payload_without_manifest = [
        "oc_input_matrix.csv",
        "oc_primary_cells.csv",
        "oc_single_signal_power.csv",
        "oc_dense_power.csv",
        "oc_loo_sensitivity.csv",
        "oc_candidate_gate_summary.csv",
        "oc_summary.json",
    ]
    manifest_rows = [
        {
            "path": name,
            "size_bytes": (output_dir / name).stat().st_size,
            "sha256": sha256_file(output_dir / name),
        }
        for name in sorted(payload_without_manifest)
    ]
    _write_json(
        output_dir / "evidence_manifest.json",
        {
            "schema_version": "1.0",
            "payload_file_count_excluding_manifest": 7,
            "manifest_self_excluded": True,
            "zip_self_excluded": True,
            "files": manifest_rows,
        },
    )

    all_payloads = payload_without_manifest + ["evidence_manifest.json"]
    _deterministic_evidence_zip(output_dir, zip_path, all_payloads)
    return summary


def _run_full_executor(
    *,
    residuals: np.ndarray,
    labels: list[dict[str, str]],
    output_dir: Path,
    profile: str,
    primary_iterations: int,
    loo_iterations: int,
    selection_enabled: bool,
    chunk_size: int,
) -> dict[str, Any]:
    zip_path = output_dir.parent / f"{output_dir.name}_evidence.zip"
    if output_dir.exists():
        raise FileExistsError(f"refuse overwrite existing output directory: {output_dir}")
    if zip_path.exists():
        raise FileExistsError(f"refuse overwrite existing evidence ZIP: {zip_path}")
    output_dir.mkdir(parents=True)

    candidate_ns = [12, 16, 20, 24, 30, 40]
    stresses = [1.0, 1.5, 2.0]
    streams = {"A": 202608071, "B": 202608072}
    baseline_sd = residuals.std(axis=0, ddof=1)

    cells: list[dict[str, Any]] = []
    for stream, base_seed in streams.items():
        for n_blocks in candidate_ns:
            for stress in stresses:
                cells.append(
                    _full_cell_statistics(
                        residuals=residuals,
                        baseline_sd=baseline_sd,
                        labels=labels,
                        n_blocks=n_blocks,
                        stress=stress,
                        stream=stream,
                        base_seed=base_seed,
                        iterations=primary_iterations,
                        profile=profile,
                        chunk_size=chunk_size,
                    )
                )

    gate_rows, selected = _candidate_gate_rows(
        cells,
        candidate_ns,
        selection_enabled,
    )
    if not selection_enabled:
        selected = None

    loo = _loo_rows(
        residuals=residuals,
        baseline_sd_full5=baseline_sd,
        labels=labels,
        candidate_ns=candidate_ns,
        iterations=loo_iterations,
        chunk_size=chunk_size,
    )

    return _write_full_outputs(
        output_dir=output_dir,
        zip_path=zip_path,
        residuals=residuals,
        labels=labels,
        cells=cells,
        loo_rows=loo,
        gate_rows=gate_rows,
        selected=selected,
        profile=profile,
        primary_iterations=primary_iterations,
        loo_iterations=loo_iterations,
        selection_enabled=selection_enabled,
    )


def run_full_dry_run(
    *,
    design_path: Path,
    i5c0_evidence: Path,
    runner_contract_path: Path,
    full_executor_contract_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    _validate_contract_hash(
        runner_contract_path,
        EXPECTED_RUNNER_CONTRACT_SHA256,
        "runner contract",
    )
    contract = _validate_contract_hash(
        full_executor_contract_path,
        EXPECTED_FULL_EXECUTOR_CONTRACT_SHA256,
        "full executor contract",
    )
    residuals, labels = prepare_full(design_path, i5c0_evidence)
    profile = contract["dry_run_profile"]

    summary = _run_full_executor(
        residuals=residuals,
        labels=labels,
        output_dir=output_dir,
        profile="full-dry-run",
        primary_iterations=int(
            profile["primary_iterations_per_cell_per_stream"]
        ),
        loo_iterations=int(profile["loo_iterations_per_cell"]),
        selection_enabled=False,
        chunk_size=100,
    )
    if summary["diagnostic_selected_candidate_n"] is not None:
        raise AssertionError("dry-run must not select a candidate N")
    if summary["full_frozen_20000_5000_profile_executed"]:
        raise AssertionError("dry-run executed frozen full profile")
    return summary


def run_full_frozen(
    *,
    design_path: Path,
    i5c0_evidence: Path,
    runner_contract_path: Path,
    full_executor_contract_path: Path,
    output_dir: Path,
    execution_authorized: bool = False,
) -> dict[str, Any]:
    """
    Full frozen 20,000/5,000 executor.

    Stage I.5C-3C-2 deliberately leaves this unreachable from the CLI.
    A later explicit execution gate must set execution_authorized=True.
    """
    if not execution_authorized:
        raise PermissionError(
            "full frozen OC execution is not authorized in Stage I.5C-3C-2"
        )

    _validate_contract_hash(
        runner_contract_path,
        EXPECTED_RUNNER_CONTRACT_SHA256,
        "runner contract",
    )
    contract = _validate_contract_hash(
        full_executor_contract_path,
        EXPECTED_FULL_EXECUTOR_CONTRACT_SHA256,
        "full executor contract",
    )
    residuals, labels = prepare_full(design_path, i5c0_evidence)
    profile = contract["frozen_full_profile"]

    return _run_full_executor(
        residuals=residuals,
        labels=labels,
        output_dir=output_dir,
        profile="full",
        primary_iterations=int(
            profile["primary_iterations_per_cell_per_stream"]
        ),
        loo_iterations=int(profile["loo_iterations_per_cell"]),
        selection_enabled=True,
        chunk_size=500,
    )
