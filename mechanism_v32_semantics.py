"""Strict semantic contract for the parallel TASK_005 FMCG-v3.2 path.

The active mechanism-v2 schema is intentionally left unchanged.  Scenario
v3.2 adds one construct, perceived peer approval, whose availability is tied to
actual social-feed observations rather than message valence or treatment id.
"""

from __future__ import annotations

import math
from typing import Mapping

from mechanism_v31_cognition import validate_peer_approval_output


SCHEMA = "semantic-appraisal-3.2"
REQUIRED_FIELDS = (
    "valence",
    "arousal",
    "credibility",
    "evidence_strength",
    "topic_relevance",
    "perceived_empathy",
    "perceived_peer_approval",
    "hypocrisy_perceived",
    "importance",
    "reasoning",
)


class SemanticV32ValidationError(ValueError):
    """Raised when an appraisal cannot satisfy the frozen v3.2 schema."""


def _numeric(payload: Mapping, field: str, lo: float, hi: float) -> float:
    if field not in payload:
        raise SemanticV32ValidationError(f"semantic response missing {field}")
    value = payload[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SemanticV32ValidationError(f"semantic response {field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not lo <= number <= hi:
        raise SemanticV32ValidationError(f"semantic response {field} out of range")
    return number


def validate_semantic_payload(
    payload: Mapping,
    *,
    social_observation_count: int,
) -> dict:
    """Validate and normalize one raw semantic response.

    `perceived_peer_approval` must be JSON null when no peer message was
    observed and numeric in [0, 1] otherwise.  This makes it impossible for a
    global event or an enterprise statement alone to move subjective norm.
    """

    if not isinstance(payload, Mapping):
        raise SemanticV32ValidationError("semantic response must be a JSON object")
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise SemanticV32ValidationError(
            "semantic response missing fields: " + ", ".join(missing)
        )

    count = int(social_observation_count)
    if count < 0:
        raise SemanticV32ValidationError("social_observation_count must be non-negative")
    peer_raw = payload["perceived_peer_approval"]
    if count == 0:
        if peer_raw is not None:
            raise SemanticV32ValidationError(
                "perceived_peer_approval must be null without social observations"
            )
        peer_approval = None
    else:
        try:
            peer_approval = validate_peer_approval_output(
                social_observation_count=count,
                perceived_peer_approval=peer_raw,
            )
        except ValueError as exc:
            raise SemanticV32ValidationError(str(exc)) from exc

    hypocrisy = payload["hypocrisy_perceived"]
    if not isinstance(hypocrisy, bool):
        raise SemanticV32ValidationError(
            "semantic response hypocrisy_perceived must be boolean"
        )
    reasoning = payload["reasoning"]
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise SemanticV32ValidationError(
            "semantic response reasoning must be non-empty"
        )

    return {
        "valence": _numeric(payload, "valence", -1.0, 1.0),
        "arousal": _numeric(payload, "arousal", 0.0, 1.0),
        "credibility": _numeric(payload, "credibility", 0.0, 1.0),
        "evidence_strength": _numeric(payload, "evidence_strength", 0.0, 1.0),
        "topic_relevance": _numeric(payload, "topic_relevance", 0.0, 1.0),
        "perceived_empathy": _numeric(payload, "perceived_empathy", 0.0, 1.0),
        "perceived_peer_approval": peer_approval,
        "hypocrisy_perceived": hypocrisy,
        "importance": _numeric(payload, "importance", 1.0, 10.0),
        "reasoning": reasoning.strip(),
    }


def peer_approval_instruction(social_observation_count: int) -> str:
    """Return the prompt rule that matches the observed message composition."""

    if int(social_observation_count) > 0:
        return (
            '"perceived_peer_approval": <float 0 to 1 measuring only the '
            "observed peers' approval of choosing VerdantCo Oat>"
        )
    return (
        '"perceived_peer_approval": null '
        "(required because no social-feed message was observed)"
    )
