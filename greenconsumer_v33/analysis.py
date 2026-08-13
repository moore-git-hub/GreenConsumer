"""Descriptive analysis for one TASK_005 v3.3.1 engineering block.

No p-values, confidence intervals or formal-sample extension are performed.
P4 is defined as the fraction of cognitive Agents that directly observed the
enterprise clarification during the configured delivery window t0..t0+lag.
The delivery lag is read from the run's parameter snapshot instead of being
hard-coded to one Tick.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from greenconsumer_v32.io import read_csv, write_csv, write_json

CONTROL = "NoClarification-Control"
ANALYSIS_SCHEMA = "task005_fmcg_v331_analysis1.0"


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
    return {tick: _mean(values) for tick, values in sorted(grouped.items()) if values}


def _normalized_trapezoid(series: dict[int, float], start: int, end: int) -> float:
    xs = [tick for tick in range(start, end + 1) if tick in series]
    if len(xs) != end - start + 1:
        raise ValueError(f"incomplete trajectory for AUC {start}-{end}: {xs}")
    area = 0.0
    for left, right in zip(xs[:-1], xs[1:]):
        area += 0.5 * (series[left] + series[right]) * (right - left)
    return area / float(end - start)


def _read_delivery_lag(run_dir: Path) -> int:
    path = run_dir / "run_summary.json"
    if not path.exists():
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    params = payload.get("clarification_v33_parameters") or {}
    lag = int(params.get("paid_delivery_lag", 1))
    if lag < 0:
        raise ValueError(f"paid_delivery_lag must be non-negative, got {lag}")
    return lag


def _lag_aware_direct_reach(
    rows: list[dict],
    delivery_lag: int,
) -> tuple[float, float, float]:
    """Return direct t0, lagged t0+lag and union direct-enterprise reach."""

    clr_ticks = {
        int(row["clarification_tick_config"])
        for row in rows
        if row.get("clarification_tick_config", "") not in ("", None)
    }
    if len(clr_ticks) != 1:
        raise ValueError(f"clarification tick is not unique: {clr_ticks}")
    t0 = next(iter(clr_ticks))
    lag = int(delivery_lag)
    agents = sorted({str(row["agent_id"]) for row in rows})
    n = len(agents)
    if not n:
        return float("nan"), float("nan"), float("nan")

    by_tick_agent = {
        (int(row["tick"]), str(row["agent_id"])): _as_bool(
            row.get("enterprise_clarification_observed")
        )
        for row in rows
    }
    direct = {agent for agent in agents if by_tick_agent.get((t0, agent), False)}
    lagged_tick = t0 + lag
    lagged = {
        agent for agent in agents if by_tick_agent.get((lagged_tick, agent), False)
    }
    union = direct | lagged
    return len(direct) / n, len(lagged) / n, len(union) / n


def _single_block_estimands(cognitive_by_condition, demand_rows, delivery_lag: int):
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
        return [], []

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

    rational = [x for x in strategy_ids if x.startswith("Rational-")]
    empathy = [x for x in strategy_ids if x.startswith("Empathy-")]
    immediate = [x for x in strategy_ids if x.endswith("-Immediate")]
    delayed = [x for x in strategy_ids if x.endswith("-Delayed")]
    hub = [x for x in strategy_ids if "-Hub-" in x]
    random = [x for x in strategy_ids if "-Random-" in x]

    reach_rows = []
    reach_union = {}
    for exp_id in strategy_ids:
        direct, lagged, union = _lag_aware_direct_reach(
            cognitive_by_condition[exp_id], delivery_lag
        )
        reach_union[exp_id] = union
        reach_rows.append(
            {
                "exp_id": exp_id,
                "delivery_lag": int(delivery_lag),
                "direct_reach_t0": direct,
                "lagged_reach_t0_plus_lag": lagged,
                "eventual_enterprise_reach": union,
                "note": (
                    "direct enterprise clarification only; excludes downstream "
                    "UGC persuasion"
                ),
            }
        )

    estimands = [
        {
            "estimand_id": "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
            "label": "Overall clarification vs control, post-crisis trust",
            "value": _mean(post_auc[x] for x in strategy_ids) - post_auc[CONTROL],
            "unit": "trust points",
            "analysis_role": "single-block descriptive only",
        },
        {
            "estimand_id": "P2_CONTENT_POST_TRUST_V33",
            "label": "Rational minus Empathy, post-crisis trust",
            "value": _mean(post_auc[x] for x in rational) - _mean(post_auc[x] for x in empathy),
            "unit": "trust points",
            "analysis_role": "single-block descriptive only",
        },
        {
            "estimand_id": "P3_TIMING_PRE_DELAY_TRUST_V33",
            "label": "Immediate minus Delayed, early trust T6-T9",
            "value": _mean(early_auc[x] for x in immediate) - _mean(early_auc[x] for x in delayed),
            "unit": "trust points",
            "analysis_role": "exploratory single-block descriptive only",
        },
        {
            "estimand_id": "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33",
            "label": (
                "Hub minus Random enterprise reach across configured delivery window"
            ),
            "value": _mean(reach_union[x] for x in hub) - _mean(reach_union[x] for x in random),
            "unit": "proportion",
            "analysis_role": "exploratory reach only; excludes persuasion/purchase",
        },
    ]

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
            metric = {x: _mean(choice_by_condition[x]) for x in required}
            estimands.append(
                {
                    "estimand_id": "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
                    "label": "Overall clarification vs control, expected repeat choice",
                    "value": _mean(metric[x] for x in strategy_ids) - metric[CONTROL],
                    "unit": "expected focal-brand choice share",
                    "analysis_role": "single-block descriptive only",
                }
            )

        support_deltas = []
        for exp_id in sorted(required):
            absent = support_by_condition[exp_id].get("absent", [])
            present = support_by_condition[exp_id].get("present", [])
            if absent and present:
                support_deltas.append(_mean(present) - _mean(absent))
        if support_deltas:
            estimands.append(
                {
                    "estimand_id": "S1_CONVERSION_SUPPORT_EXPECTED_REPEAT_CHOICE_V33",
                    "label": "Conversion support present minus absent",
                    "value": _mean(support_deltas),
                    "unit": "expected focal-brand choice share",
                    "analysis_role": "secondary descriptive only",
                }
            )

    return estimands, reach_rows


def analyze_run(run_dir: Path) -> dict:
    cognitive_path = run_dir / "cognitive_records.csv"
    demand_path = run_dir / "demand_opportunities.csv"
    if not cognitive_path.exists():
        raise FileNotFoundError(cognitive_path)

    cognitive = read_csv(cognitive_path)
    by_condition = defaultdict(list)
    for row in cognitive:
        by_condition[row["exp_id"]].append(row)

    summaries = []
    for exp_id, rows in sorted(by_condition.items()):
        t30 = [r for r in rows if int(r["tick"]) == 30]
        post = [r for r in rows if 6 <= int(r["tick"]) <= 30]
        summaries.append(
            {
                "exp_id": exp_id,
                "mean_trust_t30": _mean(float(r["trust_final"]) for r in t30),
                "mean_trust_t6_t30": _mean(float(r["trust_final"]) for r in post),
                "mean_purchase_intention_t30": _mean(
                    float(r["purchase_intention"]) for r in t30
                ),
            }
        )

    demand = read_csv(demand_path) if demand_path.exists() else []
    demand_summary = []
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
                    "mean_loyalty_after_t6_t30": _mean(
                        float(r["loyalty_after"]) for r in post
                    ),
                }
            )

    delivery_lag = _read_delivery_lag(run_dir)
    estimands, reach_rows = _single_block_estimands(
        dict(by_condition), demand, delivery_lag
    )
    write_csv(run_dir / "analysis_condition_summary.csv", summaries)
    write_csv(run_dir / "analysis_demand_summary.csv", demand_summary)
    write_csv(run_dir / "single_block_estimands.csv", estimands)
    write_csv(run_dir / "clarification_reach_v33.csv", reach_rows)

    payload = {
        "schema_version": ANALYSIS_SCHEMA,
        "status": "PASS",
        "scope": "single engineering/demo block; descriptive only",
        "conditions": len(by_condition),
        "delivery_lag": delivery_lag,
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "formal_reuse_permitted": False,
        "external_validity_claimed": False,
        "clarification_reach_definition": (
            "union of direct enterprise observations at t0 and t0+configured lag; "
            "excludes downstream UGC"
        ),
    }
    write_json(run_dir / "analysis_summary.json", payload)
    return payload
