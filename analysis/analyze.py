"""
analysis/analyze.py — 统一分析入口

整合了原来四个分析脚本的功能：
  - analyze_thoughts.py     → analyze_thoughts()
  - analyze_agent_thoughts.py → print_agent_timeline(), print_tick_snapshot(), analyze_cognitive_patterns()
  - analyze_text_deep.py    → analyze_text_deep()
  - debug_dashboard.py      → debug_dashboard()

用法：
  python analysis/analyze.py                        # 全面分析（默认）
  python analysis/analyze.py --mode thoughts        # 认知层分析（伪善感知+信任变动）
  python analysis/analyze.py --mode agent --id Consumer_001   # 单 Agent 深度追踪
  python analysis/analyze.py --mode tick --tick 5   # 单 Tick 快照
  python analysis/analyze.py --mode text            # 文本深度分析（情感/关键词/语言风格）
  python analysis/analyze.py --mode debug           # 调试看板
  python analysis/analyze.py --mode all             # 运行全部分析
"""
import os
import sys
import glob
import re
import argparse
from collections import Counter
from typing import Optional, Dict, List

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns

# ── 路径设置 ─────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results")

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# ── 常量 ─────────────────────────────────────────────────────────────
EVENTS = {1: 'Launch', 5: 'Blackstone', 10: 'Health', 15: 'Short+IPO'}

CLUSTER_STYLES = {
    'Active_Greens':     {'color': '#2ca02c', 'ls': '-',  'marker': 'o', 'label': 'Active Greens'},
    'Convenient_Greens': {'color': '#98df8a', 'ls': '--', 'marker': 's', 'label': 'Convenient Greens'},
    'Dormant_Greens':    {'color': '#1f77b4', 'ls': ':',  'marker': '^', 'label': 'Dormant Greens'},
    'Non_Greens':        {'color': '#d62728', 'ls': '-.', 'marker': 'x', 'label': 'Non-Greens'},
}

NEGATIVE_WORDS = {
    'betrayal','betrayed','angry','furious','outraged','disgusted','disappointed',
    'fraud','fake','hypocrite','hypocrisy','greenwashing','scandal','boycott',
    'terrible','shameful','unethical','toxic','distrust','suspicious','skeptical',
    'outrage','rage','hate','despise','refuse','reject',
}
POSITIVE_WORDS = {
    'trust','good','great','excellent','pleased','satisfied','impressed','genuine',
    'authentic','transparent','honest','committed','sustainable','ethical','hope',
    'support','love','recommend','reliable','confident','forgive','recover','better',
}
AGGRESSIVE_WORDS = {'boycott','cancel','expose','attack','shame','demand','accountability','justice'}
INDIFFERENCE_WORDS = {'whatever','irrelevant','fine','okay','normal','nothing','indifferent','neutral'}


# ══════════════════════════════════════════════════════════════════════
# 数据加载工具
# ══════════════════════════════════════════════════════════════════════

def _latest(pattern: str) -> Optional[str]:
    files = glob.glob(os.path.join(RESULTS_DIR, pattern))
    return max(files, key=os.path.getctime) if files else None


def load_sim_thought():
    sim_path = _latest('simulation_log_*.csv')
    thought_path = _latest('thoughts_log_*.csv')
    if not sim_path:
        print("❌ 未找到仿真结果，请先运行 run_simulation.py")
        sys.exit(1)

    df_sim = pd.read_csv(sim_path)
    df_sim['Action'] = df_sim['Action'].fillna('IGNORE').astype(str)
    df_sim['HasBuy']  = df_sim['Action'].str.contains('BUY')
    df_sim['HasPost'] = df_sim['Action'].str.contains('POST')

    df_thought = pd.read_csv(thought_path) if thought_path else pd.DataFrame()
    if not df_thought.empty:
        df_thought['Hypocrisy'] = df_thought['Hypocrisy'].astype(bool)
        change_col = 'AffectiveChange' if 'AffectiveChange' in df_thought.columns else 'TrustChange'
        df_thought['TrustChange'] = pd.to_numeric(df_thought[change_col], errors='coerce').fillna(0)

    print(f"📂 {os.path.basename(sim_path)}")
    return df_sim, df_thought, sim_path


# ══════════════════════════════════════════════════════════════════════
# MODE 1: analyze_thoughts — 认知层量化分析
# ══════════════════════════════════════════════════════════════════════

