"""
analysis/plot_experiments.py — 三因子实验结果可视化（高区分度指标版）

核心三目标（无 censoring 问题）：
  - delta_recovery:  净信任恢复量 = Tick30 信任 - 最低点信任
  - auc_post_scandal: 丑闻后信任曲线面积（归一化），衡量整体恢复质量
  - recovery_speed:  恢复速度（信任分/天）

辅助指标：steady_state_score, recovery_rate, t50

生成图表：
  1. 三目标主效应条形图
  2. 交互效应热力图
  3. 帕累托前沿散点图
  4. 策略综合排名
  5. 澄清效果诊断图（新增）
"""
import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results", "experiments", "latest")
# OUTPUT_DIR 可由调用方在 import 后覆盖（run_experiments.py 会注入带时间戳的路径）
OUTPUT_DIR = os.path.join(RESULTS_DIR, "figures")

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

CONTENT_COLORS = {"rational-evidence": "#2166ac", "emotional-empathy": "#d6604d"}
CHANNEL_COLORS = {"hub": "#4dac26", "random": "#b8e186"}
TIMING_COLORS  = {"immediate": "#fc8d59", "delay-3": "#fdcc8a", "no-clarification": "#91bfdb"}

CONTENT_LABELS = {"rational-evidence": "Rational", "emotional-empathy": "Empathy"}
CHANNEL_LABELS = {"hub": "Hub", "random": "Random"}
TIMING_LABELS  = {"immediate": "Immediate", "delay-3": "Delay-3d", "no-clarification": "No-Clr"}


def load_data() -> pd.DataFrame:
    path = os.path.join(RESULTS_DIR, "summary.csv")
    if not os.path.exists(path):
        print(f"❌ 未找到 {path}"); sys.exit(1)
    df = pd.read_csv(path)

    # ── 兼容旧版 CSV（无新字段时，用代理指标估算）─────────────────────
    numeric_cols = ['delta_recovery', 'auc_post_scandal', 'recovery_speed',
                    'steady_state_score', 'recovery_rate', 't50', 't80',
                    'trust_min', 'baseline_trust', 'clarification_effect']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'delta_recovery' not in df.columns:
        print("⚠️  旧版 CSV 检测到：缺少 delta_recovery / auc_post_scandal / recovery_speed")
        print("    使用代理指标临时估算（请重跑 run_experiments.py 获取精确值）")
        # 代理估算：用 steady - trust_min 近似 delta_recovery
        df['delta_recovery'] = df['steady_state_score'] - df['trust_min'].fillna(df['steady_state_score'] * 0.6)
        # auc 用 steady 归一化代理
        df['auc_post_scandal'] = df['steady_state_score'] / 10.0
        # speed 用 1/t80 代理（t80=30时取0.01）
        if 't80' in df.columns:
            df['recovery_speed'] = 1.0 / df['t80'].replace(0, np.nan).fillna(30)
        else:
            df['recovery_speed'] = df['delta_recovery'] / 25.0
        if 't50' not in df.columns:
            df['t50'] = df.get('t80', 30)
        if 'clarification_effect' not in df.columns:
            df['clarification_effect'] = 0.0

    # 过滤错误行
    df = df[pd.to_numeric(df['delta_recovery'], errors='coerce').notna()].copy()

    # 标准化（归一化到 0-1，用于综合排名）
    # 注意：用 steady_state_score 替换 recovery_speed 作为第三目标，
    # 因为 recovery_speed = delta_recovery / 常数，与 delta_recovery 完全线性相关
    for col, higher_better in [
        ('delta_recovery', True), ('auc_post_scandal', True), ('steady_state_score', True)
    ]:
        r = df[col].max() - df[col].min()
        df[f'{col}_norm'] = (df[col] - df[col].min()) / (r + 1e-9) if r > 0 else 0.5

    df['composite'] = (df['delta_recovery_norm'] + df['auc_post_scandal_norm'] + df['steady_state_score_norm']) / 3.0
    return df


