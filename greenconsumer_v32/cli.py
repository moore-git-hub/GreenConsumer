"""统一命令行接口。

PyCharm/终端用户只应从 ``run_v32.py`` 进入本模块。子命令把整个项目
收敛为 preflight → verify → run/pipeline → analyze → plot → formal-status。

这里刻意使用“延迟导入”：即使 AgentKernel 等运行依赖缺失，``preflight``
本身仍能启动并报告缺失项，而不是在 CLI import 阶段直接崩溃。
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .config import (
    DEFAULT_DEMAND_SEED,
    DEFAULT_LLM_SEED,
    DEFAULT_SIMULATION_SEED,
    PROJECT_ROOT,
    RunSettings,
)


def build_parser() -> argparse.ArgumentParser:
    """构建唯一 CLI，不暴露历史 runner。"""
    parser = argparse.ArgumentParser(
        prog="python run_v32.py",
        description="TASK_005 FMCG v3.2 clean workflow",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_pre = sub.add_parser("preflight", help="zero-API dependency/model/key readiness check")
    p_pre.add_argument("--real", action="store_true")
    sub.add_parser("verify", help="run the six current v3.2 regression test groups")

    def add_run_args(p):
        p.add_argument("--llm", choices=("fake", "real"), default="fake")
        p.add_argument("--condition", default="all")
        p.add_argument("--simulation-seed", type=int, default=DEFAULT_SIMULATION_SEED)
        p.add_argument("--llm-seed", type=int, default=DEFAULT_LLM_SEED)
        p.add_argument("--demand-seed", type=int, default=DEFAULT_DEMAND_SEED)
        p.add_argument("--support", choices=("absent", "present", "both"), default="both")
        p.add_argument("--no-demand", action="store_true")
        # 双重显式条件：--llm real + --allow-real-llm。
        # 用于避免在 PyCharm 中误点后产生真实 API 调用。
        p.add_argument("--allow-real-llm", action="store_true")
        p.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "results" / "v32_runs")

    p_run = sub.add_parser("run", help="run cognition + optional demand; no auto analysis/plots")
    add_run_args(p_run)
    p_pipeline = sub.add_parser("pipeline", help="run cognition + demand + descriptive analysis + plots")
    add_run_args(p_pipeline)

    p_an = sub.add_parser("analyze", help="analyze an existing clean-workflow run")
    p_an.add_argument("run_dir", type=Path)
    p_plot = sub.add_parser("plot", help="plot an existing clean-workflow run")
    p_plot.add_argument("run_dir", type=Path)
    sub.add_parser("formal-status", help="read the closed F001-F010 archive; never launches formal runs")
    return parser


def main(argv=None) -> int:
    """解析命令并按需导入对应模块。"""
    args = build_parser().parse_args(argv)

    if args.command == "preflight":
        from .preflight import print_preflight
        return print_preflight(require_real_llm=args.real)

    if args.command == "verify":
        from .verification import verify_tests
        payload = verify_tests()
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if payload["status"] == "PASS" else 2

    if args.command in {"run", "pipeline"}:
        from .preflight import print_preflight
        # 真实模式先进行 zero-call preflight；失败时绝不导入/启动 runner。
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
            payload = {"status": "PASS", "run": payload, "analysis": analysis, "figures": figures}

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

    if args.command == "formal-status":
        from .formal import formal_status
        print(json.dumps(formal_status(), ensure_ascii=False, sort_keys=True))
        return 0

    raise RuntimeError(args.command)
