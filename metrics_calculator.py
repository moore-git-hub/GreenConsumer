"""
metrics_calculator.py — 多维评估指标计算

从逐 Tick 的信任轨迹和转化率轨迹计算以下指标：

  ── 核心三目标（高区分度版本）──────────────────────────────────────────
  1. delta_recovery   信任恢复量：Tick 30 信任 - 最低点信任（越大越好）
                      相比 T80/T50，此指标不存在 censoring 问题，所有实验都有值
  2. auc_post_scandal 丑闻后信任曲线面积（Tick 5~30，归一化到满分 10.0）
                      衡量整体恢复过程质量，而非仅看终点
  3. recovery_speed   加速度指标：(Tick 30 信任 - 最低点信任) / (30 - 最低点 Tick)
                      单位"信任分/天"，衡量恢复斜率（速度）

  ── 保留辅助指标（用于论文诊断） ──────────────────────────────────────
  4. steady_state_score  Tick 30 最终平均信任
  5. t50                 半恢复时间（从最低点到恢复 50% 区间，有时会 censored=30）
  6. t80                 全恢复时间（从最低点到基线 80%，大概率 censored）
  7. recovery_rate       转化率修复比

设计原则：
  - 避免 censoring：优先使用"总量/面积"指标，而非"达到门槛的时间"
  - 高区分度：实验组间差异量化到小数点后两位
  - 可解释：每个指标都有清晰的行为/认知意义
"""
from dataclasses import dataclass, asdict, field
from typing import List


@dataclass
class SimulationMetrics:
    """单次仿真运行的多维评估结果"""

    # ── 核心三目标（高区分度，无 censoring 问题）────────────────────────
    delta_recovery: float      # 信任净恢复量 = 最终信任 - 最低点信任（越大越好）
    auc_post_scandal: float    # 丑闻后归一化 AUC（越大越好，满分 1.0）
    recovery_speed: float      # 恢复速度 = delta_recovery / 恢复所用天数（越大越好）

    # ── 保留辅助指标 ─────────────────────────────────────────────────────
    t80: int                   # 恢复到基线 80% 的 Tick 数（可能 censored）
    t50: int                   # 半恢复时间（可能 censored）
    steady_state_score: float  # Tick 30 最终平均信任
    recovery_rate: float       # 转化率修复比

    # ── 诊断信息 ─────────────────────────────────────────────────────────
    trust_min: float           # 信任最低点
    trust_min_tick: int        # 最低点所在 Tick（1-indexed）
    baseline_trust: float      # 丑闻前基线信任（Tick 4）
    clarification_effect: float  # 澄清注入后的信任变化量（诊断用）

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metrics(
    trust_trajectory: List[float],
    conversion_trajectory: List[float],
    scandal_tick: int = 5,
    total_ticks: int = 30,
    clarification_tick: int = None,  # 新增：用于诊断澄清效果
) -> SimulationMetrics:
    """
    从逐 Tick 的信任和转化率轨迹计算多维指标。

    Args:
        trust_trajectory: 长度为 total_ticks 的平均信任分列表
                          index 0 对应 Tick 1，index 29 对应 Tick 30
        conversion_trajectory: 累计转化率列表
        scandal_tick: 丑闻爆发 Tick（1-indexed），默认 5
        total_ticks: 总 Tick 数，默认 30
        clarification_tick: 企业澄清注入 Tick（1-indexed），用于诊断

    Returns:
        SimulationMetrics 实例
    """
    assert len(trust_trajectory) == total_ticks, \
        f"trust_trajectory length {len(trust_trajectory)} != total_ticks {total_ticks}"
    assert len(conversion_trajectory) == total_ticks, \
        f"conversion_trajectory length {len(conversion_trajectory)} != total_ticks {total_ticks}"
    # 丑闻必须在仿真窗口内，否则指标无意义
    if scandal_tick > total_ticks:
        raise ValueError(
            f"scandal_tick={scandal_tick} > total_ticks={total_ticks}; "
            f"increase total_ticks or decrease scandal_tick"
        )

    # ── 1. 基线信任：丑闻前一 Tick（Tick 4 → index 3） ────────────────
    baseline_idx = max(0, scandal_tick - 2)   # Tick 4 → index 3
    baseline_trust = trust_trajectory[baseline_idx]

    # ── 2. 信任最低点（丑闻后） ──────────────────────────────────────
    post_scandal_start = scandal_tick - 1     # Tick 5 → index 4
    post_scandal_values = trust_trajectory[post_scandal_start:]

    if not post_scandal_values:
        trust_min = trust_trajectory[-1]
        trust_min_tick = total_ticks
    else:
        trust_min = min(post_scandal_values)
        trust_min_idx_local = post_scandal_values.index(trust_min)
        trust_min_idx = post_scandal_start + trust_min_idx_local
        trust_min_tick = trust_min_idx + 1    # 1-indexed

    # ── 3. 核心指标一：delta_recovery ────────────────────────────────
    # 最终信任（Tick 30）与最低点信任的差值
    # 不存在 censoring，所有实验都有确定值，区分度高
    final_trust = trust_trajectory[-1]
    delta_recovery = round(final_trust - trust_min, 4)

    # ── 4. 核心指标二：auc_post_scandal（丑闻后归一化 AUC） ──────────
    # 计算 Tick [scandal_tick, 30] 区间的信任面积，归一化到 [0, 1]
    # AUC 越大 → 整个恢复过程中信任越高 → 策略效果越好
    post_scandal_segment = trust_trajectory[post_scandal_start:]
    n_post = len(post_scandal_segment)
    if n_post > 0:
        # 梯形积分（相邻 Tick 之间的面积）
        auc_raw = sum(
            (post_scandal_segment[i] + post_scandal_segment[i + 1]) / 2.0
            for i in range(n_post - 1)
        )
        # 归一化：除以最大可能面积（满分 10.0，共 n_post-1 个区间）
        max_auc = 10.0 * (n_post - 1) if n_post > 1 else 1.0
        auc_post_scandal = round(auc_raw / max_auc, 4)
    else:
        auc_post_scandal = 0.0

    # ── 5. 核心指标三：recovery_speed ────────────────────────────────
    # 恢复速度 = 净恢复量 / 恢复所用天数
    # 如果最低点在 Tick 30，分母为 1（防除零）
    trust_min_idx = trust_min_tick - 1  # 0-indexed
    days_to_recover = max(1, (total_ticks - 1) - trust_min_idx)   # 从最低点到 Tick 30
    recovery_speed = round(delta_recovery / days_to_recover, 4)

    # ── 6. T50（半恢复时间，辅助指标） ───────────────────────────────
    target_trust_50 = trust_min + 0.5 * (baseline_trust - trust_min)
    t50 = total_ticks  # 默认：censored
    for i in range(trust_min_idx, total_ticks):
        if trust_trajectory[i] >= target_trust_50:
            t50 = (i + 1) - trust_min_tick
            if t50 <= 0:
                t50 = 1
            break

    # ── 7. T80（全恢复时间，辅助指标） ───────────────────────────────
    target_trust_80 = baseline_trust * 0.8
    t80 = total_ticks  # 默认：censored
    for i in range(trust_min_idx, total_ticks):
        if trust_trajectory[i] >= target_trust_80:
            t80 = (i + 1) - trust_min_tick
            if t80 <= 0:
                t80 = 1
            break

    # ── 8. 稳态信任（辅助指标） ──────────────────────────────────────
    steady_state_score = trust_trajectory[-1]

    # ── 9. 转化率修复比（辅助指标） ──────────────────────────────────
    pre_scandal_conversions = conversion_trajectory[:scandal_tick - 1]
    pre_scandal_peak = max(pre_scandal_conversions) if pre_scandal_conversions else 0.0
    final_conversion = conversion_trajectory[-1]
    if pre_scandal_peak > 0:
        recovery_rate = final_conversion / pre_scandal_peak
    else:
        recovery_rate = final_conversion
    recovery_rate = min(recovery_rate, 2.0)

    # ── 10. 澄清效果诊断（新增）──────────────────────────────────────
    # 澄清注入后 3 个 Tick 的信任均值 vs 澄清前 3 个 Tick 的均值
    clarification_effect = 0.0
    if clarification_tick is not None and 1 <= clarification_tick <= total_ticks:
        clr_idx = clarification_tick - 1  # 0-indexed
        # 澄清前：最多取前 3 天
        pre_window_start = max(0, clr_idx - 3)
        pre_avg = sum(trust_trajectory[pre_window_start:clr_idx]) / max(1, clr_idx - pre_window_start)
        # 澄清后：最多取后 3 天
        post_window_end = min(total_ticks, clr_idx + 4)
        post_avg = sum(trust_trajectory[clr_idx + 1:post_window_end]) / max(1, post_window_end - clr_idx - 1)
        clarification_effect = round(post_avg - pre_avg, 4)

    return SimulationMetrics(
        delta_recovery=delta_recovery,
        auc_post_scandal=auc_post_scandal,
        recovery_speed=recovery_speed,
        t80=t80,
        t50=t50,
        steady_state_score=round(steady_state_score, 3),
        recovery_rate=round(recovery_rate, 3),
        trust_min=round(trust_min, 3),
        trust_min_tick=trust_min_tick,
        baseline_trust=round(baseline_trust, 3),
        clarification_effect=clarification_effect,
    )


