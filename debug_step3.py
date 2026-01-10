import networkx as nx
from typing import Dict, Any, List
from agentkernel_standalone.mas.environment.base.plugin_base import EnvironmentPlugin


class SocialNetworkPlugin(EnvironmentPlugin):
    def __init__(self):
        # 存储图结构
        self.graph = nx.Graph()
        # “上帝通讯录”：Agent ID -> Agent 实例
        self.agent_registry = {}

    async def init(self):
        print("🌐 [Network] 社交网络插件初始化...")
        pass

    def register_agents(self, agents: List[Any]):
        """
        [初始化辅助] 将所有 Agent 注册到网络中，并生成随机连接
        """
        self.agent_registry = {a.agent_id: a for a in agents}
        agent_ids = list(self.agent_registry.keys())

        # 构建一个随机图 (例如 Watts-Strogatz 小世界网络)
        # 如果节点太少，就构建全连接图以便测试
        n = len(agent_ids)
        if n > 1:
            # 简单起见，这里手动构建一个环状链式结构 A-B-C-D-E
            # 或者直接用 nx 生成
            if n < 5:
                self.graph = nx.complete_graph(n)
            else:
                self.graph = nx.watts_strogatz_graph(n, k=2, p=0.0)  # 环状

            # 将图节点的整数索引映射回 Agent ID
            mapping = {i: agent_ids[i] for i in range(n)}
            self.graph = nx.relabel_nodes(self.graph, mapping)

        print(f"🌐 [Network] 网络构建完成: {n} 节点, {self.graph.number_of_edges()} 边")
        # 打印一下连接关系方便调试
        for node in self.graph.nodes():
            print(f"   - {node} 的邻居: {list(self.graph.neighbors(node))}")

    def get_neighbors(self, agent_id: str) -> List[str]:
        """获取邻居 ID 列表"""
        if agent_id in self.graph:
            return list(self.graph.neighbors(agent_id))
        return []

    async def broadcast_message(self, sender_id: str, content: str):
        """
        [核心功能] 将消息投递给所有邻居
        """
        neighbors = self.get_neighbors(sender_id)
        print(f"📡 [Network] '{sender_id}' 正在广播消息给 {len(neighbors)} 个邻居...")

        message_packet = {
            "source": sender_id,
            "content": content,
            "type": "social_review"
        }

        deliver_count = 0
        for neighbor_id in neighbors:
            neighbor_agent = self.agent_registry.get(neighbor_id)
            if neighbor_agent:
                # 获取邻居的 State 插件
                # 注意：这里假设邻居组件名为 'state'，且有 _plugin 属性
                state_comp = neighbor_agent.get_component("state")
                if state_comp and hasattr(state_comp, "_plugin"):
                    state_plugin = state_comp._plugin

                    # 读取旧收件箱
                    # 兼容 state_data / _state_data
                    s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
                    inbox = s_data.get("incoming_messages") or []

                    # 写入新消息
                    inbox.append(message_packet)
                    await state_plugin.set_state("incoming_messages", inbox)
                    deliver_count += 1

        print(f"   ✅ 成功投递给 {deliver_count} 个邻居。")

    async def execute(self, current_tick: int) -> None:
        pass

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass