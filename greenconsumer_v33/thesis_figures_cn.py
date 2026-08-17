"""中文学术论文图表生成模块 — TASK_005 FMCG v3.3.1。

本模块为《基于GABM的绿色快消品品牌信任危机修复策略研究》硕士论文
提供中文标注的学术级可视化图表。所有图表仅用于已完成运行结果的后处理
展示，不改变模型状态、参数或种子。

图表类型覆盖：
  1. 品牌信任动态轨迹比较图
  2. 实验条件间品牌信任差异热力图
  3. 品牌信任参数局部敏感性旋风图（Stage-A OAT）
  4. Morris 全局筛查散点图
  5. 网络拓扑结构可视化与度分布
  6. 企业信息到达速度×触达概率矩阵图
  7. 网络规模与投放配置对比图
  8. 实验设计因素矩阵概览图
  9. 消费者异质性面板图
 10. 条件品牌选择传导图
 11. 语义评价维度雷达图
 12. 信任机制路径分解图

中文字体设置：优先使用 SimHei/Microsoft YaHei，
回退到系统可用中文字体。
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator
import numpy as np

# ── 字体配置 ──────────────────────────────────────────────────────────────
_CN_FONTS = ["SimHei", "Microsoft YaHei", "STSong", "FangSong", "KaiTi"]


def _setup_chinese_font():
    """配置 matplotlib 中文字体，避免乱码。

    设置 axes.unicode_minus=False 使用 ASCII hyphen-minus 代替 Unicode
    MINUS SIGN (U+2212)，避免 SimHei 缺少该字形的警告。
    """
    plt.rcParams["font.sans-serif"] = _CN_FONTS + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = 10
    plt.rcParams["axes.titlesize"] = 12
    plt.rcParams["axes.labelsize"] = 10.5
    plt.rcParams["xtick.labelsize"] = 9
    plt.rcParams["ytick.labelsize"] = 9
    plt.rcParams["legend.fontsize"] = 9
    # 抑制字体缺字形警告（SimHei 对部分 Unicode 数学符号不完整）
    import warnings
    warnings.filterwarnings("ignore", message="Glyph.*missing from.*font")


_setup_chinese_font()

# ── 通用样式常量 ──────────────────────────────────────────────────────────
DPI = 300
FIGSIZE_WIDE = (10, 5.5)
FIGSIZE_SQUARE = (7, 6)
FIGSIZE_TALL = (8, 7)
FIGSIZE_MATRIX = (12, 6)

CONTROL = "NoClarification-Control"

# 条件中文映射
CONDITION_CN = {
    "NoClarification-Control": "不澄清对照",
    "Rational-Hub-Immediate": "理性-核心-即时",
    "Rational-Hub-Delayed": "理性-核心-延迟",
    "Rational-Random-Immediate": "理性-随机-即时",
    "Rational-Random-Delayed": "理性-随机-延迟",
    "Empathy-Hub-Immediate": "共情-核心-即时",
    "Empathy-Hub-Delayed": "共情-核心-延迟",
    "Empathy-Random-Immediate": "共情-随机-即时",
    "Empathy-Random-Delayed": "共情-随机-延迟",
}

# 配色方案（学术友好，适合黑白打印）
COLORS_CONTENT = {"rational": "#2166AC", "empathy": "#B2182B"}
COLORS_CHANNEL = {"hub": "#1B7837", "random": "#762A83"}
COLORS_TIMING = {"immediate": "#E66101", "delayed": "#5E3C99"}

CMAP_DIVERGING = "RdBu_r"
CMAP_SEQUENTIAL = "YlOrRd"


# ── 数据辅助函数 ──────────────────────────────────────────────────────────

def _mean(values) -> float:
    values = [v for v in values if v is not None and not math.isnan(v)]
    return sum(values) / len(values) if values else float("nan")


def _tick_mean(rows: list[dict], field: str) -> dict[int, float]:
    grouped: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        value = row.get(field, "")
        if value in ("", None):
            continue
        try:
            grouped[int(row["tick"])].append(float(value))
        except (ValueError, TypeError):
            continue
    return {tick: _mean(vals) for tick, vals in sorted(grouped.items())}


def _group_by_condition(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        out[str(row["exp_id"])].append(row)
    return dict(out)


def _cn(exp_id: str) -> str:
    """将条件英文 ID 转为中文标签。"""
    return CONDITION_CN.get(exp_id, exp_id)


def _save(fig, path: Path, dpi: int = DPI):
    """保存图片并关闭。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return str(path)


def _read_csv(path: Path) -> list[dict]:
    """简易 CSV 读取，返回字典列表。"""
    import csv
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 1：品牌信任动态轨迹比较图
# ══════════════════════════════════════════════════════════════════════════════

def plot_trust_dynamics_cn(
    run_dir: Path,
    output_dir: Path | None = None,
    *,
    crisis_tick: int = 5,
    immediate_tick: int = 6,
    delayed_tick: int = 10,
) -> str:
    """生成中文标注的品牌信任动态轨迹对比图。

    显示不澄清对照组 vs 八策略组均值与范围带。
    """
    cognitive = _read_csv(Path(run_dir) / "cognitive_records.csv")
    if not cognitive:
        raise FileNotFoundError("cognitive_records.csv 不存在或为空")

    by_cond = _group_by_condition(cognitive)
    if CONTROL not in by_cond:
        raise ValueError("需要不澄清对照组数据")

    output_dir = Path(output_dir or Path(run_dir) / "figures_cn")
    control_series = _tick_mean(by_cond[CONTROL], "trust_final")
    strategy_ids = sorted(x for x in by_cond if x != CONTROL)
    strategy_series = {
        eid: _tick_mean(by_cond[eid], "trust_final") for eid in strategy_ids
    }
    ticks = sorted(control_series)

    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)

    # 对照组
    ax.plot(
        ticks, [control_series[t] for t in ticks],
        "k-o", markersize=3, linewidth=1.8, label="不澄清对照组"
    )

    # 策略组均值和范围
    s_mean = [_mean([strategy_series[x].get(t, float("nan")) for x in strategy_ids]) for t in ticks]
    s_min = [min(strategy_series[x].get(t, float("nan")) for x in strategy_ids) for t in ticks]
    s_max = [max(strategy_series[x].get(t, float("nan")) for x in strategy_ids) for t in ticks]

    ax.plot(ticks, s_mean, "s-", color="#D32F2F", markersize=3, linewidth=1.8, label="八策略组均值")
    ax.fill_between(ticks, s_min, s_max, alpha=0.12, color="#D32F2F", label="策略组取值范围")

    # 关键事件标注
    ymin, ymax = ax.get_ylim()
    ax.axvline(crisis_tick, linestyle="--", color="gray", linewidth=1)
    ax.axvline(immediate_tick, linestyle=":", color=COLORS_TIMING["immediate"], linewidth=1)
    ax.axvline(delayed_tick, linestyle=":", color=COLORS_TIMING["delayed"], linewidth=1)
    ax.text(crisis_tick + 0.2, ymax * 0.98, "危机发生", fontsize=8, va="top", color="gray")
    ax.text(immediate_tick + 0.2, ymax * 0.93, "即时回应", fontsize=8, va="top",
            color=COLORS_TIMING["immediate"])
    ax.text(delayed_tick + 0.2, ymax * 0.88, "延迟回应", fontsize=8, va="top",
            color=COLORS_TIMING["delayed"])

    ax.set_xlabel("时间步（Tick）")
    ax.set_ylabel("品牌信任均值")
    ax.set_title("品牌信任动态轨迹：澄清组 vs 不澄清对照组")
    ax.legend(loc="lower right", framealpha=0.9)
    ax.set_xlim(min(ticks), max(ticks))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(True, alpha=0.3, linestyle="--")

    path = output_dir / "01_品牌信任动态轨迹.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 2：处理条件间品牌信任差异热力图
# ══════════════════════════════════════════════════════════════════════════════

def plot_trust_delta_heatmap_cn(
    run_dir: Path,
    output_dir: Path | None = None,
) -> str:
    """生成中文标注的策略条件−对照组信任差异热力图。"""
    cognitive = _read_csv(Path(run_dir) / "cognitive_records.csv")
    if not cognitive:
        raise FileNotFoundError("cognitive_records.csv 不存在或为空")

    by_cond = _group_by_condition(cognitive)
    if CONTROL not in by_cond:
        raise ValueError("需要不澄清对照组数据")

    output_dir = Path(output_dir or Path(run_dir) / "figures_cn")
    control_series = _tick_mean(by_cond[CONTROL], "trust_final")
    strategy_ids = sorted(x for x in by_cond if x != CONTROL)
    strategy_series = {
        eid: _tick_mean(by_cond[eid], "trust_final") for eid in strategy_ids
    }
    ticks = sorted(control_series)

    matrix = np.array([
        [strategy_series[eid].get(t, float("nan")) - control_series.get(t, 0) for t in ticks]
        for eid in strategy_ids
    ])
    vmax = max(abs(float(np.nanmin(matrix))), abs(float(np.nanmax(matrix))), 1e-9)

    fig, ax = plt.subplots(figsize=FIGSIZE_MATRIX)
    im = ax.imshow(matrix, aspect="auto", cmap=CMAP_DIVERGING, vmin=-vmax, vmax=vmax)
    ax.set_yticks(range(len(strategy_ids)))
    ax.set_yticklabels([_cn(eid) for eid in strategy_ids], fontsize=9)
    ax.set_xticks(range(0, len(ticks), 2))
    ax.set_xticklabels([ticks[i] for i in range(0, len(ticks), 2)])
    ax.set_xlabel("时间步（Tick）")
    ax.set_ylabel("策略条件")
    ax.set_title("各策略条件相对不澄清对照组的品牌信任差异")
    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    cbar.set_label("ΔTrust（处理组 − 对照组）")

    path = output_dir / "02_信任差异热力图.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 3：品牌信任参数局部敏感性旋风图
# ══════════════════════════════════════════════════════════════════════════════

# 参数中文映射
PARAM_CN = {
    "crisis_retention": "危机记忆保持率",
    "repair_retention": "修复记忆保持率",
    "event_adjustment": "事件调整速度",
    "quiet_adjustment": "静默调整速度",
    "repair_saturation": "修复饱和系数",
    "hypocrisy_weight": "伪善感知权重",
    "empathy_repair_weight": "共情修复权重",
}

# Estimand 中文映射
ESTIMAND_CN = {
    "P1_OVERALL_CLARIFICATION_POST_TRUST_V33": "P1 总体澄清效应（品牌信任）",
    "P2_CONTENT_POST_TRUST_V33": "P2 内容框架差异（品牌信任）",
    "P3_TIMING_PRE_DELAY_TRUST_V33": "P3 回应时机差异（早期信任）",
    "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33": "P4 投放渠道差异（直接触达）",
    "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33": "P5 总体澄清效应（条件品牌选择）",
}

ESTIMAND_UNIT_CN = {
    "P1_OVERALL_CLARIFICATION_POST_TRUST_V33": "品牌信任指数",
    "P2_CONTENT_POST_TRUST_V33": "品牌信任指数",
    "P3_TIMING_PRE_DELAY_TRUST_V33": "品牌信任指数",
    "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33": "触达比例",
    "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33": "条件选择概率",
}


def plot_sensitivity_tornado_cn(
    suite_dir: Path,
    estimand_id: str = "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
    output_dir: Path | None = None,
) -> str:
    """生成中文标注的局部敏感性分析旋风图（Stage-A OAT）。"""
    import pandas as pd

    suite_dir = Path(suite_dir)
    csv_path = suite_dir / "trust_sensitivity_local_effects.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"局部敏感性数据不存在: {csv_path}")

    df = pd.read_csv(csv_path)
    df = df[df["estimand_id"].astype(str) == estimand_id].copy()
    if df.empty:
        raise ValueError(f"未找到指标: {estimand_id}")

    df["max_abs_delta"] = df[
        ["low_delta_from_baseline", "high_delta_from_baseline"]
    ].abs().max(axis=1)
    df = df.sort_values("max_abs_delta", ascending=True)

    output_dir = Path(output_dir or suite_dir / "figures_cn")
    title = ESTIMAND_CN.get(estimand_id, estimand_id)
    unit = ESTIMAND_UNIT_CN.get(estimand_id, "")

    fig, ax = plt.subplots(figsize=FIGSIZE_SQUARE)
    y = list(range(len(df)))
    param_labels = [PARAM_CN.get(p, p) for p in df["parameter"]]

    ax.barh(y, df["high_delta_from_baseline"] - df["low_delta_from_baseline"],
            left=df["low_delta_from_baseline"], color="#4393C3", alpha=0.7,
            edgecolor="#2166AC", linewidth=0.8)
    ax.scatter(df["low_delta_from_baseline"], y, color="#2166AC", s=40,
               zorder=5, label="低值 − 基准")
    ax.scatter(df["high_delta_from_baseline"], y, color="#B2182B", s=40,
               zorder=5, label="高值 − 基准")

    ax.axvline(0.0, linewidth=1, color="black", linestyle="-")
    ax.set_yticks(y)
    ax.set_yticklabels(param_labels)
    ax.set_xlabel(f"相对基准情形的有符号变化量（{unit}）")
    ax.set_title(f"{title}\n局部敏感性分析（OAT）")
    ax.legend(loc="lower right")
    ax.grid(True, axis="x", alpha=0.3, linestyle="--")

    path = output_dir / f"03_局部敏感性_{estimand_id[:2]}.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 4：Morris 全局筛查散点图
