"""v3.3.1 experiment-design configuration.

This module intentionally separates the current v3.3.1 experiment design from
``greenconsumer_v32.config`` so the closed v3.2/F001-F010 workflow keeps its
30-Tick historical defaults unchanged.

The scientific mechanism is unchanged here. The baseline finite horizon is 35
Ticks (30 post-crisis days after T5). Prompt robustness profiles are explicit
engineering probes; ``baseline_exact`` remains the frozen scientific prompt.
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
from .prompt_profiles import BASELINE_PROMPT_PROFILE, PROMPT_PROFILES

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
    network mechanism coefficient. Prompt profiles are limited to a pre-
    specified set. Non-baseline prompt profiles are Real-LLM robustness probes,
    not alternative production prompts.
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
    prompt_profile: str = BASELINE_PROMPT_PROFILE

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
        if self.prompt_profile not in PROMPT_PROFILES:
            raise ValueError(
                f"prompt_profile must be one of {PROMPT_PROFILES}; got {self.prompt_profile}"
            )
        if self.llm_mode == "fake" and self.prompt_profile != BASELINE_PROMPT_PROFILE:
            raise ValueError(
                "non-baseline prompt profiles are reserved for Real-LLM robustness; "
                "Fake routing would test fixture parsing rather than LLM prompt sensitivity"
            )
        if self.llm_mode == "real" and not self.allow_real_llm:
            raise ValueError(
                "real LLM execution requires --allow-real-llm; "
                "this is an engineering/demo run, not a new formal replication"
            )
