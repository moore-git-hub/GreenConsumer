from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from scipy import stats


def _as_finite_1d(values: Iterable[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{name} must be 1-D")
    if array.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _as_finite_2d(values, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2:
        raise ValueError(f"{name} must be 2-D")
    if array.shape[0] < 2:
        raise ValueError(f"{name} must contain at least two rows")
    if array.shape[1] < 1:
        raise ValueError(f"{name} must contain at least one column")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def holm_adjust(p_values: Iterable[float]) -> np.ndarray:
    """
    Return Holm-adjusted p-values in the original input order.

    The adjustment is:
      p_(i)^adj = max_{j <= i} (m-j+1) * p_(j)
    on ascending raw p-values, clipped to [0, 1].
    """
    p = _as_finite_1d(p_values, "p_values")
    if np.any((p < 0.0) | (p > 1.0)):
        raise ValueError("p_values must lie in [0, 1]")

    m = p.size
    order = np.argsort(p, kind="mergesort")
    sorted_p = p[order]
    scaled = (m - np.arange(m)) * sorted_p
    adjusted_sorted = np.minimum(
        1.0,
        np.maximum.accumulate(scaled),
    )

    adjusted = np.empty_like(adjusted_sorted)
    adjusted[order] = adjusted_sorted
    return adjusted


def wilson_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Wilson score interval for a binomial proportion.
    """
    if isinstance(successes, bool) or isinstance(trials, bool):
        raise ValueError("successes and trials must be integers")
    successes = int(successes)
    trials = int(trials)
    if trials <= 0:
        raise ValueError("trials must be positive")
    if successes < 0 or successes > trials:
        raise ValueError("successes must lie in [0, trials]")
    if not (0.0 < float(confidence) < 1.0):
        raise ValueError("confidence must lie in (0, 1)")

    z = float(stats.norm.ppf(0.5 + float(confidence) / 2.0))
    phat = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (phat + z2 / (2.0 * trials)) / denominator
    half = (
        z
        * math.sqrt(
            phat * (1.0 - phat) / trials
            + z2 / (4.0 * trials * trials)
        )
        / denominator
    )
    lower = max(0.0, center - half)
    upper = min(1.0, center + half)
    return float(lower), float(upper)


def center_residual_matrix(values) -> np.ndarray:
    """
    Column-center a block x estimand matrix.
    """
    matrix = _as_finite_2d(values, "values")
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    # A second subtraction removes residual floating-point mean drift.
    centered = centered - centered.mean(axis=0, keepdims=True)
    return centered


def draw_synthetic_blocks(
    centered_residuals,
    n_blocks: int,
    stress_multiplier: float,
    rng_seed: int,
    truth_vector=None,
) -> np.ndarray:
    """
    Draw synthetic whole-block residual vectors with deterministic PCG64 RNG.

    Frozen draw order:
      1. row indices
      2. Rademacher sign bits
      3. same sign applied to every coordinate of one sampled block
    """
    residuals = _as_finite_2d(
        centered_residuals,
        "centered_residuals",
    )

    if isinstance(n_blocks, bool):
        raise ValueError("n_blocks must be an integer")
    n_blocks = int(n_blocks)
    if n_blocks < 2:
        raise ValueError("n_blocks must be at least 2")

    stress_multiplier = float(stress_multiplier)
    if not math.isfinite(stress_multiplier) or stress_multiplier <= 0.0:
        raise ValueError("stress_multiplier must be finite and positive")

    if isinstance(rng_seed, bool):
        raise ValueError("rng_seed must be an integer")
    rng_seed = int(rng_seed)
    if rng_seed < 0:
        raise ValueError("rng_seed must be nonnegative")

    if truth_vector is None:
        truth = np.zeros(residuals.shape[1], dtype=float)
    else:
        truth = _as_finite_1d(truth_vector, "truth_vector")
        if truth.shape[0] != residuals.shape[1]:
            raise ValueError(
                "truth_vector length must equal number of estimands"
            )

    rng = np.random.Generator(np.random.PCG64(rng_seed))
    row_indices = rng.integers(
        0,
        residuals.shape[0],
        size=n_blocks,
    )
    sign_bits = rng.integers(0, 2, size=n_blocks)
    signs = np.where(sign_bits == 0, -1.0, 1.0)

    return (
        truth[None, :]
        + stress_multiplier
        * residuals[row_indices]
        * signs[:, None]
    )


def one_sample_t_pvalues(sample) -> np.ndarray:
    """
    Two-sided one-sample Student-t p-values against 0, by column.

    Zero-variance policy:
      * all values exactly zero -> p = 1
      * constant nonzero values -> p = 0
    """
    matrix = _as_finite_2d(sample, "sample")
    n = matrix.shape[0]
    if n < 2:
        raise ValueError("sample must contain at least two blocks")

    means = matrix.mean(axis=0)
    sds = matrix.std(axis=0, ddof=1)
    result = np.empty(matrix.shape[1], dtype=float)

    zero_variance = sds == 0.0
    all_zero = zero_variance & (means == 0.0)
    nonzero_constant = zero_variance & (means != 0.0)

    result[all_zero] = 1.0
    result[nonzero_constant] = 0.0

    regular = ~zero_variance
    if np.any(regular):
        t_values = means[regular] / (sds[regular] / math.sqrt(n))
        p_values = 2.0 * stats.t.sf(
            np.abs(t_values),
            df=n - 1,
        )
        result[regular] = p_values

    return np.clip(result, 0.0, 1.0)


def student_t_confidence_intervals(
    sample,
    confidence: float = 0.95,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Student-t confidence intervals for column means.
    """
    matrix = _as_finite_2d(sample, "sample")
    if not (0.0 < float(confidence) < 1.0):
        raise ValueError("confidence must lie in (0, 1)")

    n = matrix.shape[0]
    means = matrix.mean(axis=0)
    sds = matrix.std(axis=0, ddof=1)
    critical = float(
        stats.t.ppf(
            0.5 + float(confidence) / 2.0,
            df=n - 1,
        )
    )
    half = critical * sds / math.sqrt(n)
    return means - half, means + half
