"""
plot_action_composition.py — 不同人群的动作组成分析

绘制各消费者类型在整个仿真期间的 BUY / POST / IGNORE 动作占比，
以堆叠柱状图展示不同人群的行为差异。
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import glob

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# 学术配色
COLORS = {
    'BUY':    '#2ca02c',   # 绿色
    'POST':   '#d62728',   # 红色
    'IGNORE': '#aec7e8',   # 浅蓝灰
}

CLUSTER_ORDER = ['Active_Greens', 'Convenient_Greens', 'Dormant_Greens', 'Non_Greens']
CLUSTER_LABELS = {
    'Active_Greens':     'Active\n(积极派)',
    'Convenient_Greens': 'Convenient\n(便利派)',
    'Dormant_Greens':    'Dormant\n(沉睡派)',
    'Non_Greens':        'Non-Greens\n(非环保派)',
}


def plot_action_composition():
    """绘制不同人群的动作组成图"""
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    sim_files = glob.glob(os.path.join(results_dir, 'simulation_log_*.csv'))

    if not sim_files:
        print("❌ 未找到 simulation_log 文件，请先运行 run_simulation.py")
        return

    latest_file = max(sim_files, key=os.path.getctime)
    print(f"📊 正在分析动作组成: {os.path.basename(latest_file)}")

    df = pd.read_csv(latest_file)

    # 解析 Action 字段（兼容 BUY+POST 组合动作）
    df['HasBuy']  = df['Action'].astype(str).str.contains('BUY')
    df['HasPost'] = df['Action'].astype(str).str.contains('POST')
    df['IsIgnore'] = (~df['HasBuy']) & (~df['HasPost'])

    # ══════════════════════════════════════════════════════════════════
    # 图 1：各人群的总体动作占比（堆叠柱状图）
    # ══════════════════════════════════════════════════════════════════
    action_counts = df.groupby('Type').agg(
        BUY=('HasBuy', 'sum'),
        POST=('HasPost', 'sum'),
        IGNORE=('IsIgnore', 'sum'),
    )

    # 按预定义顺序排列
    available_clusters = [c for c in CLUSTER_ORDER if c in action_counts.index]
    action_counts = action_counts.loc[available_clusters]

    # 转为百分比
    action_pct = action_counts.div(action_counts.sum(axis=1), axis=0) * 100

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Action Composition by Consumer Segment', fontsize=16, fontweight='bold', y=0.98)

    # 子图 1：百分比堆叠柱状图
    ax1 = axes[0]
    x = np.arange(len(available_clusters))
    width = 0.6

    bottom = np.zeros(len(available_clusters))
    for action in ['BUY', 'POST', 'IGNORE']:
        values = action_pct[action].values
        ax1.bar(x, values, width, bottom=bottom, label=action, color=COLORS[action], alpha=0.85)
        # 在每段中间标注百分比
        for i, (v, b) in enumerate(zip(values, bottom)):
            if v > 5:  # 只标注占比 > 5% 的
                ax1.text(i, b + v/2, f'{v:.0f}%', ha='center', va='center', fontsize=9, fontweight='bold')
        bottom += values

    ax1.set_xticks(x)
    ax1.set_xticklabels([CLUSTER_LABELS.get(c, c) for c in available_clusters], fontsize=10)
    ax1.set_ylabel('Action Proportion (%)', fontsize=12)
    ax1.set_ylim(0, 100)
    ax1.set_title('(A) Overall Action Proportion', fontsize=13)
    ax1.legend(loc='upper right', fontsize=10)
    ax1.grid(axis='y', linestyle=':', alpha=0.4)

    # 子图 2：绝对数量分组柱状图
    ax2 = axes[1]
    bar_width = 0.25
    x2 = np.arange(len(available_clusters))

    for i, action in enumerate(['BUY', 'POST', 'IGNORE']):
        values = action_counts[action].values
        bars = ax2.bar(x2 + i * bar_width, values, bar_width,
                       label=action, color=COLORS[action], alpha=0.85)
        # 标注数值
        for bar, v in zip(bars, values):
            if v > 0:
                ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                         str(int(v)), ha='center', va='bottom', fontsize=8)

    ax2.set_xticks(x2 + bar_width)
    ax2.set_xticklabels([CLUSTER_LABELS.get(c, c) for c in available_clusters], fontsize=10)
    ax2.set_ylabel('Action Count (across all Ticks)', fontsize=12)
    ax2.set_title('(B) Absolute Action Counts', fontsize=13)
    ax2.legend(loc='upper right', fontsize=10)
    ax2.grid(axis='y', linestyle=':', alpha=0.4)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    img_path = latest_file.replace(".csv", "_action_composition.png")
    plt.savefig(img_path, dpi=300)
    print(f"🖼️ 动作组成图已保存: {img_path}")

    # ══════════════════════════════════════════════════════════════════
    # 图 2：动作组成随时间变化（面积图）
    # ══════════════════════════════════════════════════════════════════
    fig2, axes2 = plt.subplots(2, 2, figsize=(14, 10))
    fig2.suptitle('Action Composition Over Time by Segment', fontsize=16, fontweight='bold', y=0.98)

    events = {1: 'Launch', 5: 'Scandal', 10: 'Health'}

    for idx, cluster in enumerate(available_clusters):
        ax = axes2[idx // 2, idx % 2]
        cluster_df = df[df['Type'] == cluster]

        # 按 Tick 统计各动作数量
        tick_actions = cluster_df.groupby('Tick').agg(
            BUY=('HasBuy', 'sum'),
            POST=('HasPost', 'sum'),
            IGNORE=('IsIgnore', 'sum'),
        ).reindex(range(1, df['Tick'].max() + 1), fill_value=0)

        ax.stackplot(tick_actions.index,
                     tick_actions['BUY'], tick_actions['POST'], tick_actions['IGNORE'],
                     labels=['BUY', 'POST', 'IGNORE'],
                     colors=[COLORS['BUY'], COLORS['POST'], COLORS['IGNORE']],
                     alpha=0.8)

        # 标注事件
        for t, label in events.items():
            if t <= tick_actions.index.max():
                ax.axvline(x=t, color='gray', linestyle='--', alpha=0.6)
                ax.text(t + 0.3, ax.get_ylim()[1] * 0.85, label, fontsize=8, color='gray')

        ax.set_title(f'{CLUSTER_LABELS.get(cluster, cluster)}', fontsize=12)
        ax.set_xlabel('Tick')
        ax.set_ylabel('Count')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(axis='y', linestyle=':', alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    img_path2 = latest_file.replace(".csv", "_action_timeline.png")
    plt.savefig(img_path2, dpi=300)
    print(f"🖼️ 动作时间线图已保存: {img_path2}")

    # ══════════════════════════════════════════════════════════════════
    # 打印统计摘要
    # ══════════════════════════════════════════════════════════════════
    print(f"\n{'═'*60}")
    print("📋 动作组成统计摘要")
    print(f"{'═'*60}")
    print(f"{'Cluster':<20} {'BUY':<8} {'POST':<8} {'IGNORE':<8} {'BUY%':<8} {'POST%':<8}")
    print(f"{'─'*60}")
    for cluster in available_clusters:
        row = action_counts.loc[cluster]
        total = row.sum()
        print(f"{cluster:<20} {int(row['BUY']):<8} {int(row['POST']):<8} {int(row['IGNORE']):<8} "
              f"{row['BUY']/total*100:.1f}%   {row['POST']/total*100:.1f}%")
    print(f"{'─'*60}")

    try:
        plt.show()
    except Exception:
        pass


if __name__ == "__main__":
    plot_action_composition()
