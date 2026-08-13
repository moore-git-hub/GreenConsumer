"""Zero-API regression tests for the v3.3.1 runtime horizon guard."""
from __future__ import annotations

import asyncio
import dataclasses

import pytest

from experiment_config import generate_experiment_matrix
from task005_fmcg_runtime_v33 import run_scenario_v33


def _config(total_ticks: int):
    base = generate_experiment_matrix()[0]
    return dataclasses.replace(
        base,
        num_agents=20,
        total_ticks=int(total_ticks),
        scandal_tick=5,
    )


def test_runtime_rejects_horizon_outside_pre_specified_grid():
    with pytest.raises(ValueError, match="pre-specified horizon grid"):
        asyncio.run(run_scenario_v33(_config(31), override_router=object()))


def test_runtime_accepts_t35_before_entering_simulation(monkeypatch):
    """Regression for the stale legacy guard that previously required T30."""

    import simulation_core

    async def fake_run_simulation_core(config, *, override_router):
        assert int(config.total_ticks) == 35
        assert override_router is not None
        return {}

    monkeypatch.setattr(simulation_core, "run_simulation_core", fake_run_simulation_core)
    result = asyncio.run(run_scenario_v33(_config(35), override_router=object()))
    assert result["runtime_total_ticks"] == 35
    assert result["runtime_horizon_grid"] == [30, 35, 40]


def test_runtime_accepts_t40_before_entering_simulation(monkeypatch):
    import simulation_core

    async def fake_run_simulation_core(config, *, override_router):
        assert int(config.total_ticks) == 40
        return {}

    monkeypatch.setattr(simulation_core, "run_simulation_core", fake_run_simulation_core)
    result = asyncio.run(run_scenario_v33(_config(40), override_router=object()))
    assert result["runtime_total_ticks"] == 40
