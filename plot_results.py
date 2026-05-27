import pandas as pd
import matplotlib.pyplot as plt
import os
import glob

# 绘图字体防乱码设置 (兼容中英文)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


def plot_latest_simulation():
    # 1. 强制精确匹配 simulation_log 文件
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
    if 'Type' not in df.columns or 'TrustScore' not in df.columns:
        print("❌ CSV 文件中缺失 'Type' 或 'TrustScore' 列，请检查日志格式。")
        return

    grouped = df.groupby(['Tick', 'Type'])['TrustScore'].mean().unstack()

    # 4. 绘图
    plt.figure(figsize=(12, 7))  # 稍微加宽，留出图例位置

    # 定义 Forrester 2026 四大阵营的学术图表配色与样式
    styles = {
        'Active_Greens': {'label': 'Active Greens (积极环保派)', 'color': '#2ca02c', 'marker': 'o', 'linestyle': '-'},
        # 浓绿 实线
        'Convenient_Greens': {'label': 'Convenient Greens (便利环保派)', 'color': '#98df8a', 'marker': 's',
                              'linestyle': '--'},  # 浅绿 虚线
        'Dormant_Greens': {'label': 'Dormant Greens (沉睡环保派)', 'color': '#1f77b4', 'marker': '^', 'linestyle': ':'},
        # 蓝色 点线
        'Non_Greens': {'label': 'Non-Greens (非环保派)', 'color': '#d62728', 'marker': 'x', 'linestyle': '-.'}  # 红色 点划线
    }

    # 动态遍历并绘制存在的阵营
    for col in grouped.columns:
        if col in styles:
            s = styles[col]
            plt.plot(grouped.index, grouped[col], label=s['label'],
                     marker=s['marker'], color=s['color'], linestyle=s['linestyle'], linewidth=2.5)
        else:
            # 兼容未知的类别防报错
            plt.plot(grouped.index, grouped[col], label=col, marker='.', linewidth=1.5)

    # ==========================================
    # 标注突发新闻事件的发生时间点 (增加论文图表的说服力)
    # ==========================================
    events = {
        1: 'Product Launch',
        5: 'Blackstone Scandal (Greenwashing)',
        10: 'Canola Oil (Utility Drop)'
    }
    for t, label in events.items():
        if t in grouped.index:
            plt.axvline(x=t, color='gray', linestyle='--', alpha=0.6)
            plt.text(t + 0.2, 0.5, label, rotation=90, verticalalignment='bottom', color='gray', fontsize=10,
                     fontweight='bold')

    # 装饰图表
    plt.title('Dynamics of Trust Evolution by Forrester Consumer Segments', fontsize=16, fontweight='bold', pad=15)
    plt.xlabel('Simulation Tick (Time)', fontsize=14)
    plt.ylabel('Average Trust Score (0-10)', fontsize=14)
    plt.grid(True, linestyle='-', alpha=0.3)
    plt.ylim(0, 10.5)

    # 把图例移到图表外侧右边，防止挡住折线走势
    plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=12)
    plt.tight_layout()

    # 保存图片
    img_path = latest_file.replace(".csv", "_trust_evolution.png")
    plt.savefig(img_path, dpi=300)  # dpi=300 保证插入论文打印时的高清画质
    print(f"🖼️ 高清学术图表已保存至: {img_path}")

    # 防止在无界面服务器运行时报错，先存图再显示
    try:
        plt.show()
    except Exception as e:
        print("💡 当前环境可能无法弹出窗口，但图片已成功保存。")


if __name__ == "__main__":
    plot_latest_simulation()