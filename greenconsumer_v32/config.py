from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCENARIO_SCHEMA = "fmcg-scenario-3.2"
DEFAULT_NUM_AGENTS = 20
DEFAULT_TOTAL_TICKS = 30
DEFAULT_CRISIS_TICK = 5
DEFAULT_SIMULATION_SEED = 2026081501
DEFAULT_LLM_SEED = 2026081601
DEFAULT_DEMAND_SEED = 2026081701
DEFAULT_MICRO_BUYERS = 25

CONDITION_ORDER = (
    "NoClarification-Control",
    "Rational-Hub-Immediate",
    "Rational-Hub-Delayed",
    "Rational-Random-Immediate",
    "Rational-Random-Delayed",
    "Empathy-Hub-Immediate",
    "Empathy-Hub-Delayed",
    "Empathy-Random-Immediate",
    "Empathy-Random-Delayed",
)

@dataclass(frozen=True)
class RunSettings:
    llm_mode: str
    condition: str
    simulation_seed: int
    requested_llm_seed: int
    demand_seed: int
    output_dir: Path
    run_demand: bool = True
    support_mode: str = "both"
    allow_real_llm: bool = False

    def validate(self) -> None:
        if self.llm_mode not in {"fake", "real"}:
            raise ValueError("llm_mode must be fake or real")
        if self.condition not in {"all", *CONDITION_ORDER}:
            raise ValueError(f"unknown condition: {self.condition}")
        if self.support_mode not in {"absent", "present", "both"}:
            raise ValueError("support_mode must be absent, present, or both")
        if self.llm_mode == "real" and not self.allow_real_llm:
            raise ValueError(
                "real LLM execution requires --allow-real-llm; "
                "this is an engineering/demo run, not a new formal replication"
            )
