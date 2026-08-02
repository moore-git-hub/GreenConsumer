"""
analysis/plot_experiments.py - TASK_003 v3.0 experiment result visualizations.

Core objectives:
  - Δ Recovery
  - AUC Post-Scandal
  - Steady-State Trust

Generated figures:
  1. Main effects for the three objectives
  2. Interaction heatmaps
  3. Pareto frontier
  4. Strategy composite ranking
  5. Clarification effect diagnosis
"""
import os
import sys
import json
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
TIMING_COLORS  = {"immediate": "#fc8d59", "delayed": "#fdcc8a"}

CONTENT_LABELS = {"rational-evidence": "Rational", "emotional-empathy": "Empathy"}
CHANNEL_LABELS = {"hub": "Hub", "random": "Random"}
TIMING_LABELS  = {"immediate": "Immediate", "delayed": "Delayed"}

CONTROL_EXP_ID = "NoClarification-Control"


def _parse_is_control_value(value) -> bool:
    """Parse explicit bool values only; reject empty/ERROR/unknown tokens."""
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str):
        if value == "True":
            return True
        if value == "False":
            return False
    raise AssertionError(f"invalid is_control value: {value!r}")


def _with_control_flags(df: pd.DataFrame) -> pd.DataFrame:
    if "is_control" not in df.columns:
        raise AssertionError("summary.csv must contain is_control")
    rows = df.copy()
    rows["_is_control_bool"] = rows["is_control"].map(_parse_is_control_value)
    return rows


def _strategy_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return strategy rows only; fail if not-applicable leaks into strategies."""
    checked = _with_control_flags(df)
    rows = checked[~checked["_is_control_bool"]].copy()
    if len(rows) != 8:
        raise AssertionError(f"expected 8 strategy rows, found {len(rows)}")
    for col in ("content_factor", "channel_factor"):
        if "not-applicable" in set(rows[col]):
            raise AssertionError(
                "'not-applicable' leaked into strategy rows via %s: is_control filter failed"
                % col
            )
    return rows.drop(columns=["_is_control_bool"], errors="ignore")


def _control_row(df: pd.DataFrame) -> pd.Series:
    checked = _with_control_flags(df)
    controls = checked[checked["_is_control_bool"]].copy()
    if len(controls) != 1:
        raise AssertionError(f"expected 1 common control row, found {len(controls)}")
    row = controls.iloc[0]
    if row.get("exp_id") != CONTROL_EXP_ID:
        raise AssertionError(f"common control exp_id must be {CONTROL_EXP_ID}")
    expected = {
        "content_factor": "not-applicable",
        "channel_factor": "not-applicable",
        "timing_factor": "no-clarification",
    }
    for col, expected_value in expected.items():
        if row.get(col) != expected_value:
            raise AssertionError(
                f"common control {col} must be {expected_value}, got {row.get(col)!r}"
            )
    return row.drop(labels=["_is_control_bool"], errors="ignore")


def _assert_v3_metadata() -> None:
    metadata_path = os.path.join(RESULTS_DIR, "run_metadata.json")
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"run_metadata.json is required: {metadata_path}")
    with open(metadata_path, encoding="utf-8") as f:
        meta = json.load(f)
    matrix = meta.get("experiment_matrix", {})
    if matrix.get("matrix_version") != "3.0" or matrix.get("condition_count") != 9:
        raise ValueError("legacy experiment_matrix metadata cannot be analyzed as v3.0")


def load_data() -> pd.DataFrame:
    path = os.path.join(RESULTS_DIR, "summary.csv")
    _assert_v3_metadata()
    if not os.path.exists(path):
        raise FileNotFoundError(f"summary.csv is required: {path}")

    df = pd.read_csv(path)
    required_cols = [
        "exp_id",
        "content_factor",
        "channel_factor",
        "timing_factor",
        "is_control",
        "delta_recovery",
        "auc_post_scandal",
        "steady_state_score",
        "trust_gain_vs_control",
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise AssertionError(f"summary.csv missing required columns: {missing}")

    checked = _with_control_flags(df)
    metric_cols = [
        "delta_recovery",
        "auc_post_scandal",
        "steady_state_score",
        "trust_gain_vs_control",
    ]
    for col in metric_cols:
        try:
            checked[col] = pd.to_numeric(checked[col], errors="raise")
        except Exception as e:
            raise AssertionError(f"summary.csv column {col} must be numeric") from e

    strategy = checked[~checked["_is_control_bool"]]
    for col in metric_cols:
        values = strategy[col].to_numpy(dtype=float)
        if strategy[col].isna().any() or not np.isfinite(values).all():
            raise AssertionError(f"strategy rows contain invalid numeric values in {col}")

    control = checked[checked["_is_control_bool"]]
    for col in ("auc_post_scandal", "steady_state_score", "trust_gain_vs_control"):
        values = control[col].to_numpy(dtype=float)
        if control[col].isna().any() or not np.isfinite(values).all():
            raise AssertionError(f"control row contains invalid numeric values in {col}")

    checked = checked.drop(columns=["_is_control_bool"], errors="ignore")
    _strategy_rows(checked)
    _control_row(checked)
    return checked

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
    df = _rankable_strategy_rows(df)
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
    df = _rankable_strategy_rows(df)
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


def _rankable_strategy_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows = _strategy_rows(df)
    for col in ('delta_recovery', 'auc_post_scandal', 'steady_state_score'):
        r = rows[col].max() - rows[col].min()
        rows[f'{col}_norm'] = (rows[col] - rows[col].min()) / (r + 1e-9) if r > 0 else 0.5
    rows['composite'] = (
        rows['delta_recovery_norm'] + rows['auc_post_scandal_norm'] + rows['steady_state_score_norm']
    ) / 3.0
    return rows


def plot_pareto_frontier(df: pd.DataFrame):
    """Plot the Pareto frontier for the 8 clarification strategies."""
    original_df = df
    df = _rankable_strategy_rows(df)
    df['is_pareto'] = ~df.apply(lambda r: is_pareto_dominated(r, df), axis=1)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('Pareto Frontier (3 Objectives: Δ Recovery / AUC Post-Scandal / Steady-State Trust)', fontsize=14, fontweight='bold')

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
    print(f"  saved fig3: {out}")

    pareto_df = df[df['is_pareto']].sort_values('delta_recovery', ascending=False)
    print(f"\n  Pareto optimal ({len(pareto_df)}):")
    print(f"  {'exp_id':<25} {'Δ Recovery':>12} {'AUC Post-Scandal':>17} {'Steady-State Trust':>18}")
    print(f"  {'-'*55}")
    for _, r in pareto_df.iterrows():
        print(f"  {r['exp_id']:<25} {r['delta_recovery']:>12.4f} {r['auc_post_scandal']:>17.4f} {r['steady_state_score']:>18.4f}")
    return original_df


def plot_strategy_ranking(df: pd.DataFrame):
    """Plot the composite ranking for the 8 clarification strategies."""
    df = _rankable_strategy_rows(df)
    df_sorted = df.sort_values('composite', ascending=True)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_title('Strategy Composite Ranking (Equal Weight: Δ Recovery + AUC Post-Scandal + Steady-State Trust)',
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
    print(f"  saved fig4: {out}")


def plot_clarification_diagnosis(df: pd.DataFrame):
    """Plot clarification effects against the common control."""
    strategy = _strategy_rows(df)
    control = _control_row(df)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('Clarification Effect Diagnosis: Strategies vs Common Control',
                 fontsize=14, fontweight='bold')

    metrics = [
        ('trust_gain_vs_control', 'Trust Gain vs Control (↑)', 0.0),
        ('auc_post_scandal', 'AUC Post-Scandal (↑)', float(control['auc_post_scandal'])),
        ('steady_state_score', 'Steady-State Trust (↑)', float(control['steady_state_score'])),
    ]
    levels = ['Strategies', 'Common Control']
    colors_clr = ['#2166ac', '#d6604d']

    for ax, (metric_col, ylabel, control_value) in zip(axes, metrics):
        if metric_col not in strategy.columns:
            raise AssertionError(f"summary.csv must contain {metric_col}")
        values = pd.to_numeric(strategy[metric_col], errors='raise')
        strategy_mean = float(values.mean())
        strategy_std = float(values.std()) if len(values) > 1 else 0.0
        means = [strategy_mean, control_value]
        stds = [strategy_std, 0.0]

        bars = ax.bar(levels, means, color=colors_clr, alpha=0.85, edgecolor='white',
                      linewidth=1.5, yerr=stds, capsize=6, width=0.45)
        span = max(means) - min(means) if max(means) != min(means) else 0.01
        ax.set_ylim(min(means) - span*1.5, max(means) + span*3)
        for bar, val in zip(bars, means):
            ylim = ax.get_ylim()
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + (ylim[1] - ylim[0]) * 0.02,
                    f'{val:.4f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

        diff = means[0] - means[1]
        sign = "↑" if diff > 0 else ("↓" if diff < 0 else "=")
        ax.set_title(f'{ylabel}\nDiff: {diff:+.4f} {sign}', fontsize=11)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(axis='y', linestyle=':', alpha=0.4)
        ax.tick_params(axis='x', labelsize=10)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "fig5_clarification_diagnosis.png")
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  saved fig5: {out}")

def print_summary_table(df: pd.DataFrame):
    """Print the three-objective TASK_003 summary table."""
    print(f"\n{'='*100}")
    print("Experiment Summary: Δ Recovery / AUC Post-Scandal / Steady-State Trust")
    print(f"{'='*100}")
    print(f"{'Strategy':<25} {'Content':<10} {'Channel':<8} {'Timing':<10} "
          f"{'Δ Recovery':>12} {'AUC Post-Scandal':>17} {'Steady-State Trust':>18}")
    print(f"{'-'*100}")

    df_sorted = df.sort_values('delta_recovery', ascending=False)
    for _, r in df_sorted.iterrows():
        print(f"{r['exp_id']:<25} "
              f"{CONTENT_LABELS.get(r['content_factor'], r['content_factor']):<10} "
              f"{CHANNEL_LABELS.get(r['channel_factor'], r['channel_factor']):<8} "
              f"{TIMING_LABELS.get(r['timing_factor'], r['timing_factor']):<10} "
              f"{r['delta_recovery']:>12.4f} {r['auc_post_scandal']:>17.4f} "
              f"{r['steady_state_score']:>18.3f}")
    print(f"{'-'*100}")

    strategy = _strategy_rows(df)
    control = _control_row(df)
    print("\nClarification effect summary: Strategies vs Common Control")
    comparisons = [
        ('trust_gain_vs_control', 'Trust Gain vs Control', 0.0),
        ('auc_post_scandal', 'AUC Post-Scandal', float(control['auc_post_scandal'])),
        ('steady_state_score', 'Steady-State Trust', float(control['steady_state_score'])),
    ]
    for col, label, control_value in comparisons:
        strategy_mean = strategy[col].mean()
        diff = strategy_mean - control_value
        print(f"   {label:>22}: strategies={strategy_mean:.4f} | control={control_value:.4f} | Δ={diff:+.4f}")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"📂 读取数据: {os.path.join(RESULTS_DIR, 'summary.csv')}")
    _assert_v3_metadata()
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
