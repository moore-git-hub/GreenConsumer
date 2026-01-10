import sys
import os
import asyncio
import yaml
import json

# 1. 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
standalone_path = os.path.join(project_root, "packages", "agentkernel-standalone")
if os.path.exists(standalone_path) and standalone_path not in sys.path:
    sys.path.insert(0, standalone_path)

from agentkernel_standalone.mas.agent.agent import Agent
from agentkernel_standalone.mas.environment.environment import Environment
from agentkernel_standalone.mas.agent.components.profile import ProfileComponent
from agentkernel_standalone.mas.agent.components.state import StateComponent
from agentkernel_standalone.mas.agent.components.plan import PlanComponent
from agentkernel_standalone.mas.agent.components.invoke import InvokeComponent
from agentkernel_standalone.mas.environment.base.component_base import EnvironmentComponent

sys.path.append(current_dir)
try:
    from plugins.agent.profile.GreenProfilePlugin import GreenProfilePlugin
    from plugins.agent.state.GreenStatePlugin import GreenStatePlugin
    from plugins.agent.plan.ConsumerPlanPlugin import ConsumerPlanPlugin
    from plugins.agent.invoke.GreenInvokePlugin import GreenInvokePlugin
    from plugins.environment.network.SocialNetworkPlugin import SocialNetworkPlugin
except ImportError as e:
    print(f"❌ 插件导入失败: {e}")
    sys.exit(1)


# === 辅助函数：智能挂载环境组件 ===
def mount_env_component(env, comp, name):
    comp.COMPONENT_NAME = name

    # 尝试标准方法
    if hasattr(env, "add_component"):
        try:
            # 尝试单参数调用 (新版风格)
            env.add_component(comp)
        except TypeError:
            # 失败则尝试双参数调用 (旧版风格: name, component)
            # print(f"⚠️ [Debug] add_component 需要 name 参数，尝试双参数调用...")
            env.add_component(name, comp)
        return

    # 尝试直接操作属性
    if hasattr(env, "components") and isinstance(env.components, dict):
        env.components[name] = comp
        return
    if hasattr(env, "_components") and isinstance(env._components, dict):
        env._components[name] = comp
        return

    print(f"❌ 无法将组件 {name} 挂载到 Environment。")


async def verify_network():
    print("🚀 开始验证里程碑 4：网络扩散 (最终修复版)")

    # 1. 初始化环境
    env = Environment()

    # 准备网络插件
    net_plugin = SocialNetworkPlugin()
    net_comp = EnvironmentComponent()

    # 双重绑定
    net_comp.plugin = net_plugin
    net_comp._plugin = net_plugin
    net_plugin.component = net_comp

    # 【关键】智能挂载
    mount_env_component(env, net_comp, "network")
    print("✅ 环境初始化完成")

    # 2. 创建 3 个 Agents
    agents = []
    agent_ids = ["Consumer_A", "Consumer_B", "Consumer_C"]

    print("🤖 初始化 Agents...")
    for aid in agent_ids:
        agent = Agent(aid, ["profile", "state", "plan", "invoke"])
        agent.env = env  # 注入环境引用

        def bind(cls, plugin, name):
            c = cls()
            c.plugin = plugin
            c._plugin = plugin
            plugin.component = c
            c._agent = agent
            agent.add_component(c)
            return plugin

        bind(ProfileComponent,
             GreenProfilePlugin({"name": aid, "psychology": {"environmental_involvement": "Light Green"}}), "profile")
        s_plugin = bind(StateComponent, GreenStatePlugin(), "state")
        bind(PlanComponent, ConsumerPlanPlugin(), "plan")
        bind(InvokeComponent, GreenInvokePlugin(), "invoke")

        # 初始化状态
        await s_plugin.set_state("budget", 100)
        await s_plugin.set_state("trust_score", 5.0)
        await s_plugin.set_state("incoming_messages", [])

        agents.append(agent)

    # 3. 注册到网络并建立连接
    # 注意：init 可能会重置图，所以先 init 再 register
    await net_plugin.init()
    net_plugin.register_agents(agents)

    # 打印 A 的邻居
    neighbors_a = net_plugin.get_neighbors("Consumer_A")
    print(f"🌐 社交拓扑检查: Consumer_A 的邻居 -> {neighbors_a}")
    if not neighbors_a:
        print("❌ 错误：网络构建失败，Agent A 没有邻居！")
        return

    # 4. 强制 Agent A 发帖
    print("\n🎬 [Action] Consumer_A 发布谣言...")
    state_comp = agents[0].get_component("state")
    # 防御性获取插件
    state_a = getattr(state_comp, "_plugin", getattr(state_comp, "plugin", None))

    await state_a.set_state("plan_result", {
        "action": "post_review",
        "content": "DON'T BUY! IT'S GREENWASHING!",
        "reason": "Test viral message"
    })

    # 执行 Invoke
    invoke_comp = agents[0].get_component("invoke")
    invoke_a = getattr(invoke_comp, "_plugin", getattr(invoke_comp, "plugin", None))
    await invoke_a.execute(0)

    # 5. 验证：检查邻居是否收到了消息
    print("\n🔍 [Verification] 检查邻居邮箱...")
    success_count = 0
    for neighbor_id in neighbors_a:
        # 找到 Agent 对象
        neighbor = next((a for a in agents if a.agent_id == neighbor_id), None)
        if not neighbor: continue

        n_state_comp = neighbor.get_component("state")
        state_n = getattr(n_state_comp, "_plugin", getattr(n_state_comp, "plugin", None))

        # 读取收件箱
        s_data = getattr(state_n, "state_data", getattr(state_n, "_state_data", {}))
        inbox = s_data.get("incoming_messages")

        print(f"   - {neighbor_id} 收件箱: {inbox}")

        if inbox and len(inbox) > 0:
            msg = inbox[0]
            # 简单校验内容
            if msg.get('source') == "Consumer_A" and "GREENWASHING" in msg.get('content'):
                success_count += 1

    if success_count > 0:
        print(f"\n🏆 里程碑 4 达成！{success_count} 个邻居成功收到谣言。")
    else:
        print("\n❌ 验证失败：邻居没有收到消息。")


if __name__ == "__main__":
    asyncio.run(verify_network())