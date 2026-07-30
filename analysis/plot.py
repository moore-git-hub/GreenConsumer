"""
analysis/plot.py — 统一可视化入口

整合了原来五个可视化脚本的功能：
  - plot_results.py          → plot_trust_evolution()
  - plot_advanced_dashboard.py → plot_dashboard()
  - plot_action_composition.py → plot_actions()
  - plot_comparison.py       → plot_comparison()
  - visualize_network.py     → plot_network_gif()

用法：
  python analysis/plot.py                # 运行全部图表（默认）
  python analysis/plot.py --mode trust   # 信任演化折线图
  python analysis/plot.py --mode dash    # 2×2 全景看板
  python analysis/plot.py --mode actions # 动作组成图
  python analysis/plot.py --mode compare # 多实验对比图
  python analysis/plot.py --mode network # 社交网络动态 GIF
  python analysis/plot.py --mode all     # 全部
"""
import os
import sys
import glob
import json
import argparse
from typing import Optional

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import networkx as nx

# ── 路径设置 ─────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results", "simulations")

def _latest(pattern: str) -> Optional[str]:
    # 在所有 run_* 子目录中查找匹配文件，返回最新的
    files = glob.glob(os.path.join(RESULTS_DIR, "run_*", pattern))
    return max(files, key=os.path.getctime) if files else None

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# ── 常量 ─────────────────────────────────────────────────────────────
EVENTS = {
    1:  '发售期\nLaunch',
    5:  '黑石漂绿\nBlackstone',
    10: '健康争议\nHealth',
    15: '做空+IPO\nSpruce'
}
EVENTS_EN = {
    1:  'Launch',
    5:  'Blackstone',
    10: 'Health',
    15: 'Short+IPO'
}

CLUSTER_STYLES = {
    'Active_Greens':     {'label': 'Active Greens (积极派)',     'color': '#2ca02c', 'marker': 'o', 'ls': '-'},
    'Convenient_Greens': {'label': 'Convenient Greens (便利派)', 'color': '#98df8a', 'marker': 's', 'ls': '--'},
    'Dormant_Greens':    {'label': 'Dormant Greens (沉睡派)',    'color': '#1f77b4', 'marker': '^', 'ls': ':'},
    'Non_Greens':        {'label': 'Non-Greens (非环保派)',      'color': '#d62728', 'marker': 'x', 'ls': '-.'},
}


def _add_events(ax, ticks, rotate=False, offset=0.2, y_ratio=0.88):
    """在图表上标注事件线"""
    ylim = ax.get_ylim()
    for t, lbl in EVENTS.items():
        if t <= ticks:
            ax.axvline(x=t, color='gray', linestyle='--', alpha=0.5)
            ax.text(t + offset, ylim[0] + (ylim[1] - ylim[0]) * y_ratio,
                    lbl, fontsize=8, color='dimgray', rotation=90, va='top')





def _load_sim(require_macro=False):
    sim_path = _latest('simulation_log_*.csv')
    if not sim_path:
        print("❌ 未找到 simulation_log，请先运行 run_simulation.py")
        sys.exit(1)
    df = pd.read_csv(sim_path)
    df['Action'] = df['Action'].fillna('IGNORE').astype(str)
    df['IsBuy']  = df['Action'].str.contains('BUY')
    df['IsPost'] = df['Action'].str.contains('POST')
    print(f"📂 {os.path.basename(sim_path)}")

    df_macro = None
    if require_macro:
        macro_path = _latest('macro_metrics_*.csv')
        if macro_path:
            df_macro = pd.read_csv(macro_path)
    return df, df_macro, sim_path


# ══════════════════════════════════════════════════════════════════════
# 1. 信任演化折线图
# ══════════════════════════════════════════════════════════════════════

def plot_trust_evolution():
    df, _, sim_path = _load_sim()
    grouped = df.groupby(['Tick', 'Type'])['TrustScore'].mean().unstack()

    plt.figure(figsize=(13, 7))
    for col in grouped.columns:
        s = CLUSTER_STYLES.get(col, {'label': col, 'color': 'gray', 'marker': '.', 'ls': '-'})
        plt.plot(grouped.index, grouped[col],
                 label=s['label'], color=s['color'], marker=s['marker'],
                 linestyle=s['ls'], linewidth=2.5)

    ax = plt.gca()
    _add_events(ax, grouped.index.max(), offset=0.3, y_ratio=0.05)

    plt.title('Trust Evolution by Forrester Consumer Segments\n(Oatly Case Study)',
              fontsize=15, fontweight='bold', pad=12)
    plt.xlabel('Simulation Tick', fontsize=13)
    plt.ylabel('Average Trust Score (0–10)', fontsize=13)
    plt.ylim(0, 10.5)
    plt.grid(True, linestyle=':', alpha=0.4)
    plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=11)
    plt.tight_layout()

    out = sim_path.replace(".csv", "_trust_evolution.png")
    plt.savefig(out, dpi=300)
    print(f"🖼️  {out}")
    plt.close()


# ══════════════════════════════════════════════════════════════════════
# 2. 全景看板（2×2）
# ══════════════════════════════════════════════════════════════════════

def plot_dashboard():
    df, df_macro, sim_path = _load_sim(require_macro=True)
    if df_macro is None:
        print("❌ 未找到 macro_metrics，跳过看板")
        return

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('GABM Simulation Dashboard — Oatly Case', fontsize=17, fontweight='bold', y=0.97)

    max_tick = df['Tick'].max()

    # (A) 信任演化
    ax = axes[0, 0]
    trust_g = df.groupby(['Tick', 'Type'])['TrustScore'].mean().unstack()
    for col in trust_g.columns:
        s = CLUSTER_STYLES.get(col, {'label': col, 'color': 'gray'})
        ax.plot(trust_g.index, trust_g[col], color=s['color'], linewidth=2, label=s['label'])
    _add_events(ax, max_tick)
    ax.set_title('(A) Trust Divergence', fontsize=13)
    ax.set_ylim(0, 10.5)
    ax.legend(fontsize=8, loc='lower left')
    ax.grid(True, linestyle=':', alpha=0.5)

    # (B) 累计购买量
    ax = axes[0, 1]
    buys = df[df['IsBuy']].groupby(['Tick', 'Type']).size().unstack(fill_value=0)
    buys = buys.reindex(range(1, max_tick + 1), fill_value=0).cumsum()
    for col in buys.columns:
        s = CLUSTER_STYLES.get(col, {'label': col, 'color': 'gray'})
        ax.plot(buys.index, buys[col], color=s['color'], linestyle='--', linewidth=2.5, label=s['label'])
    _add_events(ax, max_tick)
    ax.set_title('(B) Cumulative Purchases', fontsize=13)
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(True, linestyle=':', alpha=0.5)

    # (C) 发帖量堆叠柱
    ax = axes[1, 0]
    posts = df[df['IsPost']].groupby(['Tick', 'Type']).size().unstack(fill_value=0)
    posts = posts.reindex(range(1, max_tick + 1), fill_value=0)
    colors = [CLUSTER_STYLES.get(c, {}).get('color', '#888888') for c in posts.columns]
    labels = [CLUSTER_STYLES.get(c, {}).get('label', c) for c in posts.columns]
    posts.plot(kind='bar', stacked=True, ax=ax, color=colors, width=0.8)
    step = max(1, max_tick // 15)
    ax.set_xticks(range(0, len(posts.index), step))
    ax.set_xticklabels(posts.index[::step], rotation=0, fontsize=8)
    ax.set_title('(C) Posting Activity', fontsize=13)
    ax.legend(labels, fontsize=8, loc='upper right')
    ax.grid(axis='y', linestyle=':', alpha=0.4)
    # 事件线（柱状图 x 从 0 开始）
    for t, lbl in EVENTS.items():
        if t <= max_tick:
            ax.axvline(t - 1, color='gray', linestyle='--', alpha=0.5)

    # (D) 宏观双轴
    ax = axes[1, 1]
    ax2 = ax.twinx()
    l1 = ax.plot(df_macro['Tick'], df_macro['ConversionRate'] * 100,
                 color='forestgreen', linewidth=2.5, marker='D', markersize=4, label='Conversion Rate %')
    l2 = ax2.plot(df_macro['Tick'], df_macro['AvgTrust'],
                  color='purple', linewidth=2.5, linestyle='-.', label='Avg Trust')
    _add_events(ax, max_tick)
    ax.set_ylim(0, 100)
    ax2.set_ylim(0, 10.5)
    ax.set_title('(D) Macro Trends', fontsize=13)
    ax.set_ylabel('Conversion Rate (%)', color='forestgreen')
    ax2.set_ylabel('Avg Trust (0–10)', color='purple')
    lns = l1 + l2
    ax.legend(lns, [l.get_label() for l in lns], fontsize=8, loc='lower right')
    ax.grid(True, linestyle=':', alpha=0.4)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out = sim_path.replace(".csv", "_dashboard.png")
    plt.savefig(out, dpi=300)
    print(f"🖼️  {out}")
    plt.close()


# ══════════════════════════════════════════════════════════════════════
# 3. 动作组成图
# ══════════════════════════════════════════════════════════════════════

def plot_actions():
    df, _, sim_path = _load_sim()
    df['IsIgnore'] = (~df['IsBuy']) & (~df['IsPost'])

    action_counts = df.groupby('Type').agg(
        BUY=('IsBuy', 'sum'), POST=('IsPost', 'sum'), IGNORE=('IsIgnore', 'sum')
    )
    cluster_order = [c for c in CLUSTER_STYLES if c in action_counts.index]
    ac = action_counts.loc[cluster_order]
    ac_pct = ac.div(ac.sum(axis=1), axis=0) * 100

    ACTION_COLORS = {'BUY': '#2ca02c', 'POST': '#d62728', 'IGNORE': '#aec7e8'}
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Action Composition by Consumer Segment', fontsize=15, fontweight='bold')

    # 百分比堆叠
    ax = axes[0]
    x = np.arange(len(cluster_order))
    bottom = np.zeros(len(cluster_order))
    for action in ['BUY', 'POST', 'IGNORE']:
        vals = ac_pct[action].values
        ax.bar(x, vals, 0.6, bottom=bottom, label=action, color=ACTION_COLORS[action], alpha=0.85)
        for i, (v, b) in enumerate(zip(vals, bottom)):
            if v > 5:
                ax.text(i, b + v/2, f'{v:.0f}%', ha='center', va='center', fontsize=9, fontweight='bold')
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels([c.split('_')[0] for c in cluster_order], fontsize=10)
    ax.set_title('(A) Action Proportion')
    ax.set_ylim(0, 100)
    ax.legend()
    ax.grid(axis='y', linestyle=':', alpha=0.4)

    # 绝对数量
    ax = axes[1]
    w = 0.25
    x2 = np.arange(len(cluster_order))
    for i, action in enumerate(['BUY', 'POST', 'IGNORE']):
        bars = ax.bar(x2 + i * w, ac[action].values, w, label=action,
                      color=ACTION_COLORS[action], alpha=0.85)
        for bar, v in zip(bars, ac[action].values):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                        str(int(v)), ha='center', va='bottom', fontsize=8)
    ax.set_xticks(x2 + w)
    ax.set_xticklabels([c.split('_')[0] for c in cluster_order], fontsize=10)
    ax.set_title('(B) Action Counts')
    ax.legend()
    ax.grid(axis='y', linestyle=':', alpha=0.4)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out = sim_path.replace(".csv", "_action_composition.png")
    plt.savefig(out, dpi=300)
    print(f"🖼️  {out}")
    plt.close()


# ══════════════════════════════════════════════════════════════════════
# 4. 多实验对比图（从命名文件读取）
# ══════════════════════════════════════════════════════════════════════

def plot_comparison():
    files = {
        "Exp1_DeepGreen.csv": ("Deep Green Population", "green"),
        "Exp2_LightGreen.csv": ("Light Green Population", "lightgreen"),
        "Exp3_Mixed.csv": ("Mixed Population", "steelblue"),
    }
    plt.figure(figsize=(12, 7))
    has_data = False
    for fname, (label, color) in files.items():
        fpath = os.path.join(RESULTS_DIR, fname)
        if not os.path.exists(fpath):
            print(f"⚠️  跳过缺失文件: {fname}")
            continue
        df = pd.read_csv(fpath)
        avg = df.groupby('Tick')['TrustScore'].mean()
        plt.plot(avg.index, avg.values, label=label, color=color, marker='o', linewidth=2.5)
        has_data = True

    if not has_data:
        print("❌ 无对比实验数据（Exp1/Exp2/Exp3 命名文件不存在）")
        plt.close()
        return

    ax = plt.gca()
    _add_events(ax, 30)
    plt.title('Multi-Experiment Trust Comparison', fontsize=15)
    plt.xlabel('Simulation Tick', fontsize=13)
    plt.ylabel('Avg Trust (0–10)', fontsize=13)
    plt.ylim(0, 10)
    plt.legend(fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    out = os.path.join(RESULTS_DIR, "comparison_result.png")
    plt.savefig(out, dpi=300)
    print(f"🖼️  {out}")
    plt.close()


# ══════════════════════════════════════════════════════════════════════
# 5. 社交网络动态 GIF
# ══════════════════════════════════════════════════════════════════════

def plot_network_gif():
    sim_path = _latest('simulation_log_*.csv')
    graph_path = _latest('network_graph_*.json')
    if not sim_path or not graph_path:
        print("❌ 未找到数据文件")
        return

    with open(graph_path, encoding='utf-8') as f:
        gd = json.load(f)
    try:
        G = nx.node_link_graph(gd, edges="links")
    except TypeError:
        G = nx.node_link_graph(gd)

    df = pd.read_csv(sim_path)
    ticks = sorted(df['Tick'].unique())

    print("🕸️  计算网络布局...")
    pos = nx.spring_layout(G, k=0.5, seed=42)
    fig, ax = plt.subplots(figsize=(10, 8))

    def update(tick):
        ax.clear()
        cur = df[df['Tick'] == tick]
        trust_map  = dict(zip(cur['AgentID'], cur['TrustScore']))
        action_map = dict(zip(cur['AgentID'], cur['Action'].fillna('IGNORE')))
        node_colors, node_sizes, edge_cols = [], [], []
        for node in G.nodes():
            trust = trust_map.get(node, 5.0)
            node_colors.append(plt.cm.RdYlGn(min(trust / 10.0, 1.0)))
            action = str(action_map.get(node, ''))
            if 'POST' in action:
                node_sizes.append(600)
                edge_cols.append('red')
            else:
                node_sizes.append(300)
                edge_cols.append('gray')
        event_tag = f" — {EVENTS_EN[tick]}" if tick in EVENTS_EN else ""
        ax.set_title(f"Tick {tick}{event_tag}\n🟢 Green=High Trust  🔴 Red=Low Trust  Large=Posting", fontsize=12)
        nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.3, edge_color='gray')
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                               node_size=node_sizes, edgecolors=edge_cols, linewidths=2)
        if len(G.nodes) <= 30:
            labels = {n: n.split('_')[-1] for n in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=7)
        ax.axis('off')

    print("🎥 生成 GIF...")
    ani = animation.FuncAnimation(fig, update, frames=ticks, interval=800, repeat=True)
    out = sim_path.replace(".csv", "_network.gif")
    try:
        ani.save(out, writer='pillow', fps=1)
        print(f"🖼️  {out}")
    except Exception as e:
        print(f"⚠️  GIF 保存失败: {e}")
    plt.close()


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="GreenConsumer GABM 可视化工具")
    parser.add_argument('--mode', default='all',
                        choices=['all', 'trust', 'dash', 'actions', 'compare', 'network'],
                        help='可视化模式')
    args = parser.parse_args()

    if args.mode in ('trust', 'all'):
        plot_trust_evolution()
    if args.mode in ('dash', 'all'):
        plot_dashboard()
    if args.mode in ('actions', 'all'):
        plot_actions()
    if args.mode in ('compare', 'all'):
        plot_comparison()
    if args.mode in ('network',):
        plot_network_gif()

    print("\n✅ 可视化完成。图表已保存到 results/ 目录。")


if __name__ == "__main__":
    main()
