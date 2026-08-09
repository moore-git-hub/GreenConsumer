"""
run_experiments.py — 实验批量调度入口

观测目标：单一漂绿事件（Blackstone 丑闻，Tick 5）后，
         8 clarification strategies + 1 unique common control.

设计原则：
  1. 单事件控制  — 临时 patch ENTERPRISE_STRATEGY 为仅含 Tick 5 的漂绿事件，
                   屏蔽 Tick 10/15 的后续事件，确保策略效果归因干净。
  2. 路径对齐   — 先跑 no-clarification 对照组并缓存 LLM 响应（RecordingRouter），
                   8 strategy conditions replay the same cache before clarification_tick,
                   保证 Tick 1~(clarification_tick-1) 的信任轨迹完全一致。
  3. 真实 LLM   — 澄清 Tick 当天及之后走真实 LLM，差异完全由策略内容决定。

用法：
    python run_experiments.py
"""
import sys
import os
import argparse
import asyncio
import copy
import csv
import datetime
import hashlib
import json
import math
import platform
import subprocess
import shutil
import inspect
from dataclasses import replace
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from experiment_config import (
    CHANNEL_LEVELS,
    CONTENT_LEVELS,
    CONTROL_EXP_ID,
    CONTROL_TIMING,
    DELAYED_OFFSET_TICKS,
    EXPERIMENT_MATRIX_VERSION,
    IMMEDIATE_OFFSET_TICKS,
    NOT_APPLICABLE,
    STRATEGY_TIMING_LEVELS,
    generate_experiment_matrix,
    ExperimentConfig,
)
from simulation_core import (
    run_simulation_core,
    ENTERPRISE_STRATEGY,
    AGENT_RECORDS_FIELDS,
    AGENT_RECORDS_SCHEMA_VERSION,
    MECHANISM_RECORDS_FIELDS,
    MECHANISM_RECORDS_SCHEMA_VERSION,
)
from metrics_calculator import (
    METRICS_SCHEMA_VERSION,
    LOCAL_WINDOW_TICKS,
    EARLY_HORIZON_INTERVALS,
    RANKING_WEIGHT_STEP,
    NUM_WEIGHT_COMBINATIONS,
    V4_FIELDS,
    PRIMARY_OBJECTIVES_V4,
    compute_relative_metrics_v4,
    build_control_metrics_v4,
    compute_ranking_sensitivity_v4,
)
from replication_config import (
    CACHE_SCOPE as REPLICATION_CACHE_SCOPE,
    EXECUTION_MODE as REPLICATION_EXECUTION_MODE,
    EXECUTION_ORDER as REPLICATION_EXECUTION_ORDER,
    LATEST_POLICY as REPLICATION_LATEST_POLICY,
    LLM_SEED_SUPPORTED_VALUES,
    REPLICATION_SCHEMA_VERSION,
    SEED_MAX,
    SEED_MIN,
)


# ══════════════════════════════════════════════════════════════════════
# 单事件 patch：只保留 Tick 5 的 Blackstone 漂绿丑闻
# ══════════════════════════════════════════════════════════════════════
_SINGLE_SCANDAL = {5: ENTERPRISE_STRATEGY[5]}


# ══════════════════════════════════════════════════════════════════════
# Recording / Replay Router（复用 run_clarification_trial 的设计）
# ══════════════════════════════════════════════════════════════════════

class RecordingRouter:
    """记录所有 LLM 调用：(prompt_hash, tick, call_index) → response"""

    def __init__(self, inner_router):
        self._inner = inner_router
        self._cache: dict = {}
        self._current_tick: int = 0
        self._call_counts: dict = {}

    def set_tick(self, tick: int):
        self._current_tick = tick
        self._call_counts = {}

    @staticmethod
    def _pk(prompt: str) -> str:
        return str(hash(prompt[:200]) & 0xFFFFFFFF)

    async def chat(self, prompt: str) -> str:
        pk = self._pk(prompt)
        count = self._call_counts.get(pk, 0)
        self._call_counts[pk] = count + 1
        response = await self._inner.chat(prompt)
        self._cache[(pk, self._current_tick, count)] = response
        return response

    @property
    def cache(self) -> dict:
        return self._cache


class ReplayAlignmentError(RuntimeError):
    """Raised when a replay-window cache miss breaks alignment."""

    def __init__(self, exp_id: str, tick: int, replay_until: int, miss_count: int):
        self.exp_id = exp_id
        self.tick = tick
        self.replay_until = replay_until
        self.miss_count = miss_count
        super().__init__(
            f"Replay alignment miss exp_id={exp_id} tick={tick} "
            f"replay_until={replay_until} miss_count={miss_count}"
        )


class ReplayRouter:
    """Replay cached calls before replay_until_tick; fail closed on window misses."""

    def __init__(self, inner_router, cache: dict, replay_until_tick: int, exp_id: str = ""):
        self._inner = inner_router
        self._cache = cache
        self._replay_until = replay_until_tick
        self._exp_id = exp_id
        self._current_tick: int = 0
        self._call_counts: dict = {}
        self.miss_count: int = 0

    def set_tick(self, tick: int):
        self._current_tick = tick
        self._call_counts = {}

    async def chat(self, prompt: str) -> str:
        pk = RecordingRouter._pk(prompt)
        count = self._call_counts.get(pk, 0)
        self._call_counts[pk] = count + 1

        if self._current_tick < self._replay_until:
            key = (pk, self._current_tick, count)
            if key in self._cache:
                return self._cache[key]
            self.miss_count += 1
            raise ReplayAlignmentError(
                exp_id=self._exp_id,
                tick=self._current_tick,
                replay_until=self._replay_until,
                miss_count=self.miss_count,
            )
        return await self._inner.chat(prompt)


# ══════════════════════════════════════════════════════════════════════
# CSV 写入函数
# ══════════════════════════════════════════════════════════════════════

SUMMARY_FIELDS = [
    "exp_id", "content_factor", "channel_factor", "timing_factor", "is_control",
    "delta_recovery", "auc_post_scandal", "recovery_speed",
    "steady_state_score", "recovery_rate", "t50", "t80",
    "trust_min", "trust_min_tick", "baseline_trust", "clarification_effect",
    "trust_gain_vs_control",
] + list(V4_FIELDS)


def _build_metrics_metadata_v4() -> dict:
    return {
        "schema_version": METRICS_SCHEMA_VERSION,
        "primary_objectives": list(PRIMARY_OBJECTIVES_V4),
        "post_scandal_window": {
            "start": "scandal_tick",
            "end": "total_ticks",
            "integration": "trapezoid",
            "normalization": "divide_by_interval_count",
        },
        "local_did": {
            "pre_ticks": LOCAL_WINDOW_TICKS,
            "post_ticks": LOCAL_WINDOW_TICKS,
            "post_includes_clarification_tick": True,
        },
        "early_window": {
            "horizon_intervals": EARLY_HORIZON_INTERVALS,
            "observations": EARLY_HORIZON_INTERVALS + 1,
        },
        "ranking": {
            "pareto_primary": True,
            "equal_weight_supplementary": True,
            "weight_sensitivity_step": RANKING_WEIGHT_STEP,
            "weight_combination_count": NUM_WEIGHT_COMBINATIONS,
        },
    }


def _finite_real_sequence(value, name: str, expected_len: int) -> list[float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a numeric list/tuple")
    if len(value) != expected_len:
        raise ValueError(f"{name} length {len(value)} != total_ticks {expected_len}")
    out = []
    for idx, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{name}[{idx}] must be a finite real number")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"{name}[{idx}] must be finite")
        out.append(number)
    return out


def _expected_clarification_tick_from_config(cfg: dict) -> int:
    generated = ExperimentConfig(
        content_factor=cfg["content_factor"],
        channel_factor=cfg["channel_factor"],
        timing_factor=cfg["timing_factor"],
        budget_k=cfg.get("budget_k", 3),
        random_seed=cfg.get("random_seed", 42),
        num_agents=cfg.get("num_agents", 20),
        total_ticks=cfg["total_ticks"],
        scandal_tick=cfg["scandal_tick"],
    )
    expected = generated.clarification_tick
    if expected is None:
        raise ValueError("strategy clarification_tick rule generated None")
    return expected


def _validate_v4_metric_keys(metrics: dict, exp_id: str) -> None:
    if not isinstance(metrics, dict):
        raise ValueError(f"{exp_id} relative_metrics_v4 must be a dict")
    if set(metrics.keys()) != set(V4_FIELDS):
        raise ValueError(f"{exp_id} relative_metrics_v4 keys must equal V4_FIELDS")


def _validate_control_metrics_v4(metrics: dict) -> None:
    _validate_v4_metric_keys(metrics, CONTROL_EXP_ID)
    if metrics["final_trust_gain_vs_control"] != 0:
        raise ValueError("control final_trust_gain_vs_control must be 0")
    if metrics["post_scandal_auc_gain_vs_control"] != 0:
        raise ValueError("control post_scandal_auc_gain_vs_control must be 0")
    for field in V4_FIELDS[2:]:
        if metrics[field] is not None:
            raise ValueError(f"control {field} must be None")


def _validate_strategy_metrics_v4(metrics: dict, exp_id: str) -> None:
    _validate_v4_metric_keys(metrics, exp_id)
    for field in V4_FIELDS:
        value = metrics[field]
        if field == "negative_gain_tick_count":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{exp_id} {field} must be a non-negative int")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{exp_id} {field} must be a finite number")


