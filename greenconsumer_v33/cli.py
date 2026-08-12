"""Command-line interface for the parallel TASK_005 FMCG v3.3 workflow."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from greenconsumer_v32.config import (
    DEFAULT_DEMAND_SEED,
    DEFAULT_LLM_SEED,
    DEFAULT_SIMULATION_SEED,
    PROJECT_ROOT,
    RunSettings,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python run_v33.py",
        description="TASK_005 FMCG v3.3 parallel engineering workflow",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_pre = sub.add_parser("preflight", help="reuse v3.2 zero-API dependency/key check")
    p_pre.add_argument("--real", action="store_true")

    def add_run_args(p):
        p.add_argument("--llm", choices=("fake", "real"), default="fake")
        p.add_argument("--condition", default="all")
        p.add_argument("--simulation-seed", type=int, default=DEFAULT_SIMULATION_SEED)
        p.add_argument("--llm-seed", type=int, default=DEFAULT_LLM_SEED)
        p.add_argument("--demand-seed", type=int, default=DEFAULT_DEMAND_SEED)
        p.add_argument("--support", choices=("absent", "present", "both"), default="both")
        p.add_argument("--no-demand", action="store_true")
        p.add_argument("--allow-real-llm", action="store_true")
        p.add_argument(
            "--output-root",
            type=Path,
            default=PROJECT_ROOT / "results" / "v33_runs",
        )

    p_run = sub.add_parser("run", help="run v3.3 cognition + optional renewal demand")
    add_run_args(p_run)
    p_pipeline = sub.add_parser(
        "pipeline",
        help="run v3.3 cognition + renewal demand + lag-aware descriptive diagnostics",
    )
    add_run_args(p_pipeline)

    p_an = sub.add_parser("analyze", help="analyze an existing v3.3 run")
    p_an.add_argument("run_dir", type=Path)
    p_plot = sub.add_parser("plot", help="plot an existing v3.3 run")
    p_plot.add_argument("run_dir", type=Path)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "preflight":
        from greenconsumer_v32.preflight import print_preflight

        return print_preflight(require_real_llm=args.real)

    if args.command in {"run", "pipeline"}:
        from greenconsumer_v32.preflight import print_preflight

        code = print_preflight(require_real_llm=(args.llm == "real"))
        if code:
            return code

        from .runner import execute

        settings = RunSettings(
            llm_mode=args.llm,
            condition=args.condition,
            simulation_seed=args.simulation_seed,
            requested_llm_seed=args.llm_seed,
            demand_seed=args.demand_seed,
            output_dir=args.output_root,
            run_demand=not args.no_demand,
            support_mode=args.support,
            allow_real_llm=args.allow_real_llm,
        )
        payload = asyncio.run(execute(settings))

        if args.command == "pipeline":
            from .analysis import analyze_run
            from .visualization import plot_run

            run_dir = Path(payload["output_dir"])
            analysis = analyze_run(run_dir)
            figures = plot_run(run_dir)
            payload = {
                "status": "PASS",
                "run": payload,
                "analysis": analysis,
                "figures": figures,
            }

        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "analyze":
        from .analysis import analyze_run

        payload = analyze_run(args.run_dir.resolve())
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "plot":
        from .visualization import plot_run

        outputs = plot_run(args.run_dir.resolve())
        print(json.dumps({"status": "PASS", "figures": outputs}, ensure_ascii=False))
        return 0

    raise RuntimeError(args.command)
