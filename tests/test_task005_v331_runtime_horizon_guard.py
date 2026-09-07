"""Pure zero-I/O regression tests for the v3.3.1 runtime horizon guard.

These tests intentionally do not import ``simulation_core``.  Importing the full
AgentKernel runtime can initialize embedding/Hugging Face clients and therefore
turn a guard unit test into a network/client-lifecycle integration test.  The
runtime itself calls the same pure validator before any heavy imports.
"""
from __future__ import annotations

import dataclasses

import pytest

from experiment_config import generate_experiment_matrix
from task005_fmcg_runtime_v33 import _validate_runtime_config_v331


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
        _validate_runtime_config_v331(_config(31), override_router=object())


@pytest.mark.parametrize("total_ticks", [30, 35, 40])
def test_runtime_accepts_pre_specified_horizon_grid(total_ticks):
    result = _validate_runtime_config_v331(
        _config(total_ticks),
        override_router=object(),
    )
    assert result["runtime_total_ticks"] == total_ticks
    assert result["runtime_horizon_grid"] == [30, 35, 40]
    assert result["runtime_num_agents"] == 20
    assert result["runtime_crisis_tick"] == 5


def test_runtime_rejects_missing_version_scoped_router():
    with pytest.raises(ValueError, match="explicit version-scoped router"):
        _validate_runtime_config_v331(_config(35), override_router=None)


def test_runtime_rejects_wrong_agent_count():
    cfg = dataclasses.replace(_config(35), num_agents=21)
    with pytest.raises(ValueError, match="20 cognitive agents"):
        _validate_runtime_config_v331(cfg, override_router=object())


def test_runtime_rejects_wrong_crisis_tick():
    cfg = dataclasses.replace(_config(35), scandal_tick=6)
    with pytest.raises(ValueError, match="crisis Tick 5"):
        _validate_runtime_config_v331(cfg, override_router=object())
