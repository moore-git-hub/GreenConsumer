"""Execute the v3.2 9 x 2 smoke test through the real AgentKernel lifecycle.

Only the deterministic fake semantic router is permitted here.  A successful
run is an engineering gate, not a real-LLM pilot or formal experiment.
"""

from __future__ import annotations

import asyncio
import csv
import dataclasses
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.task005_fmcg_fake_model_smoke_v32 import (
    CONTRACT_SEED,
    _pre_signature,
    _schedule_signature,
    _simulate_demand,
    _write_csv,
)
from experiment_config import generate_experiment_matrix
from task005_fmcg_fake_router_v32 import DeterministicFMCGSemanticRouterV32
from task005_fmcg_runtime_v32 import run_scenario_v32


OUT_DIR = ROOT / ".kiro" / "specs" / "task005-replication-inference"
BLOCKER_PATH = OUT_DIR / "fmcg_v32_kernel_fake_smoke_blocker1.0.json"
RESULT_PATH = OUT_DIR / "fmcg_v32_kernel_fake_smoke_result1.0.json"
COGNITIVE_PATH = OUT_DIR / "fmcg_v32_kernel_fake_cognitive_records1.0.csv"
DEMAND_PATH = OUT_DIR / "fmcg_v32_kernel_fake_demand_opportunities1.0.csv"
CURVE_PATH = OUT_DIR / "fmcg_v32_kernel_fake_choice_curves1.0.csv"


async def _run_all_conditions():
    conditions = {}
    meta = {}
    for base in generate_experiment_matrix():
        config = dataclasses.replace(
            base,
            random_seed=CONTRACT_SEED,
            num_agents=20,
            total_ticks=30,
            scandal_tick=5,
        )
        router = DeterministicFMCGSemanticRouterV32()
        result = await run_scenario_v32(config, override_router=router)
        conditions[config.exp_id] = result["mechanism_records"]
        meta[config.exp_id] = {
            "fake_router_calls": router.call_count,
            "event_ticks": [row["tick"] for row in result["effective_event_timeline"]],
            "legacy_purchase_endpoint_retired": result[
                "legacy_purchase_endpoint_retired"
            ],
        }
    return conditions, meta


def _dependency_blocker(exc: ModuleNotFoundError) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "fmcg_v32_kernel_fake_smoke_blocker1.0",
        "status": "BLOCKED_MISSING_DEPENDENCY",
        "missing_module": exc.name,
        "error_type": type(exc).__name__,
        "real_llm_calls": 0,
        "external_api_calls": 0,
        "engineering_pilot_authorized": False,
        "formal_execution_authorized": False,
    }
    BLOCKER_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, sort_keys=True))
    return 2


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        cognitive_by_condition, runtime_meta = asyncio.run(_run_all_conditions())
    except ModuleNotFoundError as exc:
        return _dependency_blocker(exc)

    cognitive_rows = [
        row for rows in cognitive_by_condition.values() for row in rows
    ]
    demand_by_condition = {}
    curves = []
    for exp_id, cognitive in cognitive_by_condition.items():
        for support_present in (False, True):
            rows, condition_curves = _simulate_demand(cognitive, support_present)
            support = "present" if support_present else "absent"
            demand_by_condition[(exp_id, support)] = rows
            curves.extend(condition_curves)
    demand_rows = [
        row for rows in demand_by_condition.values() for row in rows
    ]

    gates = {
        "nine_cognitive_conditions": len(cognitive_by_condition) == 9,
        "eighteen_demand_conditions": len(demand_by_condition) == 18,
        "six_hundred_mechanism_rows_each": all(
            len(rows) == 600 for rows in cognitive_by_condition.values()
        ),
        "scenario_runtime_active": all(
            all(row.get("scenario_schema_version") == "fmcg-scenario-3.2" for row in rows)
            for rows in cognitive_by_condition.values()
        ),
        "legacy_purchase_retired": all(
            row.get("legacy_purchase_endpoint_retired") is True
            for row in cognitive_rows
        ),
        "event_tick_five_only": all(
            row["event_ticks"] == [5] for row in runtime_meta.values()
        ),
        "opportunity_schedule_and_draw_invariant": len(
            {
                tuple(sorted(_schedule_signature(rows).items()))
                for rows in demand_by_condition.values()
            }
        )
        == 1,
        "precrisis_demand_alignment": len(
            {tuple(_pre_signature(rows)) for rows in demand_by_condition.values()}
        )
        == 1,
    }
    result = "PASS" if all(gates.values()) else "FAIL"
    if result == "PASS":
        _write_csv(COGNITIVE_PATH, cognitive_rows)
        _write_csv(DEMAND_PATH, demand_rows)
        _write_csv(CURVE_PATH, curves)
    payload = {
        "schema_version": "fmcg_v32_kernel_fake_smoke_result1.0",
        "result": result,
        "diagnostic_seed": CONTRACT_SEED,
        "cognitive_conditions": len(cognitive_by_condition),
        "demand_conditions": len(demand_by_condition),
        "cognitive_rows": len(cognitive_rows),
        "demand_opportunity_rows": len(demand_rows),
        "fake_semantic_calls": sum(
            row["fake_router_calls"] for row in runtime_meta.values()
        ),
        "real_llm_calls": 0,
        "external_api_calls": 0,
        "p_values_computed": False,
        "formal_reuse_forbidden": True,
        "engineering_pilot_authorized": False,
        "gates": gates,
        "runtime_meta": runtime_meta,
    }
    RESULT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, sort_keys=True))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