# ══════════════════════════════════════════════════════════════════════════════

def plot_morris_screening_cn(
    suite_dir: Path,
    estimand_id: str = "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
    output_dir: Path | None = None,
) -> str:
    """生成中文标注的 Morris 基本效应筛查散点图。"""
    import pandas as pd

    suite_dir = Path(suite_dir)
    csv_path = suite_dir / "morris_statistics.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Morris 筛查数据不存在: {csv_path}")

    df = pd.read_csv(csv_path)
    df = df[df["estimand_id"].astype(str) == estimand_id].copy()
    if df.empty:
        raise ValueError(f"未找到指标: {estimand_id}")

    output_dir = Path(output_dir or suite_dir / "figures_cn")
    title = ESTIMAND_CN.get(estimand_id, estimand_id)
    unit = ESTIMAND_UNIT_CN.get(estimand_id, "")

    fig, ax = plt.subplots(figsize=FIGSIZE_SQUARE)
    ax.scatter(df["mu_star"], df["sigma"], s=80, c="#D32F2F", edgecolors="black",
               linewidth=0.8, zorder=5)

    for row in df.itertuples(index=False):
        label = PARAM_CN.get(str(row.parameter), str(row.parameter))
        ax.annotate(
            label,
            (float(row.mu_star), float(row.sigma)),
            fontsize=8.5, xytext=(6, 5), textcoords="offset points",
            arrowprops=dict(arrowstyle="-", color="gray", lw=0.5),
        )

    # 添加 σ = μ* 参考线
    max_val = max(df["mu_star"].max(), df["sigma"].max()) * 1.1
    ax.plot([0, max_val], [0, max_val], "--", color="gray", linewidth=0.8,
            label="σ = μ*（非线性/交互参考线）")

    ax.set_xlabel(f"μ* — 平均绝对基本效应（{unit}）")
    ax.set_ylabel(f"σ — 基本效应标准差（{unit}）")
    ax.set_title(f"{title}\nMorris 全局敏感性筛查")
    ax.legend(loc="upper left", framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)

    path = output_dir / f"04_Morris筛查_{estimand_id[:2]}.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 5：网络拓扑结构可视化与度分布
# ══════════════════════════════════════════════════════════════════════════════

def plot_network_topology_cn(
    run_dir: Path,
    output_dir: Path | None = None,
    *,
    layout_seed: int = 42,
) -> str:
    """生成中文标注的网络拓扑结构图（含度分布子图）。"""
    import networkx as nx

    run_dir = Path(run_dir)
    nodes_csv = _read_csv(run_dir / "network_nodes.csv")
    edges_csv = _read_csv(run_dir / "network_edges.csv")
    if not nodes_csv or not edges_csv:
        raise FileNotFoundError("网络拓扑数据不存在")

    output_dir = Path(output_dir or run_dir / "figures_cn")
    G = nx.DiGraph()
    for node in nodes_csv:
        G.add_node(str(node["agent_id"]))
    for edge in edges_csv:
        G.add_edge(str(edge["source_agent_id"]), str(edge["target_agent_id"]))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5),
                                     gridspec_kw={"width_ratios": [1.6, 1]})

    # 左图：网络拓扑
    pos = nx.spring_layout(G, seed=layout_seed, k=1.5 / math.sqrt(len(G)))
    degrees = dict(G.out_degree())
    node_sizes = [80 + degrees.get(n, 0) * 60 for n in G.nodes()]
    node_colors = [degrees.get(n, 0) for n in G.nodes()]

    nx.draw_networkx_edges(G, pos, ax=ax1, alpha=0.15, width=0.5,
                           edge_color="gray", arrows=True, arrowsize=6)
    scatter = nx.draw_networkx_nodes(
        G, pos, ax=ax1, node_size=node_sizes,
        node_color=node_colors, cmap="YlOrRd",
        edgecolors="black", linewidths=0.5,
    )
    plt.colorbar(scatter, ax=ax1, label="出度", shrink=0.8)
    ax1.set_title("社会网络拓扑结构（BA 无标度有向网络）")
    ax1.axis("off")

    # 右图：度分布
    out_degrees = [d for _, d in G.out_degree()]
    in_degrees = [d for _, d in G.in_degree()]
    max_deg = max(max(out_degrees), max(in_degrees)) + 1
    bins = range(0, max_deg + 1)
    ax2.hist(out_degrees, bins=bins, alpha=0.6, color="#2166AC", label="出度", edgecolor="white")
    ax2.hist(in_degrees, bins=bins, alpha=0.6, color="#B2182B", label="入度", edgecolor="white")
    ax2.set_xlabel("度数")
    ax2.set_ylabel("节点数量")
    ax2.set_title("度分布")
    ax2.legend()
    ax2.grid(True, alpha=0.3, linestyle="--")

    path = output_dir / "05_网络拓扑与度分布.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 6：企业信息直接触达对比图
# ══════════════════════════════════════════════════════════════════════════════

