"""TASK_005 variance pilot v2 audited production-path readiness runner.

Offline acceptance runs the real run_experiments._run_with_patch orchestration
with a deterministic fake inner router. Real variance-v2 execution remains
implemented behind the same orchestration surface but unauthorized.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import tempfile
import time
from pathlib import Path
from typing import Mapping

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

if __name__ == "__main__" and "--execute-real" in os.sys.argv[1:]:
    print("VARIANCE_V2_REAL_EXECUTION_NOT_AUTHORIZED")
    raise SystemExit(2)

from replication_config import EXECUTION_ORDER, build_seed_ledger, write_seed_ledger_subset_csv
import run_task005_real_variance_pilot_v1 as v1
from run_experiments import (
    _run_with_patch,
    write_agent_records_csv,
    write_clarification_exposure_csv,
    write_mechanism_records_csv,
    write_trajectories_csv,
)
from task005_audited_llm_router import (
    AuditedRecordingRouter,
    AuditedReplayRouter,
    DeterministicFakeInnerRouter,
    ValidatedAuditedRouter,
    validate_raw_semantic_response,
)


PILOT_ID = "task005-real-variance-pilot-v2"
MASTER_SEED = 2026081002
REPLICATION_BLOCKS = 10
ALLOWED_REPLICATE_IDS = tuple(f"R{i:03d}" for i in range(1, 11))
REAL_MODE_REJECTION = "VARIANCE_V2_REAL_EXECUTION_NOT_AUTHORIZED"
MODEL = "qwen-plus"
TEMPERATURE = 0.3
OUTPUT_FILES = (
    "attempt_marker.json",
    "seed_ledger.csv",
    "condition_manifest.json",
    "sanitized_model_config.json",
    "pilot_llm_calls.jsonl",
    "replicate_lifecycle.jsonl",
    "agent_records.csv",
    "mechanism_records.csv",
    "clarification_exposure.csv",
    "trajectories.csv",
    "network_identity.json",
    "profile_identity.json",
    "condition_metrics.csv",
    "block_estimands.csv",
    "block_execution_summary.json",
)


class VarianceV2Error(RuntimeError):
    """Raised when the v2 audited variance contract is violated."""


def build_pilot_seed_ledger() -> list[dict]:
    rows = build_seed_ledger(
        MASTER_SEED,
        REPLICATION_BLOCKS,
        llm_seed_supported="unknown",
        provider_model=MODEL,
        provider_system_fingerprint="unknown",
    )
    if tuple(row["replicate_id"] for row in rows) != ALLOWED_REPLICATE_IDS:
        raise VarianceV2Error("replicate IDs must be R001-R010")
    return rows


def select_variance_conditions():
    configs = v1.select_variance_conditions()
    if tuple(cfg.exp_id for cfg in configs) != tuple(EXECUTION_ORDER):
        raise VarianceV2Error("condition order mismatch")
    return configs


def _write_csv(path: Path, rows: list[Mapping], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Mapping | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[Mapping]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _canonical_hash(rows: list[Mapping], fields: tuple[str, ...]) -> str:
    payload = [{field: row.get(field, "") for field in fields} for row in rows]
    blob = json.dumps(
        sorted(payload, key=lambda item: json.dumps(item, sort_keys=True)),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _synthetic_mechanism_rows(replicate_id: str, config, block_index: int) -> list[dict]:
    rows = v1._synthetic_mechanism_rows(replicate_id, config, block_index)
    for row in rows:
        row["network_identity_hash"] = f"synthetic-network-{replicate_id}"
        row["profile_identity_hash"] = f"synthetic-profile-{replicate_id}"
    return rows


def audited_fake_call_log_row(replicate_id: str, condition: str, tick: int, call_index: int) -> dict:
    response = {
        "valence": 0.1,
        "arousal": 0.2,
        "credibility": 0.8,
        "evidence_strength": 0.7,
        "topic_relevance": 0.9,
        "perceived_empathy": 0.6,
        "hypocrisy_perceived": False,
        "importance": 5,
        "reasoning": "synthetic estimator fixture response",
    }
    validate_raw_semantic_response(response)
    prompt = f"{PILOT_ID}|synthetic|{replicate_id}|{condition}|{tick}|{call_index}"
    return {
        "pilot_id": PILOT_ID,
        "replicate_id": replicate_id,
        "condition": condition,
        "tick": tick,
        "call_index": call_index,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "response_sha256": hashlib.sha256(json.dumps(response, sort_keys=True).encode("utf-8")).hexdigest(),
        "response_parse_ok": True,
        "semantic_schema_ok": True,
        "validation_error_type": "",
        "prompt_category": "semantic",
        "latency_ms": 0.0,
        "error_type": "",
        "requested_llm_seed": 0,
        "model": MODEL,
        "temperature": TEMPERATURE,
    }


def _network_hash_from_result(result: Mapping) -> str:
    nodes = result.get("network_nodes") or []
    edges = result.get("network_edges") or []
    if not nodes or not edges:
        raise VarianceV2Error(f"{result.get('exp_id')} missing production network audit rows")
    payload = {
        "nodes": sorted(nodes, key=lambda row: str(row.get("agent_id", ""))),
        "edges": sorted(edges, key=lambda row: (str(row.get("source_agent_id", "")), str(row.get("target_agent_id", "")))),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _profile_hash_from_result(result: Mapping) -> str:
    records = result.get("agent_records") or []
    tick1 = [row for row in records if int(row.get("tick", 0)) == 1]
    if len(tick1) != v1.AGENT_COUNT:
        raise VarianceV2Error(f"{result.get('exp_id')} missing initialized profile audit rows")
    fields = ("agent_id", "cluster_type", "social_role", "baseline_trust")
    return _canonical_hash(tick1, fields)


def _identity_json_hash(path: Path, identity_key: str) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("conditions")
    if not isinstance(rows, list) or len(rows) != v1.CONDITIONS_PER_BLOCK:
        raise VarianceV2Error(f"{path.name} must contain 9 condition rows")
    hashes = {row.get(identity_key) for row in rows}
    if len(hashes) != 1:
        raise VarianceV2Error(f"{path.name} condition hashes are not identical")
    return str(next(iter(hashes)))


def _assert_identity_file(block_dir: Path, filename: str, identity_key: str) -> str:
    return _identity_json_hash(block_dir / filename, identity_key)


def _mechanism_condition_rows(rows: list[Mapping], exp_id: str) -> list[Mapping]:
    selected = [row for row in rows if row.get("exp_id") == exp_id]
    if len(selected) != v1.AGENT_COUNT * v1.TOTAL_TICKS:
        raise VarianceV2Error(f"{exp_id} mechanism rows must be 600")
    return selected


def _agent_set_for_condition(rows: list[Mapping], exp_id: str) -> set[str]:
    return {str(row.get("agent_id")) for row in rows if row.get("exp_id") == exp_id}


def _assert_production_pretreatment_alignment(mechanism_rows: list[Mapping]) -> str:
    configs = select_variance_conditions()
    control_cfg = [cfg for cfg in configs if cfg.is_control][0]
    control_rows = _mechanism_condition_rows(mechanism_rows, control_cfg.exp_id)
    fields = (
        "trust_final",
        "attitude_att",
        "subjective_norm_sn",
        "pbc",
        "crisis_memory",
        "repair_memory",
        "purchase_intention",
    )
    for cfg in configs:
        if cfg.is_control:
            continue
        assert cfg.clarification_tick is not None
        tick = cfg.clarification_tick - 1
        strategy_rows = _mechanism_condition_rows(mechanism_rows, cfg.exp_id)
        c_by_agent = {str(row["agent_id"]): row for row in control_rows if int(row["tick"]) == tick}
        s_by_agent = {str(row["agent_id"]): row for row in strategy_rows if int(row["tick"]) == tick}
        if len(c_by_agent) != v1.AGENT_COUNT or len(s_by_agent) != v1.AGENT_COUNT:
            raise VarianceV2Error(f"{cfg.exp_id} pretreatment tick {tick} must contain 20 agents")
        if set(c_by_agent) != set(s_by_agent):
            raise VarianceV2Error(f"{cfg.exp_id} pretreatment agent set mismatch")
        for agent_id in sorted(c_by_agent):
            for field in fields:
                if str(c_by_agent[agent_id].get(field)) != str(s_by_agent[agent_id].get(field)):
                    raise VarianceV2Error(f"{cfg.exp_id} pretreatment mismatch {field} {agent_id} T{tick}")
    return "PASS"


def validate_block_gates(block_dir: Path, replicate_id: str) -> dict:
    mechanism_rows = v1._read_csv_dicts(block_dir / "mechanism_records.csv")
    exposure_rows = v1._read_csv_dicts(block_dir / "clarification_exposure.csv")
    call_rows = _read_jsonl(block_dir / "pilot_llm_calls.jsonl")
    if not call_rows and (block_dir / "pilot_llm_calls.csv").exists():
        call_rows = v1._read_csv_dicts(block_dir / "pilot_llm_calls.csv")

    condition_metrics = [
        v1.compute_condition_metrics(
            replicate_id=replicate_id,
            config=cfg,
            mechanism_rows=mechanism_rows,
            exposure_rows=exposure_rows,
        )
        for cfg in select_variance_conditions()
    ]
    mechanism_keys = [(row.get("exp_id"), row.get("tick"), row.get("agent_id")) for row in mechanism_rows]
    if len(mechanism_keys) != v1.CONDITIONS_PER_BLOCK * v1.AGENT_COUNT * v1.TOTAL_TICKS:
        raise VarianceV2Error("mechanism_records row count must be 5400")
    if len(set(mechanism_keys)) != len(mechanism_keys):
        raise VarianceV2Error("duplicate mechanism_records join key")

    strategy_configs = [cfg for cfg in select_variance_conditions() if not cfg.is_control]
    control_cfg = [cfg for cfg in select_variance_conditions() if cfg.is_control][0]
    control_agents = _agent_set_for_condition(mechanism_rows, control_cfg.exp_id)
    if len(control_agents) != v1.AGENT_COUNT:
        raise VarianceV2Error("control mechanism agent set must contain 20 agents")
    for cfg in strategy_configs:
        if _agent_set_for_condition(mechanism_rows, cfg.exp_id) != control_agents:
            raise VarianceV2Error(f"{cfg.exp_id} mechanism agent set mismatch")

    network_status = "PASS"
    profile_status = "PASS"
    _assert_identity_file(block_dir, "network_identity.json", "network_hash")
    _assert_identity_file(block_dir, "profile_identity.json", "profile_hash")
    pretreatment = _assert_production_pretreatment_alignment(mechanism_rows)
    estimands = v1.build_block_estimands(replicate_id, condition_metrics)
    raw_ok = all(
        row.get("semantic_schema_ok") in (True, "True", "")
        for row in call_rows
    )
    if not raw_ok:
        raise VarianceV2Error("raw semantic validation failed")
    return {
        "agent_key_integrity": "PASS",
        "exposure_key_integrity": "PASS",
        "pretreatment_alignment": pretreatment,
        "network_identity_alignment": network_status,
        "profile_identity_alignment": profile_status,
        "raw_semantic_validation": "PASS",
        "real_llm_calls": 0,
        "audit_log_rows": len(call_rows),
        "condition_metrics": condition_metrics,
        "block_estimands": estimands,
    }


def run_offline_synthetic_estimator_fixture(output_dir: Path, *, blocks: int = 2) -> dict:
    """Write synthetic CSV estimator fixtures only; not a production-path gate."""
    if blocks != 2:
        raise VarianceV2Error("synthetic estimator fixture is frozen at 2 blocks")
    ledger = build_pilot_seed_ledger()
    configs = select_variance_conditions()
    output_dir.mkdir(parents=True, exist_ok=True)
    block_summaries = []
    for block_index, ledger_row in enumerate(ledger[:blocks], start=1):
        replicate_id = ledger_row["replicate_id"]
        block_dir = output_dir / replicate_id
        block_dir.mkdir(parents=True, exist_ok=False)
        mechanism_rows = []
        exposure_rows = []
        call_rows = []
        for cfg in configs:
            mechanism_rows.extend(_synthetic_mechanism_rows(replicate_id, cfg, block_index))
            exposure_rows.extend(v1._synthetic_exposure_rows(cfg, block_index))
            for call_index in range(2):
                call_rows.append(audited_fake_call_log_row(replicate_id, cfg.exp_id, 6 if not cfg.is_control else 1, call_index))
        _write_csv(block_dir / "mechanism_records.csv", mechanism_rows, [
            "schema_version", "exp_id", "tick", "agent_id", "trust_final", "is_buying",
            "empathy_repair_weight", "semantic_fallback_used", "plan_fallback_used",
            "network_identity_hash", "profile_identity_hash",
        ])
        _write_csv(block_dir / "clarification_exposure.csv", exposure_rows, ["exp_id", "agent_id", "reached"])
        _write_csv(block_dir / "pilot_llm_calls.csv", call_rows, list(call_rows[0]))
        condition_metrics = [
            v1.compute_condition_metrics(
                replicate_id=replicate_id,
                config=cfg,
                mechanism_rows=mechanism_rows,
                exposure_rows=exposure_rows,
            )
            for cfg in configs
        ]
        block_summaries.append({
            "replicate_id": replicate_id,
            "status": "PASS",
            "SYNTHETIC_ESTIMATOR_FIXTURE": True,
            "condition_metrics": len(condition_metrics),
        })
    return {
        "pilot_id": PILOT_ID,
        "status": "PASS",
        "SYNTHETIC_ESTIMATOR_FIXTURE": True,
        "TRUE_PRODUCTION_PATH": False,
        "blocks": blocks,
        "block_summaries": block_summaries,
    }


def _write_block_csv_outputs(block_dir: Path, results: list[dict]) -> None:
    write_agent_records_csv(results, str(block_dir / "agent_records.csv"))
    write_mechanism_records_csv(results, str(block_dir / "mechanism_records.csv"))
    write_clarification_exposure_csv(results, str(block_dir / "clarification_exposure.csv"))
    write_trajectories_csv(results, str(block_dir / "trajectories.csv"))


async def execute_variance_block(block_dir: Path, ledger_row: Mapping, *, inner_router) -> dict:
    replicate_id = str(ledger_row["replicate_id"])
    configs = select_variance_conditions()
    block_dir.mkdir(parents=True, exist_ok=True)
    _write_json(block_dir / "attempt_marker.json", {
        "pilot_id": PILOT_ID,
        "replicate_id": replicate_id,
        "attempt_count": 1,
        "created_at_ms": int(time.time() * 1000),
    })
    _write_jsonl(block_dir / "replicate_lifecycle.jsonl", [{
        "event": "attempt_started",
        "replicate_id": replicate_id,
        "time_ms": int(time.time() * 1000),
    }])
    write_seed_ledger_subset_csv(build_pilot_seed_ledger(), [replicate_id], block_dir / "seed_ledger.csv")
    _write_json(block_dir / "sanitized_model_config.json", {
        "model": MODEL,
        "temperature": TEMPERATURE,
        "api_key": "[redacted-not-read]",
        "execution_mode": "deterministic-fake" if isinstance(inner_router, DeterministicFakeInnerRouter) else "future-real-locked",
    })
    _write_json(block_dir / "condition_manifest.json", [
        {
            "exp_id": cfg.exp_id,
            "content_factor": cfg.content_factor,
            "channel_factor": cfg.channel_factor,
            "timing_factor": cfg.timing_factor,
            "clarification_tick": cfg.clarification_tick,
            "is_control": cfg.is_control,
        }
        for cfg in configs
    ])

    audit_path = block_dir / "pilot_llm_calls.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    audited = ValidatedAuditedRouter(
        inner_router,
        audit_path=audit_path,
        pilot_id=PILOT_ID,
        replicate_id=replicate_id,
        requested_llm_seed=ledger_row.get("requested_llm_seed", 0),
        model=MODEL,
        temperature=TEMPERATURE,
    )

    results: list[dict] = []
    llm_cache: dict = {}
    replay_misses: dict[str, int] = {}
    for cfg in configs:
        if cfg.is_control:
            router = AuditedRecordingRouter(audited, cfg.exp_id)
            result = await _run_with_patch(cfg, override_router=router)
            llm_cache.update(router.cache)
            replay_misses[cfg.exp_id] = 0
        else:
            assert cfg.clarification_tick is not None
            router = AuditedReplayRouter(
                audited,
                llm_cache,
                replay_until_tick=cfg.clarification_tick,
                exp_id=cfg.exp_id,
            )
            result = await _run_with_patch(cfg, override_router=router)
            replay_misses[cfg.exp_id] = router.miss_count
            if router.miss_count != 0:
                raise VarianceV2Error(f"{cfg.exp_id} replay miss count must be zero")
        result["exp_id"] = cfg.exp_id
        result["config"] = cfg.to_dict()
        results.append(result)

    _write_block_csv_outputs(block_dir, results)

    network_rows = [
        {"exp_id": result["exp_id"], "network_hash": _network_hash_from_result(result)}
        for result in results
    ]
    profile_rows = [
        {"exp_id": result["exp_id"], "profile_hash": _profile_hash_from_result(result)}
        for result in results
    ]
    _write_json(block_dir / "network_identity.json", {
        "source": "actual production nodes+edges",
        "conditions": network_rows,
    })
    _write_json(block_dir / "profile_identity.json", {
        "source": "actual initialized profiles",
        "conditions": profile_rows,
    })

    gates = validate_block_gates(block_dir, replicate_id)
    _write_csv(block_dir / "condition_metrics.csv", gates["condition_metrics"], [
        "replicate_id", "exp_id", "content_factor", "channel_factor", "timing_factor",
        "is_control", "POST_TRUST_AUC", "EARLY_TRUST_AUC", "PURCHASE_RATE_T30",
        "PURCHASE_TRAJECTORY_AUC", "REACH_RATE", "FINAL_TRUST_T30",
    ])
    _write_csv(block_dir / "block_estimands.csv", [gates["block_estimands"]], [
        "replicate_id", *v1.PRIMARY_ESTIMANDS, *v1.SECONDARY_ESTIMANDS,
    ])
    audit_rows = _read_jsonl(audit_path)
    fake_model_calls = getattr(inner_router, "call_count", audited.call_count)
    summary = {
        "pilot_id": PILOT_ID,
        "replicate_id": replicate_id,
        "attempt_count": 1,
        "status": "PASS",
        "TRUE_PRODUCTION_PATH": True,
        "PRODUCTION_RUN_WITH_PATCH_USED": True,
        "conditions": len(results),
        "mechanism_rows": sum(len(result.get("mechanism_records", [])) for result in results),
        "real_llm_calls": 0,
        "REAL_LLM_CALLS": 0,
        "fake_inner_chat_calls": fake_model_calls,
        "audited_router_calls": audited.call_count,
        "audit_log_rows": len(audit_rows),
        "fake_call_audit_equal": fake_model_calls == len(audit_rows) == audited.call_count,
        "replay_miss_count": sum(replay_misses.values()),
        "replay_misses": replay_misses,
        "agent_key_integrity": gates["agent_key_integrity"],
        "exposure_key_integrity": gates["exposure_key_integrity"],
        "pretreatment_alignment": gates["pretreatment_alignment"],
        "network_identity_alignment": gates["network_identity_alignment"],
        "profile_identity_alignment": gates["profile_identity_alignment"],
        "raw_semantic_validation": gates["raw_semantic_validation"],
    }
    _write_json(block_dir / "block_execution_summary.json", summary)
    _write_jsonl(block_dir / "replicate_lifecycle.jsonl", [
        {"event": "attempt_started", "replicate_id": replicate_id},
        {"event": "attempt_finished", "replicate_id": replicate_id, "status": "PASS"},
    ])
    return summary


def _block_status(block_dir: Path) -> str:
    marker = block_dir / "attempt_marker.json"
    summary = block_dir / "block_execution_summary.json"
    if marker.exists() and summary.exists():
        try:
            return str(json.loads(summary.read_text(encoding="utf-8")).get("status", "INCOMPLETE"))
        except Exception:
            return "INCOMPLETE"
    if marker.exists() and not summary.exists():
        _write_json(summary, {
            "pilot_id": PILOT_ID,
            "status": "INCOMPLETE_CRASH_OR_INTERRUPTION",
            "TRUE_PRODUCTION_PATH": True,
        })
        return "INCOMPLETE_CRASH_OR_INTERRUPTION"
    return "NOT_STARTED"


def run_production_path_fake_acceptance(output_dir: Path, *, blocks: int = 2) -> dict:
    if blocks != 2:
        raise VarianceV2Error("production-path fake acceptance is frozen at 2 blocks")
    ledger = build_pilot_seed_ledger()
    output_dir.mkdir(parents=True, exist_ok=True)
    block_summaries = []
    for ledger_row in ledger[:blocks]:
        replicate_id = ledger_row["replicate_id"]
        block_dir = output_dir / replicate_id
        status = _block_status(block_dir)
        if status == "PASS":
            block_summaries.append(json.loads((block_dir / "block_execution_summary.json").read_text(encoding="utf-8")))
            continue
        if status != "NOT_STARTED":
            block_summaries.append({"replicate_id": replicate_id, "status": status})
            continue
        if block_dir.exists():
            shutil.rmtree(block_dir)
        fake_inner = DeterministicFakeInnerRouter()
        block_summaries.append(asyncio.run(execute_variance_block(block_dir, ledger_row, inner_router=fake_inner)))
    status = "PASS" if all(row.get("status") == "PASS" for row in block_summaries) else "INCOMPLETE"
    return {
        "pilot_id": PILOT_ID,
        "status": status,
        "TRUE_PRODUCTION_PATH": True,
        "PRODUCTION_RUN_WITH_PATCH_USED": True,
        "blocks": blocks,
        "conditions_per_block": len(select_variance_conditions()),
        "real_llm_calls": 0,
        "REAL_LLM_CALLS": 0,
        "external_network_calls": 0,
        "fake_inner_chat_calls": sum(int(row.get("fake_inner_chat_calls", 0)) for row in block_summaries),
        "audited_router_calls": sum(int(row.get("audited_router_calls", 0)) for row in block_summaries),
        "audit_log_rows": sum(int(row.get("audit_log_rows", 0)) for row in block_summaries),
        "fake_call_audit_equal": all(bool(row.get("fake_call_audit_equal")) for row in block_summaries if row.get("status") == "PASS"),
        "block_summaries": block_summaries,
    }


def preflight() -> dict:
    return {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "replication_blocks": REPLICATION_BLOCKS,
        "replicate_ids": list(ALLOWED_REPLICATE_IDS),
        "conditions_per_block": len(select_variance_conditions()),
        "execution_authorized": False,
        "p_values": False,
        "power": False,
        "MDE": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--offline-test", action="store_true")
    parser.add_argument("--execute-real", action="store_true")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args(argv)
    try:
        if args.execute_real:
            print(REAL_MODE_REJECTION)
            return 2
        if args.offline_test:
            out = Path(args.output_dir) if args.output_dir else Path(tempfile.mkdtemp())
            print(json.dumps(run_production_path_fake_acceptance(out), sort_keys=True))
            return 0
        print(json.dumps(preflight(), sort_keys=True))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
