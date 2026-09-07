"""TASK_005 v3.2 的统一运行调度器。

本模块串联：
ExperimentConfig → v3.2 AgentKernel cognition → LLM audit/replay →
offline FMCG demand → 统一结果目录。

它只创建 engineering/demo run；已经关闭的 F001-F010 formal sample 不会从
这里启动或扩充。

除机制记录外，本调度器还会把每个 Agent、每个 Tick 的可审计认知摘要写入
``agent_thoughts.csv``。这里的“thought”仅指 GreenCognitionV32Plugin 要求 LLM
返回的一句简短 first-person ``reasoning`` 及其结构化语义评价；它不是隐藏的
chain-of-thought，也不会要求模型输出私有推理过程。
"""
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
    """从唯一实验矩阵构造本次 run 的条件列表。"""
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
    """把 20-agent 机制记录聚合为每 Tick 的 mean trust。"""
    grouped = defaultdict(list)
    for row in rows:
        grouped[int(row["tick"])].append(float(row["trust_final"]))
    return [
        {"tick": tick, "mean_trust": sum(grouped[tick]) / len(grouped[tick])}
        for tick in sorted(grouped)
    ]


def _agent_thought_rows(agent_records: list[dict], mechanism_records: list[dict]) -> list[dict]:
    """构造每 Agent × Tick 的可读 LLM appraisal 审计表。

    ``simulation_core`` 已经在同一 Tick 结算阶段分别生成 agent_records 与
    mechanism_records。本函数只按 (condition, tick, agent_id) 合并两份只读记录，
    不重新计算任何科学变量，也不改变模型状态。

    注意：quiet Tick 没有新的外部/社交观察，因此 ``reasoning`` 可以为空。
    仍然保留这些行，保证一个完整 condition 恰好有
    ``num_agents × total_ticks`` 条记录，便于检查漏行与时序。
    """
    mech_by_key = {
        (str(row["exp_id"]), int(row["tick"]), str(row["agent_id"])): row
        for row in mechanism_records
    }
    rows: list[dict] = []
    for agent_row in agent_records:
        key = (
            str(agent_row["exp_id"]),
            int(agent_row["tick"]),
            str(agent_row["agent_id"]),
        )
        mech = mech_by_key.get(key)
        if mech is None:
            raise RuntimeError(f"missing mechanism record for agent thought key={key}")

        reasoning = str(agent_row.get("reasoning", "") or "").strip()
        rows.append(
            {
                "exp_id": key[0],
                "tick": key[1],
                "agent_id": key[2],
                "cluster_type": str(agent_row.get("cluster_type", "")),
                "social_role": str(agent_row.get("social_role", "")),
                "content_factor": str(agent_row.get("content_factor", "")),
                "channel_factor": str(agent_row.get("channel_factor", "")),
                "timing_factor": str(agent_row.get("timing_factor", "")),
                "reflect_primary_source": str(agent_row.get("reflect_primary_source", "")),
                "observation_count": int(agent_row.get("observation_count", 0) or 0),
                "observation_sources": str(agent_row.get("observation_sources", "")),
                "semantic_observation_present": bool(
                    mech.get("semantic_observation_present", False)
                ),
                "semantic_social_observation_count": int(
                    mech.get("semantic_social_observation_count", 0) or 0
                ),
                "semantic_valence": mech.get("semantic_valence", ""),
                "semantic_arousal": mech.get("semantic_arousal", ""),
                "semantic_credibility": mech.get("semantic_credibility", ""),
                "semantic_evidence_strength": mech.get(
                    "semantic_evidence_strength", ""
                ),
                "semantic_topic_relevance": mech.get("semantic_topic_relevance", ""),
                "semantic_perceived_empathy": mech.get(
                    "semantic_perceived_empathy", ""
                ),
                "semantic_hypocrisy_perceived": bool(
                    mech.get("semantic_hypocrisy_perceived", False)
                ),
                "importance": agent_row.get("importance", ""),
                "thought_present": bool(reasoning),
                "reasoning": reasoning,
                "previous_trust": mech.get("previous_trust", ""),
                "trust_final": mech.get("trust_final", ""),
                "attitude_att": mech.get("attitude_att", ""),
                "subjective_norm_sn": mech.get("subjective_norm_sn", ""),
                "pbc": mech.get("pbc", ""),
                "purchase_intention": mech.get("purchase_intention", ""),
                "posting_intention": mech.get("posting_intention", ""),
                "is_posting": bool(agent_row.get("is_posting", False)),
                "post_content": str(agent_row.get("post_content", "") or ""),
                "clarification_received": bool(
                    agent_row.get("clarification_received", False)
                ),
                "clarification_content_type": str(
                    agent_row.get("clarification_content_type", "")
                ),
                "semantic_fallback_used": bool(
                    mech.get("semantic_fallback_used", False)
                ),
            }
        )
    return rows