def plot_reach_comparison_cn(
    run_dir: Path,
    output_dir: Path | None = None,
) -> str:
    """生成中文标注的企业信息直接触达对比图。"""
    reach = _read_csv(Path(run_dir) / "clarification_reach_v33.csv")
    if not reach:
        raise FileNotFoundError("clarification_reach_v33.csv 不存在")

    output_dir = Path(output_dir or Path(run_dir) / "figures_cn")

    labels = [_cn(row["exp_id"]) for row in reach]
    direct = [float(row["direct_reach_t0"]) for row in reach]
    eventual = [float(row["eventual_enterprise_reach"]) for row in reach]

    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    y = np.arange(len(labels))
    width = 0.35

    bars1 = ax.barh(y + width / 2, direct, width, label="即时直接触达（t₀）",
                    color="#2166AC", edgecolor="white")
    bars2 = ax.barh(y - width / 2, eventual, width, label="最终直接触达（含延迟窗口）",
                    color="#B2182B", edgecolor="white")

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("触达比例（认知智能体占比）")
    ax.set_ylabel("策略条件")
    ax.set_title("企业澄清信息的直接触达比较")
    ax.legend(loc="lower right")
    ax.set_xlim(0, 1.05)
    ax.grid(True, axis="x", alpha=0.3, linestyle="--")

    # 添加数值标注
    for bar in bars1:
        w = bar.get_width()
        ax.text(w + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{w:.2f}", va="center", fontsize=8)
    for bar in bars2:
        w = bar.get_width()
        ax.text(w + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{w:.2f}", va="center", fontsize=8)

    path = output_dir / "06_企业信息直接触达对比.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 7：信息到达速度×触达概率矩阵图
# ══════════════════════════════════════════════════════════════════════════════

def plot_arrival_speed_matrix_cn(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> str:
    """生成信息到达速度与触达概率对早期回应差异的矩阵图。

    参数 results 应为形如：
    [{"reach_rate": 0.30, "delivery_lag": 0, "timing_delta": 0.307}, ...]
    的字典列表，代表9种"触达概率×到达时延"组合下的早期时机差异值。
    """
    if not results:
        raise ValueError("results 为空，无法绘图")

    output_dir = Path(output_dir)

    reach_rates = sorted(set(r["reach_rate"] for r in results))
    lags = sorted(set(r["delivery_lag"] for r in results))

    matrix = np.full((len(reach_rates), len(lags)), float("nan"))
    for r in results:
        i = reach_rates.index(r["reach_rate"])
        j = lags.index(r["delivery_lag"])
        matrix[i, j] = r["timing_delta"]

    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(matrix, cmap=CMAP_SEQUENTIAL, aspect="auto")

    ax.set_xticks(range(len(lags)))
    ax.set_xticklabels([f"延后{lag}步" if lag > 0 else "同步到达" for lag in lags])
    ax.set_yticks(range(len(reach_rates)))
    ax.set_yticklabels([f"{r:.0%}" for r in reach_rates])
    ax.set_xlabel("信息到达时延")
    ax.set_ylabel("企业直接触达概率")
    ax.set_title("信息到达速度对早期回应时机差异的影响\n（即时回应 − 延迟回应的品牌信任差值）")

    # 在每个单元格显示数值
    for i in range(len(reach_rates)):
        for j in range(len(lags)):
            val = matrix[i, j]
            if not math.isnan(val):
                ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                        fontsize=10, color="white" if val > np.nanmax(matrix) * 0.6 else "black")

    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    cbar.set_label("早期品牌信任差值")

    path = output_dir / "07_信息到达速度矩阵.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 8：网络规模与投放配置对比图
# ══════════════════════════════════════════════════════════════════════════════

def plot_network_scale_comparison_cn(
    results: list[dict[str, Any]],
    output_dir: Path,
    *,
    metric: str = "reach_delta",
    ylabel: str = "核心节点 − 随机节点的直接触达差值",
    title: str = "网络规模扩大时两类初始投放资源配置的触达差异",
) -> str:
    """生成网络规模×投放配置对比图。

    参数 results 应为形如：
    [{"n_agents": 20, "config": "fixed_3", "value": 0.40, "std": 0.05}, ...]
    """
    if not results:
        raise ValueError("results 为空")

    output_dir = Path(output_dir)
    configs = sorted(set(r["config"] for r in results))
    n_agents_list = sorted(set(r["n_agents"] for r in results))

    config_cn = {
        "fixed_3": "固定投放3个节点",
        "proportional_15pct": "按15%比例投放",
    }
    config_colors = {"fixed_3": "#2166AC", "proportional_15pct": "#B2182B"}

    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    x = np.arange(len(n_agents_list))
    width = 0.35

    for i, cfg in enumerate(configs):
        cfg_data = [r for r in results if r["config"] == cfg]
        values = []
        errors = []
        for n in n_agents_list:
            matched = [r for r in cfg_data if r["n_agents"] == n]
            if matched:
                values.append(matched[0]["value"])
                errors.append(matched[0].get("std", 0))
            else:
                values.append(0)
                errors.append(0)

        offset = (i - len(configs) / 2 + 0.5) * width
        bars = ax.bar(
            x + offset, values, width, yerr=errors,
            label=config_cn.get(cfg, cfg),
            color=config_colors.get(cfg, f"C{i}"),
            edgecolor="white", capsize=3,
        )
        # 数值标注
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([f"N={n}" for n in n_agents_list])
    ax.set_xlabel("网络规模（消费者智能体数量）")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(loc="upper right")
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    path = output_dir / "08_网络规模投放配置对比.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 9：实验设计因素矩阵概览图
# ══════════════════════════════════════════════════════════════════════════════

def plot_experiment_matrix_cn(output_dir: Path) -> str:
    """生成 2×2×2 + 对照组的实验设计矩阵概览图。"""
    output_dir = Path(output_dir)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis("off")

    # 用表格形式展示实验矩阵
    columns = ["即时回应", "延迟回应"]
    rows_hub = ["理性-核心", "共情-核心"]
    rows_random = ["理性-随机", "共情-随机"]

    # 绘制两个 2×2 子表格
    table_data_hub = [
        ["理性-核心-即时", "理性-核心-延迟"],
        ["共情-核心-即时", "共情-核心-延迟"],
    ]
    table_data_random = [
        ["理性-随机-即时", "理性-随机-延迟"],
        ["共情-随机-即时", "共情-随机-延迟"],
    ]

    # 上半部分：核心节点投放
    ax.text(0.5, 0.95, "企业危机沟通策略实验设计：2×2×2 + 共同不澄清对照",
            ha="center", va="top", fontsize=13, fontweight="bold", transform=ax.transAxes)

    # 绘制结构化示意
    cell_w, cell_h = 0.18, 0.12
    x_start = 0.15
    y_start_hub = 0.72
    y_start_random = 0.38

    # 标题行
    ax.text(x_start + cell_w * 1.5, y_start_hub + cell_h * 1.3, "核心节点投放",
            ha="center", fontsize=11, fontweight="bold", color=COLORS_CHANNEL["hub"])
    ax.text(x_start + cell_w * 1.5, y_start_random + cell_h * 1.3, "随机节点投放",
            ha="center", fontsize=11, fontweight="bold", color=COLORS_CHANNEL["random"])

    # 列标题
    for block_y in (y_start_hub, y_start_random):
        ax.text(x_start + cell_w * 0.5, block_y + cell_h, "即时回应",
                ha="center", va="center", fontsize=9, color=COLORS_TIMING["immediate"])
        ax.text(x_start + cell_w * 2.5, block_y + cell_h, "延迟回应",
                ha="center", va="center", fontsize=9, color=COLORS_TIMING["delayed"])

    def _draw_cell(x, y, text, color):
        rect = mpatches.FancyBboxPatch(
            (x, y), cell_w * 0.9, cell_h * 0.85,
            boxstyle="round,pad=0.02", facecolor=color, alpha=0.3,
            edgecolor=color, linewidth=1.5,
        )
        ax.add_patch(rect)
        ax.text(x + cell_w * 0.45, y + cell_h * 0.42, text,
                ha="center", va="center", fontsize=8.5)

    # 核心节点 block
    _draw_cell(x_start, y_start_hub - cell_h * 0.1, "理性-核心-即时", COLORS_CONTENT["rational"])
    _draw_cell(x_start + cell_w * 2, y_start_hub - cell_h * 0.1, "理性-核心-延迟", COLORS_CONTENT["rational"])
    _draw_cell(x_start, y_start_hub - cell_h * 1.2, "共情-核心-即时", COLORS_CONTENT["empathy"])
    _draw_cell(x_start + cell_w * 2, y_start_hub - cell_h * 1.2, "共情-核心-延迟", COLORS_CONTENT["empathy"])

    # 随机节点 block
    _draw_cell(x_start, y_start_random - cell_h * 0.1, "理性-随机-即时", COLORS_CONTENT["rational"])
    _draw_cell(x_start + cell_w * 2, y_start_random - cell_h * 0.1, "理性-随机-延迟", COLORS_CONTENT["rational"])
    _draw_cell(x_start, y_start_random - cell_h * 1.2, "共情-随机-即时", COLORS_CONTENT["empathy"])
    _draw_cell(x_start + cell_w * 2, y_start_random - cell_h * 1.2, "共情-随机-延迟", COLORS_CONTENT["empathy"])

    # 对照组
    rect = mpatches.FancyBboxPatch(
        (0.65, 0.35), 0.25, 0.25,
        boxstyle="round,pad=0.03", facecolor="#E0E0E0", alpha=0.5,
        edgecolor="black", linewidth=1.5,
    )
    ax.add_patch(rect)
    ax.text(0.775, 0.475, "不澄清对照组\n（共同历史基线）",
            ha="center", va="center", fontsize=10)

    # 因素标注
    ax.text(0.02, 0.5, "内容因素\n理性证据型\nvs\n情感共情型",
            ha="center", va="center", fontsize=9, transform=ax.transAxes,
            bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8))

    path = output_dir / "09_实验设计矩阵概览.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 10：条件品牌选择传导图
# ══════════════════════════════════════════════════════════════════════════════

def plot_choice_transmission_cn(
    run_dir: Path,
    output_dir: Path | None = None,
) -> str:
    """生成品牌信任→条件品牌选择传导关系图。"""
    cognitive = _read_csv(Path(run_dir) / "cognitive_records.csv")
    curves = _read_csv(Path(run_dir) / "choice_curves.csv")
    if not cognitive or not curves:
        raise FileNotFoundError("需要 cognitive_records.csv 和 choice_curves.csv")

    output_dir = Path(output_dir or Path(run_dir) / "figures_cn")
    by_cond = _group_by_condition(cognitive)
    strategy_ids = sorted(x for x in by_cond if x != CONTROL)

    # 计算每个策略条件相对对照组的信任差和选择差
    control_trust = _tick_mean(by_cond[CONTROL], "trust_final")
    end_tick = max(control_trust.keys())

    trust_deltas = []
    choice_deltas = []
    labels = []

    for eid in strategy_ids:
        s_trust = _tick_mean(by_cond[eid], "trust_final")
        trust_delta = _mean([
            s_trust.get(t, 0) - control_trust.get(t, 0)
            for t in range(6, end_tick + 1)
            if t in s_trust and t in control_trust
        ])
        trust_deltas.append(trust_delta)
        labels.append(_cn(eid))

    # 选择概率差
    curve_by_cond: dict[str, list[dict]] = defaultdict(list)
    for row in curves:
        curve_by_cond[str(row["exp_id"])].append(row)

    for eid in strategy_ids:
        c_rows = [r for r in curve_by_cond.get(eid, [])
                  if str(r.get("conversion_support", "")) == "absent"]
        ctrl_rows = [r for r in curve_by_cond.get(CONTROL, [])
                     if str(r.get("conversion_support", "")) == "absent"]
        if c_rows and ctrl_rows:
            c_val = _mean([float(r.get("cumulative_expected_choice_share", 0)) for r in c_rows])
            ctrl_val = _mean([float(r.get("cumulative_expected_choice_share", 0)) for r in ctrl_rows])
            choice_deltas.append(c_val - ctrl_val)
        else:
            choice_deltas.append(float("nan"))

    fig, ax = plt.subplots(figsize=FIGSIZE_SQUARE)
    ax.scatter(trust_deltas, choice_deltas, s=80, c="#D32F2F", edgecolors="black",
               linewidth=0.8, zorder=5)
    for i, label in enumerate(labels):
        ax.annotate(label, (trust_deltas[i], choice_deltas[i]),
                    fontsize=8, xytext=(5, 5), textcoords="offset points")

    # 趋势线
    valid_mask = [not math.isnan(t) and not math.isnan(c)
                  for t, c in zip(trust_deltas, choice_deltas)]
    x_valid = [t for t, m in zip(trust_deltas, valid_mask) if m]
    y_valid = [c for c, m in zip(choice_deltas, valid_mask) if m]
    if len(x_valid) >= 2:
        z = np.polyfit(x_valid, y_valid, 1)
        x_line = np.linspace(min(x_valid), max(x_valid), 50)
        ax.plot(x_line, np.polyval(z, x_line), "--", color="gray", linewidth=1,
                label=f"线性趋势 (斜率={z[0]:.4f})")
        ax.legend(loc="lower right")

    ax.axhline(0, linewidth=0.8, color="black", alpha=0.5)
    ax.axvline(0, linewidth=0.8, color="black", alpha=0.5)
    ax.set_xlabel("品牌信任差值（处理组 − 对照组均值）")
    ax.set_ylabel("条件品牌选择差值（处理组 − 对照组）")
    ax.set_title("品牌信任修复向条件品牌选择的传导关系")
    ax.grid(True, alpha=0.3, linestyle="--")

    path = output_dir / "10_信任选择传导关系.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 11：语义评价维度雷达图
# ══════════════════════════════════════════════════════════════════════════════

def plot_semantic_radar_cn(
    run_dir: Path,
    output_dir: Path | None = None,
) -> str:
    """生成消费者对不同策略条件澄清信息的语义评价雷达图。"""
    thoughts = _read_csv(Path(run_dir) / "agent_thoughts.csv")
    if not thoughts:
        raise FileNotFoundError("agent_thoughts.csv 不存在")

    output_dir = Path(output_dir or Path(run_dir) / "figures_cn")

    # 筛选接收了澄清的记录
    clar_thoughts = [
        r for r in thoughts
        if str(r.get("clarification_received", "")).lower() in ("true", "1", "yes")
    ]
    if not clar_thoughts:
        raise ValueError("没有接收澄清的记录")

    dimensions = [
        ("semantic_credibility", "可信度"),
        ("semantic_evidence_strength", "证据充分性"),
        ("semantic_perceived_empathy", "共情程度"),
        ("semantic_topic_relevance", "主题相关性"),
        ("semantic_arousal", "唤醒程度"),
    ]
    dim_keys = [d[0] for d in dimensions]
    dim_labels = [d[1] for d in dimensions]

    # 按内容因素分组计算均值
    groups = defaultdict(list)
    for r in clar_thoughts:
        content = str(r.get("content_factor", "unknown"))
        groups[content].append(r)

    content_cn = {"rational-evidence": "理性证据型", "emotional-empathy": "情感共情型"}
    content_colors = {"rational-evidence": COLORS_CONTENT["rational"],
                      "emotional-empathy": COLORS_CONTENT["empathy"]}

    angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
    angles += angles[:1]  # 闭合

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    for content_key, rows in groups.items():
        if content_key in ("not-applicable", "unknown"):
            continue
        values = []
        for key in dim_keys:
            vals = [float(r[key]) for r in rows if r.get(key, "") not in ("", None)]
            values.append(_mean(vals) if vals else 0)
        values += values[:1]
        label = content_cn.get(content_key, content_key)
        color = content_colors.get(content_key, "gray")
        ax.plot(angles, values, "o-", linewidth=2, label=label, color=color, markersize=4)
        ax.fill(angles, values, alpha=0.1, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dim_labels, fontsize=10)
    ax.set_ylim(0, 1)
    ax.set_title("消费者对企业澄清信息的语义评价\n（理性证据型 vs 情感共情型）", y=1.08)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    path = output_dir / "11_语义评价雷达图.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 12：消费者异质性面板图
# ══════════════════════════════════════════════════════════════════════════════

def plot_consumer_heterogeneity_cn(
    run_dir: Path,
    output_dir: Path | None = None,
    *,
    condition: str = "Empathy-Hub-Immediate",
) -> str:
    """生成按消费者类型分组的品牌信任恢复轨迹面板图。"""
    cognitive = _read_csv(Path(run_dir) / "cognitive_records.csv")
    if not cognitive:
        raise FileNotFoundError("cognitive_records.csv 不存在")

    output_dir = Path(output_dir or Path(run_dir) / "figures_cn")

    # 筛选指定条件
    cond_rows = [r for r in cognitive if str(r["exp_id"]) == condition]
    if not cond_rows:
        raise ValueError(f"条件 {condition} 不存在")

    # 按消费者类型分组
    cluster_cn = {
        "Active_Greens": "积极绿色型",
        "Convenient_Greens": "便利绿色型",
        "Dormant_Greens": "潜在绿色型",
        "Non_Greens": "非绿色型",
    }
    cluster_colors = {
        "Active_Greens": "#1B7837",
        "Convenient_Greens": "#7FBC41",
        "Dormant_Greens": "#FDB863",
        "Non_Greens": "#B2182B",
    }

    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for r in cond_rows:
        cluster = str(r.get("cluster_type", "Unknown"))
        by_cluster[cluster].append(r)

    clusters = [c for c in cluster_cn if c in by_cluster]
    if not clusters:
        # 回退：如果没有cluster_type列，按agent_id分组展示前4个
        clusters = sorted(set(r.get("agent_id", "") for r in cond_rows))[:4]
        is_agent_level = True
    else:
        is_agent_level = False

    n_panels = len(clusters)
    n_cols = min(2, n_panels)
    n_rows = math.ceil(n_panels / n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5.5 * n_cols, 4 * n_rows), sharex=True)
    if n_panels == 1:
        axes = np.array([axes])
    axes_flat = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for idx, cluster in enumerate(clusters):
        ax = axes_flat[idx]
        if is_agent_level:
            rows = [r for r in cond_rows if r.get("agent_id", "") == cluster]
            label = f"智能体 {cluster}"
            color = f"C{idx}"
        else:
            rows = by_cluster[cluster]
            label = cluster_cn.get(cluster, cluster)
            color = cluster_colors.get(cluster, f"C{idx}")

        series = _tick_mean(rows, "trust_final")
        ticks = sorted(series)
        values = [series[t] for t in ticks]
        ax.plot(ticks, values, "-o", markersize=2.5, linewidth=1.5, color=color)
        ax.set_title(label, fontsize=10)
        ax.set_ylabel("品牌信任")
        ax.axvline(5, linestyle="--", color="gray", linewidth=0.8)
        ax.grid(True, alpha=0.25, linestyle="--")

    for ax in axes_flat[n_panels:]:
        ax.set_visible(False)
    for ax in axes_flat[max(0, n_panels - n_cols):n_panels]:
        ax.set_xlabel("时间步（Tick）")

    fig.suptitle(
        f"不同消费者类型的品牌信任恢复轨迹\n条件：{_cn(condition)}",
        fontsize=12, y=1.02,
    )

    path = output_dir / "12_消费者异质性面板.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 13：内容×时机×投放三因素交互作用图
# ══════════════════════════════════════════════════════════════════════════════

def plot_three_factor_interaction_cn(
    run_dir: Path,
    output_dir: Path | None = None,
) -> str:
    """生成内容×时机×投放三因素的品牌信任修复交互效应图。"""
    cognitive = _read_csv(Path(run_dir) / "cognitive_records.csv")
    if not cognitive:
        raise FileNotFoundError("cognitive_records.csv 不存在")

    output_dir = Path(output_dir or Path(run_dir) / "figures_cn")
    by_cond = _group_by_condition(cognitive)
    control_trust = _tick_mean(by_cond.get(CONTROL, []), "trust_final")
    end_tick = max(control_trust.keys()) if control_trust else 35

    # 计算每条件的危机后平均信任（减去对照）
    strategy_ids = sorted(x for x in by_cond if x != CONTROL)
    condition_deltas = {}
    for eid in strategy_ids:
        s = _tick_mean(by_cond[eid], "trust_final")
        delta = _mean([
            s.get(t, 0) - control_trust.get(t, 0)
            for t in range(6, end_tick + 1)
            if t in s and t in control_trust
        ])
        condition_deltas[eid] = delta

    # 按因素拆解
    content_groups = {"rational-evidence": [], "emotional-empathy": []}
    timing_groups = {"immediate": [], "delayed": []}
    channel_groups = {"hub": [], "random": []}

    factor_map = {
        "Rational-Hub-Immediate": ("rational-evidence", "hub", "immediate"),
        "Rational-Hub-Delayed": ("rational-evidence", "hub", "delayed"),
        "Rational-Random-Immediate": ("rational-evidence", "random", "immediate"),
        "Rational-Random-Delayed": ("rational-evidence", "random", "delayed"),
        "Empathy-Hub-Immediate": ("emotional-empathy", "hub", "immediate"),
        "Empathy-Hub-Delayed": ("emotional-empathy", "hub", "delayed"),
        "Empathy-Random-Immediate": ("emotional-empathy", "random", "immediate"),
        "Empathy-Random-Delayed": ("emotional-empathy", "random", "delayed"),
    }

    for eid, delta in condition_deltas.items():
        if eid in factor_map:
            content, channel, timing = factor_map[eid]
            content_groups[content].append(delta)
            timing_groups[timing].append(delta)
            channel_groups[channel].append(delta)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))

    # 内容因素
    ax = axes[0]
    cats = ["理性证据型", "情感共情型"]
    vals = [_mean(content_groups["rational-evidence"]),
            _mean(content_groups["emotional-empathy"])]
    colors_bar = [COLORS_CONTENT["rational"], COLORS_CONTENT["empathy"]]
    bars = ax.bar(cats, vals, color=colors_bar, edgecolor="white", width=0.5)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.003,
                f"{val:.4f}", ha="center", fontsize=9)
    ax.set_ylabel("ΔTrust（处理组 − 对照组均值）")
    ax.set_title("内容因素")
    ax.axhline(0, linewidth=0.8, color="black")
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    # 时机因素
    ax = axes[1]
    cats = ["即时回应", "延迟回应"]
    vals = [_mean(timing_groups["immediate"]), _mean(timing_groups["delayed"])]
    colors_bar = [COLORS_TIMING["immediate"], COLORS_TIMING["delayed"]]
    bars = ax.bar(cats, vals, color=colors_bar, edgecolor="white", width=0.5)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.003,
                f"{val:.4f}", ha="center", fontsize=9)
    ax.set_title("时机因素")
    ax.axhline(0, linewidth=0.8, color="black")
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    # 渠道因素
    ax = axes[2]
    cats = ["核心节点", "随机节点"]
    vals = [_mean(channel_groups["hub"]), _mean(channel_groups["random"])]
    colors_bar = [COLORS_CHANNEL["hub"], COLORS_CHANNEL["random"]]
    bars = ax.bar(cats, vals, color=colors_bar, edgecolor="white", width=0.5)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.003,
                f"{val:.4f}", ha="center", fontsize=9)
    ax.set_title("渠道因素")
    ax.axhline(0, linewidth=0.8, color="black")
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    fig.suptitle("三类企业策略因素的品牌信任修复效应比较", fontsize=12, y=1.02)

    path = output_dir / "13_三因素交互效应.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 14：品牌信任机制分解（危机记忆 + 修复记忆 + 静默恢复）
# ══════════════════════════════════════════════════════════════════════════════

def plot_trust_mechanism_decomposition_cn(
    run_dir: Path,
    output_dir: Path | None = None,
    *,
    condition: str = "Empathy-Hub-Immediate",
) -> str:
    """生成品牌信任机制分解图：危机记忆、修复记忆与信任轨迹的关系。"""
    cognitive = _read_csv(Path(run_dir) / "cognitive_records.csv")
    if not cognitive:
        raise FileNotFoundError("cognitive_records.csv 不存在")

    output_dir = Path(output_dir or Path(run_dir) / "figures_cn")
    cond_rows = [r for r in cognitive if str(r["exp_id"]) == condition]
    if not cond_rows:
        raise ValueError(f"条件 {condition} 不存在")

    trust_series = _tick_mean(cond_rows, "trust_final")
    crisis_series = _tick_mean(cond_rows, "crisis_memory")
    repair_series = _tick_mean(cond_rows, "repair_memory")

    ticks = sorted(trust_series)

    fig, ax1 = plt.subplots(figsize=FIGSIZE_WIDE)

    # 品牌信任（主 Y 轴）
    line1 = ax1.plot(ticks, [trust_series[t] for t in ticks], "-o",
                     color="#2166AC", markersize=3, linewidth=2, label="品牌信任")
    ax1.set_xlabel("时间步（Tick）")
    ax1.set_ylabel("品牌信任指数", color="#2166AC")
    ax1.tick_params(axis="y", labelcolor="#2166AC")

    # 危机/修复记忆（副 Y 轴）
    ax2 = ax1.twinx()
    crisis_vals = [crisis_series.get(t, 0) for t in ticks]
    repair_vals = [repair_series.get(t, 0) for t in ticks]
    line2 = ax2.plot(ticks, crisis_vals, "--s", color="#B2182B",
                     markersize=3, linewidth=1.5, label="危机记忆")
    line3 = ax2.plot(ticks, repair_vals, "--^", color="#1B7837",
                     markersize=3, linewidth=1.5, label="修复记忆")
    ax2.set_ylabel("记忆强度", color="black")

    # 合并图例
    lines = line1 + line2 + line3
    labels_legend = [l.get_label() for l in lines]
    ax1.legend(lines, labels_legend, loc="center right")

    ax1.axvline(5, linestyle="--", color="gray", linewidth=0.8)
    ax1.text(5.2, ax1.get_ylim()[1] * 0.95, "危机发生", fontsize=8, color="gray")
    ax1.set_title(f"品牌信任机制分解：信任、危机记忆与修复记忆\n条件：{_cn(condition)}")
    ax1.grid(True, alpha=0.25, linestyle="--")
    ax1.xaxis.set_major_locator(MaxNLocator(integer=True))

    path = output_dir / "14_信任机制分解.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 15：网络拓扑类型对比图（BA / WS / SBM）
