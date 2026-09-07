"""Run zero-API demand-only micro-buyer resolution robustness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from greenconsumer_v32.config import PROJECT_ROOT
from greenconsumer_v33.microbuyer_sensitivity import run_sync


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run_v33_microbuyer_sensitivity.py",
        description=(
            "Reuse five frozen N20/K3 cognitive histories and rerun only downstream demand "
            "at M=10/25/50 micro-buyers per cognitive Agent. No LLM/API execution."
        ),
    )
    parser.add_argument(
        "--source-size-dir",
        type=Path,
        required=True,
        help="Completed v33 network-size suite directory containing size_summary.json.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "results" / "v33_microbuyer_sensitivity",
    )
    args = parser.parse_args(argv)
    payload = run_sync(
        source_size_dir=args.source_size_dir,
        output_root=args.output_root,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
