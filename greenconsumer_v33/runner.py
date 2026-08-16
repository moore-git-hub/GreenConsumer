"""TASK_005 v3.3.1 engineering runner.

This runner remains parallel to ``greenconsumer_v32.runner``. It never extends
the closed F001-F010 formal sample. Real-LLM temperature remains 0.3 so model
structure and LLM sampling are not changed simultaneously.

v3.3.1 adds output/provenance instrumentation only:
- complete per-Agent appraisal text via the version-scoped v3.3 cognition path;
- run-level network topology and targeting/exposure audit files;
- Git provenance and explicit code-release markers.

Experiment-design note:
- the v3.3.1 scientific mechanism is unchanged;
- the baseline finite horizon is 35 Ticks = 30 post-crisis days after T5;
- T30 and T40 are pre-specified endpoint-robustness checks, not tuned endpoints;
- an explicit Trust-parameter argument is available only for labelled
  sensitivity suites; its default is the frozen v3.3.1 baseline.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import subprocess
from pathlib import Path

from experiment_config import generate_experiment_matrix
from mechanism_v33 import DEFAULT_TRUST_PARAMETERS, TrustDynamicsV33Parameters
from task005_fmcg_runtime_v33 import CODE_RELEASE, run_scenario_v33

from greenconsumer_v32.io import write_csv, write_json
from greenconsumer_v32.routers import (
    RecordingRouter,
    ReplayRouter,
    build_inner_router,
    close_inner_router,
    wrap_audited,
)
from greenconsumer_v32.runner import _agent_thought_rows, _trust_trajectory

from .config import (
    CONDITION_ORDER,
    DEFAULT_CRISIS_TICK,
    DEFAULT_MICRO_BUYERS,
    DEFAULT_NUM_AGENTS,
    DEFAULT_TOTAL_TICKS,
    HORIZON_ROBUSTNESS_TICKS,
    PROJECT_ROOT,
    RunSettings,
    TIME_UNIT,
    horizon_role,
)
from .demand import simulate_demand

MODEL = "qwen-plus-2025-12-01"
TEMPERATURE = 0.3
RUN_SCHEMA = "task005_fmcg_v331_engineering_run1.1"


def _configs(settings: RunSettings):
    matrix = {cfg.exp_id: cfg for cfg in generate_experiment_matrix()}
    ids = list(CONDITION_ORDER) if settings.condition == "all" else [settings.condition]
    return [
        dataclasses.replace(
            matrix[exp_id],
            random_seed=settings.simulation_seed,
            num_agents=DEFAULT_NUM_AGENTS,
            total_ticks=int(settings.total_ticks),
            scandal_tick=DEFAULT_CRISIS_TICK,
        )
        for exp_id in ids
    ]


def _git_provenance(project_root: Path = PROJECT_ROOT) -> dict:
    """Best-effort Git identity for reproducibility; never mutates the repository."""

    def run_git(*args):
        proc = subprocess.run(
            ["git", *args],
            cwd=str(project_root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""

    head = run_git("rev-parse", "HEAD")
    branch = run_git("branch", "--show-current")
    status = run_git("status", "--porcelain", "--untracked-files=normal")
    return {
        "git_head": head,
        "git_branch": branch,
        "git_dirty": bool(status),
        "git_status_short": status,
    }


def _topology_signature(meta: dict, nodes: list[dict], edges: list[dict]) -> tuple:
    """Canonical immutable topology identity used to verify all conditions share one graph."""

    return (
        str(meta.get("network_hash", "")),
        tuple(
            sorted(
                (
                    str(row.get("agent_id", "")),
                    int(row.get("out_degree", 0)),
                    int(row.get("in_degree", 0)),
                )
                for row in nodes
            )
        ),
        tuple(
            sorted(
                (
                    str(row.get("source_agent_id", "")),
                    str(row.get("target_agent_id", "")),
                    str(row.get("is_directed", "")),
                )
                for row in edges
            )
        ),
    )


async def execute(
    settings: RunSettings,
    *,
    trust_parameters: TrustDynamicsV33Parameters = DEFAULT_TRUST_PARAMETERS,
    before_provider_call=None,
) -> dict:
    """Run one v3.3.1 engineering/demo job and persist auditable outputs."""

    settings.validate()
    if not isinstance(trust_parameters, TrustDynamicsV33Parameters):
        raise TypeError("trust_parameters must be TrustDynamicsV33Parameters")
    if before_provider_call is not None and settings.condition != "all":
        raise ValueError(
            "before_provider_call is supported only for condition='all', where "
            "RecordingRouter/ReplayRouter identify actual provider invocations"
        )

    run_id = dt.datetime.now().strftime("v331_%Y%m%d_%H%M%S")
    run_dir = settings.output_dir / run_id
    if run_dir.exists():
        raise FileExistsError(run_dir)
    run_dir.mkdir(parents=True)

    configs = _configs(settings)
    inner = build_inner_router(
        settings.llm_mode,
        settings.requested_llm_seed,
        model_override=MODEL,
    )

    control_cache = None
    all_cognitive: list[dict] = []
    all_agent_records: list[dict] = []
    all_thoughts: list[dict] = []
    all_demand: list[dict] = []
    all_curves: list[dict] = []
    all_target_nodes: list[dict] = []
    all_exposure_plan: list[dict] = []
    condition_meta = []
    trust_parameter_payload = None
    clarification_parameters = None

    topology_signature = None
    topology_meta = None
    topology_nodes = None
    topology_edges = None
    event_timeline = None

    try:
        for cfg in configs:
            condition_dir = run_dir / "conditions" / cfg.exp_id
            audit_path = condition_dir / "llm_audit.jsonl"

            routed_inner = inner
            route_role = "direct"
            replay_hits = 0
            replay_misses = 0

            if settings.condition == "all":
                if cfg.is_control:
                    routed_inner = RecordingRouter(
                        inner, before_provider_call=before_provider_call
                    )
                    route_role = "record-control"
                else:
                    if control_cache is None:
                        raise RuntimeError("control history cache was not created")
                    routed_inner = ReplayRouter(
                        inner,
                        control_cache,
                        replay_until=int(cfg.clarification_tick),
                        before_provider_call=before_provider_call,
                    )
                    route_role = "replay-before-treatment"

            audited = wrap_audited(
                routed_inner,
                audit_path=audit_path,
                run_id=run_id,
                condition=cfg.exp_id,
                requested_llm_seed=settings.requested_llm_seed,
                model="deterministic-fake" if settings.llm_mode == "fake" else MODEL,
                temperature=0.0 if settings.llm_mode == "fake" else TEMPERATURE,
            )

            result = await run_scenario_v33(
                cfg,
                override_router=audited,
                trust_parameters=trust_parameters,
            )
            cognitive = result["mechanism_records"]
            agent_records = result["agent_records"]
            thoughts = _agent_thought_rows(agent_records, cognitive)
            trust_parameter_payload = result.get("trust_v33_parameters")
            clarification_parameters = result.get("clarification_v33_parameters")

            all_cognitive.extend(cognitive)
            all_agent_records.extend(agent_records)
            all_thoughts.extend(thoughts)

            write_csv(condition_dir / "cognitive_records.csv", cognitive)
            write_csv(condition_dir / "agent_records.csv", agent_records)
            write_csv(condition_dir / "agent_thoughts.csv", thoughts)
            write_csv(
                condition_dir / "trust_trajectory.csv",
                [
                    {"exp_id": cfg.exp_id, **row}
                    for row in _trust_trajectory(cognitive)
                ],
            )

            network_meta = dict(result.get("network_meta") or {})
            network_nodes = list(result.get("network_nodes") or [])
            network_edges = list(result.get("network_edges") or [])
            signature = _topology_signature(network_meta, network_nodes, network_edges)
            if topology_signature is None:
                topology_signature = signature
                topology_meta = {k: v for k, v in network_meta.items() if k != "exp_id"}
                topology_nodes = network_nodes
                topology_edges = network_edges
            elif signature != topology_signature:
                raise RuntimeError(
                    f"{cfg.exp_id}: network topology differs within one blocked run"
                )

            target_rows = list(result.get("target_nodes_meta") or [])
            exposure_rows = list(result.get("clarification_exposure_meta") or [])
            all_target_nodes.extend(target_rows)
            all_exposure_plan.extend(exposure_rows)

            current_timeline = list(result.get("effective_event_timeline") or [])
            if event_timeline is None:
                event_timeline = current_timeline
            elif current_timeline != event_timeline:
                raise RuntimeError(
                    f"{cfg.exp_id}: effective global-event timeline differs within run"
                )

            if settings.condition == "all" and cfg.is_control:
                control_cache = dict(routed_inner.cache)

            if isinstance(routed_inner, ReplayRouter):
                replay_hits = routed_inner.replay_hits
                replay_misses = routed_inner.replay_misses
                if replay_misses:
                    raise RuntimeError(f"{cfg.exp_id}: common-history replay miss")

            support_levels = []
            if settings.run_demand:
                if settings.support_mode in {"absent", "both"}:
                    support_levels.append(False)
                if settings.support_mode in {"present", "both"}:
                    support_levels.append(True)

                for support in support_levels:
                    demand, curves = simulate_demand(
                        cognitive,
                        support_present=support,
                        demand_seed=settings.demand_seed,
                        micro_buyers=DEFAULT_MICRO_BUYERS,
                    )
                    all_demand.extend(demand)
                    all_curves.extend(curves)

            condition_meta.append(
                {
                    "exp_id": cfg.exp_id,
                    "route_role": route_role,
                    "logical_llm_calls": audited.call_count,
                    "provider_calls": int(
                        getattr(routed_inner, "provider_calls", audited.call_count)
                    ),
                    "replay_hits": replay_hits,
                    "replay_misses": replay_misses,
                    "agent_tick_rows": len(agent_records),
                    "agent_thought_rows": len(thoughts),
                    "agent_thought_events": sum(
                        1 for row in thoughts if row["thought_present"]
                    ),
                    "semantic_fallback_events": sum(
                        1 for row in thoughts if row["semantic_fallback_used"]
                    ),
                    "legacy_purchase_endpoint_retired": bool(
                        result["legacy_purchase_endpoint_retired"]
                    ),
                    "event_ticks": [
                        int(row["tick"])
                        for row in result["effective_event_timeline"]
                    ],
                    "network_hash": network_meta.get("network_hash", ""),
                    "target_node_count": len(target_rows),
                    "planned_exposure_count": sum(
                        1 for row in exposure_rows if bool(row.get("reached"))
                    ),
                }
            )
    finally:
        await close_inner_router(inner)

    write_csv(run_dir / "cognitive_records.csv", all_cognitive)
    write_csv(run_dir / "agent_records.csv", all_agent_records)
    write_csv(run_dir / "agent_thoughts.csv", all_thoughts)
    write_csv(run_dir / "demand_opportunities.csv", all_demand)
    write_csv(run_dir / "choice_curves.csv", all_curves)

    write_json(run_dir / "network_meta.json", topology_meta or {})
    write_csv(run_dir / "network_nodes.csv", topology_nodes or [])
    write_csv(run_dir / "network_edges.csv", topology_edges or [])
    write_csv(run_dir / "target_nodes.csv", all_target_nodes)
    write_csv(run_dir / "clarification_exposure_plan.csv", all_exposure_plan)
    write_json(
        run_dir / "effective_event_timeline.json",
        {"events": event_timeline or []},
    )

    provenance = _git_provenance()
    payload = {
        "schema_version": RUN_SCHEMA,
        "code_release": CODE_RELEASE,
        "run_id": run_id,
        "status": "PASS",
        "scope": "v3.3.1 engineering/demo; not a new formal replication",
        "llm_mode": settings.llm_mode,
        "llm_model": "deterministic-fake" if settings.llm_mode == "fake" else MODEL,
        "llm_temperature": 0.0 if settings.llm_mode == "fake" else TEMPERATURE,
        "condition_request": settings.condition,
        "simulation_seed": settings.simulation_seed,
        "requested_llm_seed": settings.requested_llm_seed,
        "demand_seed": settings.demand_seed,
        "total_ticks": int(settings.total_ticks),
        "time_design": {
            "tick_unit": TIME_UNIT,
            "crisis_tick": DEFAULT_CRISIS_TICK,
            "total_ticks": int(settings.total_ticks),
            "post_crisis_observation_days": int(settings.total_ticks) - DEFAULT_CRISIS_TICK,
            "baseline_total_ticks": DEFAULT_TOTAL_TICKS,
            "pre_specified_horizon_robustness_ticks": list(HORIZON_ROBUSTNESS_TICKS),
            "horizon_role": horizon_role(settings.total_ticks),
            "endpoint_rule": (
                "T35 is the baseline endpoint; T30 and T40 are horizon-robustness checks only"
            ),
        },
        "conditions_run": [row["exp_id"] for row in condition_meta],
        "condition_meta": condition_meta,
        "trust_v33_parameters": trust_parameter_payload,
        "trust_parameter_role": (
            "frozen-baseline"
            if trust_parameters == DEFAULT_TRUST_PARAMETERS
            else "explicit-sensitivity-profile"
        ),
        "clarification_v33_parameters": clarification_parameters,
        "demand_v33": {
            "renewal_purchase_opportunities": True,
            "loyalty_update": "bounded_ewma",
            "micro_buyers_per_cognitive_agent": DEFAULT_MICRO_BUYERS,
            "empirically_calibrated": False,
        },
        "network": {
            **(topology_meta or {}),
            "cognitive_agents": DEFAULT_NUM_AGENTS,
            "network_nodes_file": "network_nodes.csv",
            "network_edges_file": "network_edges.csv",
            "target_nodes_file": "target_nodes.csv",
            "clarification_exposure_plan_file": "clarification_exposure_plan.csv",
        },
        "agent_thought_output": "agent_thoughts.csv",
        "agent_thought_rows": len(all_thoughts),
        "agent_thought_events": sum(
            1 for row in all_thoughts if row["thought_present"]
        ),
        "semantic_fallback_events": sum(
            1 for row in all_thoughts if row["semantic_fallback_used"]
        ),
        "real_llm_execution": settings.llm_mode == "real",
        "formal_inference_performed": False,
        "formal_reuse_permitted": False,
        "external_validity_claimed": False,
        "git_provenance": provenance,
        "output_dir": str(run_dir),
    }
    write_json(run_dir / "run_summary.json", payload)
    return payload