# ══════════════════════════════════════════════════════════════════════════════

def plot_topology_comparison_cn(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> str:
    """生成不同网络结构下核心节点投放触达差异对比图。

    参数 results 应为形如：
    [{"topology": "BA", "reach_delta_mean": 0.40, "reach_delta_min": 0.25,
      "reach_delta_max": 0.55}, ...]
    """
    if not results:
        raise ValueError("results 为空")

    output_dir = Path(output_dir)
    topology_cn = {"BA": "无标度网络\n(BA)", "WS": "小世界网络\n(WS)", "SBM": "社群网络\n(SBM)"}
    topology_colors = {"BA": "#2166AC", "WS": "#B2182B", "SBM": "#1B7837"}

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(results))

    for i, r in enumerate(results):
        topo = r["topology"]
        color = topology_colors.get(topo, f"C{i}")
        label = topology_cn.get(topo, topo)
        mean_val = r["reach_delta_mean"]
        err_low = mean_val - r["reach_delta_min"]
        err_high = r["reach_delta_max"] - mean_val

        ax.bar(i, mean_val, color=color, edgecolor="white", width=0.5)
        ax.errorbar(i, mean_val, yerr=[[err_low], [err_high]],
                    fmt="none", color="black", capsize=5, linewidth=1.5)
        ax.text(i, mean_val + err_high + 0.02, f"{mean_val:.2f}",
                ha="center", fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels([topology_cn.get(r["topology"], r["topology"]) for r in results])
    ax.set_ylabel("核心节点 − 随机节点的直接触达差值")
    ax.set_title("不同网络结构下企业初始投放方式的直接触达差异\n（每类5张预设网络，误差线为最小-最大值）")
    ax.axhline(0, linewidth=0.8, color="black")
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    path = output_dir / "15_网络拓扑对比.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 图表 16：主要结果参数范围总览图
# ══════════════════════════════════════════════════════════════════════════════

def plot_result_range_overview_cn(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> str:
    """生成参数空间中主要结果取值范围总览图（类似中期报告图4）。

    参数 results 应为形如：
    [{"estimand": "P1 总体澄清效应", "baseline": 0.2503,
      "range_min": 0.156, "range_max": 0.336}, ...]
    """
    if not results:
        raise ValueError("results 为空")

    output_dir = Path(output_dir)

    fig, ax = plt.subplots(figsize=(9, 5))
    y = np.arange(len(results))

    for i, r in enumerate(results):
        ax.plot([r["range_min"], r["range_max"]], [i, i],
                linewidth=3, color="#4393C3", solid_capstyle="round")
        ax.scatter([r["baseline"]], [i], s=80, color="#D32F2F",
                   edgecolors="black", linewidth=0.8, zorder=5)

    ax.set_yticks(y)
    ax.set_yticklabels([r["estimand"] for r in results])
    ax.set_xlabel("指标取值")
    ax.set_title("信任机制参数变化下主要品牌信任结果的取值范围\n（圆点=基准情形，线段=参数空间内的最小-最大值）")
    ax.axvline(0, linewidth=0.8, color="black", linestyle="--", alpha=0.5)
    ax.grid(True, axis="x", alpha=0.3, linestyle="--")
    ax.legend(
        handles=[
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#D32F2F",
                       markersize=10, markeredgecolor="black", label="基准情形"),
            plt.Line2D([0], [0], color="#4393C3", linewidth=3, label="参数空间取值范围"),
        ],
        loc="lower right",
    )

    path = output_dir / "16_结果取值范围总览.png"
    return _save(fig, path)


# ══════════════════════════════════════════════════════════════════════════════
# 统一入口：从运行目录生成全部可生成的中文图表
# ══════════════════════════════════════════════════════════════════════════════

def generate_all_run_figures_cn(
    run_dir: Path,
    output_dir: Path | None = None,
) -> dict:
    """从一次完整运行的结果目录生成所有可生成的中文学术图表。

    返回生成的图表列表和状态。
    """
    run_dir = Path(run_dir)
    output_dir = Path(output_dir or run_dir / "figures_cn")
    outputs: list[str] = []
    errors: list[str] = []

    # 逐个尝试生成
    generators = [
        ("01_品牌信任动态轨迹", lambda: plot_trust_dynamics_cn(run_dir, output_dir)),
        ("02_信任差异热力图", lambda: plot_trust_delta_heatmap_cn(run_dir, output_dir)),
        ("06_企业信息直接触达对比", lambda: plot_reach_comparison_cn(run_dir, output_dir)),
        ("10_信任选择传导关系", lambda: plot_choice_transmission_cn(run_dir, output_dir)),
        ("11_语义评价雷达图", lambda: plot_semantic_radar_cn(run_dir, output_dir)),
        ("12_消费者异质性面板", lambda: plot_consumer_heterogeneity_cn(run_dir, output_dir)),
        ("13_三因素交互效应", lambda: plot_three_factor_interaction_cn(run_dir, output_dir)),
        ("14_信任机制分解", lambda: plot_trust_mechanism_decomposition_cn(run_dir, output_dir)),
    ]

    # 如果有网络数据
    if (run_dir / "network_nodes.csv").exists():
        generators.append(
            ("05_网络拓扑与度分布", lambda: plot_network_topology_cn(run_dir, output_dir))
        )

    for name, gen_fn in generators:
        try:
            path = gen_fn()
            outputs.append(path)
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    manifest = {
        "schema_version": "thesis_figures_cn_1.0",
        "scope": "中文学术论文图表后处理",
        "run_dir": str(run_dir),
        "output_dir": str(output_dir),
        "figures_generated": len(outputs),
        "figures_failed": len(errors),
        "figures": outputs,
        "errors": errors,
        "post_processing_only": True,
        "model_rerun_performed": False,
    }

    manifest_path = output_dir / "figures_cn_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
