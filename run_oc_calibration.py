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
from oc_calibration_runner import prepare_full, run_smoke


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
        description="Offline TASK_005 OC-calibration utility."
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

    smoke = sub.add_parser(
        "calibrate-smoke",
        help="Run the frozen small deterministic OC implementation smoke.",
    )
    smoke.add_argument("--fixture", type=Path, required=True)
    smoke.add_argument("--runner-contract", type=Path, required=True)
    smoke.add_argument("--output-dir", type=Path, required=True)

    full = sub.add_parser(
        "calibrate-full",
        help=(
            "Prepare the frozen full OC calibration. "
            "Execution requires explicit confirmation."
        ),
    )
    full.add_argument("--runner-contract", type=Path, required=True)
    full.add_argument("--design", type=Path, required=True)
    full.add_argument("--i5c0-evidence", type=Path, required=True)
    full.add_argument("--output-dir", type=Path, required=True)
    full.add_argument(
        "--confirm-full-calibration",
        action="store_true",
        help="Explicitly acknowledge the expensive full offline calibration.",
    )

    args = parser.parse_args()

    if args.command == "validate-fixture":
        data = load_fixture(args.fixture.resolve())
        matrix = np.asarray(
            data["centered_residual_matrix"],
            dtype=float,
        )
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
        data = load_fixture(args.fixture.resolve())
        matrix = np.asarray(
            data["centered_residual_matrix"],
            dtype=float,
        )
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
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.command == "calibrate-smoke":
        summary = run_smoke(
            args.fixture.resolve(),
            args.runner_contract.resolve(),
            args.output_dir.resolve(),
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.command == "calibrate-full":
        if not args.confirm_full_calibration:
            parser.error(
                "calibrate-full requires --confirm-full-calibration; "
                "no output has been created"
            )
        # Stage I.5C-3C-1 validates the full frozen inputs but does not
        # execute 20,000-iteration cells. Full execution is a later gate.
        residuals, labels = prepare_full(
            args.design.resolve(),
            args.i5c0_evidence.resolve(),
        )
        payload = {
            "status": "prepared-only",
            "shape": list(residuals.shape),
            "estimands": len(labels),
            "output_dir": str(args.output_dir.resolve()),
            "full_oc_calibration_executed": False,
            "formal_target_n_frozen": False,
            "formal_llm_launch_permitted": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
