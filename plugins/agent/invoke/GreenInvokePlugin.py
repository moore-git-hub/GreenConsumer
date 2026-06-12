import json
from agentkernel_standalone.mas.agent.base.plugin_base import InvokePlugin


class GreenInvokePlugin(InvokePlugin):
    async def init(self):
        pass

    def _get_agent(self):
        if hasattr(self, "agent") and self.agent: return self.agent
        if self.component and hasattr(self.component, "agent"): return self.component.agent
        if hasattr(self, "_component") and self._component: return self._component.agent
        return None

    async def execute(self, current_tick: int) -> None:
        agent = self._get_agent()
        if not agent: return

        state_plugin = agent.get_component("state")._plugin
        if not state_plugin: return

        s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))

        plan = s_data.get("plan_result", {})
        if not plan: return

        is_buying = plan.get("is_buying", False)
        is_posting = plan.get("is_posting", False)

        # ==========================================
        # 🚀 并行执行器：购买与发帖互不干扰
        # ==========================================

        # 动作 1：处理购买
        if is_buying:
            print(f"[Invoke] {agent.agent_id} 购买成功！")

        # 动作 2：处理发声
        if is_posting:
            content = plan.get("post_content", "No content provided.")
            print(f"[Invoke] {agent.agent_id} 发帖: {content[:60]}...")
            # latest_post 供外部查询用，post_content 已在 plan_result 中供主循环路由使用
            latest_post = {"author": agent.agent_id, "content": content, "tick": current_tick}
            await state_plugin.set_state("latest_post", latest_post)

        # 动作 3：无作为
        if not is_buying and not is_posting:
            pass  # 纯粹的 Ignore 状态

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass