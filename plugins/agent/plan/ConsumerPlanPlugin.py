import json
from agentkernel_standalone.mas.agent.base.plugin_base import PlanPlugin


class ConsumerPlanPlugin(PlanPlugin):
    async def init(self):
        pass

    def _get_agent(self):
        if hasattr(self, "agent") and self.agent: return self.agent
        if self.component and hasattr(self.component, "agent"): return self.component.agent
        if hasattr(self, "_component") and self._component: return self._component.agent
        return None

    def _get_plugin(self, name):
        agent = self._get_agent()
        if not agent: return None
        comp = agent.get_component(name)
        if not comp: return None
        # 优先拿 _plugin，如果为 None，再拿 plugin
        p = getattr(comp, "_plugin", None)
        if p: return p
        return getattr(comp, "plugin", None)

    async def execute(self, current_tick: int) -> None:
        """
        S-O-R 中的 R (Response) - 规划阶段
        """
        agent = self._get_agent()
        if not agent:
            print("❌ [Plan] 无法获取 Agent 实例")
            return

        state_plugin = self._get_plugin("state")
        profile_plugin = self._get_plugin("profile")

        # [诊断信息]
        if not state_plugin:
            print("❌ [Plan] 缺少 State 插件，无法决策")
            return
        if not profile_plugin:
            print("❌ [Plan] 缺少 Profile 插件，无法决策")
            return

        # 1. 获取决策所需状态
        # 兼容性：检查 state_data 是否存在，部分旧版可能是 _state_data
        s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))

        trust_score = s_data.get("trust_score", 5.0)
        budget = s_data.get("budget", 100)
        latest_thought = s_data.get("latest_thought", {})

        product_price = 50
        product_name = "EcoBottle"

        # 2. 规则过滤器
        if budget < product_price:
            print(f"💰 [Plan] 预算不足 ({budget} < {product_price})，放弃购买。")
            await state_plugin.set_state("plan_result", {"action": "ignore", "reason": "No budget"})
            return

        # 3. 构造决策 Prompt
        persona = profile_plugin.get_prompt()
        thought_str = json.dumps(latest_thought) if latest_thought else "No specific thoughts."

        prompt = f"""
{persona}

[Context]
You are considering buying '{product_name}' (Price: {product_price}).
Your Budget: {budget}

[State]
- Trust: {trust_score}/10.0 (Buy Threshold: ~6.0)
- Thought: {thought_str}

[Task]
Decide NEXT ACTION:
1. 'buy': If trust high enough.
2. 'post_review': If trust low, warn others.
3. 'ignore': Do nothing.

Output JSON: {{ "action": "...", "content": "..." (if review), "reason": "..." }}
"""
        try:
            # 4. 调用 LLM
            model = getattr(agent, "model", getattr(agent, "_model", None))
            if not model:
                print("❌ [Plan] Agent 没有挂载 ModelRouter")
                return

            response = await model.chat(prompt)

            if isinstance(response, str):
                clean_json = response.replace("```json", "").replace("```", "").strip()
                plan = json.loads(clean_json)
            elif isinstance(response, list):
                plan = response[0]
            else:
                plan = response

            # 5. 保存计划
            await state_plugin.set_state("plan_result", plan)
            print(f"📅 [Plan] 决策生成: {plan.get('action')} (理由: {plan.get('reason')})")

        except Exception as e:
            print(f"❌ [Plan Error] {e}")

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass