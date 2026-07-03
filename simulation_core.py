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
from generate_data import FORRESTER_2026_CLUSTERS, SOCIAL_MEDIA_ROLES, ROLE_PROBS, SOCIAL_ROLES  # kept for reference

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
        "Oatly's Barista Edition oat milk is expanding rapidly across the US. "
        "The brand now supplies over 10,000 coffee shops in North America, up from 2,000 two years ago. "
        "Oatly holds B Corp certification (score: 93.4/200, above the 80-point qualifying threshold) "
        "and publishes an annual sustainability report disclosing its carbon footprint at 0.44 kg CO₂e "
        "per liter — roughly 80% lower than conventional dairy milk. "
        "The brand's signature ad 'It's like milk, but made for humans' goes viral with 4.2 million "
        "organic shares. Independent barista forums rate Oatly Barista as the #1 plant-based milk "
        "for latte art, citing its consistent micro-foam texture. Oatly is widely regarded as the "
        "most credible and transparent brand in the sustainable food sector."
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
    """
    内联生成 Agent profiles（不写文件）。
    与 generate_data.py 的配额制逻辑保持一致：按 AGENT_QUOTA 比例分配群体，
    然后随机打乱顺序，保证同 seed 下结果可复现。
    """
    from generate_data import AGENT_QUOTA, FORRESTER_2026_CLUSTERS, SOCIAL_MEDIA_ROLES, ROLE_PROBS, SOCIAL_ROLES

    rng_random = random_module.Random(seed)
    rng_np     = np.random.RandomState(seed)

    # 按配额比例计算每个类型的 Agent 数量
    total_quota = sum(AGENT_QUOTA.values())
    quota = {k: max(1, round(v / total_quota * num_agents)) for k, v in AGENT_QUOTA.items()}
    # 误差修正：多余的补到 Dormant_Greens（占比最大，影响最小）
    quota["Dormant_Greens"] += num_agents - sum(quota.values())

    # 按配额展开为 cluster_id 列表并随机打乱
    cluster_order = []
    for cid, count in quota.items():
        cluster_order.extend([cid] * count)
    rng_random.shuffle(cluster_order)

    cluster_map = {c["cluster_id"]: c for c in FORRESTER_2026_CLUSTERS}
    profiles = []

    for i, cluster_id in enumerate(cluster_order):
        agent_id    = f"Consumer_{i:03d}"
        base_cluster = cluster_map[cluster_id]
        role         = rng_np.choice(SOCIAL_ROLES, p=ROLE_PROBS)

        persona_prompt = base_cluster["persona"] + SOCIAL_MEDIA_ROLES[role]

        profiles.append({
            "id":   agent_id,
            "name": agent_id,
            "psychology": {
                "cluster_type": base_cluster["cluster_id"],
                "social_role":  role,
            },
            "persona": persona_prompt,
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

    # ── 2. 生成 Agent profiles 并写入临时文件，让 Builder 正常解析 ──
    # 这样完全复用框架的 Pydantic 验证路径，避免手工构造 AgentComponentConfig 对象
    profiles = _generate_profiles_inline(config.num_agents, config.random_seed)

    tmp_profiles_path = os.path.join(current_dir, "data", "agents", "_tmp_profiles.jsonl")
    os.makedirs(os.path.dirname(tmp_profiles_path), exist_ok=True)

    # 备份原始 profiles.jsonl，写入临时数据
    original_profiles_path = os.path.join(current_dir, "data", "agents", "profiles.jsonl")
    original_backup_path   = os.path.join(current_dir, "data", "agents", "profiles.jsonl.bak")
    profiles_swapped = False
    try:
        if os.path.exists(original_profiles_path):
            os.rename(original_profiles_path, original_backup_path)
        with open(original_profiles_path, "w", encoding="utf-8") as f:
            for p in profiles:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        profiles_swapped = True

        # ── 3. Builder 正常解析（走 Pydantic 验证，生成真实 AgentConfig 对象）──
        builder = Builder(current_dir, resource_maps)
        builder._load_data_into_config()
        agent_configs = builder.config.agents

    finally:
        # 恢复原始 profiles.jsonl
        if profiles_swapped:
            if os.path.exists(original_profiles_path):
                os.remove(original_profiles_path)
            if os.path.exists(original_backup_path):
                os.rename(original_backup_path, original_profiles_path)

    # ── 4. 构建环境与网络插件（不在此处建图，延迟到 Agents 初始化后） ──
    env = Environment()
    net_plugin = SocialNetworkPlugin()
    net_comp = EnvironmentComponent()
    net_comp.plugin = net_plugin
    net_comp._plugin = net_plugin
    net_plugin.component = net_comp

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

    # 网络构建：调用 register_agents() 统一走有向 BA 网络逻辑
    # 与 run_simulation.py 路径行为完全一致
    net_plugin.register_agents(agents, seed=config.random_seed)

    # ── 6. 初始化 LLM Router ────────────────────────────────────────
    try:
        with open(os.path.join(current_dir, "configs/models_config.yaml"), "r") as f:
            models_conf = yaml.safe_load(f)
        router = ModelRouter(AsyncModelRouter(models_conf))
    except Exception:
        class Mock:
            async def chat(self, prompt):
                # Reflect 层特征：含 trust_change_affective 或 hypocrisy_perceived 字段
                # Plan 层特征：含 is_buying 和 is_posting 字段
                # 注意：不再用 "System 1" 识别（Prompt 已移除该技术标签）
                if "trust_change_affective" in prompt or "hypocrisy_perceived" in prompt:
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
        await state_plugin.set_state("last_observations", [])   # Plan 层读取的只读快照
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
    target_nodes = select_target_nodes(net_plugin.graph, config.channel_factor, config.budget_k, config.random_seed)
    injector.set_target_nodes(target_nodes)

    # ── 9. 仿真主循环 ───────────────────────────────────────────────
    trust_trajectory = []
    conversion_trajectory = []
    cumulative_buyers = set()
    # 逐 Agent 逐 Tick 详细记录（供后续分析使用）
    agent_records = []    # List[dict]，每条一个 Agent 在一个 Tick 的完整快照
    tick_post_counts = [] # 每 Tick 发帖总数（用于社交活跃度分析）
    tick_buy_counts  = [] # 每 Tick 新增购买数

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
        injected_count = await injector.inject(agents, tick)
        # ── 澄清注入当天：同步更新 current_news，让 Plan 层感知到澄清事件 ──
        # 否则 Plan 层会把澄清当成"平静日"，quiet_ticks 继续累加，
        # 遗忘曲线把信任往 baseline 拉，而澄清的正向冲击被抵消
        if injected_count > 0:
            clarification_headline = (
                "[Enterprise Clarification] The brand has issued an official statement "
                "addressing the controversy. The company responds to the greenwashing allegations."
            )
            for ag in agents:
                if ag.agent_id in injector.target_nodes:
                    s_plugin = ag.get_component("state")._plugin
                    # current_news 更新 → Plan 层 is_quiet_day=False → quiet_ticks 不累加
                    await s_plugin.set_state("current_news", clarification_headline)

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
        tick_posts = 0
        for ag in agents:
            s_data = getattr(ag.get_component("state")._plugin, "state_data",
                             getattr(ag.get_component("state")._plugin, "_state_data", {}))
            p_data = getattr(ag.get_component("profile")._plugin, "_profile_data",
                             getattr(ag.get_component("profile")._plugin, "profile_data", {}))
            trust = float(s_data.get("trust_score", 5.0))
            trust_list.append(trust)

            plan    = s_data.get("plan_result", {}) or {}
            thought = s_data.get("latest_thought", {}) or {}
            cluster = p_data.get("psychology", {}).get("cluster_type", "Unknown")
            role    = p_data.get("psychology", {}).get("social_role", "Unknown")
            is_buying_flag  = bool(plan.get("is_buying", False))
            is_posting_flag = bool(plan.get("is_posting", False))

            if is_buying_flag:
                tick_buys += 1
                cumulative_buyers.add(ag.agent_id)
            if is_posting_flag:
                tick_posts += 1

            # 逐 Agent 详细记录
            agent_records.append({
                "exp_id":            config.exp_id,
                "tick":              tick,
                "agent_id":          ag.agent_id,
                "cluster_type":      cluster,
                "social_role":       role,
                "trust_score":       round(trust, 4),
                "baseline_trust":    round(float(s_data.get("baseline_trust", trust)), 4),
                "trust_after_decay": round(float(plan.get("trust_after_decay", trust)), 4),
                "affective_change":  round(float(plan.get("affective_change", 0.0)), 4),
                "shock_anchor":      round(float(plan.get("shock_anchor", trust)), 4),
                "quiet_ticks":       int(plan.get("quiet_ticks", 0)),
                "decay_lambda":      float(plan.get("decay_lambda", 0.0)),
                "is_buying":         is_buying_flag,
                "is_posting":        is_posting_flag,
                "post_content":      str(plan.get("post_content", ""))[:200],
                "hypocrisy_perceived": bool(thought.get("hypocrisy_perceived", False)),
                "importance":          float(thought.get("importance", 0.0)),
                "reasoning":           str(thought.get("reasoning", ""))[:300],
                "has_global_event":    tick in ENTERPRISE_STRATEGY,
                "has_clarification":   (config.clarification_tick == tick),
                "cumulative_buyers":   len(cumulative_buyers),
            })

        tick_post_counts.append(tick_posts)
        tick_buy_counts.append(tick_buys)

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

    # ── 10. 计算多维指标 ─────────────────────────────────────────────
    metrics = compute_metrics(
        trust_trajectory, conversion_trajectory,
        scandal_tick=config.scandal_tick,
        total_ticks=config.total_ticks,
        clarification_tick=config.clarification_tick,
    )

    print(f"📊 [{config.exp_id}] "
          f"ΔRecovery={metrics.delta_recovery:.3f} | "
          f"AUC={metrics.auc_post_scandal:.4f} | "
          f"Speed={metrics.recovery_speed:.4f} | "
          f"Steady={metrics.steady_state_score:.2f} | "
          f"ClarEffect={metrics.clarification_effect:+.3f}")

    return {
        "exp_id": config.exp_id,
        "config": config.to_dict(),
        "metrics": metrics,
        "trust_trajectory": trust_trajectory,
        "conversion_trajectory": conversion_trajectory,
        "agent_records": agent_records,       # 逐 Agent 逐 Tick 详细数据
        "tick_post_counts": tick_post_counts, # 每 Tick 发帖数
        "tick_buy_counts":  tick_buy_counts,  # 每 Tick 新增购买数
    }
