"""
GreenCognitionPlugin — Reflect 层（System 1：快速直觉评估）

本修订版修复两个状态残留问题：
1. 无新观察时清空 last_observations，防止前一 Tick 的澄清被 Plan 层重复识别；
2. 无新观察时清空 latest_thought，防止旧情绪被行为决策 Prompt 无限重复使用。

同时新增不改变信任更新机制的审计字段：
- raw_affective_output：LLM 原始数值输出；
- trust_change_affective：量表边界处理后的 Reflect 输出；
- affective_was_clipped：是否发生边界截断；
- reflect_primary_source / reflect_message_sources；
- reflect_parse_error。
"""
import json
import re
from agentkernel_standalone.mas.agent.base.plugin_base import ReflectPlugin


class GreenCognitionPlugin(ReflectPlugin):
    async def init(self):
        pass

    def _get_agent(self):
        if hasattr(self, "agent") and self.agent:
            return self.agent
        if self.component and hasattr(self.component, "agent"):
            return self.component.agent
        if hasattr(self, "_component") and self._component:
            return self._component.agent
        return None

    def _get_plugin(self, name):
        agent = self._get_agent()
        if not agent:
            return None
        comp = agent.get_component(name)
        if not comp:
            return None
        return getattr(comp, "_plugin", getattr(comp, "plugin", None))

    async def _reset_no_observation_state(self, state_plugin) -> None:
        """清空仅应在当前 Tick 有效的 Reflect 状态。"""
        await state_plugin.set_state("trust_change_affective", 0.0)
        await state_plugin.set_state("raw_affective_output", 0.0)
        await state_plugin.set_state("affective_was_clipped", False)
        await state_plugin.set_state("latest_thought", None)
        await state_plugin.set_state("last_observations", [])
        await state_plugin.set_state("reflect_primary_source", "None")
        await state_plugin.set_state("reflect_message_sources", [])
        await state_plugin.set_state("reflect_parse_error", "")

    async def execute(self, current_tick: int) -> None:
        agent = self._get_agent()
        if not agent:
            return

        state_plugin = self._get_plugin("state")
        profile_plugin = self._get_plugin("profile")
        if not state_plugin or not profile_plugin:
            return

        state_data = getattr(
            state_plugin,
            "state_data",
            getattr(state_plugin, "_state_data", {}),
        )
        observations = state_data.get("observations") or []

        # 无新观察时，当前 Tick 不应继承上一 Tick 的观察类型或即时情绪。
        # 否则：
        # - 澄清会被 Plan 层连续多日误判为“当天仍收到澄清”；
        # - latest_thought 会在行为决策 Prompt 中被无限重复使用。
        if not observations:
            await self._reset_no_observation_state(state_plugin)
            return

        # 聚合多条观察（全局新闻优先，企业澄清次之，社交帖子补充）。
        global_news = [o for o in observations if o.get("source") == "Global News"]
        clarifications = [
            o for o in observations
            if o.get("source") == "Enterprise_Clarification"
        ]
        social_posts = [
            o for o in observations
            if o.get("source") in ("Social", "social_review")
        ]
        other_obs = [
            o for o in observations
            if o not in global_news
            and o not in clarifications
            and o not in social_posts
        ]

        info_parts = []
        primary_source = "Unknown"

        if global_news:
            primary_source = "Global News"
            info_parts.append(f"[Breaking News] {global_news[0]['content']}")
        if clarifications:
            if not global_news:
                primary_source = "Enterprise_Clarification"
            info_parts.append(f"[Brand Statement] {clarifications[0]['content']}")
        if social_posts:
            for post in social_posts[:2]:
                info_parts.append(f"[Social Feed] {post['content'][:120]}")
            if not global_news and not clarifications:
                primary_source = "Social"
        if other_obs and not info_parts:
            primary_source = other_obs[0].get("source", "Unknown")
            info_parts.append(other_obs[0].get("content", ""))

        combined_info = "\n".join(info_parts)
        current_trust = float(state_data.get("trust_score", 5.0))
        message_sources = sorted(
            {str(o.get("source", "Unknown")) for o in observations}
        )

        p_data = getattr(
            profile_plugin,
            "profile_data",
            getattr(profile_plugin, "_profile_data", {}),
        )
        persona_rules = p_data.get("persona", "You are a consumer.")

        retrieved_memories = state_plugin.retrieve_memory(
            current_tick,
            combined_info,
            top_k=3,
        )
        memory_text = (
            "\n".join([f"- {m}" for m in retrieved_memories])
            if retrieved_memories
            else "No relevant past memories."
        )

        # 本补丁仅修复状态残留与增加日志，不在此阶段移除数值信任输入。
        # “是否向 Reflect 暴露精确信任分”应作为后续独立消融实验处理。
        prompt = f"""
[Character Persona]
{persona_rules}

[Your Past Experiences (Retrieved from Memory)]
{memory_text}

[What You Just Encountered]
- Source: '{primary_source}'
- Your Current Trust Score: {current_trust:.1f}/10.0
- Information:
{combined_info}

[Your Task — Immediate Gut Reaction]
Something just reached you. React the way YOUR character naturally would —
based on who you are, what you care about, and what this information means to you.
Be honest and specific about your emotional response.

Output JSON ONLY:
{{
    "hypocrisy_perceived": <true or false — does this feel dishonest or contradictory?>,
    "trust_change_affective": <float, -2.0 to +1.5 — how much does this move you emotionally?>,
    "importance": <float, 1.0 to 10.0 — how much will this stick with you?>,
    "reasoning": "One sentence in first person describing your gut reaction. (IN ENGLISH)"
}}

Scale for trust_change_affective:
  -2.0  deep personal betrayal
  -1.0  genuinely concerned and disappointed
  -0.3  slightly unsettled
   0.0  indifferent
  +0.5  reassured, this is good to know
  +1.5  genuinely impressed, trust significantly restored

SOURCE CONTEXT:
  - [Breaking News]: external report — assess severity and credibility of the claims
  - [Social Feed]: a peer's opinion — weigh with moderate skepticism, people exaggerate online
  - [Brand Statement]: this is a clarification issued AFTER a controversy. The company is
    attempting to address your concerns. Even if the statement reminds you of the original
    issue, consider whether it provides genuine transparency (specific data, named auditors,
    verifiable commitments) that partially restores your confidence. A clarification that
    acknowledges wrongdoing AND provides evidence of corrective action is more credible than
    one that only deflects. Weigh the net effect: does this make you feel somewhat better
    or somewhat worse compared to having no statement at all?
"""

        try:
            model = getattr(agent, "model", getattr(agent, "_model", None))
            if not model:
                raise RuntimeError("Agent has no model router")

            response = await model.chat(prompt)

            if isinstance(response, str):
                clean = re.sub(r"```(?:json)?", "", response).replace("```", "").strip()
                clean = re.sub(r"\bNone\b", "null", clean)
                clean = re.sub(r"\bTrue\b", "true", clean)
                clean = re.sub(r"\bFalse\b", "false", clean)
                match = re.search(r"\{.*\}", clean, re.DOTALL)
                if not match:
                    raise ValueError(f"No JSON found in response: {response[:80]}...")

                json_str = match.group(0)
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    import ast
                    try:
                        result = ast.literal_eval(json_str)
                    except Exception:
                        result = {
                            "hypocrisy_perceived": bool(
                                re.search(
                                    r'"hypocrisy_perceived"\s*:\s*true',
                                    json_str,
                                    re.I,
                                )
                            ),
                            "trust_change_affective": float(m.group(1))
                            if (
                                m := re.search(
                                    r'"trust_change_affective"\s*:\s*(-?[\d.]+)',
                                    json_str,
                                )
                            )
                            else 0.0,
                            "importance": float(m.group(1))
                            if (
                                m := re.search(
                                    r'"importance"\s*:\s*([\d.]+)',
                                    json_str,
                                )
                            )
                            else 5.0,
                            "reasoning": m.group(1)
                            if (
                                m := re.search(
                                    r'"reasoning"\s*:\s*"([^"]*)"',
                                    json_str,
                                )
                            )
                            else "",
                        }
            elif isinstance(response, list):
                result = response[0]
            else:
                result = response

            if not isinstance(result, dict):
                raise TypeError(f"Reflect output must be dict, got {type(result).__name__}")

            raw_change = float(
                result.get(
                    "trust_change_affective",
                    result.get("trust_change", 0.0),
                )
            )
            affective_change = max(-2.0, min(1.5, raw_change))
            was_clipped = abs(raw_change - affective_change) > 1e-12
            importance_score = max(
                1.0,
                min(10.0, float(result.get("importance", 5.0))),
            )

            await state_plugin.set_state("raw_affective_output", raw_change)
            await state_plugin.set_state(
                "trust_change_affective",
                affective_change,
            )
            await state_plugin.set_state("affective_was_clipped", was_clipped)
            await state_plugin.set_state("latest_thought", result)
            await state_plugin.set_state("reflect_primary_source", primary_source)
            await state_plugin.set_state("reflect_message_sources", message_sources)
            await state_plugin.set_state("reflect_parse_error", "")

            memory_entry = (
                f"[Tick {current_tick}] Source={primary_source} | "
                f"Info: {combined_info[:100]} | "
                f"My reaction: {result.get('reasoning', '')}"
            )
            state_plugin.add_to_memory(
                current_tick,
                memory_entry,
                importance_score,
            )

            # 快照只对当前 Tick 有效；下一 Tick 无观察时会明确清空。
            await state_plugin.set_state("last_observations", list(observations))
            await state_plugin.set_state("observations", [])

            print(
                f"[Reflect] {agent.agent_id} | "
                f"Affective raw={raw_change:+.2f}, used={affective_change:+.2f} | "
                f"Hypocrisy: {result.get('hypocrisy_perceived', False)} | "
                f"Importance: {importance_score:.1f}"
            )

        except Exception as exc:
            try:
                raw_response = str(response)[:200] if "response" in locals() else "N/A"
            except Exception:
                raw_response = "N/A"

            print(
                f"❌ [Cognition Error] {agent.agent_id} "
                f"Tick {current_tick}: {exc}"
            )
            print(f"   RAW RESPONSE: {raw_response!r}")

            await state_plugin.set_state("raw_affective_output", 0.0)
            await state_plugin.set_state("trust_change_affective", 0.0)
            await state_plugin.set_state("affective_was_clipped", False)
            await state_plugin.set_state("latest_thought", None)
            await state_plugin.set_state("reflect_primary_source", primary_source)
            await state_plugin.set_state("reflect_message_sources", message_sources)
            await state_plugin.set_state("reflect_parse_error", str(exc)[:500])
            await state_plugin.set_state("last_observations", list(observations))
            await state_plugin.set_state("observations", [])

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass
