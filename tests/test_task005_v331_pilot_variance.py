"""Zero-API contract tests for TASK-PV01 Pilot variance infrastructure."""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd

from greenconsumer_v33.pilot_variance import (
    CONFIRMATORY_ESTIMANDS,
    DEMAND_SEEDS,
    LLM_SEEDS,
    P1,
    P2,
    P5,
    PILOT_LLM_MODEL,
    SIMULATION_SEEDS,
    ProviderCallBudgetExceeded,
    WallClockBudgetExceeded,
    _ProviderCallBudget,
    _holm_rejections,
    demand_seed_table,
    operating_characteristics,
    plan_payload,
    planning_sd_table,
    profile_table,
    three_way_variance_components,
    two_way_variance_components,
    validate_execution_budget,
    variance_component_table,
)
from greenconsumer_v32.routers import RecordingRouter, ReplayRouter, prompt_key


def _synthetic_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    block_rows = []
    demand_rows = []
    for _, profile in profile_table().iterrows():
        s = int(profile["simulation_network_seed"]) - SIMULATION_SEEDS[0]
        l = int(profile["requested_llm_seed"]) - LLM_SEEDS[0]
        common = {
            "pilot_id": profile["pilot_id"],
            "simulation_network_seed": int(profile["simulation_network_seed"]),
            "requested_llm_seed": int(profile["requested_llm_seed"]),
        }
        block_rows.extend(
            [
                {**common, "estimand_id": P1, "value": 0.20 + 0.02 * s + 0.03 * l + 0.005 * s * l},
                {**common, "estimand_id": P2, "value": -0.10 + 0.01 * s - 0.02 * l + 0.003 * s * l},
            ]
        )
        for demand_seed in DEMAND_SEEDS:
            d = demand_seed - DEMAND_SEEDS[0]
            demand_rows.append(
                {
                    **common,
                    "estimand_id": P5,
                    "demand_seed": demand_seed,
                    "value": 0.04 + 0.01 * s + 0.02 * l + 0.03 * d + 0.002 * s * l * d,
                }
            )
    return pd.DataFrame(block_rows), pd.DataFrame(demand_rows)


def test_frozen_seed_grid_is_exact() -> None:
    profiles = profile_table()
    assert profiles["pilot_id"].tolist() == [f"P{i:03d}" for i in range(1, 7)]
    assert profiles[["simulation_network_seed", "requested_llm_seed"]].to_records(index=False).tolist() == [
        (2026081501, 2026081601),
        (2026081501, 2026081602),
        (2026081502, 2026081601),
        (2026081502, 2026081602),
        (2026081503, 2026081601),
        (2026081503, 2026081602),
    ]
    assert demand_seed_table()["demand_seed"].tolist() == [2026081701, 2026081702, 2026081703]


def test_plan_only_is_explicitly_nonexecuting() -> None:
    payload = plan_payload(
        n_max=40,
        provider_call_ceiling=10_000,
        max_wall_clock_hours=2.0,
    )
    assert payload["status"] == "PLAN_ONLY"
    assert payload["real_llm_calls_started"] is False
    assert payload["pilot_executed"] is False
    assert payload["formal_experiment_started"] is False
    assert payload["formal_inference_performed"] is False
    assert payload["execution_authorized"] is False
    assert payload["cognitive_blocks"] == 6
    assert payload["p5_demand_realizations"] == 18
    assert payload["max_wall_clock_hours"] == 2.0
    assert payload["llm_model"] == "qwen-plus-2025-12-01"


def test_execution_caps_fail_closed() -> None:
    for n_max, ceiling, hours in (
        (9, 100, 2.0),
        (10, 0, 2.0),
        (10, -1, 2.0),
        (10, 100, 0.0),
        (10, 100, float("inf")),
    ):
        try:
            validate_execution_budget(n_max, ceiling, hours)
        except ValueError:
            pass
        else:
            raise AssertionError((n_max, ceiling, hours))
    validate_execution_budget(10, 1, 0.01)


def test_plan_caps_must_be_supplied_together() -> None:
    partials = (
        {"n_max": 10},
        {"provider_call_ceiling": 1200},
        {"max_wall_clock_hours": 2.0},
        {"n_max": 10, "provider_call_ceiling": 1200},
    )
    for kwargs in partials:
        try:
            plan_payload(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(kwargs)


def test_wall_clock_budget_blocks_before_late_provider_call() -> None:
    now = [100.0]
    budget = _ProviderCallBudget(
        10,
        max_wall_clock_hours=1.0,
        clock=lambda: now[0],
    )
    budget.reserve()
    assert budget.calls_attempted == 1
    now[0] += 3600.0
    try:
        budget.reserve()
    except WallClockBudgetExceeded:
        pass
    else:
        raise AssertionError("wall-clock ceiling did not stop the late call")
    assert budget.calls_attempted == 1


def test_provider_budget_blocks_before_excess_call() -> None:
    class Inner:
        def __init__(self):
            self.calls = 0

        async def chat(self, prompt: str) -> str:
            self.calls += 1
            return prompt

    inner = Inner()
    budget = _ProviderCallBudget(1)
    router = RecordingRouter(inner, before_provider_call=budget.reserve)
    assert asyncio.run(router.chat("first")) == "first"
    try:
        asyncio.run(router.chat("blocked"))
    except ProviderCallBudgetExceeded:
        pass
    else:
        raise AssertionError("provider ceiling did not stop the second call")
    assert inner.calls == 1
    assert budget.calls_attempted == 1


def test_replay_hits_do_not_consume_provider_budget() -> None:
    class Inner:
        def __init__(self):
            self.calls = 0

        async def chat(self, prompt: str) -> str:
            self.calls += 1
            return "provider"

    prompt = "same prompt"
    cache = {(prompt_key(prompt), 5, 0): "replayed"}
    inner = Inner()
    budget = _ProviderCallBudget(1)
    router = ReplayRouter(
        inner,
        cache,
        replay_until=10,
        before_provider_call=budget.reserve,
    )
    router.set_tick(5)
    assert asyncio.run(router.chat(prompt)) == "replayed"
    assert budget.calls_attempted == 0
    assert inner.calls == 0

    router.set_tick(10)
    assert asyncio.run(router.chat(prompt)) == "provider"
    assert budget.calls_attempted == 1
    assert inner.calls == 1


def test_two_way_components_are_complete_and_nonnegative_after_bounding() -> None:
    block, _ = _synthetic_inputs()
    table = two_way_variance_components(block[block["estimand_id"] == P1])
    assert table["component"].tolist() == [
        "simulation_network",
        "requested_llm_provider",
        "interaction_unresolved_runtime",
    ]
    assert (table["bounded_variance_component"] >= 0).all()
    assert "confounded" in table["warning"].iloc[0]


def test_three_way_components_are_complete_and_nonnegative_after_bounding() -> None:
    _, demand = _synthetic_inputs()
    table = three_way_variance_components(demand)
    assert len(table) == 7
    assert set(table["component"]) == {
        "simulation_network",
        "requested_llm_provider",
        "offline_demand",
        "simulation_x_llm",
        "simulation_x_demand",
        "llm_x_demand",
        "three_way_unresolved",
    }
    assert (table["bounded_variance_component"] >= 0).all()


def test_planning_sd_is_conservative_and_does_not_use_pilot_mean() -> None:
    block, demand = _synthetic_inputs()
    components = variance_component_table(block, demand)
    planning = planning_sd_table(block, demand, components)
    assert planning["estimand_id"].tolist() == list(CONFIRMATORY_ESTIMANDS)
    assert planning["pilot_mean_used"].eq(False).all()
    assert planning["status"].eq("PASS").all()
    assert (planning["planning_variance"] >= planning["raw_block_variance"]).all()
    p5 = planning.set_index("estimand_id").loc[P5]
    assert p5["planning_variance"] >= p5["component_sum_variance"]


def test_zero_variance_is_unresolved_not_modified() -> None:
    block, demand = _synthetic_inputs()
    block["value"] = 0.0
    demand["value"] = 0.0
    components = variance_component_table(block, demand)
    planning = planning_sd_table(block, demand, components)
    assert planning["status"].eq("VARIANCE_ZERO_UNRESOLVED").all()
    assert planning["planning_sd"].eq(0.0).all()


def test_holm_step_down_stops_after_first_failure() -> None:
    p = np.array(
        [
            [0.010, 0.020, 0.040],
            [0.020, 0.001, 0.002],
            [0.001, 0.030, 0.040],
        ]
    )
    observed = _holm_rejections(p)
    assert observed.tolist() == [
        [True, True, True],
        [True, True, True],
        [True, False, False],
    ]


def test_operating_characteristics_are_deterministic_and_mean_free() -> None:
    block, demand = _synthetic_inputs()
    components = variance_component_table(block, demand)
    planning = planning_sd_table(block, demand, components)
    correlation = np.eye(3)
    first, first_n = operating_characteristics(
        planning, correlation, n_max=10, replications=1_000, random_seed=123
    )
    second, second_n = operating_characteristics(
        planning, correlation, n_max=10, replications=1_000, random_seed=123
    )
    pd.testing.assert_frame_equal(first, second)
    assert first_n == second_n
    assert first["pilot_mean_used"].eq(False).all()
    assert len(first) == 5 * 3


def test_zero_api_module_has_no_top_level_runner_or_agentkernel_import() -> None:
    path = Path(__file__).parents[1] / "greenconsumer_v33" / "pilot_variance.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top_level = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_level.append(node.module or "")
    assert "greenconsumer_v33.runner" not in top_level
    assert "greenconsumer_v32.routers" not in top_level
    assert not any(name.startswith("agentkernel") for name in top_level)


def test_pilot_does_not_monkeypatch_runner_router_builder() -> None:
    path = Path(__file__).parents[1] / "greenconsumer_v33" / "pilot_variance.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assigned_attributes = {
        node.attr
        for item in ast.walk(tree)
        if isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign))
        for node in (
            item.targets
            if isinstance(item, ast.Assign)
            else [item.target]
        )
        if isinstance(node, ast.Attribute)
    }
    assert "build_inner_router" not in assigned_attributes


