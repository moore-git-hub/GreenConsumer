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
        p = getattr(comp, "_plugin", None)
        if p: return p
        return getattr(comp, "plugin", None)

    async def execute(self, current_tick: int) -> None:
        agent = self._get_agent()
        if not agent: return

        state_plugin = self._get_plugin("state")
        profile_plugin = self._get_plugin("profile")
        if not state_plugin or not profile_plugin: return

        s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))

        trust_score = s_data.get("trust_score", 5.0)

        # 从 State 获取同步后的预算，默认为 0 以防止未初始化带来的错误决策
        budget = s_data.get("budget", 0)

        # 从 State 获取同步后的价格
        product_price = s_data.get("product_price", 50)
        product_name = "EcoBottle"

        latest_thought = s_data.get("latest_thought", {})

        # 2. 规则过滤器 (Fail Fast)
        if budget < product_price:
            # 这里的 print 可以帮助你确认 budget 是否正确传入
            # print(f"💰 [Plan] 预算不足 ({budget} < {product_price})，跳过购买选项。")
            # 注意：这里我们不直接 return，而是让 Agent 知道自己没钱，但也许它想吐槽呢？
            pass

            # 3. 构造决策 Prompt
        persona = profile_plugin.get_prompt()
        thought_str = json.dumps(latest_thought) if latest_thought else "No specific thoughts."

        prompt = f"""
{persona}

[Context]
You are considering buying '{product_name}' (Price: {product_price}).
Your Budget: {budget}

[State]
- Trust: {trust_score}/10.0
- Thought: {thought_str}

[Task]
Decide NEXT ACTION:
1. 'buy': ONLY if budget >= price AND trust is high.
2. 'post_review': If trust low, warn others.
3. 'ignore': Do nothing (or if cannot afford).

Output JSON: {{ "action": "...", "content": "..." (if review), "reason": "..." }}
"""
        try:
            model = getattr(agent, "model", getattr(agent, "_model", None))
            if not model: return

            response = await model.chat(prompt)

            if isinstance(response, str):
                clean_json = response.replace("```json", "").replace("```", "").strip()
                plan = json.loads(clean_json)
            elif isinstance(response, list):
                plan = response[0]
            else:
                plan = response

            # 安全检查：如果 Agent 没钱还硬要买，Plan 层拦截
            if plan.get("action") == "buy" and budget < product_price:
                plan = {"action": "ignore", "reason": "Budget insufficient (Auto-corrected)"}

            await state_plugin.set_state("plan_result", plan)
            if plan.get("action") != "ignore":
                print(f"📅 [Plan] 决策生成: {plan.get('action')} (理由: {plan.get('reason')})")

        except Exception as e:
            print(f"❌ [Plan Error] {e}")

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass