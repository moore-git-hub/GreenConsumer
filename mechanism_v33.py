"""TASK_005 FMCG v3.3 trust dynamics.

This module is deliberately parallel to ``mechanism_v2.py``.  It does not
modify the frozen v3.2 mechanism or the closed F001-F010 formal archive.

Scientific intent
-----------------
The v3.2 trust stock is useful and auditable, but its quiet-period trajectory is
very regular because crisis and repair memories share one retention rate and
Trust is recomputed directly from the memory target every Tick.  v3.3 keeps the
same semantic inputs while introducing three transparent mechanisms:

1. crisis and repair memories may decay at different rates;
2. observed events and quiet periods use partial Trust adjustment rather than
   instantaneous movement to the memory-implied target;
3. repeated repair has diminishing marginal impact, while perceived hypocrisy
   can amplify negative crisis-memory increments.

All numeric defaults below are DEVELOPMENT ENGINEERING ASSUMPTIONS, not
population estimates.  They must be reported as such and sensitivity-tested.
No random noise is added to Trust merely to make trajectories look irregular.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from mechanism_v2 import (
    ATTITUDE_UPDATE_RATE,
    EMPATHY_REPAIR_WEIGHT,
    TRUST_CRISIS_WEIGHT,
    TRUST_REPAIR_WEIGHT,
    clip,
    clip01,
    semantic_to_affective,
    sigmoid,
)

SCHEMA = "trust-dynamics-3.3"


@dataclass(frozen=True)
class TrustDynamicsV33Parameters:
    """Transparent development defaults for the v3.3 trust mechanism.

    The defaults are intentionally conservative and close to v3.2.  They are
    not claimed to be empirically calibrated.  Use ``legacy_v32()`` for a
    compatibility profile that reproduces the v3.2 trust transition equation.
    """

    crisis_retention: float = 0.98
    repair_retention: float = 0.96
    event_adjustment: float = 0.80
    quiet_adjustment: float = 0.18
    repair_saturation: float = 0.30
    hypocrisy_weight: float = 0.25
    empathy_repair_weight: float = EMPATHY_REPAIR_WEIGHT

    def __post_init__(self) -> None:
        for name in (
            "crisis_retention",
            "repair_retention",
            "event_adjustment",
            "quiet_adjustment",
            "empathy_repair_weight",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        for name in ("repair_saturation", "hypocrisy_weight"):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must be non-negative")

    @classmethod
    def legacy_v32(cls) -> "TrustDynamicsV33Parameters":
        """Return settings that recover the v3.2 trust-memory transition."""

        return cls(
            crisis_retention=0.97,
            repair_retention=0.97,
            event_adjustment=1.0,
            quiet_adjustment=1.0,
            repair_saturation=0.0,
            hypocrisy_weight=0.0,
            empathy_repair_weight=EMPATHY_REPAIR_WEIGHT,
        )


DEFAULT_TRUST_PARAMETERS = TrustDynamicsV33Parameters()


def parameters_audit_payload(
    parameters: TrustDynamicsV33Parameters = DEFAULT_TRUST_PARAMETERS,
) -> dict:
    """Expose assumptions so every run can be reconstructed and audited."""

    return {
        "schema_version": SCHEMA,
        "empirically_calibrated": False,
        "parameters": asdict(parameters),
        "notes": (
            "development engineering assumptions; require sensitivity analysis; "
            "no stochastic Trust noise"
        ),
    }


def update_psychological_state_v33(
    *,
    baseline_trust,
    previous_trust,
    attitude_att,
    subjective_norm_sn,
    pbc,
    crisis_memory,
    repair_memory,
    valence,
    arousal,
    credibility,
    evidence_strength,
    topic_relevance,
    had_observation,
    social_observation_count,
    perceived_empathy=0.0,
    hypocrisy_perceived=False,
    enterprise_clarification_observed=False,
    parameters: TrustDynamicsV33Parameters = DEFAULT_TRUST_PARAMETERS,
):
    """Advance one cognitive Agent by one Tick under v3.3 trust dynamics.

    The function preserves the v3.2 semantic-to-Attitude mapping and the legacy
    SN branch for compatibility.  Scenario-v3.3 disables that legacy SN branch
    in its Plan plugin and updates SN separately from observed peer approval,
    exactly as scenario-v3.2 already does.
    """

    base = clip(baseline_trust, 0, 10)
    prev = clip(previous_trust, 0, 10)
    att = clip01(attitude_att)
    sn = clip01(subjective_norm_sn)
    pbc = clip01(pbc)

    # Memory decay is explicit and asymmetric in v3.3.
    cb = max(0.0, float(crisis_memory)) * float(parameters.crisis_retention)
    rb = max(0.0, float(repair_memory)) * float(parameters.repair_retention)
    target_before_signal = clip(
        base + TRUST_REPAIR_WEIGHT * rb - TRUST_CRISIS_WEIGHT * cb,
        0,
        10,
    )

    v = clip(valence, -1, 1)
    a = clip01(arousal)
    c = clip01(credibility)
    e = clip01(evidence_strength)
    r = clip01(topic_relevance)
    pe = clip01(perceived_empathy)

    affect = 0.0
    crisis_increment = 0.0
    repair_increment = 0.0
    relational_repair_signal = 0.0
    relational_repair_increment = 0.0
    repair_saturation_multiplier = 1.0

    if had_observation:
        affect = semantic_to_affective(v, a, c)
        information_weight = (0.5 + 0.5 * c) * (0.5 + 0.5 * r)

        if affect < 0:
            hypocrisy_multiplier = (
                1.0 + float(parameters.hypocrisy_weight)
                if bool(hypocrisy_perceived)
                else 1.0
            )
            crisis_increment = (-affect) * information_weight * hypocrisy_multiplier
            cb += crisis_increment

        elif affect > 0:
            # Diminishing returns operate on accumulated repair memory.  With
            # repair_saturation=0 the legacy linear increment is recovered.
            repair_saturation_multiplier = 1.0 / (
                1.0 + float(parameters.repair_saturation) * rb
            )
            positive_signal = (
                affect * information_weight * (0.5 + 0.5 * e)
            )
            repair_increment = positive_signal * repair_saturation_multiplier
            rb += repair_increment

        if bool(enterprise_clarification_observed):
            relational_repair_signal = pe * information_weight
            relational_raw = (
                float(parameters.empathy_repair_weight)
                * relational_repair_signal
            )
            # The same diminishing-return principle is applied to relational
            # repair so repeated clarification does not accumulate linearly.
            relational_repair_increment = (
                relational_raw * repair_saturation_multiplier
            )
            rb += relational_repair_increment

        v01 = (v + 1.0) / 2.0
        signal = clip01(0.45 * v01 + 0.25 * c + 0.20 * e + 0.10 * r)
        att = clip01(
            (1.0 - ATTITUDE_UPDATE_RATE) * att
            + ATTITUDE_UPDATE_RATE * signal
        )
        if int(social_observation_count) > 0:
            # Kept only for compatibility with the v2 function signature.
            # Scenario-v3.3 passes zero and updates SN from explicit peer
            # approval in ConsumerPlanV33Plugin.
            from mechanism_v2 import SUBJECTIVE_NORM_UPDATE_RATE

            sn = clip01(
                (1.0 - SUBJECTIVE_NORM_UPDATE_RATE) * sn
                + SUBJECTIVE_NORM_UPDATE_RATE * v01
            )

    target_after_signal = clip(
        base + TRUST_REPAIR_WEIGHT * rb - TRUST_CRISIS_WEIGHT * cb,
        0,
        10,
    )

    adjustment = (
        float(parameters.event_adjustment)
        if had_observation
        else float(parameters.quiet_adjustment)
    )
    trust = clip(prev + adjustment * (target_after_signal - prev), 0, 10)

    z = (
        -0.50
        + 1.40 * (att - 0.5)
        + 0.80 * (sn - 0.5)
        + 0.60 * (pbc - 0.5)
        + 1.20 * (trust / 10.0 - 0.5)
    )
    purchase_intention = sigmoid(z)
    posting_intention = (
        sigmoid(-1.0 + 1.20 * a + 0.80 * abs(v)) if had_observation else 0.0
    )

    return {
        "trust_before_signal": target_before_signal,
        "trust_target_after_signal": target_after_signal,
        "trust_adjustment_rate": adjustment,
        "trust_final": trust,
        "attitude_att": att,
        "subjective_norm_sn": sn,
        "pbc": pbc,
        "emotion_valence": v if had_observation else 0.0,
        "emotion_arousal": a if had_observation else 0.0,
        "crisis_memory_before": max(0.0, float(crisis_memory))
        * float(parameters.crisis_retention),
        "repair_memory_before": max(0.0, float(repair_memory))
        * float(parameters.repair_retention),
        "crisis_memory": cb,
        "repair_memory": rb,
        "crisis_increment": crisis_increment,
        "repair_increment": repair_increment,
        "repair_saturation_multiplier": repair_saturation_multiplier,
        "affective_change": affect,
        "purchase_intention": purchase_intention,
        "posting_intention": posting_intention,
        "trust_delta": trust - prev,
        "relational_repair_signal": relational_repair_signal,
        "relational_repair_increment": relational_repair_increment,
        "empathy_repair_weight": float(parameters.empathy_repair_weight),
        "hypocrisy_perceived": bool(hypocrisy_perceived),
        "trust_dynamics_schema_version": SCHEMA,
    }
