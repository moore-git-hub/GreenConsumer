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
import math as _math
import statistics as _statistics
from collections.abc import Iterable, Mapping
from typing import List


METRICS_SCHEMA_VERSION = "4.0"
LOCAL_WINDOW_TICKS = 3
EARLY_HORIZON_INTERVALS = 5
RANKING_WEIGHT_STEP = 0.1
NUM_WEIGHT_COMBINATIONS = 66

V4_FIELDS = (
    "final_trust_gain_vs_control",
    "post_scandal_auc_gain_vs_control",
    "local_trust_effect_did_3",
    "early_trust_auc_gain_5",
    "early_trust_gain_slope_5",
    "secondary_harm_depth",
    "negative_gain_tick_count",
)

PRIMARY_OBJECTIVES_V4 = (
    "final_trust_gain_vs_control",
    "post_scandal_auc_gain_vs_control",
    "local_trust_effect_did_3",
)

TIE_TOLERANCE = 1e-12
NEGATIVE_GAIN_THRESHOLD = -1e-9


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

    # ── 4. 核心指标二：auc_post_scandal（从最低点之后的恢复面积） ────
    # 从 trust_min_tick 之后开始计算，更准确反映恢复阶段的信任质量
    # AUC 越大 → 恢复过程中信任维持在更高水平 → 策略效果越好
    recovery_start = trust_min_tick  # 最低点的下一个 Tick（0-indexed = trust_min_tick）
    recovery_segment = trust_trajectory[recovery_start:]
    n_rec = len(recovery_segment)
    if n_rec > 1:
        auc_raw = sum(
            (recovery_segment[i] + recovery_segment[i + 1]) / 2.0
            for i in range(n_rec - 1)
        )
        max_auc = 10.0 * (n_rec - 1)
        auc_post_scandal = round(auc_raw / max_auc, 4)
    elif n_rec == 1:
        auc_post_scandal = round(recovery_segment[0] / 10.0, 4)
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


def _is_int_not_bool(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_float_sequence(value, name: str) -> list[float]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a numeric iterable, not str/bytes")
    if not isinstance(value, Iterable):
        raise ValueError(f"{name} must be a numeric iterable")
    out = []
    for idx, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{name}[{idx}] must be a finite real number")
        number = float(item)
        if not _math.isfinite(number):
            raise ValueError(f"{name}[{idx}] must be finite")
        out.append(number)
    return out


def _validate_trajectories(
    strategy_trust,
    control_trust,
    *,
    scandal_tick: int,
    clarification_tick: int,
    total_ticks: int,
) -> tuple[list[float], list[float], list[float]]:
    if not _is_int_not_bool(total_ticks) or total_ticks <= 0:
        raise ValueError("total_ticks must be a positive integer")
    if not _is_int_not_bool(scandal_tick):
        raise ValueError("scandal_tick must be an integer")
    if not _is_int_not_bool(clarification_tick):
        raise ValueError("clarification_tick must be an integer")
    if not 1 <= scandal_tick <= total_ticks:
        raise ValueError("scandal_tick must be within 1..total_ticks")
    if not 1 <= clarification_tick <= total_ticks:
        raise ValueError("clarification_tick must be within 1..total_ticks")

    strategy = _as_float_sequence(strategy_trust, "strategy_trust")
    control = _as_float_sequence(control_trust, "control_trust")
    if len(strategy) != len(control):
        raise ValueError("strategy_trust and control_trust lengths must match")
    if len(strategy) != total_ticks:
        raise ValueError("trajectory length must equal total_ticks")
    gains = [strategy[i] - control[i] for i in range(total_ticks)]
    return strategy, control, gains


def _trapezoid_average(values: list[float]) -> float:
    if len(values) == 1:
        return values[0]
    intervals = len(values) - 1
    return sum((values[i] + values[i + 1]) / 2.0 for i in range(intervals)) / intervals


def _require_window(start_tick: int, end_tick: int, total_ticks: int, name: str) -> tuple[int, int]:
    if start_tick < 1 or end_tick > total_ticks or start_tick > end_tick:
        raise ValueError(f"{name} window is incomplete")
    return start_tick - 1, end_tick


def calculate_final_trust_gain_vs_control(
    strategy_trust,
    control_trust,
    *,
    scandal_tick: int,
    clarification_tick: int,
    total_ticks: int,
) -> float:
    """Return final-tick strategy trust minus common-control trust."""
    _, _, gains = _validate_trajectories(
        strategy_trust,
        control_trust,
        scandal_tick=scandal_tick,
        clarification_tick=clarification_tick,
        total_ticks=total_ticks,
    )
    return gains[total_ticks - 1]


def calculate_post_scandal_auc_gain_vs_control(
    strategy_trust,
    control_trust,
    *,
    scandal_tick: int,
    clarification_tick: int,
    total_ticks: int,
) -> float:
    """Return fixed-window post-scandal trapezoid AUC gain versus control."""
    if _is_int_not_bool(total_ticks) and _is_int_not_bool(scandal_tick) and total_ticks < scandal_tick:
        raise ValueError("total_ticks must be >= scandal_tick")
    _, _, gains = _validate_trajectories(
        strategy_trust,
        control_trust,
        scandal_tick=scandal_tick,
        clarification_tick=clarification_tick,
        total_ticks=total_ticks,
    )
    if total_ticks == scandal_tick:
        return gains[scandal_tick - 1]
    return _trapezoid_average(gains[scandal_tick - 1:total_ticks])


def calculate_local_trust_effect_did_3(
    strategy_trust,
    control_trust,
    *,
    scandal_tick: int,
    clarification_tick: int,
    total_ticks: int,
) -> float:
    """Return 3-pre/3-post local difference-in-differences at clarification."""
    strategy, control, _ = _validate_trajectories(
        strategy_trust,
        control_trust,
        scandal_tick=scandal_tick,
        clarification_tick=clarification_tick,
        total_ticks=total_ticks,
    )
    pre_start, pre_end = _require_window(
        clarification_tick - LOCAL_WINDOW_TICKS,
        clarification_tick - 1,
        total_ticks,
        "local pre",
    )
    post_start, post_end = _require_window(
        clarification_tick,
        clarification_tick + LOCAL_WINDOW_TICKS - 1,
        total_ticks,
        "local post",
    )
    strategy_pre = strategy[pre_start:pre_end]
    strategy_post = strategy[post_start:post_end]
    control_pre = control[pre_start:pre_end]
    control_post = control[post_start:post_end]
    if not (len(strategy_pre) == len(strategy_post) == len(control_pre) == len(control_post) == LOCAL_WINDOW_TICKS):
        raise ValueError("local DID windows must each contain exactly 3 ticks")
    return (
        (sum(strategy_post) / LOCAL_WINDOW_TICKS - sum(strategy_pre) / LOCAL_WINDOW_TICKS)
        - (sum(control_post) / LOCAL_WINDOW_TICKS - sum(control_pre) / LOCAL_WINDOW_TICKS)
    )


def calculate_early_trust_auc_gain_5(
    strategy_trust,
    control_trust,
    *,
    scandal_tick: int,
    clarification_tick: int,
    total_ticks: int,
) -> float:
    """Return fixed clarification-window AUC gain over h=0..5."""
    _, _, gains = _validate_trajectories(
        strategy_trust,
        control_trust,
        scandal_tick=scandal_tick,
        clarification_tick=clarification_tick,
        total_ticks=total_ticks,
    )
    start, end = _require_window(
        clarification_tick,
        clarification_tick + EARLY_HORIZON_INTERVALS,
        total_ticks,
        "early AUC",
    )
    early = gains[start:end]
    if len(early) != EARLY_HORIZON_INTERVALS + 1:
        raise ValueError("early AUC window must contain exactly 6 observations")
    return _trapezoid_average(early)


def calculate_early_trust_gain_slope_5(
    strategy_trust,
    control_trust,
    *,
    scandal_tick: int,
    clarification_tick: int,
    total_ticks: int,
) -> float:
    """Return OLS slope of gain over clarification-relative h=0..5."""
    _, _, gains = _validate_trajectories(
        strategy_trust,
        control_trust,
        scandal_tick=scandal_tick,
        clarification_tick=clarification_tick,
        total_ticks=total_ticks,
    )
    start, end = _require_window(
        clarification_tick,
        clarification_tick + EARLY_HORIZON_INTERVALS,
        total_ticks,
        "early slope",
    )
    y = gains[start:end]
    if len(y) != EARLY_HORIZON_INTERVALS + 1:
        raise ValueError("early slope window must contain exactly 6 observations")
    x = list(range(EARLY_HORIZON_INTERVALS + 1))
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denominator = sum((xi - mean_x) ** 2 for xi in x)
    return numerator / denominator


def calculate_secondary_harm_depth(
    strategy_trust,
    control_trust,
    *,
    scandal_tick: int,
    clarification_tick: int,
    total_ticks: int,
) -> float:
    """Return the deepest negative post-clarification gain, capped at zero."""
    _, _, gains = _validate_trajectories(
        strategy_trust,
        control_trust,
        scandal_tick=scandal_tick,
        clarification_tick=clarification_tick,
        total_ticks=total_ticks,
    )
    return min(0.0, min(gains[clarification_tick - 1:total_ticks]))


def calculate_negative_gain_tick_count(
    strategy_trust,
    control_trust,
    *,
    scandal_tick: int,
    clarification_tick: int,
    total_ticks: int,
) -> int:
    """Count post-clarification ticks whose gain is strictly below -1e-9."""
    _, _, gains = _validate_trajectories(
        strategy_trust,
        control_trust,
        scandal_tick=scandal_tick,
        clarification_tick=clarification_tick,
        total_ticks=total_ticks,
    )
    return sum(1 for gain in gains[clarification_tick - 1:total_ticks] if gain < NEGATIVE_GAIN_THRESHOLD)


def compute_relative_metrics_v4(
    strategy_trust,
    control_trust,
    *,
    scandal_tick: int,
    clarification_tick: int,
    total_ticks: int,
) -> dict:
    """Compute all seven TASK_004 v4 relative metrics as an ordered dict."""
    args = {
        "scandal_tick": scandal_tick,
        "clarification_tick": clarification_tick,
        "total_ticks": total_ticks,
    }
    return {
        "final_trust_gain_vs_control": calculate_final_trust_gain_vs_control(strategy_trust, control_trust, **args),
        "post_scandal_auc_gain_vs_control": calculate_post_scandal_auc_gain_vs_control(strategy_trust, control_trust, **args),
        "local_trust_effect_did_3": calculate_local_trust_effect_did_3(strategy_trust, control_trust, **args),
        "early_trust_auc_gain_5": calculate_early_trust_auc_gain_5(strategy_trust, control_trust, **args),
        "early_trust_gain_slope_5": calculate_early_trust_gain_slope_5(strategy_trust, control_trust, **args),
        "secondary_harm_depth": calculate_secondary_harm_depth(strategy_trust, control_trust, **args),
        "negative_gain_tick_count": calculate_negative_gain_tick_count(strategy_trust, control_trust, **args),
    }


def build_control_metrics_v4() -> dict:
    """Return the formal v4 metric values for the unique common control row."""
    return {
        "final_trust_gain_vs_control": 0,
        "post_scandal_auc_gain_vs_control": 0,
        "local_trust_effect_did_3": None,
        "early_trust_auc_gain_5": None,
        "early_trust_gain_slope_5": None,
        "secondary_harm_depth": None,
        "negative_gain_tick_count": None,
    }


def _parse_is_control(value) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, str) and value in ("True", "False"):
        return value == "True"
    raise ValueError("is_control must be True, False, 'True', or 'False'")


