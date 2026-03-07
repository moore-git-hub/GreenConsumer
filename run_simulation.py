import sys
import os
import asyncio
import yaml
import json
import csv
import datetime
import numpy as np
import networkx as nx
import logging

# === 强制屏蔽 Agent-Kernel 底层 INFO 日志 ===
logging.getLogger("agentkernel_standalone").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
# ============================================

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

    # --- 准备日志文件 ---
    results_dir = os.path.join(current_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(results_dir, f"simulation_log_{timestamp}.csv")
    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    writer.writerow(["Tick", "AgentID", "Type", "TrustScore", "Action", "Thought_Hypocrisy"])

    thought_path = os.path.join(results_dir, f"thoughts_log_{timestamp}.csv")
    thought_file = open(thought_path, "w", newline="", encoding="utf-8")
    thought_writer = csv.writer(thought_file)
    thought_writer.writerow(["Tick", "AgentID", "AgentType", "Hypocrisy", "TrustChange", "Reasoning"])
    print(f"📂 日志文件已创建。")

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
    for conf in agent_configs:
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

    await net_plugin.init()
    net_plugin.register_agents(agents)

    try:
        with open(os.path.join(current_dir, "configs/models_config.yaml"), "r") as f:
            models_conf = yaml.safe_load(f)
        router = ModelRouter(AsyncModelRouter(models_conf))
        print("🧠 LLM 引擎已就绪。")
    except:
        print("⚠️ 使用 Mock Router")

        class Mock:
            async def chat(self, p):
                return json.dumps(
                    {"hypocrisy_perceived": True, "trust_change": -1.0, "importance": 5.0, "reasoning": "Mock"})

        router = Mock()

    for ag in agents: ag._model = router

    # 🧹 状态初始化
    print("🧹 正在初始化 Agent 状态...")
    for ag in agents:
        state_plugin = ag.get_component("state")._plugin
        profile_plugin = ag.get_component("profile")._plugin
        p_data = getattr(profile_plugin, "profile_data", getattr(profile_plugin, "_profile_data", {}))

        init_trust = p_data.get("initial_trust", 5.0)
        budget = p_data.get("budget", 100)

        await state_plugin.set_state("trust_score", float(init_trust))
        await state_plugin.set_state("budget", float(budget))
        await state_plugin.set_state("incoming_messages", [])
        await state_plugin.set_state("observations", [])
        await state_plugin.set_state("latest_thought", None)

    print("✅ 状态初始化完成 (Trust & Budget 已同步)。")

    # ==========================================
    # 🚀 唯一仿真主循环
    # ==========================================
    TOTAL_TICKS = 20
    BURN_IN_TICKS = 5  # 预热期: 绝对禁止购买

    ENTERPRISE_STRATEGY = {
        2: {"source": "EcoBrand_Official", "content": "【产品预热】最新一代100%可降解材料即将上市！"},
        6: {"source": "EcoBrand_Official", "content": "【正式发售】产品发售，获国际绿色环保认证(GGS)。"},
        10: {"source": "Whistleblower", "content": "【黑料曝光】所谓GGS认证系内部伪造，生产线存在严重水污染！"},
        14: {"source": "EcoBrand_PR", "content": "【企业澄清】前员工造谣，已发律师函，我们的材料经得起检验。"},
        17: {"source": "KOL_Environmentalist", "content": "【KOL实地测评】受邀参观工厂，污染传闻为虚，治污系统确在运作。"}
    }

    for tick in range(1, TOTAL_TICKS + 1):
        print(f"\n⏰ === Tick {tick} ===")

        # 1. 注入时间感知与动作限制
        if tick <= BURN_IN_TICKS:
            time_context = f"产品上市预热中，当前是预热期第 {tick} 天。不允许购买。"
        else:
            time_context = f"产品已正式发售第 {tick - BURN_IN_TICKS} 天。"

        # 2. 触发全局信息干预
        if tick in ENTERPRISE_STRATEGY:
            event = ENTERPRISE_STRATEGY[tick]
            print(f"📣 [全局干预注入] {event['source']}: {event['content']}")
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                inbox = getattr(s_plugin, "state_data", {}).get("incoming_messages", [])
                await s_plugin.set_state("incoming_messages", list(inbox) + [event])

        # 3. Agent 执行感知与认知
        for ag in agents:
            s_plugin = ag.get_component("state")._plugin
            await s_plugin.set_state("time_context", time_context)
            await s_plugin.set_state("current_tick", tick)  # 同步tick供RAG使用

            await ag.get_component("perceive").execute(tick)
            await ag.get_component("reflect").execute(tick)

        # 4. Agent 执行计划与行动 (预热期阻断 Plan)
        for ag in agents:
            if tick > BURN_IN_TICKS:
                await ag.get_component("plan").execute(tick)
            await ag.get_component("invoke").execute(tick)

        # 5. 数据记录
        trust_list = []
        for ag in agents:
            state_plugin = ag.get_component("state")._plugin
            profile_plugin = ag.get_component("profile")._plugin
            s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
            p_data = getattr(profile_plugin, "profile_data", getattr(profile_plugin, "_profile_data", {}))

            agent_type = p_data.get("psychology", {}).get("environmental_involvement", "Unknown")
            trust = s_data.get("trust_score", 5.0)

            plan = s_data.get("plan_result", {})
            action = plan.get("action", "none") if plan else "none"

            thought = s_data.get("latest_thought")
            hypocrisy = thought.get("hypocrisy_perceived", False) if thought else False

            writer.writerow([tick, ag.agent_id, agent_type, trust, action, hypocrisy])
            trust_list.append(trust)

            if thought:
                reasoning = thought.get("reasoning", "No detail")
                trust_change = thought.get("trust_change", 0.0)
                thought_writer.writerow([tick, ag.agent_id, agent_type, hypocrisy, trust_change, reasoning])

        avg_trust = np.mean(trust_list)
        print(f"📊 平均信任: {avg_trust:.2f}")

    # 清理工作
    csv_file.close()
    thought_file.close()
    print(f"\n✅ 仿真结束。")


if __name__ == "__main__":
    asyncio.run(run())