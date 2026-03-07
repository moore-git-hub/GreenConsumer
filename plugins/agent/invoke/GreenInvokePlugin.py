from agentkernel_standalone.mas.agent.base.plugin_base import InvokePlugin


class GreenInvokePlugin(InvokePlugin):
    async def init(self):
        pass

    # === Helper ===
    def _get_agent(self):
        if hasattr(self, "agent") and self.agent: return self.agent
        if self.component and hasattr(self.component, "agent"): return self.component.agent
        if hasattr(self, "_component") and self._component: return self._component.agent
        return None

    def _get_plugin(self, name):
        agent = self._get_agent()
        if not agent: return None
        comp = agent.get_component(name)
        return getattr(comp, "_plugin", getattr(comp, "plugin", None)) if comp else None

    def _get_env_plugin(self, name):
        agent = self._get_agent()
        if hasattr(agent, "env") and agent.env:
            comp = agent.env.get_component(name)
            return getattr(comp, "_plugin", getattr(comp, "plugin", None)) if comp else None
        return None

    # ==============

    async def execute(self, current_tick: int) -> None:
        state_plugin = self._get_plugin("state")
        if not state_plugin: return

        # 获取计划
        s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
        plan = s_data.get("plan_result")

        if not plan: return
        if isinstance(plan, list): plan = plan[0] if plan else {}

        action_type = plan.get("action")

        if action_type == "buy":
            await self._perform_buy(state_plugin)
        elif action_type == "post_review":
            content = plan.get("content", "No content")
            await self._perform_post_review(content)

        # 清空计划，防止下一轮重复执行
        # await state_plugin.set_stateset_state("plan_result", None)

    async def _perform_buy(self, state_plugin):
        s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))

        # ✅ 修复 1: 正确读取 budget (之前写成了 "+")
        current_budget = s_data.get("budget", 0)

        # ✅ 修复 2: 从 State 读取统一价格，不再硬编码 50
        price = s_data.get("product_price", 50)

        if current_budget >= price:
            new_budget = current_budget - price
            await state_plugin.set_state("budget", new_budget)
            print(f"🛒 [Invoke] {self._get_agent().agent_id} 购买成功！(花费: {price}, 余额: {new_budget})")
        else:
            print(f"❌ [Invoke] {self._get_agent().agent_id} 预算不足 (余额: {current_budget}, 价格: {price})，购买失败。")

    async def _perform_post_review(self, content):
        agent = self._get_agent()
        print(f"📢 [Invoke] {agent.agent_id} 决定发帖: \"{content}\"")

        network_plugin = self._get_env_plugin("network")
        if network_plugin:
            await network_plugin.broadcast_message(agent.agent_id, content)
        else:
            print("⚠️ [Invoke] 未找到 SocialNetworkPlugin，消息无法扩散。")

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass