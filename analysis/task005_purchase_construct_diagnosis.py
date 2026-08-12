"""Offline diagnosis and construct-only replay of TASK_005 purchase outcomes.

The script reads the frozen v2 variance pilot, computes no p-values, chooses no
winner and writes no model parameter.  Its v3 replay only separates recurring
purchase opportunities from focal-brand choice while retaining the v2 TPB
purchase intentions exactly as observed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import purchase_mechanism_v3 as p3
from mechanism_v2 import PURCHASE_OPPORTUNITY_RATE


EXPECTED_REPLICATES = tuple(f"R{i:03d}" for i in range(1, 11))
CONTROL_ID = "NoClarification-Control"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("mean requires at least one value")
    return statistics.fmean(values)


def _summary(values: list[float]) -> dict[str, Any]:
    return {
        "n_blocks": len(values),
        "mean": _mean(values),
        "sd": statistics.stdev(values) if len(values) > 1 else None,
        "min": min(values),
        "max": max(values),
        "positive_blocks": sum(value > 0 for value in values),
        "zero_blocks": sum(abs(value) < 1e-12 for value in values),
        "negative_blocks": sum(value < 0 for value in values),
        "values": values,
    }


def _bool(value: str) -> bool:
    return str(value).strip().lower() == "true"


def _cumulative_buy_share(rows: list[dict[str, Any]], through_tick: int) -> float:
    agents = {row["agent_id"] for row in rows}
    buyers = {
        row["agent_id"]
        for row in rows
        if row["tick"] <= through_tick and row["is_buying"]
    }
    return len(buyers) / len(agents)


def _v3_choice_metrics(rows: list[dict[str, Any]], seed: int) -> dict[str, float | int]:
    expected: list[float] = []
    realized: list[float] = []
    agents = {row["agent_id"] for row in rows}
    for row in rows:
        choice = p3.purchase_choice(
            seed=seed,
            agent_id=row["agent_id"],
            tick=row["tick"],
            purchase_intention=row["purchase_intention"],
        )
        if not choice.opportunity:
            continue
        assert choice.choice_probability is not None
        expected.append(choice.choice_probability)
        realized.append(float(choice.focal_brand_chosen))
    if not expected:
        raise ValueError("v3 replay produced no purchase opportunities")
    return {
        "agents": len(agents),
        "opportunities": len(expected),
        "expected_choice_share": _mean(expected),
        "realized_choice_share": _mean(realized),
    }


def _load_block(root: Path, replicate_id: str) -> tuple[int, dict[str, list[dict[str, Any]]]]:
    block = root / replicate_id
    ledger = _read_csv(block / "seed_ledger.csv")
    if len(ledger) != 1:
        raise ValueError(f"{replicate_id} seed ledger must have one row")
    seed = int(ledger[0]["simulation_seed"])
    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in _read_csv(block / "mechanism_records.csv"):
        row: dict[str, Any] = dict(raw)
        row["tick"] = int(raw["tick"])
        row["is_buying"] = _bool(raw["is_buying"])
        for field in (
            "purchase_intention",
            "buy_probability",
            "trust_final",
            "attitude_att",
            "subjective_norm_sn",
            "pbc",
        ):
            row[field] = float(raw[field])
        by_condition[row["exp_id"]].append(row)
    if CONTROL_ID not in by_condition or len(by_condition) != 9:
        raise ValueError(f"{replicate_id} must contain one control and eight strategies")
    return seed, dict(by_condition)


def build_report(variance_root: Path, contract_path: Path) -> dict[str, Any]:
    block_rows: list[dict[str, Any]] = []
    for replicate_id in EXPECTED_REPLICATES:
        seed, conditions = _load_block(variance_root, replicate_id)
        control = conditions[CONTROL_ID]
        strategy_sets = [rows for exp_id, rows in conditions.items() if exp_id != CONTROL_ID]

        control_pre4 = _cumulative_buy_share(control, 4)
        strategy_pre4 = _mean([_cumulative_buy_share(rows, 4) for rows in strategy_sets])
        control_t30 = _cumulative_buy_share(control, 30)
        strategy_t30 = _mean([_cumulative_buy_share(rows, 30) for rows in strategy_sets])

        def post_mean(rows: list[dict[str, Any]], field: str) -> float:
            return _mean([row[field] for row in rows if 6 <= row["tick"] <= 30])

        control_intention = post_mean(control, "purchase_intention")
        strategy_intention = _mean(
            [post_mean(rows, "purchase_intention") for rows in strategy_sets]
        )
        control_daily_buy_probability = post_mean(control, "buy_probability")
        strategy_daily_buy_probability = _mean(
            [post_mean(rows, "buy_probability") for rows in strategy_sets]
        )

        control_v3 = _v3_choice_metrics(control, seed)
        strategy_v3 = [_v3_choice_metrics(rows, seed) for rows in strategy_sets]
        strategy_opportunities = {int(row["opportunities"]) for row in strategy_v3}
        if strategy_opportunities != {int(control_v3["opportunities"])}:
            raise ValueError(f"{replicate_id} v3 opportunity counts differ by condition")

        block_rows.append(
            {
                "replicate_id": replicate_id,
                "pre_tick5_control_cumulative_buy_share": control_pre4,
                "pre_tick5_strategy_cumulative_buy_share": strategy_pre4,
                "v2_control_cumulative_buy_share_t30": control_t30,
                "v2_strategy_cumulative_buy_share_t30": strategy_t30,
                "v2_p5_contrast": strategy_t30 - control_t30,
                "post_crisis_control_purchase_intention": control_intention,
                "post_crisis_strategy_purchase_intention": strategy_intention,
                "latent_intention_contrast": strategy_intention - control_intention,
                "eligible_daily_probability_contrast": (
                    PURCHASE_OPPORTUNITY_RATE
                    * (strategy_intention - control_intention)
                ),
                "post_crisis_control_daily_buy_probability": control_daily_buy_probability,
                "post_crisis_strategy_daily_buy_probability": strategy_daily_buy_probability,
                "daily_probability_contrast": (
                    strategy_daily_buy_probability - control_daily_buy_probability
                ),
                "v3_opportunities_per_condition": int(control_v3["opportunities"]),
                "v3_control_expected_choice_share": float(
                    control_v3["expected_choice_share"]
                ),
                "v3_strategy_expected_choice_share": _mean(
                    [float(row["expected_choice_share"]) for row in strategy_v3]
                ),
                "v3_expected_choice_contrast": _mean(
                    [float(row["expected_choice_share"]) for row in strategy_v3]
                )
                - float(control_v3["expected_choice_share"]),
                "v3_control_realized_choice_share": float(
                    control_v3["realized_choice_share"]
                ),
                "v3_strategy_realized_choice_share": _mean(
                    [float(row["realized_choice_share"]) for row in strategy_v3]
                ),
                "v3_realized_choice_contrast": _mean(
                    [float(row["realized_choice_share"]) for row in strategy_v3]
                )
                - float(control_v3["realized_choice_share"]),
            }
        )

    def values(field: str) -> list[float]:
        return [float(row[field]) for row in block_rows]

    pre_control = values("pre_tick5_control_cumulative_buy_share")
    control_ceiling = values("v2_control_cumulative_buy_share_t30")
    latent = values("latent_intention_contrast")
    eligible_daily = values("eligible_daily_probability_contrast")
    daily = values("daily_probability_contrast")
    v3_expected = values("v3_expected_choice_contrast")
    v3_realized = values("v3_realized_choice_contrast")

    return {
        "schema_version": "task005_purchase_construct_diagnosis1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "post_hoc_descriptive_construct_diagnosis",
        "source": {
            "pilot_id": "task005-real-variance-pilot-v3",
            "replication_blocks": len(EXPECTED_REPLICATES),
            "real_llm_calls_added": 0,
            "all_block_estimands_sha256": _sha256(
                variance_root / "all_block_estimands.csv"
            ),
            "contract_path": str(contract_path.relative_to(ROOT)),
            "contract_sha256": _sha256(contract_path),
        },
        "firewall": {
            "p_values": False,
            "formal_inference": False,
            "winner_selection": False,
            "coefficient_tuning": False,
            "v2_rows_reusable_for_v3_formal": False,
        },
        "v2_construct_diagnosis": {
            "mean_cumulative_purchase_before_scandal": _mean(pre_control),
            "mean_control_cumulative_purchase_t30": _mean(control_ceiling),
            "p5_contrast": _summary(values("v2_p5_contrast")),
            "latent_purchase_intention_contrast": _summary(latent),
            "eligible_nonabsorbing_daily_probability_contrast": _summary(
                eligible_daily
            ),
            "stateful_daily_buy_probability_contrast": _summary(daily),
            "frozen_v2_purchase_opportunity_rate": PURCHASE_OPPORTUNITY_RATE,
            "mean_compression_ratio_eligible_probability_to_intention": (
                _mean(eligible_daily) / _mean(latent)
            ),
            "mean_compression_ratio_stateful_probability_to_intention": (
                _mean(daily) / _mean(latent)
            ),
            "mean_absorbing_state_attenuation_ratio": (
                _mean(daily) / _mean(eligible_daily)
            ),
            "verdict": "RETIRE_PURCHASE_RATE_T30_AS_CAUSAL_PURCHASE_ENDPOINT"
        },
        "v3_construct_only_replay": {
            "opportunity_interval_ticks": p3.DEFAULT_OPPORTUNITY_INTERVAL_TICKS,
            "opportunities_condition_invariant": True,
            "pre_crisis_opportunities_in_estimand": 0,
            "expected_choice_contrast": _summary(v3_expected),
            "realized_choice_contrast": _summary(v3_realized),
            "interpretation": (
                "The replay changes only the purchase construct. It retains observed v2 "
                "TPB intentions and cannot validate a v3 treatment effect."
            ),
        },
        "block_diagnostics": block_rows,
        "decision_rules": {
            "formal_v2_execution": "HOLD_AND_SUPERSEDE_IF_V3_ADOPTED",
            "real_llm_pilot": "NOT_AUTHORIZED_BY_THIS_REPORT",
            "next_required_decision": "freeze final scenario: FMCG repeat purchase or NEV adoption",
            "significance_claim": "PROHIBITED"
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variance_root", type=Path)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.variance_root.resolve(), args.contract.resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
