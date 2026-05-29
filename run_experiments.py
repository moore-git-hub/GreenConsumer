"""
run_experiments.py — 实验批量调度入口

遍历 2×2×3=12 个策略组合，顺序执行仿真，汇总结果并生成帕累托分析。

用法：
    python run_experiments.py
"""
import sys
import os
import asyncio
import csv
import json
import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from experiment_config import generate_experiment_matrix
from simulation_core import run_simulation_core


def write_summary_csv(results: list, output_path: str):
    """将所有实验结果写入汇总 CSV"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "exp_id", "content_factor", "channel_factor", "timing_factor",
            "t80", "steady_state_score", "recovery_rate",
            "trust_min", "trust_min_tick", "baseline_trust"
        ])
        for r in results:
            if "error" in r:
                writer.writerow([r["exp_id"], "", "", "", "ERROR", "", "", "", "", ""])
                continue
            cfg = r["config"]
            m = r["metrics"]
            writer.writerow([
                r["exp_id"],
                cfg["content_factor"],
                cfg["channel_factor"],
                cfg["timing_factor"],
                m.t80,
                m.steady_state_score,
                m.recovery_rate,
                m.trust_min,
                m.trust_min_tick,
                m.baseline_trust,
            ])


async def main():
    print("=" * 60)
    print("🧪 GABM 策略因子化实验 — 批量调度启动")
    print("   实验矩阵: 2(内容) × 2(渠道) × 3(时机) = 12 组")
    print("=" * 60)

    configs = generate_experiment_matrix()
    total = len(configs)
    results = []
    errors = []

    for i, config in enumerate(configs, 1):
        print(f"\n{'─'*60}")
        print(f"  [{i}/{total}] 🚀 Running: {config.exp_id}")
        print(f"    Content={config.content_factor} | Channel={config.channel_factor} | Timing={config.timing_factor}")
        print(f"{'─'*60}")

        try:
            result = await run_simulation_core(config)
            results.append(result)
        except Exception as e:
            error_msg = f"{config.exp_id}: {type(e).__name__}: {e}"
            print(f"  ❌ FAILED: {error_msg}")
            errors.append(error_msg)
            results.append({"exp_id": config.exp_id, "error": str(e)})

    # ── 写入汇总 CSV ────────────────────────────────────────────────
    results_dir = os.path.join(current_dir, "results", "experiments")
    os.makedirs(results_dir, exist_ok=True)

    summary_path = os.path.join(results_dir, "summary.csv")
    write_summary_csv(results, summary_path)
    print(f"\n📄 汇总表已保存: {summary_path}")

    # ── 写入错误日志 ────────────────────────────────────────────────
    if errors:
        error_path = os.path.join(results_dir, "errors.log")
        with open(error_path, "w", encoding="utf-8") as f:
            f.write(f"Experiment Errors — {datetime.datetime.now()}\n")
            f.write("=" * 50 + "\n")
            for err in errors:
                f.write(f"  {err}\n")
        print(f"⚠️ {len(errors)} 次运行失败，详见: {error_path}")

    # ── 帕累托分析 ──────────────────────────────────────────────────
    successful = [r for r in results if "error" not in r]
    if successful:
        try:
            from plot_pareto import analyze_and_plot_pareto
            analyze_and_plot_pareto(successful, results_dir)
        except ImportError:
            print("⚠️ plot_pareto.py 未找到，跳过帕累托分析。")
        except Exception as e:
            print(f"⚠️ 帕累托分析失败: {e}")

    # ── 最终汇总 ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"✅ 实验完成: {len(successful)}/{total} 成功, {len(errors)}/{total} 失败")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