def analyze_thoughts(df_thought: pd.DataFrame):
    """认知层：伪善感知率 + 信任变动 + 关键词"""
    if df_thought.empty:
        print("❌ 无 thoughts_log 数据")
        return

    print(f"\n{'═'*60}")
    print("📊 认知层分析 (Thoughts Analysis)")
    print(f"{'═'*60}")

    summary = df_thought.groupby('AgentType').agg(
        Avg_Trust_Change=('TrustChange', 'mean'),
        Hypocrisy_Rate=('Hypocrisy', lambda x: x.mean() * 100),
        N=('AgentID', 'count')
    ).round(3)
    print(summary.to_string())

    # 关键词
    stop = {'that','this','with','from','have','they','will','just','about',
            'their','when','what','brand','product','would','could','should','been'}
    print()
    for atype in df_thought['AgentType'].unique():
        angry = df_thought[(df_thought['AgentType'] == atype) & (df_thought['TrustChange'] < -0.3)]['Reasoning'].dropna()
        if angry.empty:
            continue
        words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', ' '.join(angry).lower()) if w not in stop]
        top = Counter(words).most_common(5)
        print(f"  [{atype}] angry keywords: {', '.join(f'{w}({c})' for w, c in top)}")

    # 图
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle('Thoughts Analysis', fontweight='bold')

    sns.barplot(x=summary.index, y='Hypocrisy_Rate', data=summary, ax=axes[0], color='lightblue', alpha=0.8)
    axes[0].set_title('Hypocrisy Perception Rate (%)')
    axes[0].set_ylim(0, 100)
    axes[0].tick_params(axis='x', rotation=20)

    sns.lineplot(data=df_thought, x='Tick', y='TrustChange', hue='AgentType', ax=axes[1],
                 marker='o', errorbar=None)
    axes[1].set_title('Trust Change Dynamics')
    axes[1].axhline(0, color='black', alpha=0.3)

    plt.tight_layout()
    out = os.path.join(RESULTS_DIR, "analysis_thoughts.png")
    plt.savefig(out, dpi=300)
    print(f"\n🖼️  {out}")
    plt.close()


# ══════════════════════════════════════════════════════════════════════
# MODE 2: agent — 单 Agent 深度追踪
# ══════════════════════════════════════════════════════════════════════

def print_agent_timeline(df_sim: pd.DataFrame, df_thought: pd.DataFrame, agent_id: str):
    agent_sim = df_sim[df_sim['AgentID'] == agent_id].sort_values('Tick')
    if agent_sim.empty:
        print(f"❌ 未找到 Agent: {agent_id}")
        return

    agent_thought = df_thought[df_thought['AgentID'] == agent_id].sort_values('Tick') if not df_thought.empty else pd.DataFrame()
    atype = agent_sim['Type'].iloc[0]

    print(f"\n{'═'*80}")
    print(f"🧠 Agent Timeline: {agent_id} ({atype})")
    print(f"{'═'*80}")

    for _, row in agent_sim.iterrows():
        tick = int(row['Tick'])
        trust = row['TrustScore']
        action = row['Action']

        reasoning, affective, hypo_tag = "", "", ""
        if not agent_thought.empty:
            t_row = agent_thought[agent_thought['Tick'] == tick]
            if not t_row.empty:
                t = t_row.iloc[0]
                reasoning = str(t.get('Reasoning', ''))[:100]
                affective = f"Δ={t.get('TrustChange', 0):+.2f}"
                hypo_tag = "🚨" if t.get('Hypocrisy', False) else ""

        icon = ("🛒" if 'BUY' in action else "") + ("📢" if 'POST' in action else "") or "😶"
        event_tag = f" ← {EVENTS[tick]}" if tick in EVENTS else ""
        print(f"  Tick {tick:2d}{event_tag}")
        print(f"         Trust={trust:.1f} {affective:<10} {icon} {action:<12} {hypo_tag}")
        if reasoning:
            print(f"         💭 {reasoning}")
        print(f"         {'─'*70}")


