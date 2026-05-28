import pandas as pd
import matplotlib.pyplot as plt
import os
import glob
import numpy as np

# 绘图字体防乱码设置 (兼容中英文)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


def plot_advanced_dashboard():
    results_dir = os.path.join(os.path.dirname(__file__), "results")

    # 1. 获取最新的基础日志和宏观日志
    sim_files = glob.glob(os.path.join(results_dir, 'simulation_log_*.csv'))
    macro_files = glob.glob(os.path.join(results_dir, 'macro_metrics_*.csv'))

    if not sim_files or not macro_files:
        print("❌ 缺失日志文件，请先运行 run_simulation.py")
        return

    latest_sim = max(sim_files, key=os.path.getctime)
    latest_macro = max(macro_files, key=os.path.getctime)

    print(f"📈 正在分析: {os.path.basename(latest_sim)}")
    df_sim = pd.read_csv(latest_sim)
    df_macro = pd.read_csv(latest_macro)

    # 预处理 Action 字段 (兼容 BUY+POST 的情况)
    df_sim['Action'] = df_sim['Action'].fillna('IGNORE').astype(str)
    df_sim['IsBuy'] = df_sim['Action'].str.contains('BUY')
    df_sim['IsPost'] = df_sim['Action'].str.contains('POST')

    # 定义统一的学术配色与样式字典
    styles = {
        'Active_Greens': {'label': 'Active (积极派)', 'color': '#2ca02c', 'marker': 'o'},
        'Convenient_Greens': {'label': 'Convenient (便利派)', 'color': '#98df8a', 'marker': 's'},
        'Dormant_Greens': {'label': 'Dormant (沉睡派)', 'color': '#1f77b4', 'marker': '^'},
        'Non_Greens': {'label': 'Non-Greens (非环保派)', 'color': '#d62728', 'marker': 'x'}
    }

    # 突发事件标注
    events = {
        1: '发售期\nLaunch',
        5: '黑石漂绿危机\nGreenwashing',
        10: '配方降质危机\nUtility Drop'
    }

    # 建立 2x2 画布
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('Generative Agent-Based Model (GABM) Simulation Dashboard', fontsize=18, fontweight='bold', y=0.96)

    # ==========================================
    # [子图 1: 左上] 各阵营信任演化图
    # ==========================================
    ax1 = axes[0, 0]
    trust_grouped = df_sim.groupby(['Tick', 'Type'])['TrustScore'].mean().unstack()
    for col in trust_grouped.columns:
        if col in styles:
            s = styles[col]
            ax1.plot(trust_grouped.index, trust_grouped[col], label=s['label'], color=s['color'], linewidth=2)
        else:
            ax1.plot(trust_grouped.index, trust_grouped[col], label=col)

    ax1.set_title('(A) 心理层: 信任度分化演化 (Trust Divergence)', fontsize=13)
    ax1.set_ylabel('信任度 (0-10)')
    ax1.set_ylim(0, 10.5)
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='lower left', fontsize=9)

    # ==========================================
    # [子图 2: 右上] 累计购买行为分化图
    # ==========================================
    ax2 = axes[0, 1]
    buy_counts = df_sim[df_sim['IsBuy']].groupby(['Tick', 'Type']).size().unstack(fill_value=0)
    # 补全缺失的 Tick 以防前面没人买
    buy_counts = buy_counts.reindex(range(1, df_sim['Tick'].max() + 1), fill_value=0)
    cumulative_buys = buy_counts.cumsum()

    for col in cumulative_buys.columns:
        if col in styles:
            s = styles[col]
            ax2.plot(cumulative_buys.index, cumulative_buys[col], label=s['label'], color=s['color'], linestyle='--',
                     linewidth=2.5)

    ax2.set_title('(B) 行为层: 累计转化购买量 (Cumulative Purchases)', fontsize=13)
    ax2.set_ylabel('累计购买人次')
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='upper left', fontsize=9)

    # ==========================================
    # [子图 3: 左下] 负面舆情爆发(发帖)堆叠柱状图
    # ==========================================
    ax3 = axes[1, 0]
    post_counts = df_sim[df_sim['IsPost']].groupby(['Tick', 'Type']).size().unstack(fill_value=0)
    post_counts = post_counts.reindex(range(1, df_sim['Tick'].max() + 1), fill_value=0)

    # 获取可用列对应的颜色（fallback 用合法的灰色 hex）
    colors = [styles[c]['color'] if c in styles else '#888888' for c in post_counts.columns]
    labels = [styles[c]['label'] if c in styles else c for c in post_counts.columns]

    post_counts.plot(kind='bar', stacked=True, ax=ax3, color=colors, width=0.8)
    ax3.set_title('(C) 传播层: 危机舆情发帖量 (Negative WOM / Outrage)', fontsize=13)
    ax3.set_ylabel('发帖人次 (Posts)')
    ax3.set_xlabel('Tick')
    # 优化 X 轴刻度显示
    ax3.set_xticks(range(0, len(post_counts.index), 2))
    ax3.set_xticklabels(post_counts.index[::2], rotation=0)
    ax3.legend(labels, loc='upper right', fontsize=9)

    # ==========================================
    # [子图 4: 右下] 宏观市场基本面 (双Y轴)
    # ==========================================
    ax4 = axes[1, 1]
    ax4_right = ax4.twinx()

    # 转化率 (绿色折线)
    l1 = ax4.plot(df_macro['Tick'], df_macro['ConversionRate'] * 100, color='forestgreen', linewidth=2.5, marker='D',
                  markersize=5, label='宏观转化率 (Conversion Rate %)')
    # 平均信任度 (紫色折线)
    l2 = ax4_right.plot(df_macro['Tick'], df_macro['AvgTrust'], color='purple', linewidth=2.5, linestyle='-.',
                        label='全局平均信任 (Avg Trust)')

    ax4.set_title('(D) 宏观层: 基本面剪刀差 (Macro Trends)', fontsize=13)
    ax4.set_ylabel('转化率 (%)', color='forestgreen')
    ax4_right.set_ylabel('信任度 (0-10)', color='purple')
    ax4.set_ylim(0, 100)
    ax4_right.set_ylim(0, 10.5)
    ax4.grid(True, linestyle=':', alpha=0.6)

    # 合并两个图例
    lns = l1 + l2
    labs = [l.get_label() for l in lns]
    ax4.legend(lns, labs, loc='lower right', fontsize=9)

    # ==========================================
    # 统一给四个子图画上事件触发线
    # ==========================================
    for ax in axes.flat:
        for t, label in events.items():
            # 柱状图的 x 坐标是从 0 开始的索引，其余是具体的 Tick 值
            x_val = t - 1 if ax == ax3 else t
            ax.axvline(x=x_val, color='gray', linestyle='-', alpha=0.8)
            ax.text(x_val + 0.1, ax.get_ylim()[1] * 0.8, label, color='black', fontsize=9, rotation=90,
                    bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))

    plt.tight_layout(rect=[0, 0, 1, 0.95])  # 留出顶部标题空间

    img_path = latest_sim.replace(".csv", "_advanced_dashboard.png")
    plt.savefig(img_path, dpi=300)
    print(f"📊 高级全景看板已保存至: {img_path}")

    try:
        plt.show()
    except Exception as e:
        pass


if __name__ == "__main__":
    plot_advanced_dashboard()