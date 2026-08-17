"""生成中文学术论文图表 — 基于已完成的 v3.3.1 运行结果。

本脚本是纯后处理工具，不运行仿真、不调用 LLM、不修改任何参数或数据。
它从已完成的运行目录读取 CSV/JSON 数据并生成中文标注的学术级图表。

用法：
    # 从一次完整运行生成所有可生成的中文图表
    python run_v33_figures_cn.py <run_dir>

    # 指定输出目录
    python run_v33_figures_cn.py <run_dir> --output-dir ./my_figures

    # 只生成指定图表
    python run_v33_figures_cn.py <run_dir> --only trust-dynamics
    python run_v33_figures_cn.py <run_dir> --only heatmap
    python run_v33_figures_cn.py <run_dir> --only topology
    python run_v33_figures_cn.py <run_dir> --only radar
    python run_v33_figures_cn.py <run_dir> --only mechanism
    python run_v33_figures_cn.py <run_dir> --only interaction

    # 从敏感性分析套件生成中文旋风图/Morris图
    python run_v33_figures_cn.py --sensitivity-suite <suite_dir>
    python run_v33_figures_cn.py --sensitivity-suite <suite_dir> --estimand P1

    # 生成实验设计矩阵概览图（无需运行数据）
    python run_v33_figures_cn.py --experiment-matrix --output-dir ./figures
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run_v33_figures_cn.py",
        description=(
            "从已完成的 v3.3.1 运行结果生成中文学术论文图表。"
            "本脚本是纯后处理工具，不运行仿真或调用 LLM。"
        ),
    )
    parser.add_argument(
        "run_dir", type=Path, nargs="?", default=None,
        help="已完成的 v3.3.1 运行结果目录",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="图表输出目录（默认为 run_dir/figures_cn）",
    )
    parser.add_argument(
        "--only", type=str, default=None,
        choices=[
            "trust-dynamics", "heatmap", "reach", "transmission",
            "radar", "heterogeneity", "interaction", "mechanism",
            "topology", "all",
        ],
        help="只生成指定类型的图表",
    )
    parser.add_argument(
        "--condition", type=str, default=None,
        help="指定条件（用于异质性面板和机制分解图）",
    )
    parser.add_argument(
        "--sensitivity-suite", type=Path, default=None,
        help="敏感性分析套件目录（生成中文旋风图/Morris图）",
    )
    parser.add_argument(
        "--estimand", type=str, default="P1",
        choices=["P1", "P2", "P3", "P4", "P5"],
        help="敏感性图表对应的指标（默认 P1）",
    )
    parser.add_argument(
        "--experiment-matrix", action="store_true",
        help="生成实验设计矩阵概览图（无需运行数据）",
    )

    args = parser.parse_args(argv)

    # 延迟导入，确保字体配置在导入时执行
    from greenconsumer_v33.thesis_figures_cn import (
        generate_all_run_figures_cn,
        plot_trust_dynamics_cn,
        plot_trust_delta_heatmap_cn,
        plot_reach_comparison_cn,
        plot_choice_transmission_cn,
        plot_semantic_radar_cn,
        plot_consumer_heterogeneity_cn,
        plot_three_factor_interaction_cn,
        plot_trust_mechanism_decomposition_cn,
        plot_network_topology_cn,
        plot_experiment_matrix_cn,
        plot_sensitivity_tornado_cn,
        plot_morris_screening_cn,
    )

    ESTIMAND_MAP = {
        "P1": "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
        "P2": "P2_CONTENT_POST_TRUST_V33",
        "P3": "P3_TIMING_PRE_DELAY_TRUST_V33",
        "P4": "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33",
        "P5": "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    }

    # ── 模式 1：实验设计矩阵（无需运行数据）──────────────────────────
    if args.experiment_matrix:
        out_dir = args.output_dir or Path(".")
        path = plot_experiment_matrix_cn(out_dir)
        print(json.dumps({"status": "PASS", "figure": path}, ensure_ascii=False, indent=2))
        return 0

    # ── 模式 2：敏感性分析套件 ──────────────────────────────────────
    if args.sensitivity_suite is not None:
        suite_dir = args.sensitivity_suite.resolve()
        out_dir = args.output_dir or suite_dir / "figures_cn"
        estimand_id = ESTIMAND_MAP[args.estimand]

        outputs = []
        # 尝试 Stage-A（旋风图）
        stage_a_path = suite_dir / "trust_sensitivity_local_effects.csv"
        morris_path = suite_dir / "morris_statistics.csv"

        if stage_a_path.exists():
            path = plot_sensitivity_tornado_cn(suite_dir, estimand_id, out_dir)
            outputs.append(path)
            print(f"[OK] 局部敏感性旋风图: {path}")
        if morris_path.exists():
            path = plot_morris_screening_cn(suite_dir, estimand_id, out_dir)
            outputs.append(path)
            print(f"[OK] Morris 筛查散点图: {path}")

        if not outputs:
            print("[ERROR] 未找到敏感性分析数据文件", file=sys.stderr)
            return 2

        payload = {
            "status": "PASS",
            "mode": "sensitivity",
            "suite_dir": str(suite_dir),
            "figures": outputs,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    # ── 模式 3：从运行目录生成图表 ─────────────────────────────────
    if args.run_dir is None:
        parser.error("必须提供 run_dir 或使用 --sensitivity-suite / --experiment-matrix")

    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        print(f"[ERROR] 目录不存在: {run_dir}", file=sys.stderr)
        return 2

    out_dir = args.output_dir or run_dir / "figures_cn"
    only = args.only

    if only is None or only == "all":
        # 生成全部
        payload = generate_all_run_figures_cn(run_dir, out_dir)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if payload["figures_failed"] > 0:
            print(f"\n[WARN] {payload['figures_failed']} 张图表生成失败:", file=sys.stderr)
            for err in payload["errors"]:
                print(f"  - {err}", file=sys.stderr)
        return 0 if payload["figures_generated"] > 0 else 2

    # 单独生成指定图表
    condition = args.condition or "Empathy-Hub-Immediate"
    single_map = {
        "trust-dynamics": lambda: plot_trust_dynamics_cn(run_dir, out_dir),
        "heatmap": lambda: plot_trust_delta_heatmap_cn(run_dir, out_dir),
        "reach": lambda: plot_reach_comparison_cn(run_dir, out_dir),
        "transmission": lambda: plot_choice_transmission_cn(run_dir, out_dir),
        "radar": lambda: plot_semantic_radar_cn(run_dir, out_dir),
        "heterogeneity": lambda: plot_consumer_heterogeneity_cn(
            run_dir, out_dir, condition=condition
        ),
        "interaction": lambda: plot_three_factor_interaction_cn(run_dir, out_dir),
        "mechanism": lambda: plot_trust_mechanism_decomposition_cn(
            run_dir, out_dir, condition=condition
        ),
        "topology": lambda: plot_network_topology_cn(run_dir, out_dir),
    }

    try:
        path = single_map[only]()
        print(json.dumps({"status": "PASS", "figure": path}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
