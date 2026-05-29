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
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd

# === 强制屏蔽 Agent-Kernel 底层 INFO 日志 ===
logging.getLogger("agentkernel_standalone").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# 绘图字体防乱码设置 (兼容中英文)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

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

    # 1. 基础动作日志（新增双过程分解字段：TrustAfterDecay / AffectiveChange / DecayLambda）
    csv_path = os.path.join(results_dir, f"simulation_log_{timestamp}.csv")
    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    writer.writerow([
        "Tick", "AgentID", "Type",
        "TrustScore", "BaselineTrust", "TrustAfterDecay", "AffectiveChange",
        "DecayLambda", "QuietTicks", "Action", "Thought_Hypocrisy"
    ])

    # 2. 详细思维日志（新增 AffectiveChange 替代旧的 TrustChange）
    thought_path = os.path.join(results_dir, f"thoughts_log_{timestamp}.csv")
    thought_file = open(thought_path, "w", newline="", encoding="utf-8")
    thought_writer = csv.writer(thought_file)
    thought_writer.writerow([
        "Tick", "AgentID", "AgentType",
        "Hypocrisy", "AffectiveChange", "TrustAfterDecay", "FinalTrust", "Reasoning"
    ])

    # 3. 宏观 KPI 日志
    macro_path = os.path.join(results_dir, f"macro_metrics_{timestamp}.csv")
    macro_file = open(macro_path, "w", newline="", encoding="utf-8")
    macro_writer = csv.writer(macro_file)
    macro_writer.writerow(["Tick", "AvgTrust", "NewBuys", "CumulativeBuys", "ConversionRate", "PostCount"])
    print(f"📂 数据收集流管道已建立。")

    # 注册 finally 保证文件在任何情况下都能关闭
    _open_files = [csv_file, thought_file, macro_file]

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

    # 保存网络拓扑用于后续级联推导（兼容 networkx >= 3.0 的 edges 参数变更）
    graph_path = os.path.join(results_dir, f"network_graph_{timestamp}.json")
    try:
        graph_data = nx.node_link_data(net_plugin.graph, edges="links")
    except TypeError:
        graph_data = nx.node_link_data(net_plugin.graph)
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f)

    try:
        with open(os.path.join(current_dir, "configs/models_config.yaml"), "r") as f:
            models_conf = yaml.safe_load(f)
        router = ModelRouter(AsyncModelRouter(models_conf))
        print("🧠 LLM 引擎已就绪。")
    except Exception:
        print("⚠️ 使用 Mock Router")

        class Mock:
            async def chat(self, prompt):
                # 根据 Prompt 内容区分 Reflect 层和 Plan 层的响应
                if "System 1" in prompt or "trust_change_affective" in prompt:
                    # Reflect 层 Mock：返回情绪冲击
                    return json.dumps({
                        "hypocrisy_perceived": True,
                        "trust_change_affective": -1.5,
                        "importance": 7.0,
                        "reasoning": "Mock: I feel betrayed by this brand."
                    })
                else:
                    # Plan 层 Mock：返回行为决策
                    return json.dumps({
                        "is_buying": False,
                        "is_posting": True,
                        "post_content": "I can't believe this brand betrayed us!",
                        "reason": "Mock: Trust is too low to buy."
                    })

        router = Mock()

    for ag in agents: ag._model = router

    print("初始化 Agent 状态")
    # 各消费者类型的初始信任基线
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

        # 根据消费者类型设置差异化初始信任（而非统一 5.0）
        p_data = getattr(ag.get_component("profile")._plugin, "_profile_data",
                         getattr(ag.get_component("profile")._plugin, "profile_data", {}))
        cluster_type = p_data.get("psychology", {}).get("cluster_type", "")
        initial_trust = INITIAL_TRUST_MAP.get(cluster_type, 5.5)
        await state_plugin.set_state("trust_score", initial_trust)
        await state_plugin.set_state("baseline_trust", initial_trust)
        await state_plugin.set_state("trust_score_initialized", True)

    # ==========================================
    # 🚀 仿真主循环
    # ==========================================
    TOTAL_TICKS = 30  # 延长至30期，观察长尾遗忘曲线效应

    # ==========================================
    # 🕒 Oatly 真实时间轴干预策略 (宏观环境刺激)
    # ==========================================
    ENTERPRISE_STRATEGY = {
        1: (
            "Oatly launches a quirky, eco-friendly ad campaign highlighting their Barista edition oat milk's perfect micro-foam. "
            "The slogan is: 'It's like milk, but made for humans.'"
        ),
        5: (
            "BREAKING NEWS & SCANDAL: It is publicly revealed that Oatly accepted a $200 million investment from Blackstone Group, "
            "a controversial private equity firm heavily linked to deforestation in the Amazon rainforest and backing anti-climate politicians. "
            "Environmentalists are furious, calling it a massive betrayal and severe greenwashing."
        ),
        10: (
            "VIRAL HEALTH CONTROVERSY: A top nutrition influencer posts a viral video exposing Oatly's ingredients. "
            "They claim Oatly is 'essentially sugar water' packed with inflammatory canola oil (rapeseed oil) that causes massive blood glucose spikes. "
            "Consumers are starting to worry about the health impacts."
        )
    }

    cumulative_buyers = set()  # 追踪历史购买者

    for tick in range(1, TOTAL_TICKS + 1):
        print(f"\n" + "=" * 40)
        print(f" ⏳ === Simulation Tick {tick} ===")
        print("=" * 40)

        # 1. 宏观时间上下文
        time_context = f"Current Environment: Day {tick} of the simulation."

        # 2. 全局事件注入
        if tick in ENTERPRISE_STRATEGY:
            event_text = ENTERPRISE_STRATEGY[tick]
            print(f"🚨 [Global News Injection]: {event_text}")

            event_msg = {"source": "Global News", "content": event_text}
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                s_data = getattr(s_plugin, "state_data", getattr(s_plugin, "_state_data", {}))
                inbox = s_data.get("incoming_messages", [])
                await s_plugin.set_state("incoming_messages", list(inbox) + [event_msg])
                # 同时写入专用的 current_news 字段，供 Plan 层独立读取
                # （Reflect 层会消费并清空 observations，Plan 层不能依赖它）
                await s_plugin.set_state("current_news", event_text)
        else:
            # 无事件的 Tick：重置 current_news 为平静状态
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                await s_plugin.set_state("current_news", "")
        # 3. 认知与反思层
        for ag in agents:
            s_plugin = ag.get_component("state")._plugin
            await s_plugin.set_state("time_context", time_context)
            await s_plugin.set_state("current_tick", tick)

            await ag.get_component("perceive").execute(tick)
            await ag.get_component("reflect").execute(tick)

        # 4. 计划与执行层
        for ag in agents:
            await ag.get_component("plan").execute(tick)
            await ag.get_component("invoke").execute(tick)

        # ==========================================
        # 📊 5. 数据结算与持久化
        # ==========================================
        trust_list = []
        tick_buys = 0
        tick_posts = 0

        for ag in agents:
            s_data = getattr(ag.get_component("state")._plugin, "state_data",
                             getattr(ag.get_component("state")._plugin, "_state_data", {}))
            p_data = getattr(ag.get_component("profile")._plugin, "_profile_data",
                             getattr(ag.get_component("profile")._plugin, "profile_data", {}))

            agent_type = p_data.get("psychology", {}).get("cluster_type", "Unknown")
            trust = round(float(s_data.get("trust_score", 5.0)), 2)
            trust_list.append(trust)

            plan = s_data.get("plan_result", {})
            is_buying  = plan.get("is_buying", False)
            is_posting = plan.get("is_posting", False)

            baseline_trust    = round(float(s_data.get("baseline_trust", trust)), 3)
            quiet_ticks       = int(s_data.get("quiet_ticks", 0))
            trust_after_decay = round(float(plan.get("trust_after_decay", trust)), 3)
            affective_change  = round(float(plan.get("affective_change", 0.0)), 3)
            decay_lambda      = float(plan.get("decay_lambda", 0.15))

            thought   = s_data.get("latest_thought", {}) or {}
            hypocrisy = thought.get("hypocrisy_perceived", False)

            if is_buying:
                tick_buys += 1
                cumulative_buyers.add(ag.agent_id)
            if is_posting:
                tick_posts += 1

            action_tags = []
            if is_buying:  action_tags.append("BUY")
            if is_posting: action_tags.append("POST")
            if not action_tags: action_tags.append("IGNORE")
            action_log = "+".join(action_tags)

            writer.writerow([
                tick, ag.agent_id, agent_type,
                trust, baseline_trust, trust_after_decay, affective_change,
                decay_lambda, quiet_ticks, action_log, hypocrisy
            ])

            if thought:
                reasoning = thought.get("reasoning", "")
                thought_writer.writerow([
                    tick, ag.agent_id, agent_type,
                    hypocrisy, affective_change, trust_after_decay, trust, reasoning
                ])

        avg_trust = np.mean(trust_list)
        conversion_rate = len(cumulative_buyers) / len(agents)
        macro_writer.writerow([tick, avg_trust, tick_buys, len(cumulative_buyers), conversion_rate, tick_posts])
        print(
            f"📈 [宏观结算] 平均信任 {avg_trust:.2f} | 累计转化率 {conversion_rate * 100:.1f}% | 本期发帖 {tick_posts} 人")

        # ==========================================
        # 🌐 6. 社交网络路由与时间步状态重置
        # ==========================================
        print(f"🔄 正在执行网络消息分发与跨周期清理...")

        # 1. 收集本回合所有人的发帖
        tick_posts_dict = {}
        for ag in agents:
            try:
                state_plugin = ag.get_component("state")._plugin
                s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
                plan = s_data.get("plan_result", {})
                if plan.get("is_posting", False) and plan.get("post_content", "").strip():
                    tick_posts_dict[ag.agent_id] = plan.get("post_content").strip()
            except Exception:
                pass

        # 2. 物理清空所有人的本回合信箱，防止"土拨鼠之日"陷阱
        for ag in agents:
            state_plugin = ag.get_component("state")._plugin
            await state_plugin.set_state("incoming_messages", [])

        # 3. 跨周期路由：通过 SocialNetworkPlugin.broadcast_message() 分发帖子
        #    帖子在 Tick N 发出，Tick N+1 才被邻居的 Perceive 层读取（模拟传播时延）
        for author_id, content in tick_posts_dict.items():
            social_content = f"[Social Media Feed] Connection {author_id} posted: \"{content}\""
            await net_plugin.broadcast_message(author_id, social_content)

        # 4. 拦截信箱爆炸：每人最多保留 3 条消息，防止 Token 爆炸
        MAX_RETAINED_MESSAGES = 3
        for ag in agents:
            state_plugin = ag.get_component("state")._plugin
            msgs = state_plugin.get_state_sync("incoming_messages") or []
            if len(msgs) > MAX_RETAINED_MESSAGES:
                await state_plugin.set_state("incoming_messages", msgs[-MAX_RETAINED_MESSAGES:])

    # 循环结束，用 finally 保证文件关闭
    for f in _open_files:
        try:
            f.close()
        except Exception:
            pass
    print(f"\n仿真阶段结束。进入后置数据分析阶段...")

    # 自动触发级联深度与转化率图谱分析
    analyze_results(macro_path, csv_path, graph_path, len(agents), results_dir, timestamp)


# ==========================================
# 📊 自动化后置分析：转化率与级联深度计算
# ==========================================
def analyze_results(macro_path, log_path, graph_path, total_agents, results_dir, timestamp):
    print("\n正在通过 NetworkX 计算级联深度与转化率图谱...")
    df_macro = pd.read_csv(macro_path)
    df_log = pd.read_csv(log_path)

    # 1. 计算 T50 (达到 50% 转化率的时间)
    t50_row = df_macro[df_macro['ConversionRate'] >= 0.5]
    t50 = t50_row['Tick'].iloc[0] if not t50_row.empty else "未达到50%"
    print(f"T50 扩散指标: {t50}")

    # 2. 计算最大信息级联深度 (Cascade Depth)
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
    # networkx >= 3.0 node_link_graph 签名变更，兼容新旧版本
    try:
        base_G = nx.node_link_graph(graph_data, edges="links")
    except TypeError:
        base_G = nx.node_link_graph(graph_data)

    cascade_G = nx.DiGraph()  # 有向传播图
    # 🚨 修复：由于使用了 BUY+POST，必须用 str.contains 才能抓取到所有发帖事件
    post_events = df_log[df_log['Action'].astype(str).str.contains('POST')].sort_values(by='Tick')

    for _, row in post_events.iterrows():
        tick = row['Tick']
        agent_id = row['AgentID']
        cascade_G.add_node(agent_id, tick=tick)

        neighbors = list(base_G.neighbors(agent_id))
        potential_sources = post_events[(post_events['Tick'] < tick) & (post_events['AgentID'].isin(neighbors))]
        if not potential_sources.empty:
            source = potential_sources.iloc[-1]['AgentID']
            cascade_G.add_edge(source, agent_id)

    max_depth = 0
    if len(cascade_G.edges) > 0:
        try:
            max_depth = len(nx.dag_longest_path(cascade_G)) - 1
        except Exception:
            pass
    print(f"最大信息级联深度: {max_depth} 级")

    # 3. 绘制转化率与信任度耦合图谱
    plt.figure(figsize=(10, 5))
    ax1 = plt.gca()
    ax2 = ax1.twinx()

    ax1.plot(df_macro['Tick'], df_macro['AvgTrust'], color='blue', marker='o', label='平均信任度 (Avg Trust)')
    ax1.set_xlabel('仿真周期 (Tick)')
    ax1.set_ylabel('信任度 (0-10)', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.set_ylim([0, 10])

    ax2.plot(df_macro['Tick'], df_macro['ConversionRate'] * 100, color='green', marker='^', linestyle='--',
             label='累计转化率 (%)')
    ax2.set_ylabel('转化率 (%)', color='green')
    ax2.tick_params(axis='y', labelcolor='green')
    ax2.set_ylim([0, 100])

    # 🚨 修复：标注干预事件完全对齐最新的 ENTERPRISE_STRATEGY (1, 5, 10)
    events = {
        1: '发售预热 (Launch)',
        5: '黑石漂绿丑闻 (Greenwashing)',
        10: '菜籽油健康风波 (Utility Drop)'
    }
    for t, label in events.items():
        if t <= df_macro['Tick'].max():
            ax1.axvline(x=t, color='red', linestyle=':', alpha=0.5)
            ax1.text(t + 0.2, 2.0, label, rotation=90, verticalalignment='bottom', color='red', fontweight='bold')

    plt.title('信任度波动与购买转化率耦合图谱 (含网络传播修正)', pad=15)
    plot_path = os.path.join(results_dir, f"macro_analysis_{timestamp}.png")

    # 防止图例重叠
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')

    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"🖼️ 图谱已保存至: {plot_path}")


if __name__ == "__main__":
    asyncio.run(run())