def _bar_group(ax, df, factor_col, metric_col, labels_map, colors_map,
               ylabel, higher_better=True, zoom=True):
    """辅助：绘制单个分组条形图，自动放大 Y 轴差异"""
    grouped = df.groupby(factor_col)[metric_col].agg(['mean', 'std'])
    levels  = list(grouped.index)
    means   = [grouped.loc[l, 'mean'] for l in levels]
    stds    = [grouped.loc[l, 'std'] for l in levels]
    bar_colors = [colors_map.get(l, '#888888') for l in levels]
    bar_labels = [labels_map.get(l, l) for l in levels]

    bars = ax.bar(bar_labels, means, color=bar_colors, alpha=0.85,
                  edgecolor='white', linewidth=1.5, yerr=stds, capsize=4)

    if zoom and max(means) != min(means):
        span = max(means) - min(means)
        # 先设置 ylim，再加标注，确保标注在可见范围内
        y_lo = min(means) - span * 1.5
        y_hi = max(means) + span * 3.0   # 留足标注空间
        ax.set_ylim(y_lo, y_hi)

    for bar, val in zip(bars, means):
        ylim = ax.get_ylim()
        span_visible = ylim[1] - ylim[0]
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + span_visible * 0.02,
                f'{val:.4f}', ha='center', va='bottom', fontsize=8)

    best_idx = means.index(max(means) if higher_better else min(means))
    bars[best_idx].set_edgecolor('#333333')
    bars[best_idx].set_linewidth(2.5)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.grid(axis='y', linestyle=':', alpha=0.4)
    ax.tick_params(axis='x', labelsize=9)


def plot_main_effects(df: pd.DataFrame):
    """图1：三核心目标 × 三因子 = 9格主效应图"""
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    fig.suptitle('Main Effects: 3 Factors × 3 Metrics (High-Discriminability)', fontsize=14, fontweight='bold')

    metrics = [
        ('delta_recovery',    'Δ Recovery (↑)',         True),
        ('auc_post_scandal',  'AUC Post-Scandal (↑)',   True),
        ('steady_state_score','Steady-State Trust (↑)', True),
    ]
    factors = [
        ('content_factor', 'Content',  CONTENT_LABELS, CONTENT_COLORS),
        ('channel_factor', 'Channel',  CHANNEL_LABELS, CHANNEL_COLORS),
        ('timing_factor',  'Timing',   TIMING_LABELS,  TIMING_COLORS),
    ]

    for col, (metric_col, metric_label, higher_better) in enumerate(metrics):
        for row, (factor_col, factor_label, labels_map, colors_map) in enumerate(factors):
            ax = axes[row][col]
            _bar_group(ax, df, factor_col, metric_col, labels_map, colors_map,
                       metric_label, higher_better)
            if row == 0:
                ax.set_title(metric_label, fontsize=11, fontweight='bold')
            if col == 0:
                ax.set_ylabel(f'{factor_label}\n{metric_label}', fontsize=9)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig1_main_effects.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✅ 图1 已保存: {out}")


