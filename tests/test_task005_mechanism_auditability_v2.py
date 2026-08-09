from __future__ import annotations

import ast
import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import simulation_core
import run_experiments
from experiment_config import ExperimentConfig


START_HEAD = "29cb4e49fb67a7902ae8773929d671b793f4dac1"
PROTECTED_SOURCES = (
    "mechanism_v2.py",
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "plugins/agent/plan/ConsumerPlanPlugin.py",
    "node_selector.py",
    "experiment_config.py",
)

P = 0
F = 0


def check(name: str, condition: bool, actual=None) -> None:
    global P, F
    if condition:
        P += 1
        print("PASS", name)
    else:
        F += 1
        print("FAIL", name, actual)


def _git_show(path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{START_HEAD}:{path}"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )


def _literal_name(src: str, name: str):
    module = ast.parse(src)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found")


def _snapshot():
    cfg = ExperimentConfig(
        content_factor="rational-evidence",
        channel_factor="hub",
        timing_factor="immediate",
    )
    s_data = {
        "baseline_trust": 6.1234567891234,
        "last_observations": [
            {"source": "Enterprise_Clarification", "type": "clarification"},
        ],
        "reflect_message_sources": ["Enterprise_Clarification"],
        "raw_affective_output": 0.9876543219876,
        "trust_change_affective": 0.2222222222222,
        "affective_was_clipped": False,
        "reflect_primary_source": "Enterprise_Clarification",
        "semantic_observation_present": True,
        "semantic_social_observation_count": 2,
        "semantic_valence": 0.500000000001,
        "semantic_arousal": 0.450000000001,
        "semantic_credibility": 0.900000000001,
        "semantic_evidence_strength": 0.950000000001,
        "semantic_topic_relevance": 0.900000000001,
        "semantic_hypocrisy_perceived": False,
    }
    plan = {
        "is_buying": True,
        "is_posting": False,
        "post_content": "",
        "reason": "TPB-v2 I=0.712 Trust=6.456",
        "plan_fallback_used": False,
        "trust_after_decay": 5.9012,
        "affective_change": 0.3333,
        "shock_anchor": 5.8,
        "decay_lambda": 0.03,
        "quiet_ticks": 0,
        "previous_trust_raw": 5.876543219876,
        "baseline_trust_raw": 6.123456789123,
        "trust_after_decay_raw": 5.901234567891,
        "affective_change_raw": 0.333333333333,
        "trust_score_raw": 6.456789123456,
        "shock_anchor_before_raw": 5.8,
        "shock_anchor_after_raw": 6.4,
        "decay_rate_raw": 0.03,
        "sensitivity_multiplier": 1.0,
        "trust_clipped_at_bound": False,
        "anchor_update_branch": "mechanism_v2_clarification",
        "clr_anchor_lift_ratio": 0.123456789123,
        "clr_lift_raw": 0.6,
        "clarification_detected_by_plan": True,
        "clarification_content_type": "rational-evidence",
        "attitude_att": 0.612345678912,
        "subjective_norm_sn": 0.512345678912,
        "pbc": 0.5,
        "emotion_valence": 0.500000000001,
        "emotion_arousal": 0.450000000001,
        "crisis_memory_before": 1.111111111111,
        "repair_memory_before": 0.222222222222,
        "crisis_memory": 1.077777777777,
        "repair_memory": 0.888888888888,
        "purchase_intention": 0.712345678912,
        "posting_intention": 0.312345678912,
        "buy_probability": 0.071234567891,
        "post_probability": 0.140555555555,
        "buy_draw": 0.061234567891,
        "post_draw": 0.781234567891,
    }
    thought = {
        "hypocrisy_perceived": False,
        "importance": 8.0,
        "reasoning": "statement was credible",
        "semantic_fallback_used": False,
    }
    return cfg, s_data, plan, thought


def _writer_raises(results, path: Path) -> bool:
    try:
        run_experiments.write_mechanism_records_csv(results, str(path))
        return False
    except ValueError:
        return True


def main() -> int:
    current_agent_fields = list(simulation_core.AGENT_RECORDS_FIELDS)
    start_agent_fields = _literal_name(_git_show("simulation_core.py"), "AGENT_RECORDS_FIELDS")
    start_schema = _literal_name(
        _git_show("simulation_core.py"), "AGENT_RECORDS_SCHEMA_VERSION"
    )
    check("legacy schema version preserved", simulation_core.AGENT_RECORDS_SCHEMA_VERSION == start_schema)
    check("legacy 60 field count preserved", len(current_agent_fields) == 60, len(current_agent_fields))
    check("legacy field order preserved", current_agent_fields == start_agent_fields)

    required = {
        "schema_version", "exp_id", "tick", "agent_id",
        "content_factor", "channel_factor", "timing_factor", "clarification_tick_config",
        "semantic_observation_present", "semantic_social_observation_count",
        "semantic_valence", "semantic_arousal", "semantic_credibility",
        "semantic_evidence_strength", "semantic_topic_relevance",
        "semantic_hypocrisy_perceived", "semantic_fallback_used",
        "reflect_primary_source", "previous_trust", "baseline_trust",
        "trust_before_signal", "affective_change", "trust_final",
        "attitude_att", "subjective_norm_sn", "pbc",
        "emotion_valence", "emotion_arousal", "crisis_memory_before",
        "repair_memory_before", "crisis_memory", "repair_memory",
        "purchase_intention", "posting_intention", "buy_probability",
        "post_probability", "buy_draw", "post_draw", "is_buying",
        "is_posting", "plan_fallback_used", "clarification_detected_by_plan",
        "clarification_content_type",
    }
    fields = list(simulation_core.MECHANISM_RECORDS_FIELDS)
    check("mechanism schema version", simulation_core.MECHANISM_RECORDS_SCHEMA_VERSION == "1.0")
    check("mechanism schema unique", len(fields) == len(set(fields)), fields)
    check("mechanism required fields present", required <= set(fields), sorted(required - set(fields)))
    check("runner imports same mechanism schema", run_experiments.MECHANISM_RECORDS_FIELDS == fields)

    cfg, s_data, plan, thought = _snapshot()
    agent_record = simulation_core.build_agent_record(
        config=cfg,
        tick=6,
        agent_id="Consumer_001",
        cluster_type="Eco_Actives",
        social_role="Sharer",
        trust=plan["trust_score_raw"],
        s_data=s_data,
        plan=plan,
        thought=thought,
        out_degree=4,
        in_degree=2,
        is_clarification_target=True,
        clarification_injected=True,
        cumulative_buyers_count=1,
    )
    mechanism_record = simulation_core.build_mechanism_record(
        config=cfg,
        tick=6,
        agent_id="Consumer_001",
        s_data=s_data,
        plan=plan,
        thought=thought,
    )
    check("agent record remains 60 fields", len(agent_record) == 60, len(agent_record))
    check("mechanism record exact schema", set(mechanism_record) == set(fields))
    check("join key matches agent record", tuple(mechanism_record[k] for k in ("exp_id", "tick", "agent_id")) == tuple(agent_record[k] for k in ("exp_id", "tick", "agent_id")))

    result = {"agent_records": [], "mechanism_records": []}
    for tick in (1, 2, 3):
        for agent_id in ("Consumer_001", "Consumer_002"):
            ar = dict(agent_record, tick=tick, agent_id=agent_id)
            mr = dict(mechanism_record, tick=tick, agent_id=agent_id)
            result["agent_records"].append(ar)
            result["mechanism_records"].append(mr)
    agent_keys = {(r["exp_id"], r["tick"], r["agent_id"]) for r in result["agent_records"]}
    mechanism_keys = {(r["exp_id"], r["tick"], r["agent_id"]) for r in result["mechanism_records"]}
    check("one-to-one key coverage", agent_keys == mechanism_keys)
    check("one-to-one row count", len(result["agent_records"]) == len(result["mechanism_records"]))
    check("no duplicate mechanism keys", len(mechanism_keys) == len(result["mechanism_records"]))

    audit = simulation_core._audit_float
    check("semantic persistence", mechanism_record["semantic_valence"] == audit(s_data["semantic_valence"]))
    check("TPB persistence", mechanism_record["attitude_att"] == audit(plan["attitude_att"]))
    check("memory persistence", mechanism_record["crisis_memory"] == audit(plan["crisis_memory"]) and mechanism_record["repair_memory"] == audit(plan["repair_memory"]))
    check("intention persistence", mechanism_record["purchase_intention"] == audit(plan["purchase_intention"]))
    check("behavior probability persistence", mechanism_record["buy_probability"] == audit(plan["buy_probability"]))
    check("RNG draw persistence", mechanism_record["buy_draw"] == audit(plan["buy_draw"]))
    check("behavior persistence", mechanism_record["is_buying"] is plan["is_buying"])
    check("fallback flags", mechanism_record["semantic_fallback_used"] is False and mechanism_record["plan_fallback_used"] is False)
    check("high precision retained", mechanism_record["buy_draw"] == round(plan["buy_draw"], 12))

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "mechanism_records.csv"
        complete_result = {
            "exp_id": cfg.exp_id,
            "agent_records": [agent_record],
            "mechanism_records": [mechanism_record],
        }
        run_experiments.write_mechanism_records_csv(
            [complete_result],
            str(out),
        )
        with out.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        check("mechanism CSV header strict", tuple(reader.fieldnames or ()) == tuple(fields))
        check("mechanism CSV writes one row", len(rows) == 1, len(rows))
        bad = dict(mechanism_record)
        bad["extra_silent_field"] = "forbidden"
        strict_failed = _writer_raises(
            [{"exp_id": cfg.exp_id, "agent_records": [agent_record], "mechanism_records": [bad]}],
            Path(td) / "bad.csv",
        )
        check("mechanism CSV rejects extra fields", strict_failed)
        check(
            "successful result missing mechanism_records raises",
            _writer_raises(
                [{"exp_id": cfg.exp_id, "agent_records": [agent_record]}],
                Path(td) / "missing_mechanism.csv",
            ),
        )
        check(
            "successful result missing agent_records raises",
            _writer_raises(
                [{"exp_id": cfg.exp_id, "mechanism_records": [mechanism_record]}],
                Path(td) / "missing_agent.csv",
            ),
        )
        check(
            "mechanism row count mismatch raises",
            _writer_raises(
                [{
                    "exp_id": cfg.exp_id,
                    "agent_records": [agent_record, dict(agent_record, tick=7)],
                    "mechanism_records": [mechanism_record],
                }],
                Path(td) / "row_mismatch.csv",
            ),
        )
        check(
            "mechanism key mismatch raises",
            _writer_raises(
                [{
                    "exp_id": cfg.exp_id,
                    "agent_records": [agent_record],
                    "mechanism_records": [dict(mechanism_record, agent_id="Consumer_999")],
                }],
                Path(td) / "key_mismatch.csv",
            ),
        )
        check(
            "duplicate mechanism key raises",
            _writer_raises(
                [{
                    "exp_id": cfg.exp_id,
                    "agent_records": [agent_record, dict(agent_record, tick=7)],
                    "mechanism_records": [mechanism_record, dict(mechanism_record)],
                }],
                Path(td) / "duplicate_key.csv",
            ),
        )
        run_experiments.write_mechanism_records_csv(
            [{"exp_id": "Error-Condition", "error": "boom"}],
            str(Path(td) / "error_skip.csv"),
        )
        check("error result may be skipped", (Path(td) / "error_skip.csv").exists())

        agent_out = Path(td) / "agent_records.csv"
        run_experiments.write_agent_records_csv(
            [{"agent_records": [agent_record]}],
            str(agent_out),
        )
        with agent_out.open(newline="", encoding="utf-8") as f:
            agent_reader = csv.DictReader(f)
            agent_rows = list(agent_reader)
        check("legacy agent CSV remains 60 columns", len(agent_reader.fieldnames or []) == 60)
        check("legacy agent CSV still writes", len(agent_rows) == 1)

    for path in PROTECTED_SOURCES:
        current = (ROOT / path).read_text(encoding="utf-8")
        check(f"protected source unchanged {path}", current == _git_show(path))

    contract = (
        ROOT
        / ".kiro/specs/task005-replication-inference/"
        / "mechanism_auditability_schema_amendment1.0.json"
    ).read_text(encoding="utf-8")
    check("contract says no p tuning", '"parameter_tuning": false' in contract)
    check("contract says reporting only", '"amendment_type": "reporting_only"' in contract)

    print("\nTASK_005 MECHANISM AUDITABILITY V2")
    print("Passed:", P)
    print("Failed:", F)
    raise SystemExit(1 if F else 0)


if __name__ == "__main__":
    main()
