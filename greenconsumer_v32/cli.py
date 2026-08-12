from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .analysis import analyze_run
from .config import (
    DEFAULT_DEMAND_SEED,
    DEFAULT_LLM_SEED,
    DEFAULT_SIMULATION_SEED,
    PROJECT_ROOT,
    RunSettings,
)
from .formal import formal_status
from .preflight import print_preflight
from .runner import execute
from .verification import verify_tests
from .visualization import plot_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python run_v32.py",
        description="Clean TASK_005 FMCG v3.2 workflow",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_pre = sub.add_parser("preflight")
    p_pre.add_argument("--real", action="store_true")

    sub.add_parser("verify")

    def add_run_args(p):
        p.add_argument("--llm", choices=("fake", "real"), default="fake")
        p.add_argument("--condition", default="all")
        p.add_argument(
            "--simulation-seed", type=int, default=DEFAULT_SIMULATION_SEED
        )
        p.add_argument("--llm-seed", type=int, default=DEFAULT_LLM_SEED)
        p.add_argument("--demand-seed", type=int, default=DEFAULT_DEMAND_SEED)
        p.add_argument(
            "--support", choices=("absent", "present", "both"), default="both"
        )
        p.add_argument("--no-demand", action="store_true")
        p.add_argument("--allow-real-llm", action="store_true")
        p.add_argument(
            "--output-root",
            type=Path,
            default=PROJECT_ROOT / "results" / "v32_runs",
        )

    p_run = sub.add_parser("run")
    add_run_args(p_run)

    p_pipeline = sub.add_parser("pipeline")
    add_run_args(p_pipeline)

    p_an = sub.add_parser("analyze")
    p_an.add_argument("run_dir", type=Path)

    p_plot = sub.add_parser("plot")
    p_plot.add_argument("run_dir", type=Path)

    sub.add_parser("formal-status")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "preflight":
        return print_preflight(require_real_llm=args.real)

    if args.command == "verify":
        payload = verify_tests()
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if payload["status"] == "PASS" else 2

    if args.command in {"run", "pipeline"}:
        code = print_preflight(require_real_llm=(args.llm == "real"))
        if code:
            return code
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
        payload = analyze_run(args.run_dir.resolve())
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "plot":
        outputs = plot_run(args.run_dir.resolve())
        print(json.dumps({"status": "PASS", "figures": outputs}, ensure_ascii=False))
        return 0

    if args.command == "formal-status":
        print(json.dumps(formal_status(), ensure_ascii=False, sort_keys=True))
        return 0

    raise RuntimeError(args.command)
