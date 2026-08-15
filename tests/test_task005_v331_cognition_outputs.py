"""Zero-API tests for v3.3.1 cognition-evolution post-processing."""
from __future__ import annotations

import inspect
import json

import pandas as pd

from greenconsumer_v33.cognition_outputs import (
    _agent_transitions,
    _reasoning_ledger,
    _validate_and_load,
    build_cognition_outputs,
)


def test_cognition_module_has_no_runtime_or_provider_imports():
    import greenconsumer_v33.cognition_outputs as module

    source = inspect.getsource(module)
    forbidden = (
        "agentkernel_standalone", "build_inner_router", "run_scenario_v33",
        "RecordingRouter", "DASHSCOPE_API_KEY",
    )
    assert not any(token in source for token in forbidden)


def _fixture(tmp_path, *, horizon=10):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run_summary.json").write_text(
        json.dumps({"run_id": "synthetic-test-only", "total_ticks": horizon, "code_release": "test"}),
        encoding="utf-8",
    )
    thoughts = []
    cognitive = []
    for exp_id, offset in (("NoClarification-Control", 0.0), ("Rational-Hub-Immediate", 0.2)):
        for agent_id in ("A", "B"):
            for tick in range(1, horizon + 1):
                thought = "I observed an event." if tick in {5, 6} else ""
                thoughts.append({
                    "exp_id": exp_id, "tick": tick, "agent_id": agent_id,
                    "thought_present": bool(thought), "reasoning": thought,
                    "clarification_received": exp_id != "NoClarification-Control" and tick == 6,
                    "semantic_observation_present": tick in {5, 6},
                    "semantic_social_observation_count": 0,
                    "semantic_fallback_used": False,
                    "cluster_type": "test", "social_role": "ordinary",
                })
                cognitive.append({
                    "exp_id": exp_id, "tick": tick, "agent_id": agent_id,
                    "trust_final": 5.0 + offset + tick / 100,
                    "attitude_att": 0.5 + tick / 1000,
                    "subjective_norm_after": 0.5,
                    "pbc": 0.6,
                    "purchase_intention": 0.4 + tick / 1000,
                    "crisis_memory": 1.0 if tick >= 5 else 0.0,
                    "repair_memory": 0.5 if exp_id != "NoClarification-Control" and tick >= 6 else 0.0,
                })
    pd.DataFrame(thoughts).to_csv(run_dir / "agent_thoughts.csv", index=False)
    pd.DataFrame(cognitive).to_csv(run_dir / "cognitive_records.csv", index=False)
    return run_dir


def test_reasoning_ledger_preserves_only_explicit_text(tmp_path):
    run_dir = _fixture(tmp_path)
    _, thoughts, _, _ = _validate_and_load(run_dir)
    ledger = _reasoning_ledger(thoughts)
    assert len(ledger) == 8
    assert set(ledger["reasoning"]) == {"I observed an event."}
    assert set(ledger["interpretation_scope"]) == {"explicit_appraisal_only_not_hidden_CoT"}


def test_transitions_are_predefined_within_agent_changes(tmp_path):
    run_dir = _fixture(tmp_path)
    _, _, cognitive, end_tick = _validate_and_load(run_dir)
    out = _agent_transitions(cognitive, end_tick)
    assert set(out["transition"]) == {
        "crisis_shock", "immediate_response", "delayed_onset", "recovery_to_endpoint"
    }
    recovery = out[out["transition"] == "recovery_to_endpoint"]
    assert (recovery["delta_trust_final"].round(10) == 0.05).all()


def test_build_cognition_outputs_writes_manifest_and_declares_no_inference(tmp_path):
    run_dir = _fixture(tmp_path)
    payload = build_cognition_outputs(run_dir)
    assert payload["status"] == "PASS"
    assert payload["formal_inference_performed"] is False
    manifest = json.loads((run_dir / "thesis_outputs/cognition/cognition_output_manifest.json").read_text(encoding="utf-8"))
    assert manifest["formal_inference_performed"] is False
    assert manifest["text_coding_performed"] is False
    assert set(manifest["source_run_git_provenance"]) == set()
    assert manifest["postprocessor_git_provenance"]["git_head"]
    assert manifest["postprocessor_git_provenance"]["git_branch"] == "refactor/task005-v32-clean-codebase"
    assert [row["path"] for row in manifest["analysis_code_hashes"]] == [
        "greenconsumer_v33/cognition_outputs.py",
        "run_v33_cognition.py",
    ]
    assert all(len(row["sha256"]) == 64 for row in manifest["analysis_code_hashes"])
    assert len(manifest["generated_outputs"]) == 8


def test_loader_rejects_horizon_mismatch(tmp_path):
    run_dir = _fixture(tmp_path)
    (run_dir / "run_summary.json").write_text(
        json.dumps({"run_id": "synthetic-test-only", "total_ticks": 35}), encoding="utf-8"
    )
    try:
        _validate_and_load(run_dir)
    except ValueError as exc:
        assert "time-horizon mismatch" in str(exc)
    else:
        raise AssertionError("horizon mismatch was not rejected")


def test_loader_rejects_incomplete_agent_tick_panel(tmp_path):
    run_dir = _fixture(tmp_path)
    frame = pd.read_csv(run_dir / "cognitive_records.csv")
    frame = frame[~(
        (frame["exp_id"] == "Rational-Hub-Immediate")
        & (frame["agent_id"] == "A")
        & (frame["tick"] == 7)
    )]
    frame.to_csv(run_dir / "cognitive_records.csv", index=False)
    thoughts = pd.read_csv(run_dir / "agent_thoughts.csv")
    thoughts = thoughts[~(
        (thoughts["exp_id"] == "Rational-Hub-Immediate")
        & (thoughts["agent_id"] == "A")
        & (thoughts["tick"] == 7)
    )]
    thoughts.to_csv(run_dir / "agent_thoughts.csv", index=False)
    try:
        _validate_and_load(run_dir)
    except ValueError as exc:
        assert "incomplete Agent x Tick panel" in str(exc)
    else:
        raise AssertionError("incomplete Agent x Tick panel was not rejected")
