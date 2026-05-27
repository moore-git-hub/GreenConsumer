import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re
from collections import Counter
import os

# 设置图表字体以支持中文和英文
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


def analyze_thoughts_log(file_path):
    print(f"📂 正在加载数据: {file_path}")
    df = pd.read_csv(file_path)

    # 清理和格式化数据
    df['Hypocrisy'] = df['Hypocrisy'].astype(bool)
    df['TrustChange'] = pd.to_numeric(df['TrustChange'], errors='coerce').fillna(0)

    # 建立输出目录
    results_dir = os.path.dirname(file_path)
    if not results_dir: results_dir = '.'

    print("\n" + "=" * 40)
    print("📊 第一部分：核心量化指标 (Quantitative Metrics)")
    print("=" * 40)

    # 1. 计算不同群体的平均信任惩罚与伪善感知率
    summary = df.groupby('AgentType').agg(
        Average_Trust_Change=('TrustChange', 'mean'),
        Hypocrisy_Perception_Rate=('Hypocrisy', lambda x: x.mean() * 100),
        Total_Thoughts=('AgentID', 'count')
    ).round(2)

    print(summary)

    # ==========================================
    # 📈 可视化 1：不同人群的伪善感知与信任惩罚对比图
    # ==========================================
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # 柱状图：伪善感知率
    sns.barplot(x=summary.index, y='Hypocrisy_Perception_Rate', data=summary, ax=ax1, color='lightblue', alpha=0.7)
    ax1.set_ylabel('伪善感知率 / Hypocrisy Perception Rate (%)', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.set_ylim(0, 100)

    # 折线图：信任惩罚 (双Y轴)
    ax2 = ax1.twinx()
    sns.lineplot(x=summary.index, y='Average_Trust_Change', data=summary, ax=ax2, color='red', marker='o', linewidth=3,
                 markersize=10)
    ax2.set_ylabel('平均信任惩罚 / Avg Trust Change', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    plt.title('Agent 认知层核算：各群体伪善感知与信任惩罚对比', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plot_path1 = os.path.join(results_dir, "thoughts_analysis_summary.png")
    plt.savefig(plot_path1, dpi=300)
    print(f"\n🖼️ 图表1已保存: {plot_path1}")

    # ==========================================
    # 📈 可视化 2：信任度变化随时间 (Tick) 的演化分布
    # ==========================================
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x='Tick', y='TrustChange', hue='AgentType', marker='o', errorbar=None)

    # 标注可能的危机点 (假定负值最深的地方是危机点)
    min_tick = df.groupby('Tick')['TrustChange'].mean().idxmin()
    plt.axvline(x=min_tick, color='gray', linestyle='--', alpha=0.7)
    plt.text(min_tick + 0.5, df['TrustChange'].min(), 'Major Outrage Point', color='black', fontsize=10)

    plt.title('不同群体内心信任变动轨迹 (Trust Change Dynamics over Time)', fontsize=14, fontweight='bold')
    plt.xlabel('Simulation Tick')
    plt.ylabel('Trust Change (per tick)')
    plt.legend(title='Agent Type', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plot_path2 = os.path.join(results_dir, "thoughts_analysis_timeline.png")
    plt.savefig(plot_path2, dpi=300)
    print(f"🖼️ 图表2已保存: {plot_path2}")

    print("\n" + "=" * 40)
    print("🧠 第二部分：深度语义分析 (Qualitative Analysis)")
    print("=" * 40)

    # 简单的 NLP 高频词汇提取，挖掘各阵营脑子里的核心聚焦点
    stop_words = {'that', 'this', 'with', 'from', 'your', 'have', 'they', 'will', 'just', 'about',
                  'their', 'when', 'what', 'brand', 'product', 'because', 'which', 'than', 'more',
                  'also', 'would', 'could', 'should', 'been', 'were'}

    def get_top_keywords(texts, n=10):
        words = re.findall(r'\b[a-zA-Z]{4,}\b', ' '.join(texts).lower())
        words = [w for w in words if w not in stop_words]
        return Counter(words).most_common(n)

    for agent_type in df['AgentType'].unique():
        type_texts = df[(df['AgentType'] == agent_type) & (df['TrustChange'] < -0.3)]['Reasoning'].dropna()
        if not type_texts.empty:
            top_words = get_top_keywords(type_texts, 5)
            print(f"[{agent_type}] 在极度愤怒(Trust Drop < -0.3)时，内心 OS 的高频词汇:")
            words_str = ", ".join([f"{w} ({c}次)" for w, c in top_words])
            print(f"   👉 {words_str}\n")


if __name__ == "__main__":
    # 请确保将文件名替换为你实际的最新文件名
    target_csv = "thoughts_log_20260515_140826.csv"

    if os.path.exists(target_csv):
        analyze_thoughts_log(target_csv)
    else:
        print(f"❌ 找不到文件 {target_csv}，请检查路径。")