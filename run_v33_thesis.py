"""Post-process one TASK_005 v3.3.1 run into thesis-ready evidence outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from greenconsumer_v33.thesis_outputs import build_thesis_outputs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run_v33_thesis.py",
        description=(
            "Build descriptive thesis tables, internal-validity evidence, figures, "
            "and an optional fixed-topology network-state GIF."
        ),
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--animate-condition",
        default=None,
        help=(
            "Optional condition, e.g. Rational-Hub-Immediate. Requires "
            "network_nodes.csv/network_edges.csv from the v3.3.1 runner."
        ),
    )
    parser.add_argument("--fps", type=int, default=3)
    args = parser.parse_args(argv)

    payload = build_thesis_outputs(
        args.run_dir.resolve(),
        animate_condition=args.animate_condition,
        animation_fps=args.fps,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
