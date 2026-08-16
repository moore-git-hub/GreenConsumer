"""Plan, analyze, or explicitly execute the v3.3.1 Pilot variance suite."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from greenconsumer_v32.config import PROJECT_ROOT
from greenconsumer_v33.pilot_variance import (
    DEFAULT_OC_REPLICATIONS,
    analyze_existing_suite,
    plan_payload,
    run_sync,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run_v33_pilot_variance.py",
        description=(
            "Zero-API Pilot planning/analysis, or explicitly gated execution of "
            "the six pre-registered Real-LLM Pilot blocks."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--analyze-existing", type=Path, metavar="SUITE_DIR")
    mode.add_argument("--execute-real-pilot", action="store_true")
    parser.add_argument("--allow-real-llm", action="store_true")
    parser.add_argument("--n-max", type=int)
    parser.add_argument("--provider-call-ceiling", type=int)
    parser.add_argument("--max-wall-clock-hours", type=float)
    parser.add_argument("--expected-git-head")
    parser.add_argument(
        "--oc-replications",
        type=int,
        default=DEFAULT_OC_REPLICATIONS,
        help="analysis-only override; protocol execution remains fixed at 200,000/scenario",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "results" / "v33_pilot_variance",
    )
    args = parser.parse_args(argv)

    if args.plan_only:
        supplied = (
            args.n_max is not None,
            args.provider_call_ceiling is not None,
            args.max_wall_clock_hours is not None,
        )
        if any(supplied) and not all(supplied):
            parser.error(
                "plan-only accepts --n-max, --provider-call-ceiling, and "
                "--max-wall-clock-hours only together"
            )
        payload = plan_payload(
            n_max=args.n_max,
            provider_call_ceiling=args.provider_call_ceiling,
            max_wall_clock_hours=args.max_wall_clock_hours,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.analyze_existing is not None:
        if args.n_max is None:
            parser.error("--analyze-existing requires --n-max")
        payload = analyze_existing_suite(
            args.analyze_existing,
            n_max=args.n_max,
            replications=args.oc_replications,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload["status"] == "PASS" else 2

    required = {
        "--allow-real-llm": args.allow_real_llm,
        "--n-max": args.n_max is not None,
        "--provider-call-ceiling": args.provider_call_ceiling is not None,
        "--max-wall-clock-hours": args.max_wall_clock_hours is not None,
        "--expected-git-head": bool(args.expected_git_head),
    }
    missing = [name for name, present in required.items() if not present]
    if missing:
        parser.error("--execute-real-pilot additionally requires " + ", ".join(missing))
    if args.oc_replications != DEFAULT_OC_REPLICATIONS:
        parser.error("Pilot execution fixes --oc-replications at 200000")

    payload = run_sync(
        output_root=args.output_root,
        allow_real_llm=True,
        n_max=args.n_max,
        provider_call_ceiling=args.provider_call_ceiling,
        max_wall_clock_hours=args.max_wall_clock_hours,
        expected_git_head=args.expected_git_head,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
