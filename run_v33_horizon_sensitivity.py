"""Run the zero-API 30/35/40 finite-horizon robustness suite."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from greenconsumer_v33.horizon_sensitivity import run_sync
from greenconsumer_v32.config import PROJECT_ROOT


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run_v33_horizon_sensitivity.py",
        description=(
            "Run pre-specified Fake-LLM T30/T35/T40 horizon checks with identical seeds. "
            "This is engineering robustness only, not formal inference."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "results" / "v33_horizon_sensitivity",
    )
    args = parser.parse_args(argv)
    payload = run_sync(output_root=args.output_root)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
