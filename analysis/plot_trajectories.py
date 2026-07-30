"""
analysis/plot_trajectories.py — 实验策略对比折线图

读取 results/experiments/trajectories.csv，生成：
  1. 按时机因子分组——12条信任轨迹对比（核心论文图）
  2. 内容因子对比（理性证据 vs 情感共情）
  3. 渠道因子对比（Hub vs Random）
  4. 时机因子对比（即时/延迟3天/不澄清）
  5. 全部12条轨迹的综合面板图

用法：
    python analysis/plot_trajectories.py

"""
import os, sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results", "experiments", "latest")
# OUTPUT_DIR 可由调用方在 import 后覆盖（run_experiments.py 会注入带时间戳的路径）
OUTPUT_DIR  = os.path.join(RESULTS_DIR, "figures")

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# ── 配色方案 ─────────────────────────────────────────────────────────
TIMING_STYLE = {
    "immediate":        {"color": "#d62728", "ls": "-",  "lw": 2.5, "label": "即时澄清"},
    "delay-3":          {"color": "#ff7f0e", "ls": "--", "lw": 2.2, "label": "延迟3天"},
    "no-clarification": {"color": "#1f77b4", "ls": ":",  "lw": 2.0, "label": "不澄清（对照）"},
}
CONTENT_STYLE = {
    "rational-evidence": {"color": "#2166ac", "ls": "-",  "lw": 2.5, "label": "理性证据型"},
    "emotional-empathy": {"color": "#d6604d", "ls": "--", "lw": 2.5, "label": "情感共情型"},
}
CHANNEL_STYLE = {
    "hub":    {"color": "#4dac26", "ls": "-",  "lw": 2.5, "label": "Hub投放"},
    "random": {"color": "#984ea3", "ls": "--", "lw": 2.2, "label": "随机投放"},
}

EVENTS = {1: "Launch", 5: "黑石\nBlackstone", 10: "健康争议\nHealth", 15: "做空+IPO\nSpruce"}
EVENT_TICKS = list(EVENTS.keys())


def load_trajectories() -> pd.DataFrame:
    path = os.path.join(RESULTS_DIR, "trajectories.csv")
    if not os.path.exists(path):
        print(f"❌ 未找到 trajectories.csv")
        print(f"   请先重新运行 run_experiments.py 以生成轨迹数据")
        sys.exit(1)
    df = pd.read_csv(path)
    print(f"✅ 读取轨迹数据: {len(df)} 行，{df['exp_id'].nunique()} 组实验")
    return df


def _add_events(ax, max_tick: int, y_range: tuple):
    """在图上标注事件时间点"""
    ymin, ymax = y_range
    for t, label in EVENTS.items():
        if t <= max_tick:
            ax.axvline(x=t, color='gray', linestyle='--', alpha=0.45, linewidth=1.0)
            ax.text(t + 0.2, ymin + (ymax - ymin) * 0.02, label,
                    fontsize=7, color='dimgray', rotation=90, va='bottom', ha='left')


def _add_clarification_band(ax, timing: str, scandal_tick: int = 5):
    """标注澄清注入时间点"""
    clr_tick = {"immediate": scandal_tick, "delay-3": scandal_tick + 3}.get(timing)
    if clr_tick:
        ax.axvline(x=clr_tick, color='green', linestyle='-', alpha=0.6, linewidth=1.5)
        ax.text(clr_tick + 0.2, ax.get_ylim()[1] * 0.92, "↓澄清",
                fontsize=7, color='green', va='top')


