import json
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
        # await state_plugin.set_state("plan_result", None)

    async def _perform_buy(self, state_plugin):
        s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
        current_budget = s_data.get("budget", 0)
        price = s_data.get("product_price", 50)  # 默认 50

        if current_budget >= price:
            new_budget = current_budget - price
            await state_plugin.set_state("budget", new_budget)
            print(f"🛒 [Invoke] {self._get_agent().agent_id} 购买成功！(花费: {price}, 余额: {new_budget})")
        else:
            print(f"❌ [Invoke] {self._get_agent().agent_id} 预算不足 (余额: {current_budget}, 价格: {price})，购买失败。")

    async def _perform_post_review(self, original_content: str):
        """
        核心升级：执行语义变异与再框架 (Reframing)
        模拟真实社交网络中的“传话筒效应”，依据自身画像对原内容进行改写后再广播。
        """
        agent = self._get_agent()
        profile_plugin = self._get_plugin("profile")
        p_data = getattr(profile_plugin, "profile_data", getattr(profile_plugin, "_profile_data", {}))

        persona = p_data.get("persona", "")
        involvement = p_data.get("psychology", {}).get("environmental_involvement", "Light Green")

        # 构造变异 Prompt
        mutation_prompt = f"""
[你的画像]
{persona}

[你原本计划发送或转发的初始信息]
"{original_content}"

[任务：UGC 内容变异机制]
请基于你的画像特质，将上述信息改写为一条真实的社交媒体发文或评论。
规则：
必须符合人类在社交网络上交流的口吻（如带有一些主观感叹）。

仅输出严格的 JSON 格式：
{{
    "mutated_content": "变异后的具体社交媒体发文内容"
}}
"""
        mutated_content = original_content  # 默认兜底机制
        try:
            model = getattr(agent, "model", getattr(agent, "_model", None))
            if model:
                response = await model.chat(mutation_prompt)
                clean_json = response.replace("```json", "").replace("```", "").strip()
                result = json.loads(clean_json)
                mutated_content = result.get("mutated_content", original_content)
        except Exception as e:
            print(f"变异失败，采用原文本。错误: {e}")

        # print(
        #     f"📢 [Invoke 语义变异] {agent.agent_id} ({involvement})\n  原意: {original_content[:20]}...\n  发帖: \"{mutated_content}\"")

        # 广播变异后的内容
        network_plugin = self._get_env_plugin("network")
        if network_plugin:
            await network_plugin.broadcast_message(agent.agent_id, mutated_content)
        else:
            print("未找到 SocialNetworkPlugin，消息无法扩散。")

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass