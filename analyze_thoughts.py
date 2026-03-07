import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob
from collections import Counter
import re
import warnings

# 忽略一些无关紧要的警告
warnings.filterwarnings("ignore")

# 设置绘图风格 (支持中文)
sns.set_theme(style="whitegrid")
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


def analyze_thoughts():
    # 1. 自动读取最新的 thoughts_log
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    list_of_files = glob.glob(os.path.join(results_dir, 'thoughts_log_*.csv'))

    if not list_of_files:
        print("❌ 未找到 thoughts_log 文件，请先运行 run_simulation.py")
        return

    latest_file = max(list_of_files, key=os.path.getctime)
    print(f"📖 正在分析思维日志: {os.path.basename(latest_file)}")

    try:
        df = pd.read_csv(latest_file, encoding='ansi')
    except Exception as e:
        print(f"⚠️ 读取失败，尝试默认编码... {e}")
        df = pd.read_csv(latest_file)

    if df.empty:
        print("❌ 日志为空，无法分析。")
        return

    # 预处理：将 Hypocrisy 转为布尔/数值
    df['Hypocrisy'] = df['Hypocrisy'].astype(str).str.lower() == 'true'

    # 创建画布 (2行2列)
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f'认知思维分析\n {os.path.basename(latest_file)}', fontsize=16)

    # --- 图 1: 伪善感知率 ---
    # 统计每个 Tick 不同类型的 Agent 有多少比例感知到了 Hypocrisy
    hypocrisy_rate = df.groupby(['Tick', 'AgentType'])['Hypocrisy'].mean().reset_index()

    sns.barplot(
        ax=axes[0, 0],
        data=hypocrisy_rate,
        x='Tick',
        y='Hypocrisy',
        hue='AgentType',
        palette='Set2'
    )
    axes[0, 0].set_title('不同群体的“漂绿”感知率', fontsize=12)
    axes[0, 0].set_ylabel('感知比例')
    axes[0, 0].set_ylim(0, 1.1)

    # --- 图 2: 信任扣分力度 (愤怒程度) ---
    # 分析当 TrustChange < 0 时，扣分的力度分布
    negative_impact = df[df['TrustChange'] < 0]

    if not negative_impact.empty:
        sns.boxplot(
            ax=axes[0, 1],
            data=negative_impact,
            x='AgentType',
            y='TrustChange',
            palette='Reds'
        )
        axes[0, 1].set_title('负面冲击分布', fontsize=12)
        axes[0, 1].set_ylabel('信任值变化')
    else:
        axes[0, 1].text(0.5, 0.5, "无负面信任变化记录", ha='center')

    # --- 图 3 & 4: 关键词提取 (他们在说什么？) ---
    # 简单的分词与词频统计
    def get_top_words(text_series, top_n=10):
        text = " ".join(text_series.astype(str).tolist()).lower()
        # 简单清洗：去标点
        text = re.sub(r'[^\w\s]', '', text)
        words = text.split()
        # 过滤停用词 (根据需要添加)
        stopwords = {'the', 'a', 'to', 'of', 'is', 'in', 'and', 'for', 'that', 'it', 'its', 'but', 'with', 'be', 'as',
                     'on', 'not', 'have', 'are'}
        words = [w for w in words if w not in stopwords and len(w) > 2]
        return Counter(words).most_common(top_n)

    # 提取 Deep Green 的高频词
    deep_green_thoughts = df[df['AgentType'].str.contains('Deep', case=False, na=False)]['Reasoning']
    deep_words = get_top_words(deep_green_thoughts)

    # 提取 Light Green 的高频词
    light_green_thoughts = df[df['AgentType'].str.contains('Light', case=False, na=False)]['Reasoning']
    light_words = get_top_words(light_green_thoughts)

    # 绘制 Deep Green 词频
    if deep_words:
        words, counts = zip(*deep_words)
        sns.barplot(ax=axes[1, 0], x=list(counts), y=list(words), palette="Greens_r")
        axes[1, 0].set_title('深绿消费者高频关注词', fontsize=12)
    else:
        axes[1, 0].text(0.5, 0.5, "数据不足", ha='center')

    # 绘制 Light Green 词频
    if light_words:
        words, counts = zip(*light_words)
        sns.barplot(ax=axes[1, 1], x=list(counts), y=list(words), palette="Blues_r")
        axes[1, 1].set_title('浅绿消费者高频关注词', fontsize=12)
    else:
        axes[1, 1].text(0.5, 0.5, "数据不足", ha='center')

    # 保存与显示
    plt.tight_layout()
    save_path = latest_file.replace(".csv", "_analysis.png")
    plt.savefig(save_path, dpi=300)
    print(f"✅ 深度分析图表已生成: {save_path}")
    plt.show()

    # --- 打印具体的 Case Study (控制台输出) ---
    print("\n🧐 [Case Study] 随机抽取各类型的一条推理记录:")
    for atype in df['AgentType'].unique():
        sample = df[df['AgentType'] == atype].sample(1)
        if not sample.empty:
            print(f"--- {atype} (Tick {sample.iloc[0]['Tick']}) ---")
            print(f"Trust Change: {sample.iloc[0]['TrustChange']}")
            print(f"Thought: {sample.iloc[0]['Reasoning']}\n")


if __name__ == "__main__":
    analyze_thoughts()