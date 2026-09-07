"""Isolated AgentKernel runtime adapter for TASK_005 scenario-v3.2.

The adapter temporarily supplies versioned profiles, stimuli and plugins to the
existing simulation engine, then restores every patched object.  Default
mechanism-v2 behavior and historical runners remain byte- and behavior-stable.
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


RUNTIME_SCHEMA = "task005-fmcg-runtime-3.2"
MECHANISM_AUDIT_SCHEMA = "mechanism-records-fmcg-3.2"


def _scenario_profiles(num_agents: int, seed: int) -> list[dict]:
    del seed  # The balanced engineering panel is frozen independently of RNG.
    if int(num_agents) != len(ENGINEERING_PERSONAS):
        raise ValueError(
            f"scenario-v3.2 requires exactly {len(ENGINEERING_PERSONAS)} cognitive agents"
        )
    return [copy.deepcopy(row) for row in engineering_profiles()]


@contextmanager
def _isolated_runtime_patch(
    simulation_module,
    clarification_module,
    reflect_plugin_class,
    plan_plugin_class,
):
    """Patch explicit module objects so restoration can be unit-tested."""

    original_profile_builder = simulation_module._generate_profiles_inline
    original_record_builder = simulation_module.build_mechanism_record
    original_events = dict(simulation_module.ENTERPRISE_STRATEGY)
    original_templates = dict(clarification_module.CONTENT_TEMPLATES)
    plugin_map = simulation_module.resource_maps["agent_plugins"]
    original_reflect = plugin_map["GreenCognitionPlugin"]
    original_plan = plugin_map["ConsumerPlanPlugin"]

    def build_v32_mechanism_record(*args, **kwargs):
        row = original_record_builder(*args, **kwargs)
        state_data = kwargs["s_data"]
        plan = kwargs["plan"]
        social_count = int(
            state_data.get("semantic_social_observation_count", 0)
        )
        row.update(
            {
                "scenario_schema_version": SCENARIO_SCHEMA,
                "runtime_schema_version": RUNTIME_SCHEMA,
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
            }
        )
        return row

    try:
        simulation_module._generate_profiles_inline = _scenario_profiles
        simulation_module.build_mechanism_record = build_v32_mechanism_record
        simulation_module.ENTERPRISE_STRATEGY.clear()
        simulation_module.ENTERPRISE_STRATEGY.update({5: CRISIS_STIMULUS})
        clarification_module.CONTENT_TEMPLATES.clear()
        clarification_module.CONTENT_TEMPLATES.update(CLARIFICATION_TEMPLATES)
        plugin_map["GreenCognitionPlugin"] = reflect_plugin_class
        plugin_map["ConsumerPlanPlugin"] = plan_plugin_class
        yield
    finally:
        simulation_module._generate_profiles_inline = original_profile_builder
        simulation_module.build_mechanism_record = original_record_builder
        simulation_module.ENTERPRISE_STRATEGY.clear()
        simulation_module.ENTERPRISE_STRATEGY.update(original_events)
        clarification_module.CONTENT_TEMPLATES.clear()
        clarification_module.CONTENT_TEMPLATES.update(original_templates)
        plugin_map["GreenCognitionPlugin"] = original_reflect
        plugin_map["ConsumerPlanPlugin"] = original_plan


async def run_scenario_v32(config: ExperimentConfig, *, override_router) -> dict:
    """Run one communication condition on the isolated v3.2 cognitive path."""

    if override_router is None:
        raise ValueError(
            "scenario-v3.2 requires an explicit version-scoped router; "
            "implicit model construction is prohibited"
        )
    if int(config.num_agents) != len(ENGINEERING_PERSONAS):
        raise ValueError("scenario-v3.2 configuration must use 20 cognitive agents")
    if int(config.scandal_tick) != 5 or int(config.total_ticks) != 30:
        raise ValueError("scenario-v3.2 requires crisis Tick 5 and a 30-Tick horizon")

    # Lazy imports keep pure contract tests executable in restricted containers;
    # the actual kernel dependency is still mandatory when this function runs.
    import clarification_injector
    import simulation_core
    from plugins.agent.plan.ConsumerPlanV32Plugin import ConsumerPlanV32Plugin
    from plugins.agent.reflect.GreenCognitionV32Plugin import (
        GreenCognitionV32Plugin,
    )

    with _isolated_runtime_patch(
        simulation_core,
        clarification_injector,
        GreenCognitionV32Plugin,
        ConsumerPlanV32Plugin,
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
    return result
