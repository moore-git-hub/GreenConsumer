"""统一工作流配置。

这里只放“运行层参数”，不放心理机制系数。心理机制系数仍保留在冻结的
scientific core 中，避免为了工程整理而改变论文模型。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# 仓库根目录。所有输入/输出都相对此目录解析，避免 PyCharm working directory
# 不同导致路径漂移。
PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCENARIO_SCHEMA = "fmcg-scenario-3.2"
DEFAULT_NUM_AGENTS = 20
DEFAULT_TOTAL_TICKS = 30
DEFAULT_CRISIS_TICK = 5

# 以下仅是新的 engineering/demo workflow 默认随机种子。
# 它们不是已完成的 F001-F010 formal seed ledger。
DEFAULT_SIMULATION_SEED = 2026081501
DEFAULT_LLM_SEED = 2026081601
DEFAULT_DEMAND_SEED = 2026081701
DEFAULT_MICRO_BUYERS = 25

# 顺序固定为 control first，再运行 8 个策略条件。
# condition=all 时，control 用于建立 treatment 前 common-history replay cache。
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
    """一次 engineering/demo run 的不可变运行参数。"""

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
        """在任何真实 API 调用发生前验证运行意图。"""
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