def attach_relative_metrics_v4(results: list) -> None:
    """Attach TASK_004 relative metrics atomically to the 9 successful batch results."""
    if not isinstance(results, list):
        raise ValueError("results must be a list")
    old_values = []
    sentinel = object()
    for result in results:
        if isinstance(result, dict) and "relative_metrics_v4" in result:
            old_values.append((result, result["relative_metrics_v4"]))
        elif isinstance(result, dict):
            old_values.append((result, sentinel))

    try:
        if len(results) != 9:
            raise ValueError(f"results must contain exactly 9 entries, got {len(results)}")
        for idx, result in enumerate(results):
            if not isinstance(result, dict):
                raise ValueError(f"results[{idx}] must be a dict")
            if "error" in result:
                raise ValueError(f"{result.get('exp_id', idx)} contains error")
            if not isinstance(result.get("config"), dict):
                raise ValueError(f"{result.get('exp_id', idx)} config must be a dict")

        controls = [r for r in results if r["config"].get("is_control") is True]
        strategies = [r for r in results if r["config"].get("is_control") is False]
        if len(controls) != 1:
            raise ValueError(f"expected exactly one control result, got {len(controls)}")
        if len(strategies) != 8:
            raise ValueError(f"expected exactly eight strategy results, got {len(strategies)}")

        control = controls[0]
        control_cfg = control["config"]
        if control.get("exp_id") != CONTROL_EXP_ID or control_cfg.get("exp_id") != CONTROL_EXP_ID:
            raise ValueError("control exp_id must be NoClarification-Control")
        if control_cfg.get("timing_factor") != CONTROL_TIMING:
            raise ValueError("control timing_factor must be no-clarification")
        if control_cfg.get("clarification_tick") is not None:
            raise ValueError("control clarification_tick must be None")

        total_ticks = control_cfg.get("total_ticks")
        scandal_tick = control_cfg.get("scandal_tick")
        if isinstance(total_ticks, bool) or not isinstance(total_ticks, int) or total_ticks <= 0:
            raise ValueError("control total_ticks must be a positive int")
        if isinstance(scandal_tick, bool) or not isinstance(scandal_tick, int):
            raise ValueError("control scandal_tick must be an int")
        control_trust = _finite_real_sequence(control.get("trust_trajectory"), CONTROL_EXP_ID, total_ticks)

        exp_ids = [r.get("exp_id") for r in strategies]
        if len(set(exp_ids)) != 8 or any(not isinstance(exp_id, str) or not exp_id for exp_id in exp_ids):
            raise ValueError("strategy exp_id values must be unique non-empty strings")

        pending = {id(control): build_control_metrics_v4()}
        for result in strategies:
            cfg = result["config"]
            exp_id = result.get("exp_id")
            if cfg.get("exp_id") != exp_id:
                raise ValueError(f"{exp_id} config exp_id mismatch")
            if cfg.get("is_control") is not False:
                raise ValueError(f"{exp_id} is_control must be False")
            if cfg.get("total_ticks") != total_ticks:
                raise ValueError(f"{exp_id} total_ticks differs from control")
            if cfg.get("scandal_tick") != scandal_tick:
                raise ValueError(f"{exp_id} scandal_tick differs from control")
            clarification_tick = cfg.get("clarification_tick")
            if isinstance(clarification_tick, bool) or not isinstance(clarification_tick, int):
                raise ValueError(f"{exp_id} clarification_tick must be an int")
            expected_tick = _expected_clarification_tick_from_config(cfg)
            if clarification_tick != expected_tick:
                raise ValueError(
                    f"{exp_id} clarification_tick {clarification_tick} != rule-generated {expected_tick}"
                )
            strategy_trust = _finite_real_sequence(result.get("trust_trajectory"), exp_id, total_ticks)
            pending[id(result)] = compute_relative_metrics_v4(
                strategy_trust,
                control_trust,
                scandal_tick=scandal_tick,
                clarification_tick=clarification_tick,
                total_ticks=total_ticks,
            )

        _validate_control_metrics_v4(pending[id(control)])
        for result in strategies:
            _validate_strategy_metrics_v4(pending[id(result)], result["exp_id"])

        for result in results:
            result["relative_metrics_v4"] = pending[id(result)]
    except Exception:
        for result, old_value in old_values:
            if old_value is sentinel:
                result.pop("relative_metrics_v4", None)
            else:
                result["relative_metrics_v4"] = old_value
        raise


def write_summary_csv(results: list, output_path: str):
    """Write summary.csv with a single common-control baseline."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(SUMMARY_FIELDS)
        for r in results:
            if "error" in r:
                writer.writerow([r["exp_id"]] + ["ERROR"] * (len(SUMMARY_FIELDS) - 1))
                continue
            cfg = r["config"]
            m = r["metrics"]
            relative = r.get("relative_metrics_v4")
            if relative is None:
                raise ValueError(f"{r.get('exp_id', 'unknown')} missing relative_metrics_v4")
            _validate_v4_metric_keys(relative, r.get("exp_id", "unknown"))
            trust_gain = relative["final_trust_gain_vs_control"]
            writer.writerow([
                r["exp_id"], cfg["content_factor"], cfg["channel_factor"],
                cfg["timing_factor"], cfg.get("is_control", False),
                m.delta_recovery, m.auc_post_scandal, m.recovery_speed,
                m.steady_state_score, m.recovery_rate, m.t50, m.t80,
                m.trust_min, m.trust_min_tick, m.baseline_trust,
                m.clarification_effect, trust_gain,
                *[relative[field] for field in V4_FIELDS],
            ])


def _build_v4_analysis_rows(results: list) -> list[dict]:
    if not isinstance(results, list) or len(results) != 9:
        raise ValueError("results must be a 9-row list")
    rows = []
    for result in results:
        if "error" in result:
            raise ValueError(f"{result.get('exp_id', 'unknown')} contains error")
        cfg = result.get("config")
        relative = result.get("relative_metrics_v4")
        if not isinstance(cfg, dict):
            raise ValueError(f"{result.get('exp_id', 'unknown')} config must be a dict")
        _validate_v4_metric_keys(relative, result.get("exp_id", "unknown"))
        row = {
            "exp_id": result.get("exp_id"),
            "content_factor": cfg.get("content_factor"),
            "channel_factor": cfg.get("channel_factor"),
            "timing_factor": cfg.get("timing_factor"),
            "is_control": cfg.get("is_control"),
        }
        row.update({field: relative[field] for field in V4_FIELDS})
        rows.append(row)
    return rows


def _finite_csv_number(row: dict, field: str) -> bool:
    value = row.get(field)
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def write_ranking_outputs_v4(
    results: list,
    sensitivity_path: str,
    robustness_path: str,
) -> tuple[list[dict], list[dict]]:
    rows = _build_v4_analysis_rows(results)
    sensitivity_rows, robustness_rows = compute_ranking_sensitivity_v4(rows)
    sensitivity_fields = [
        "weight_final", "weight_auc", "weight_local", "exp_id",
        "weighted_score", "rank", "top1_credit",
    ]
    robustness_fields = [
        "exp_id", "top1_share", "mean_rank", "median_rank",
        "best_rank", "worst_rank",
    ]

    if len(sensitivity_rows) != 528:
        raise ValueError(f"ranking_sensitivity must contain 528 rows, got {len(sensitivity_rows)}")
    if len(robustness_rows) != 8:
        raise ValueError(f"ranking_robustness must contain 8 rows, got {len(robustness_rows)}")
    for row in sensitivity_rows:
        if set(row.keys()) != set(sensitivity_fields):
            raise ValueError("ranking_sensitivity row keys do not match header")
        for field in ("weight_final", "weight_auc", "weight_local", "weighted_score", "rank", "top1_credit"):
            if not _finite_csv_number(row, field):
                raise ValueError(f"ranking_sensitivity {field} must be finite")
    for row in robustness_rows:
        if set(row.keys()) != set(robustness_fields):
            raise ValueError("ranking_robustness row keys do not match header")
        for field in ("top1_share", "mean_rank", "median_rank", "best_rank", "worst_rank"):
            if not _finite_csv_number(row, field):
                raise ValueError(f"ranking_robustness {field} must be finite")

    by_weight = {}
    for row in sensitivity_rows:
        key = (row["weight_final"], row["weight_auc"], row["weight_local"])
        by_weight.setdefault(key, []).append(row)
    if len(by_weight) != NUM_WEIGHT_COMBINATIONS:
        raise ValueError(f"expected {NUM_WEIGHT_COMBINATIONS} weight groups, got {len(by_weight)}")
    for key, items in by_weight.items():
        exp_ids = {item["exp_id"] for item in items}
        if len(items) != 8 or len(exp_ids) != 8:
            raise ValueError(f"weight group {key} must contain 8 distinct exp_id values")
        if abs(sum(float(item["top1_credit"]) for item in items) - 1.0) > 1e-9:
            raise ValueError(f"weight group {key} top1_credit sum must be 1")
    if len({row["exp_id"] for row in robustness_rows}) != 8:
        raise ValueError("ranking_robustness exp_id values must be unique")

    with open(sensitivity_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sensitivity_fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(sensitivity_rows)
    with open(robustness_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=robustness_fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(robustness_rows)
    return sensitivity_rows, robustness_rows

def write_trajectories_csv(results: list, output_path: str):
    """将所有实验的逐 Tick 轨迹写入 CSV（供折线图使用）"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "exp_id", "content_factor", "channel_factor", "timing_factor", "is_control",
            "tick", "avg_trust", "conversion_rate",
        ])
        for r in results:
            if "error" in r:
                continue
            cfg        = r["config"]
            trust_traj = r.get("trust_trajectory", [])
            conv_traj  = r.get("conversion_trajectory", [])
            for tick_idx, (trust, conv) in enumerate(zip(trust_traj, conv_traj), start=1):
                writer.writerow([
                    r["exp_id"], cfg["content_factor"], cfg["channel_factor"],
                    cfg["timing_factor"], cfg.get("is_control", False),
                    tick_idx, round(trust, 4), round(conv, 4),
                ])


def write_agent_records_csv(results: list, output_path: str):
    """逐 Agent 逐 Tick 详细记录 → CSV（schema v2.0，60 个唯一字段）

    字段清单来自 simulation_core.AGENT_RECORDS_FIELDS（单一事实来源），
    此处只做硬性契约校验，避免任何字段被重复列出（历史事故：trust_after_decay 出现两次）。
    """
    fieldnames = list(AGENT_RECORDS_FIELDS)
    duplicates = sorted({n for n in fieldnames if fieldnames.count(n) > 1})
    assert len(fieldnames) == 60, \
        f"agent_records schema 必须为 60 字段，实际 {len(fieldnames)}"
    assert len(fieldnames) == len(set(fieldnames)), \
        f"agent_records schema 存在重复字段: {duplicates}"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="", extrasaction="raise")
        writer.writeheader()
        for r in results:
            if "error" in r or "agent_records" not in r:
                continue
            for rec in r["agent_records"]:
                writer.writerow(rec)


def write_mechanism_records_csv(results: list, output_path: str):
    """Persist mechanism-v2 audit rows without changing agent_records.csv."""
    fieldnames = list(MECHANISM_RECORDS_FIELDS)
    duplicates = sorted({n for n in fieldnames if fieldnames.count(n) > 1})
    assert len(fieldnames) == len(set(fieldnames)), \
        f"mechanism_records schema 存在重复字段: {duplicates}"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="", extrasaction="raise")
        writer.writeheader()
        for r in results:
            if "error" in r or "mechanism_records" not in r:
                continue
            for rec in r["mechanism_records"]:
                writer.writerow(rec)


CLARIFICATION_EXPOSURE_FIELDS = [
    "exp_id", "agent_id", "public_organic", "paid_seed",
    "paid_one_hop", "reached", "exposure_modes",
]


def write_clarification_exposure_csv(results: list, output_path: str):
    # Persist public-vs-paid exposure audit.
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=CLARIFICATION_EXPOSURE_FIELDS,
            restval="", extrasaction="raise"
        )
        writer.writeheader()
        for result in results:
            if "error" in result:
                continue
            for row in result.get("clarification_exposure_meta", []):
                writer.writerow(row)


def write_target_nodes_csv(results: list, output_path: str):
    """目标节点选择审计明细 → CSV

    Random 渠道的 metric_value 写空字符串（不适用），禁止写 0：
    0 会与"该节点出度确实为 0"混淆，破坏审计可判定性。
    """
    fieldnames = ["exp_id", "content_factor", "channel_factor", "timing_factor",
                  "agent_id", "selection_metric", "metric_value", "rank"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for r in results:
            if "error" in r:
                continue
            for row in r.get("target_nodes_meta", []):
                writer.writerow(row)


# ── R10：run 级网络文件的列契约（均**不含** exp_id）──
NETWORK_NODES_FIELDS = ["agent_id", "cluster_type", "social_role",
                        "out_degree", "in_degree"]
NETWORK_EDGES_FIELDS = ["source_agent_id", "target_agent_id", "is_directed"]


def verify_single_network(results: list) -> dict:
    """TASK_002 / R10：验证"整个 run 只有一张网络"这个前提，而不是假设它。

    network_nodes.csv / network_edges.csv 是 run 级静态文件（全 run 一份、无 exp_id），
    其成立条件是所有成功实验的拓扑完全相同。该条件由 (num_agents, random_seed) 决定，
    9 conditions currently share (20, 42), but this must be verified; if a seed changes,
    静默写出"某一组"的拓扑会让全部网络分析结论失去归属。

    Returns:
        {"status": "consistent" | "inconsistent" | "unavailable",
         "network_hash": str, "source_exp_id": str,
         "hash_groups": {hash: [exp_id…]}, "per_experiment": [...],
         "node_row_mismatch": [...], "edge_row_mismatch": [...],
         "checked_experiments": int, "reason": str}
    """
    ok = [r for r in results if "error" not in r and r.get("network_meta")]
    ok.sort(key=lambda r: str(r.get("exp_id", "")))
    per_exp = []
    for r in ok:
        nm = r.get("network_meta", {}) or {}
        cfg = r.get("config", {}) or {}
        per_exp.append({
            "exp_id": r.get("exp_id", "unknown"),
            "network_hash": nm.get("network_hash", ""),
            "num_nodes": nm.get("num_nodes", ""),
            "num_edges": nm.get("num_edges", ""),
            "network_type": nm.get("network_type", ""),
            "network_params": nm.get("network_params", {}),
            "random_seed": cfg.get("random_seed", ""),
            "num_agents": cfg.get("num_agents", ""),
        })

    hash_groups: dict = {}
    for e in per_exp:
        hash_groups.setdefault(e["network_hash"], []).append(e["exp_id"])

    base = {
        "hash_groups": hash_groups,
        "per_experiment": per_exp,
        "checked_experiments": len(ok),
        "node_row_mismatch": [],
        "edge_row_mismatch": [],
        "refused_outputs": ["network_nodes.csv", "network_edges.csv"],
    }

    if not ok:
        base.update({"status": "unavailable", "network_hash": "", "source_exp_id": "",
                     "reason": "no successful experiment reported network_meta"})
        return base

    if len(hash_groups) > 1:
        base.update({"status": "inconsistent", "network_hash": "", "source_exp_id": "",
                     "reason": "network_hash differs across successful experiments"})
        return base

    # 哈希只覆盖拓扑；节点表还含 cluster_type / social_role，逐行再核一次
    ref = ok[0]
    ref_nodes = [tuple(row[k] for k in NETWORK_NODES_FIELDS)
                 for row in ref.get("network_nodes", [])]
    ref_edges = [tuple(row[k] for k in NETWORK_EDGES_FIELDS)
                 for row in ref.get("network_edges", [])]
    for r in ok[1:]:
        rn = [tuple(row[k] for k in NETWORK_NODES_FIELDS)
              for row in r.get("network_nodes", [])]
        re_ = [tuple(row[k] for k in NETWORK_EDGES_FIELDS)
               for row in r.get("network_edges", [])]
        if rn != ref_nodes:
            base["node_row_mismatch"].append(r.get("exp_id", "unknown"))
        if re_ != ref_edges:
            base["edge_row_mismatch"].append(r.get("exp_id", "unknown"))

    if base["node_row_mismatch"] or base["edge_row_mismatch"]:
        base.update({"status": "inconsistent", "network_hash": "", "source_exp_id": "",
                     "reason": "network_hash matches but node/edge rows differ "
                               "(cluster_type / social_role / degree mismatch)"})
        return base

    base.update({
        "status": "consistent",
        "network_hash": per_exp[0]["network_hash"],
        # 按 exp_id 字典序取最小者作为 run 级代表，使选择是确定性的
        "source_exp_id": per_exp[0]["exp_id"],
        "reason": "",
        "refused_outputs": [],
    })
    return base


def write_network_inconsistency_report(verification: dict, output_path: str):
    """R10 失败路径：把"为什么拒绝写出 run 级网络文件"完整落盘。

    刻意包含 random_seed / num_agents / network_type / network_params——
    一致性被打破时，原因几乎总在这四项里。
    """
    report = dict(verification)
    report["remedy"] = (
        "Topology must be identical across the run (same num_agents / random_seed "
        "and the same register_agents path). Inspect per_experiment: differing "
        "random_seed or num_agents, or a non-deterministic graph construction."
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def write_network_nodes_csv(results: list, output_path: str, verification: dict) -> bool:
    """run 级社交网络节点表 → CSV（整个 run 一份，每节点一行，**无 exp_id**）。

    TASK_002 / R10：
      · 只有 verification["status"] == "consistent" 时才写出；否则**连表头都不写**
        （空表头文件会被下游误读为"网络为空"），返回 False 由调用方判 FAIL。
      · 行数据取自 verification["source_exp_id"] 指定的那组实验——此时已验证
        所有成功实验的行完全相同，取哪组都一样，取最小 exp_id 只为确定性。
      · 不含 is_clarification_target：目标身份是实验级事实，唯一落点是 target_nodes.csv。
    """
    if verification.get("status") != "consistent":
        return False
    src = next((r for r in results
                if r.get("exp_id") == verification.get("source_exp_id")), None)
    if src is None:
        return False
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NETWORK_NODES_FIELDS,
                               restval="", extrasaction="raise")
        writer.writeheader()
        for row in src.get("network_nodes", []):
            writer.writerow(row)
    return True


def write_network_edges_csv(results: list, output_path: str, verification: dict) -> bool:
    """run 级社交网络边表 → CSV（整个 run 一份，字典序，**无 exp_id**）。

    与 write_network_nodes_csv 同样的前置条件：不一致 / 不可判定 → 不写出，返回 False。
    """
    if verification.get("status") != "consistent":
        return False
    src = next((r for r in results
                if r.get("exp_id") == verification.get("source_exp_id")), None)
    if src is None:
        return False
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NETWORK_EDGES_FIELDS,
                               restval="", extrasaction="raise")
        writer.writeheader()
        for row in src.get("network_edges", []):
            writer.writerow(row)
    return True


# R12：18 个字段。因子/seed/预算来自 config.to_dict()（异常分支也必须带 config），
#      target_nodes / network_hash / effective_event_timeline 来自实验结果。
EXPERIMENT_METADATA_FIELDS = [
    # 标识
    "exp_id",
    # 实验因子与参数（真实字段名已核对：random_seed 不是 seed；
    # clarification_tick 是 ExperimentConfig 的 @property，由 to_dict() 补入）
    "content_factor", "channel_factor", "timing_factor",
    "clarification_tick", "random_seed", "budget_k",
    # 运行时序
    "started_at", "finished_at",
    # Router 审计（router_role 说明 recording_cache_size 的语义归属）
    "recording_cache_size", "replay_miss_count", "router_role",
    # 实验输入指纹
    "target_nodes", "network_hash", "effective_event_timeline",
    # 状态
    "success", "error_type", "error",
]


