"""FMCG repeat-choice demand layer for TASK_005 mechanism v3.1.

The module is parallel to the frozen production path.  It contains no
communication-treatment labels and makes no empirical-calibration claim.  Its
purpose is to test a prospectively frozen demand structure using existing
psychological trajectories without making real LLM calls.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Sequence

from mechanism_v2 import clip, clip01, deterministic_uniform, sigmoid
from purchase_mechanism_v3 import tpb_purchase_intention


SCHEMA = "purchase-demand-3.1"
CHOICE_ACTION_LABEL = "focal_brand_choice_v31"
DEFAULT_MICRO_BUYERS_PER_ARCHETYPE = 25
DEFAULT_OPPORTUNITY_INTERVALS = (5, 7, 10, 14)


def logit(probability: float) -> float:
    """Return a numerically safe logit without changing interior values."""

    p = clip(float(probability), 1e-12, 1.0 - 1e-12)
    return math.log(p / (1.0 - p))


def _stable_index(seed: int, entity_id: str, label: str) -> int:
    payload = f"{int(seed)}|{str(entity_id)}|{str(label)}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def balanced_normal_quantiles(count: int, latent_sd: float) -> tuple[float, ...]:
    """Return midpoint normal quantiles with an exactly zero arithmetic mean."""

    n = int(count)
    sd = float(latent_sd)
    if n <= 0:
        raise ValueError("count must be positive")
    if sd < 0.0:
        raise ValueError("latent_sd must be non-negative")
    if sd == 0.0:
        return (0.0,) * n
    normal = NormalDist()
    raw = [normal.inv_cdf((rank + 0.5) / n) * sd for rank in range(n)]
    mean = math.fsum(raw) / n
    return tuple(value - mean for value in raw)


def _permuted_quantile(
    *,
    seed: int,
    archetype_id: str,
    micro_index: int,
    micro_count: int,
    latent_sd: float,
    label: str,
) -> float:
    if not 0 <= int(micro_index) < int(micro_count):
        raise ValueError("micro_index must be in [0, micro_count)")
    offset = _stable_index(seed, archetype_id, label) % int(micro_count)
    rank = (int(micro_index) + offset) % int(micro_count)
    return balanced_normal_quantiles(int(micro_count), latent_sd)[rank]


@dataclass(frozen=True)
class MicroBuyerProfile:
    buyer_id: str
    archetype_id: str
    micro_index: int
    opportunity_interval: int
    opportunity_phase: int
    preference_offset: float
    baseline_pbc: float
    initial_loyalty: float


@dataclass(frozen=True)
class DemandParameters:
    """Illustrative reference parameters frozen in contract 3.1.

    These defaults are a structural stress-test setting, not estimates.
    """

    micro_buyers_per_archetype: int = DEFAULT_MICRO_BUYERS_PER_ARCHETYPE
    opportunity_intervals: tuple[int, ...] = DEFAULT_OPPORTUNITY_INTERVALS
    preference_sd: float = 0.60
    baseline_pbc_sd: float = 0.40
    initial_loyalty_sd: float = 0.60
    pbc_behavior_weight: float = 1.00
    loyalty_weight: float = 0.50
    loyalty_retention: float = 0.85
    loyalty_learning_rate: float = 0.20
    facilitation_signal: float = 0.35
    facilitation_start_tick: int = 6
    facilitation_end_tick: int = 19

    def __post_init__(self) -> None:
        if int(self.micro_buyers_per_archetype) <= 0:
            raise ValueError("micro_buyers_per_archetype must be positive")
        if not self.opportunity_intervals:
            raise ValueError("opportunity_intervals must not be empty")
        if any(int(value) <= 0 for value in self.opportunity_intervals):
            raise ValueError("all opportunity intervals must be positive")
        for name in (
            "preference_sd",
            "baseline_pbc_sd",
            "initial_loyalty_sd",
            "pbc_behavior_weight",
            "loyalty_weight",
            "loyalty_learning_rate",
        ):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must be non-negative")
        if not 0.0 <= float(self.loyalty_retention) <= 1.0:
            raise ValueError("loyalty_retention must be in [0, 1]")
        if not 0.0 <= float(self.facilitation_signal) <= 1.0:
            raise ValueError("facilitation_signal must be in [0, 1]")
        if int(self.facilitation_end_tick) < int(self.facilitation_start_tick):
            raise ValueError("facilitation_end_tick must not precede start_tick")


@dataclass(frozen=True)
class DemandState:
    loyalty: float


@dataclass(frozen=True)
class DemandChoice:
    opportunity: bool
    pbc: float
    purchase_intention: float
    choice_probability: float | None
    choice_draw: float | None
    focal_brand_chosen: bool
    loyalty_before: float
    loyalty_after: float


def build_micro_profile(
    *,
    seed: int,
    archetype_id: str,
    micro_index: int,
    archetype_pbc: float,
    parameters: DemandParameters,
) -> MicroBuyerProfile:
    """Build one treatment-invariant micro-buyer from balanced latent grids."""

    count = int(parameters.micro_buyers_per_archetype)
    index = int(micro_index)
    buyer_id = f"{str(archetype_id)}::M{index:03d}"
    intervals = tuple(int(value) for value in parameters.opportunity_intervals)
    interval = intervals[_stable_index(seed, buyer_id, "opportunity-interval") % len(intervals)]
    phase = _stable_index(seed, buyer_id, "opportunity-phase") % interval
    preference = _permuted_quantile(
        seed=seed,
        archetype_id=archetype_id,
        micro_index=index,
        micro_count=count,
        latent_sd=parameters.preference_sd,
        label="preference-rank",
    )
    pbc_offset = _permuted_quantile(
        seed=seed,
        archetype_id=archetype_id,
        micro_index=index,
        micro_count=count,
        latent_sd=parameters.baseline_pbc_sd,
        label="pbc-rank",
    )
    loyalty_offset = _permuted_quantile(
        seed=seed,
        archetype_id=archetype_id,
        micro_index=index,
        micro_count=count,
        latent_sd=parameters.initial_loyalty_sd,
        label="loyalty-rank",
    )
    baseline_pbc = sigmoid(logit(clip01(archetype_pbc)) + pbc_offset)
    initial_loyalty = 2.0 * sigmoid(loyalty_offset) - 1.0
    return MicroBuyerProfile(
        buyer_id=buyer_id,
        archetype_id=str(archetype_id),
        micro_index=index,
        opportunity_interval=interval,
        opportunity_phase=phase,
        preference_offset=preference,
        baseline_pbc=baseline_pbc,
        initial_loyalty=initial_loyalty,
    )

def build_micro_cohort(
    *,
    seed: int,
    archetype_id: str,
    archetype_pbc: float,
    parameters: DemandParameters,
) -> tuple[MicroBuyerProfile, ...]:
    return tuple(
        build_micro_profile(
            seed=seed,
            archetype_id=archetype_id,
            micro_index=index,
            archetype_pbc=archetype_pbc,
            parameters=parameters,
        )
        for index in range(parameters.micro_buyers_per_archetype)
    )


def is_purchase_opportunity(profile: MicroBuyerProfile, tick: int) -> bool:
    current_tick = int(tick)
    first_tick = 1 + int(profile.opportunity_phase)
    return current_tick >= first_tick and (
        (current_tick - first_tick) % int(profile.opportunity_interval) == 0
    )


def current_pbc(
    *,
    profile: MicroBuyerProfile,
    tick: int,
    facilitation_present: bool,
    parameters: DemandParameters,
) -> float:
    baseline = clip01(profile.baseline_pbc)
    active = (
        bool(facilitation_present)
        and int(parameters.facilitation_start_tick)
        <= int(tick)
        <= int(parameters.facilitation_end_tick)
    )
    if not active:
        return baseline
    signal = clip01(parameters.facilitation_signal)
    return clip01(baseline + signal * (1.0 - baseline))


def focal_choice_probability(
    *,
    attitude_att: float,
    subjective_norm_sn: float,
    pbc: float,
    trust: float,
    profile: MicroBuyerProfile,
    state: DemandState,
    parameters: DemandParameters,
) -> tuple[float, float]:
    """Return extended-TPB intention and conditional focal-brand probability."""

    intention = tpb_purchase_intention(
        attitude_att=attitude_att,
        subjective_norm_sn=subjective_norm_sn,
        pbc=pbc,
        trust=trust,
    )
    utility = (
        logit(intention)
        + float(profile.preference_offset)
        + float(parameters.pbc_behavior_weight)
        * (clip01(pbc) - clip01(profile.baseline_pbc))
        + float(parameters.loyalty_weight) * clip(state.loyalty, -1.0, 1.0)
    )
    return intention, sigmoid(utility)


def update_loyalty(
    *,
    previous_loyalty: float,
    focal_brand_chosen: bool,
    parameters: DemandParameters,
) -> float:
    signed_choice = 1.0 if bool(focal_brand_chosen) else -1.0
    return clip(
        float(parameters.loyalty_retention) * clip(previous_loyalty, -1.0, 1.0)
        + float(parameters.loyalty_learning_rate) * signed_choice,
        -1.0,
        1.0,
    )


def purchase_step(
    *,
    seed: int,
    tick: int,
    attitude_att: float,
    subjective_norm_sn: float,
    trust: float,
    profile: MicroBuyerProfile,
    state: DemandState,
    facilitation_present: bool,
    parameters: DemandParameters,
) -> tuple[DemandChoice, DemandState]:
    """Advance one micro-buyer by one Tick without an absorbing purchase state."""

    pbc = current_pbc(
        profile=profile,
        tick=tick,
        facilitation_present=facilitation_present,
        parameters=parameters,
    )
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
    if not is_purchase_opportunity(profile, tick):
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
    loyalty_after = update_loyalty(
        previous_loyalty=loyalty_before,
        focal_brand_chosen=chosen,
        parameters=parameters,
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
    return result, DemandState(loyalty=loyalty_after)


def no_effect_parameters(
    *,
    opportunity_intervals: Sequence[int] = DEFAULT_OPPORTUNITY_INTERVALS,
    micro_buyers_per_archetype: int = DEFAULT_MICRO_BUYERS_PER_ARCHETYPE,
) -> DemandParameters:
    """Return an intention-only bridge used to prove the absence of hidden lift."""

    return DemandParameters(
        micro_buyers_per_archetype=int(micro_buyers_per_archetype),
        opportunity_intervals=tuple(int(value) for value in opportunity_intervals),
        preference_sd=0.0,
        baseline_pbc_sd=0.0,
        initial_loyalty_sd=0.0,
        pbc_behavior_weight=0.0,
        loyalty_weight=0.0,
        loyalty_retention=0.85,
        loyalty_learning_rate=0.0,
        facilitation_signal=0.0,
    )
