import pandas as pd
import matplotlib.pyplot as plt
import os
import glob


def plot_latest_simulation():
    # 1. 强制精确匹配 simulation_log 文件，彻底阻断抓取到 thought 或 macro 日志
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    list_of_files = glob.glob(os.path.join(results_dir, 'simulation_log_*.csv'))

    if not list_of_files:
        print("❌ 没有找到 simulation_log 数据文件，请先运行 run_simulation.py")
        return

    latest_file = max(list_of_files, key=os.path.getctime)
    print(f"📈 正在读取并绘制基础动作日志: {os.path.basename(latest_file)}")

    # 2. 读取数据
    df = pd.read_csv(latest_file)

    # 3. 分组计算平均信任值
    # 按 Tick 和 Type 分组，计算 TrustScore 的均值
    grouped = df.groupby(['Tick', 'Type'])['TrustScore'].mean().unstack()

    # 4. 绘图
    plt.figure(figsize=(10, 6))

    # 绘制折线
    if 'Deep Green' in grouped.columns:
        plt.plot(grouped.index, grouped['Deep Green'], label='Deep Green Consumers', marker='o', color='green',
                 linewidth=2)

    if 'Light Green' in grouped.columns:
        plt.plot(grouped.index, grouped['Light Green'], label='Light Green Consumers', marker='s', color='lightgreen',
                 linestyle='--', linewidth=2)

    # 装饰图表
    plt.title('Trust Evolution: Deep vs. Light Green Consumers', fontsize=14)
    plt.xlabel('Simulation Tick', fontsize=12)
    plt.ylabel('Average Trust Score (0-10)', fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.ylim(0, 10)

    # 保存图片
    img_path = latest_file.replace(".csv", ".png")
    plt.savefig(img_path)
    print(f"🖼️ 信任演化对比图已保存至: {img_path}")
    plt.show()


if __name__ == "__main__":
    plot_latest_simulation()