def print_tick_snapshot(df_sim: pd.DataFrame, df_thought: pd.DataFrame, tick: int):
    tick_sim = df_sim[df_sim['Tick'] == tick].sort_values('Type')
    if tick_sim.empty:
        print(f"❌ Tick {tick} 无数据")
        return

    event_tag = f" — {EVENTS[tick]}" if tick in EVENTS else ""
    print(f"\n{'═'*80}")
    print(f"📸 Tick {tick} Snapshot{event_tag}")
    print(f"{'═'*80}")
    print(f"{'Agent':<15} {'Type':<20} {'Trust':<8} {'Action':<10} {'Affect':<8} {'Reasoning'}")
    print(f"{'─'*80}")

    tick_thought = df_thought[df_thought['Tick'] == tick] if not df_thought.empty else pd.DataFrame()
    for _, row in tick_sim.iterrows():
        aid = row['AgentID']
        reasoning, affective = "", ""
        if not tick_thought.empty:
            t_row = tick_thought[tick_thought['AgentID'] == aid]
            if not t_row.empty:
                t = t_row.iloc[0]
                reasoning = str(t.get('Reasoning', ''))[:55]
                affective = f"{t.get('TrustChange', 0):+.2f}"
        print(f"{aid:<15} {row['Type']:<20} {row['TrustScore']:<8.1f} {row['Action']:<10} {affective:<8} {reasoning}")


def analyze_cognitive_patterns(df_thought: pd.DataFrame):
    if df_thought.empty:
        return
    print(f"\n{'═'*70}")
    print("🧪 Cognitive Patterns by Consumer Type")
    print(f"{'═'*70}")
    for atype in sorted(df_thought['AgentType'].unique()):
        td = df_thought[df_thought['AgentType'] == atype]
        avg_c = td['TrustChange'].mean()
        hyp_r = td['Hypocrisy'].mean() * 100
        print(f"\n  [{atype}] n={len(td)}")
        print(f"    Avg Affective Change: {avg_c:+.3f} | Hypocrisy Rate: {hyp_r:.1f}%")
        all_text = ' '.join(td['Reasoning'].dropna().astype(str))
        stop = {'that','this','with','from','have','they','will','just','about','your','were'}
        words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', all_text.lower()) if w not in stop]
        top = Counter(words).most_common(8)
        if top:
            print(f"    Keywords: {', '.join(f'{w}({c})' for w, c in top)}")


def all_posts_timeline(df_sim: pd.DataFrame, df_thought: pd.DataFrame):
    posts = df_sim[df_sim['HasPost']].sort_values('Tick')
    if posts.empty:
        print("\n📭 无发帖记录")
        return
    print(f"\n{'═'*80}")
    print(f"📢 Posts Timeline ({len(posts)} total)")
    print(f"{'═'*80}")
    cur_tick = -1
    for _, row in posts.iterrows():
        tick = int(row['Tick'])
        if tick != cur_tick:
            cur_tick = tick
            event_tag = f" — {EVENTS[tick]}" if tick in EVENTS else ""
            print(f"\n  ┌─── Tick {tick}{event_tag}")
        reasoning = ""
        if not df_thought.empty:
            t_row = df_thought[(df_thought['AgentID'] == row['AgentID']) & (df_thought['Tick'] == tick)]
            if not t_row.empty:
                reasoning = str(t_row.iloc[0].get('Reasoning', ''))[:120]
        print(f"  │ 📢 {row['AgentID']} ({row['Type']}) Trust={row['TrustScore']:.1f}")
        if reasoning:
            print(f"  │    {reasoning}")


# ══════════════════════════════════════════════════════════════════════
# MODE 3: text — 文本深度分析
# ══════════════════════════════════════════════════════════════════════

def _sentiment(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        return {'polarity': 0.0, 'neg': 0.0, 'pos': 0.0, 'agg': 0.0, 'ind': 0.0, 'n': 0}
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    n = max(len(words), 1)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS) / n
    pos = sum(1 for w in words if w in POSITIVE_WORDS) / n
    agg = sum(1 for w in words if w in AGGRESSIVE_WORDS) / n
    ind = sum(1 for w in words if w in INDIFFERENCE_WORDS) / n
    return {'polarity': round(pos - neg, 4), 'neg': round(neg, 4), 'pos': round(pos, 4),
            'agg': round(agg, 4), 'ind': round(ind, 4), 'n': len(words)}


