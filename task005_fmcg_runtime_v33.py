"""Isolated AgentKernel runtime adapter for TASK_005 scenario-v3.3.1.

v3.3.1 preserves the v3.3 scientific mechanism while fixing text-integrity
artifacts and enriching auditable output. It reuses the same fictional FMCG
scenario and experiment matrix while patching only explicitly version-scoped
components.

Optional ``trust_parameters``, ``clarification_parameters`` and ``network_spec``
arguments exist solely to support labelled sensitivity experiments. Their
defaults preserve the frozen v3.3.1 baseline. Every patched object/parameter is
restored after the condition run. No v3.2 source file or closed F001-F010 formal
result is modified by this runtime.
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
from mechanism_v33 import (
    DEFAULT_TRUST_PARAMETERS,
    TrustDynamicsV33Parameters,
    parameters_audit_payload,
)
from clarification_diffusion_v33 import (
    DEFAULT_CLARIFICATION_PARAMETERS,
    ClarificationDiffusionV33Parameters,
    ClarificationInjectorV33,
    clarification_parameters_audit_payload,
    select_paid_amplification_nodes_v33,
    select_public_exposure_nodes_v33,
)
from greenconsumer_v33.config import DEFAULT_CRISIS_TICK, HORIZON_ROBUSTNESS_TICKS
from greenconsumer_v33.network_variants import (
    NetworkVariantV331Spec,
    build_directed_network_variant,
)

RUNTIME_SCHEMA = "task005-fmcg-runtime-3.3.1"
MECHANISM_AUDIT_SCHEMA = "mechanism-records-fmcg-3.3.1"
CODE_RELEASE = "TASK_005_FMCG_V3.3.1"


def _validate_runtime_config_v331(
    config: ExperimentConfig,
    *,
    override_router,
) -> dict:
    """Pure, zero-I/O validation of v3.3.1 runtime invariants."""

    if override_router is None:
        raise ValueError("scenario-v3.3.1 requires an explicit version-scoped router")
    if int(config.num_agents) != len(ENGINEERING_PERSONAS):
        raise ValueError("scenario-v3.3.1 configuration must use 20 cognitive agents")
    if int(config.scandal_tick) != DEFAULT_CRISIS_TICK:
        raise ValueError(
            f"scenario-v3.3.1 requires crisis Tick {DEFAULT_CRISIS_TICK}"
        )
    if int(config.total_ticks) not in HORIZON_ROBUSTNESS_TICKS:
        raise ValueError(
            "scenario-v3.3.1 total_ticks must use the pre-specified horizon grid "
            f"{HORIZON_ROBUSTNESS_TICKS}; got {config.total_ticks}"
        )
    return {
        "runtime_total_ticks": int(config.total_ticks),
        "runtime_horizon_grid": list(HORIZON_ROBUSTNESS_TICKS),
        "runtime_num_agents": int(config.num_agents),
        "runtime_crisis_tick": int(config.scandal_tick),
    }


def _restore_full_text_audit_fields(row: dict, *, plan, thought) -> dict:
    """Restore full v3.3.1 LLM text after the legacy audit builder runs."""

    restored = dict(row or {})
    restored["post_content"] = str((plan or {}).get("post_content", "") or "")
    restored["reasoning"] = str((thought or {}).get("reasoning", "") or "")
    return restored


def _scenario_profiles(num_agents: int, seed: int) -> list[dict]:
    del seed
    if int(num_agents) != len(ENGINEERING_PERSONAS):
        raise ValueError(
            f"scenario-v3.3.1 requires exactly {len(ENGINEERING_PERSONAS)} cognitive agents"
        )
    return [copy.deepcopy(row) for row in engineering_profiles()]


@contextmanager
def _isolated_runtime_patch(
    simulation_module,
    clarification_module,
    reflect_plugin_class,
    plan_plugin_class,
    config: ExperimentConfig,
    trust_parameters: TrustDynamicsV33Parameters,
    clarification_parameters: ClarificationDiffusionV33Parameters,
    network_spec: NetworkVariantV331Spec | None,
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
    original_plan_trust_parameters = plan_plugin_class.TRUST_PARAMETERS

    original_injector = simulation_module.ClarificationInjector
    original_public_selector = simulation_module.select_public_exposure_nodes
    original_amplification_selector = simulation_module.one_hop_amplification_nodes
    original_network_plugin = simulation_module.SocialNetworkPlugin

    def _audit_compatible_plan(plan):
        """Keep legacy audit fields numeric without changing v3.3 science."""
        row = dict(plan or {})
        legacy_decay = 1.0 - float(trust_parameters.repair_retention)
        row["decay_lambda"] = legacy_decay
        row["decay_rate_raw"] = legacy_decay
        return row

    def build_v331_agent_record(*args, **kwargs):
        safe = dict(kwargs)
        safe["plan"] = _audit_compatible_plan(kwargs.get("plan", {}))
        row = original_agent_record_builder(*args, **safe)
        return _restore_full_text_audit_fields(
            row,
            plan=kwargs.get("plan", {}),
            thought=kwargs.get("thought", {}),
        )

    def build_v331_mechanism_record(*args, **kwargs):
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
                "code_release": CODE_RELEASE,
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
            edge_probability=float(clarification_parameters.paid_edge_probability),
        )

    class RuntimeInjectorV33(ClarificationInjectorV33):
        def __init__(self, cfg):
            super().__init__(
                cfg,
                delivery_lag=int(clarification_parameters.paid_delivery_lag),
            )

    if network_spec is not None:
        class RuntimeSocialNetworkPlugin(original_network_plugin):
            """Version-scoped topology variant; production plugin remains untouched."""

            def register_agents(self, agents, seed: int = 42):
                del seed
                self.agent_registry = {a.agent_id: a for a in agents}
                agent_ids = list(self.agent_registry.keys())
                graph, audit = build_directed_network_variant(agent_ids, network_spec)
                self.graph = graph
                self.network_type = str(audit["network_type"])
                self.network_params = dict(audit)
                self.network_fallback_reason = ""
                print(
                    f"[Network-v3.3.1-variant] topology={network_spec.topology} "
                    f"network_seed={network_spec.network_seed} "
                    f"nodes={graph.number_of_nodes()} edges={graph.number_of_edges()}"
                )
    else:
        RuntimeSocialNetworkPlugin = original_network_plugin

    try:
        simulation_module._generate_profiles_inline = _scenario_profiles
        simulation_module.build_agent_record = build_v331_agent_record
        simulation_module.build_mechanism_record = build_v331_mechanism_record
        simulation_module.ENTERPRISE_STRATEGY.clear()
        simulation_module.ENTERPRISE_STRATEGY.update({5: CRISIS_STIMULUS})
        clarification_module.CONTENT_TEMPLATES.clear()
        clarification_module.CONTENT_TEMPLATES.update(CLARIFICATION_TEMPLATES)
        plan_plugin_class.TRUST_PARAMETERS = trust_parameters
        plugin_map["GreenCognitionPlugin"] = reflect_plugin_class
        plugin_map["ConsumerPlanPlugin"] = plan_plugin_class
        simulation_module.ClarificationInjector = RuntimeInjectorV33
        simulation_module.select_public_exposure_nodes = public_selector
        simulation_module.one_hop_amplification_nodes = amplification_selector
        simulation_module.SocialNetworkPlugin = RuntimeSocialNetworkPlugin
        yield
    finally:
        simulation_module._generate_profiles_inline = original_profile_builder
        simulation_module.build_agent_record = original_agent_record_builder
        simulation_module.build_mechanism_record = original_record_builder
        simulation_module.ENTERPRISE_STRATEGY.clear()
        simulation_module.ENTERPRISE_STRATEGY.update(original_events)
        clarification_module.CONTENT_TEMPLATES.clear()
        clarification_module.CONTENT_TEMPLATES.update(original_templates)
        plan_plugin_class.TRUST_PARAMETERS = original_plan_trust_parameters
        plugin_map["GreenCognitionPlugin"] = original_reflect
        plugin_map["ConsumerPlanPlugin"] = original_plan
        simulation_module.ClarificationInjector = original_injector
        simulation_module.select_public_exposure_nodes = original_public_selector
        simulation_module.one_hop_amplification_nodes = original_amplification_selector
        simulation_module.SocialNetworkPlugin = original_network_plugin


async def run_scenario_v33(
    config: ExperimentConfig,
    *,
    override_router,
    trust_parameters: TrustDynamicsV33Parameters = DEFAULT_TRUST_PARAMETERS,
    clarification_parameters: ClarificationDiffusionV33Parameters = DEFAULT_CLARIFICATION_PARAMETERS,
    network_spec: NetworkVariantV331Spec | None = None,
) -> dict:
    """Run one communication condition on the isolated v3.3.1 cognitive path."""

    if not isinstance(trust_parameters, TrustDynamicsV33Parameters):
        raise TypeError("trust_parameters must be TrustDynamicsV33Parameters")
    if not isinstance(clarification_parameters, ClarificationDiffusionV33Parameters):
        raise TypeError(
            "clarification_parameters must be ClarificationDiffusionV33Parameters"
        )
    if network_spec is not None and not isinstance(network_spec, NetworkVariantV331Spec):
        raise TypeError("network_spec must be NetworkVariantV331Spec or None")
    if network_spec is not None:
        network_spec.validate(int(config.num_agents))

    runtime_validation = _validate_runtime_config_v331(
        config,
        override_router=override_router,
    )

    import clarification_injector
    import simulation_core
    from plugins.agent.plan.ConsumerPlanV33Plugin import ConsumerPlanV33Plugin
    from plugins.agent.reflect.GreenCognitionV33Plugin import GreenCognitionV33Plugin

    with _isolated_runtime_patch(
        simulation_core,
        clarification_injector,
        GreenCognitionV33Plugin,
        ConsumerPlanV33Plugin,
        config,
        trust_parameters,
        clarification_parameters,
        network_spec,
    ):
        result = await simulation_core.run_simulation_core(
            config,
            override_router=override_router,
        )

    result["scenario_schema_version"] = SCENARIO_SCHEMA
    result["runtime_schema_version"] = RUNTIME_SCHEMA
    result["code_release"] = CODE_RELEASE
    result["mechanism_records_schema_version"] = MECHANISM_AUDIT_SCHEMA
    result["engineering_profiles"] = list(engineering_profiles())
    result["legacy_purchase_endpoint_retired"] = True
    result.update(runtime_validation)
    result["trust_v33_parameters"] = parameters_audit_payload(trust_parameters)
    result["clarification_v33_parameters"] = clarification_parameters_audit_payload(
        clarification_parameters
    )
    result["network_variant"] = (
        network_spec.audit_payload() if network_spec is not None else {
            "topology": "production-baseline",
            "role": "frozen-baseline",
        }
    )
    return result
