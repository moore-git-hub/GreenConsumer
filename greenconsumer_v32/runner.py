from __future__ import annotations

import dataclasses
import datetime as dt
from collections import defaultdict

from experiment_config import generate_experiment_matrix
from task005_fmcg_runtime_v32 import run_scenario_v32

from .config import (
    CONDITION_ORDER,
    DEFAULT_CRISIS_TICK,
    DEFAULT_MICRO_BUYERS,
    DEFAULT_NUM_AGENTS,
    DEFAULT_TOTAL_TICKS,
    RunSettings,
)
from .demand import simulate_demand
from .io import write_csv, write_json
from .routers import (
    RecordingRouter,
    ReplayRouter,
    build_inner_router,
    close_inner_router,
    wrap_audited,
)

MODEL = "qwen-plus"
TEMPERATURE = 0.3


def _configs(settings: RunSettings):
    matrix = {cfg.exp_id: cfg for cfg in generate_experiment_matrix()}
    ids = list(CONDITION_ORDER) if settings.condition == "all" else [settings.condition]
    return [
        dataclasses.replace(
            matrix[exp_id],
            random_seed=settings.simulation_seed,
            num_agents=DEFAULT_NUM_AGENTS,
            total_ticks=DEFAULT_TOTAL_TICKS,
            scandal_tick=DEFAULT_CRISIS_TICK,
        )
        for exp_id in ids
    ]


def _trust_trajectory(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[int(row["tick"])].append(float(row["trust_final"]))
    return [
        {
            "tick": tick,
            "mean_trust": sum(grouped[tick]) / len(grouped[tick]),
        }
        for tick in sorted(grouped)
    ]


async def execute(settings: RunSettings) -> dict:
    settings.validate()
    run_id = dt.datetime.now().strftime("v32_%Y%m%d_%H%M%S")
    run_dir = settings.output_dir / run_id
    if run_dir.exists():
        raise FileExistsError(run_dir)
    run_dir.mkdir(parents=True)

    configs = _configs(settings)
    inner = build_inner_router(settings.llm_mode, settings.requested_llm_seed)
    control_cache = None
    all_cognitive: list[dict] = []
    all_demand: list[dict] = []
    all_curves: list[dict] = []
    condition_meta = []
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
                    routed_inner = RecordingRouter(inner)
                    route_role = "record-control"
                else:
                    if control_cache is None:
                        raise RuntimeError("control history cache was not created")
                    routed_inner = ReplayRouter(
                        inner,
                        control_cache,
                        replay_until=int(cfg.clarification_tick),
                    )
                    route_role = "replay-before-treatment"

            audited = wrap_audited(
                routed_inner,
                audit_path=audit_path,
                run_id=run_id,
                condition=cfg.exp_id,
                requested_llm_seed=settings.requested_llm_seed,
                model=("deterministic-fake" if settings.llm_mode == "fake" else MODEL),
                temperature=(0.0 if settings.llm_mode == "fake" else TEMPERATURE),
            )
            result = await run_scenario_v32(cfg, override_router=audited)
            cognitive = result["mechanism_records"]
            all_cognitive.extend(cognitive)
            write_csv(condition_dir / "cognitive_records.csv", cognitive)
            write_csv(
                condition_dir / "trust_trajectory.csv",
                [
                    {"exp_id": cfg.exp_id, **row}
                    for row in _trust_trajectory(cognitive)
                ],
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
                    "legacy_purchase_endpoint_retired": bool(
                        result["legacy_purchase_endpoint_retired"]
                    ),
                    "event_ticks": [
                        int(row["tick"])
                        for row in result["effective_event_timeline"]
                    ],
                }
            )
    finally:
        await close_inner_router(inner)

    write_csv(run_dir / "cognitive_records.csv", all_cognitive)
    write_csv(run_dir / "demand_opportunities.csv", all_demand)
    write_csv(run_dir / "choice_curves.csv", all_curves)

    payload = {
        "schema_version": "task005_fmcg_v32_clean_run1.0",
        "run_id": run_id,
        "status": "PASS",
        "scope": "engineering/demo; not a new formal replication",
        "llm_mode": settings.llm_mode,
        "condition_request": settings.condition,
        "simulation_seed": settings.simulation_seed,
        "requested_llm_seed": settings.requested_llm_seed,
        "demand_seed": settings.demand_seed,
        "conditions_run": [row["exp_id"] for row in condition_meta],
        "condition_meta": condition_meta,
        "real_llm_execution": settings.llm_mode == "real",
        "formal_reuse_permitted": False,
        "output_dir": str(run_dir),
    }
    write_json(run_dir / "run_summary.json", payload)
    return payload
