"""Isolated AgentKernel runtime adapter for TASK_005 scenario-v3.3.

v3.3 is intentionally parallel to the frozen v3.2 runtime.  It reuses the
same fictional FMCG scenario, LLM semantic plugin, experiment matrix and social
network topology while patching only:

- ConsumerPlanV33Plugin (gradual/asymmetric Trust dynamics)
- ClarificationInjectorV33 (lagged probabilistic one-hop reach)
- Bernoulli public exposure and probabilistic one-hop amplification selectors

Every patched object is restored after the condition run.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager

from experiment_config import ExperimentConfig
from fmcg_scenario_v32 import (
    CLARIFICATION_TEMPLATES,
    CRISIS_STIMULUS,
    ENGINEERING_PERSONAS,
    SCHEMA as SCENARIO_SCHEMA,
    engineering_profiles,
)
from mechanism_v33 import DEFAULT_TRUST_PARAMETERS, parameters_audit_payload
from clarification_diffusion_v33 import (
    DEFAULT_PAID_DELIVERY_LAG,
    DEFAULT_PAID_EDGE_PROBABILITY,
    ClarificationInjectorV33,
    select_paid_amplification_nodes_v33,
    select_public_exposure_nodes_v33,
)

RUNTIME_SCHEMA = "task005-fmcg-runtime-3.3"
MECHANISM_AUDIT_SCHEMA = "mechanism-records-fmcg-3.3"


def _scenario_profiles(num_agents: int, seed: int) -> list[dict]:
    del seed
    if int(num_agents) != len(ENGINEERING_PERSONAS):
        raise ValueError(
            f"scenario-v3.3 requires exactly {len(ENGINEERING_PERSONAS)} cognitive agents"
        )
    return [copy.deepcopy(row) for row in engineering_profiles()]


@contextmanager
def _isolated_runtime_patch(
    simulation_module,
    clarification_module,
    reflect_plugin_class,
    plan_plugin_class,
    config: ExperimentConfig,
):
    """Patch explicit module objects and restore them on every exit path."""

    original_profile_builder = simulation_module._generate_profiles_inline
    original_agent_record_builder = simulation_module.build_agent_record
    original_record_builder = simulation_module.build_mechanism_record
    original_events = dict(simulation_module.ENTERPRISE_STRATEGY)
    original_templates = dict(clarification_module.CONTENT_TEMPLATES)
    plugin_map = simulation_module.resource_maps["agent_plugins"]
    original_reflect = plugin_map["GreenCognitionPlugin"]
    original_plan = plugin_map["ConsumerPlanPlugin"]

    original_injector = simulation_module.ClarificationInjector
    original_public_selector = simulation_module.select_public_exposure_nodes
    original_amplification_selector = simulation_module.one_hop_amplification_nodes

    def _audit_compatible_plan(plan):
        """Keep legacy audit fields numeric without changing v3.3 science."""
        row = dict(plan or {})
        # simulation_core's legacy audit schema expects numeric decay fields.
        # v3.3 has two retentions, so the repair-memory decay is stored in the
        # legacy scalar slot while the full pair is preserved in v3.3 fields.
        legacy_decay = 1.0 - float(DEFAULT_TRUST_PARAMETERS.repair_retention)
        row["decay_lambda"] = legacy_decay
        row["decay_rate_raw"] = legacy_decay
        return row

    def build_v33_agent_record(*args, **kwargs):
        safe = dict(kwargs)
        safe["plan"] = _audit_compatible_plan(kwargs.get("plan", {}))
        return original_agent_record_builder(*args, **safe)

    def build_v33_mechanism_record(*args, **kwargs):
        safe = dict(kwargs)
        safe_plan = _audit_compatible_plan(kwargs.get("plan", {}))
        safe["plan"] = safe_plan
        row = original_record_builder(*args, **safe)
        state_data = kwargs["s_data"]
        plan = kwargs["plan"]
        social_count = int(state_data.get("semantic_social_observation_count", 0))
        row.update(
            {
                "scenario_schema_version": SCENARIO_SCHEMA,
                "runtime_schema_version": RUNTIME_SCHEMA,
                "trust_dynamics_schema_version": plan.get(
                    "mechanism_schema_version", ""
                ),
                "semantic_schema_version": state_data.get(
                    "semantic_schema_version", ""
                ),
                "semantic_perceived_peer_approval": state_data.get(
                    "semantic_perceived_peer_approval"
                ),
                "subjective_norm_before": plan.get(
                    "subjective_norm_before", row["subjective_norm_sn"]
                ),
                "subjective_norm_after": plan.get(
                    "subjective_norm_after", row["subjective_norm_sn"]
                ),
                "subjective_norm_peer_update_applied": social_count > 0,
                "legacy_purchase_endpoint_retired": bool(
                    plan.get("legacy_purchase_endpoint_retired", False)
                ),
                "trust_target_after_signal": plan.get(
                    "trust_target_after_signal", ""
                ),
                "trust_adjustment_rate": plan.get("trust_adjustment_rate", ""),
                "crisis_increment": plan.get("crisis_increment", ""),
                "repair_increment": plan.get("repair_increment", ""),
                "repair_saturation_multiplier": plan.get(
                    "repair_saturation_multiplier", ""
                ),
                "crisis_retention": plan.get("crisis_retention", ""),
                "repair_retention": plan.get("repair_retention", ""),
                "event_adjustment": plan.get("event_adjustment", ""),
                "quiet_adjustment": plan.get("quiet_adjustment", ""),
                "repair_saturation": plan.get("repair_saturation", ""),
                "hypocrisy_weight": plan.get("hypocrisy_weight", ""),
            }
        )
        return row

    def public_selector(nodes, base_seed, rate):
        return select_public_exposure_nodes_v33(nodes, base_seed, rate=rate)

    def amplification_selector(graph, seed_nodes):
        return select_paid_amplification_nodes_v33(
            graph,
            seed_nodes,
            base_seed=int(config.random_seed),
            edge_probability=DEFAULT_PAID_EDGE_PROBABILITY,
        )

    class RuntimeInjectorV33(ClarificationInjectorV33):
        def __init__(self, cfg):
            super().__init__(cfg, delivery_lag=DEFAULT_PAID_DELIVERY_LAG)

    try:
        simulation_module._generate_profiles_inline = _scenario_profiles
        simulation_module.build_agent_record = build_v33_agent_record
        simulation_module.build_mechanism_record = build_v33_mechanism_record
        simulation_module.ENTERPRISE_STRATEGY.clear()
        simulation_module.ENTERPRISE_STRATEGY.update({5: CRISIS_STIMULUS})
        clarification_module.CONTENT_TEMPLATES.clear()
        clarification_module.CONTENT_TEMPLATES.update(CLARIFICATION_TEMPLATES)
        plugin_map["GreenCognitionPlugin"] = reflect_plugin_class
        plugin_map["ConsumerPlanPlugin"] = plan_plugin_class
        simulation_module.ClarificationInjector = RuntimeInjectorV33
        simulation_module.select_public_exposure_nodes = public_selector
        simulation_module.one_hop_amplification_nodes = amplification_selector
        yield
    finally:
        simulation_module._generate_profiles_inline = original_profile_builder
        simulation_module.build_agent_record = original_agent_record_builder
        simulation_module.build_mechanism_record = original_record_builder
        simulation_module.ENTERPRISE_STRATEGY.clear()
        simulation_module.ENTERPRISE_STRATEGY.update(original_events)
        clarification_module.CONTENT_TEMPLATES.clear()
        clarification_module.CONTENT_TEMPLATES.update(original_templates)
        plugin_map["GreenCognitionPlugin"] = original_reflect
        plugin_map["ConsumerPlanPlugin"] = original_plan
        simulation_module.ClarificationInjector = original_injector
        simulation_module.select_public_exposure_nodes = original_public_selector
        simulation_module.one_hop_amplification_nodes = original_amplification_selector


async def run_scenario_v33(config: ExperimentConfig, *, override_router) -> dict:
    """Run one communication condition on the isolated v3.3 cognitive path."""

    if override_router is None:
        raise ValueError("scenario-v3.3 requires an explicit version-scoped router")
    if int(config.num_agents) != len(ENGINEERING_PERSONAS):
        raise ValueError("scenario-v3.3 configuration must use 20 cognitive agents")
    if int(config.scandal_tick) != 5 or int(config.total_ticks) != 30:
        raise ValueError("scenario-v3.3 requires crisis Tick 5 and a 30-Tick horizon")

    import clarification_injector
    import simulation_core
    from plugins.agent.plan.ConsumerPlanV33Plugin import ConsumerPlanV33Plugin
    from plugins.agent.reflect.GreenCognitionV32Plugin import GreenCognitionV32Plugin

    with _isolated_runtime_patch(
        simulation_core,
        clarification_injector,
        GreenCognitionV32Plugin,
        ConsumerPlanV33Plugin,
        config,
    ):
        result = await simulation_core.run_simulation_core(
            config,
            override_router=override_router,
        )

    result["scenario_schema_version"] = SCENARIO_SCHEMA
    result["runtime_schema_version"] = RUNTIME_SCHEMA
    result["mechanism_records_schema_version"] = MECHANISM_AUDIT_SCHEMA
    result["engineering_profiles"] = list(engineering_profiles())
    result["legacy_purchase_endpoint_retired"] = True
    result["trust_v33_parameters"] = parameters_audit_payload(DEFAULT_TRUST_PARAMETERS)
    result["clarification_v33_parameters"] = {
        "paid_edge_probability": DEFAULT_PAID_EDGE_PROBABILITY,
        "paid_delivery_lag": DEFAULT_PAID_DELIVERY_LAG,
        "empirically_calibrated": False,
    }
    return result
