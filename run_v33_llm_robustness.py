"""Plan or execute selected Real-LLM prompt/stochasticity robustness blocks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from greenconsumer_v32.config import PROJECT_ROOT
from greenconsumer_v33.llm_robustness import plan_payload, run_sync


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run_v33_llm_robustness.py",
        description=(
            "Pre-register or explicitly execute five selected Real-LLM engineering blocks: "
            "three prompt-layout profiles and three baseline repeats with one overlapping anchor."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true", help="print the zero-API execution plan")
    mode.add_argument("--execute-real", action="store_true", help="execute the Real-LLM robustness suite")
    parser.add_argument(
        "--allow-real-llm",
        action="store_true",
        help="required together with --execute-real to prevent accidental provider calls",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "results" / "v33_llm_robustness",
    )
    args = parser.parse_args(argv)

    if args.plan_only:
        payload = plan_payload()
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if not args.allow_real_llm:
        parser.error("--execute-real requires explicit --allow-real-llm")
    payload = run_sync(output_root=args.output_root, allow_real_llm=True)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
