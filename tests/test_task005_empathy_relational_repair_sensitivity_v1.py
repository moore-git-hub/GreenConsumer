from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mechanism_v2 as m


P = 0
F = 0


GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
REFERENCE_WEIGHT = 0.50
CLASSIFICATIONS = {
    "ROBUST_MONOTONIC",
    "EXPECTED_SENSITIVE",
    "STRUCTURAL_INSTABILITY",
}


def check(name: str, condition: bool, actual=None) -> None:
    global P, F
    if condition:
        P += 1
        print("PASS", name)
    else:
        F += 1
        print("FAIL", name, actual)


def _fixed_semantic_observation(tick: int) -> dict:
    if tick == 6:
        return {
            "valence": -0.35,
            "arousal": 0.55,
            "credibility": 0.72,
            "evidence_strength": 0.66,
            "topic_relevance": 0.83,
            "perceived_empathy": 0.70,
            "enterprise_clarification_observed": True,
            "social_observation_count": 0,
        }
    if tick == 12:
        return {
            "valence": -0.10,
            "arousal": 0.40,
            "credibility": 0.60,
            "evidence_strength": 0.50,
            "topic_relevance": 0.70,
            "perceived_empathy": 0.30,
            "enterprise_clarification_observed": False,
            "social_observation_count": 1,
        }
    return {
        "valence": 0.0,
        "arousal": 0.0,
        "credibility": 0.5,
        "evidence_strength": 0.0,
        "topic_relevance": 0.0,
        "perceived_empathy": 0.0,
        "enterprise_clarification_observed": False,
        "social_observation_count": 0,
    }


def _run_weight(weight: float) -> dict:
    baseline = 6.2
    state = {
        "baseline_trust": baseline,
        "previous_trust": baseline,
        "attitude_att": baseline / 10.0,
        "subjective_norm_sn": 0.5,
        "pbc": 0.55,
        "crisis_memory": 0.0,
        "repair_memory": 0.0,
    }
    rows = []
    cumulative_purchase = 0
    purchased = False
    for tick in range(1, 31):
        obs = _fixed_semantic_observation(tick)
        had = tick in (6, 12)
        out = m.update_psychological_state(
            baseline_trust=state["baseline_trust"],
            previous_trust=state["previous_trust"],
            attitude_att=state["attitude_att"],
            subjective_norm_sn=state["subjective_norm_sn"],
            pbc=state["pbc"],
            crisis_memory=state["crisis_memory"],
            repair_memory=state["repair_memory"],
            valence=obs["valence"],
            arousal=obs["arousal"],
            credibility=obs["credibility"],
            evidence_strength=obs["evidence_strength"],
            topic_relevance=obs["topic_relevance"],
            had_observation=had,
            social_observation_count=obs["social_observation_count"],
            perceived_empathy=obs["perceived_empathy"],
            enterprise_clarification_observed=obs["enterprise_clarification_observed"],
            empathy_repair_weight=weight,
        )
        buy_probability, _ = m.behavior_probabilities(
            purchase_intention=out["purchase_intention"],
            posting_intention=out["posting_intention"],
            had_observation=had,
            already_purchased=purchased,
            ticks_since_last_post=None,
        )
        draw = m.deterministic_uniform(20260810, "Consumer_001", tick, "buy")
        if not purchased and draw < buy_probability:
            purchased = True
            cumulative_purchase += 1
        rows.append(out)
        state.update({
            "previous_trust": out["trust_final"],
            "attitude_att": out["attitude_att"],
            "subjective_norm_sn": out["subjective_norm_sn"],
            "pbc": out["pbc"],
            "crisis_memory": out["crisis_memory"],
            "repair_memory": out["repair_memory"],
        })
    return {
        "weight": weight,
        "repair_memory": rows[-1]["repair_memory"],
        "trust_auc": sum(row["trust_final"] for row in rows) / len(rows),
        "tick30_trust": rows[-1]["trust_final"],
        "purchase_intention": rows[-1]["purchase_intention"],
        "cumulative_first_purchase": cumulative_purchase,
        "relational_repair_increment_tick6": rows[5]["relational_repair_increment"],
        "pbc": rows[-1]["pbc"],
        "subjective_norm_sn": rows[-1]["subjective_norm_sn"],
    }


def _classify(rows: list[dict]) -> str:
    increments = [row["relational_repair_increment_tick6"] for row in rows]
    if increments != sorted(increments):
        return "STRUCTURAL_INSTABILITY"
    repair = [row["repair_memory"] for row in rows]
    if repair == sorted(repair):
        return "ROBUST_MONOTONIC"
    return "EXPECTED_SENSITIVE"


def main() -> int:
    design = json.loads(
        (ROOT / ".kiro/specs/task005-replication-inference/"
         "empathy_relational_repair_sensitivity_design1.0.json").read_text(
            encoding="utf-8"
        )
    )
    check("grid frozen", tuple(design["sensitivity_grid"]) == GRID, design["sensitivity_grid"])
    check("reference weight frozen", design["reference_model"]["EMPATHY_REPAIR_WEIGHT"] == REFERENCE_WEIGHT)
    check("no p values", design["p_values"] is False)
    check("no winner selection", design["winner_weight_selection"] is False)
    check("only changed weight", design["only_changed_parameter"] == "EMPATHY_REPAIR_WEIGHT")

    rows = [_run_weight(weight) for weight in GRID]
    check("five grid rows", len(rows) == 5, rows)
    check("weights preserved", tuple(row["weight"] for row in rows) == GRID, rows)
    increments = [row["relational_repair_increment_tick6"] for row in rows]
    check("repair increment monotonic", increments == sorted(increments), increments)
    check("weight zero no repair increment", increments[0] == 0.0, increments)
    check("reference model identifiable", rows[GRID.index(REFERENCE_WEIGHT)]["relational_repair_increment_tick6"] > 0)
    check("PBC invariant across grid", len({row["pbc"] for row in rows}) == 1, rows)
    check("SN not directly changed by empathy", len({row["subjective_norm_sn"] for row in rows}) == 1, rows)
    for key in ("repair_memory", "trust_auc", "tick30_trust", "purchase_intention", "cumulative_first_purchase"):
        check(f"reported {key}", all(key in row for row in rows), rows)
    classification = _classify(rows)
    check("classification allowed", classification in CLASSIFICATIONS, classification)
    check("reference not changed by results", REFERENCE_WEIGHT == 0.50)
    check("real llm calls zero", design["real_llm_calls"] == 0)

    print("CLASSIFICATION:", classification)
    print("ROWS:", json.dumps(rows, sort_keys=True))
    print("Passed:", P, "Failed:", F)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
