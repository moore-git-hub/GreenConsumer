import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob
import numpy as np

# 设置绘图风格
sns.set_theme(style="whitegrid")
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号


def generate_dashboard():
    # 1. 自动读取最新的 CSV
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if not os.path.exists(results_dir):
        print(" 未找到 results 文件夹")
        return

    list_of_files = glob.glob(os.path.join(results_dir, 'simulation_log_*.csv'))
    if not list_of_files:
        print("未找到数据文件，请先运行 run_simulation.py")
        return

    latest_file = max(list_of_files, key=os.path.getctime)
    print(f"📊 正在分析: {os.path.basename(latest_file)}")

    df = pd.read_csv(latest_file)

    # 2. 准备画布 (2x2)
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f'调试数据\n源文件: {os.path.basename(latest_file)}', fontsize=16)

    # --- 图 1: 个体信任轨迹 (微观视角) ---
    sns.lineplot(
        ax=axes[0, 0],
        data=df,
        x='Tick',
        y='TrustScore',
        hue='Type',
        units='AgentID',
        estimator=None,  # 不计算平均，画出每一条线
        lw=1,
        alpha=0.6  # 设置透明度，防止重叠
    )
    axes[0, 0].set_title('Agent信任轨迹', fontsize=12)
    axes[0, 0].set_ylim(-0.5, 10.5)
    axes[0, 0].set_ylabel('信任评分 (0-10)')
    axes[0, 0].legend(title='类型')

    # --- 图 2: 行动分布堆叠图 (行为视角) ---
    # 作用：检查 T=4 时到底有没有人 post_review？如果没有，说明决策逻辑有问题。
    # 统计每个 Tick 每种 Action 的数量
    action_counts = df.groupby(['Tick', 'Action']).size().unstack(fill_value=0)
    # 绘制堆叠柱状图
    action_counts.plot(kind='bar', stacked=True, ax=axes[0, 1], colormap='viridis', alpha=0.9)
    axes[0, 1].set_title('各 Tick 动作分布', fontsize=12)
    axes[0, 1].set_ylabel('Agent 数量')
    axes[0, 1].legend(title='动作', loc='upper right')

    # --- 图 3: 伪善感知率 (认知视角) ---
    # 作用：检查 LLM 是否理解了“漂绿”。如果曲线一直是 0，说明 Prompt 没生效。
    # 将 True/False 转换为 1/0
    if 'Thought_Hypocrisy' in df.columns:
        df['Hypocrisy_Val'] = df['Thought_Hypocrisy'].astype(int)
        sns.lineplot(
            ax=axes[1, 0],
            data=df,
            x='Tick',
            y='Hypocrisy_Val',
            hue='Type',
            marker='o',
            err_style="bars",  # 显示误差棒
            ci=None  # 不显示置信区间，让图更清晰
        )
        axes[1, 0].set_title('漂绿感知比例', fontsize=12)
        axes[1, 0].set_ylabel('感知比例 (0=无, 1=全员感知)')
        axes[1, 0].set_ylim(-0.1, 1.1)
    else:
        axes[1, 0].text(0.5, 0.5, '数据中无 Thought_Hypocrisy 列', ha='center')

    # --- 图 4: 最终信任分布箱线图 (结果视角) ---
    # 作用：对比 Deep Green 和 Light Green 在结束时是否有显著差异。
    final_tick = df['Tick'].max()
    final_df = df[df['Tick'] == final_tick]

    sns.boxplot(
        ax=axes[1, 1],
        data=final_df,
        x='Type',
        y='TrustScore',
        palette="Set2"
    )
    sns.swarmplot(  # 加上散点，看清具体分布
        ax=axes[1, 1],
        data=final_df,
        x='Type',
        y='TrustScore',
        color=".25",
        alpha=0.5
    )
    axes[1, 1].set_title(f'最终信任值分布', fontsize=12)
    axes[1, 1].set_ylim(-0.5, 10.5)

    # 3. 保存与显示
    plt.tight_layout()
    save_path = latest_file.replace(".csv", "_dashboard.png")
    plt.savefig(save_path, dpi=300)
    print(f"✅ 仪表盘已生成: {save_path}")
    plt.show()


if __name__ == "__main__":
    generate_dashboard()