import sys
import os
import asyncio

# 1. 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
# 假设结构是 examples/green_consumption/debug_step1.py
# 需要回退两级到 Agent-Kernel 根目录，再进入 packages/agentkernel-standalone
package_path = os.path.abspath(os.path.join(current_dir, "../../packages/agentkernel-standalone"))
if package_path not in sys.path:
    sys.path.append(package_path)

# 2. 引入框架核心类
from agentkernel_standalone.mas.builder import Builder
from agentkernel_standalone.mas.agent.agent import Agent

# 引入标准组件 (Agent 的骨架)
from agentkernel_standalone.mas.agent.components.profile import ProfileComponent
from agentkernel_standalone.mas.agent.components.state import StateComponent
from agentkernel_standalone.mas.agent.components.perceive import PerceiveComponent
from agentkernel_standalone.mas.agent.components.plan import PlanComponent
from agentkernel_standalone.mas.agent.components.invoke import InvokeComponent
from agentkernel_standalone.mas.agent.components.reflect import ReflectComponent

# 引入系统组件
from agentkernel_standalone.mas.system.components.timer import Timer
from agentkernel_standalone.mas.system.components.messager import Messager

# 3. 引入自定义插件 (我们写的逻辑)
sys.path.append(current_dir)
try:
    from plugins.agent.profile.GreenProfilePlugin import GreenProfilePlugin
    from plugins.agent.state.GreenStatePlugin import GreenStatePlugin
except ImportError as e:
    print("❌ 导入插件失败，请检查 plugins/agent/profile/GreenProfilePlugin.py 是否存在")
    raise e

# 4. 【关键修正】构造符合框架规范的资源映射表
resource_maps = {
    # (A) "agent_components": 告诉框架 "profile" 这一层用哪个类 (通常是标准组件类)
    "agent_components": {
        "profile": ProfileComponent,
        "state": StateComponent,
        "perceive": PerceiveComponent,
        "plan": PlanComponent,
        "invoke": InvokeComponent,
        "reflect": ReflectComponent
    },

    # (B) "agent_plugins": 告诉框架 "GreenProfilePlugin" 这一层用哪个类 (这是报错缺失的键！)
    "agent_plugins": {
        "GreenProfilePlugin": GreenProfilePlugin,
        "GreenStatePlugin": GreenStatePlugin,
        # 如果有其他插件，都在这里注册
        "EasyProfilePlugin": None,  # 占位防报错
        "EasyStatePlugin": None  # 占位防报错
    },

    # (C) 其他必须存在的键，防止 Builder 检查报错
    "action_components": {},
    "environment_components": {},
    "system_components": {
        "timer": Timer,
        "messager": Messager
    },
    "controller": None
}


async def verify():
    print("🚀 开始验证里程碑 1 (最终修正版)...")
    print(f"📂 项目路径: {current_dir}")

    try:
        # 1. 初始化 Builder
        builder = Builder(current_dir, resource_maps)

        # 2. 检查数据加载
        if "agent_profiles" not in builder.config.loaded_data:
            print("❌ 错误：loaded_data 中没有 agent_profiles。请检查 configs/simulation_config.yaml")
            return

        profiles = builder.config.loaded_data["agent_profiles"]
        first_agent_id = list(profiles.keys())[0]
        print(f"✅ 数据加载成功。示例 Agent ID: {first_agent_id}")

        # 3. 注入数据配置
        builder._load_data_into_config()
        if not builder.config.agents:
            print("❌ 错误：Agent 配置生成失败")
            return

        target_conf = builder.config.agents[0]
        print(f"✅ Agent 配置生成完毕: {target_conf.id}")

        # 4. 实例化 Agent
        print("🤖 正在初始化 Agent 容器...")
        agent = Agent(target_conf.id, target_conf.component_order)

        # 这一步会调用 Component.init -> 查找 resource_maps["agent_plugins"]
        await agent.init(target_conf.components, resource_maps)
        print("✅ Agent 组件初始化成功 (未报错即成功)")

        # 5. 验证内容
        profile_comp = agent.get_component("profile")
        # 这里的 hack 是因为框架封装较深，我们直接调用插件的方法验证
        if profile_comp and hasattr(profile_comp, "_plugin"):
            plugin = profile_comp._plugin
            prompt = plugin.get_prompt()

            print("\n✨ [Success] 生成的 System Prompt:")
            print("=" * 50)
            print(prompt)
            print("=" * 50)

            if "Green Identity" in prompt:
                print("\n🏆 里程碑 1 完美达成！插件加载机制已修复。")
            else:
                print("\n⚠️  警告：Prompt 内容不对，请检查插件逻辑。")
        else:
            print("❌ 错误：无法获取 Profile Plugin 实例")

    except Exception as e:
        print(f"\n💥 发生异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(verify())