def plot_timing_comparison(df: pd.DataFrame):
    """图1：时机因子主效应对比（核心论文图）——平均跨内容和渠道"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('时机因子主效应：澄清时机对信任演化与转化率的影响',
                 fontsize=13, fontweight='bold')

    ticks = sorted(df['tick'].unique())
    max_tick = max(ticks)

    for col, (metric, ylabel, title) in enumerate([
        ('avg_trust',       '平均信任分 (0-10)', '(A) 信任轨迹对比'),
        ('conversion_rate', '累计转化率',         '(B) 转化率轨迹对比'),
    ]):
        ax = axes[col]
        for timing, style in TIMING_STYLE.items():
            raw   = df[df['timing_factor'] == timing].groupby('tick')[metric].mean()
            # 3点移动平均使曲线更清晰（保留原始置信带）
            smooth = raw.rolling(window=3, center=True, min_periods=1).mean()
            std   = df[df['timing_factor'] == timing].groupby('tick')[metric].std().fillna(0)
            ax.plot(smooth.index, smooth.values,
                    color=style['color'], linestyle=style['ls'],
                    linewidth=style['lw'], label=style['label'], zorder=5)
            ax.fill_between(raw.index,
                            raw.values - std.values,
                            raw.values + std.values,
                            color=style['color'], alpha=0.12)

        y_range = (ax.get_ylim()[0] if ax.get_ylim()[0] != 0 else 0,
                   ax.get_ylim()[1] if ax.get_ylim()[1] != 1 else 1)
        _add_events(ax, max_tick, y_range)
        ax.set_xlabel('仿真周期 (Tick)', fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.legend(fontsize=10, loc='best')
        ax.grid(True, linestyle=':', alpha=0.4)
        ax.set_xlim(1, max_tick)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "line_timing_effect.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✅ 图1 时机效应: {out}")


def plot_content_channel_comparison(df: pd.DataFrame):
    """图2：内容×渠道因子效应对比（2×2格）
    
    只使用有澄清的条件（immediate + delay-3）计算内容/渠道主效应，
    并额外叠加 NoClr 对照组参考线，便于直观对比策略效果。
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('内容与渠道因子效应对比', fontsize=13, fontweight='bold')

    max_tick = df['tick'].max()
    # 只取有澄清的数据计算内容/渠道主效应
    df_clr = df[df['timing_factor'] != 'no-clarification']
    # NoClr 对照组（所有4个NoClr平均，作为基线参考）
    df_noclr = df[df['timing_factor'] == 'no-clarification']

    comparisons = [
        (axes[0, 0], 'content_factor', CONTENT_STYLE, 'avg_trust',       '(A) 内容因子 → 信任轨迹'),
        (axes[0, 1], 'content_factor', CONTENT_STYLE, 'conversion_rate', '(B) 内容因子 → 转化率'),
        (axes[1, 0], 'channel_factor', CHANNEL_STYLE,  'avg_trust',       '(C) 渠道因子 → 信任轨迹'),
        (axes[1, 1], 'channel_factor', CHANNEL_STYLE,  'conversion_rate', '(D) 渠道因子 → 转化率'),
    ]

    for ax, factor_col, style_map, metric, title in comparisons:
        # ── 对照组参考线 ──────────────────────────────────────────────
        noclr_raw  = df_noclr.groupby('tick')[metric].mean()
        noclr_smooth = noclr_raw.rolling(window=3, center=True, min_periods=1).mean()
        noclr_std  = df_noclr.groupby('tick')[metric].std().fillna(0)
        ax.plot(noclr_smooth.index, noclr_smooth.values,
                color='#888888', linestyle=':', linewidth=1.8,
                label='不澄清（对照）', zorder=4)
        ax.fill_between(noclr_raw.index,
                        noclr_raw.values - noclr_std.values,
                        noclr_raw.values + noclr_std.values,
                        color='#888888', alpha=0.08)

        # ── 各因子水平（仅澄清组）────────────────────────────────────
        for level, style in style_map.items():
            raw   = df_clr[df_clr[factor_col] == level].groupby('tick')[metric].mean()
            smooth = raw.rolling(window=3, center=True, min_periods=1).mean()
            std   = df_clr[df_clr[factor_col] == level].groupby('tick')[metric].std().fillna(0)
            ax.plot(smooth.index, smooth.values,
                    color=style['color'], linestyle=style['ls'],
                    linewidth=style['lw'], label=style['label'], zorder=5)
            ax.fill_between(raw.index,
                            raw.values - std.values,
                            raw.values + std.values,
                            color=style['color'], alpha=0.12)

        ylim = ax.get_ylim()
        _add_events(ax, max_tick, ylim if ylim != (0.0, 1.0) else (0, 1))
        ax.set_xlabel('Tick', fontsize=10)
        ax.set_ylabel('平均信任 / 转化率', fontsize=10)
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(True, linestyle=':', alpha=0.4)
        ax.set_xlim(1, max_tick)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "line_content_channel.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✅ 图2 内容×渠道效应: {out}")


