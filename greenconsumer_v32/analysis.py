from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .io import read_csv, write_csv, write_json


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else float("nan")


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
    for exp_id, rows in by_condition.items():
        t30 = [float(r["trust_final"]) for r in rows if int(r["tick"]) == 30]
        post = [float(r["trust_final"]) for r in rows if 6 <= int(r["tick"]) <= 30]
        summaries.append(
            {
                "exp_id": exp_id,
                "mean_trust_t30": _mean(t30),
                "mean_trust_t6_t30": _mean(post),
            }
        )

    demand_summary = []
    if demand_path.exists():
        demand = read_csv(demand_path)
        grouped = defaultdict(list)
        for row in demand:
            grouped[(row["exp_id"], row["conversion_support"])].append(row)
        for (exp_id, support), rows in grouped.items():
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
                        1.0
                        if str(r["focal_brand_chosen"]).lower() == "true"
                        else 0.0
                        for r in post
                    ),
                }
            )

    write_csv(run_dir / "analysis_condition_summary.csv", summaries)
    write_csv(run_dir / "analysis_demand_summary.csv", demand_summary)
    payload = {
        "schema_version": "task005_fmcg_v32_clean_analysis1.0",
        "status": "PASS",
        "scope": "descriptive engineering/demo analysis only",
        "conditions": len(by_condition),
        "formal_inference_performed": False,
        "condition_summary_csv": "analysis_condition_summary.csv",
        "demand_summary_csv": (
            "analysis_demand_summary.csv" if demand_summary else None
        ),
    }
    write_json(run_dir / "analysis_summary.json", payload)
    return payload