async def execute(settings: RunSettings) -> dict:
    """运行一个完整 engineering/demo job，并返回 run summary。"""
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
    all_agent_records: list[dict] = []
    all_thoughts: list[dict] = []
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

            # 全矩阵运行：control 先记录；8个策略在各自 clarification tick
            # 之前重放同一 control history。单条件运行则直接调用 router。
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

            # 每个 condition 独立写一份 LLM audit JSONL。
            audited = wrap_audited(
                routed_inner,
                audit_path=audit_path,
                run_id=run_id,
                condition=cfg.exp_id,
                requested_llm_seed=settings.requested_llm_seed,
                model="deterministic-fake" if settings.llm_mode == "fake" else MODEL,
                temperature=0.0 if settings.llm_mode == "fake" else TEMPERATURE,
            )

            # 这里进入冻结的 v3.2 scientific runtime。
            result = await run_scenario_v32(cfg, override_router=audited)
            cognitive = result["mechanism_records"]
            agent_records = result["agent_records"]
            thoughts = _agent_thought_rows(agent_records, cognitive)

            all_cognitive.extend(cognitive)
            all_agent_records.extend(agent_records)
            all_thoughts.extend(thoughts)

            write_csv(condition_dir / "cognitive_records.csv", cognitive)
            write_csv(condition_dir / "agent_records.csv", agent_records)
            write_csv(condition_dir / "agent_thoughts.csv", thoughts)
            write_csv(
                condition_dir / "trust_trajectory.csv",
                [{"exp_id": cfg.exp_id, **row} for row in _trust_trajectory(cognitive)],
            )

            # control 结束后冻结本次 run 的 common-history cache。
            if settings.condition == "all" and cfg.is_control:
                control_cache = dict(routed_inner.cache)

            if isinstance(routed_inner, ReplayRouter):
                replay_hits = routed_inner.replay_hits
                replay_misses = routed_inner.replay_misses
                if replay_misses:
                    raise RuntimeError(f"{cfg.exp_id}: common-history replay miss")

            # Demand 与认知轨迹离线交叉；conversion support 不改变 LLM
            # cognition，只通过购买层的 PBC facilitation 生效。
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
                }
            )
    finally:
        # 即使中途报错，也尽量释放 HTTP/client 资源。
        await close_inner_router(inner)

    # run-level 汇总文件是分析/画图的唯一输入入口。
    write_csv(run_dir / "cognitive_records.csv", all_cognitive)
    write_csv(run_dir / "agent_records.csv", all_agent_records)
    write_csv(run_dir / "agent_thoughts.csv", all_thoughts)
    write_csv(run_dir / "demand_opportunities.csv", all_demand)
    write_csv(run_dir / "choice_curves.csv", all_curves)

    payload = {
        "schema_version": "task005_fmcg_v32_clean_run1.2",
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
        "agent_thought_output": "agent_thoughts.csv",
        "agent_thought_definition": (
            "one concise first-person reasoning sentence returned by the semantic "
            "appraisal prompt plus structured appraisal/state fields; not hidden chain-of-thought"
        ),
        "agent_thought_rows": len(all_thoughts),
        "agent_thought_events": sum(
            1 for row in all_thoughts if row["thought_present"]
        ),
        "semantic_fallback_events": sum(
            1 for row in all_thoughts if row["semantic_fallback_used"]
        ),
        "real_llm_execution": settings.llm_mode == "real",
        "formal_reuse_permitted": False,
        "output_dir": str(run_dir),
    }
    write_json(run_dir / "run_summary.json", payload)
    return payload
