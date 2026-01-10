import json
from agentkernel_standalone.mas.agent.base.plugin_base import ReflectPlugin


class GreenCognitionPlugin(ReflectPlugin):
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
        if not comp:
            return None
        return getattr(comp, "_plugin", getattr(comp, "plugin", None))

    async def execute(self, current_tick: int) -> None:
        agent = self._get_agent()
        if not agent: return

        state_plugin = self._get_plugin("state")
        profile_plugin = self._get_plugin("profile")
        if not state_plugin or not profile_plugin: return

        # 获取数据
        state_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
        observations = state_data.get("observations")
        if not observations: return

        # 1. 准备上下文数据
        target_info = observations[0]
        info_content = target_info.get("content", "")
        info_source = target_info.get("source", "Unknown")
        current_trust = state_data.get("trust_score", 5.0)

        # 获取画像数据用于构建价值观
        p_data = getattr(profile_plugin, "profile_data", getattr(profile_plugin, "_profile_data", {}))
        psych = p_data.get('psychology', {})
        env_involvement = psych.get('environmental_involvement', 'Light Green')

        # 2. 构建价值观描述
        if env_involvement == 'Deep Green':
            # 深绿价值观：唯证据论，眼里揉不得沙子
            core_values = (
                "You are a skeptic who values scientific evidence and third-party certification above all else. "
                "You inherently distrust corporate marketing unless it is backed by verifiable proof. "
                "Vague claims trigger your suspicion immediately."
            )
        else:
            # 浅绿价值观：实用主义，差不多就行
            core_values = (
                "You care about the environment but prioritize convenience, price, and social trends. "
                "You generally trust well-known brands unless you see a major scandal. "
                "You are tolerant of minor marketing exaggerations."
            )

        # 3. 构造“自发性”Prompt
        prompt = f"""
[Character Profile]
{profile_plugin.get_prompt()}
[Inner Values]
{core_values}

[Current Situation]
- Brand: '{info_source}'
- Your Current Trust: {current_trust}/10.0
- New Info Received: "{info_content}"

[Internal Monologue]
Reflect on this new information through the lens of your Inner Values.
1. **Credibility Check**: Does this information align with your standards for evidence? (e.g. Does "No certification" bother *you* personally?)
2. **Emotional Reaction**: Do you feel reassured, indifferent, or deceived?
3. **Trust Adjustment**: Based on your feelings, naturally adjust your trust score.

Output JSON ONLY:
{{
    "hypocrisy_perceived": true/false,
    "trust_change": float,  // Negative if you feel deceived, positive if impressed.
    "reasoning": "Write a short first-person thought expressing your reaction."
}}
"""
        try:
            # 4. 调用 LLM
            model = getattr(agent, "model", getattr(agent, "_model", None))
            if not model: return

            response = await model.chat(prompt)

            if isinstance(response, str):
                clean_json = response.replace("```json", "").replace("```", "").strip()
                result = json.loads(clean_json)
            elif isinstance(response, list):
                result = response[0]
            else:
                result = response

            # 5. 更新状态
            change = float(result.get("trust_change", 0.0))
            change = max(-3.0, min(3.0, change))

            new_trust = max(0.0, min(10.0, current_trust + change))

            await state_plugin.set_state("trust_score", new_trust)
            await state_plugin.set_state("latest_thought", result)
            # 消费掉信息
            await state_plugin.set_state("observations", [])

            print(
                f"🧠 [Cognition] {agent.agent_id} ({env_involvement}): 信任 {current_trust:.1f} -> {new_trust:.1f} (Δ{change}) | 想法: {result.get('reasoning')[:50]}...")

        except Exception as e:
            print(f"❌ [Cognition Error] {e}")

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass