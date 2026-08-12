"""Scenario-v3.3 cognitive transition and posting plan.

Parallel to ConsumerPlanV32Plugin.  Purchase remains absent from AgentKernel and
is evaluated downstream by the v3.3 FMCG renewal-demand layer.
"""
from __future__ import annotations

from agentkernel_standalone.mas.agent.base.plugin_base import PlanPlugin

from mechanism_v2 import behavior_probabilities, deterministic_uniform
from mechanism_v31_cognition import update_subjective_norm
from mechanism_v32_semantics import SCHEMA as SEMANTIC_SCHEMA
from mechanism_v33 import (
    DEFAULT_TRUST_PARAMETERS,
    SCHEMA as TRUST_V33_SCHEMA,
    update_psychological_state_v33,
)
from purchase_mechanism_v3 import tpb_purchase_intention

SCHEMA = "consumer-plan-3.3"


class ConsumerPlanV33Plugin(PlanPlugin):
    async def init(self):
        pass

    def _get_agent(self):
        if hasattr(self, "agent") and self.agent:
            return self.agent
        if self.component and hasattr(self.component, "agent"):
            return self.component.agent
        if hasattr(self, "_component") and self._component:
            return self._component.agent
        return None

    def _get_plugin(self, name):
        agent = self._get_agent()
        if not agent:
            return None
        component = agent.get_component(name)
        return (
            getattr(component, "_plugin", getattr(component, "plugin", None))
            if component
            else None
        )

    async def execute(self, current_tick: int) -> None:
        agent = self._get_agent()
        if not agent:
            return
        state_plugin = self._get_plugin("state")
        profile_plugin = self._get_plugin("profile")
        if not state_plugin or not profile_plugin:
            return

        state_data = getattr(
            state_plugin, "state_data", getattr(state_plugin, "_state_data", {})
        )
        observations = state_data.get("last_observations") or []
        had_observation = bool(observations)
        has_clarification = any(
            isinstance(row, dict)
            and (
                row.get("source") == "Enterprise_Clarification"
                or row.get("type") == "clarification"
            )
            for row in observations
        )
        enterprise_clarification_observed = any(
            isinstance(row, dict)
            and row.get("source") == "Enterprise_Clarification"
            for row in observations
        )
        clarification_type = ""
        for row in observations:
            if isinstance(row, dict) and (
                row.get("source") == "Enterprise_Clarification"
                or row.get("type") == "clarification"
            ):
                clarification_type = str(row.get("content_factor", "unknown"))
                break

        quiet_ticks = int(state_data.get("quiet_ticks", 0))
        quiet_ticks = quiet_ticks + 1 if not had_observation else 0
        previous_trust = float(state_data.get("trust_score", 5.0))
        baseline_trust = float(state_data.get("baseline_trust", previous_trust))
        previous_sn = float(state_data.get("subjective_norm_SN", 0.5))
        pbc = float(state_data.get("perceived_behavioral_control_PBC", 0.5))

        transition = update_psychological_state_v33(
            baseline_trust=baseline_trust,
            previous_trust=previous_trust,
            attitude_att=float(
                state_data.get(
                    "attitude_Att", max(0.0, min(1.0, baseline_trust / 10.0))
                )
            ),
            subjective_norm_sn=previous_sn,
            pbc=pbc,
            crisis_memory=float(state_data.get("crisis_memory", 0.0)),
            repair_memory=float(state_data.get("repair_memory", 0.0)),
            valence=float(state_data.get("semantic_valence", 0.0)),
            arousal=float(state_data.get("semantic_arousal", 0.0)),
            credibility=float(state_data.get("semantic_credibility", 0.5)),
            evidence_strength=float(
                state_data.get("semantic_evidence_strength", 0.0)
            ),
            topic_relevance=float(
                state_data.get("semantic_topic_relevance", 0.0)
            ),
            had_observation=had_observation,
            social_observation_count=0,
            perceived_empathy=float(
                state_data.get("semantic_perceived_empathy", 0.0)
            ),
            hypocrisy_perceived=bool(
                state_data.get("semantic_hypocrisy_perceived", False)
            ),
            enterprise_clarification_observed=enterprise_clarification_observed,
            parameters=DEFAULT_TRUST_PARAMETERS,
        )

        social_count = int(
            state_data.get("semantic_social_observation_count", 0)
        )
        peer_approval = state_data.get("semantic_perceived_peer_approval")
        updated_sn = update_subjective_norm(
            previous_sn=previous_sn,
            social_observation_count=social_count,
            perceived_peer_approval=peer_approval,
        )
        purchase_intention = tpb_purchase_intention(
            attitude_att=transition["attitude_att"],
            subjective_norm_sn=updated_sn,
            pbc=pbc,
            trust=transition["trust_final"],
        )

        last_post_tick = state_data.get("last_post_tick")
        ticks_since_last_post = (
            None
            if last_post_tick in (None, "")
            else current_tick - int(last_post_tick)
        )
        _, posting_probability = behavior_probabilities(
            purchase_intention=purchase_intention,
            posting_intention=transition["posting_intention"],
            had_observation=had_observation,
            already_purchased=True,
            ticks_since_last_post=ticks_since_last_post,
        )
        behavior_seed = int(state_data.get("behavior_seed_base", 0))
        post_draw = deterministic_uniform(
            behavior_seed, agent.agent_id, current_tick, "post"
        )
        posting = post_draw < posting_probability
        thought = state_data.get("latest_thought") or {}
        reasoning = str(thought.get("reasoning", "")).strip()
        post_content = (
            reasoning
            if posting and reasoning
            else ("I am still evaluating this brand." if posting else "")
        )
        if posting:
            await state_plugin.set_state("last_post_tick", current_tick)

        final_trust = float(transition["trust_final"])
        shock_anchor = float(state_data.get("shock_anchor", previous_trust))
        shock_anchor_after = final_trust if had_observation else shock_anchor

        state_updates = {
            "quiet_ticks": quiet_ticks,
            "trust_score": final_trust,
            "shock_anchor": shock_anchor_after,
            "attitude_Att": transition["attitude_att"],
            "subjective_norm_SN": updated_sn,
            "perceived_behavioral_control_PBC": pbc,
            "emotion_valence": transition["emotion_valence"],
            "emotion_arousal": transition["emotion_arousal"],
            "crisis_memory": transition["crisis_memory"],
            "repair_memory": transition["repair_memory"],
            "purchase_intention": purchase_intention,
            "posting_intention": transition["posting_intention"],
        }
        for key, value in state_updates.items():
            await state_plugin.set_state(key, value)

        gap = baseline_trust - shock_anchor
        lift = final_trust - shock_anchor if has_clarification else ""
        ratio = (
            (lift / gap if abs(gap) > 1e-12 else 0.0)
            if has_clarification
            else ""
        )

        plan = {
            "mechanism_schema_version": TRUST_V33_SCHEMA,
            "scenario_plan_schema_version": SCHEMA,
            "semantic_schema_version": SEMANTIC_SCHEMA,
            "current_trust": final_trust,
            "is_buying": False,
            "is_posting": posting,
            "post_content": post_content,
            "reason": (
                f"TPB-v3.3 I={purchase_intention:.3f} "
                f"Trust={final_trust:.3f}; repeat choice evaluated downstream"
            ),
            "trust_after_decay": transition["trust_before_signal"],
            "trust_target_after_signal": transition["trust_target_after_signal"],
            "trust_adjustment_rate": transition["trust_adjustment_rate"],
            "affective_change": transition["affective_change"],
            "shock_anchor": shock_anchor,
            "quiet_ticks": quiet_ticks,
            "previous_trust_raw": previous_trust,
            "baseline_trust_raw": baseline_trust,
            "trust_after_decay_raw": transition["trust_before_signal"],
            "affective_change_raw": transition["affective_change"],
            "trust_score_raw": final_trust,
            "shock_anchor_before_raw": shock_anchor,
            "shock_anchor_after_raw": shock_anchor_after,
            "decay_rate_raw": "asymmetric_v33",
            "sensitivity_multiplier": 1.0,
            "trust_clipped_at_bound": final_trust <= 0 or final_trust >= 10,
            "anchor_update_branch": (
                "mechanism_v33_clarification"
                if has_clarification
                else (
                    "mechanism_v33_observation"
                    if had_observation
                    else "mechanism_v33_quiet"
                )
            ),
            "clr_anchor_lift_ratio": ratio,
            "clr_lift_raw": lift,
            "is_quiet_day": not had_observation,
            "clarification_detected_by_plan": has_clarification,
            "clarification_content_type": clarification_type,
            "plan_fallback_used": False,
            "attitude_att": transition["attitude_att"],
            "subjective_norm_sn": updated_sn,
            "subjective_norm_before": previous_sn,
            "subjective_norm_after": updated_sn,
            "perceived_peer_approval": peer_approval,
            "pbc": pbc,
            "emotion_valence": transition["emotion_valence"],
            "emotion_arousal": transition["emotion_arousal"],
            "crisis_memory_before": transition["crisis_memory_before"],
            "repair_memory_before": transition["repair_memory_before"],
            "crisis_memory": transition["crisis_memory"],
            "repair_memory": transition["repair_memory"],
            "crisis_increment": transition["crisis_increment"],
            "repair_increment": transition["repair_increment"],
            "repair_saturation_multiplier": transition[
                "repair_saturation_multiplier"
            ],
            "enterprise_clarification_observed": enterprise_clarification_observed,
            "relational_repair_signal": transition["relational_repair_signal"],
            "relational_repair_increment": transition[
                "relational_repair_increment"
            ],
            "empathy_repair_weight": transition["empathy_repair_weight"],
            "hypocrisy_perceived": transition["hypocrisy_perceived"],
            "crisis_retention": DEFAULT_TRUST_PARAMETERS.crisis_retention,
            "repair_retention": DEFAULT_TRUST_PARAMETERS.repair_retention,
            "event_adjustment": DEFAULT_TRUST_PARAMETERS.event_adjustment,
            "quiet_adjustment": DEFAULT_TRUST_PARAMETERS.quiet_adjustment,
            "repair_saturation": DEFAULT_TRUST_PARAMETERS.repair_saturation,
            "hypocrisy_weight": DEFAULT_TRUST_PARAMETERS.hypocrisy_weight,
            "purchase_intention": purchase_intention,
            "posting_intention": transition["posting_intention"],
            "buy_probability": "",
            "post_probability": posting_probability,
            "buy_draw": "",
            "post_draw": post_draw,
            "semantic_valence": float(state_data.get("semantic_valence", 0.0)),
            "semantic_arousal": float(state_data.get("semantic_arousal", 0.0)),
            "semantic_credibility": float(
                state_data.get("semantic_credibility", 0.5)
            ),
            "semantic_evidence_strength": float(
                state_data.get("semantic_evidence_strength", 0.0)
            ),
            "semantic_topic_relevance": float(
                state_data.get("semantic_topic_relevance", 0.0)
            ),
            "legacy_purchase_endpoint_retired": True,
        }
        await state_plugin.set_state("plan_result", plan)

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass
