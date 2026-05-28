import pandas as pd
import matplotlib.pyplot as plt
import os


def plot_comparison():
    results_dir = os.path.join(os.path.dirname(__file__), "results")

    # 定义要读取的文件和显示的标签
    files = {
        "Exp1_DeepGreen.csv": ("Deep Green Population", "green"),
        "Exp2_LightGreen.csv": ("Light Green Population", "lightgreen"),
        "Exp3_Mixed.csv": ("Mixed Population", "blue")
    }

    plt.figure(figsize=(12, 7))

    for filename, (label, color) in files.items():
        filepath = os.path.join(results_dir, filename)
        if not os.path.exists(filepath):
            print(f"⚠️ 跳过缺失文件: {filename}")
            continue

        # 读取数据
        df = pd.read_csv(filepath)

        # 计算每一 Tick 的全网平均信任值
        # 我们只关心整体趋势，所以取所有 Agent 的均值
        avg_trust_per_tick = df.groupby('Tick')['TrustScore'].mean()

        # 绘图
        plt.plot(avg_trust_per_tick.index, avg_trust_per_tick.values,
                 label=label, color=color, marker='o', linewidth=2.5)

    plt.title('Impact of Environmental Awareness on Trust Evolution', fontsize=16)
    plt.xlabel('Simulation Time (Tick)', fontsize=14)
    plt.ylabel('Average Market Trust (0-10)', fontsize=14)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(fontsize=12)
    plt.ylim(0, 10)

    # 标注漂绿事件（对齐 ENTERPRISE_STRATEGY Tick 5）
    plt.axvline(x=5, color='red', linestyle=':', alpha=0.5)
    plt.text(5.1, 9.5, 'Greenwashing Scandal (Tick 5)', color='red')

    save_path = os.path.join(results_dir, "Comparison_Result.png")
    plt.savefig(save_path, dpi=300)
    print(f"🖼️ 对比图已保存至: {save_path}")
    plt.show()


if __name__ == "__main__":
    plot_comparison()