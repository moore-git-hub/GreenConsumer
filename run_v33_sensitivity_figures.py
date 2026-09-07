"""Regenerate thesis-safe Stage-A or Morris sensitivity figures without rerunning the model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from greenconsumer_v33.sensitivity_figures import replot_sensitivity_suite


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run_v33_sensitivity_figures.py",
        description=(
            "Replot an existing v3.3.1 Stage-A or Morris sensitivity suite using "
            "thesis-safe labels. This is post-processing only and performs no GABM run."
        ),
    )
    parser.add_argument("suite_dir", type=Path)
    args = parser.parse_args(argv)
    payload = replot_sensitivity_suite(args.suite_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