def test_machine_contract_matches_code_constants() -> None:
    path = (
        Path(__file__).parents[1]
        / "docs"
        / "architecture"
        / "task_pv01_pilot_variance_contract1.0.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    code_profiles = profile_table()[
        ["pilot_id", "requested_llm_seed", "simulation_network_seed"]
    ].to_dict(orient="records")
    assert payload["pilot_profiles"] == code_profiles
    assert [row["demand_seed"] for row in payload["demand_seeds"]] == list(DEMAND_SEEDS)
    assert payload["analysis"]["confirmatory_estimands"] == list(CONFIRMATORY_ESTIMANDS)
    assert payload["execution"]["pilot_execution_authorized"] is False
    assert payload["execution"]["formal_execution_authorized"] is False
    assert payload["execution"]["max_wall_clock_hours_required_before_pilot"] is True


def test_v331_model_is_dated_and_v32_model_path_is_unchanged() -> None:
    root = Path(__file__).parents[1]
    contract_path = (
        root
        / "docs"
        / "architecture"
        / "task_pv01_pilot_variance_contract1.0.json"
    )
    payload = json.loads(contract_path.read_text(encoding="utf-8"))

    def assigned_string(path: Path, name: str) -> str:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if any(
                    isinstance(target, ast.Name) and target.id == name
                    for target in node.targets
                ):
                    assert isinstance(node.value, ast.Constant)
                    return str(node.value.value)
        raise AssertionError(f"{name} assignment not found in {path}")

    v33_runner = root / "greenconsumer_v33" / "runner.py"
    v32_runner = root / "greenconsumer_v32" / "runner.py"
    assert assigned_string(v33_runner, "MODEL") == "qwen-plus-2025-12-01"
    assert assigned_string(v32_runner, "MODEL") == "qwen-plus"

    source = v33_runner.read_text(encoding="utf-8")
    assert "model_override=MODEL" in source
    shared_config = (root / "configs" / "models_config.yaml").read_text(
        encoding="utf-8-sig"
    )
    assert "model: qwen-plus" in shared_config
    assert payload["frozen_model"]["llm_model"] == "qwen-plus-2025-12-01"
    assert PILOT_LLM_MODEL == payload["frozen_model"]["llm_model"]
    assert payload["execution"]["n_max"] == 10
    assert payload["execution"]["provider_call_ceiling"] == 1200
    assert payload["execution"]["max_wall_clock_hours"] == 2.0