def plot_heatmap_interactions(df: pd.DataFrame):
    """图2：交互效应热力图"""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('Interaction Effects Heatmap (delta_recovery)', fontsize=14, fontweight='bold')

    interactions = [
        ('content_factor', 'timing_factor',  '内容 × 时机'),
        ('channel_factor', 'timing_factor',  '渠道 × 时机'),
        ('content_factor', 'channel_factor', '内容 × 渠道'),
    ]
    label_maps = {
        'content_factor': CONTENT_LABELS, 'channel_factor': CHANNEL_LABELS,
        'timing_factor': TIMING_LABELS
    }

    for ax, (row_f, col_f, title) in zip(axes, interactions):
        pivot = df.pivot_table(index=row_f, columns=col_f, values='delta_recovery', aggfunc='mean')
        row_labels = [label_maps[row_f].get(i, i) for i in pivot.index]
        col_labels = [label_maps[col_f].get(c, c) for c in pivot.columns]

        vmin = df['delta_recovery'].min() * 0.98
        vmax = df['delta_recovery'].max() * 1.02
        im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto', vmin=vmin, vmax=vmax)
        ax.set_xticks(range(len(col_labels)))
        ax.set_xticklabels(col_labels, fontsize=9, rotation=20, ha='right')
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels, fontsize=9)
        ax.set_title(title, fontsize=11, fontweight='bold', pad=8)

        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                ax.text(j, i, f'{pivot.values[i, j]:.4f}', ha='center', va='center',
                        fontsize=10, color='black', fontweight='bold')
        plt.colorbar(im, ax=ax, shrink=0.8)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig2_interactions.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✅ 图2 已保存: {out}")


def is_pareto_dominated(row, df: pd.DataFrame) -> bool:
    """所有目标越大越好（delta_recovery, auc_post_scandal, steady_state_score）"""
    for _, other in df.iterrows():
        if other['exp_id'] == row['exp_id']:
            continue
        dominated = (
            other['delta_recovery']    >= row['delta_recovery']    and
            other['auc_post_scandal']  >= row['auc_post_scandal']  and
            other['steady_state_score'] >= row['steady_state_score'] and
            (other['delta_recovery']    > row['delta_recovery'] or
             other['auc_post_scandal']  > row['auc_post_scandal'] or
             other['steady_state_score'] > row['steady_state_score'])
        )
        if dominated:
            return True
    return False


def plot_pareto_frontier(df: pd.DataFrame):
    """图3：帕累托前沿散点图（三组二维投影）"""
    df = df.copy()
    df['is_pareto'] = ~df.apply(lambda r: is_pareto_dominated(r, df), axis=1)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('Pareto Frontier (3 Objectives: Δ Recovery / AUC / Speed)', fontsize=14, fontweight='bold')

    projections = [
        ('delta_recovery',   'auc_post_scandal',   'Δ Recovery (↑)',     'AUC Post-Scandal (↑)'),
        ('delta_recovery',   'steady_state_score', 'Δ Recovery (↑)',     'Steady-State Trust (↑)'),
        ('auc_post_scandal', 'steady_state_score', 'AUC Post-Scandal',   'Steady-State Trust (↑)'),
    ]

    for ax, (x_col, y_col, xlabel, ylabel) in zip(axes, projections):
        x_vals = df[x_col].values
        y_vals = df[y_col].values
        x_range = x_vals.max() - x_vals.min() if x_vals.max() != x_vals.min() else 1e-6
        y_range = y_vals.max() - y_vals.min() if y_vals.max() != y_vals.min() else 1e-6

        for i, (_, row) in enumerate(df.iterrows()):
            color = '#d62728' if row['is_pareto'] else '#aec7e8'
            size  = 200 if row['is_pareto'] else 80
            edge  = '#8B0000' if row['is_pareto'] else 'none'
            ax.scatter(row[x_col], row[y_col], c=color, s=size, zorder=10 if row['is_pareto'] else 5,
                       edgecolors=edge, linewidths=1.5, alpha=0.9)
            dy = y_range * 0.06 * (1 if i % 2 == 0 else -1.5)
            ax.annotate(row['exp_id'], (row[x_col], row[y_col]),
                        xytext=(row[x_col] + x_range*0.02, row[y_col] + dy),
                        fontsize=6.5, alpha=0.85, ha='left')

        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.grid(True, linestyle=':', alpha=0.4)
        ax.legend(handles=[mpatches.Patch(color='#d62728', label='Pareto Optimal'),
                            mpatches.Patch(color='#aec7e8', label='Dominated')], fontsize=9)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig3_pareto.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✅ 图3 已保存: {out}")

    pareto_df = df[df['is_pareto']].sort_values('delta_recovery', ascending=False)
    print(f"\n  🏆 Pareto最优解 ({len(pareto_df)} 个):")
    print(f"  {'exp_id':<25} {'ΔRecov':>8} {'AUC':>8} {'Speed':>8}")
    print(f"  {'─'*55}")
    for _, r in pareto_df.iterrows():
        print(f"  {r['exp_id']:<25} {r['delta_recovery']:>8.4f} {r['auc_post_scandal']:>8.4f} {r['steady_state_score']:>8.4f}")
    return df


