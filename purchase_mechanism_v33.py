"""TASK_005 FMCG v3.3 renewal repeat-choice mechanism.

Parallel to purchase_mechanism_v31/v32.  The v3.2 demand path remains frozen.

v3.3 changes only two structural assumptions:
1. category-purchase opportunities follow a reproducible renewal process: after
   each opportunity, the next interval is re-drawn from the persona's declared
   purchase-frequency interval set instead of remaining fixed forever;
2. loyalty uses a bounded EWMA update, rho*L + (1-rho)*choice, avoiding the
   legacy coefficient sum above one.

All magnitudes remain engineering assumptions, not population estimates.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from mechanism_v2 import clip, deterministic_uniform
from purchase_mechanism_v31 import (
    CHOICE_ACTION_LABEL,
    DemandChoice,
    DemandParameters,
    MicroBuyerProfile,
    current_pbc,
    focal_choice_probability,
)

SCHEMA = "purchase-demand-3.3"
RENEWAL_ACTION_LABEL = "category_opportunity_interval_v33"


@dataclass(frozen=True)
class RenewalDemandState:
    loyalty: float
    next_opportunity_tick: int
    purchase_index: int = 0


def initial_renewal_state(profile: MicroBuyerProfile) -> RenewalDemandState:
    """Preserve v3.2's initial phase, then switch to renewal intervals."""

    return RenewalDemandState(
        loyalty=clip(profile.initial_loyalty, -1.0, 1.0),
        next_opportunity_tick=1 + int(profile.opportunity_phase),
        purchase_index=0,
    )


def _stable_index(seed: int, entity_id: str, label: str) -> int:
    payload = f"{int(seed)}|{str(entity_id)}|{str(label)}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def next_renewal_interval(
    *,
    seed: int,
    buyer_id: str,
    purchase_index: int,
    allowed_intervals: Sequence[int],
) -> int:
    """Draw a deterministic/reproducible interval from a declared interval set."""

    allowed = tuple(int(value) for value in allowed_intervals)
    if not allowed or any(value <= 0 for value in allowed):
        raise ValueError("allowed_intervals must contain positive integers")
    label = f"{RENEWAL_ACTION_LABEL}|purchase_index={int(purchase_index)}"
    return allowed[_stable_index(seed, buyer_id, label) % len(allowed)]


def update_loyalty_v33(
    *,
    previous_loyalty: float,
    focal_brand_chosen: bool,
    retention: float,
) -> float:
    """Bounded EWMA path dependence for repeated brand choice."""

    rho = float(retention)
    if not 0.0 <= rho <= 1.0:
        raise ValueError("retention must be in [0, 1]")
    signed_choice = 1.0 if bool(focal_brand_chosen) else -1.0
    return clip(
        rho * clip(previous_loyalty, -1.0, 1.0)
        + (1.0 - rho) * signed_choice,
        -1.0,
        1.0,
    )


def purchase_step_v33(
    *,
    seed: int,
    tick: int,
    attitude_att: float,
    subjective_norm_sn: float,
    trust: float,
    profile: MicroBuyerProfile,
    state: RenewalDemandState,
    facilitation_present: bool,
    parameters: DemandParameters,
    allowed_intervals: Sequence[int],
) -> tuple[DemandChoice, RenewalDemandState]:
    """Advance one micro-buyer by one Tick under renewal purchase opportunities."""

    pbc = current_pbc(
        profile=profile,
        tick=tick,
        facilitation_present=facilitation_present,
        parameters=parameters,
    )

    # focal_choice_probability only reads the loyalty field from state; the
    # renewal state therefore remains interface-compatible with the v3.1 utility.
    intention, probability = focal_choice_probability(
        attitude_att=attitude_att,
        subjective_norm_sn=subjective_norm_sn,
        pbc=pbc,
        trust=trust,
        profile=profile,
        state=state,
        parameters=parameters,
    )

    loyalty_before = clip(state.loyalty, -1.0, 1.0)
    if int(tick) != int(state.next_opportunity_tick):
        result = DemandChoice(
            opportunity=False,
            pbc=pbc,
            purchase_intention=intention,
            choice_probability=None,
            choice_draw=None,
            focal_brand_chosen=False,
            loyalty_before=loyalty_before,
            loyalty_after=loyalty_before,
        )
        return result, state

    draw = deterministic_uniform(seed, profile.buyer_id, tick, CHOICE_ACTION_LABEL)
    chosen = draw < probability
    loyalty_after = update_loyalty_v33(
        previous_loyalty=loyalty_before,
        focal_brand_chosen=chosen,
        retention=parameters.loyalty_retention,
    )

    next_index = int(state.purchase_index) + 1
    interval = next_renewal_interval(
        seed=seed,
        buyer_id=profile.buyer_id,
        purchase_index=next_index,
        allowed_intervals=allowed_intervals,
    )
    next_state = RenewalDemandState(
        loyalty=loyalty_after,
        next_opportunity_tick=int(tick) + int(interval),
        purchase_index=next_index,
    )
    result = DemandChoice(
        opportunity=True,
        pbc=pbc,
        purchase_intention=intention,
        choice_probability=probability,
        choice_draw=draw,
        focal_brand_chosen=chosen,
        loyalty_before=loyalty_before,
        loyalty_after=loyalty_after,
    )
    return result, next_state
