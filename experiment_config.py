"""
experiment_config.py — 实验配置定义模块

定义三因子实验空间（内容×渠道×时机），生成 2×2×3=12 个实验配置。
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from itertools import product

# 合法因子水平
VALID_CONTENT_FACTORS = {"rational-evidence", "emotional-empathy"}
VALID_CHANNEL_FACTORS = {"hub", "random"}
VALID_TIMING_FACTORS  = {"immediate", "delay-3", "no-clarification"}


@dataclass(frozen=True)
class ExperimentConfig:
    """单次实验运行的完整配置（不可变）"""

    # ── 因子水平 ─────────────────────────────────────────────────────
    content_factor: str      # "rational-evidence" | "emotional-empathy"
    channel_factor: str      # "hub" | "random"
    timing_factor: str       # "immediate" | "delay-3" | "no-clarification"

    # ── 固定参数 ─────────────────────────────────────────────────────
    budget_k: int = 3        # 每次澄清投放的目标节点数
    random_seed: int = 42
    num_agents: int = 10     # 快速迭代阶段 10 个，生产阶段可调为 50
    total_ticks: int = 30
    scandal_tick: int = 5    # 丑闻爆发 Tick（对应 ENTERPRISE_STRATEGY 中的黑石事件）

    def __post_init__(self):
        """字段验证"""
        if self.content_factor not in VALID_CONTENT_FACTORS:
            raise ValueError(
                f"content_factor must be one of {VALID_CONTENT_FACTORS}, got '{self.content_factor}'"
            )
        if self.channel_factor not in VALID_CHANNEL_FACTORS:
            raise ValueError(
                f"channel_factor must be one of {VALID_CHANNEL_FACTORS}, got '{self.channel_factor}'"
            )
        if self.timing_factor not in VALID_TIMING_FACTORS:
            raise ValueError(
                f"timing_factor must be one of {VALID_TIMING_FACTORS}, got '{self.timing_factor}'"
            )
        if self.num_agents <= 0:
            raise ValueError(f"num_agents must be > 0, got {self.num_agents}")
        if self.total_ticks <= 0:
            raise ValueError(f"total_ticks must be > 0, got {self.total_ticks}")

    @property
    def exp_id(self) -> str:
        """唯一实验标识符，如 'Rational-Hub-Imm'"""
        content_short = "Rational" if self.content_factor == "rational-evidence" else "Empathy"
        channel_short = "Hub" if self.channel_factor == "hub" else "Random"
        timing_map = {"immediate": "Imm", "delay-3": "D3", "no-clarification": "NoClr"}
        timing_short = timing_map[self.timing_factor]
        return f"{content_short}-{channel_short}-{timing_short}"

    @property
    def clarification_tick(self) -> Optional[int]:
        """澄清注入的 Tick，None 表示不澄清

        时机定义（相对于丑闻爆发 Tick）：
          - immediate:        丑闻次日（scandal_tick + 1）
          - delay-3:          丑闻后第 4 天（scandal_tick + 3）
          - no-clarification: 不澄清
        """
        if self.timing_factor == "immediate":
            return self.scandal_tick + 1   # 次日即刻响应
        elif self.timing_factor == "delay-3":
            return self.scandal_tick + 3
        return None

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 存档）"""
        d = asdict(self)
        d["exp_id"] = self.exp_id
        d["clarification_tick"] = self.clarification_tick
        return d


def generate_experiment_matrix() -> List[ExperimentConfig]:
    """
    生成完整的因子实验矩阵。

    2（内容）× 2（渠道）× 3（时机）= 12 个配置。
    """
    content_levels = ["rational-evidence", "emotional-empathy"]
    channel_levels = ["hub", "random"]
    timing_levels  = ["immediate", "delay-3", "no-clarification"]

    configs = []
    for content, channel, timing in product(content_levels, channel_levels, timing_levels):
        configs.append(ExperimentConfig(
            content_factor=content,
            channel_factor=channel,
            timing_factor=timing,
        ))
    return configs


if __name__ == "__main__":
    # 快速验证
    matrix = generate_experiment_matrix()
    print(f"实验矩阵共 {len(matrix)} 组：")
    for i, cfg in enumerate(matrix, 1):
        print(f"  [{i:2d}] {cfg.exp_id:20s} | clarification_tick={cfg.clarification_tick}")
