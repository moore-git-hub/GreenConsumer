"""
metrics_calculator.py — 三目标评估指标计算

从逐 Tick 的信任轨迹和转化率轨迹计算：
  1. T80（速度）：信任从最低点恢复到基线 80% 所需 Tick 数
  2. Steady_State_Score（稳态）：Tick 30 最终平均信任分
  3. Recovery_Rate（修复率）：转化率恢复程度
"""
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class SimulationMetrics:
    """单次仿真运行的三目标评估结果"""

    # ── 核心三目标 ────────────────────────────────────────────────────
    t80: int                    # 恢复到基线 80% 的 Tick 数（越小越好）
    steady_state_score: float   # Tick 30 最终平均信任（越高越好）
    recovery_rate: float        # 转化率恢复程度（越高越好）

    # ── 辅助诊断信息 ──────────────────────────────────────────────────
    trust_min: float            # 信任最低点
    trust_min_tick: int         # 最低点所在 Tick（1-indexed）
    baseline_trust: float       # 丑闻前基线信任（Tick 4 的平均信任）

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metrics(
    trust_trajectory: List[float],
    conversion_trajectory: List[float],
    scandal_tick: int = 5,
    total_ticks: int = 30,
) -> SimulationMetrics:
    """
    从逐 Tick 的信任和转化率轨迹计算三目标指标。

    Args:
        trust_trajectory: 长度为 total_ticks 的平均信任分列表
                          index 0 对应 Tick 1，index 29 对应 Tick 30
        conversion_trajectory: 长度为 total_ticks 的累计转化率列表（0.0~1.0）
        scandal_tick: 丑闻爆发 Tick（1-indexed），默认 5
        total_ticks: 总 Tick 数，默认 30

    Returns:
        SimulationMetrics 实例
    """
    assert len(trust_trajectory) == total_ticks, \
        f"trust_trajectory length {len(trust_trajectory)} != total_ticks {total_ticks}"
    assert len(conversion_trajectory) == total_ticks, \
        f"conversion_trajectory length {len(conversion_trajectory)} != total_ticks {total_ticks}"

    # ── 1. 基线信任：丑闻前一 Tick（Tick 4 → index 3） ────────────────
    baseline_idx = scandal_tick - 2  # Tick 4 → index 3
    if baseline_idx < 0:
        baseline_idx = 0
    baseline_trust = trust_trajectory[baseline_idx]

    # ── 2. 信任最低点（丑闻后） ──────────────────────────────────────
    post_scandal_start = scandal_tick - 1  # Tick 5 → index 4
    post_scandal_values = trust_trajectory[post_scandal_start:]

    if not post_scandal_values:
        # 边界情况：丑闻在最后一个 Tick
        trust_min = trust_trajectory[-1]
        trust_min_tick = total_ticks
    else:
        trust_min = min(post_scandal_values)
        # 在完整轨迹中找到最低点的 index
        trust_min_idx = post_scandal_start + post_scandal_values.index(trust_min)
        trust_min_tick = trust_min_idx + 1  # 转为 1-indexed

    # ── 3. T80：从最低点恢复到基线 80% 的时间 ─────────────────────────
    target_trust = baseline_trust * 0.8
    t80 = total_ticks  # 默认：未恢复（censored value）

    trust_min_idx = trust_min_tick - 1  # 转回 0-indexed
    for i in range(trust_min_idx, total_ticks):
        if trust_trajectory[i] >= target_trust:
            t80 = (i + 1) - trust_min_tick  # 从最低点算起的 Tick 数
            if t80 <= 0:
                t80 = 1  # 最低点本身就达标，记为 1
            break

    # ── 4. 稳态信任：Tick 30 的平均信任 ──────────────────────────────
    steady_state_score = trust_trajectory[-1]

    # ── 5. 修复率：Tick 30 转化率 / 丑闻前峰值转化率 ──────────────────
    pre_scandal_conversions = conversion_trajectory[:scandal_tick - 1]
    pre_scandal_peak = max(pre_scandal_conversions) if pre_scandal_conversions else 0.0
    final_conversion = conversion_trajectory[-1]

    if pre_scandal_peak > 0:
        recovery_rate = final_conversion / pre_scandal_peak
    else:
        # 丑闻前无人购买，修复率定义为最终转化率本身
        recovery_rate = final_conversion

    # Cap at 2.0（防止极端值影响帕累托分析）
    recovery_rate = min(recovery_rate, 2.0)

    return SimulationMetrics(
        t80=t80,
        steady_state_score=round(steady_state_score, 3),
        recovery_rate=round(recovery_rate, 3),
        trust_min=round(trust_min, 3),
        trust_min_tick=trust_min_tick,
        baseline_trust=round(baseline_trust, 3),
    )


if __name__ == "__main__":
    # 快速验证：模拟一条信任轨迹
    import math

    # 模拟：Tick 1-4 信任 7.0，Tick 5 跌至 3.0，之后指数恢复
    trajectory = []
    for t in range(1, 31):
        if t <= 4:
            trajectory.append(7.0)
        elif t == 5:
            trajectory.append(3.0)
        else:
            # 指数恢复：3.0 + (7.0-3.0) * (1 - exp(-0.15*(t-5)))
            recovery = 3.0 + 4.0 * (1 - math.exp(-0.15 * (t - 5)))
            trajectory.append(recovery)

    # 模拟转化率：前 4 Tick 线性增长，丑闻后停滞
    conversion = [i * 0.1 for i in range(1, 5)] + [0.4] * 26

    metrics = compute_metrics(trajectory, conversion, scandal_tick=5, total_ticks=30)
    print(f"T80 = {metrics.t80} ticks")
    print(f"Steady State = {metrics.steady_state_score}")
    print(f"Recovery Rate = {metrics.recovery_rate}")
    print(f"Trust Min = {metrics.trust_min} at Tick {metrics.trust_min_tick}")
    print(f"Baseline Trust = {metrics.baseline_trust}")