def write_experiment_metadata_jsonl(results: list, output_path: str):
    """每个 exp_id 一行的实验级运行元数据（JSON Lines，18 字段）。

    取值来源（全部为真实运行期采集，见设计文档 §C6）：
      content/channel/timing/clarification_tick/random_seed/budget_k
                               : result["config"]（= ExperimentConfig.to_dict()）
                                 —— 成功与失败实验**都**带 config（R12）
      started_at / finished_at : main() 循环内在 _run_with_patch 调用前后取 datetime
      recording_cache_size     : 录制组 len(RecordingRouter.cache)；
                                 回放组 len(llm_cache)（该组实际消费的缓存规模）
      replay_miss_count        : ReplayRouter.miss_count；录制组不适用 → ""
      target_nodes             : result["target_nodes_meta"] 的 agent_id 列表（真实选点）
      network_hash             : result["network_meta"]["network_hash"]（真实图指纹）
      effective_event_timeline : result["effective_event_timeline"]（运行期快照，
                                 绝不从 ENTERPRISE_STRATEGY 重建）
      success / error_type / error : 实验结果状态
    "" 表示"不适用"，与数值 0 严格区分；缺失键一律补 "" / []，绝不猜测。
    clarification_tick 为 None（no-clarification）时写 ""，不写 0。
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            audit = r.get("run_audit", {}) or {}
            cfg = r.get("config", {}) or {}
            clr_tick = cfg.get("clarification_tick", None)
            row = {
                "exp_id": r.get("exp_id", cfg.get("exp_id", "unknown")),
                # ── R12：实验因子与参数（异常结果同样具备）──
                "content_factor": cfg.get("content_factor", ""),
                "channel_factor": cfg.get("channel_factor", ""),
                "timing_factor": cfg.get("timing_factor", ""),
                "clarification_tick": "" if clr_tick is None else clr_tick,
                "random_seed": cfg.get("random_seed", ""),
                "budget_k": cfg.get("budget_k", ""),
                # ── 运行时序与 Router ──
                "started_at": audit.get("started_at", ""),
                "finished_at": audit.get("finished_at", ""),
                "recording_cache_size": audit.get("recording_cache_size", ""),
                "replay_miss_count": audit.get("replay_miss_count", ""),
                "router_role": audit.get("router_role", ""),
                # ── R12：实验输入指纹（依赖运行结果，失败实验记空）──
                "target_nodes": [row_.get("agent_id")
                                 for row_ in (r.get("target_nodes_meta") or [])],
                "network_hash": (r.get("network_meta", {}) or {}).get("network_hash", ""),
                "effective_event_timeline": r.get("effective_event_timeline", []),
                # ── 状态 ──
                "success": "error" not in r,
                "error_type": r.get("error_type", "") if "error" in r else "",
                "error": str(r.get("error", "")) if "error" in r else "",
            }
            assert set(row.keys()) == set(EXPERIMENT_METADATA_FIELDS), \
                "experiment_metadata 行字段与契约不一致"
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _sha256_file(path: str) -> str:
    """文件 SHA-256。文件缺失时返回 'missing:<basename>'，绝不返回 'unknown'。"""
    if not os.path.isfile(path):
        return f"missing:{os.path.basename(path)}"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_porcelain(project_root: str, paths=None):
    """`git status --porcelain` 的非空行列表；无法执行/非零退出时返回 None（= 不可判定）。

    使用列表形式的 argv（不经过 shell），路径作为独立参数传入，避免任何注入风险。
    """
    cmd = ["git", "status", "--porcelain", "--untracked-files=all"]
    if paths:
        cmd = cmd + ["--"] + [str(p) for p in paths]
    try:
        proc = subprocess.run(cmd, cwd=project_root, capture_output=True,
                              text=True, timeout=30)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def _git_is_dirty(project_root: str):
    """仓库是否存在未提交修改（含未跟踪文件）。

    不可判定（无 git / 非仓库 / 命令失败）时返回字符串 "unknown"——
    绝不假设为 False，否则会把"不知道"记录成"干净"。
    """
    lines = _git_porcelain(project_root)
    if lines is None:
        return "unknown"
    return len(lines) > 0


def _read_git_info(project_root: str) -> dict:
    """直接读取 .git 内的文本引用取 branch/commit（不依赖子进程），
    另用 git status 取 is_dirty（TASK_002 / R8：脏工作区必须显式记录）。"""
    git_dir = os.path.join(project_root, ".git")
    info = {"branch": "unknown", "commit": "unknown",
            "is_dirty": _git_is_dirty(project_root)}
    head_path = os.path.join(git_dir, "HEAD")
    if not os.path.isfile(head_path):
        return info
    with open(head_path, "r", encoding="utf-8") as f:
        head = f.read().strip()
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        info["branch"] = ref.split("/")[-1]
        ref_path = os.path.join(git_dir, *ref.split("/"))
        if os.path.isfile(ref_path):
            with open(ref_path, "r", encoding="utf-8") as f:
                info["commit"] = f.read().strip()
        else:
            packed = os.path.join(git_dir, "packed-refs")
            if os.path.isfile(packed):
                with open(packed, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.rstrip().endswith(" " + ref):
                            info["commit"] = line.split()[0]
                            break
    else:
        info["branch"] = "DETACHED"
        info["commit"] = head
    return info


def _read_llm_config(project_root: str) -> dict:
    """读取 models_config.yaml 的采样参数。

    未在配置中出现的参数一律记为 "unknown"——例如当前配置没有 top_p，
    就必须记 "unknown"，禁止填 1.0 之类的假设默认值冒充"已知配置"。
    api_key 只记录是否存在，绝不写入结果文件。
    """
    import yaml
    cfg_path = os.path.join(project_root, "configs", "models_config.yaml")
    meta = {"config_file": "configs/models_config.yaml",
            "config_sha256": _sha256_file(cfg_path)}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            conf = yaml.safe_load(f)
    except Exception as e:
        meta["read_error"] = f"{type(e).__name__}: {e}"
        return meta
    entries = conf if isinstance(conf, list) else [conf]
    entries = [e for e in entries if isinstance(e, dict)]
    entry = next((e for e in entries if "chat" in (e.get("capabilities") or [])),
                 entries[0] if entries else {})
    for key in ("name", "model", "base_url", "temperature", "top_p", "seed",
                "max_tokens", "frequency_penalty", "presence_penalty"):
        meta[key] = entry.get(key, "unknown")
    meta["api_key_present"] = bool(entry.get("api_key"))
    return meta


def _is_deterministic_mock_context(replication_context: dict | None) -> bool:
    return (
        replication_context is not None
        and replication_context.get("llm_mode") == "deterministic-mock"
    )


def _build_llm_metadata(project_root: str, replication_context: dict | None) -> dict:
    if _is_deterministic_mock_context(replication_context):
        return {
            "mode": "deterministic-mock",
            "config_read": False,
            "config_file": "not-read",
            "config_sha256": "not-read",
            "api_key_present": "not-read",
            "requested_llm_seed": replication_context["requested_llm_seed"],
            "engineering_acceptance_only": True,
        }

    meta = _read_llm_config(project_root)
    if replication_context is not None:
        meta["mode"] = "real"
        meta["requested_llm_seed"] = replication_context["requested_llm_seed"]
        meta["seed"] = replication_context["requested_llm_seed"]
        meta["llm_seed_supported"] = replication_context["llm_seed_supported"]
        meta["engineering_acceptance_only"] = False
    return meta


# 元数据中登记哈希的源文件（相对 project_root）
_HASHED_SOURCES = [
    "run_experiments.py",
    "simulation_core.py",
    "mechanism_v2.py",
    "experiment_config.py",
    "node_selector.py",
    "clarification_injector.py",
    "metrics_calculator.py",
    "generate_data.py",
    "plugins/agent/plan/ConsumerPlanPlugin.py",
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "plugins/agent/reflect/MemoryManager.py",
    "plugins/agent/perceive/GreenPerceivePlugin.py",
    "plugins/agent/profile/GreenProfilePlugin.py",
    "plugins/agent/state/GreenStatePlugin.py",
    "plugins/agent/invoke/GreenInvokePlugin.py",
    "plugins/environment/network/SocialNetworkPlugin.py",
    "configs/models_config.yaml",
]


def _source_file_hashes(project_root: str, replication_context: dict | None) -> dict:
    hashes = {}
    for rel in _HASHED_SOURCES:
        if _is_deterministic_mock_context(replication_context) and rel == "configs/models_config.yaml":
            hashes[rel] = "not-read: deterministic-mock"
        else:
            hashes[rel] = _sha256_file(os.path.join(project_root, *rel.split("/")))
    return hashes

# Prompt / Persona 的权威来源文件。路径**必须**由 project_root 解析，
# 禁止从 output_path 推导（输出目录是 results/experiments/run_*，与源码目录无结构关系）。
_PROMPT_SOURCES = {
    "reflect_prompt":          "plugins/agent/reflect/GreenCognitionPlugin.py",
    "plan_prompt":             "plugins/agent/plan/ConsumerPlanPlugin.py",
    "clarification_templates": "clarification_injector.py",
    "global_event_script":     "simulation_core.py",
}
_PERSONA_SOURCES = {
    "persona_templates":       "generate_data.py",
    "persona_profile_plugin":  "plugins/agent/profile/GreenProfilePlugin.py",
}


def write_run_metadata_json(results: list, output_path: str, project_root: str,
                            run_id: str = "", network_verification: dict = None,
                            batch_exit_code: int = 0,
                            run_completed: bool = True,
                            *,
                            replication_context: dict | None = None) -> dict:
    """写入运行级元数据（schema v2.0 的补充证据）。

    Args:
        results:      实验结果列表
        output_path:  run_metadata.json 目标路径
        project_root: 项目根目录绝对路径。Prompt / Persona / 配置文件路径**必须**
                      由该参数解析，禁止从 output_path 反推。
        run_id:       本次运行时间戳 ID
        network_verification: verify_single_network() 的返回值（R10）。
                      为 None 时表示调用方未做验证 → 记 status="not_verified"，
                      绝不记成 "consistent"（不知道 ≠ 一致）。
    """
    from clarification_injector import CONTENT_TEMPLATES

    git_info = _read_git_info(project_root)
    meta = {
        "agent_records_schema_version": AGENT_RECORDS_SCHEMA_VERSION,
        "agent_records_field_count": len(AGENT_RECORDS_FIELDS),
        "agent_records_fields": list(AGENT_RECORDS_FIELDS),
        "mechanism_records_schema_version": MECHANISM_RECORDS_SCHEMA_VERSION,
        "mechanism_records_field_count": len(MECHANISM_RECORDS_FIELDS),
        "mechanism_records_fields": list(MECHANISM_RECORDS_FIELDS),
        "run_id": run_id,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "project_root": project_root,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "git": git_info,
        "batch_exit_code": batch_exit_code,
        "run_completed": run_completed,
        "experiment_matrix": {
            "matrix_version": EXPERIMENT_MATRIX_VERSION,
            "condition_count": 9,
            "strategy_condition_count": 8,
            "control_condition_count": 1,
            "control_exp_id": CONTROL_EXP_ID,
            "content_levels": list(CONTENT_LEVELS),
            "channel_levels": list(CHANNEL_LEVELS),
            "timing_levels": list(STRATEGY_TIMING_LEVELS),
            "control_timing": CONTROL_TIMING,
            "not_applicable_value": NOT_APPLICABLE,
            "immediate_offset_ticks": IMMEDIATE_OFFSET_TICKS,
            "delayed_offset_ticks": DELAYED_OFFSET_TICKS,
            "recording_exp_id": CONTROL_EXP_ID,
            "replay_until_by_exp_id": {
                r.get("exp_id", ""): (r.get("config") or {}).get("clarification_tick")
                for r in results
                if not (r.get("config") or {}).get("is_control", False)
            },
            "replay_alignment_violated": any(
                (r.get("run_audit") or {}).get("replay_miss_count") not in ("", 0, "0")
                for r in results
            ),
            "replay_miss_by_exp_id": {
                r.get("exp_id", ""): (r.get("run_audit") or {}).get("replay_miss_count")
                for r in results
                if (r.get("run_audit") or {}).get("replay_miss_count") not in ("", 0, "0")
            },
            "divergent_recording_enabled": False,
        },
        "metrics": _build_metrics_metadata_v4(),
        # R8：顶层显式镜像，便于审计脚本直接 grep；值恒等于 git["is_dirty"]
        #     True/False = 已判定，"unknown" = 无法判定（绝不静默当作干净）
        "git_is_dirty": git_info["is_dirty"],
        "llm": _build_llm_metadata(project_root, replication_context),
        # R10：run 级网络文件的前提是否被验证通过。唯一的运行级元数据文件
        #      自身即可判定：status != "consistent" 时两个网络 CSV 必然不存在。
        "network_consistency": (dict(network_verification)
                                if network_verification is not None
                                else {"status": "not_verified",
                                      "reason": "verify_single_network() was not called",
                                      "refused_outputs": ["network_nodes.csv",
                                                          "network_edges.csv"]}),
        "source_file_hashes": _source_file_hashes(project_root, replication_context),
        "prompt_sources": {
            key: {"path": rel,
                  "sha256": _sha256_file(os.path.join(project_root, *rel.split("/")))}
            for key, rel in _PROMPT_SOURCES.items()
        },
        "persona_sources": {
            key: {"path": rel,
                  "sha256": _sha256_file(os.path.join(project_root, *rel.split("/")))}
            for key, rel in _PERSONA_SOURCES.items()
        },
        "clarification_templates": {
            name: {
                "word_count": len(text.split()),
                "char_count": len(text),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
            for name, text in CONTENT_TEMPLATES.items()
        },
        # R4：**删除** 旧的 "global_event_ticks": sorted(ENTERPRISE_STRATEGY.keys())。
        #     该写法在运行结束后从常量重建时间线，无法反映 _run_with_patch 的实际改写，
        #     且与 patch 的恢复顺序耦合。改为从实验结果读取真实生效的时间线（见下）。
        "experiments": [],
    }
    if replication_context is not None:
        meta["replication"] = {
            field: replication_context[field]
            for field in REPLICATION_METADATA_FIELDS
        }

    for r in results:
        entry = {"exp_id": r.get("exp_id", "unknown")}
        if "error" in r:
            entry["status"] = "error"
            entry["error_type"] = str(r.get("error_type", ""))
            entry["error"] = str(r["error"])
            # R12：异常结果同样保存 config —— 失败实验最需要"它是哪一组因子/什么 seed"
            entry["config"] = r.get("config", {})
            # 失败实验没有生效时间线；显式记空列表 + 原因，不回退到常量
            entry["effective_event_timeline"] = []
            entry["effective_event_timeline_source"] = "unavailable: experiment failed"
        else:
            entry["status"] = "ok"
            entry["config"] = r.get("config", {})
            entry["network"] = r.get("network_meta", {})
            entry["target_nodes"] = [row.get("agent_id") for row in r.get("target_nodes_meta", [])]
            entry["agent_record_count"] = len(r.get("agent_records", []))
            entry["network_node_count"] = len(r.get("network_nodes", []))
            entry["network_edge_count"] = len(r.get("network_edges", []))
            # R4：只从实验结果读取；结果里没有就记 unknown，绝不从 ENTERPRISE_STRATEGY 重建
            if "effective_event_timeline" in r:
                entry["effective_event_timeline"] = r["effective_event_timeline"]
                entry["effective_event_timeline_source"] = "run_simulation_core (runtime snapshot)"
            else:
                entry["effective_event_timeline"] = []
                entry["effective_event_timeline_source"] = "unknown: not reported by result"
            if "relative_metrics_v4" in r:
                entry["relative_metrics_v4"] = r["relative_metrics_v4"]
        meta["experiments"].append(entry)

    # 全部成功实验实际生效的事件 Tick 并集（仅由结果聚合，不引用任何常量）
    meta["effective_event_ticks_union"] = sorted({
        int(e["tick"])
        for entry in meta["experiments"]
        for e in entry.get("effective_event_timeline", [])
    })

    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, output_path)
    return meta


LATEST_MANAGED_TARGETS = (
    "summary.csv",
    "ranking_sensitivity.csv",
    "ranking_robustness.csv",
    "trajectories.csv",
    "agent_records.csv",
    "mechanism_records.csv",
    "target_nodes.csv",
    "network_nodes.csv",
    "network_edges.csv",
    "experiment_metadata.jsonl",
    "run_metadata.json",
    "network_inconsistency_report.json",
    "errors.log",
    "run_info.txt",
    "figures",
)


def sync_latest_snapshot(run_dir: str, latest_dir: str, run_id: str,
                         results: list, total: int) -> None:
    """Refresh only files managed by this batch runner in latest/."""
    os.makedirs(latest_dir, exist_ok=True)
    for name in LATEST_MANAGED_TARGETS:
        target = os.path.join(latest_dir, name)
        if os.path.isdir(target):
            shutil.rmtree(target)
        elif os.path.exists(target):
            os.remove(target)

    for name in LATEST_MANAGED_TARGETS:
        if name == "run_info.txt":
            continue
        src = os.path.join(run_dir, name)
        dst = os.path.join(latest_dir, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        elif os.path.exists(src):
            shutil.copy2(src, dst)

    with open(os.path.join(latest_dir, "run_info.txt"), "w", encoding="utf-8") as f:
        f.write(f"run_id   : {run_id}\n")
        f.write(f"run_dir  : {run_dir}\n")
        f.write(f"generated: {datetime.datetime.now()}\n")
        f.write(f"success  : {len([r for r in results if 'error' not in r])}/{total}\n")


REPLICATION_CLI_ARGS = (
    "replication_id",
    "replicate_id",
    "replicate_index",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "python_hash_seed",
    "output_dir",
    "no_latest",
    "llm_mode",
)

LLM_MODES = ("real", "deterministic-mock")
FORMAL_CHILD_AUTH_ENV = (
    "TASK005_FORMAL_AUTHORIZATION_SHA256",
    "TASK005_FORMAL_ACTIVATION_CODE_HEAD",
    "TASK005_FORMAL_AUTHORIZATION_PATH",
    "TASK005_FORMAL_LAUNCH_CONTRACT_SHA256",
)
FORMAL_EXECUTION_AUTH_REL = Path(
    ".kiro/specs/task005-replication-inference/"
    "formal_execution_authorization1.1.json"
)

REPLICATION_METADATA_FIELDS = (
    "schema_version",
    "replication_id",
    "replicate_id",
    "replicate_index",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "python_hash_seed",
    "cache_scope",
    "execution_mode",
    "latest_policy",
    "engineering_acceptance_only",
)


class ReplicationStartupError(ValueError):
    """Raised for TASK_005 child-mode pre-simulation contract failures."""


def parse_cli_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--replication-id", dest="replication_id", default=None)
    parser.add_argument("--replicate-id", dest="replicate_id", default=None)
    parser.add_argument("--replicate-index", dest="replicate_index", type=int, default=None)
    parser.add_argument("--simulation-seed", dest="simulation_seed", type=int, default=None)
    parser.add_argument("--requested-llm-seed", dest="requested_llm_seed", type=int, default=None)
    parser.add_argument("--llm-seed-supported", dest="llm_seed_supported",
                        choices=LLM_SEED_SUPPORTED_VALUES, default=None)
    parser.add_argument("--python-hash-seed", dest="python_hash_seed", type=int, default=None)
    parser.add_argument("--output-dir", dest="output_dir", default=None)
    parser.add_argument("--no-latest", dest="no_latest", action="store_true", default=False)
    parser.add_argument("--llm-mode", dest="llm_mode", choices=LLM_MODES, default=None)
    return parser.parse_args(argv)


def _replication_argument_was_supplied(name, value) -> bool:
    if name == "no_latest":
        return value is True
    return value is not None


def build_replication_context(args) -> dict | None:
    values = {name: getattr(args, name, None) for name in REPLICATION_CLI_ARGS}
    child_requested = any(
        _replication_argument_was_supplied(name, value)
        for name, value in values.items()
    )
    if not child_requested:
        return None

    missing = [
        name for name, value in values.items()
        if value is None or (name == "no_latest" and value is not True)
    ]
    if missing:
        raise ReplicationStartupError(
            "replication child mode requires all replication arguments"
        )

    replication_id = _require_non_empty_string(values["replication_id"], "replication_id")
    replicate_index = _require_non_bool_int(values["replicate_index"], "replicate_index")
    if replicate_index < 1:
        raise ReplicationStartupError("replicate_index must be >= 1")
    replicate_id = _require_non_empty_string(values["replicate_id"], "replicate_id")
    expected_replicate_id = f"R{replicate_index:03d}"
    if replicate_id != expected_replicate_id:
        raise ReplicationStartupError(
            f"replicate_id must equal {expected_replicate_id}"
        )
    simulation_seed = _require_seed(values["simulation_seed"], "simulation_seed")
    requested_llm_seed = _require_seed(
        values["requested_llm_seed"],
        "requested_llm_seed",
    )
    python_hash_seed = _require_seed(values["python_hash_seed"], "python_hash_seed")
    llm_seed_supported = values["llm_seed_supported"]
    if llm_seed_supported not in LLM_SEED_SUPPORTED_VALUES:
        raise ReplicationStartupError("llm_seed_supported is invalid")
    output_dir = _require_non_empty_string(values["output_dir"], "output_dir")
    llm_mode = values["llm_mode"]
    if llm_mode not in LLM_MODES:
        raise ReplicationStartupError("llm_mode is invalid")
    _validate_formal_child_authorization(replication_id, llm_mode)

    return {
        "schema_version": REPLICATION_SCHEMA_VERSION,
        "replication_id": replication_id,
        "replicate_id": replicate_id,
        "replicate_index": replicate_index,
        "simulation_seed": simulation_seed,
        "requested_llm_seed": requested_llm_seed,
        "llm_seed_supported": llm_seed_supported,
        "python_hash_seed": python_hash_seed,
        "cache_scope": REPLICATION_CACHE_SCOPE,
        "execution_mode": REPLICATION_EXECUTION_MODE,
        "latest_policy": REPLICATION_LATEST_POLICY,
        "engineering_acceptance_only": llm_mode == "deterministic-mock",
        "output_dir": output_dir,
        "llm_mode": llm_mode,
    }


def _validate_formal_child_authorization(
    replication_id: str,
    llm_mode: str,
    environ=None,
) -> None:
    if not replication_id.startswith("task005-formal-") or llm_mode != "real":
        return
    env = os.environ if environ is None else environ
    for key in FORMAL_CHILD_AUTH_ENV:
        value = env.get(key)
        if not isinstance(value, str) or not value:
            raise ReplicationStartupError(
                "formal real child requires dedicated authorization provenance"
            )
    auth_sha = str(env["TASK005_FORMAL_AUTHORIZATION_SHA256"])
    activation_head = str(env["TASK005_FORMAL_ACTIVATION_CODE_HEAD"])
    launch_sha = str(env["TASK005_FORMAL_LAUNCH_CONTRACT_SHA256"])
    if len(auth_sha)!=64 or any(c not in "0123456789abcdefABCDEF" for c in auth_sha):
        raise ReplicationStartupError("formal authorization SHA is invalid")
    if len(activation_head)!=40 or any(c not in "0123456789abcdefABCDEF" for c in activation_head):
        raise ReplicationStartupError("formal activation code head is invalid")
    if len(launch_sha)!=64 or any(c not in "0123456789abcdefABCDEF" for c in launch_sha):
        raise ReplicationStartupError("formal launch contract SHA is invalid")

    expected = (Path(current_dir) / FORMAL_EXECUTION_AUTH_REL).resolve()
    try:
        auth_path = Path(env["TASK005_FORMAL_AUTHORIZATION_PATH"]).resolve()
    except Exception as exc:
        raise ReplicationStartupError("formal authorization path is invalid") from exc
    if auth_path != expected or not auth_path.is_file():
        raise ReplicationStartupError("formal authorization path mismatch")
    if hashlib.sha256(auth_path.read_bytes()).hexdigest().lower() != auth_sha.lower():
        raise ReplicationStartupError("formal authorization artifact SHA mismatch")
    try:
        authorization = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReplicationStartupError("formal authorization artifact is invalid") from exc
    if not isinstance(authorization, dict):
        raise ReplicationStartupError("formal authorization artifact must be an object")
    expected_pairs = {
        "schema_version": "1.1",
        "status": "frozen",
        "formal_batch_id": replication_id,
        "human_cost_time_authorized": True,
        "human_real_execution_authorized": True,
        "activation_code_head": activation_head,
        "formal_launch_contract_sha256": launch_sha,
    }
    for key, expected_value in expected_pairs.items():
        if authorization.get(key) != expected_value:
            raise ReplicationStartupError(
                f"formal authorization provenance mismatch: {key}"
            )


def _require_non_empty_string(value, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReplicationStartupError(f"{name} must be a non-empty string")
    return value


def _require_non_bool_int(value, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ReplicationStartupError(f"{name} must be a non-boolean integer")
    return value


def _require_seed(value, name: str) -> int:
    seed = _require_non_bool_int(value, name)
    if not (SEED_MIN <= seed <= SEED_MAX):
        raise ReplicationStartupError(f"{name} must be in [{SEED_MIN}, {SEED_MAX}]")
    return seed


def _validate_python_hash_seed(replication_context: dict, environ=None) -> None:
    env = os.environ if environ is None else environ
    expected = str(replication_context["python_hash_seed"])
    actual = env.get("PYTHONHASHSEED")
    if actual != expected:
        raise ReplicationStartupError("PYTHONHASHSEED must match ledger python_hash_seed")


def _preflight_replication_output_dir(replication_context: dict) -> Path:
    run_dir = Path(replication_context["output_dir"]).resolve()
    if not str(run_dir):
        raise ReplicationStartupError("output_dir must be non-empty")
    if run_dir.exists() and (not run_dir.is_dir() or any(run_dir.iterdir())):
        raise ReplicationStartupError("output_dir must be absent or empty")
    return run_dir


def _create_replication_run_dir(replication_context: dict) -> str:
    run_dir = _preflight_replication_output_dir(replication_context)
    run_dir.mkdir(parents=True, exist_ok=True)
    return str(run_dir)


def _ordered_experiment_configs(replication_context: dict | None = None) -> list[ExperimentConfig]:
    base_configs = generate_experiment_matrix()
    if replication_context is None:
        control_config = next(c for c in base_configs if c.is_control)
        strategy_configs = sorted((c for c in base_configs if not c.is_control), key=lambda c: c.exp_id)
        assert len(strategy_configs) == 8
        return [control_config] + strategy_configs

    simulation_seed = replication_context["simulation_seed"]
    configs = [replace(config, random_seed=simulation_seed) for config in base_configs]
    by_exp_id = {config.exp_id: config for config in configs}
    if len(configs) != 9 or set(by_exp_id) != set(REPLICATION_EXECUTION_ORDER):
        raise ReplicationStartupError("replication matrix exp_id set mismatch")
    ordered = [by_exp_id[exp_id] for exp_id in REPLICATION_EXECUTION_ORDER]
    if any(config.random_seed != simulation_seed for config in ordered):
        raise ReplicationStartupError("replication simulation_seed injection failed")
    if sum(1 for config in ordered if config.is_control) != 1:
        raise ReplicationStartupError("replication matrix must contain one control")
    if sum(1 for config in ordered if not config.is_control) != 8:
        raise ReplicationStartupError("replication matrix must contain eight strategies")
    return ordered


class _DeterministicMockRouter:
    _task005_router_close_noop = True

    async def chat(self, prompt: str) -> str:
        if "trust_change_affective" in prompt or "hypocrisy_perceived" in prompt:
            return json.dumps({
                "hypocrisy_perceived": True,
                "trust_change_affective": -1.5,
                "importance": 7.0,
                "reasoning": "Mock: betrayed.",
            })
        return json.dumps({
            "is_buying": False,
            "is_posting": True,
            "post_content": "Upset about this.",
            "reason": "Mock.",
        })


def _build_deterministic_mock_router():
    return _DeterministicMockRouter()


def _is_chat_capable_model_entry(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    capabilities = entry.get("capabilities")
    if not isinstance(capabilities, (list, tuple, set)):
        return False
    return "chat" in capabilities


def _config_with_requested_llm_seed(models_conf, requested_llm_seed: int):
    conf_copy = copy.deepcopy(models_conf)
    entries = conf_copy if isinstance(conf_copy, list) else [conf_copy]
    updated_count = 0
    for entry in entries:
        if _is_chat_capable_model_entry(entry):
            entry["seed"] = requested_llm_seed
            updated_count += 1
    if updated_count == 0:
        raise ReplicationStartupError(
            "no chat-capable model configuration accepted requested_llm_seed"
        )
    return conf_copy


def _build_real_router(requested_llm_seed: int | None = None):
    import yaml
    with open(os.path.join(current_dir, "configs/models_config.yaml"), "r", encoding="utf-8") as f:
        models_conf = yaml.safe_load(f)
    if requested_llm_seed is not None:
        models_conf = _config_with_requested_llm_seed(models_conf, requested_llm_seed)
    from agentkernel_standalone.toolkit.models.router import ModelRouter, AsyncModelRouter
    async_router = AsyncModelRouter(models_conf)
    router = ModelRouter(async_router)
    router._task005_async_router = async_router
    return router


async def _close_router_resource(router) -> None:
    if router is None or getattr(router, "_task005_router_close_noop", False):
        return

    if getattr(router, "_task005_router_close_attempted", False):
        return

    close_method = None
    for name in ("close", "aclose", "shutdown"):
        candidate = getattr(router, name, None)
        if callable(candidate):
            close_method = candidate
            break
    if close_method is None:
        inner = getattr(router, "_task005_async_router", None)
        candidate = getattr(inner, "close", None)
        if callable(candidate):
            close_method = candidate

    if close_method is None:
        raise AttributeError("router has no supported close/aclose/shutdown API")

    setattr(router, "_task005_router_close_attempted", True)
    result = close_method()
    if inspect.isawaitable(result):
        await result


def _build_router_for_mode(replication_context: dict | None = None):
    if replication_context is None:
        try:
            router = _build_real_router()
            print("🧠 LLM 引擎已就绪")
            return router
        except Exception:
            router = _build_deterministic_mock_router()
            print("⚠️  使用 Mock Router")
            return router

    if replication_context["llm_mode"] == "deterministic-mock":
        print("⚠️  使用 deterministic Mock Router")
        return _build_deterministic_mock_router()
    if replication_context["llm_mode"] == "real":
        try:
            router = _build_real_router(replication_context["requested_llm_seed"])
        except Exception as exc:
            raise ReplicationStartupError(
                f"real Router initialization failed: {type(exc).__name__}"
            ) from exc
        print("🧠 replication real LLM 引擎已就绪")
        return router
    raise ReplicationStartupError("llm_mode is invalid")


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

async def _run_with_patch(config: ExperimentConfig, override_router=None) -> dict:
    """
    在单事件策略下运行一组实验。
    临时 patch ENTERPRISE_STRATEGY → 只保留 Tick 5 漂绿丑闻。
    """
    import simulation_core as _sc
    original = _sc.ENTERPRISE_STRATEGY.copy()
    _sc.ENTERPRISE_STRATEGY.clear()
    _sc.ENTERPRISE_STRATEGY.update(_SINGLE_SCANDAL)
    try:
        return await run_simulation_core(config, override_router=override_router)
    finally:
        _sc.ENTERPRISE_STRATEGY.clear()
        _sc.ENTERPRISE_STRATEGY.update(original)


async def main(args=None):
    replication_context = build_replication_context(args) if args is not None else None
    if replication_context is not None:
        _validate_python_hash_seed(replication_context)
        _preflight_replication_output_dir(replication_context)

    print("=" * 65)
    print("GABM batch experiment - 8 clarification strategies + 1 common control")
    print("   Scandal : Tick 5 (single-event patch)")
    print("   Matrix  : 2(content) x 2(channel) x 2(timing) = 8 + common control = 9")
    print("   Replay  : common control records; strategies replay before clarification_tick")
    print("=" * 65)

    ordered_configs = _ordered_experiment_configs(replication_context)
    configs = ordered_configs
    total = len(configs)
    _real_router = _build_router_for_mode(replication_context)

    results = []
    errors  = []
    llm_cache: dict = {}   # 对照组建立后填入
    router_close_error: BaseException | None = None

    loop_exception = None
    try:
        for i, config in enumerate(ordered_configs, 1):
            is_recording = config.is_control
            role_label = ("[RECORDING control]" if is_recording
                          else f"[REPLAY until T{config.clarification_tick}]")

            print(f"\n{'─'*65}")
            print(f"  [{i}/{total}] 🚀 {config.exp_id}")
            print(f"    Content={config.content_factor} | Channel={config.channel_factor} "
                  f"| Timing={config.timing_factor} {role_label}")
            print(f"{'─'*65}")

            # ── TASK_002 审计插桩：计时点位于 _run_with_patch 之外，不进入仿真 ──
            run_audit = {
                "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "finished_at": "",
                "recording_cache_size": "",   # "" = 不适用；录制组=产出规模，回放组=消费规模
                "replay_miss_count": "",      # "" = 不适用（录制组无 ReplayRouter）；0 = 回放零 miss
                "router_role": "recording" if is_recording else "replay",
            }
            rp_router = None
            try:
                if is_recording:
                    # ── 唯一的录制组：建立全局 LLM 缓存 ────────────────────
                    rec_router = RecordingRouter(_real_router)
                    result = await _run_with_patch(config, override_router=rec_router)
                    llm_cache.update(rec_router.cache)
                    print(f"  📼 全局缓存已建立: {len(llm_cache)} 条 LLM 响应")
                    # 真实来源：RecordingRouter._cache（由 .cache 属性暴露）
                    run_audit["recording_cache_size"] = len(rec_router.cache)
                    # 录制组不存在 ReplayRouter → replay_miss_count 保持 ""，不写 0
                else:
                    assert config.clarification_tick is not None
                    clr_tick = config.clarification_tick
                    rp_router = ReplayRouter(
                        _real_router, llm_cache,
                        replay_until_tick=clr_tick,
                        exp_id=config.exp_id,
                    )
                    result = await _run_with_patch(config, override_router=rp_router)
                    # 真实来源：该组实际消费的缓存规模 + ReplayRouter.miss_count
                    run_audit["recording_cache_size"] = len(llm_cache)
                    run_audit["replay_miss_count"] = rp_router.miss_count

                run_audit["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                result["run_audit"] = run_audit
                results.append(result)

            except ReplayAlignmentError as e:
                error_msg = f"{config.exp_id}: {type(e).__name__}: {e}"
                print(f"  FAILED: {error_msg}")
                errors.append(error_msg)
                run_audit["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                run_audit["recording_cache_size"] = len(llm_cache)
                run_audit["replay_miss_count"] = e.miss_count
                results.append({"exp_id": config.exp_id,
                                "config": config.to_dict(),
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "run_audit": run_audit})
                continue

            except Exception as e:
                import traceback
                error_msg = f"{config.exp_id}: {type(e).__name__}: {e}"
                print(f"  ❌ FAILED: {error_msg}")
                traceback.print_exc()
                errors.append(error_msg)
                run_audit["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                if not is_recording:
                    run_audit["recording_cache_size"] = len(llm_cache)
                    run_audit["replay_miss_count"] = getattr(rp_router, "miss_count", 0)
                # R12：异常分支必须一并写入 config —— 只保存 exp_id + error 会丢掉
                #      "哪一组因子 / 什么 seed / 预算多少"，而失败实验恰恰最需要复现。
                #      ExperimentConfig.to_dict() 已核实存在，返回 asdict + exp_id + clarification_tick。
                results.append({"exp_id": config.exp_id,
                                "config": config.to_dict(),
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "run_audit": run_audit})

    except BaseException as exc:
        loop_exception = exc
    finally:
        try:
            await _close_router_resource(_real_router)
        except BaseException as exc:
            router_close_error = exc

    if loop_exception is not None:
        if router_close_error is not None:
            print(
                "WARNING: router close also failed: "
                f"{type(router_close_error).__name__}"
            )
        raise loop_exception

    if router_close_error is not None and not isinstance(router_close_error, Exception):
        raise router_close_error

    # ── 写入输出文件 ─────────────────────────────────────────────────
    # legacy creates run_<timestamp> and refreshes latest/; replication-child
    # writes directly into the parent runner's output_dir and disables latest.
    timestamp  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if replication_context is None:
        run_id = timestamp
        base_dir   = os.path.join(current_dir, "results", "experiments")
        run_dir    = os.path.join(base_dir, f"run_{timestamp}")
        latest_dir = os.path.join(base_dir, "latest")
        os.makedirs(run_dir,    exist_ok=True)
        os.makedirs(latest_dir, exist_ok=True)
    else:
        run_id = f"{replication_context['replication_id']}-{replication_context['replicate_id']}"
        run_dir = _create_replication_run_dir(replication_context)
        latest_dir = None

    postprocess_errors = []

    def _record_postprocess_error(stage: str, exc: Exception) -> None:
        msg = f"{stage}: {type(exc).__name__}: {exc}"
        postprocess_errors.append(msg)
        print(f"WARNING: {msg}")

    if router_close_error is not None:
        safe_close_error = RuntimeError(type(router_close_error).__name__)
        _record_postprocess_error("close router resource", safe_close_error)

    def _has_replay_miss(value) -> bool:
        return value not in ("", 0, "0", None)

    def _compute_final_status() -> tuple[int, bool]:
        replay_alignment_violated_now = any(
            _has_replay_miss((r.get("run_audit") or {}).get("replay_miss_count"))
            for r in results
        )
        successful_count_now = len([r for r in results if "error" not in r])
        ordinary_failure = (
            len(results) != total
            or successful_count_now != total
            or bool(errors)
            or bool(postprocess_errors)
        )
        if replay_alignment_violated_now:
            code = 4
        elif net_verification.get("status") != "consistent":
            code = 3
        elif ordinary_failure:
            code = 1
        else:
            code = 0
        completed = (
            code == 0
            and successful_count_now == 9
            and not errors
            and not postprocess_errors
        )
        return code, completed

    v4_ready = False
    try:
        attach_relative_metrics_v4(results)
        v4_ready = True
    except Exception as e:
        _record_postprocess_error("attach relative metrics v4", e)

    summary_path = os.path.join(run_dir, "summary.csv")
    if v4_ready:
        try:
            write_summary_csv(results, summary_path)
            print(f"\nsummary: {summary_path}")
        except Exception as e:
            v4_ready = False
            _record_postprocess_error("write summary.csv", e)

    if v4_ready:
        try:
            sensitivity_path = os.path.join(run_dir, "ranking_sensitivity.csv")
            robustness_path = os.path.join(run_dir, "ranking_robustness.csv")
            write_ranking_outputs_v4(results, sensitivity_path, robustness_path)
            print(f"ranking_sensitivity: {sensitivity_path}")
            print(f"ranking_robustness: {robustness_path}")
        except Exception as e:
            v4_ready = False
            _record_postprocess_error("write ranking outputs v4", e)

    trajectories_path = os.path.join(run_dir, "trajectories.csv")
    try:
        write_trajectories_csv(results, trajectories_path)
        print(f"trajectories: {trajectories_path}")
    except Exception as e:
        _record_postprocess_error("write trajectories.csv", e)

    agent_records_path = os.path.join(run_dir, "agent_records.csv")
    try:
        write_agent_records_csv(results, agent_records_path)
        print(f"agent_records: {agent_records_path}")
    except Exception as e:
        _record_postprocess_error("write agent_records.csv", e)

    mechanism_records_path = os.path.join(run_dir, "mechanism_records.csv")
    try:
        write_mechanism_records_csv(results, mechanism_records_path)
        print(f"mechanism_records: {mechanism_records_path}")
    except Exception as e:
        _record_postprocess_error("write mechanism_records.csv", e)

    clarification_exposure_path = os.path.join(
        run_dir, "clarification_exposure.csv"
    )
    try:
        write_clarification_exposure_csv(results, clarification_exposure_path)
        print(f"clarification_exposure: {clarification_exposure_path}")
    except Exception as e:
        _record_postprocess_error("write clarification_exposure.csv", e)

    target_nodes_path = os.path.join(run_dir, "target_nodes.csv")
    try:
        write_target_nodes_csv(results, target_nodes_path)
        print(f"target_nodes: {target_nodes_path}")
    except Exception as e:
        _record_postprocess_error("write target_nodes.csv", e)

    net_verification = {"status": "unavailable", "reason": "verify_single_network() failed before assignment"}
    try:
        net_verification = verify_single_network(results)
        network_nodes_path = os.path.join(run_dir, "network_nodes.csv")
        network_edges_path = os.path.join(run_dir, "network_edges.csv")
        if net_verification["status"] == "consistent":
            write_network_nodes_csv(results, network_nodes_path, net_verification)
            write_network_edges_csv(results, network_edges_path, net_verification)
            print(f"network_nodes: {network_nodes_path}")
            print(f"network_edges: {network_edges_path}")
            print(f"   network_hash: {net_verification['network_hash'][:12]} "
                  f"(source: {net_verification['source_exp_id']}, "
                  f"checked {net_verification['checked_experiments']} conditions)")
        else:
            report_path = os.path.join(run_dir, "network_inconsistency_report.json")
            write_network_inconsistency_report(net_verification, report_path)
            msg = (f"NETWORK CONSISTENCY {net_verification['status'].upper()}: "
                   f"{net_verification['reason']}; refused to write "
                   f"network_nodes.csv / network_edges.csv; see {report_path}")
            print("=" * 65)
            print(f"  FAIL: {msg}")
            print(f"     hash_groups: {net_verification.get('hash_groups', {})}")
            print("=" * 65)
            errors.append(msg)
    except Exception as e:
        net_verification = {"status": "unavailable", "reason": f"{type(e).__name__}: {e}"}
        _record_postprocess_error("verify/write network artifacts", e)

    exp_meta_path = os.path.join(run_dir, "experiment_metadata.jsonl")
    try:
        write_experiment_metadata_jsonl(results, exp_meta_path)
        print(f"experiment_metadata: {exp_meta_path}")
    except Exception as e:
        _record_postprocess_error("write experiment_metadata.jsonl", e)

    metadata_path = os.path.join(run_dir, "run_metadata.json")
    try:
        write_run_metadata_json(results, metadata_path,
                                project_root=current_dir, run_id=run_id,
                                network_verification=net_verification,
                                batch_exit_code=1,
                                run_completed=False,
                                replication_context=replication_context)
        print(f"run_metadata temporary: {metadata_path}")
    except Exception as e:
        _record_postprocess_error("write temporary run_metadata.json", e)

    successful = [r for r in results if "error" not in r]
    results_dir = run_dir
    if v4_ready and successful:
        # Pareto frontier and ranking are owned by analysis/plot_experiments.py.
        # The legacy plot_pareto.py entry is intentionally not called here.
        analysis_dir = os.path.join(current_dir, "analysis")
        if analysis_dir not in sys.path:
            sys.path.insert(0, analysis_dir)
        try:
            import plot_experiments as _pe
            import plot_trajectories as _pt_traj
            run_figures_dir = os.path.join(run_dir, "figures")
            os.makedirs(run_figures_dir, exist_ok=True)
            _pe.OUTPUT_DIR = run_figures_dir
            _pe.RESULTS_DIR = run_dir
            _pt_traj.OUTPUT_DIR = run_figures_dir
            _pt_traj.RESULTS_DIR = run_dir
            print("\ngenerating experiment figures...")
            df_exp = _pe.load_data(require_v4=True)
            _pe.plot_main_effects(df_exp)
            _pe.plot_heatmap_interactions(df_exp)
            _pe.plot_pareto_frontier(df_exp)
            _pe.plot_strategy_ranking(df_exp)
            _pe.plot_clarification_diagnosis(df_exp)
            _pe.plot_ranking_sensitivity_v4(df_exp)
            df_traj = _pt_traj.load_trajectories()
            _pt_traj.plot_timing_comparison(df_traj)
            _pt_traj.plot_content_channel_comparison(df_traj)
            _pt_traj.plot_all_9_conditions(df_traj)
            _pt_traj.plot_trust_recovery_zoom(df_traj)
            print(f"  figures: {run_figures_dir}")
        except Exception as e:
            _record_postprocess_error("plot experiment figures", e)

    def _write_errors_log() -> None:
        combined_errors = list(errors) + list(postprocess_errors)
        if not combined_errors:
            return
        error_path = os.path.join(run_dir, "errors.log")
        with open(error_path, "w", encoding="utf-8") as f:
            f.write(f"Experiment Errors - {datetime.datetime.now()}\n")
            f.write("=" * 50 + "\n")
            for err in combined_errors:
                f.write(f"  {err}\n")
        print(f"warnings/errors logged: {error_path}")

    try:
        _write_errors_log()
    except Exception as e:
        _record_postprocess_error("write errors.log", e)

    batch_exit_code, run_completed = _compute_final_status()
    try:
        write_run_metadata_json(results, metadata_path,
                                project_root=current_dir, run_id=run_id,
                                network_verification=net_verification,
                                batch_exit_code=batch_exit_code,
                                run_completed=run_completed,
                                replication_context=replication_context)
        print(f"run_metadata final: {metadata_path}")
    except Exception as e:
        _record_postprocess_error("write final run_metadata.json", e)
        batch_exit_code, run_completed = _compute_final_status()

    if replication_context is None:
        try:
            sync_latest_snapshot(run_dir, latest_dir, run_id, results, total)
            print(f"run_dir: {run_dir}")
            print(f"latest snapshot: {latest_dir}")
        except Exception as e:
            _record_postprocess_error("sync latest snapshot", e)
            batch_exit_code, run_completed = _compute_final_status()
            try:
                _write_errors_log()
                write_run_metadata_json(results, metadata_path,
                                        project_root=current_dir, run_id=run_id,
                                        network_verification=net_verification,
                                        batch_exit_code=batch_exit_code,
                                        run_completed=run_completed,
                                        replication_context=replication_context)
            except Exception as final_e:
                print(f"WARNING: final failure state could not be persisted: {type(final_e).__name__}: {final_e}")
    else:
        print(f"run_dir: {run_dir}")

    replay_alignment_violated = any(
        _has_replay_miss((r.get("run_audit") or {}).get("replay_miss_count"))
        for r in results
    )
    successful = [r for r in results if "error" not in r]
    print(f"\n{'='*65}")
    print(f"batch finished: {len(successful)}/{total} succeeded, {len(errors)}/{total} experiment errors, "
          f"{len(postprocess_errors)} postprocess errors")
    print(f"   result dir: {run_dir}")
    print(f"   batch_exit_code: {batch_exit_code}")
    print(f"   run_completed: {run_completed}")
    print(f"{'='*65}")

    if batch_exit_code != 0:
        if batch_exit_code == 4:
            print("FAIL: replay alignment violated; exit code 4")
            raise SystemExit(4)
        elif batch_exit_code == 3:
            print(f"FAIL: network consistency violation ({net_verification.get('status')}): "
                  f"{net_verification.get('reason')}")
            raise SystemExit(3)
        else:
            print("FAIL: one or more experiments/artifacts/plots failed; exit code 1")
            raise SystemExit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_cli_args()))
    except ReplicationStartupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
