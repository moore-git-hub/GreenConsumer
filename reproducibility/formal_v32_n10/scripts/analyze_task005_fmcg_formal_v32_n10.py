"""TASK_005 FMCG v3.2 N=10 frozen formal analysis.

Confirmatory:
- P1_OVERALL_CLARIFICATION_POST_TRUST_V32
- P2_CONTENT_POST_TRUST_V32
- P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V32
with block-level two-sided one-sample t-tests vs 0 and Holm FWER 0.05.

Exploratory/mechanistic only:
- P3_TIMING_PRE_DELAY_TRUST_V32
- P4_CHANNEL_REACH_V32
No p-values or confirmatory significance claims are produced for P3/P4.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path

from scipy.stats import t as student_t

ROOT = Path(__file__).resolve().parent
BATCH_ID = "task005-fmcg-v32-formal-n10"
DEFAULT_ROOT = ROOT / "results" / "formal" / BATCH_ID

ORDER = (
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

CONFIRMATORY = (
    "P1_OVERALL_CLARIFICATION_POST_TRUST_V32",
    "P2_CONTENT_POST_TRUST_V32",
    "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V32",
)
EXPLORATORY = (
    "P3_TIMING_PRE_DELAY_TRUST_V32",
    "P4_CHANNEL_REACH_V32",
)
MDE = {
    "P1_OVERALL_CLARIFICATION_POST_TRUST_V32": 0.15,
    "P2_CONTENT_POST_TRUST_V32": 0.15,
    "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V32": 0.05,
}


class AnalysisError(RuntimeError):
    pass


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AnalysisError(f"{path} must contain JSON object")
    return value


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise AnalysisError(f"empty output: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def mean(values) -> float:
    values = [float(x) for x in values]
    if not values:
        raise AnalysisError("mean requires values")
    return sum(values) / len(values)


def normalized_trapezoid(points: dict[int, float], start: int, end: int) -> float:
    ticks = range(start, end + 1)
    missing = [tick for tick in ticks if tick not in points]
    if missing:
        raise AnalysisError(f"missing trajectory ticks: {missing}")
    area = sum(
        (float(points[left]) + float(points[left + 1])) / 2.0
        for left in range(start, end)
    )
    return area / (end - start)


def factor(exp_id: str, name: str) -> str:
    if exp_id == "NoClarification-Control":
        return "control"
    if name == "content":
        return "rational" if exp_id.startswith("Rational-") else "empathy"
    if name == "timing":
        return "immediate" if exp_id.endswith("-Immediate") else "delayed"
    if name == "channel":
        return "hub" if "-Hub-" in exp_id else "random"
    raise ValueError(name)


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def block_estimands(block_dir: Path, block_id: str) -> dict:
    summary = read_json(block_dir / "block_summary.json")
    if summary.get("status") != "PASS":
        raise AnalysisError(f"{block_id}: block not valid")

    trajectory_rows = read_csv(block_dir / "trust_trajectories.csv")
    cognitive_rows = read_csv(block_dir / "cognitive_records.csv")
    demand_rows = read_csv(block_dir / "demand_opportunities.csv")

    trust = {exp_id: {} for exp_id in ORDER}
    for row in trajectory_rows:
        exp_id = row["exp_id"]
        if exp_id in trust:
            trust[exp_id][int(row["tick"])] = float(row["mean_trust"])
    if any(len(trust[exp_id]) != 30 for exp_id in ORDER):
        raise AnalysisError(f"{block_id}: incomplete trust trajectories")

    post_auc = {
        exp_id: normalized_trapezoid(trust[exp_id], 6, 30)
        for exp_id in ORDER
    }
    pre_delay_auc = {
        exp_id: normalized_trapezoid(trust[exp_id], 6, 9)
        for exp_id in ORDER
    }
    strategies = list(ORDER[1:])

    def avg_metric(metric, dimension=None, level=None):
        ids = strategies
        if dimension is not None:
            ids = [x for x in ids if factor(x, dimension) == level]
        return mean(metric[x] for x in ids)

    p1 = avg_metric(post_auc) - post_auc[ORDER[0]]
    p2 = (
        avg_metric(post_auc, "content", "rational")
        - avg_metric(post_auc, "content", "empathy")
    )
    p3 = (
        avg_metric(pre_delay_auc, "timing", "immediate")
        - avg_metric(pre_delay_auc, "timing", "delayed")
    )

    reach = {}
    for exp_id in strategies:
        clarification_tick = 6 if exp_id.endswith("-Immediate") else 10
        rows = [
            row
            for row in cognitive_rows
            if row["exp_id"] == exp_id
            and int(row["tick"]) == clarification_tick
        ]
        if len(rows) != 20:
            raise AnalysisError(
                f"{block_id}/{exp_id}: expected 20 rows at clarification tick"
            )
        reached_agents = {
            row["agent_id"]
            for row in rows
            if as_bool(row.get("enterprise_clarification_observed", False))
        }
        reach[exp_id] = len(reached_agents) / 20.0

    p4 = (
        avg_metric(reach, "channel", "hub")
        - avg_metric(reach, "channel", "random")
    )

    expected_choice = {}
    for exp_id in ORDER:
        rows = [
            row
            for row in demand_rows
            if row["exp_id"] == exp_id
            and row["conversion_support"] == "absent"
            and 6 <= int(row["tick"]) <= 30
        ]
        if not rows:
            raise AnalysisError(
                f"{block_id}/{exp_id}: no T6-T30 support-absent opportunities"
            )
        expected_choice[exp_id] = mean(
            float(row["choice_probability"]) for row in rows
        )

    p5 = avg_metric(expected_choice) - expected_choice[ORDER[0]]

    return {
        "formal_block_id": block_id,
        "P1_OVERALL_CLARIFICATION_POST_TRUST_V32": p1,
        "P2_CONTENT_POST_TRUST_V32": p2,
        "P3_TIMING_PRE_DELAY_TRUST_V32": p3,
        "P4_CHANNEL_REACH_V32": p4,
        "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V32": p5,
    }


def t_summary(values: list[float], estimand: str) -> dict:
    n = len(values)
    if n < 3:
        raise AnalysisError("confirmatory t-test requires at least 3 valid blocks")
    mu = statistics.mean(values)
    sd = statistics.stdev(values)
    se = sd / math.sqrt(n)
    df = n - 1
    if sd == 0:
        if mu == 0:
            t_stat = 0.0
            raw_p = 1.0
        else:
            t_stat = math.copysign(math.inf, mu)
            raw_p = 0.0
    else:
        t_stat = mu / se
        raw_p = float(2.0 * student_t.sf(abs(t_stat), df))
    critical = float(student_t.ppf(0.975, df))
    ci_low = mu - critical * se
    ci_high = mu + critical * se
    mde = float(MDE[estimand])
    return {
        "estimand": estimand,
        "N_valid_blocks": n,
        "mean": mu,
        "SD": sd,
        "SE": se,
        "df": df,
        "t_stat": t_stat,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "raw_p": raw_p,
        "managerial_MDE": mde,
        "managerially_relevant_by_abs_mean": abs(mu) >= mde,
    }


def holm_adjust(rows: list[dict], alpha: float = 0.05) -> list[dict]:
    ordered = sorted(enumerate(rows), key=lambda item: float(item[1]["raw_p"]))
    m = len(rows)
    running_adjusted = 0.0
    still_rejecting = True
    adjusted_by_index = {}
    reject_by_index = {}
    rank_by_index = {}
    for rank0, (original_index, row) in enumerate(ordered):
        multiplier = m - rank0
        candidate = min(1.0, multiplier * float(row["raw_p"]))
        running_adjusted = max(running_adjusted, candidate)
        adjusted_by_index[original_index] = running_adjusted
        rank_by_index[original_index] = rank0 + 1
        threshold = alpha / multiplier
        reject = still_rejecting and float(row["raw_p"]) <= threshold
        reject_by_index[original_index] = reject
        if not reject:
            still_rejecting = False

    output = []
    for index, row in enumerate(rows):
        copied = dict(row)
        copied["holm_rank"] = rank_by_index[index]
        copied["holm_adjusted_p"] = adjusted_by_index[index]
        copied["holm_reject_FWER_0_05"] = reject_by_index[index]
        copied["confirmatory_claim_permitted"] = True
        output.append(copied)
    return output


def exploratory_summary(values: list[float], estimand: str) -> dict:
    ordered = sorted(values)
    n = len(ordered)
    q = statistics.quantiles(ordered, n=4, method="inclusive") if n >= 2 else [ordered[0]] * 3
    return {
        "estimand": estimand,
        "N_valid_blocks": n,
        "mean": statistics.mean(ordered),
        "SD": statistics.stdev(ordered) if n >= 2 else 0.0,
        "median": statistics.median(ordered),
        "q1": q[0],
        "q3": q[2],
        "IQR": q[2] - q[0],
        "min": min(ordered),
        "max": max(ordered),
        "p_value_computed": False,
        "holm_included": False,
        "confirmatory_significance_claim_permitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("formal_root", nargs="?", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.formal_root.resolve()

    block_ids = [f"F{i:03d}" for i in range(1, 11)]
    completed = []
    invalid_or_missing = []
    for block_id in block_ids:
        block_dir = root / block_id
        summary_path = block_dir / "block_summary.json"
        if not summary_path.exists():
            invalid_or_missing.append(block_id)
            continue
        summary = read_json(summary_path)
        if summary.get("status") != "PASS":
            invalid_or_missing.append(block_id)
            continue
        completed.append(block_estimands(block_dir, block_id))

    if not completed:
        raise AnalysisError("no valid formal blocks available")

    write_csv(root / "formal_block_estimands.csv", completed)
    n_valid = len(completed)
    planned_n_achieved = n_valid == 10

    confirmatory_results = []
    if n_valid >= 3:
        confirmatory_results = holm_adjust(
            [
                t_summary(
                    [float(row[estimand]) for row in completed],
                    estimand,
                )
                for estimand in CONFIRMATORY
            ]
        )
        write_csv(root / "formal_confirmatory_results.csv", confirmatory_results)

    exploratory_results = [
        exploratory_summary(
            [float(row[estimand]) for row in completed],
            estimand,
        )
        for estimand in EXPLORATORY
    ]
    write_csv(root / "formal_exploratory_results.csv", exploratory_results)

    summary = {
        "schema_version": "task005_fmcg_v32_formal_analysis_result1.0",
        "formal_batch_id": BATCH_ID,
        "status": (
            "PASS_PLANNED_N_ACHIEVED"
            if planned_n_achieved
            else "COMPLETE_WITH_PLANNED_N_NOT_ACHIEVED"
        ),
        "planned_attempt_blocks": 10,
        "valid_blocks": n_valid,
        "planned_N_achieved": planned_n_achieved,
        "valid_formal_block_ids": [
            row["formal_block_id"] for row in completed
        ],
        "invalid_or_missing_frozen_block_ids": invalid_or_missing,
        "replacement_blocks_added": False,
        "confirmatory_family": list(CONFIRMATORY),
        "confirmatory_test": (
            "block-level two-sided one-sample t-test vs 0; "
            "Holm FWER 0.05 across exactly P1/P2/P5"
        ),
        "confirmatory_analysis_available": n_valid >= 3,
        "exploratory_family": list(EXPLORATORY),
        "P3_P4_p_values_computed": False,
        "engineering_blocks_reused": False,
        "natural_trust_recovery_allowed": True,
        "formal_result_interpretation_scope": (
            "stochastic replication uncertainty within the frozen GABM; "
            "not direct validation of real-world population effects"
        ),
    }
    write_json(root / "formal_analysis_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
