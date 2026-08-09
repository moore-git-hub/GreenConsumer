from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import run_task005_real_manipulation_pilot_v1 as pilot


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


def test_identity_and_seed_ledger() -> None:
    rows = pilot.build_pilot_seed_ledger()
    rows2 = pilot.build_pilot_seed_ledger()
    check("pilot id exact", pilot.PILOT_ID == "task005-real-manipulation-pilot-v1", pilot.PILOT_ID)
    check("master seed exact", pilot.MASTER_SEED == 2026080902, pilot.MASTER_SEED)
    check("two replicate blocks", len(rows) == 2, len(rows))
    check("replicate ids exact", tuple(row["replicate_id"] for row in rows) == ("R001", "R002"), rows)
    check("no R003", "R003" not in {row["replicate_id"] for row in rows}, rows)
    check("seed ledger deterministic", rows == rows2)
    check("provider model qwen-plus", {row["provider_model"] for row in rows} == {"qwen-plus"})
    check("llm seed supported unknown", {row["llm_seed_supported"] for row in rows} == {"unknown"})
    check("python hash seed present", all(isinstance(row["python_hash_seed"], int) for row in rows))


def test_conditions_from_matrix_and_record_replay() -> None:
    configs = pilot.select_pilot_conditions()
    check("exact 3 conditions", len(configs) == 3, [cfg.exp_id for cfg in configs])
    check("condition ids exact", tuple(cfg.exp_id for cfg in configs) == pilot.PILOT_CONDITION_IDS)
    check("control first", configs[0].is_control)
    check("rational hub immediate", configs[1].exp_id == "Rational-Hub-Immediate")
    check("empathy hub immediate", configs[2].exp_id == "Empathy-Hub-Immediate")
    check("authorized clarification tick 6", configs[1].clarification_tick == 6 and configs[2].clarification_tick == 6)
    manifest = pilot.build_pilot_manifest_rows(pilot.build_pilot_seed_ledger())
    check("manifest has 2x3 rows", len(manifest) == 6, len(manifest))
    check("record replay order", pilot.validate_record_replay_order(manifest))
    check("router roles exact", [row["router_role"] for row in manifest[:3]] == ["recording", "replay", "replay"])
    check("formal flags false", all(row["FORMAL_INFERENCE"] is False for row in manifest))
    check("pilot flags true", all(row["PILOT_ONLY"] is True for row in manifest))


def test_replay_miss_and_matched_exposure_gates() -> None:
    pilot.assert_no_replay_miss([{"replay_miss_count": 0}, {"replay_miss_count": "0"}])
    check("replay miss zero accepted", True)
    try:
        pilot.assert_no_replay_miss([{"replay_miss_count": 1}])
    except pilot.PilotContractError:
        check("replay miss fail closed", True)
    else:
        check("replay miss fail closed", False)

    rational = [
        _semantic_row("A1", True, 0.8, 0.7, 0.2, 0.2, 0.9),
        _semantic_row("A2", True, 0.7, 0.6, 0.3, 0.3, 0.8),
    ]
    empathy = [
        _semantic_row("A1", True, 0.4, 0.4, 0.8, 0.7, 0.86),
        _semantic_row("A2", True, 0.5, 0.4, 0.7, 0.6, 0.74),
    ]
    pairs = pilot.compute_manipulation_pairs(rational, empathy)
    check("matched pairs count", len(pairs) == 2, pairs)
    check("D evidence direction", all(row["D_evidence"] > 0 for row in pairs), pairs)
    check("D credibility direction", all(row["D_credibility"] > 0 for row in pairs), pairs)
    check("D valence direction", all(row["D_valence"] > 0 for row in pairs), pairs)
    check("D arousal direction", all(row["D_arousal"] > 0 for row in pairs), pairs)
    empathy_bad = [dict(row) for row in empathy[:1]]
    try:
        pilot.compute_manipulation_pairs(rational, empathy_bad)
    except pilot.PilotContractError:
        check("matched exposure mismatch fails", True)
    else:
        check("matched exposure mismatch fails", False)


def _semantic_row(agent_id, detected, evidence, credibility, valence, arousal, topic):
    return {
        "agent_id": agent_id,
        "clarification_detected_by_plan": detected,
        "evidence_strength": evidence,
        "credibility": credibility,
        "valence": valence,
        "arousal": arousal,
        "topic_relevance": topic,
    }


