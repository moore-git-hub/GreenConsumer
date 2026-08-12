"""Deterministic, network-free semantic fixture for scenario-v3.2 smoke tests."""

from __future__ import annotations

import json


class DeterministicFMCGSemanticRouterV32:
    """Return schema-valid appraisals based only on the observed prompt text."""

    is_fake_router = True
    _task005_router_close_noop = True

    def __init__(self):
        self.call_count = 0
        self.categories: list[str] = []
        self.prompts: list[str] = []
        self.current_tick: int | None = None

    def set_tick(self, tick: int) -> None:
        self.current_tick = int(tick)

    @staticmethod
    def _peer_approval(prompt: str) -> float | None:
        if "[Social Feed]" not in prompt:
            return None
        lowered = prompt.lower()
        if "structured, checkable evidence" in lowered:
            return 0.72
        if "acknowledges consumer concern" in lowered:
            return 0.76
        if "concerned" in lowered or "controversy" in lowered:
            return 0.22
        return 0.50

    async def chat(self, prompt: str) -> str:
        self.call_count += 1
        self.prompts.append(prompt)
        peer_approval = self._peer_approval(prompt)

        if "[Brand Statement]" in prompt and (
            "structured response" in prompt
            or "verification, auditability" in prompt
        ):
            self.categories.append("rational_statement")
            payload = {
                "valence": 0.50,
                "arousal": 0.45,
                "credibility": 0.90,
                "evidence_strength": 0.95,
                "topic_relevance": 0.90,
                "perceived_empathy": 0.30,
                "perceived_peer_approval": peer_approval,
                "hypocrisy_perceived": False,
                "importance": 7,
                "reasoning": (
                    "I see structured, checkable evidence in the fictional "
                    "brand statement."
                ),
            }
        elif "[Brand Statement]" in prompt and (
            "acknowledges why" in prompt or "relationship repair" in prompt
        ):
            self.categories.append("empathy_statement")
            payload = {
                "valence": 0.72,
                "arousal": 0.72,
                "credibility": 0.72,
                "evidence_strength": 0.35,
                "topic_relevance": 0.90,
                "perceived_empathy": 0.88,
                "perceived_peer_approval": peer_approval,
                "hypocrisy_perceived": False,
                "importance": 7,
                "reasoning": (
                    "I feel the fictional brand acknowledges consumer concern."
                ),
            }
        elif "[Breaking News]" in prompt:
            self.categories.append("breaking_news")
            payload = {
                "valence": -0.85,
                "arousal": 0.80,
                "credibility": 0.80,
                "evidence_strength": 0.65,
                "topic_relevance": 0.95,
                "perceived_empathy": 0.10,
                "perceived_peer_approval": peer_approval,
                "hypocrisy_perceived": True,
                "importance": 8,
                "reasoning": (
                    "I am concerned because the fictional controversy appears "
                    "relevant and credible."
                ),
            }
        elif "[Social Feed]" in prompt:
            self.categories.append("social_feed")
            social_valence = 2.0 * float(peer_approval) - 1.0
            payload = {
                "valence": social_valence,
                "arousal": 0.30,
                "credibility": 0.45,
                "evidence_strength": 0.20,
                "topic_relevance": 0.55,
                "perceived_empathy": 0.10,
                "perceived_peer_approval": peer_approval,
                "hypocrisy_perceived": peer_approval < 0.4,
                "importance": 4,
                "reasoning": "The peer message shaped my perceived social approval.",
            }
        else:
            raise RuntimeError("unknown scenario-v3.2 semantic prompt")
        return json.dumps(payload, sort_keys=True)