def analyze_text_deep(df_thought: pd.DataFrame):
    if df_thought.empty or 'Reasoning' not in df_thought.columns:
        print("❌ 无文本数据可分析")
        return

    df = df_thought.copy()
    df['_pol'] = df['Reasoning'].fillna('').apply(lambda t: _sentiment(str(t))['polarity'])
    df['_neg'] = df['Reasoning'].fillna('').apply(lambda t: _sentiment(str(t))['neg'])
    df['_agg'] = df['Reasoning'].fillna('').apply(lambda t: _sentiment(str(t))['agg'])
    df['_ind'] = df['Reasoning'].fillna('').apply(lambda t: _sentiment(str(t))['ind'])

    # 情感统计表
    print(f"\n{'═'*75}")
    print("📊 Sentiment & Language Style by Consumer Type")
    print(f"{'═'*75}")
    print(f"{'Type':<20} {'Polarity':<10} {'NegDens':<10} {'Aggres':<10} {'Indiffer':<10} {'Mood'}")
    print(f"{'─'*75}")
    for atype in sorted(df['AgentType'].unique()):
        td = df[df['AgentType'] == atype]
        p = td['_pol'].mean()
        n = td['_neg'].mean()
        a = td['_agg'].mean()
        i = td['_ind'].mean()
        mood = "😠 Neg" if p < -0.05 else ("😊 Pos" if p > 0.05 else "😐 Neu")
        print(f"  {atype:<18} {p:+.4f}    {n:.4f}    {a:.4f}    {i:.4f}    {mood}")

    # 主题关键词
    stop = {'that','this','with','from','have','they','will','just','about','your',
            'were','feel','think','know','much','very','really','because','after','into'}
    print(f"\n{'─'*75}")
    print("Top Keywords:")
    for atype in sorted(df['AgentType'].unique()):
        texts = df[df['AgentType'] == atype]['Reasoning'].dropna()
        words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', ' '.join(texts).lower()) if w not in stop]
        top = Counter(words).most_common(10)
        if top:
            print(f"  [{atype}] {' | '.join(f'{w}({c})' for w, c in top[:6])}")

    # 语言风格
    print(f"\n{'─'*75}")
    print(f"{'Type':<20} {'AvgWords':<10} {'Exclaim%':<10} {'1stPerson%'}")
    print(f"{'─'*75}")
    for atype in sorted(df['AgentType'].unique()):
        texts = df[df['AgentType'] == atype]['Reasoning'].dropna().astype(str)
        if texts.empty:
            continue
        avg_w = texts.apply(lambda t: len(t.split())).mean()
        excl = texts.apply(lambda t: '!' in t).mean() * 100
        fp = texts.apply(lambda t: len(re.findall(r'\b(I|my|me)\b', t, re.I)) / max(len(t.split()), 1)).mean() * 100
        print(f"  {atype:<18} {avg_w:<10.1f} {excl:<10.1f} {fp:.1f}")

    # 可视化
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Deep Text Analysis', fontsize=15, fontweight='bold')
    colors = {t: s['color'] for t, s in CLUSTER_STYLES.items()}
    type_order = [t for t in CLUSTER_STYLES if t in df['AgentType'].unique()]

    # (A) 极性时间线
    ax = axes[0, 0]
    for atype in type_order:
        avg = df[df['AgentType'] == atype].groupby('Tick')['_pol'].mean()
        ax.plot(avg.index, avg.values, color=colors.get(atype, 'gray'), linewidth=2, label=atype)
    ax.axhline(0, color='black', alpha=0.3)
    for t, lbl in EVENTS.items():
        ax.axvline(t, color='gray', linestyle='--', alpha=0.4)
    ax.set_title('(A) Sentiment Polarity Over Time')
    ax.legend(fontsize=8)
    ax.grid(True, linestyle=':', alpha=0.4)

    # (B) 负面词密度箱线图
    ax = axes[0, 1]
    box_data = [df[df['AgentType'] == t]['_neg'].values for t in type_order]
    bp = ax.boxplot(box_data, labels=[t.split('_')[0] for t in type_order], patch_artist=True)
    for patch, t in zip(bp['boxes'], type_order):
        patch.set_facecolor(colors.get(t, 'gray'))
        patch.set_alpha(0.6)
    ax.set_title('(B) Negative Word Density')
    ax.grid(True, linestyle=':', alpha=0.4)

    # (C) 极性分布直方图
    ax = axes[1, 0]
    for atype in type_order:
        ax.hist(df[df['AgentType'] == atype]['_pol'], bins=20, alpha=0.5,
                color=colors.get(atype, 'gray'), label=atype, density=True)
    ax.set_title('(C) Polarity Distribution')
    ax.legend(fontsize=8)
    ax.grid(True, linestyle=':', alpha=0.4)

    # (D) 攻击性 vs 冷漠
    ax = axes[1, 1]
    for atype in type_order:
        td = df[df['AgentType'] == atype]
        ax.scatter(td['_agg'], td['_ind'], color=colors.get(atype, 'gray'), alpha=0.5, s=30, label=atype)
    ax.set_title('(D) Aggression vs Indifference')
    ax.set_xlabel('Aggression')
    ax.set_ylabel('Indifference')
    ax.legend(fontsize=8)
    ax.grid(True, linestyle=':', alpha=0.4)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(RESULTS_DIR, "analysis_text_deep.png")
    plt.savefig(out, dpi=300)
    print(f"\n🖼️  {out}")
    plt.close()