def plot_all_12_strategies(df: pd.DataFrame):
    """图3：全部12条信任轨迹面板图（按时机分3列，内容×渠道分4行）"""
    timing_levels  = ["immediate", "delay-3", "no-clarification"]
    strategy_grid  = [
        ("rational-evidence", "hub"),
        ("rational-evidence", "random"),
        ("emotional-empathy", "hub"),
        ("emotional-empathy", "random"),
    ]
    row_labels = ["理性-Hub", "理性-Random", "情感-Hub", "情感-Random"]
    col_labels = ["即时澄清", "延迟3天", "不澄清（对照）"]

    fig, axes = plt.subplots(4, 3, figsize=(16, 14), sharey=True, sharex=True)
    fig.suptitle('全部12组策略信任轨迹对比面板', fontsize=14, fontweight='bold', y=0.99)
    max_tick = df['tick'].max()

    for row, (content, channel) in enumerate(strategy_grid):
        for col, timing in enumerate(timing_levels):
            ax = axes[row][col]
            mask = ((df['content_factor'] == content) &
                    (df['channel_factor'] == channel) &
                    (df['timing_factor']  == timing))
            sub = df[mask].groupby('tick')['avg_trust'].mean()

            # 对照组（不澄清）的相同内容×渠道组合作为灰色背景参考线
            no_clr_mask = ((df['content_factor'] == content) &
                           (df['channel_factor'] == channel) &
                           (df['timing_factor']  == 'no-clarification'))
            baseline = df[no_clr_mask].groupby('tick')['avg_trust'].mean()

            if not baseline.empty and timing != 'no-clarification':
                ax.plot(baseline.index, baseline.values,
                        color='#bbbbbb', linewidth=1.2, linestyle=':', zorder=3, label='对照（不澄清）')

            color = TIMING_STYLE[timing]['color']
            ax.plot(sub.index, sub.values,
                    color=color, linewidth=2.2, linestyle='-', zorder=5)

            for t in EVENT_TICKS:
                if t <= max_tick:
                    ax.axvline(x=t, color='gray', linestyle='--', alpha=0.35, linewidth=0.8)

            # 标注澄清注入时间点
            clr_tick = {"immediate": 5, "delay-3": 8}.get(timing)
            if clr_tick:
                ax.axvline(x=clr_tick, color='green', linestyle='-', alpha=0.7, linewidth=1.5)

            ax.set_ylim(0, 10)
            ax.grid(True, linestyle=':', alpha=0.3)
            ax.set_xlim(1, max_tick)

            if row == 0:
                ax.set_title(col_labels[col], fontsize=10, fontweight='bold',
                             color=TIMING_STYLE[timing]['color'])
            if col == 0:
                ax.set_ylabel(f"{row_labels[row]}\n平均信任", fontsize=9)
            if row == 3:
                ax.set_xlabel("Tick", fontsize=9)

    # 公共图例
    legend_elements = [
        Line2D([0], [0], color='#bbbbbb', linestyle=':', linewidth=1.2, label='对照（不澄清）'),
        Line2D([0], [0], color='green',   linestyle='-', linewidth=1.5, label='↓ 澄清注入'),
        Line2D([0], [0], color='gray',    linestyle='--', linewidth=0.8, label='事件时间点'),
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=3,
               fontsize=9, bbox_to_anchor=(0.5, -0.01))

    plt.tight_layout(rect=[0, 0.03, 1, 0.98])
    out = os.path.join(OUTPUT_DIR, "line_all_12_strategies.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✅ 图3 全策略面板: {out}")


def plot_trust_recovery_zoom(df: pd.DataFrame):
    """图4：以丑闻（Tick 5）为原点的信任恢复放大图——只看丑闻后"""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title('丑闻后信任恢复轨迹对比（Tick 5 = 黑石漂绿丑闻爆发）',
                 fontsize=12, fontweight='bold')

    scandal_tick = 5
    df_post = df[df['tick'] >= scandal_tick].copy()
    df_post['relative_tick'] = df_post['tick'] - scandal_tick

    # 按时机分三组，每组平均化
    timing_order = ["no-clarification", "delay-3", "immediate"]
    for timing in timing_order:
        style = TIMING_STYLE[timing]
        group = df_post[df_post['timing_factor'] == timing].groupby('relative_tick')['avg_trust'].mean()
        std   = df_post[df_post['timing_factor'] == timing].groupby('relative_tick')['avg_trust'].std().fillna(0)
        ax.plot(group.index, group.values,
                color=style['color'], linestyle=style['ls'],
                linewidth=style['lw'], label=style['label'], zorder=5)
        ax.fill_between(group.index,
                        group.values - std.values,
                        group.values + std.values,
                        color=style['color'], alpha=0.12)

        # 标注澄清注入
        clr_relative = {"immediate": 0, "delay-3": 3}.get(timing)
        if clr_relative is not None:
            ax.axvline(x=clr_relative, color=style['color'], linestyle='-',
                       alpha=0.5, linewidth=1.0)
            ax.text(clr_relative + 0.2, ax.get_ylim()[0] + 0.3 if ax.get_ylim()[0] > 0 else 0.3,
                    "↑澄清", fontsize=8, color=style['color'])

    ax.axvline(x=0, color='#8B0000', linestyle='-', linewidth=2, alpha=0.8, zorder=10)
    ax.text(0.2, ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] > 0 else 9.5,
            "丑闻爆发", fontsize=9, color='#8B0000', fontweight='bold')

    # 后续事件（相对时间）
    for t, label in {5: "健康争议\n(+5)", 10: "做空报告\n(+10)"}.items():
        if t <= df_post['relative_tick'].max():
            ax.axvline(x=t, color='gray', linestyle='--', alpha=0.4, linewidth=1.0)
            ax.text(t + 0.2, 1.0, label, fontsize=7, color='gray', rotation=90, va='bottom')

    ax.set_xlabel('距丑闻爆发天数 (Days After Scandal)', fontsize=11)
    ax.set_ylabel('平均信任分 (0-10)', fontsize=11)
    ax.legend(fontsize=10, loc='best')
    ax.grid(True, linestyle=':', alpha=0.4)
    ax.set_xlim(0, df_post['relative_tick'].max())

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "line_recovery_zoom.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✅ 图4 恢复放大图: {out}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = load_trajectories()

    print(f"\n🎨 开始生成折线图...")
    plot_timing_comparison(df)
    plot_content_channel_comparison(df)
    plot_all_12_strategies(df)
    plot_trust_recovery_zoom(df)

    print(f"\n✅ 全部折线图已保存至: {OUTPUT_DIR}")
    print(f"   - line_timing_effect.png      ← 时机因子主效应（核心图）")
    print(f"   - line_content_channel.png    ← 内容×渠道效应")
    print(f"   - line_all_12_strategies.png  ← 12组策略全面板")
    print(f"   - line_recovery_zoom.png      ← 丑闻后恢复放大图")
    print(f"\n⚠️  注意：如果图表数据缺失，请先运行 python run_experiments.py 重新生成轨迹数据")


if __name__ == "__main__":
    main()
