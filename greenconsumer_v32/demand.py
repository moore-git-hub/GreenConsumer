from __future__ import annotations

from fmcg_scenario_v32 import ENGINEERING_PERSONAS
from purchase_mechanism_v31 import DemandParameters, DemandState, purchase_step
from purchase_mechanism_v32 import build_scenario_micro_cohort


def simulate_demand(
    cognitive_rows: list[dict],
    *,
    support_present: bool,
    demand_seed: int,
    micro_buyers: int = 25,
) -> tuple[list[dict], list[dict]]:
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
        profile.buyer_id: DemandState(loyalty=profile.initial_loyalty)
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
            for profile in cohorts[persona.agent_id]:
                choice, next_state = purchase_step(
                    seed=demand_seed,
                    tick=tick,
                    attitude_att=float(psych["attitude_att"]),
                    subjective_norm_sn=float(psych["subjective_norm_after"]),
                    trust=float(psych["trust_final"]),
                    profile=profile,
                    state=states[profile.buyer_id],
                    facilitation_present=support_present,
                    parameters=params,
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
            }
        )
    return rows, curves