def plot_strategy_ranking(df: pd.DataFrame):
    """图4：策略综合排名（基于三核心目标的等权综合得分）"""
    df_sorted = df.sort_values('composite', ascending=True)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_title('Strategy Composite Ranking (Equal Weight: ΔRecovery + AUC + Speed)',
                 fontsize=13, fontweight='bold')

    colors = [TIMING_COLORS.get(t, '#888') for t in df_sorted['timing_factor']]
    bars = ax.barh(df_sorted['exp_id'], df_sorted['composite'],
                   color=colors, alpha=0.85, edgecolor='white', height=0.65)
    for bar, val in zip(bars, df_sorted['composite']):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2,
                f'{val:.3f}', va='center', fontsize=9)

    ax.set_xlabel('Composite Score (0-1, higher is better)', fontsize=11)
    ax.set_xlim(0, df['composite'].max() * 1.2)
    ax.grid(axis='x', linestyle=':', alpha=0.4)
    ax.legend(handles=[mpatches.Patch(color=v, label=TIMING_LABELS[k])
                        for k, v in TIMING_COLORS.items()],
              loc='lower right', fontsize=9)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig4_ranking.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✅ 图4 已保存: {out}")


def plot_clarification_diagnosis(df: pd.DataFrame):
    """图5：澄清效果诊断图

    使用三个互补指标衡量澄清效果：
    - trust_gain_vs_control: 澄清组最终信任 vs NoClr 最终信任的净增益（直接衡量策略价值）
    - auc_post_scandal:      丑闻后恢复期信任曲线面积（衡量整体恢复质量）
    - steady_state_score:    Tick 30 最终信任水平（衡量长期恢复效果）

    注意：不用 delta_recovery（最终信任 - 最低点），因为澄清当天可能产生
    额外的负向情绪（回火效应），导致 trust_min 更低，掩盖了澄清的净正效果。
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('Clarification Effect Diagnosis: With vs Without Clarification',
                 fontsize=14, fontweight='bold')

    df_copy = df.copy()
    df_copy['has_clarification'] = df_copy['timing_factor'].apply(
        lambda x: 'With Clarification' if x != 'no-clarification' else 'No Clarification'
    )

    # 使用 trust_gain_vs_control 替代 delta_recovery 作为主指标
    metrics = [
        ('trust_gain_vs_control' if 'trust_gain_vs_control' in df.columns else 'delta_recovery',
         'Trust Gain vs Control (↑)\n(final trust − noClr final trust)', True),
        ('auc_post_scandal', 'AUC Post-Scandal (↑)', True),
        ('steady_state_score', 'Steady-State Trust (↑)', True),
    ]
    colors_clr = {'With Clarification': '#2166ac', 'No Clarification': '#d6604d'}

    for ax, (metric_col, ylabel, higher_better) in zip(axes, metrics):
        if metric_col not in df_copy.columns:
            ax.text(0.5, 0.5, f'字段 {metric_col} 不存在\n请重跑 run_experiments.py',
                    ha='center', va='center', transform=ax.transAxes)
            continue

        grouped = df_copy.groupby('has_clarification')[metric_col].agg(['mean', 'std'])
        levels  = ['With Clarification', 'No Clarification']
        means   = [grouped.loc[l, 'mean'] if l in grouped.index else 0 for l in levels]
        stds    = [grouped.loc[l, 'std']  if l in grouped.index else 0 for l in levels]
        bar_colors = [colors_clr[l] for l in levels]

        bars = ax.bar(levels, means, color=bar_colors, alpha=0.85, edgecolor='white',
                      linewidth=1.5, yerr=stds, capsize=6, width=0.45)

        if ax.get_ylim()[1] > 0:
            for bar, val in zip(bars, means):
                ax.text(bar.get_x() + bar.get_width()/2,
                        bar.get_height() + max(abs(s) for s in stds) * 0.15,
                        f'{val:.4f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

        diff = means[0] - means[1]
        sign = "↑" if diff > 0 else "↓"
        ax.set_title(f'{ylabel.split(chr(10))[0]}\nDiff: {diff:+.4f} {sign}', fontsize=11)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(axis='y', linestyle=':', alpha=0.4)
        span = max(means) - min(means) if max(means) != min(means) else 0.01
        ax.set_ylim(min(means) - span*1.5, max(means) + span*3)
        ax.tick_params(axis='x', labelsize=10)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig5_clarification_diagnosis.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✅ 图5 已保存: {out}")


def print_summary_table(df: pd.DataFrame):
    """终端打印结果汇总（新三目标）"""
    print(f"\n{'═'*90}")
    print("📊 实验结果汇总（核心三目标 — 无 censoring）")
    print(f"{'═'*90}")
    print(f"{'Strategy':<25} {'Content':<10} {'Channel':<8} {'Timing':<10} "
          f"{'ΔRecov':>8} {'AUC':>8} {'Speed':>8} {'Steady':>8}")
    print(f"{'─'*85}")

    df_sorted = df.sort_values('delta_recovery', ascending=False)
    for _, r in df_sorted.iterrows():
        print(f"{r['exp_id']:<25} "
              f"{CONTENT_LABELS.get(r['content_factor'], r['content_factor']):<10} "
              f"{CHANNEL_LABELS.get(r['channel_factor'], r['channel_factor']):<8} "
              f"{TIMING_LABELS.get(r['timing_factor'], r['timing_factor']):<10} "
              f"{r['delta_recovery']:>8.4f} {r['auc_post_scandal']:>8.4f} "
              f"{r['recovery_speed']:>8.4f} {r['steady_state_score']:>8.3f}")
    print(f"{'─'*85}")

    # 澄清效果摘要
    with_clr = df[df['timing_factor'] != 'no-clarification']
    no_clr   = df[df['timing_factor'] == 'no-clarification']
    print(f"\n📌 澄清效果摘要 (With Clarification vs No Clarification):")
    for col, label in [('delta_recovery','ΔRecovery'), ('auc_post_scandal','AUC'), ('steady_state_score','Steady')]:
        diff = with_clr[col].mean() - no_clr[col].mean()
        print(f"   {label:>15}: with={with_clr[col].mean():.4f} | no={no_clr[col].mean():.4f} | Δ={diff:+.4f}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"📂 读取数据: {os.path.join(RESULTS_DIR, 'summary.csv')}")
    df = load_data()
    print(f"   共 {len(df)} 组实验结果")

    print_summary_table(df)

    print(f"\n🎨 生成图表...")
    plot_main_effects(df)
    plot_heatmap_interactions(df)
    df = plot_pareto_frontier(df)
    plot_strategy_ranking(df)
    plot_clarification_diagnosis(df)

    print(f"\n✅ 全部图表已保存至: {OUTPUT_DIR}")
    print(f"   fig1 — 三目标主效应（高区分度）")
    print(f"   fig2 — 交互效应热力图")
    print(f"   fig3 — 帕累托前沿")
    print(f"   fig4 — 综合排名")
    print(f"   fig5 — 澄清效果诊断（有/无澄清对比）")


if __name__ == "__main__":
    main()
