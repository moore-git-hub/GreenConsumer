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
        if not comp: return None
        return getattr(comp, "_plugin", getattr(comp, "plugin", None))

    async def execute(self, current_tick: int) -> None:
        agent = self._get_agent()
        if not agent: return

        state_plugin = self._get_plugin("state")
        profile_plugin = self._get_plugin("profile")
        if not state_plugin or not profile_plugin: return

        state_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
        observations = state_data.get("observations")
        if not observations: return

        target_info = observations[0]
        info_content = target_info.get("content", "")
        info_source = target_info.get("source", "Unknown")
        current_trust = state_data.get("trust_score", 5.0)

        p_data = getattr(profile_plugin, "profile_data", getattr(profile_plugin, "_profile_data", {}))
        persona_rules = p_data.get("persona", "你是一名普通消费者。")  # 直接读取生成好的严格画像

        # === RAG 检索执行 ===
        retrieved_memories = state_plugin.retrieve_memory(current_tick, info_content, top_k=3)
        memory_text = "\n".join([f"- {m}" for m in retrieved_memories]) if retrieved_memories else "无相关历史回忆。"

        prompt = f"""
[Character Persona]
{persona_rules}

[Your Historical Memory (Retrieved via RAG)]
{memory_text}

[Current Context]
- Time: Tick {current_tick}
- Source: '{info_source}'
- Your Current Trust: {current_trust}/10.0
- New Info: "{info_content}"

[Task]
Based on your persona and historical memory, evaluate this information. Limited rationality and path dependence applies.
Output JSON ONLY:
{{
    "hypocrisy_perceived": true/false,
    "trust_change": float, // Scale: -1.0 to +1.0
    "importance": float, // Rate importance of this event (1.0 to 10.0) for future memory
    "reasoning": "Short first-person thought."
}}
"""
        try:
            model = getattr(agent, "model", getattr(agent, "_model", None))
            response = await model.chat(prompt)

            if isinstance(response, str):
                clean_json = response.replace("```json", "").replace("```", "").strip()
                result = json.loads(clean_json)
            elif isinstance(response, list):
                result = response[0]
            else:
                result = response

            change = max(-1.0, min(1.0, float(result.get("trust_change", 0.0))))
            new_trust = max(0.0, min(10.0, current_trust + change))

            await state_plugin.set_state("trust_score", new_trust)
            await state_plugin.set_state("latest_thought", result)

            # === 写入记忆库 ===
            importance_score = float(result.get("importance", 5.0))
            memory_entry = f"接收到来源 {info_source} 的消息: {info_content}。我的评价是: {result.get('reasoning')}"
            state_plugin.add_to_memory(current_tick, memory_entry, importance_score)

            await state_plugin.set_state("observations", [])

            print(
                f"🧠 [Cognition] {agent.agent_id} | 信任 {current_trust:.1f}->{new_trust:.1f} | 想法: {result.get('reasoning')[:40]}")
        except Exception as e:
            print(f"❌ [Cognition Error] {e}")

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass