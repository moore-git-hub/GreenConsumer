from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from oc_calibration import (
    center_residual_matrix,
    draw_synthetic_blocks,
    holm_adjust,
    one_sample_t_pvalues,
    student_t_confidence_intervals,
    wilson_interval,
)


def load_fixture(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    matrix = np.asarray(
        data["centered_residual_matrix"],
        dtype=float,
    )
    if matrix.shape != (5, 28):
        raise ValueError(
            f"expected frozen fixture shape (5, 28), got {matrix.shape}"
        )
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Offline TASK_005 OC-calibration utility. "
            "Stage I.5C-3B does not execute the full frozen calibration."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser(
        "validate-fixture",
        help="Validate the synthetic fixture and deterministic draw path.",
    )
    validate.add_argument("--fixture", type=Path, required=True)

    draw = sub.add_parser(
        "draw-smoke",
        help="Produce one deterministic synthetic draw summary.",
    )
    draw.add_argument("--fixture", type=Path, required=True)
    draw.add_argument("--n-blocks", type=int, default=12)
    draw.add_argument("--stress", type=float, default=1.0)
    draw.add_argument("--seed", type=int, default=202608071)

    args = parser.parse_args()

    data = load_fixture(args.fixture.resolve())
    matrix = np.asarray(
        data["centered_residual_matrix"],
        dtype=float,
    )

    if args.command == "validate-fixture":
        centered = center_residual_matrix(matrix)
        if not np.allclose(centered, matrix, atol=1e-12, rtol=0):
            raise AssertionError("fixture matrix is not centered")

        print("Fixture validation: PASS")
        print("Shape: 5 x 28")
        print("Network access: not used")
        print("Real LLM calls: not used")
        print("Full OC calibration executed: False")
        return 0

    if args.command == "draw-smoke":
        sample = draw_synthetic_blocks(
            matrix,
            args.n_blocks,
            args.stress,
            args.seed,
        )
        raw_p = one_sample_t_pvalues(sample)
        adjusted_strategy = holm_adjust(raw_p[:16])
        adjusted_factorial = holm_adjust(raw_p[16:])
        lower, upper = student_t_confidence_intervals(
            sample,
            0.95,
        )
        lo50, hi50 = wilson_interval(50, 100, 0.95)

        payload = {
            "status": "passed",
            "sample_shape": list(sample.shape),
            "seed": args.seed,
            "stress": args.stress,
            "strategy_min_holm_p": float(
                adjusted_strategy.min()
            ),
            "factorial_min_holm_p": float(
                adjusted_factorial.min()
            ),
            "ci_all_finite": bool(
                np.isfinite(lower).all()
                and np.isfinite(upper).all()
            ),
            "wilson_50_of_100": [lo50, hi50],
            "network_access_used": False,
            "real_llm_calls_used": False,
            "full_oc_calibration_executed": False,
        }
        print(json.dumps(payload, indent=2))
        return 0

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