def _finite_metric(value, field: str) -> float:
    if value == "" or value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite real number")
    number = float(value)
    if not _math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _normalize_strategy_rows(rows) -> list[dict]:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Iterable):
        raise ValueError("rows must be an iterable of mappings")
    strategies = []
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"rows[{idx}] must be a mapping")
        row_copy = dict(row)
        is_control = _parse_is_control(row_copy.get("is_control", False))
        if is_control:
            continue
        exp_id = row_copy.get("exp_id")
        if not isinstance(exp_id, str) or not exp_id:
            raise ValueError("strategy exp_id must be a non-empty string")
        normalized = {"exp_id": exp_id, "is_control": False}
        for field in PRIMARY_OBJECTIVES_V4:
            if field not in row_copy:
                raise ValueError(f"missing v4 objective: {field}")
            normalized[field] = _finite_metric(row_copy[field], field)
        strategies.append(normalized)
    if len(strategies) != 8:
        raise ValueError("rows must contain exactly 8 strategy rows after excluding control")
    exp_ids = [row["exp_id"] for row in strategies]
    if len(set(exp_ids)) != 8:
        raise ValueError("strategy exp_id values must be unique")
    return sorted(strategies, key=lambda row: row["exp_id"])


def _dominates(candidate: dict, target: dict) -> bool:
    no_worse = all(
        candidate[field] >= target[field] - TIE_TOLERANCE
        for field in PRIMARY_OBJECTIVES_V4
    )
    strictly_better = any(
        candidate[field] > target[field] + TIE_TOLERANCE
        for field in PRIMARY_OBJECTIVES_V4
    )
    return no_worse and strictly_better


def compute_pareto_flags_v4(rows) -> list[dict]:
    """Return 8 strategy rows with v4 Pareto flags, excluding any control row."""
    strategies = _normalize_strategy_rows(rows)
    output = []
    for row in strategies:
        is_pareto = not any(
            _dominates(other, row)
            for other in strategies
            if other["exp_id"] != row["exp_id"]
        )
        output.append({
            "exp_id": row["exp_id"],
            "is_control": False,
            "final_trust_gain_vs_control": row["final_trust_gain_vs_control"],
            "post_scandal_auc_gain_vs_control": row["post_scandal_auc_gain_vs_control"],
            "local_trust_effect_did_3": row["local_trust_effect_did_3"],
            "is_pareto": bool(is_pareto),
        })
    return output


def _normalize_objective(strategies: list[dict], field: str) -> dict[str, float]:
    values = [row[field] for row in strategies]
    low = min(values)
    high = max(values)
    if abs(high - low) <= TIE_TOLERANCE:
        return {row["exp_id"]: 0.5 for row in strategies}
    return {row["exp_id"]: (row[field] - low) / (high - low) for row in strategies}


def _average_ranks(scores: dict[str, float]) -> dict[str, float]:
    ordered = sorted(scores, key=lambda exp_id: (-scores[exp_id], exp_id))
    ranks = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and abs(scores[ordered[end]] - scores[ordered[index]]) <= TIE_TOLERANCE:
            end += 1
        rank = (index + 1 + end) / 2.0
        for pos in range(index, end):
            ranks[ordered[pos]] = rank
        index = end
    return ranks


def _normalized_scores(strategies: list[dict]) -> dict[str, dict[str, float]]:
    final_norm = _normalize_objective(strategies, "final_trust_gain_vs_control")
    auc_norm = _normalize_objective(strategies, "post_scandal_auc_gain_vs_control")
    local_norm = _normalize_objective(strategies, "local_trust_effect_did_3")
    return {
        row["exp_id"]: {
            "final_norm": final_norm[row["exp_id"]],
            "auc_norm": auc_norm[row["exp_id"]],
            "local_norm": local_norm[row["exp_id"]],
        }
        for row in strategies
    }


def compute_equal_weight_ranking_v4(rows) -> list[dict]:
    """Return supplementary equal-weight ranking over the 8 strategy rows."""
    strategies = _normalize_strategy_rows(rows)
    norms = _normalized_scores(strategies)
    scores = {
        exp_id: (values["final_norm"] + values["auc_norm"] + values["local_norm"]) / 3.0
        for exp_id, values in norms.items()
    }
    ranks = _average_ranks(scores)
    output = []
    for exp_id in sorted(scores, key=lambda item: (ranks[item], item)):
        output.append({
            "exp_id": exp_id,
            "final_norm": norms[exp_id]["final_norm"],
            "auc_norm": norms[exp_id]["auc_norm"],
            "local_norm": norms[exp_id]["local_norm"],
            "score_equal": scores[exp_id],
            "rank": ranks[exp_id],
            "analysis_role": "supplementary",
        })
    return output


def generate_weight_combinations():
    """Generate the 66 deterministic 0.1-grid v4 objective weight triples."""
    for i in range(11):
        for j in range(11 - i):
            k = 10 - i - j
            yield (i / 10.0, j / 10.0, k / 10.0)


def compute_ranking_sensitivity_v4(rows) -> tuple[list[dict], list[dict]]:
    """Return v4 weight-sensitivity rows and per-strategy robustness rows."""
    strategies = _normalize_strategy_rows(rows)
    norms = _normalized_scores(strategies)
    sensitivity_rows = []
    for weight_final, weight_auc, weight_local in generate_weight_combinations():
        scores = {
            exp_id: (
                weight_final * values["final_norm"]
                + weight_auc * values["auc_norm"]
                + weight_local * values["local_norm"]
            )
            for exp_id, values in norms.items()
        }
        ranks = _average_ranks(scores)
        top_score = max(scores.values())
        winners = [
            exp_id for exp_id, score in scores.items()
            if abs(score - top_score) <= TIE_TOLERANCE
        ]
        ordered_ids = sorted(scores, key=lambda exp_id: (ranks[exp_id], exp_id))
        for exp_id in ordered_ids:
            sensitivity_rows.append({
                "weight_final": weight_final,
                "weight_auc": weight_auc,
                "weight_local": weight_local,
                "exp_id": exp_id,
                "weighted_score": scores[exp_id],
                "rank": ranks[exp_id],
                "top1_credit": 1.0 / len(winners) if exp_id in winners else 0.0,
            })

    robustness_rows = []
    for row in strategies:
        exp_id = row["exp_id"]
        rows_for_exp = [item for item in sensitivity_rows if item["exp_id"] == exp_id]
        ranks = [item["rank"] for item in rows_for_exp]
        robustness_rows.append({
            "exp_id": exp_id,
            "top1_share": sum(item["top1_credit"] for item in rows_for_exp) / NUM_WEIGHT_COMBINATIONS,
            "mean_rank": sum(ranks) / len(ranks),
            "median_rank": _statistics.median(ranks),
            "best_rank": min(ranks),
            "worst_rank": max(ranks),
        })
    return sensitivity_rows, sorted(robustness_rows, key=lambda row: row["exp_id"])


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
