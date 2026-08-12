"""v3.3 FMCG demand adapter with renewal category-purchase opportunities."""
from __future__ import annotations

from fmcg_scenario_v32 import ENGINEERING_PERSONAS
from purchase_mechanism_v31 import DemandParameters
from purchase_mechanism_v32 import (
    FREQUENCY_INTERVALS,
    build_scenario_micro_cohort,
)
from purchase_mechanism_v33 import (
    initial_renewal_state,
    purchase_step_v33,
)


def simulate_demand(
    cognitive_rows: list[dict],
    *,
    support_present: bool,
    demand_seed: int,
    micro_buyers: int = 25,
) -> tuple[list[dict], list[dict]]:
    """Run v3.3 renewal repeat-choice demand on one cognitive condition."""

    if not cognitive_rows:
        raise ValueError("cognitive_rows is empty")

    exp_id = str(cognitive_rows[0]["exp_id"])
    cognitive = {
        (int(row["tick"]), str(row["agent_id"])): row
        for row in cognitive_rows
    }

    params = DemandParameters(micro_buyers_per_archetype=micro_buyers)
    cohorts = {
        persona.agent_id: build_scenario_micro_cohort(
            seed=demand_seed,
            persona=persona,
            parameters=params,
        )
        for persona in ENGINEERING_PERSONAS
    }
    states = {
        profile.buyer_id: initial_renewal_state(profile)
        for cohort in cohorts.values()
        for profile in cohort
    }

    rows: list[dict] = []
    curves: list[dict] = []
    cumulative_n = 0
    cumulative_expected = 0.0
    cumulative_chosen = 0

    for tick in range(1, 31):
        tick_n = 0
        tick_expected = 0.0
        tick_chosen = 0

        for persona in ENGINEERING_PERSONAS:
            psych = cognitive[(tick, persona.agent_id)]
            allowed_intervals = FREQUENCY_INTERVALS[
                persona.category_purchase_frequency
            ]
            for profile in cohorts[persona.agent_id]:
                state_before = states[profile.buyer_id]
                choice, next_state = purchase_step_v33(
                    seed=demand_seed,
                    tick=tick,
                    attitude_att=float(psych["attitude_att"]),
                    subjective_norm_sn=float(psych["subjective_norm_after"]),
                    trust=float(psych["trust_final"]),
                    profile=profile,
                    state=state_before,
                    facilitation_present=support_present,
                    parameters=params,
                    allowed_intervals=allowed_intervals,
                )
                states[profile.buyer_id] = next_state
                if not choice.opportunity:
                    continue

                tick_n += 1
                tick_expected += float(choice.choice_probability)
                tick_chosen += int(choice.focal_brand_chosen)
                rows.append(
                    {
                        "exp_id": exp_id,
                        "conversion_support": (
                            "present" if support_present else "absent"
                        ),
                        "tick": tick,
                        "agent_id": persona.agent_id,
                        "buyer_id": profile.buyer_id,
                        "current_pbc": choice.pbc,
                        "purchase_intention": choice.purchase_intention,
                        "choice_probability": choice.choice_probability,
                        "choice_draw": choice.choice_draw,
                        "focal_brand_chosen": choice.focal_brand_chosen,
                        "loyalty_before": choice.loyalty_before,
                        "loyalty_after": choice.loyalty_after,
                        "purchase_index_before": state_before.purchase_index,
                        "purchase_index_after": next_state.purchase_index,
                        "next_opportunity_tick": next_state.next_opportunity_tick,
                        "renewal_process": True,
                    }
                )

        cumulative_n += tick_n
        cumulative_expected += tick_expected
        cumulative_chosen += tick_chosen
        curves.append(
            {
                "exp_id": exp_id,
                "conversion_support": "present" if support_present else "absent",
                "tick": tick,
                "opportunities": tick_n,
                "expected_choice_share": (
                    tick_expected / tick_n if tick_n else ""
                ),
                "realized_choice_share": (
                    tick_chosen / tick_n if tick_n else ""
                ),
                "cumulative_opportunities": cumulative_n,
                "cumulative_expected_choice_share": (
                    cumulative_expected / cumulative_n if cumulative_n else ""
                ),
                "cumulative_realized_choice_share": (
                    cumulative_chosen / cumulative_n if cumulative_n else ""
                ),
                "renewal_process": True,
            }
        )

    return rows, curves
