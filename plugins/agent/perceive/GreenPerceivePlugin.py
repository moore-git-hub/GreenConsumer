from typing import List, Any, Dict
from agentkernel_standalone.mas.agent.base.plugin_base import PerceivePlugin


class GreenPerceivePlugin(PerceivePlugin):
    async def init(self):
        pass

    def _get_agent(self):
        """防御性获取 Agent 实例"""
        # 1. 尝试直接属性
        if hasattr(self, "agent") and self.agent:
            return self.agent
        # 2. 尝试通过 component 获取 (标准路径)
        if self.component and hasattr(self.component, "agent"):
            return self.component.agent
        # 3. 尝试通过私有变量 _component
        if hasattr(self, "_component") and self._component and hasattr(self._component, "agent"):
            return self._component.agent
        return None

    def _get_state_plugin(self):
        """防御性获取 State 插件"""
        agent = self._get_agent()
        if not agent:
            print("❌ [Perceive] Critical: Cannot find Agent instance.")
            return None

        # 通过 Agent 获取组件
        comp = agent.get_component("state")
        if not comp: return None

        # 获取插件 (兼容 _plugin 和 plugin 属性)
        return getattr(comp, "_plugin", getattr(comp, "plugin", None))

    async def add_message(self, message: Any) -> None:
        state_plugin = self._get_state_plugin()
        if not state_plugin: return

        current_inbox = state_plugin.state_data.get("incoming_messages") or []
        msg_content = getattr(message, "content", str(message))
        sender = getattr(message, "sender_id", "Unknown")

        formatted_msg = {"source": sender, "content": msg_content, "type": "communication"}
        current_inbox.append(formatted_msg)
        await state_plugin.set_state("incoming_messages", current_inbox)

    async def execute(self, current_tick: int) -> None:
        state_plugin = self._get_state_plugin()
        if not state_plugin: return

        new_messages = state_plugin.state_data.get("incoming_messages") or []
        current_observations = state_plugin.state_data.get("observations") or []

        if new_messages:
            current_observations.extend(new_messages)
            await state_plugin.set_state("incoming_messages", [])
            await state_plugin.set_state("observations", current_observations)
            print(f"👀 [Perceive] 感知到 {len(new_messages)} 条新消息。")