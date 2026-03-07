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

    # 1. 基础动作日志
    csv_path = os.path.join(results_dir, f"simulation_log_{timestamp}.csv")
    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    writer.writerow(["Tick", "AgentID", "Type", "TrustScore", "Action", "Hypocrisy"])

    # 2. 详细思维日志
    thought_path = os.path.join(results_dir, f"thoughts_log_{timestamp}.csv")
    thought_file = open(thought_path, "w", newline="", encoding="utf-8")
    thought_writer = csv.writer(thought_file)
    thought_writer.writerow(["Tick", "AgentID", "AgentType", "Hypocrisy", "TrustChange", "Reasoning"])

    # 3. 宏观 KPI 日志 (新引入的转化率收集流)
    macro_path = os.path.join(results_dir, f"macro_metrics_{timestamp}.csv")
    macro_file = open(macro_path, "w", newline="", encoding="utf-8")
    macro_writer = csv.writer(macro_file)
    macro_writer.writerow(["Tick", "AvgTrust", "NewBuys", "CumulativeBuys", "ConversionRate", "PostCount"])
    print(f"📂 数据收集流管道已建立。")

    # --- 初始化 ---
    builder = Builder(current_dir, resource_maps)
    builder._load_data_into_config()
    agent_configs = builder.config.agents

    env = Environment()
    net_plugin = SocialNetworkPlugin()
    net_comp = EnvironmentComponent()
    net_comp.plugin = net_plugin;
    net_comp._plugin = net_plugin;
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
                comp._plugin = plugin;
                plugin.component = comp
        agents.append(agent)

    print(f"👥 初始化了 {len(agents)} 个 Agent。")

    await net_plugin.init()
    net_plugin.register_agents(agents)

    # 保存网络拓扑用于后续级联推导
    graph_path = os.path.join(results_dir, f"network_graph_{timestamp}.json")
    graph_data = nx.node_link_data(net_plugin.graph)
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f)

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
                    {"hypocrisy_perceived": True, "trust_change": -0.5, "importance": 5.0, "reasoning": "Mocking..."})

        router = Mock()

    for ag in agents: ag._model = router

    print("初始化 Agent 状态")
    for ag in agents:
        state_plugin = ag.get_component("state")._plugin
        profile_plugin = ag.get_component("profile")._plugin
        p_data = getattr(profile_plugin, "profile_data", getattr(profile_plugin, "_profile_data", {}))

        await state_plugin.set_state("trust_score", float(p_data.get("initial_trust", 5.0)))
        await state_plugin.set_state("budget", float(p_data.get("budget", 100)))
        await state_plugin.set_state("incoming_messages", [])
        await state_plugin.set_state("observations", [])
        await state_plugin.set_state("latest_thought", None)

    # ==========================================
    # 🚀 仿真主循环
    # ==========================================
    TOTAL_TICKS = 30
    BURN_IN_TICKS = 5

    # ==========================================
    # 🚀 高阶真实商业公关博弈矩阵 (Advanced Enterprise Strategy)
    # ==========================================
    ENTERPRISE_STRATEGY = {
        1: {
            "source": "EcoBrand_Official",
            "content": "自然，是我们唯一的答案。历经1000个日夜，EcoBottle 采用独家提取的深海海藻复合纤维，为您带来极致体验。这不仅是一个水杯，更是对地球的一份承诺。每售出一件，我们将向‘蓝色海洋计划’捐助1元。下周，开启您的零碳生活方式。"
        },
        6: {
            "source": "EcoBrand_Official",
            "content": "今日正式开售！EcoBottle 荣获业内首创的 'Eco-Future 内部先锋环保金奖'。产品生命周期参数已上传我们的自建碳足迹模型（注：该测算正由第三方智库评估中）。"
        },
        10: {
            "source": "Consumer_Rights_Blogger (测评博主)",
            "content": "避雷！刚收到首发盲盒，用开水一烫底部竟然轻微变形了？而且我刮开底部的所谓的‘原木环保漆’，里面隐约印着回收代码7（不可降解的PC塑料）！说好的海藻提取物呢？这真的是智商税吧！"
        },
        15: {
            "source": "Green_Earth_NGO (独立环保组织)",
            "content": "【深度调查】经本机构实验室光谱分析，EcoBottle 核心材质仍为传统石油基塑料，海藻纤维含量不足 2%。更令人震惊的是，其宣称捐助的‘蓝色海洋计划’实为该企业高管实际控制的空壳基金。这是极其恶劣的‘漂绿’与虚假营销。"
        },
        20: {
            "source": "EcoBrand_PR (官方公关部)",
            "content": "致关心我们的朋友：对不起。经连夜彻查，系上游原材料供应商为压缩成本，私自篡改了配方比例，我们未能察觉，这也是我们的失职。目前已向公安机关报案并起诉该供应商，全线产品启动召回。至于基金争议，属于合理合法的税务统筹，绝非中饱私囊。我们做环保的初心从未改变，恳请大家给本土创新企业一个纠错的机会。"
        },
        25: {
            "source": "Top_Lifestyle_KOL (百万粉丝生活大V)",
            "content": "今天去了EcoBrand的总部。其实大家没必要这么苛刻，国内做植物基新材料的本来就没几家，能迈出第一步已经很了不起了。我亲眼看到那些被坑的年轻研发人员在哭。揪着一点管理漏洞往死里打，以后谁还敢做环保创新？（我已下单支持复产版，不喜勿喷）"
        }
    }

    cumulative_buyers = set()  # 追踪历史购买者

    for tick in range(1, TOTAL_TICKS + 1):
        print(f"\n === Tick {tick} ===")

        if tick <= BURN_IN_TICKS:
            time_context = f"产品上市预热中，当前是预热期第 {tick} 天。不允许购买。"
        else:
            time_context = f"产品已正式发售第 {tick - BURN_IN_TICKS} 天。"

        if tick in ENTERPRISE_STRATEGY:
            event = ENTERPRISE_STRATEGY[tick]
            print(f"📣 [全局干预注入] {event['source']}: {event['content']}")
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                inbox = getattr(s_plugin, "state_data", {}).get("incoming_messages", [])
                await s_plugin.set_state("incoming_messages", list(inbox) + [event])

        for ag in agents:
            s_plugin = ag.get_component("state")._plugin
            await s_plugin.set_state("time_context", time_context)
            await s_plugin.set_state("current_tick", tick)
            await ag.get_component("perceive").execute(tick)
            await ag.get_component("reflect").execute(tick)

        for ag in agents:
            await ag.get_component("plan").execute(tick)
            await ag.get_component("invoke").execute(tick)

        # 数据结算
        trust_list = []
        tick_buys = 0
        tick_posts = 0

        for ag in agents:
            s_data = getattr(ag.get_component("state")._plugin, "state_data", {})
            p_data = getattr(ag.get_component("profile")._plugin, "profile_data", {})

            agent_type = p_data.get("psychology", {}).get("environmental_involvement", "Unknown")
            trust = s_data.get("trust_score", 5.0)
            trust_list.append(trust)

            plan = s_data.get("plan_result", {})
            action = plan.get("action", "none") if plan else "none"
            thought = s_data.get("latest_thought", {}) or {}
            hypocrisy = thought.get("hypocrisy_perceived", False)

            if action == "buy":
                tick_buys += 1
                cumulative_buyers.add(ag.agent_id)
            elif action == "post_review":
                tick_posts += 1

            writer.writerow([tick, ag.agent_id, agent_type, trust, action, hypocrisy])
            if thought:
                thought_writer.writerow([tick, ag.agent_id, agent_type, hypocrisy, thought.get("trust_change", 0.0),
                                         thought.get("reasoning", "")])

        avg_trust = np.mean(trust_list)
        conversion_rate = len(cumulative_buyers) / len(agents)
        macro_writer.writerow([tick, avg_trust, tick_buys, len(cumulative_buyers), conversion_rate, tick_posts])
        print(
            f"平均信任 {avg_trust:.2f} | 累计转化率 {conversion_rate * 100:.1f}% | 本期发帖 {tick_posts} 人")

    csv_file.close()
    thought_file.close()
    macro_file.close()
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
    # 推导逻辑: A发帖后，若B(A的邻居)在后续周期发帖，则存在级联边 A->B。
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
    base_G = nx.node_link_graph(graph_data)

    cascade_G = nx.DiGraph()  # 有向传播图
    post_events = df_log[df_log['Action'] == 'post_review'].sort_values(by='Tick')

    # 构建级联树
    for _, row in post_events.iterrows():
        tick = row['Tick']
        agent_id = row['AgentID']
        cascade_G.add_node(agent_id, tick=tick)

        # 寻找启发源: 是否有邻居在之前的周期发过帖？
        neighbors = list(base_G.neighbors(agent_id))
        potential_sources = post_events[(post_events['Tick'] < tick) & (post_events['AgentID'].isin(neighbors))]
        if not potential_sources.empty:
            # 假设受最近发帖的邻居影响
            source = potential_sources.iloc[-1]['AgentID']
            cascade_G.add_edge(source, agent_id)

    max_depth = 0
    if len(cascade_G.edges) > 0:
        # 计算有向无环图的最长路径即为最大级联深度
        try:
            max_depth = len(nx.dag_longest_path(cascade_G)) - 1
        except:
            pass  # 存在环的情况忽略
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

    # 标注干预事件
    events = {
        1: '发售预热',
        6: '正式发售',
        10: '散户爆料',
        15: '实锤爆发',
        20: '甩锅公关',
        25: '大V洗地'
    }
    for t, label in events.items():
        ax1.axvline(x=t, color='red', linestyle=':', alpha=0.5)
        ax1.text(t, 0.5, label, rotation=90, verticalalignment='bottom', color='red')

    plt.title('信任度波动与购买转化率耦合图谱')
    plot_path = os.path.join(results_dir, f"macro_analysis_{timestamp}.png")
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"🖼️ 图谱已保存至: {plot_path}")


if __name__ == "__main__":
    asyncio.run(run())