"""Build zero-API, descriptive cognition-evolution outputs for one v3.3.1 run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from greenconsumer_v33.cognition_outputs import build_cognition_outputs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run_v33_cognition.py",
        description=(
            "Post-process agent_thoughts.csv and cognitive_records.csv into auditable, "
            "descriptive cognition-evolution tables and figures. No LLM calls are made."
        ),
    )
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    payload = build_cognition_outputs(args.run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
