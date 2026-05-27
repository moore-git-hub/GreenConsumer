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

        product_price = 4.0
        product_name = "Oatly Barista"

        # 提取环境上下文与新闻
        time_context = s_data.get("time_context", "")
        incoming_news = s_data.get("incoming_messages", [])
        news_text = incoming_news[-1]['content'] if incoming_news else "Normal peaceful day. No major news."

        latest_thought = s_data.get("latest_thought", {})
        thought_str = json.dumps(latest_thought) if latest_thought else "Just my usual daily routine."

        persona = profile_plugin.get_prompt()

        # ==========================================
        # 🚀 双轨决策 Prompt：购买与发声解耦 🚀
        # ==========================================
        prompt = f"""
        {persona}

        [Environment Context]
        Current Global News: {news_text}
        Product available: '{product_name}' .

        [Your Latest Inner Thought]
        {thought_str}
        
        [CRITICAL: Cognitive Immunity & Decoupling Rules]
        To act realistically, you MUST obey how your specific persona processes news:

        [Task]
        Based EXCLUSIVELY on your persona, your values, and your reaction to the current news, perform three cognitive tasks:

        1. **Self-Evaluate Trust**: Rate how much you currently trust this brand on a scale of 0.0 (total betrayal/scam) to 10.0 (absolute loyalty/faith).
        2. **Purchase Decision (is_buying)**: True if you genuinely want the product . False if you reject it.
        3. **Social Media Decision (is_posting)**: True if you strongly want to express your opinion online . False if you are a Lurker or just don't care to post.

        Output JSON ONLY (STRICT FORMAT): 
        {{ 
            "current_trust": <float between 0.0 and 10.0>, 
            "is_buying": <boolean true or false>,
            "is_posting": <boolean true or false>,
            "post_content": "Write your social media post here ONLY IF is_posting is true (IN ENGLISH, otherwise leave empty)", 
            "reason": "Explain your reasoning for these decisions (IN ENGLISH)" 
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

            # 1. 强制解析 LLM 自评的 Trust 分数
            current_trust = float(plan.get("current_trust", 5.0))

            # 2. 解析双轨决策布尔值
            is_buying = bool(plan.get("is_buying", False))
            is_posting = bool(plan.get("is_posting", False))

            plan["current_trust"] = current_trust
            plan["is_buying"] = is_buying
            plan["is_posting"] = is_posting

            # 3. 更新状态字典
            await state_plugin.set_state("plan_result", plan)
            await state_plugin.set_state("trust_score", current_trust)

            # 打印日志
            actions_str = []
            if is_buying: actions_str.append("BUY")
            if is_posting: actions_str.append("POST")
            if not actions_str: actions_str.append("IGNORE")

            print(
                f"🧠 [Thought] {agent.agent_id} | Trust: {current_trust}/10 | 动作: {'+'.join(actions_str)} | 理由: {plan.get('reason')[:50]}...")

        except Exception as e:
            print(f"❌ [Plan Error] {agent.agent_id}: {e}")

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass