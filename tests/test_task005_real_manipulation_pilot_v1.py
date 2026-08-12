from __future__ import annotations

import csv
import json
import os
import textwrap
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
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

    check(
        "actual mechanism schema has semantic source fields",
        set(pilot.REQUIRED_SEMANTIC_SOURCE_FIELDS) <= set(pilot.MECHANISM_RECORDS_FIELDS),
        pilot.REQUIRED_SEMANTIC_SOURCE_FIELDS,
    )
    rational = [
        _semantic_row("A1", True, 0.8, 0.7, 0.2, 0.2, 0.9, False),
        _semantic_row("A2", True, 0.7, 0.6, 0.3, 0.3, 0.8, True),
    ]
    empathy = [
        _semantic_row("A1", True, 0.4, 0.4, 0.8, 0.7, 0.86, True),
        _semantic_row("A2", True, 0.5, 0.4, 0.7, 0.6, 0.74, True),
    ]
    pairs = pilot.compute_manipulation_pairs("R001", rational, empathy)
    check("matched pairs count", len(pairs) == 2, pairs)
    check("pairs include replicate id", {row["replicate_id"] for row in pairs} == {"R001"}, pairs)
    check("pairs include topic values", "rational_topic_relevance" in pairs[0] and "empathy_topic_relevance" in pairs[0])
    check("pairs include hypocrisy values", "rational_hypocrisy_perceived" in pairs[0] and "empathy_hypocrisy_perceived" in pairs[0])
    check("D evidence direction", all(row["D_evidence"] > 0 for row in pairs), pairs)
    check("D credibility direction", all(row["D_credibility"] > 0 for row in pairs), pairs)
    check("D valence direction", all(row["D_valence"] > 0 for row in pairs), pairs)
    check("D arousal direction", all(row["D_arousal"] > 0 for row in pairs), pairs)
    empathy_bad = [dict(row) for row in empathy[:1]]
    try:
        pilot.compute_manipulation_pairs("R001", rational, empathy_bad)
    except pilot.PilotContractError:
        check("matched exposure mismatch fails", True)
    else:
        check("matched exposure mismatch fails", False)
    duplicate = rational + [dict(rational[0])]
    try:
        pilot.compute_manipulation_pairs("R001", duplicate, empathy)
    except pilot.PilotContractError:
        check("duplicate agent fails", True)
    else:
        check("duplicate agent fails", False)


def _semantic_row(agent_id, detected, evidence, credibility, valence, arousal, topic, hypocrisy):
    return {
        "agent_id": agent_id,
        "clarification_detected_by_plan": detected,
        "semantic_evidence_strength": evidence,
        "semantic_credibility": credibility,
        "semantic_valence": valence,
        "semantic_arousal": arousal,
        "semantic_topic_relevance": topic,
        "semantic_hypocrisy_perceived": hypocrisy,
    }


def test_floor_topic_and_fallback_logic() -> None:
    pairs = _pairs_for_blocks(0.06)
    summary = pilot.summarize_manipulation_by_block(pairs)
    check("per block direction gate pass", summary["all_blocks_direction_pass"] is True and summary["DIRECTION_GATE"] == "PASS", summary)
    check("0.05 floor pass", summary["MANIPULATION_STRENGTH"] == "PASS", summary)
    check("no topic warning below threshold", summary["topic_relevance_warning"] == "", summary)
    weak = _pairs_for_blocks(0.049)
    weak_summary = pilot.summarize_manipulation_by_block(weak)
    check("weak floor labels weak", weak_summary["MANIPULATION_STRENGTH"] == "WEAK", weak_summary)
    floor = _pairs_for_blocks(0.050)
    floor_summary = pilot.summarize_manipulation_by_block(floor)
    check("floor equals 0.050 passes", floor_summary["MANIPULATION_STRENGTH"] == "PASS", floor_summary)
    failing_block = _pairs_for_blocks(0.06)
    for row in failing_block:
        if row["replicate_id"] == "R002":
            row["D_arousal"] = -0.01
    failing_summary = pilot.summarize_manipulation_by_block(failing_block)
    check("R002 one dimension negative fails direction gate", failing_summary["all_blocks_direction_pass"] is False, failing_summary)
    topic = _pairs_for_blocks(0.06)
    for row in topic:
        row["rational_topic_relevance"] = 0.901
        row["empathy_topic_relevance"] = 0.800
    topic_summary = pilot.summarize_manipulation_by_block(topic)
    check("topic relevance warning", topic_summary["topic_relevance_warning"] == "TOPIC_RELEVANCE_IMBALANCE")
    check("topic uses group mean difference", abs(topic_summary["topic_relevance_group_mean_abs_diff"] - 0.101) < 1e-12, topic_summary)
    check("hypocrisy rates reported", "rational_hypocrisy_perceived_rate" in topic_summary and "empathy_hypocrisy_perceived_rate" in topic_summary)
    check("fallback zero pass", pilot.fallback_counts_pass([{"semantic_fallback_used": 0, "plan_fallback_used": 0, "json_parse_failure": 0}]))
    check("fallback nonzero fail", not pilot.fallback_counts_pass([{"semantic_fallback_used": 1, "plan_fallback_used": 0, "json_parse_failure": 0}]))


def _pairs_for_blocks(value: float) -> list[dict]:
    rows = []
    for replicate_id in ("R001", "R002"):
        for index in range(2):
            rows.append(
                {
                    "replicate_id": replicate_id,
                    "agent_id": f"A{index + 1}",
                    "D_evidence": value,
                    "D_credibility": value,
                    "D_valence": value,
                    "D_arousal": value,
                    "rational_topic_relevance": 0.82,
                    "empathy_topic_relevance": 0.80,
                    "rational_hypocrisy_perceived": index == 0,
                    "empathy_hypocrisy_perceived": True,
                }
            )
    return rows


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
    args = type("Args", (), {"execute_real": True, "activation_token": ""})()
    try:
        pilot.assert_real_execution_authorized(args)
    except pilot.PilotContractError as exc:
        check("real execution missing token fails", pilot.REAL_MODE_REJECTION in str(exc), str(exc))
    else:
        check("real execution missing token fails", False)
    args = type("Args", (), {"execute_real": True, "activation_token": "wrong"})()
    try:
        pilot.assert_real_execution_authorized(args)
    except pilot.PilotContractError as exc:
        check("real execution wrong token fails", pilot.REAL_MODE_REJECTION in str(exc), str(exc))
    else:
        check("real execution wrong token fails", False)
    args = type("Args", (), {"execute_real": True, "activation_token": pilot.ACTIVATION_TOKEN})()
    try:
        pilot.assert_real_execution_authorized(args)
    except pilot.PilotContractError as exc:
        check("real execution correct token passes auth boundary", False, str(exc))
    else:
        check("real execution correct token passes auth boundary", True)


def _activation_payload(source_hashes=None) -> dict:
    return {
        "pilot_id": pilot.PILOT_ID,
        "activation_token": pilot.ACTIVATION_TOKEN,
        "master_seed": pilot.MASTER_SEED,
        "replicates": list(pilot.ALLOWED_REPLICATE_IDS),
        "conditions": list(pilot.PILOT_CONDITION_IDS),
        "conditions_per_block": 3,
        "provider": pilot.PROVIDER,
        "model": pilot.MODEL,
        "temperature": pilot.TEMPERATURE,
        "credential": "environment only",
        "authorized_timeline": "Tick5 crisis only",
        "clarification_tick": 6,
        "formal_inference": False,
        "p_values": False,
        "optional_stopping": False,
        "replacement_replicates": False,
        "auto_retry": False,
        "provider_seed_determinism": "UNKNOWN_NOT_GUARANTEED",
        "content_interpretation": "composite message archetypes",
        "source_sha256": source_hashes if source_hashes is not None else pilot.current_source_hashes(),
    }


