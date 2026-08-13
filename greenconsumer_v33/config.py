"""v3.3.1 experiment-design configuration.

This module intentionally separates the current v3.3.1 experiment design from
``greenconsumer_v32.config`` so the closed v3.2/F001-F010 workflow keeps its
30-Tick historical defaults unchanged.

The scientific mechanism is unchanged here.  The only new baseline design
choice is a 35-Tick finite observation horizon, interpreted as 30 post-crisis
days because the common crisis occurs at Tick 5.  Tick 30 and Tick 40 are
pre-specified horizon-robustness checks rather than alternative tuned endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from greenconsumer_v32.config import (
    CONDITION_ORDER,
    DEFAULT_DEMAND_SEED,
    DEFAULT_LLM_SEED,
    DEFAULT_SIMULATION_SEED,
    PROJECT_ROOT,
)

DEFAULT_NUM_AGENTS = 20
DEFAULT_MICRO_BUYERS = 25
DEFAULT_CRISIS_TICK = 5

# Finite-horizon design frozen before new formal v3.3.1 outcomes.
DEFAULT_TOTAL_TICKS = 35
HORIZON_ROBUSTNESS_TICKS = (30, 35, 40)
TIME_UNIT = "day"


def horizon_role(total_ticks: int) -> str:
    """Return the pre-specified inferential role of one observation horizon."""

    value = int(total_ticks)
    if value == DEFAULT_TOTAL_TICKS:
        return "baseline-primary-horizon"
    if value in HORIZON_ROBUSTNESS_TICKS:
        return "horizon-robustness"
    return "outside-pre-specified-horizon-grid"


@dataclass(frozen=True)
class RunSettings:
    """Immutable v3.3.1 engineering/demo settings.

    ``total_ticks`` is an experiment-design parameter, not a psychological or
    network mechanism coefficient.  During the current freeze stage it is
    restricted to the pre-specified 30/35/40 horizon grid so endpoints cannot
    be changed after inspecting results.
    """

    llm_mode: str
    condition: str
    simulation_seed: int
    requested_llm_seed: int
    demand_seed: int
    output_dir: Path
    run_demand: bool = True
    support_mode: str = "both"
    allow_real_llm: bool = False
    total_ticks: int = DEFAULT_TOTAL_TICKS

    def validate(self) -> None:
        if self.llm_mode not in {"fake", "real"}:
            raise ValueError("llm_mode must be fake or real")
        if self.condition not in {"all", *CONDITION_ORDER}:
            raise ValueError(f"unknown condition: {self.condition}")
        if self.support_mode not in {"absent", "present", "both"}:
            raise ValueError("support_mode must be absent, present, or both")
        if int(self.total_ticks) not in HORIZON_ROBUSTNESS_TICKS:
            raise ValueError(
                "total_ticks must be one of the pre-specified horizon values: "
                f"{HORIZON_ROBUSTNESS_TICKS}"
            )
        if int(self.total_ticks) <= DEFAULT_CRISIS_TICK:
            raise ValueError("total_ticks must extend beyond the crisis Tick")
        if self.llm_mode == "real" and not self.allow_real_llm:
            raise ValueError(
                "real LLM execution requires --allow-real-llm; "
                "this is an engineering/demo run, not a new formal replication"
            )
