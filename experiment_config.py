"""Experiment matrix configuration for TASK_003."""

from dataclasses import asdict, dataclass
from itertools import product
from typing import List, Optional


EXPERIMENT_MATRIX_VERSION = "3.0"

NOT_APPLICABLE = "not-applicable"

CONTENT_LEVELS = ("rational-evidence", "emotional-empathy")
CHANNEL_LEVELS = ("hub", "random")
STRATEGY_TIMING_LEVELS = ("immediate", "delayed")
CONTROL_TIMING = "no-clarification"
CONTROL_EXP_ID = "NoClarification-Control"

VALID_CONTENT_FACTORS = set(CONTENT_LEVELS) | {NOT_APPLICABLE}
VALID_CHANNEL_FACTORS = set(CHANNEL_LEVELS) | {NOT_APPLICABLE}
VALID_TIMING_FACTORS = set(STRATEGY_TIMING_LEVELS) | {CONTROL_TIMING}

IMMEDIATE_OFFSET_TICKS = 1
DELAYED_OFFSET_TICKS = 5

CONTENT_ID_TOKEN = {
    "rational-evidence": "Rational",
    "emotional-empathy": "Empathy",
}
CHANNEL_ID_TOKEN = {
    "hub": "Hub",
    "random": "Random",
}
TIMING_ID_TOKEN = {
    "immediate": "Immediate",
    "delayed": "Delayed",
}

assert all(not any(ch.isdigit() for ch in lv) for lv in STRATEGY_TIMING_LEVELS)
assert NOT_APPLICABLE == "not-applicable" and "_" not in NOT_APPLICABLE
assert NOT_APPLICABLE not in (
    set(CONTENT_LEVELS) | set(CHANNEL_LEVELS) | set(STRATEGY_TIMING_LEVELS) | {CONTROL_TIMING}
)
assert not any(tok in CONTROL_EXP_ID for tok in ("Rational", "Empathy", "Hub", "Random"))


@dataclass(frozen=True)
class ExperimentConfig:
    """Immutable configuration for one matrix condition."""

    content_factor: str
    channel_factor: str
    timing_factor: str

    budget_k: int = 3
    random_seed: int = 42
    num_agents: int = 20
    total_ticks: int = 30
    scandal_tick: int = 5

    def __post_init__(self):
        if self.content_factor not in VALID_CONTENT_FACTORS:
            raise ValueError(
                f"content_factor must be one of {VALID_CONTENT_FACTORS}, got {self.content_factor!r}"
            )
        if self.channel_factor not in VALID_CHANNEL_FACTORS:
            raise ValueError(
                f"channel_factor must be one of {VALID_CHANNEL_FACTORS}, got {self.channel_factor!r}"
            )
        if self.timing_factor not in VALID_TIMING_FACTORS:
            raise ValueError(
                f"timing_factor must be one of {VALID_TIMING_FACTORS}, got {self.timing_factor!r}"
            )
        if self.num_agents <= 0:
            raise ValueError(f"num_agents must be > 0, got {self.num_agents}")
        if self.total_ticks <= 0:
            raise ValueError(f"total_ticks must be > 0, got {self.total_ticks}")
        if self.budget_k < 0:
            raise ValueError(f"budget_k must be >= 0, got {self.budget_k}")

        if self.is_control:
            if self.content_factor != NOT_APPLICABLE:
                raise ValueError("control content_factor must be not-applicable")
            if self.channel_factor != NOT_APPLICABLE:
                raise ValueError("control channel_factor must be not-applicable")
            if self.budget_k != 0:
                raise ValueError("control budget_k must be 0")
        else:
            if self.content_factor not in CONTENT_LEVELS:
                raise ValueError("strategy content_factor must be a real content level")
            if self.channel_factor not in CHANNEL_LEVELS:
                raise ValueError("strategy channel_factor must be a real channel level")
            if self.budget_k <= 0:
                raise ValueError("strategy budget_k must be > 0")

        if self.clarification_tick is not None:
            if not (self.scandal_tick < self.clarification_tick <= self.total_ticks):
                raise ValueError(
                    "clarification_tick must be after scandal_tick and within total_ticks"
                )

    @property
    def is_control(self) -> bool:
        return self.timing_factor == CONTROL_TIMING

    @property
    def exp_id(self) -> str:
        if self.is_control:
            return CONTROL_EXP_ID
        return (
            f"{CONTENT_ID_TOKEN[self.content_factor]}-"
            f"{CHANNEL_ID_TOKEN[self.channel_factor]}-"
            f"{TIMING_ID_TOKEN[self.timing_factor]}"
        )

    @property
    def clarification_tick(self) -> Optional[int]:
        if self.timing_factor == "immediate":
            return self.scandal_tick + IMMEDIATE_OFFSET_TICKS
        if self.timing_factor == "delayed":
            return self.scandal_tick + DELAYED_OFFSET_TICKS
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["exp_id"] = self.exp_id
        d["is_control"] = self.is_control
        d["clarification_tick"] = self.clarification_tick
        return d


def generate_experiment_matrix() -> List[ExperimentConfig]:
    """Generate the 8 strategy conditions plus the single common control."""
    configs = [
        ExperimentConfig(content_factor=content, channel_factor=channel, timing_factor=timing)
        for content, channel, timing in product(
            CONTENT_LEVELS, CHANNEL_LEVELS, STRATEGY_TIMING_LEVELS
        )
    ]
    configs.append(
        ExperimentConfig(
            content_factor=NOT_APPLICABLE,
            channel_factor=NOT_APPLICABLE,
            timing_factor=CONTROL_TIMING,
            budget_k=0,
        )
    )
    assert len(configs) == 9
    assert len({c.exp_id for c in configs}) == 9
    assert sum(1 for c in configs if c.is_control) == 1
    return configs


if __name__ == "__main__":
    matrix = generate_experiment_matrix()
    print(f"Experiment matrix v{EXPERIMENT_MATRIX_VERSION}: {len(matrix)} conditions")
    for i, cfg in enumerate(matrix, 1):
        print(f"  [{i:2d}] {cfg.exp_id:30s} | clarification_tick={cfg.clarification_tick}")