if __name__ == "__main__":
    # 快速验证：模拟两条有对比度的信任轨迹
    import math

    print("=" * 60)
    print("验证 1：有澄清（第 8 天）vs 无澄清 — 区分度测试")
    print("=" * 60)

    def make_trajectory(has_clarification: bool, clr_tick: int = 8):
        traj = []
        for t in range(1, 31):
            if t <= 4:
                traj.append(7.0)
            elif t == 5:
                traj.append(3.5)
            elif has_clarification and t == clr_tick:
                traj.append(traj[-1] + 1.2)   # 澄清当天 +1.2
            else:
                # 遗忘曲线
                anchor = 3.5
                quiet = t - 5 - (1 if has_clarification and t > clr_tick else 0)
                lam = 0.06
                recovery = anchor + (7.0 - anchor) * (1 - math.exp(-lam * max(0, quiet)))
                traj.append(round(recovery, 3))
        return traj

    traj_clr   = make_trajectory(True,  clr_tick=8)
    traj_noclr = make_trajectory(False)
    conversion = [i * 0.05 for i in range(1, 5)] + [0.2] * 26

    m_clr   = compute_metrics(traj_clr,   conversion, clarification_tick=8)
    m_noclr = compute_metrics(traj_noclr, conversion)

    print(f"{'指标':<25} {'有澄清':>10} {'无澄清':>10} {'差值':>10}")
    print("-" * 55)
    print(f"{'delta_recovery':<25} {m_clr.delta_recovery:>10.4f} {m_noclr.delta_recovery:>10.4f} {m_clr.delta_recovery - m_noclr.delta_recovery:>+10.4f}")
    print(f"{'auc_post_scandal':<25} {m_clr.auc_post_scandal:>10.4f} {m_noclr.auc_post_scandal:>10.4f} {m_clr.auc_post_scandal - m_noclr.auc_post_scandal:>+10.4f}")
    print(f"{'recovery_speed':<25} {m_clr.recovery_speed:>10.4f} {m_noclr.recovery_speed:>10.4f} {m_clr.recovery_speed - m_noclr.recovery_speed:>+10.4f}")
    print(f"{'steady_state_score':<25} {m_clr.steady_state_score:>10.3f} {m_noclr.steady_state_score:>10.3f} {m_clr.steady_state_score - m_noclr.steady_state_score:>+10.3f}")
    print(f"{'t50':<25} {m_clr.t50:>10} {m_noclr.t50:>10}")
    print(f"{'clarification_effect':<25} {m_clr.clarification_effect:>10.4f}")
