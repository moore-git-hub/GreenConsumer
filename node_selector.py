"""
node_selector.py — 渠道节点选择器

根据渠道策略（Hub / Random）从社交网络图中选取目标投放节点。
"""
import random
from typing import List
import networkx as nx


def select_target_nodes(graph: nx.Graph, channel: str, k: int, seed: int) -> List[str]:
    """
    根据渠道策略选择 K 个目标节点。

    Args:
        graph: 社交网络图（节点 ID 为 Agent ID 字符串）
        channel: "hub"（度数最高）或 "random"（随机采样）
        k: 投放节点数（Budget_K）
        seed: 随机种子（仅 random 策略使用）

    Returns:
        选中的 Agent ID 列表（长度 ≤ k）
    """
    nodes = list(graph.nodes())

    if not nodes:
        print("⚠️ [NodeSelector] 网络图为空，无法选择节点。")
        return []

    if len(nodes) <= k:
        print(f"⚠️ [NodeSelector] 节点数 ({len(nodes)}) ≤ K ({k})，返回全部节点。")
        return nodes

    if channel == "hub":
        # 按度数降序排列，取 top-K（度数最高 = 影响力最大的 KOL）
        degree_sorted = sorted(graph.degree(), key=lambda x: x[1], reverse=True)
        selected = [node_id for node_id, _ in degree_sorted[:k]]
        print(f"🎯 [NodeSelector] Hub 策略: 选中 top-{k} 高度数节点 {selected}")
        return selected

    elif channel == "random":
        # 使用独立的 Random 实例，不污染全局随机状态
        rng = random.Random(seed + 7777)  # 偏移种子，避免与网络生成种子重合
        selected = rng.sample(nodes, k)
        print(f"🎲 [NodeSelector] Random 策略: 随机选中 {k} 个节点 {selected}")
        return selected

    else:
        raise ValueError(f"Unknown channel strategy: '{channel}'. Must be 'hub' or 'random'.")


if __name__ == "__main__":
    # 快速验证
    G = nx.barabasi_albert_graph(10, m=2, seed=42)
    mapping = {i: f"Consumer_{i:03d}" for i in range(10)}
    G = nx.relabel_nodes(G, mapping)

    print("Hub 策略:")
    select_target_nodes(G, "hub", 3, seed=42)

    print("\nRandom 策略:")
    select_target_nodes(G, "random", 3, seed=42)
