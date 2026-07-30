"""
GreenCognitionPlugin — Reflect 层（System 1：快速直觉评估）

修复：无新观察时清空 last_observations 和 latest_thought，
防止 Plan 层跨 Tick 重复识别旧澄清、行为 Prompt 重复使用旧情绪。

职责（不变）：
  对当前观察到的信息做情绪性认知评估，输出情绪冲击量 trust_change_affective。
  不直接修改 trust_score，将冲击量交给 Plan 层（System 2）的确定性公式处理。

审计字段（新增，不影响信任更新）：
  raw_affective_output / affective_was_clipped / reflect_primary_source / reflect_message_sources
"""
import json
import re
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

        # ── 无观察时：清空本 Tick 临时认知缓存 ─────────────────────────
        # 仅清除 Reflect 层写入的临时字段；
        # 不触及 trust_score、baseline_trust、shock_anchor、quiet_ticks、memory。
        if not observations:
            await state_plugin.set_state("trust_change_affective", 0.0)
            await state_plugin.set_state("raw_affective_output", 0.0)
            await state_plugin.set_state("affective_was_clipped", False)
            await state_plugin.set_state("latest_thought", None)
            await state_plugin.set_state("last_observations", [])
            await state_plugin.set_state("reflect_primary_source", "None")
            await state_plugin.set_state("reflect_message_sources", [])
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
            # 澄清内容完整保留（新模板 225+ 词，含具体数据和证据）
            info_parts.append(f"[Brand Statement] {clarifications[0]['content']}")
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
            response = await model.chat(prompt)

            if isinstance(response, str):
                clean = re.sub(r"```(?:json)?", "", response).replace("```", "").strip()
                # 规范化 Python 字面量 → JSON 合法值（模型偶尔输出 Python 而非 JSON）
                clean = re.sub(r'\bNone\b',  'null',  clean)
                clean = re.sub(r'\bTrue\b',  'true',  clean)
                clean = re.sub(r'\bFalse\b', 'false', clean)
                match = re.search(r'\{.*\}', clean, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError:
                        # 二次修复：强制用 ast.literal_eval 尝试解析（兼容 Python 字面量混入）
                        import ast
                        try:
                            result = ast.literal_eval(json_str)
                        except Exception:
                            # 三次修复：逐字段正则抽取，放弃整体解析
                            result = {
                                "hypocrisy_perceived": bool(re.search(r'"hypocrisy_perceived"\s*:\s*true', json_str, re.I)),
                                "trust_change_affective": float(m.group(1)) if (m := re.search(r'"trust_change_affective"\s*:\s*(-?[\d.]+)', json_str)) else 0.0,
                                "importance": float(m.group(1)) if (m := re.search(r'"importance"\s*:\s*([\d.]+)', json_str)) else 5.0,
                                "reasoning": m.group(1) if (m := re.search(r'"reasoning"\s*:\s*"([^"]*)"', json_str)) else "",
                            }
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
            was_clipped = abs(raw_change - affective_change) > 1e-12

            importance_score = max(1.0, min(10.0, float(result.get("importance", 5.0))))

            # ── 写入 state（不修改 trust_score，交给 Plan 层处理） ────────
            await state_plugin.set_state("raw_affective_output", raw_change)
            await state_plugin.set_state("trust_change_affective", affective_change)
            await state_plugin.set_state("affective_was_clipped", was_clipped)
            await state_plugin.set_state("latest_thought", result)
            await state_plugin.set_state("reflect_primary_source", primary_source)
            await state_plugin.set_state("reflect_message_sources",
                                         sorted({str(o.get("source", "Unknown")) for o in observations}))

            # ── 写入记忆库 ───────────────────────────────────────────────
            memory_entry = (
                f"[Tick {current_tick}] Source={primary_source} | "
                f"Info: {combined_info[:100]} | "
                f"My reaction: {result.get('reasoning', '')}"
            )
            state_plugin.add_to_memory(current_tick, memory_entry, importance_score)

            # ── 保存本 Tick 观察快照供 Plan 层读取，然后清空 observations ──
            # Plan 在 Reflect 之后执行，此时 observations 已被消费；
            # 用 last_observations 保留一份只读副本，让 Plan 层能检测澄清等事件类型
            await state_plugin.set_state("last_observations", list(observations))
            await state_plugin.set_state("observations", [])

            print(f"[Reflect] {agent.agent_id} | "
                  f"Affective raw={raw_change:+.2f}, used={affective_change:+.2f} | "
                  f"Hypocrisy: {result.get('hypocrisy_perceived', False)} | "
                  f"Importance: {importance_score:.1f}")

        except Exception as e:
            # 打印原始响应帮助诊断（仅前200字符）
            try:
                raw = str(response)[:200] if "response" in locals() else "N/A"
            except Exception:
                raw = "N/A"
            print(f"❌ [Cognition Error] {agent.agent_id} Tick {current_tick}: {e}")
            print(f"   RAW RESPONSE: {raw!r}")
            # 失败时：清空临时缓存，Plan 层仍可正常执行遗忘曲线
            await state_plugin.set_state("raw_affective_output", 0.0)
            await state_plugin.set_state("trust_change_affective", 0.0)
            await state_plugin.set_state("affective_was_clipped", False)
            await state_plugin.set_state("latest_thought", None)
            await state_plugin.set_state("reflect_primary_source", primary_source)
            await state_plugin.set_state("reflect_message_sources",
                                         sorted({str(o.get("source", "Unknown")) for o in observations}))
            await state_plugin.set_state("last_observations", list(observations))
            await state_plugin.set_state("observations", [])

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass
