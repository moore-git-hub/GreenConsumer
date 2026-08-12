import networkx as nx
from typing import Dict, Any, List
from agentkernel_standalone.mas.environment.base.plugin_base import EnvironmentPlugin


class SocialNetworkPlugin(EnvironmentPlugin):
    def __init__(self):
        super().__init__()
        # 有向图：BA 底图中的高度数节点向低度数节点单向传播。
        # 结构角色统一按拓扑定义为 Hub 节点与普通节点。
        self.graph = nx.DiGraph()
        # "上帝通讯录"：Agent ID -> Agent 实例
        self.agent_registry = {}
        # ── TASK_002 纯审计属性：只记录实际建图分支，不参与任何建图决策 ──
        self.network_type: str = "uninitialized"
        self.network_params: Dict[str, Any] = {}
        self.network_fallback_reason: str = ""

    async def init(self):
        print("🌐 [Network] 社交网络插件初始化...")

    def register_agents(self, agents: List[Any], seed: int = 42):
        """
        将所有 Agent 注册到网络中，构建有向 BA 无标度网络。
        边方向规则：度数高的节点 → 度数低的节点（Hub 向下游节点广播）

        Args:
            agents: Agent 实例列表
            seed:   BA 网络生成随机种子，默认 42，
                    批量实验中应传入 ExperimentConfig.random_seed 保证可复现性
        """
        self.agent_registry = {a.agent_id: a for a in agents}
        agent_ids = list(self.agent_registry.keys())
        n = len(agent_ids)

        # 纯审计：默认按空网络登记，下面在真实分支内覆盖（不改变任何建图逻辑）
        self.network_type = "empty"
        self.network_params = {"n": n}
        self.network_fallback_reason = ""

        if n > 0:
            if n < 5:
                # 节点过少时使用完全图作为有向化底图
                undirected = nx.complete_graph(n)
                print(f"🌐 [Network] 节点过少 ({n})，采用完全图底图。")
                self.network_type = "complete"
                self.network_params = {"n": n}
            else:
                try:
                    undirected = nx.barabasi_albert_graph(n, m=2, seed=seed)
                    print(f"🌐 [Network] 已构建 BA 无标度网络底图 (n={n}, m=2, seed={seed})。")
                    self.network_type = "barabasi_albert"
                    self.network_params = {"n": n, "m": 2, "seed": seed}
                except Exception as e:
                    print(f"⚠️ [Network] BA 图构建失败 ({e})，回退到随机图。")
                    undirected = nx.erdos_renyi_graph(n, p=0.3, seed=seed)
                    self.network_type = "erdos_renyi"
                    self.network_params = {"n": n, "p": 0.3, "seed": seed}
                    self.network_fallback_reason = (
                        f"barabasi_albert_failed: {type(e).__name__}: {e}"
                    )

            # 映射整数索引 → Agent ID
            mapping = {i: agent_ids[i] for i in range(n)}
            undirected = nx.relabel_nodes(undirected, mapping)

            # 将无向图转换为有向图：
            # 对每条无向边 (u, v)，度数较高的节点作为发送方（→），度数较低的作为接收方
            degrees = dict(undirected.degree())
            directed = nx.DiGraph()
            directed.add_nodes_from(undirected.nodes())
            for u, v in undirected.edges():
                if degrees[u] >= degrees[v]:
                    directed.add_edge(u, v)  # u 度数更高，u → v
                else:
                    directed.add_edge(v, u)  # v 度数更高，v → u

            self.graph = directed

        print(f"🌐 [Network] 有向网络构建完成: {n} 节点, {self.graph.number_of_edges()} 条有向边")

        # 打印出度最高的结构 Hub
        out_degrees = dict(self.graph.out_degree())
        if out_degrees:
            top_k = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"   🔥 广播影响力最强的节点 (Hub, 出度 Top-3): {top_k}")

    def get_successors(self, agent_id: str) -> List[str]:
        """获取该节点的直接下游节点（它能广播到的粉丝）"""
        if agent_id in self.graph:
            return list(self.graph.successors(agent_id))
        return []

    def get_neighbors(self, agent_id: str) -> List[str]:
        """兼容旧接口，返回出向邻居（等同于 get_successors）"""
        return self.get_successors(agent_id)

    # ── TASK_002 只读审计访问器：不修改任何状态，只按确定性顺序导出图结构 ──
    def export_edges(self) -> List[tuple]:
        """导出全部有向边，按 (source, target) 字典序排序以保证落盘可复现。"""
        return sorted((str(u), str(v)) for u, v in self.graph.edges())

    def export_node_degrees(self) -> Dict[str, Dict[str, int]]:
        """导出每个节点的出度/入度（无向图时两者相同），按节点 ID 排序。"""
        is_dir = self.graph.is_directed()
        out_view = dict(self.graph.out_degree()) if is_dir else dict(self.graph.degree())
        in_view = dict(self.graph.in_degree()) if is_dir else dict(self.graph.degree())
        return {
            str(n): {"out_degree": int(out_view.get(n, 0)),
                     "in_degree": int(in_view.get(n, 0))}
            for n in sorted(str(x) for x in self.graph.nodes())
        }

    async def broadcast_message(self, sender_id: str, content: str):
        """
        将消息沿有向边投递给所有下游节点（粉丝）。
        只有出度 > 0 的节点才能实际触达下游节点；该结构属性不由 Persona 决定。
        """
        successors = self.get_successors(sender_id)
        if not successors:
            return

        message_packet = {
            "source": "Social",
            "content": content,
            "type": "social_review",
            "sender_id": sender_id
        }

        deliver_count = 0
        for neighbor_id in successors:
            neighbor_agent = self.agent_registry.get(neighbor_id)
            if neighbor_agent:
                state_comp = neighbor_agent.get_component("state")
                state_plugin = getattr(state_comp, "_plugin", getattr(state_comp, "plugin", None))

                if state_plugin:
                    s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
                    inbox = s_data.get("incoming_messages") or []
                    new_inbox = list(inbox)
                    new_inbox.append(message_packet)

                    if hasattr(state_plugin, "set_state"):
                        await state_plugin.set_state("incoming_messages", new_inbox)
                        deliver_count += 1

        if deliver_count > 0:
            print(f"📡 [Network] {sender_id} → {deliver_count} 粉丝 (单向广播)")

    async def execute(self, current_tick: int) -> None:
        pass

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass
