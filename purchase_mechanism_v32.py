"""Persona-aligned adapter for the TASK_005 FMCG-v3.2 demand layer.

The ordinal mappings below are transparent, prospectively frozen engineering
assumptions.  They are not population estimates.  They connect the fields in
the v3.2 persona contract to the already audited v3.1 repeat-choice mechanism.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

from fmcg_scenario_v32 import EngineeringPersona
from mechanism_v2 import clip, sigmoid
from purchase_mechanism_v31 import (
    DemandParameters,
    MicroBuyerProfile,
    balanced_normal_quantiles,
    logit,
)


SCHEMA = "purchase-demand-scenario-adapter-3.2"

FREQUENCY_INTERVALS = {
    "5-7 days": (5, 6, 7),
    "7-10 days": (7, 8, 9, 10),
    "10-14 days": (10, 11, 12, 13, 14),
    "14-28 days": tuple(range(14, 29)),
}
RELATIONSHIP_PREFERENCE_CENTRE = {
    "loyal": 0.65,
    "repertoire": 0.0,
    "non-user": -0.65,
}
RELATIONSHIP_LOYALTY_LATENT_CENTRE = {
    "loyal": 1.10,
    "repertoire": 0.0,
    "non-user": -1.10,
}
PBC_PRICE_LOGIT_EFFECT = {"low": 0.25, "medium": 0.0, "high": -0.25}
PBC_AVAILABILITY_LOGIT_EFFECT = {"low": 0.25, "medium": 0.0, "high": -0.25}


@dataclass(frozen=True)
class ScenarioMappingAssumptions:
    """Frozen ordinal coding; magnitudes require sensitivity analysis."""

    loyal_preference_centre: float = 0.65
    non_user_preference_centre: float = -0.65
    loyal_loyalty_latent_centre: float = 1.10
    non_user_loyalty_latent_centre: float = -1.10
    low_friction_logit_effect: float = 0.25
    high_friction_logit_effect: float = -0.25


ASSUMPTIONS = ScenarioMappingAssumptions()


def _stable_index(seed: int, entity_id: str, label: str) -> int:
    payload = f"{int(seed)}|{str(entity_id)}|{str(label)}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _permuted_quantile(
    *,
    seed: int,
    archetype_id: str,
    micro_index: int,
    micro_count: int,
    latent_sd: float,
    label: str,
) -> float:
    quantiles = balanced_normal_quantiles(micro_count, latent_sd)
    offset = _stable_index(seed, archetype_id, label) % micro_count
    return quantiles[(int(micro_index) + offset) % micro_count]


def build_scenario_micro_profile(
    *,
    seed: int,
    persona: EngineeringPersona,
    micro_index: int,
    parameters: DemandParameters,
) -> MicroBuyerProfile:
    """Construct one treatment-invariant buyer from declared persona fields."""

    count = int(parameters.micro_buyers_per_archetype)
    index = int(micro_index)
    if not 0 <= index < count:
        raise ValueError("micro_index must be in [0, micro_buyers_per_archetype)")
    if persona.category_purchase_frequency not in FREQUENCY_INTERVALS:
        raise ValueError("unknown category_purchase_frequency")
    if persona.prior_brand_relationship not in RELATIONSHIP_PREFERENCE_CENTRE:
        raise ValueError("unknown prior_brand_relationship")
    if persona.price_sensitivity not in PBC_PRICE_LOGIT_EFFECT:
        raise ValueError("unknown price_sensitivity")
    if persona.availability_friction not in PBC_AVAILABILITY_LOGIT_EFFECT:
        raise ValueError("unknown availability_friction")

    buyer_id = f"{persona.agent_id}::M{index:03d}"
    allowed_intervals = FREQUENCY_INTERVALS[persona.category_purchase_frequency]
    interval = allowed_intervals[
        _stable_index(seed, buyer_id, "scenario-opportunity-interval")
        % len(allowed_intervals)
    ]
    phase = _stable_index(seed, buyer_id, "scenario-opportunity-phase") % interval

    preference = RELATIONSHIP_PREFERENCE_CENTRE[
        persona.prior_brand_relationship
    ] + _permuted_quantile(
        seed=seed,
        archetype_id=persona.agent_id,
        micro_index=index,
        micro_count=count,
        latent_sd=parameters.preference_sd,
        label="scenario-preference-rank",
    )
    pbc_latent = (
        PBC_PRICE_LOGIT_EFFECT[persona.price_sensitivity]
        + PBC_AVAILABILITY_LOGIT_EFFECT[persona.availability_friction]
        + _permuted_quantile(
            seed=seed,
            archetype_id=persona.agent_id,
            micro_index=index,
            micro_count=count,
            latent_sd=parameters.baseline_pbc_sd,
            label="scenario-pbc-rank",
        )
    )
    loyalty_latent = RELATIONSHIP_LOYALTY_LATENT_CENTRE[
        persona.prior_brand_relationship
    ] + _permuted_quantile(
        seed=seed,
        archetype_id=persona.agent_id,
        micro_index=index,
        micro_count=count,
        latent_sd=parameters.initial_loyalty_sd,
        label="scenario-loyalty-rank",
    )

    return MicroBuyerProfile(
        buyer_id=buyer_id,
        archetype_id=persona.agent_id,
        micro_index=index,
        opportunity_interval=int(interval),
        opportunity_phase=int(phase),
        preference_offset=float(preference),
        baseline_pbc=sigmoid(logit(0.5) + pbc_latent),
        initial_loyalty=clip(2.0 * sigmoid(loyalty_latent) - 1.0, -1.0, 1.0),
    )


def build_scenario_micro_cohort(
    *,
    seed: int,
    persona: EngineeringPersona,
    parameters: DemandParameters,
) -> tuple[MicroBuyerProfile, ...]:
    return tuple(
        build_scenario_micro_profile(
            seed=seed,
            persona=persona,
            micro_index=index,
            parameters=parameters,
        )
        for index in range(parameters.micro_buyers_per_archetype)
    )


def mapping_audit_payload() -> dict:
    """Expose every ordinal mapping needed to reconstruct the cohort."""

    return {
        "schema_version": SCHEMA,
        "empirically_calibrated": False,
        "scenario_mapping_assumptions": asdict(ASSUMPTIONS),
        "frequency_intervals": {
            key: list(value) for key, value in FREQUENCY_INTERVALS.items()
        },
        "relationship_preference_centre": dict(
            RELATIONSHIP_PREFERENCE_CENTRE
        ),
        "relationship_loyalty_latent_centre": dict(
            RELATIONSHIP_LOYALTY_LATENT_CENTRE
        ),
        "pbc_price_logit_effect": dict(PBC_PRICE_LOGIT_EFFECT),
        "pbc_availability_logit_effect": dict(
            PBC_AVAILABILITY_LOGIT_EFFECT
        ),
    }
