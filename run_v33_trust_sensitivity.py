"""Run the zero-real-API Stage-A Trust parameter sensitivity suite."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from greenconsumer_v32.config import PROJECT_ROOT
from greenconsumer_v33.trust_sensitivity import run_sync


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run_v33_trust_sensitivity.py",
        description=(
            "Run pre-specified Fake-LLM local/boundary Trust parameter sensitivity at T35. "
            "This is engineering robustness, not calibration or formal inference."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "results" / "v33_trust_sensitivity",
    )
    args = parser.parse_args(argv)
    payload = run_sync(output_root=args.output_root)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
