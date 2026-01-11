import sys
import os
import asyncio
import yaml
import json
import csv
import datetime
import numpy as np
import networkx as nx  # 【新增】用于保存图结构

# --- 1. 环境与路径设置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
standalone_path = os.path.join(project_root, "packages", "agentkernel-standalone")
if os.path.exists(standalone_path) and standalone_path not in sys.path:
    sys.path.insert(0, standalone_path)

from agentkernel_standalone.mas.builder import Builder
from agentkernel_standalone.mas.agent.agent import Agent
from agentkernel_standalone.mas.environment.environment import Environment
from agentkernel_standalone.mas.environment.base.component_base import EnvironmentComponent
from agentkernel_standalone.toolkit.models.router import ModelRouter, AsyncModelRouter

from agentkernel_standalone.mas.agent.components.profile import ProfileComponent
from agentkernel_standalone.mas.agent.components.state import StateComponent
from agentkernel_standalone.mas.agent.components.perceive import PerceiveComponent
from agentkernel_standalone.mas.agent.components.plan import PlanComponent
from agentkernel_standalone.mas.agent.components.invoke import InvokeComponent
from agentkernel_standalone.mas.agent.components.reflect import ReflectComponent
from agentkernel_standalone.mas.system.components.timer import Timer
from agentkernel_standalone.mas.system.components.messager import Messager

sys.path.append(current_dir)
try:
    from plugins.agent.profile.GreenProfilePlugin import GreenProfilePlugin
    from plugins.agent.state.GreenStatePlugin import GreenStatePlugin
    from plugins.agent.perceive.GreenPerceivePlugin import GreenPerceivePlugin
    from plugins.agent.reflect.GreenCognitionPlugin import GreenCognitionPlugin
    from plugins.agent.plan.ConsumerPlanPlugin import ConsumerPlanPlugin
    from plugins.agent.invoke.GreenInvokePlugin import GreenInvokePlugin
    from plugins.environment.network.SocialNetworkPlugin import SocialNetworkPlugin
except ImportError as e:
    print(f"❌ 插件缺失: {e}")
    sys.exit(1)

# --- 2. 资源注册表 ---
resource_maps = {
    "agent_components": {
        "profile": ProfileComponent,
        "state": StateComponent,
        "perceive": PerceiveComponent,
        "reflect": ReflectComponent,
        "plan": PlanComponent,
        "invoke": InvokeComponent
    },
    "agent_plugins": {
        "GreenProfilePlugin": GreenProfilePlugin,
        "GreenStatePlugin": GreenStatePlugin,
        "GreenPerceivePlugin": GreenPerceivePlugin,
        "GreenCognitionPlugin": GreenCognitionPlugin,
        "ConsumerPlanPlugin": ConsumerPlanPlugin,
        "GreenInvokePlugin": GreenInvokePlugin
    },
    "system_components": {"timer": Timer, "messager": Messager},
    "environment_components": {}, "action_components": {}, "controller": None
}


def mount_env_component(env, comp, name):
    comp.COMPONENT_NAME = name
    if hasattr(env, "add_component"):
        try:
            env.add_component(comp)
        except TypeError:
            env.add_component(name, comp)
    elif hasattr(env, "_components"):
        env._components[name] = comp


async def run():
    print("🚀 [GABM] 绿色消费仿真启动...")

    # --- 准备 CSV Logger ---
    results_dir = os.path.join(current_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. 仿真日志路径
    csv_path = os.path.join(results_dir, f"simulation_log_{timestamp}.csv")
    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    writer.writerow(["Tick", "AgentID", "Type", "TrustScore", "Action", "Thought_Hypocrisy"])
    print(f"📂 数据将保存至: {csv_path}")

    # --- 初始化 ---
    builder = Builder(current_dir, resource_maps)
    builder._load_data_into_config()
    agent_configs = builder.config.agents

    env = Environment()
    net_plugin = SocialNetworkPlugin()
    net_comp = EnvironmentComponent()
    net_comp.plugin = net_plugin
    net_comp._plugin = net_plugin
    net_plugin.component = net_comp
    mount_env_component(env, net_comp, "network")

    agents = []
    # 限制 Agent 数量方便测试
    target_configs = agent_configs

    for conf in target_configs:
        agent = Agent(conf.id, conf.component_order)
        agent.env = env
        await agent.init(conf.components, resource_maps)
        for name, comp in agent._components.items():
            comp._agent = agent
            plugin = getattr(comp, "plugin", None)
            if plugin:
                comp._plugin = plugin
                plugin.component = comp
        agents.append(agent)

    print(f"👥 初始化了 {len(agents)} 个 Agent。")

    # 构建网络
    await net_plugin.init()
    net_plugin.register_agents(agents)

    # 保存网络结构供可视化使用
    # 将 NetworkX 图保存为 Adjacency List
    graph_path = os.path.join(results_dir, f"network_graph_{timestamp}.json")
    graph_data = nx.node_link_data(net_plugin.graph)
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f)
    print(f"网络拓扑已保存至: {graph_path}")

    # LLM Router
    try:
        with open(os.path.join(current_dir, "configs/models_config.yaml"), "r") as f:
            models_conf = yaml.safe_load(f)
        router = ModelRouter(AsyncModelRouter(models_conf))
        print("LLM 引擎已就绪。")
    except:
        print("⚠️ 使用 Mock Router")

        class Mock:
            async def chat(self, p):
                return json.dumps(
                    {"hypocrisy_perceived": True, "trust_change": -1.0, "action": "post_review", "content": "Bad!",
                     "reason": "Mock"})

        router = Mock()

    for ag in agents: ag._model = router

    # 🧹 强制清场
    print("🧹 正在清理 Agent 初始状态...")
    for ag in agents:
        state_plugin = ag.get_component("state")._plugin
        await state_plugin.set_state("incoming_messages", [])
        await state_plugin.set_state("observations", [])
        await state_plugin.set_state("latest_thought", None)
    print("✅ 状态清理完成，仿真准备就绪。")

    total_ticks = 10

    for tick in range(1, total_ticks + 1):
        print(f"\n⏰ === Tick {tick} ===")

        # 事件 A：T=1 正面品牌建设 (建立信任锚点)
        if tick == 1:
            print("📣 [Event] 厂商发布正面权威广告 (信任建立)")
            # 关键：内容要包含 Deep Green 喜欢的 "Certified", "Verified" 等词
            positive_ad = {
                "source": "EcoBrand_Official",
                "content": "We are proud to announce that EcoBottle is now officially certified by the Global Green Standard (GGS). Verified sustainability you can trust.",
                "type": "official_advertisement"
            }
            # 全员广播
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                inbox = getattr(s_plugin, "state_data", {}).get("incoming_messages", [])
                await s_plugin.set_state("incoming_messages", list(inbox) + [positive_ad])

        # 事件 B：T=4 漂绿危机爆发 (信任崩塌点)
        elif tick == 4:
            print("📣 [Event] 厂商发布涉嫌漂绿的虚假广告 (信任危机)")
            # 关键：内容包含 "No Proof", "Vague"
            greenwashing_ad = {
                "source": "EcoBrand_Official",
                "content": "Our new edition is 100% Planet-Friendly! (Internal study, no external certification available yet).",
                "type": "official_advertisement"
            }
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                inbox = getattr(s_plugin, "state_data", {}).get("incoming_messages", [])
                await s_plugin.set_state("incoming_messages", list(inbox) + [greenwashing_ad])

        # 执行循环 (保持不变)
        for ag in agents:
            await ag.get_component("perceive").execute(tick)
            await ag.get_component("reflect").execute(tick)

        for ag in agents:
            await ag.get_component("plan").execute(tick)
            await ag.get_component("invoke").execute(tick)

        # --- 数据记录 ---
        trust_list = []
        for ag in agents:
            state_plugin = ag.get_component("state")._plugin
            s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
            profile_plugin = ag.get_component("profile")._plugin
            p_data = getattr(profile_plugin, "profile_data", getattr(profile_plugin, "_profile_data", {}))
            agent_type = p_data.get("psychology", {}).get("environmental_involvement", "Unknown")

            trust = s_data.get("trust_score", 5.0)
            plan = s_data.get("plan_result", {})
            action = plan.get("action", "none") if plan else "none"
            thought = s_data.get("latest_thought", {})
            hypocrisy = thought.get("hypocrisy_perceived", False) if thought else False

            writer.writerow([tick, ag.agent_id, agent_type, trust, action, hypocrisy])
            trust_list.append(trust)

        avg_trust = np.mean(trust_list)
        print(f"📊 平均信任: {avg_trust:.2f}")

    csv_file.close()
    print(f"\n✅ 仿真结束。数据已保存至 {csv_path}")


if __name__ == "__main__":
    asyncio.run(run())