"""Pure cognitive corrections required before TASK_005 scenario-v3.2 pilot."""

from __future__ import annotations

from mechanism_v2 import clip01


SCHEMA = "cognitive-mechanism-3.1"
SUBJECTIVE_NORM_UPDATE_RATE = 0.20
SUBJECTIVE_NORM_MAX_SOCIAL_MESSAGES = 3


def update_subjective_norm(
    *,
    previous_sn: float,
    social_observation_count: int,
    perceived_peer_approval: float | None,
    update_rate: float = SUBJECTIVE_NORM_UPDATE_RATE,
    max_messages: int = SUBJECTIVE_NORM_MAX_SOCIAL_MESSAGES,
) -> float:
    """Update SN only from explicit perceived approval in actual peer messages.

    Global news, enterprise communication and general semantic valence are absent
    from the signature by design. Multiple peer messages increase exposure weight
    with diminishing returns.
    """

    previous = clip01(previous_sn)
    count = int(social_observation_count)
    if count < 0:
        raise ValueError("social_observation_count must be non-negative")
    if count == 0:
        return previous
    if perceived_peer_approval is None:
        raise ValueError("peer approval is required when social observations exist")
    if int(max_messages) <= 0:
        raise ValueError("max_messages must be positive")
    rate = clip01(update_rate)
    approval = clip01(perceived_peer_approval)
    effective_count = min(count, int(max_messages))
    effective_rate = 1.0 - (1.0 - rate) ** effective_count
    return clip01((1.0 - effective_rate) * previous + effective_rate * approval)


def validate_peer_approval_output(
    *,
    social_observation_count: int,
    perceived_peer_approval: object,
) -> float | None:
    """Validate the semantic field before it can enter the SN transition."""

    count = int(social_observation_count)
    if count < 0:
        raise ValueError("social_observation_count must be non-negative")
    if count == 0:
        return None
    if perceived_peer_approval is None or isinstance(perceived_peer_approval, bool):
        raise ValueError("perceived_peer_approval must be numeric for social observations")
    try:
        value = float(perceived_peer_approval)
    except (TypeError, ValueError) as exc:
        raise ValueError("perceived_peer_approval must be numeric") from exc
    if not 0.0 <= value <= 1.0:
        raise ValueError("perceived_peer_approval must be in [0, 1]")
    return value
