import sys
import os
import asyncio
import yaml
import json

# 1. 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
standalone_path = os.path.join(project_root, "packages", "agentkernel-standalone")

if os.path.exists(standalone_path):
    if standalone_path not in sys.path:
        sys.path.insert(0, standalone_path)
    print(f"🔧 [Debug] 优先加载本地源码: {standalone_path}")
else:
    print(f"⚠️ [Debug] 未找到本地源码，使用环境包。")

from agentkernel_standalone.mas.agent.agent import Agent
from agentkernel_standalone.mas.agent.components.profile import ProfileComponent
from agentkernel_standalone.mas.agent.components.state import StateComponent
from agentkernel_standalone.mas.agent.components.perceive import PerceiveComponent
from agentkernel_standalone.mas.agent.components.reflect import ReflectComponent
from agentkernel_standalone.toolkit.models.router import ModelRouter, AsyncModelRouter

sys.path.append(current_dir)
try:
    from plugins.agent.profile.GreenProfilePlugin import GreenProfilePlugin
    from plugins.agent.state.GreenStatePlugin import GreenStatePlugin
    from plugins.agent.perceive.GreenPerceivePlugin import GreenPerceivePlugin
    from plugins.agent.reflect.GreenCognitionPlugin import GreenCognitionPlugin
except ImportError as e:
    print(f"❌ 插件导入失败: {e}")
    sys.exit(1)


async def verify():
    print("🚀 开始验证里程碑 2 (最终修复版)...")

    agent = Agent("Test_Agent", ["profile", "state", "perceive", "reflect"])

    def bind_component(comp_cls, plugin_inst, name):
        comp = comp_cls()

        # 【关键修复】双重绑定，确保 getattr(comp, "_plugin") 不返回 None
        comp.plugin = plugin_inst
        comp._plugin = plugin_inst

        plugin_inst.component = comp
        # 兼容旧版 Agent
        comp._agent = agent

        agent.add_component(comp)
        return comp

    print("🤖 组装组件...")
    p_plugin = GreenProfilePlugin(
        profile_data={"name": "Alice", "psychology": {"environmental_involvement": "Deep Green"}})
    bind_component(ProfileComponent, p_plugin, "profile")

    s_plugin = GreenStatePlugin()
    bind_component(StateComponent, s_plugin, "state")

    per_plugin = GreenPerceivePlugin()
    bind_component(PerceiveComponent, per_plugin, "perceive")

    ref_plugin = GreenCognitionPlugin()
    bind_component(ReflectComponent, ref_plugin, "reflect")

    print(f"✅ Agent 组件: {agent.list_components()}")

    # 3. Model Router
    try:
        config_path = os.path.join(current_dir, "configs/models_config.yaml")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                models_conf = yaml.safe_load(f)
            agent._model = ModelRouter(AsyncModelRouter(models_conf))
            print("✅ 真实 ModelRouter 已就绪")
        else:
            raise FileNotFoundError("models_config.yaml not found")
    except Exception as e:
        print(f"⚠️  ModelRouter 初始化失败 ({e})")
        return

    # 4. 状态注入
    print("💉 注入初始状态...")
    await s_plugin.set_state("trust_score", 8.0)

    # 注入“漂绿”广告
    greenwashing_ad = {
        "source": "EcoBrand",
        "content": "Our bottle is 100% Earth-Friendly! (Note: No scientific proof provided, vague claims)"
    }
    await s_plugin.set_state("incoming_messages", [greenwashing_ad])

    # 5. 执行流程
    print("\n▶️  执行 Perceive 阶段...")
    await per_plugin.execute(0)

    print("▶️  执行 Cognition 阶段 (Reflect)...")
    await ref_plugin.execute(0)

    # 6. 验证
    final_trust = s_plugin.state_data.get("trust_score")
    thought = s_plugin.state_data.get("latest_thought")

    print("\n✨ [结果]")
    print(f"   初始信任: 8.0")
    print(f"   最终信任: {final_trust}")

    if final_trust is not None and final_trust < 8.0:
        print("🏆 里程碑 2 达成！逻辑验证通过。")
        print(f"   LLM 判定结果: {thought}")
    elif final_trust == 8.0:
        print("❌ 验证失败：信任值未变化 (可能 LLM 认为这不是漂绿)")
        print(f"   LLM 返回: {thought}")
    else:
        print("❌ 验证失败：状态异常")


if __name__ == "__main__":
    asyncio.run(verify())