"""Zero-API tests for the v3.3.1 finite-horizon experiment design."""
from __future__ import annotations

from pathlib import Path

import pytest

from greenconsumer_v33.cli import build_parser
from greenconsumer_v33.config import (
    DEFAULT_TOTAL_TICKS,
    HORIZON_ROBUSTNESS_TICKS,
    RunSettings,
    horizon_role,
)


def _settings(total_ticks: int) -> RunSettings:
    return RunSettings(
        llm_mode="fake",
        condition="all",
        simulation_seed=1,
        requested_llm_seed=2,
        demand_seed=3,
        output_dir=Path("results/v33_runs"),
        total_ticks=total_ticks,
    )


def test_baseline_horizon_is_35_ticks():
    assert DEFAULT_TOTAL_TICKS == 35
    assert HORIZON_ROBUSTNESS_TICKS == (30, 35, 40)
    assert horizon_role(35) == "baseline-primary-horizon"
    assert horizon_role(30) == "horizon-robustness"
    assert horizon_role(40) == "horizon-robustness"


def test_only_pre_specified_horizons_are_accepted():
    for value in HORIZON_ROBUSTNESS_TICKS:
        _settings(value).validate()

    with pytest.raises(ValueError):
        _settings(31).validate()


def test_cli_defaults_to_35_and_exposes_30_35_40_only():
    parser = build_parser()
    args = parser.parse_args(["pipeline", "--llm", "fake", "--condition", "all"])
    assert args.total_ticks == 35

    for value in (30, 35, 40):
        args = parser.parse_args(
            ["pipeline", "--llm", "fake", "--condition", "all", "--total-ticks", str(value)]
        )
        assert args.total_ticks == value
