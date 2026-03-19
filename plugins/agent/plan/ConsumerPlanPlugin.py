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

        trust_score = float(s_data.get("trust_score", 5.0))
        budget = float(s_data.get("budget", 0))
        product_price = float(s_data.get("product_price", 50))
        product_name = "EcoBottle"
        latest_thought = s_data.get("latest_thought", {})

        # 1. 判断是否处于预热期 (Tick 1-5)
        time_context = s_data.get("time_context", "")
        is_burn_in = "预热期" in time_context or "不允许购买" in time_context

        # 2. 强化购买动机的引导规则
        if is_burn_in:
            buy_rule = "STRICTLY UNAVAILABLE (Product not released yet, YOU MUST NOT CHOOSE THIS ACTION)."
        else:
            # 降低购买门槛引导，设定 5.5 及格线，鼓励转化
            buy_rule = f"STRONGLY RECOMMENDED. You MUST choose 'buy' if your budget is >= {product_price} AND your Trust is >= 4. Buying is your primary goal as a consumer."

        persona = profile_plugin.get_prompt()
        thought_str = json.dumps(latest_thought) if latest_thought else "No specific thoughts."

        # 3. 构造决策 Prompt
        prompt = f"""
{persona}

[Context]
System Environment: {time_context}
Product: '{product_name}' (Price: {product_price}).
Your Budget: {budget}

[State]
- Trust: {trust_score}/10.0
- Thought: {thought_str}

[Task]
Decide your NEXT SINGLE ACTION based on your persona and state:
1. 'buy': {buy_rule}
2. 'post_review': ONLY if you strongly want to express your opinion on social media AND you decided NOT to buy this time.
3. 'ignore': If you don't care, or if you cannot afford it.

CRITICAL RULE: The "reason" and "content" fields MUST BE WRITTEN ENTIRELY IN ENGLISH.

Output JSON ONLY: 
{{ 
    "action": "buy/post_review/ignore", 
    "content": "Social media post content if you choose post_review (IN ENGLISH, otherwise empty)", 
    "reason": "Explain your reason here (STRICTLY IN ENGLISH)" 
}}
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

            # 强制规整 action 字段，防止 LLM 输出大写如 "Buy" 或 "Action: buy"
            raw_action = str(plan.get("action", "ignore")).lower().strip()
            if "buy" in raw_action:
                raw_action = "buy"
            elif "post" in raw_action or "review" in raw_action:
                raw_action = "post_review"
            else:
                raw_action = "ignore"

            plan["action"] = raw_action

            # ==========================================
            # 🛡️ 物理拦截网 (Fail-Safe)
            # ==========================================
            if plan.get("action") == "buy" and is_burn_in:
                plan = {"action": "ignore", "reason": "Pre-release period, cannot buy (Auto-corrected)"}

            if plan.get("action") == "buy" and budget < product_price:
                plan = {"action": "ignore", "reason": "Budget insufficient (Auto-corrected)"}

            await state_plugin.set_state("plan_result", plan)

            if plan.get("action") != "ignore":
                print(
                    f"📅 [Plan] {agent.agent_id} 决策: {plan.get('action').upper()} (Trust: {trust_score:.1f}, 理由: {plan.get('reason')[:40]}...)")

        except Exception as e:
            print(f"❌ [Plan Error] {agent.agent_id}: {e}")

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass