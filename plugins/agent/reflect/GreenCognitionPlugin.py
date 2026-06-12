"""
GreenCognitionPlugin — Reflect 层（System 1：快速直觉评估）

职责：
  对当前观察到的信息做情绪性认知评估，输出情绪冲击量 trust_change_affective。
  不直接修改 trust_score，将冲击量交给 Plan 层（System 2）的确定性公式处理。

双过程理论（Dual Process Theory）对应：
  System 1（本层）：快速、情绪性、基于直觉的即时反应
  System 2（Plan层）：慢速、理性、基于规则的深思熟虑
"""
import json
import re
import math
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

        # ── 无观察时：情绪冲击归零，System 2 将只执行遗忘曲线 ──────────
        if not observations:
            await state_plugin.set_state("trust_change_affective", 0.0)
            return

        # ── 聚合多条观察（全局新闻优先，企业澄清次之，社交帖子补充） ──
        global_news = [o for o in observations if o.get("source") == "Global News"]
        clarifications = [o for o in observations if o.get("source") == "Enterprise_Clarification"]
        social_posts = [o for o in observations if o.get("source") in ("Social", "social_review")]
        other_obs = [o for o in observations
                     if o not in global_news and o not in clarifications and o not in social_posts]

        info_parts = []
        primary_source = "Unknown"

        if global_news:
            primary_source = "Global News"
            info_parts.append(f"[Breaking News] {global_news[0]['content']}")
        if clarifications:
            if not global_news:
                primary_source = "Enterprise_Clarification"
            info_parts.append(f"[Brand Statement] {clarifications[0]['content'][:200]}")
        if social_posts:
            # 最多取 2 条社交帖子，防止 Prompt 过长
            for p in social_posts[:2]:
                info_parts.append(f"[Social Feed] {p['content'][:120]}")
            if not global_news and not clarifications:
                primary_source = "Social"
        if other_obs and not info_parts:
            primary_source = other_obs[0].get("source", "Unknown")
            info_parts.append(other_obs[0].get("content", ""))

        combined_info = "\n".join(info_parts)
        current_trust = float(state_data.get("trust_score", 5.0))

        p_data = getattr(profile_plugin, "profile_data", getattr(profile_plugin, "_profile_data", {}))
        persona_rules = p_data.get("persona", "You are a consumer.")

        # ── RAG 记忆检索 ─────────────────────────────────────────────
        retrieved_memories = state_plugin.retrieve_memory(current_tick, combined_info, top_k=3)
        memory_text = (
            "\n".join([f"- {m}" for m in retrieved_memories])
            if retrieved_memories else "No relevant past memories."
        )

        # ── System 1 Prompt：只评估情绪冲击，不做行为决策 ───────────────
        prompt = f"""
[Character Persona]
{persona_rules}

[Your Historical Memory (Retrieved via RAG)]
{memory_text}

[Current Context]
- Time: Tick {current_tick}
- Primary Source: '{primary_source}'
- Your Current Trust Score: {current_trust:.1f}/10.0
- Information Received:
{combined_info}

[Your Task — System 1 (Fast, Intuitive Reaction)]
You are experiencing an immediate emotional reaction to this information.
Do NOT think about long-term consequences or rational analysis — just feel.
React as YOUR character would in this moment.

Output JSON ONLY:
{{
    "hypocrisy_perceived": <true or false — do you feel the brand is being hypocritical?>,
    "trust_change_affective": <float, -2.0 to +1.5 — how much does this emotionally move you?>,
    "importance": <float, 1.0 to 10.0 — how memorable will this be for you?>,
    "reasoning": "One sentence first-person gut reaction. (STRICTLY IN ENGLISH)"
}}

Scale guidance for trust_change_affective:
  -2.0: "I feel deeply betrayed, this is personal"
  -1.0: "This is concerning and disappointing"
  -0.3: "Hmm, that's a bit worrying I guess"
   0.0: "I don't really care about this"
  +0.5: "That's reassuring, good to hear"
  +1.5: "Wow, they really proved themselves, I'm impressed"

Remember: your PERSONA determines your sensitivity.
A Non-Greens consumer barely reacts to environmental news.
An Active Greens consumer takes greenwashing as a personal betrayal.
React authentically as YOUR character — not as a generic consumer.

SOURCE CONTEXT:
  - [Breaking News]: direct, verified information — react at full intensity
  - [Social Feed]: second-hand opinions from peers — react with less certainty (roughly half intensity)
  - [Brand Statement]: corporate communication — judge its sincerity based on your persona
"""
        try:
            model = getattr(agent, "model", getattr(agent, "_model", None))
            response = await model.chat(prompt)

            if isinstance(response, str):
                clean = re.sub(r"```(?:json)?", "", response).replace("```", "").strip()
                match = re.search(r'\{.*\}', clean, re.DOTALL)
                if match:
                    result = json.loads(match.group(0))
                else:
                    raise ValueError(f"No JSON found in response: {response[:80]}...")
            elif isinstance(response, list):
                result = response[0]
            else:
                result = response

            # 情绪冲击量：范围 [-2, +1.5]，不直接修改 trust_score
            raw_change = float(result.get("trust_change_affective",
                                          result.get("trust_change", 0.0)))
            affective_change = max(-2.0, min(1.5, raw_change))

            importance_score = max(1.0, min(10.0, float(result.get("importance", 5.0))))

            # ── 写入 state（不修改 trust_score，交给 Plan 层处理） ────────
            await state_plugin.set_state("trust_change_affective", affective_change)
            await state_plugin.set_state("latest_thought", result)

            # ── 写入记忆库 ───────────────────────────────────────────────
            memory_entry = (
                f"[Tick {current_tick}] Source={primary_source} | "
                f"Info: {combined_info[:100]} | "
                f"My reaction: {result.get('reasoning', '')}"
            )
            state_plugin.add_to_memory(current_tick, memory_entry, importance_score)

            await state_plugin.set_state("observations", [])

            print(f"[Reflect] {agent.agent_id} | "
                  f"Affective Δ: {affective_change:+.2f} | "
                  f"Hypocrisy: {result.get('hypocrisy_perceived', False)} | "
                  f"Importance: {importance_score:.1f}")

        except Exception as e:
            print(f"❌ [Cognition Error] {agent.agent_id} Tick {current_tick}: {e}")
            # 失败时情绪冲击归零，Plan 层仍可正常执行遗忘曲线
            await state_plugin.set_state("trust_change_affective", 0.0)
            await state_plugin.set_state("observations", [])

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass
