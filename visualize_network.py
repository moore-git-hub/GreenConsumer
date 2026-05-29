import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import os
import glob
import json
import numpy as np


def visualize_simulation_gif():
    # 1. 自动定位最新文件
    results_dir = os.path.join(os.path.dirname(__file__), "results")

    # 找最新的 log 和 graph
    csv_files = glob.glob(os.path.join(results_dir, 'simulation_log_*.csv'))
    graph_files = glob.glob(os.path.join(results_dir, 'network_graph_*.json'))

    if not csv_files or not graph_files:
        print("❌ 未找到数据文件，请先运行 run_simulation.py")
        return

    latest_csv = max(csv_files, key=os.path.getctime)
    # 假设 log 和 graph 是成对生成的，取时间戳匹配的 graph，或者直接取最新的
    latest_graph = max(graph_files, key=os.path.getctime)

    print(f"🎬 正在处理数据:\n   Log: {os.path.basename(latest_csv)}\n   Graph: {os.path.basename(latest_graph)}")

    # 2. 读取数据
    # 读取网络结构
    with open(latest_graph, "r", encoding="utf-8") as f:
        graph_data = json.load(f)
    # 兼容 networkx >= 3.0 的 edges 参数变更
    try:
        G = nx.node_link_graph(graph_data, edges="links")
    except TypeError:
        G = nx.node_link_graph(graph_data)

    # 读取仿真日志
    df = pd.read_csv(latest_csv)
    ticks = sorted(df['Tick'].unique())

    # 3. 设置绘图布局 (固定布局，防止节点乱跑)
    # 使用 spring_layout 模拟力导向图，k值越大节点越分散
    print("🕸️ 计算网络布局...")
    pos = nx.spring_layout(G, k=0.5, seed=42)

    # 4. 初始化画布
    fig, ax = plt.subplots(figsize=(10, 8))

    def update(frame_tick):
        ax.clear()

        # 获取当前 Tick 的数据
        current_data = df[df['Tick'] == frame_tick]

        # 准备节点颜色列表
        node_colors = []
        node_sizes = []
        edge_colors = []  # 可以在发帖者周围加粗边框

        trust_map = dict(zip(current_data['AgentID'], current_data['TrustScore']))
        action_map = dict(zip(current_data['AgentID'], current_data['Action']))

        for node in G.nodes():
            # 获取信任值 (默认 5.0)
            trust = trust_map.get(node, 5.0)

            # 颜色映射: 0(红) -> 5(黄) -> 10(绿)
            # 简单的归一化到 0-1 用于 colormap
            norm_trust = max(0, min(10, trust)) / 10.0
            # 使用 RdYlGn (红-黄-绿) 色谱
            color = plt.cm.RdYlGn(norm_trust)
            node_colors.append(color)

            # 动作检测：如果发帖，节点变大
            action = action_map.get(node, "none")
            if action == "post_review":
                node_sizes.append(600)  # 发帖者变大
                edge_colors.append('red')  # 边框变红
            else:
                node_sizes.append(300)  # 普通大小
                edge_colors.append('gray')

        # 绘制
        ax.set_title(f"Simulation Tick: {frame_tick}\nGreen=Trust, Red=Distrust, Large=Posting", fontsize=15)

        # 画边
        nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.3, edge_color="gray")

        # 画点
        nx.draw_networkx_nodes(G, pos, ax=ax,
                               node_color=node_colors,
                               node_size=node_sizes,
                               edgecolors=edge_colors,  # 节点边框颜色
                               linewidths=2)  # 节点边框粗细

        # 画标签 (可选，节点太多时不建议画)
        if len(G.nodes) <= 50:
            # 简化标签，只显示 ID 后几位
            labels = {n: n.split("_")[-1] for n in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=8, font_color="black")

        ax.axis('off')

    # 5. 生成动画
    print("🎥 生成动画中 (可能需要几秒钟)...")
    ani = animation.FuncAnimation(fig, update, frames=ticks, interval=1000, repeat=True)

    # 保存为 GIF
    save_path = latest_csv.replace(".csv", "_network.gif")

    # 使用 Pillow writer (不需要安装 ffmpeg)
    try:
        ani.save(save_path, writer='pillow', fps=1)
        print(f"✅ 动图已保存至: {save_path}")
        print("💡 请在文件夹中打开 GIF 查看效果！")
    except Exception as e:
        print(f"❌ 保存 GIF 失败: {e}\n尝试仅显示窗口...")
        plt.show()


if __name__ == "__main__":
    visualize_simulation_gif()