# ══════════════════════════════════════════════════════════════════════
# MODE 4: debug — 调试看板
# ══════════════════════════════════════════════════════════════════════

def debug_dashboard(df_sim: pd.DataFrame):
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Debug Dashboard', fontsize=16)

    # 个体信任轨迹
    sns.lineplot(ax=axes[0, 0], data=df_sim, x='Tick', y='TrustScore',
                 hue='Type', units='AgentID', estimator=None, lw=1, alpha=0.6)
    axes[0, 0].set_title('Individual Trust Trajectories')
    axes[0, 0].set_ylim(-0.5, 10.5)

    # 动作分布
    action_counts = df_sim.groupby(['Tick', 'Action']).size().unstack(fill_value=0)
    action_counts.plot(kind='bar', stacked=True, ax=axes[0, 1], colormap='viridis', alpha=0.9)
    axes[0, 1].set_title('Action Distribution per Tick')

    # 伪善感知率
    if 'Thought_Hypocrisy' in df_sim.columns:
        df_sim['Hypocrisy_Val'] = df_sim['Thought_Hypocrisy'].astype(int)
        sns.lineplot(ax=axes[1, 0], data=df_sim, x='Tick', y='Hypocrisy_Val',
                     hue='Type', marker='o', ci=None)
        axes[1, 0].set_title('Hypocrisy Perception Rate')
        axes[1, 0].set_ylim(-0.1, 1.1)
    else:
        axes[1, 0].text(0.5, 0.5, 'No Hypocrisy data', ha='center', transform=axes[1, 0].transAxes)

    # 最终信任分布
    final_df = df_sim[df_sim['Tick'] == df_sim['Tick'].max()]
    sns.boxplot(ax=axes[1, 1], data=final_df, x='Type', y='TrustScore', palette='Set2')
    sns.swarmplot(ax=axes[1, 1], data=final_df, x='Type', y='TrustScore', color='.25', alpha=0.5)
    axes[1, 1].set_title('Final Trust Distribution')
    axes[1, 1].set_ylim(-0.5, 10.5)
    axes[1, 1].tick_params(axis='x', rotation=20)

    plt.tight_layout()
    out = os.path.join(RESULTS_DIR, "analysis_debug.png")
    plt.savefig(out, dpi=300)
    print(f"🖼️  {out}")
    plt.close()


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="GreenConsumer GABM 分析工具")
    parser.add_argument('--mode', default='all',
                        choices=['all', 'thoughts', 'agent', 'tick', 'text', 'debug'],
                        help='分析模式')
    parser.add_argument('--id', type=str, help='Agent ID（mode=agent 时使用）')
    parser.add_argument('--tick', type=int, help='Tick 编号（mode=tick 时使用）')
    args = parser.parse_args()

    df_sim, df_thought, sim_path = load_sim_thought()
    print(f"📊 {df_sim['Tick'].max()} Ticks | {df_sim['AgentID'].nunique()} Agents")

    if args.mode == 'thoughts' or args.mode == 'all':
        analyze_thoughts(df_thought)

    if args.mode == 'agent':
        if not args.id:
            print("❌ 请用 --id 指定 Agent ID，例如：--id Consumer_001")
        else:
            print_agent_timeline(df_sim, df_thought, args.id)

    if args.mode == 'tick':
        if args.tick is None:
            print("❌ 请用 --tick 指定 Tick 编号，例如：--tick 5")
        else:
            print_tick_snapshot(df_sim, df_thought, args.tick)

    if args.mode == 'text' or args.mode == 'all':
        analyze_text_deep(df_thought)

    if args.mode == 'debug' or args.mode == 'all':
        debug_dashboard(df_sim)

    if args.mode == 'all':
        # 额外：所有发帖时间线 + 关键 Tick 快照
        all_posts_timeline(df_sim, df_thought)
        analyze_cognitive_patterns(df_thought)
        for t in [5, 10, 15]:
            if t <= df_sim['Tick'].max():
                print_tick_snapshot(df_sim, df_thought, t)

    print(f"\n{'─'*60}")
    print("✅ 分析完成。输出已保存到 results/ 目录。")


if __name__ == "__main__":
    main()