def test_floor_topic_and_fallback_logic() -> None:
    pairs = [
        {
            "D_evidence": 0.06,
            "D_credibility": 0.07,
            "D_valence": 0.08,
            "D_arousal": 0.09,
            "topic_relevance_abs_diff": 0.04,
        },
        {
            "D_evidence": 0.07,
            "D_credibility": 0.08,
            "D_valence": 0.06,
            "D_arousal": 0.10,
            "topic_relevance_abs_diff": 0.05,
        },
    ]
    summary = pilot.summarize_manipulation_pairs(pairs)
    check("0.05 floor pass", summary["MANIPULATION_STRENGTH"] == "PASS", summary)
    check("no topic warning below threshold", summary["topic_relevance_warning"] == "", summary)
    weak = [dict(row) for row in pairs]
    weak[0]["D_evidence"] = 0.01
    weak[1]["D_evidence"] = 0.02
    weak_summary = pilot.summarize_manipulation_pairs(weak)
    check("weak floor labels weak", weak_summary["MANIPULATION_STRENGTH"] == "WEAK", weak_summary)
    topic = [dict(row) for row in pairs]
    topic[0]["topic_relevance_abs_diff"] = 0.2
    topic[1]["topic_relevance_abs_diff"] = 0.2
    topic_summary = pilot.summarize_manipulation_pairs(topic)
    check("topic relevance warning", topic_summary["topic_relevance_warning"] == "TOPIC_RELEVANCE_IMBALANCE")
    check("fallback zero pass", pilot.fallback_counts_pass([{"semantic_fallback_used": 0, "plan_fallback_used": 0, "json_parse_failure": 0}]))
    check("fallback nonzero fail", not pilot.fallback_counts_pass([{"semantic_fallback_used": 1, "plan_fallback_used": 0, "json_parse_failure": 0}]))


def test_credential_preflight_and_real_rejection() -> None:
    old = os.environ.pop(pilot.TASK005_LLM_API_KEY_ENV, None)
    try:
        try:
            pilot.preflight()
        except pilot.PilotContractError:
            check("missing credential preflight fail", True)
        else:
            check("missing credential preflight fail", False)
    finally:
        if old is not None:
            os.environ[pilot.TASK005_LLM_API_KEY_ENV] = old
    os.environ[pilot.TASK005_LLM_API_KEY_ENV] = "dummy-pilot-key"
    try:
        preflight = pilot.preflight()
        text = json.dumps(preflight, sort_keys=True)
        check("dummy preflight succeeds", preflight["pilot_id"] == pilot.PILOT_ID, preflight)
        check("dummy key absent from preflight output", "dummy-pilot-key" not in text)
    finally:
        os.environ.pop(pilot.TASK005_LLM_API_KEY_ENV, None)
    args = type("Args", (), {"execute_real": True})()
    try:
        pilot.assert_real_execution_authorized(args)
    except pilot.PilotContractError as exc:
        check("real execution without authorization fails", pilot.REAL_MODE_REJECTION in str(exc), str(exc))
    else:
        check("real execution without authorization fails", False)


def test_dry_run_artifacts_are_sanitized() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        summary = pilot.write_offline_dry_run_artifacts(out)
        check("dry run summary no real calls", summary["REAL_LLM_CALLS"] is False, summary)
        required = {
            "seed_ledger.csv",
            "pilot_manifest.csv",
            "sanitized_model_config.json",
            "manipulation_summary.json",
        }
        check("dry run required files", required <= {p.name for p in out.iterdir()}, sorted(p.name for p in out.iterdir()))
        manifest_rows = list(csv.DictReader((out / "pilot_manifest.csv").open(encoding="utf-8")))
        check("dry manifest row count", len(manifest_rows) == 6, len(manifest_rows))
        sanitized = json.loads((out / "sanitized_model_config.json").read_text(encoding="utf-8"))
        payload = "\n".join(p.read_text(encoding="utf-8") for p in out.iterdir() if p.is_file())
        check("sanitized config redacts api key", sanitized.get("api_key") == "<REDACTED>", sanitized)
        check("placeholder absent from artifacts", pilot.TASK005_LLM_API_KEY_PLACEHOLDER not in payload)
        check("formal false in artifacts", '"FORMAL_INFERENCE": false' in payload or "False" in payload)
        check("p values false in artifacts", '"P_VALUES_COMPUTED": false' in payload or "False" in payload)


def test_no_pvalue_imports_or_formal_reuse() -> None:
    source = (ROOT / "run_task005_real_manipulation_pilot_v1.py").read_text(encoding="utf-8")
    check("no scipy stats import", "scipy.stats" not in source)
    check("no ttest call", "ttest" not in source.replace("NO_P_VALUE_TERMS", ""))
    check("no formal results path", "results/replications/task005-formal" not in source)


def test_cli_modes() -> None:
    env = dict(os.environ)
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    env.pop(pilot.TASK005_LLM_API_KEY_ENV, None)
    cmd = [sys.executable, "-X", "utf8", "run_task005_real_manipulation_pilot_v1.py", "--execute-real"]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
    check("cli real rejected exit 2", proc.returncode == 2, proc.returncode)
    check("cli real rejected label", pilot.REAL_MODE_REJECTION in proc.stdout, proc.stdout)
    cmd = [sys.executable, "-X", "utf8", "run_task005_real_manipulation_pilot_v1.py", "--offline-test"]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
    check("cli offline-test passes", proc.returncode == 0, proc.stdout + proc.stderr)


def main() -> int:
    test_identity_and_seed_ledger()
    test_conditions_from_matrix_and_record_replay()
    test_replay_miss_and_matched_exposure_gates()
    test_floor_topic_and_fallback_logic()
    test_credential_preflight_and_real_rejection()
    test_dry_run_artifacts_are_sanitized()
    test_no_pvalue_imports_or_formal_reuse()
    test_cli_modes()
    print(f"Passed: {P}")
    print(f"Failed: {F}")
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
