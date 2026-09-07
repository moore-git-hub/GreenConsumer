"""engineering/demo run 的描述性分析。

正式 F001-F010 的统计推断已经冻结并归档。本模块只为新的 engineering/demo
run 计算描述统计，以及与正式 estimand 定义一致的“单 block 描述性对应量”。
这里绝不计算 p-value、置信区间、Holm 校正，也不把一个 preview block 当成
新的正式 replication。
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .io import read_csv, write_csv, write_json


CONTROL = "NoClarification-Control"


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else float("nan")


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _tick_means(rows: list[dict], field: str) -> dict[int, float]:
    grouped = defaultdict(list)
    for row in rows:
        value = row.get(field, "")
        if value in ("", None):
            continue
        grouped[int(row["tick"])].append(float(value))
    return {
        tick: _mean(values)
        for tick, values in sorted(grouped.items())
        if values
    }


def _normalized_trapezoid(series: dict[int, float], start: int, end: int) -> float:
    """Normalized trapezoidal AUC over an inclusive tick window.

    The formal v3.2 trust estimands use a normalized trapezoidal AUC. This helper
    mirrors that definition for a *single engineering block* only.
    """
    xs = [tick for tick in range(start, end + 1) if tick in series]
    if len(xs) < 2:
        raise ValueError(f"insufficient trajectory points for AUC {start}-{end}: {xs}")
    if xs[0] != start or xs[-1] != end or len(xs) != end - start + 1:
        raise ValueError(f"incomplete trajectory for AUC {start}-{end}: {xs}")
    area = 0.0
    for left, right in zip(xs[:-1], xs[1:]):
        area += 0.5 * (series[left] + series[right]) * (right - left)
    return area / float(end - start)


def _single_block_estimands(
    cognitive_by_condition: dict[str, list[dict]],
    demand_rows: list[dict],
) -> list[dict]:
    """Compute descriptive analogues of P1-P5 for one engineering block.

    These values are useful for checking direction/magnitude and for plotting.
    They have *no sampling uncertainty estimate* because there is only one block.
    """
    required = {
        CONTROL,
        "Rational-Hub-Immediate",
        "Rational-Hub-Delayed",
        "Rational-Random-Immediate",
        "Rational-Random-Delayed",
        "Empathy-Hub-Immediate",
        "Empathy-Hub-Delayed",
        "Empathy-Random-Immediate",
        "Empathy-Random-Delayed",
    }
    if not required.issubset(cognitive_by_condition):
        return []

    strategy_ids = sorted(required - {CONTROL})
    trust_series = {
        exp_id: _tick_means(cognitive_by_condition[exp_id], "trust_final")
        for exp_id in required
    }
    post_auc = {
        exp_id: _normalized_trapezoid(series, 6, 30)
        for exp_id, series in trust_series.items()
    }
    early_auc = {
        exp_id: _normalized_trapezoid(series, 6, 9)
        for exp_id, series in trust_series.items()
    }

    rational = [exp_id for exp_id in strategy_ids if exp_id.startswith("Rational-")]
    empathy = [exp_id for exp_id in strategy_ids if exp_id.startswith("Empathy-")]
    immediate = [exp_id for exp_id in strategy_ids if exp_id.endswith("-Immediate")]
    delayed = [exp_id for exp_id in strategy_ids if exp_id.endswith("-Delayed")]
    hub = [exp_id for exp_id in strategy_ids if "-Hub-" in exp_id]
    random = [exp_id for exp_id in strategy_ids if "-Random-" in exp_id]

    # Reach = fraction of cognitive agents that actually observed the enterprise
    # clarification at that condition's own clarification tick.
    reach = {}
    for exp_id in strategy_ids:
        rows = cognitive_by_condition[exp_id]
        clr_ticks = {
            int(row["clarification_tick_config"])
            for row in rows
            if row.get("clarification_tick_config", "") not in ("", None)
        }
        if len(clr_ticks) != 1:
            raise ValueError(f"{exp_id}: clarification tick is not unique: {clr_ticks}")
        clr_tick = next(iter(clr_ticks))
        at_tick = [row for row in rows if int(row["tick"]) == clr_tick]
        reach[exp_id] = _mean(
            1.0 if _as_bool(row.get("enterprise_clarification_observed")) else 0.0
            for row in at_tick
        )

    rows = [
        {
            "estimand_id": "P1_OVERALL_CLARIFICATION_POST_TRUST_V32",
            "label": "Overall clarification vs control, post-crisis trust",
            "value": _mean(post_auc[exp_id] for exp_id in strategy_ids) - post_auc[CONTROL],
            "unit": "trust points",
            "analysis_role": "confirmatory-family analogue; single-block descriptive only",
        },
        {
            "estimand_id": "P2_CONTENT_POST_TRUST_V32",
            "label": "Rational minus Empathy, post-crisis trust",
            "value": _mean(post_auc[exp_id] for exp_id in rational) - _mean(
                post_auc[exp_id] for exp_id in empathy
            ),
            "unit": "trust points",
            "analysis_role": "confirmatory-family analogue; single-block descriptive only",
        },
        {
            "estimand_id": "P3_TIMING_PRE_DELAY_TRUST_V32",
            "label": "Immediate minus Delayed, early trust T6-T9",
            "value": _mean(early_auc[exp_id] for exp_id in immediate) - _mean(
                early_auc[exp_id] for exp_id in delayed
            ),
            "unit": "trust points",
            "analysis_role": "exploratory analogue; single-block descriptive only",
        },
        {
            "estimand_id": "P4_CHANNEL_REACH_V32",
            "label": "Hub minus Random clarification reach",
            "value": _mean(reach[exp_id] for exp_id in hub) - _mean(
                reach[exp_id] for exp_id in random
            ),
            "unit": "proportion",
            "analysis_role": "exploratory mechanism analogue; reach only",
        },
    ]

    # P5 needs the downstream demand layer, support absent only.
    if demand_rows:
        choice_by_condition = defaultdict(list)
        support_by_condition = defaultdict(lambda: defaultdict(list))
        for row in demand_rows:
            tick = int(row["tick"])
            if not 6 <= tick <= 30:
                continue
            exp_id = str(row["exp_id"])
            support = str(row["conversion_support"])
            p = float(row["choice_probability"])
            support_by_condition[exp_id][support].append(p)
            if support == "absent":
                choice_by_condition[exp_id].append(p)

        if required.issubset(choice_by_condition):
            choice_metric = {
                exp_id: _mean(choice_by_condition[exp_id])
                for exp_id in required
            }
            rows.append(
                {
                    "estimand_id": "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V32",
                    "label": "Overall clarification vs control, expected repeat choice",
                    "value": _mean(choice_metric[exp_id] for exp_id in strategy_ids)
                    - choice_metric[CONTROL],
                    "unit": "expected focal-brand choice share",
                    "analysis_role": "confirmatory-family analogue; single-block descriptive only",
                }
            )

        # Secondary conversion-support contrast; kept separate from P1-P5.
        support_deltas = []
        for exp_id in sorted(required):
            absent = support_by_condition[exp_id].get("absent", [])
            present = support_by_condition[exp_id].get("present", [])
            if absent and present:
                support_deltas.append(_mean(present) - _mean(absent))
        if support_deltas:
            rows.append(
                {
                    "estimand_id": "S1_CONVERSION_SUPPORT_EXPECTED_REPEAT_CHOICE_V32",
                    "label": "Conversion support present minus absent",
                    "value": _mean(support_deltas),
                    "unit": "expected focal-brand choice share",
                    "analysis_role": "secondary descriptive only",
                }
            )

    return rows


def analyze_run(run_dir: Path) -> dict:
    """Generate descriptive summaries for one engineering/demo run."""
    cognitive_path = run_dir / "cognitive_records.csv"
    demand_path = run_dir / "demand_opportunities.csv"
    if not cognitive_path.exists():
        raise FileNotFoundError(cognitive_path)

    cognitive = read_csv(cognitive_path)
    by_condition = defaultdict(list)
    for row in cognitive:
        by_condition[row["exp_id"]].append(row)

    # Cognitive layer: final trust, post-crisis trust and final TPB states.
    summaries = []
    for exp_id, rows in sorted(by_condition.items()):
        t30 = [r for r in rows if int(r["tick"]) == 30]
        post = [r for r in rows if 6 <= int(r["tick"]) <= 30]
        summaries.append(
            {
                "exp_id": exp_id,
                "mean_trust_t30": _mean(float(r["trust_final"]) for r in t30),
                "mean_trust_t6_t30": _mean(float(r["trust_final"]) for r in post),
                "mean_attitude_t30": _mean(float(r["attitude_att"]) for r in t30),
                "mean_subjective_norm_t30": _mean(float(r["subjective_norm_after"]) for r in t30),
                "mean_pbc_t30": _mean(float(r["pbc"]) for r in t30),
                "mean_purchase_intention_t30": _mean(float(r["purchase_intention"]) for r in t30),
            }
        )

    demand_summary = []
    demand = read_csv(demand_path) if demand_path.exists() else []
    if demand:
        grouped = defaultdict(list)
        for row in demand:
            grouped[(row["exp_id"], row["conversion_support"])].append(row)

        for (exp_id, support), rows in sorted(grouped.items()):
            post = [r for r in rows if 6 <= int(r["tick"]) <= 30]
            demand_summary.append(
                {
                    "exp_id": exp_id,
                    "conversion_support": support,
                    "opportunities_t6_t30": len(post),
                    "expected_choice_share_t6_t30": _mean(
                        float(r["choice_probability"]) for r in post
                    ),
                    "realized_choice_share_t6_t30": _mean(
                        1.0 if _as_bool(r["focal_brand_chosen"]) else 0.0
                        for r in post
                    ),
                    "mean_purchase_intention_t6_t30": _mean(
                        float(r["purchase_intention"]) for r in post
                    ),
                    "mean_loyalty_after_t6_t30": _mean(
                        float(r["loyalty_after"]) for r in post
                    ),
                }
            )

    estimands = _single_block_estimands(dict(by_condition), demand)

    write_csv(run_dir / "analysis_condition_summary.csv", summaries)
    write_csv(run_dir / "analysis_demand_summary.csv", demand_summary)
    write_csv(run_dir / "single_block_estimands.csv", estimands)

    payload = {
        "schema_version": "task005_fmcg_v32_clean_analysis1.2",
        "status": "PASS",
        "scope": "single engineering/demo block; descriptive only",
        "conditions": len(by_condition),
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "holm_adjustment_performed": False,
        "formal_reuse_permitted": False,
        "condition_summary_csv": "analysis_condition_summary.csv",
        "demand_summary_csv": "analysis_demand_summary.csv" if demand_summary else None,
        "single_block_estimands_csv": "single_block_estimands.csv" if estimands else None,
    }
    write_json(run_dir / "analysis_summary.json", payload)
    return payload
