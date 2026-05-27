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

        # 2. 追踪基线信任 (Baseline Trust)
        # 如果是前几个 Tick (如 Tick 1)，记录为该个体的天然心理锚点
        previous_trust = float(s_data.get("trust_score", 5.0))
        baseline_trust = float(s_data.get("baseline_trust", previous_trust))
        if "baseline_trust" not in s_data and current_tick <= 2:
            await state_plugin.set_state("baseline_trust", previous_trust)
            baseline_trust = previous_trust

        # 3. 追踪“平静期”时长 (Ticks Since Last Scandal) 用于计算遗忘曲线
        # 判定当前是否有负面/刺激性新闻
        is_quiet_day = "Normal peaceful day" in news_text or news_text.strip() == ""
        quiet_ticks = int(s_data.get("quiet_ticks", 0))

        if is_quiet_day:
            quiet_ticks += 1
        else:
            quiet_ticks = 0  # 一旦有大新闻，遗忘曲线重置

        await state_plugin.set_state("quiet_ticks", quiet_ticks)

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
        Product available: '{product_name}' (Price: ${product_price}).
        
        [Your Mental State & Memory]
        Your Inherent Baseline Trust for this brand: {baseline_trust}/10.0
        Your Previous Trust Score (Last Tick): {previous_trust}/10.0
        Time since last major news event: {quiet_ticks} ticks (days).
        Your Latest Inner Thought: {thought_str}
        
        [CRITICAL: Psychological Rules of Emotional Decay]
        Humans experience 'Hedonic Adaptation' and memory decay. You MUST apply these rules:
        1. **The Forgetting Curve**: If there is no new major scandal (Time since last news > 0), your intense anger or excitement MUST gradually decay. 
        2. **Mean Reversion**: During quiet periods, your current trust score MUST naturally drift from your Previous Trust ({previous_trust}) back towards your Inherent Baseline Trust ({baseline_trust}). 
        3. **Decay Speed**: The higher the 'Time since last major news event', the closer you should return to your baseline. Do not stay permanently angry at a low score if the news has been quiet for multiple ticks.
        4. **Scandal Impact**: ONLY if there is a fresh, relevant scandal TODAY (Time since last news = 0), you can drop your trust score sharply according to your persona's vulnerabilities.
        
        [Task]
        1. **Self-Evaluate Trust**: Calculate your new trust score based on the decay rules and the current news.
        2. **Purchase Decision (is_buying)**: True if you want the product, your trust is decent, and price is fine. False if you reject it.
        3. **Social Media Decision (is_posting)**: True if you are furious/supportive TODAY AND your social role allows posting. (People rarely post about old news).
        
        Output JSON ONLY (STRICT FORMAT): 
        {{ 
            "current_trust": <float between 0.0 and 10.0>, 
            "is_buying": <boolean true or false>,
            "is_posting": <boolean true or false>,
            "post_content": "Write your social media post here ONLY IF is_posting is true (IN ENGLISH, otherwise leave empty)", 
            "reason": "Explain EXACTLY how the forgetting curve or the new event influenced your trust score compared to previous_trust and baseline_trust (IN ENGLISH)" 
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

            # 解析结果
            current_trust = float(plan.get("current_trust", previous_trust))
            is_buying = bool(plan.get("is_buying", False))
            is_posting = bool(plan.get("is_posting", False))

            plan["current_trust"] = current_trust
            plan["is_buying"] = is_buying
            plan["is_posting"] = is_posting

            # 更新状态
            await state_plugin.set_state("plan_result", plan)
            await state_plugin.set_state("trust_score", current_trust)

            # 打印控制台日志，显式追踪衰减效果
            actions_str = []
            if is_buying: actions_str.append("BUY")
            if is_posting: actions_str.append("POST")
            if not actions_str: actions_str.append("IGNORE")

            trust_delta = current_trust - previous_trust
            sign = "+" if trust_delta > 0 else ""

            # 如果处于遗忘期且向基线回归，终端输出会提示 (Decay)
            decay_tag = "[Decay] " if quiet_ticks > 0 and abs(current_trust - baseline_trust) < abs(
                previous_trust - baseline_trust) else ""

            print(
                f"🧠 [Thought] {agent.agent_id} | Trust: {current_trust:.1f} ({sign}{trust_delta:.1f}) | {decay_tag}Quiet: {quiet_ticks}d | 动作: {'+'.join(actions_str)}")

        except Exception as e:
            print(f"❌ [Plan Error] {agent.agent_id}: {e}")

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass