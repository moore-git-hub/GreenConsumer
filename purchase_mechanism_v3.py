"""Construct-valid purchase opportunity and focal-brand choice bridge.

This module is deliberately parallel to the frozen mechanism-v2 production path.
It contains no treatment labels and makes no claim that its assumptions are
empirically calibrated.  Promotion into production requires a separate review.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from mechanism_v2 import clip01, deterministic_uniform, sigmoid


SCHEMA = "purchase-bridge-3.0"
DEFAULT_OPPORTUNITY_INTERVAL_TICKS = 7
CHOICE_ACTION_LABEL = "brand_choice_v3"


def _phase_hash(seed: int, agent_id: str) -> int:
    payload = f"{int(seed)}|{str(agent_id)}|purchase-opportunity-v3".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def opportunity_phase(
    *,
    seed: int,
    agent_id: str,
    interval_ticks: int = DEFAULT_OPPORTUNITY_INTERVAL_TICKS,
) -> int:
    """Return a stable agent-specific phase in ``[0, interval_ticks)``."""

    interval = int(interval_ticks)
    if interval <= 0:
        raise ValueError("interval_ticks must be positive")
    return _phase_hash(seed, agent_id) % interval


def is_post_crisis_purchase_opportunity(
    *,
    seed: int,
    agent_id: str,
    tick: int,
    scandal_tick: int = 5,
    interval_ticks: int = DEFAULT_OPPORTUNITY_INTERVAL_TICKS,
) -> bool:
    """Condition-invariant recurring opportunity after the crisis.

    The first possible opportunity is ``scandal_tick + 1 + phase``.  No
    treatment identity, semantic score, trust state or prior purchase enters the
    schedule.
    """

    current_tick = int(tick)
    crisis_tick = int(scandal_tick)
    phase = opportunity_phase(
        seed=seed,
        agent_id=agent_id,
        interval_ticks=interval_ticks,
    )
    first_tick = crisis_tick + 1 + phase
    return current_tick >= first_tick and (
        (current_tick - first_tick) % int(interval_ticks) == 0
    )


def update_pbc_from_facilitation(
    *,
    previous_pbc: float,
    facilitation_observed: bool,
    facilitation_signal: float,
    update_rate: float,
) -> float:
    """Update PBC only when a separately identified facilitation is observed.

    ``update_rate`` has no default on purpose: it must be externally justified
    or frozen prospectively, rather than chosen to obtain a desired purchase
    result.
    """

    previous = clip01(previous_pbc)
    if not bool(facilitation_observed):
        return previous
    signal = clip01(facilitation_signal)
    rate = clip01(update_rate)
    return clip01(previous + rate * signal * (1.0 - previous))


def tpb_purchase_intention(
    *,
    attitude_att: float,
    subjective_norm_sn: float,
    pbc: float,
    trust: float,
) -> float:
    """Exact v2 TPB intention equation, retained for construct-only replay."""

    att = clip01(attitude_att)
    sn = clip01(subjective_norm_sn)
    control = clip01(pbc)
    trust01 = max(0.0, min(1.0, float(trust) / 10.0))
    z = (
        -0.50
        + 1.40 * (att - 0.5)
        + 0.80 * (sn - 0.5)
        + 0.60 * (control - 0.5)
        + 1.20 * (trust01 - 0.5)
    )
    return sigmoid(z)


@dataclass(frozen=True)
class PurchaseChoice:
    opportunity: bool
    choice_probability: float | None
    choice_draw: float | None
    focal_brand_chosen: bool


def purchase_choice(
    *,
    seed: int,
    agent_id: str,
    tick: int,
    purchase_intention: float,
    scandal_tick: int = 5,
    interval_ticks: int = DEFAULT_OPPORTUNITY_INTERVAL_TICKS,
) -> PurchaseChoice:
    """Generate one conditional focal-brand choice without an absorbing state."""

    opportunity = is_post_crisis_purchase_opportunity(
        seed=seed,
        agent_id=agent_id,
        tick=tick,
        scandal_tick=scandal_tick,
        interval_ticks=interval_ticks,
    )
    if not opportunity:
        return PurchaseChoice(False, None, None, False)
    probability = clip01(purchase_intention)
    draw = deterministic_uniform(seed, agent_id, tick, CHOICE_ACTION_LABEL)
    return PurchaseChoice(True, probability, draw, draw < probability)
