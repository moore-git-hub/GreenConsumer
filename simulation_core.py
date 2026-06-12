"""
simulation_core.py — 可复用仿真核心函数

从 run_simulation.py 提取的核心逻辑，接受 ExperimentConfig 参数，
返回结构化结果（含逐 Tick 轨迹和三目标指标）。

调用方式：
    from simulation_core import run_simulation_core
    result = await run_simulation_core(config)
"""
import sys
import os
import asyncio
import yaml
import json
import random as random_module
import numpy as np
import networkx as nx
import logging

# 屏蔽底层日志
logging.getLogger("agentkernel_standalone").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
standalone_path = os.path.join(project_root, "packages", "agentkernel-standalone")
if os.path.exists(standalone_path) and standalone_path not in sys.path:
    sys.path.insert(0, standalone_path)
if current_dir not in sys.path:
    sys.path.append(current_dir)

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

from plugins.agent.profile.GreenProfilePlugin import GreenProfilePlugin
from plugins.agent.state.GreenStatePlugin import GreenStatePlugin
from plugins.agent.perceive.GreenPerceivePlugin import GreenPerceivePlugin
from plugins.agent.reflect.GreenCognitionPlugin import GreenCognitionPlugin
from plugins.agent.plan.ConsumerPlanPlugin import ConsumerPlanPlugin
from plugins.agent.invoke.GreenInvokePlugin import GreenInvokePlugin
from plugins.environment.network.SocialNetworkPlugin import SocialNetworkPlugin

from experiment_config import ExperimentConfig
from node_selector import select_target_nodes
from clarification_injector import ClarificationInjector
from metrics_calculator import compute_metrics, SimulationMetrics
from generate_data import FORRESTER_2026_CLUSTERS, SOCIAL_MEDIA_ROLES, ROLE_PROBS, SOCIAL_ROLES

resource_maps = {
    "agent_components": {
        "profile": ProfileComponent, "state": StateComponent,
        "perceive": PerceiveComponent, "reflect": ReflectComponent,
        "plan": PlanComponent, "invoke": InvokeComponent
    },
    "agent_plugins": {
        "GreenProfilePlugin": GreenProfilePlugin, "GreenStatePlugin": GreenStatePlugin,
        "GreenPerceivePlugin": GreenPerceivePlugin, "GreenCognitionPlugin": GreenCognitionPlugin,
        "ConsumerPlanPlugin": ConsumerPlanPlugin, "GreenInvokePlugin": GreenInvokePlugin
    },
    "system_components": {"timer": Timer, "messager": Messager},
    "environment_components": {}, "action_components": {}, "controller": None
}

# Oatly 真实事件时间轴（基于公开报道）
ENTERPRISE_STRATEGY = {
    1: (
        "Oatly's Barista Edition oat milk is taking US coffee shops by storm, "
        "with baristas praising its perfect micro-foam for lattes. The brand's quirky "
        "anti-dairy ads — featuring slogans like 'It's like milk, but made for humans' "
        "and 'Wow, no cow' — go viral. Demand far exceeds supply, with long waitlists "
        "at cafes across the country. Oatly is widely celebrated as the pioneer of "
        "the sustainable, plant-based milk movement."
    ),
    5: (
        "BREAKING: Oatly sold a 10% stake ($200 million) to an investment group led by "
        "Blackstone Group in July 2020. Blackstone is the world's largest private equity "
        "firm, directly linked to Amazon deforestation in Brazil, and its CEO Stephen "
        "Schwarzman is a major donor to Trump's political campaigns opposing climate policy. "
        "Activists on Twitter are trending #BoycottOatly, calling this a 'sell-out' and "
        "'enabling Blackstone to greenwash its climate-damaging portfolio.' "
        "Critics say Oatly has 'sold its soul for growth capital.' "
        "Oatly defended the deal, saying the investment would help them scale sustainably — "
        "but many long-time fans feel profoundly betrayed."
    ),
    10: (
        "HEALTH BACKLASH: A popular nutrition blogger's post exposing Oatly's ingredient "
        "list goes viral. Critics highlight that Oatly Barista contains rapeseed (canola) "
        "oil and high levels of rapidly digestible starch from enzymatic processing, "
        "which can cause significant blood sugar spikes — one analysis showed a glycemic "
        "response comparable to Coca-Cola. The post has been shared over 100,000 times. "
        "Many consumers feel misled: they bought Oatly thinking it was a health food, "
        "but are now questioning whether it is 'just glorified sugar water.' "
        "Note: mainstream nutrition scientists largely dispute these claims, but the "
        "viral perception damage is already spreading across social media."
    ),
    15: (
        "INVESTOR LAWSUIT & SHORT SELLER ATTACK: Just weeks after Oatly's May 2021 "
        "Nasdaq IPO (OTLY), activist short-seller Spruce Point Capital publishes a "
        "devastating 68-page report accusing Oatly of: overstating revenue and margins, "
        "exaggerating its sustainability impact in official filings, misleading investors "
        "about growth in China, and producing abnormally high wastewater at its New "
        "Jersey plant. Oatly's stock crashes 30% in a single day. "
        "A class-action securities lawsuit is filed. "
        "Oatly later settles a greenwashing lawsuit for $9.25 million in 2024. "
        "Consumer trust in the brand hits a new low as the IPO scandal reinforces "
        "earlier fears that Oatly was always more about marketing than sustainability."
    ),
}


def _generate_profiles_inline(num_agents: int, seed: int) -> list:
    """内联生成 Agent profiles（不写文件）"""
    rng_np = np.random.RandomState(seed)
    rng_py = random_module.Random(seed)

    cluster_probs = [c["prob"] for c in FORRESTER_2026_CLUSTERS]
    profiles = []

    for i in range(num_agents):
        agent_id = f"Consumer_{i:03d}"
        role = rng_np.choice(SOCIAL_ROLES, p=ROLE_PROBS)
        base_cluster = rng_py.choices(FORRESTER_2026_CLUSTERS, weights=cluster_probs, k=1)[0]
        age = rng_py.randint(18, 60)

        persona_blocks = [
            f"You are a {age}-year-old consumer.",
            base_cluster["persona"],
            SOCIAL_MEDIA_ROLES[role]
        ]
        persona_prompt = "\n\n".join(persona_blocks)

        profiles.append({
            "id": agent_id,
            "name": agent_id,
            "demographics": {"age": age, "income": base_cluster["income"]},
            "psychology": {
                "cluster_type": base_cluster["cluster_id"],
                "big_five": base_cluster["traits"],
                "social_role": role
            },
            "persona": persona_prompt
        })

    return profiles


async def run_simulation_core(config: ExperimentConfig) -> dict:
    """
    可复用仿真核心函数。

    Args:
        config: ExperimentConfig 实例

    Returns:
        {
            "exp_id": str,
            "config": dict,
            "metrics": SimulationMetrics,
            "trust_trajectory": List[float],
            "conversion_trajectory": List[float],
        }
    """
    # ── 1. 设置随机种子 ──────────────────────────────────────────────
    random_module.seed(config.random_seed)
    np.random.seed(config.random_seed)

    # ── 2. 生成 Agent profiles（内联，不写文件） ─────────────────────
    profiles = _generate_profiles_inline(config.num_agents, config.random_seed)

    # ── 3. 初始化框架 ────────────────────────────────────────────────
    builder = Builder(current_dir, resource_maps)
    builder._load_data_into_config()

    # 覆盖 agent_configs 为内联生成的 profiles
    # 需要构造与 Builder 兼容的 agent config 对象
    from types import SimpleNamespace
    agent_configs = []
    for p in profiles:
        conf = SimpleNamespace()
        conf.id = p["id"]
        conf.component_order = ["profile", "state", "perceive", "reflect", "plan", "invoke"]
        conf.components = {
            "profile": {"plugin": {"GreenProfilePlugin": {"profile_data": p}}},
            "state": {"plugin": {"GreenStatePlugin": {}}},
            "perceive": {"plugin": {"GreenPerceivePlugin": {}}},
            "reflect": {"plugin": {"GreenCognitionPlugin": {}}},
            "plan": {"plugin": {"ConsumerPlanPlugin": {}}},
            "invoke": {"plugin": {"GreenInvokePlugin": {}}},
        }
        agent_configs.append(conf)

    # ── 4. 构建环境与网络 ────────────────────────────────────────────
    env = Environment()
    net_plugin = SocialNetworkPlugin()
    net_comp = EnvironmentComponent()
    net_comp.plugin = net_plugin
    net_comp._plugin = net_plugin
    net_plugin.component = net_comp

    # 构建网络（传入 seed）
    n = config.num_agents
    if n < 5:
        graph = nx.complete_graph(n)
    else:
        graph = nx.barabasi_albert_graph(n, m=2, seed=config.random_seed)
    mapping = {i: f"Consumer_{i:03d}" for i in range(n)}
    graph = nx.relabel_nodes(graph, mapping)
    net_plugin.graph = graph
    net_plugin.agent_registry = {}

    # ── 5. 初始化 Agents ─────────────────────────────────────────────
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

    net_plugin.agent_registry = {a.agent_id: a for a in agents}

    # ── 6. 初始化 LLM Router ────────────────────────────────────────
    try:
        with open(os.path.join(current_dir, "configs/models_config.yaml"), "r") as f:
            models_conf = yaml.safe_load(f)
        router = ModelRouter(AsyncModelRouter(models_conf))
    except Exception:
        class Mock:
            async def chat(self, prompt):
                # 根据 Prompt 内容区分 Reflect 层和 Plan 层的响应
                if "System 1" in prompt or "trust_change_affective" in prompt:
                    return json.dumps({
                        "hypocrisy_perceived": True,
                        "trust_change_affective": -1.5,
                        "importance": 7.0,
                        "reasoning": "Mock: I feel betrayed by this brand."
                    })
                else:
                    return json.dumps({
                        "is_buying": False,
                        "is_posting": True,
                        "post_content": "I can't believe this brand betrayed us!",
                        "reason": "Mock: Trust is too low to buy."
                    })
        router = Mock()

    for ag in agents:
        ag._model = router

    # ── 7. 初始化 Agent 状态 ─────────────────────────────────────────
    # 各消费者类型的初始信任基线（差异化，而非统一 5.0）
    INITIAL_TRUST_MAP = {
        "Active_Greens":     8.0,
        "Convenient_Greens": 6.5,
        "Dormant_Greens":    5.5,
        "Non_Greens":        5.0,
    }
    for ag in agents:
        state_plugin = ag.get_component("state")._plugin
        await state_plugin.set_state("incoming_messages", [])
        await state_plugin.set_state("observations", [])
        await state_plugin.set_state("latest_thought", None)

        # 根据消费者类型设置差异化初始信任
        p_data = getattr(ag.get_component("profile")._plugin, "_profile_data",
                         getattr(ag.get_component("profile")._plugin, "profile_data", {}))
        cluster_type = p_data.get("psychology", {}).get("cluster_type", "")
        initial_trust = INITIAL_TRUST_MAP.get(cluster_type, 5.5)
        await state_plugin.set_state("trust_score", initial_trust)
        await state_plugin.set_state("baseline_trust", initial_trust)
        await state_plugin.set_state("trust_score_initialized", True)

    # ── 8. 初始化澄清注入器 ─────────────────────────────────────────
    injector = ClarificationInjector(config)
    target_nodes = select_target_nodes(graph, config.channel_factor, config.budget_k, config.random_seed)
    injector.set_target_nodes(target_nodes)

    # ── 9. 仿真主循环 ───────────────────────────────────────────────
    trust_trajectory = []
    conversion_trajectory = []
    cumulative_buyers = set()

    for tick in range(1, config.total_ticks + 1):
        # 9.1 全局事件注入
        if tick in ENTERPRISE_STRATEGY:
            event_text = ENTERPRISE_STRATEGY[tick]
            event_msg = {"source": "Global News", "content": event_text}
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                s_data = getattr(s_plugin, "state_data", getattr(s_plugin, "_state_data", {}))
                inbox = s_data.get("incoming_messages", [])
                await s_plugin.set_state("incoming_messages", list(inbox) + [event_msg])
                await s_plugin.set_state("current_news", event_text)
        else:
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                await s_plugin.set_state("current_news", "")

        # 9.2 企业澄清注入（在 Perceive 之前）
        await injector.inject(agents, tick)

        # 9.3 认知管线
        for ag in agents:
            s_plugin = ag.get_component("state")._plugin
            await s_plugin.set_state("time_context", f"Day {tick} of the simulation.")
            await s_plugin.set_state("current_tick", tick)
            await ag.get_component("perceive").execute(tick)
            await ag.get_component("reflect").execute(tick)

        # 9.4 计划与执行
        for ag in agents:
            await ag.get_component("plan").execute(tick)
            await ag.get_component("invoke").execute(tick)

        # 9.5 数据结算
        trust_list = []
        tick_buys = 0
        for ag in agents:
            s_data = getattr(ag.get_component("state")._plugin, "state_data",
                             getattr(ag.get_component("state")._plugin, "_state_data", {}))
            trust = float(s_data.get("trust_score", 5.0))
            trust_list.append(trust)

            plan = s_data.get("plan_result", {})
            if plan.get("is_buying", False):
                tick_buys += 1
                cumulative_buyers.add(ag.agent_id)

        avg_trust = np.mean(trust_list)
        conversion_rate = len(cumulative_buyers) / len(agents)
        trust_trajectory.append(round(avg_trust, 4))
        conversion_trajectory.append(round(conversion_rate, 4))

        # 9.6 社交路由
        tick_posts_dict = {}
        for ag in agents:
            s_data = getattr(ag.get_component("state")._plugin, "state_data",
                             getattr(ag.get_component("state")._plugin, "_state_data", {}))
            plan = s_data.get("plan_result", {})
            if plan.get("is_posting", False) and plan.get("post_content", "").strip():
                tick_posts_dict[ag.agent_id] = plan["post_content"].strip()

        for ag in agents:
            state_plugin = ag.get_component("state")._plugin
            await state_plugin.set_state("incoming_messages", [])

        for author_id, content in tick_posts_dict.items():
            social_content = f'[Social Media Feed] Connection {author_id} posted: "{content}"'
            await net_plugin.broadcast_message(author_id, social_content)

        # 信箱限流
        for ag in agents:
            state_plugin = ag.get_component("state")._plugin
            msgs = state_plugin.get_state_sync("incoming_messages") or []
            if len(msgs) > 3:
                await state_plugin.set_state("incoming_messages", msgs[-3:])

    # ── 10. 计算三目标指标 ───────────────────────────────────────────
    metrics = compute_metrics(
        trust_trajectory, conversion_trajectory,
        scandal_tick=config.scandal_tick,
        total_ticks=config.total_ticks
    )

    print(f"📊 [{config.exp_id}] T80={metrics.t80} | "
          f"Steady={metrics.steady_state_score:.2f} | "
          f"Recovery={metrics.recovery_rate:.2f}")

    return {
        "exp_id": config.exp_id,
        "config": config.to_dict(),
        "metrics": metrics,
        "trust_trajectory": trust_trajectory,
        "conversion_trajectory": conversion_trajectory,
    }