def test_activation_gate_negative_cases() -> None:
    old_artifact = pilot.ACTIVATION_ARTIFACT
    old_clean = pilot._assert_clean_tree
    old_process = pilot._assert_no_pilot_python_process
    old_key = os.environ.get(pilot.TASK005_LLM_API_KEY_ENV)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "activation.json"
            artifact.write_text(json.dumps(_activation_payload(), sort_keys=True), encoding="utf-8")
            pilot.ACTIVATION_ARTIFACT = artifact
            pilot._assert_clean_tree = lambda: None
            pilot._assert_no_pilot_python_process = lambda: None
            os.environ.pop(pilot.TASK005_LLM_API_KEY_ENV, None)
            try:
                pilot.assert_activation_ready(pilot.ACTIVATION_TOKEN, root / "out1")
            except pilot.PilotContractError as exc:
                check("missing credential blocked", "missing credential" in str(exc), str(exc))
            else:
                check("missing credential blocked", False)

            os.environ[pilot.TASK005_LLM_API_KEY_ENV] = "dummy-pilot-key"
            bad_hashes = pilot.current_source_hashes()
            first_key = next(iter(bad_hashes))
            bad_hashes[first_key] = "0" * 64
            artifact.write_text(json.dumps(_activation_payload(bad_hashes), sort_keys=True), encoding="utf-8")
            try:
                pilot.assert_activation_ready(pilot.ACTIVATION_TOKEN, root / "out2")
            except pilot.PilotContractError as exc:
                check("source mismatch blocked", "SOURCE_FREEZE_MISMATCH" in str(exc), str(exc))
            else:
                check("source mismatch blocked", False)

            artifact.write_text(json.dumps(_activation_payload(), sort_keys=True), encoding="utf-8")
            nonempty = root / "nonempty"
            nonempty.mkdir()
            (nonempty / "x.txt").write_text("x", encoding="utf-8")
            try:
                pilot.assert_activation_ready(pilot.ACTIVATION_TOKEN, nonempty)
            except pilot.PilotContractError as exc:
                check("nonempty output blocked", "non-empty" in str(exc), str(exc))
            else:
                check("nonempty output blocked", False)

            def dirty():
                raise pilot.PilotContractError("tracked diff must be clean")

            pilot._assert_clean_tree = dirty
            try:
                pilot.assert_activation_ready(pilot.ACTIVATION_TOKEN, root / "out3")
            except pilot.PilotContractError as exc:
                check("dirty tracked tree blocked", "tracked diff" in str(exc), str(exc))
            else:
                check("dirty tracked tree blocked", False)
    finally:
        pilot.ACTIVATION_ARTIFACT = old_artifact
        pilot._assert_clean_tree = old_clean
        pilot._assert_no_pilot_python_process = old_process
        if old_key is None:
            os.environ.pop(pilot.TASK005_LLM_API_KEY_ENV, None)
        else:
            os.environ[pilot.TASK005_LLM_API_KEY_ENV] = old_key


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
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        "run_task005_real_manipulation_pilot_v1.py",
        "--execute-real",
        "--activation-token",
        "wrong",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
    check("cli wrong token rejected", proc.returncode == 2 and pilot.REAL_MODE_REJECTION in proc.stdout, proc.stdout)
    cmd = [sys.executable, "-X", "utf8", "run_task005_real_manipulation_pilot_v1.py", "--retry"]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
    check("retry argument impossible", proc.returncode == 2, proc.returncode)
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        "run_task005_real_manipulation_pilot_v1.py",
        "--_run-replicate",
        "R003",
        "--activation-token",
        pilot.ACTIVATION_TOKEN,
    ]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
    check("R003 child entry impossible", proc.returncode == 2, proc.stdout)
    cmd = [sys.executable, "-X", "utf8", "run_task005_real_manipulation_pilot_v1.py", "--offline-test"]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
    check("cli offline-test passes", proc.returncode == 0, proc.stdout + proc.stderr)


def test_network_tripwire_offline_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sitecustomize = Path(tmp) / "sitecustomize.py"
        sitecustomize.write_text(
            textwrap.dedent(
                """
                import socket

                def _forbidden(*args, **kwargs):
                    raise RuntimeError("NETWORK_FORBIDDEN_TEST")

                socket.create_connection = _forbidden
                _orig_socket = socket.socket

                class _GuardedSocket(_orig_socket):
                    def connect(self, *args, **kwargs):
                        raise RuntimeError("NETWORK_FORBIDDEN_TEST")

                socket.socket = _GuardedSocket
                """
            ),
            encoding="utf-8",
        )
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(sitecustomize.parent) + (os.pathsep + existing if existing else "")
        env.pop("HF_HUB_OFFLINE", None)
        env.pop("TRANSFORMERS_OFFLINE", None)
        env.pop("HF_DATASETS_OFFLINE", None)
        env["TOKENIZERS_PARALLELISM"] = "true"
        cmd = [sys.executable, "-X", "utf8", "run_task005_real_manipulation_pilot_v1.py", "--offline-test"]
        proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
        combined = proc.stdout + proc.stderr
        check("NETWORK_TRIPWIRE_OFFLINE_TEST exit 0", proc.returncode == 0, combined)
        check("NETWORK_TRIPWIRE_OFFLINE_TEST not triggered", "NETWORK_FORBIDDEN_TEST" not in combined, combined)


def main() -> int:
    test_identity_and_seed_ledger()
    test_conditions_from_matrix_and_record_replay()
    test_replay_miss_and_matched_exposure_gates()
    test_floor_topic_and_fallback_logic()
    test_credential_preflight_and_real_rejection()
    test_activation_gate_negative_cases()
    test_dry_run_artifacts_are_sanitized()
    test_no_pvalue_imports_or_formal_reuse()
    test_cli_modes()
    test_network_tripwire_offline_test()
    print(f"Passed: {P}")
    print(f"Failed: {F}")
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
