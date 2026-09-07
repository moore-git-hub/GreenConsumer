"""Scenario-v3.3 semantic appraisal with complete peer-message preservation.

This plugin is intentionally parallel to GreenCognitionV32Plugin. The scientific
semantic schema and appraisal prompt are unchanged, except that observed peer
posts are passed to the receiving LLM without the legacy ``[:180]`` character
truncation. This prevents an engineering text-cutoff artifact from entering
peer approval, SN, Trust, and downstream posting dynamics.

No Trust, demand, network, treatment, seed, or LLM-temperature parameter is
changed here.
"""
from __future__ import annotations

import ast
import json
import re

from agentkernel_standalone.mas.agent.base.plugin_base import ReflectPlugin

from mechanism_v2 import semantic_to_affective
from mechanism_v32_semantics import (
    SCHEMA,
    peer_approval_instruction,
    validate_semantic_payload,
)


class GreenCognitionV33Plugin(ReflectPlugin):
    """Parse observed semantics without deciding purchase or posting behavior."""

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
        component = agent.get_component(name)
        return (
            getattr(component, "_plugin", getattr(component, "plugin", None))
            if component
            else None
        )

    @staticmethod
    def _parse(response):
        if isinstance(response, dict):
            return dict(response)
        if isinstance(response, list):
            if not response:
                raise ValueError("empty response")
            return GreenCognitionV33Plugin._parse(response[0])
        if not isinstance(response, str):
            raise ValueError("unsupported response")
        cleaned = re.sub(r"```(?:json)?", "", response).replace("```", "").strip()
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            raise ValueError("no JSON object")
        try:
            return json.loads(match.group(0))
        except Exception:
            value = ast.literal_eval(match.group(0))
            if not isinstance(value, dict):
                raise ValueError("semantic response is not a mapping")
            return value

    @staticmethod
    def _render_social_feed_content(row: dict) -> str:
        """Return the complete peer-post payload presented to the receiver.

        The existing ``social[:2]`` message-count limit is retained, but each
        selected peer post is no longer truncated at an arbitrary character
        boundary.
        """
        return str((row or {}).get("content", ""))

    async def _set_many(self, state_plugin, values):
        for key, value in values.items():
            await state_plugin.set_state(key, value)

    async def execute(self, current_tick: int) -> None:
        agent = self._get_agent()
        if not agent:
            return
        state_plugin = self._get_plugin("state")
        profile_plugin = self._get_plugin("profile")
        if not state_plugin or not profile_plugin:
            return

        state_data = getattr(
            state_plugin, "state_data", getattr(state_plugin, "_state_data", {})
        )
        observations = state_data.get("observations") or []
        if not observations:
            await self._set_many(
                state_plugin,
                {
                    "semantic_schema_version": SCHEMA,
                    "semantic_valence": 0.0,
                    "semantic_arousal": 0.0,
                    "semantic_credibility": 0.5,
                    "semantic_evidence_strength": 0.0,
                    "semantic_topic_relevance": 0.0,
                    "semantic_perceived_empathy": 0.0,
                    "semantic_perceived_peer_approval": None,
                    "semantic_hypocrisy_perceived": False,
                    "semantic_observation_present": False,
                    "semantic_social_observation_count": 0,
                    "raw_affective_output": 0.0,
                    "trust_change_affective": 0.0,
                    "affective_was_clipped": False,
                    "latest_thought": None,
                    "last_observations": [],
                    "reflect_primary_source": "None",
                    "reflect_message_sources": [],
                },
            )
            return

        global_news = [
            row for row in observations if row.get("source") == "Global News"
        ]
        clarification = [
            row
            for row in observations
            if row.get("source") == "Enterprise_Clarification"
        ]
        social = [
            row
            for row in observations
            if row.get("source") in ("Social", "social_review")
        ]

        parts = []
        primary = "Unknown"
        if global_news:
            primary = "Global News"
            parts.append(f"[Breaking News] {global_news[0].get('content', '')}")
        if clarification:
            if not global_news:
                primary = "Enterprise_Clarification"
            parts.append(f"[Brand Statement] {clarification[0].get('content', '')}")
        if social:
            for row in social[:2]:
                parts.append(
                    f"[Social Feed] {self._render_social_feed_content(row)}"
                )
            if not global_news and not clarification:
                primary = "Social"
        if not parts:
            parts = [str(observations[0].get("content", ""))]
            primary = str(observations[0].get("source", "Unknown"))

        information = "\n".join(parts)
        profile_data = getattr(
            profile_plugin,
            "profile_data",
            getattr(profile_plugin, "_profile_data", {}),
        )
        persona = profile_data.get("persona", "You are a consumer.")
        memories = state_plugin.retrieve_memory(current_tick, information, top_k=3)
        peer_rule = peer_approval_instruction(len(social))

        prompt = f"""
[Character Persona]
{persona}
[Past Experiences]
{chr(10).join('- ' + str(item) for item in memories) if memories else 'None'}
[Information]
Source: {primary}
{information}

Return one JSON object only. Appraise the information actually observed. Do not
decide buying, brand choice, or posting. `perceived_peer_approval` measures only
whether observed peers approve choosing VerdantCo Oat; never infer it from news,
the brand statement, general valence, or your own opinion.
{{
 "valence": <float -1 to 1>,
 "arousal": <float 0 to 1>,
 "credibility": <float 0 to 1>,
 "evidence_strength": <float 0 to 1>,
 "topic_relevance": <float 0 to 1>,
 "perceived_empathy": <float 0 to 1>,
 {peer_rule},
 "hypocrisy_perceived": <boolean>,
 "importance": <float 1 to 10>,
 "reasoning": "<one concise first-person sentence in English>"
}}
"""

        try:
            model = getattr(agent, "model", getattr(agent, "_model", None))
            if not model:
                raise RuntimeError("model missing")
            parsed = self._parse(await model.chat(prompt))
            semantic = validate_semantic_payload(
                parsed,
                social_observation_count=len(social),
            )
            affect = semantic_to_affective(
                semantic["valence"],
                semantic["arousal"],
                semantic["credibility"],
            )
            thought = dict(semantic)
            thought["trust_change_affective"] = affect
            values = {
                "semantic_schema_version": SCHEMA,
                "semantic_valence": semantic["valence"],
                "semantic_arousal": semantic["arousal"],
                "semantic_credibility": semantic["credibility"],
                "semantic_evidence_strength": semantic["evidence_strength"],
                "semantic_topic_relevance": semantic["topic_relevance"],
                "semantic_perceived_empathy": semantic["perceived_empathy"],
                "semantic_perceived_peer_approval": semantic[
                    "perceived_peer_approval"
                ],
                "semantic_hypocrisy_perceived": semantic["hypocrisy_perceived"],
                "semantic_observation_present": True,
                "semantic_social_observation_count": len(social),
                "raw_affective_output": affect,
                "trust_change_affective": affect,
                "affective_was_clipped": False,
                "latest_thought": thought,
                "reflect_primary_source": primary,
                "reflect_message_sources": sorted(
                    {str(row.get("source", "Unknown")) for row in observations}
                ),
                "last_observations": list(observations),
                "observations": [],
            }
            await self._set_many(state_plugin, values)
            state_plugin.add_to_memory(
                current_tick,
                (
                    f"[Tick {current_tick}] {primary} "
                    f"V={semantic['valence']:+.2f} "
                    f"C={semantic['credibility']:.2f} "
                    f"E={semantic['evidence_strength']:.2f} | "
                    f"{semantic['reasoning']}"
                ),
                semantic["importance"],
            )
        except Exception as exc:
            print(
                f"[Reflect-v3.3 ERROR] {agent.agent_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            await self._set_many(
                state_plugin,
                {
                    "semantic_schema_version": SCHEMA,
                    "semantic_valence": 0.0,
                    "semantic_arousal": 0.0,
                    "semantic_credibility": 0.5,
                    "semantic_evidence_strength": 0.0,
                    "semantic_topic_relevance": 0.0,
                    "semantic_perceived_empathy": 0.0,
                    "semantic_perceived_peer_approval": None,
                    "semantic_hypocrisy_perceived": False,
                    "semantic_observation_present": True,
                    "semantic_social_observation_count": len(social),
                    "raw_affective_output": 0.0,
                    "trust_change_affective": 0.0,
                    "affective_was_clipped": False,
                    "latest_thought": {
                        "valence": 0.0,
                        "arousal": 0.0,
                        "credibility": 0.5,
                        "evidence_strength": 0.0,
                        "topic_relevance": 0.0,
                        "perceived_empathy": 0.0,
                        "perceived_peer_approval": None,
                        "hypocrisy_perceived": False,
                        "importance": 0.0,
                        "reasoning": "",
                        "semantic_fallback_used": True,
                    },
                    "reflect_primary_source": primary,
                    "reflect_message_sources": sorted(
                        {str(row.get("source", "Unknown")) for row in observations}
                    ),
                    "last_observations": list(observations),
                    "observations": [],
                },
            )

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass
