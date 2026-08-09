"""TASK_005 real-LLM manipulation-check pilot preparation.

This module freezes the pilot cohort, condition subset, offline artifact
contracts, and manipulation-check calculations. It deliberately does not
authorize or run real LLM calls in this stage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Mapping

import yaml

from experiment_config import generate_experiment_matrix
from replication_config import (
    LEDGER_FIELDS,
    build_seed_ledger,
    write_seed_ledger_csv,
)
from run_experiments import (
    ReplicationStartupError,
    TASK005_LLM_API_KEY_ENV,
    TASK005_LLM_API_KEY_PLACEHOLDER,
    _is_placeholder_secret,
)


PILOT_ID = "task005-real-manipulation-pilot-v1"
MASTER_SEED = 2026080902
PILOT_REPLICATION_BLOCKS = 2
ALLOWED_REPLICATE_IDS = ("R001", "R002")
PILOT_CONDITION_IDS = (
    "NoClarification-Control",
    "Rational-Hub-Immediate",
    "Empathy-Hub-Immediate",
)
PROVIDER = "OpenAIProvider"
MODEL = "qwen-plus"
TEMPERATURE = 0.3
ENGINEERING_SEPARATION_FLOOR = 0.05
TOPIC_RELEVANCE_WARNING_THRESHOLD = 0.10
REAL_MODE_REJECTION = "PILOT_EXECUTION_NOT_AUTHORIZED"

PRIMARY_DIMENSIONS = (
    "evidence_strength",
    "credibility",
    "valence",
    "arousal",
)


class PilotContractError(RuntimeError):
    """Raised when the pilot preparation contract is violated."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_pilot_credential() -> str:
    value = os.environ.get(TASK005_LLM_API_KEY_ENV, "")
    if _is_placeholder_secret(value):
        raise PilotContractError("missing credential for real pilot preflight")
    return value


def build_pilot_seed_ledger() -> list[dict]:
    rows = build_seed_ledger(
        MASTER_SEED,
        PILOT_REPLICATION_BLOCKS,
        llm_seed_supported="unknown",
        provider_model=MODEL,
        provider_system_fingerprint="unknown",
    )
    if tuple(row["replicate_id"] for row in rows) != ALLOWED_REPLICATE_IDS:
        raise PilotContractError("pilot replicate IDs are not exactly R001-R002")
    return rows


def select_pilot_conditions():
    by_id = {cfg.exp_id: cfg for cfg in generate_experiment_matrix()}
    configs = []
    for exp_id in PILOT_CONDITION_IDS:
        if exp_id not in by_id:
            raise PilotContractError(f"missing pilot condition {exp_id}")
        configs.append(by_id[exp_id])
    return configs


def build_pilot_manifest_rows(ledger_rows: list[dict]) -> list[dict]:
    configs = select_pilot_conditions()
    rows: list[dict] = []
    for ledger in ledger_rows:
        for order, cfg in enumerate(configs, start=1):
            rows.append(
                {
                    "pilot_id": PILOT_ID,
                    "replicate_id": ledger["replicate_id"],
                    "replicate_index": ledger["replicate_index"],
                    "condition_order": order,
                    "exp_id": cfg.exp_id,
                    "content_factor": cfg.content_factor,
                    "channel_factor": cfg.channel_factor,
                    "timing_factor": cfg.timing_factor,
                    "clarification_tick": cfg.clarification_tick,
                    "router_role": "recording" if cfg.is_control else "replay",
                    "simulation_seed": ledger["simulation_seed"],
                    "requested_llm_seed": ledger["requested_llm_seed"],
                    "python_hash_seed": ledger["python_hash_seed"],
                    "PILOT_ONLY": True,
                    "FORMAL_INFERENCE": False,
                    "P_VALUES_COMPUTED": False,
                }
            )
    return rows


def sanitized_model_config() -> dict:
    config_path = Path("configs") / "models_config.yaml"
    conf = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    entries = conf if isinstance(conf, list) else [conf]
    entry = next(
        (
            item
            for item in entries
            if isinstance(item, dict) and "chat" in (item.get("capabilities") or [])
        ),
        entries[0] if entries else {},
    )
    safe = {
        "provider": entry.get("name"),
        "model": entry.get("model"),
        "base_url": entry.get("base_url"),
        "capabilities": list(entry.get("capabilities") or []),
        "temperature": entry.get("temperature"),
        "requested_seed": "from pilot seed ledger",
        "api_key": "<REDACTED>",
    }
    if safe["provider"] != PROVIDER or safe["model"] != MODEL or safe["temperature"] != TEMPERATURE:
        raise PilotContractError("scientific model configuration changed")
    return safe


def write_offline_dry_run_artifacts(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = build_pilot_seed_ledger()
    manifest = build_pilot_manifest_rows(ledger)
    write_seed_ledger_csv(ledger, output_dir / "seed_ledger.csv")
    _write_csv(output_dir / "pilot_manifest.csv", manifest)
    (output_dir / "sanitized_model_config.json").write_text(
        json.dumps(sanitized_model_config(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "replication_blocks": PILOT_REPLICATION_BLOCKS,
        "replicate_ids": list(ALLOWED_REPLICATE_IDS),
        "conditions_per_block": len(PILOT_CONDITION_IDS),
        "condition_ids": list(PILOT_CONDITION_IDS),
        "FORMAL_INFERENCE": False,
        "P_VALUES_COMPUTED": False,
        "PILOT_ONLY": True,
        "REAL_LLM_CALLS": False,
    }
    (output_dir / "manipulation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _write_csv(path: Path, rows: list[Mapping]) -> None:
    if not rows:
        raise PilotContractError(f"cannot write empty CSV {path}")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def validate_record_replay_order(manifest_rows: list[Mapping]) -> bool:
    by_rep: dict[str, list[Mapping]] = {}
    for row in manifest_rows:
        by_rep.setdefault(str(row["replicate_id"]), []).append(row)
    for replicate_id in ALLOWED_REPLICATE_IDS:
        rows = sorted(by_rep.get(replicate_id, []), key=lambda row: int(row["condition_order"]))
        if [row["exp_id"] for row in rows] != list(PILOT_CONDITION_IDS):
            return False
        if [row["router_role"] for row in rows] != ["recording", "replay", "replay"]:
            return False
    return True


def assert_no_replay_miss(rows: Iterable[Mapping]) -> None:
    for row in rows:
        if int(row.get("replay_miss_count", 0) or 0) != 0:
            raise PilotContractError("replay miss count must be zero")


def matched_agent_ids(rational_rows: list[Mapping], empathy_rows: list[Mapping]) -> list[str]:
    rational_ids = {
        str(row["agent_id"])
        for row in rational_rows
        if _truthy(row.get("clarification_detected_by_plan"))
    }
    empathy_ids = {
        str(row["agent_id"])
        for row in empathy_rows
        if _truthy(row.get("clarification_detected_by_plan"))
    }
    if rational_ids != empathy_ids:
        raise PilotContractError("matched Rational/Empathy reach sets differ")
    return sorted(rational_ids)


def compute_manipulation_pairs(
    rational_rows: list[Mapping],
    empathy_rows: list[Mapping],
) -> list[dict]:
    agent_ids = matched_agent_ids(rational_rows, empathy_rows)
    r_by_id = {str(row["agent_id"]): row for row in rational_rows}
    e_by_id = {str(row["agent_id"]): row for row in empathy_rows}
    pairs: list[dict] = []
    for agent_id in agent_ids:
        r = r_by_id[agent_id]
        e = e_by_id[agent_id]
        pairs.append(
            {
                "agent_id": agent_id,
                "D_evidence": _float(r["evidence_strength"]) - _float(e["evidence_strength"]),
                "D_credibility": _float(r["credibility"]) - _float(e["credibility"]),
                "D_valence": _float(e["valence"]) - _float(r["valence"]),
                "D_arousal": _float(e["arousal"]) - _float(r["arousal"]),
                "topic_relevance_abs_diff": abs(
                    _float(r["topic_relevance"]) - _float(e["topic_relevance"])
                ),
            }
        )
    return pairs


def summarize_manipulation_pairs(pairs: list[Mapping]) -> dict:
    if not pairs:
        raise PilotContractError("no matched manipulation pairs")
    summary = {
        "pilot_id": PILOT_ID,
        "FORMAL_INFERENCE": False,
        "P_VALUES_COMPUTED": False,
        "PILOT_ONLY": True,
        "threshold_type": "engineering_construct_separation_floor",
        "engineering_floor": ENGINEERING_SEPARATION_FLOOR,
        "literature_derived": False,
        "statistical_significance_threshold": False,
        "dimensions": {},
    }
    weak = []
    for dim in ("D_evidence", "D_credibility", "D_valence", "D_arousal"):
        values = [_float(row[dim]) for row in pairs]
        expected_positive = [value > 0 for value in values]
        mean_value = statistics.fmean(values)
        summary["dimensions"][dim] = {
            "mean": mean_value,
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "expected_direction_proportion": sum(expected_positive) / len(values),
            "passes_direction": mean_value > 0,
            "passes_engineering_floor": mean_value >= ENGINEERING_SEPARATION_FLOOR,
        }
        if mean_value < ENGINEERING_SEPARATION_FLOOR:
            weak.append(dim)
    topic_mean = statistics.fmean(_float(row["topic_relevance_abs_diff"]) for row in pairs)
    summary["topic_relevance_abs_mean_diff"] = topic_mean
    summary["topic_relevance_warning"] = (
        "TOPIC_RELEVANCE_IMBALANCE"
        if topic_mean > TOPIC_RELEVANCE_WARNING_THRESHOLD
        else ""
    )
    summary["MANIPULATION_STRENGTH"] = "WEAK" if weak else "PASS"
    summary["weak_dimensions"] = weak
    return summary


def fallback_counts_pass(rows: Iterable[Mapping]) -> bool:
    for row in rows:
        if int(row.get("semantic_fallback_used", 0) or 0) != 0:
            return False
        if int(row.get("plan_fallback_used", 0) or 0) != 0:
            return False
        if int(row.get("json_parse_failure", 0) or 0) != 0:
            return False
    return True


def _truthy(value) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _float(value) -> float:
    try:
        return float(value)
    except Exception as exc:
        raise PilotContractError(f"non-numeric manipulation value: {type(exc).__name__}") from exc


def assert_real_execution_authorized(args) -> None:
    if getattr(args, "execute_real", False):
        raise PilotContractError(REAL_MODE_REJECTION)


def preflight() -> dict:
    require_pilot_credential()
    ledger = build_pilot_seed_ledger()
    manifest = build_pilot_manifest_rows(ledger)
    if not validate_record_replay_order(manifest):
        raise PilotContractError("record/replay order invalid")
    return {
        "pilot_id": PILOT_ID,
        "master_seed": MASTER_SEED,
        "replicate_ids": list(ALLOWED_REPLICATE_IDS),
        "condition_ids": list(PILOT_CONDITION_IDS),
        "sanitized_model_config": sanitized_model_config(),
        "REAL_LLM_CALLS": False,
    }


def run_offline_self_test() -> dict:
    ledger = build_pilot_seed_ledger()
    manifest = build_pilot_manifest_rows(ledger)
    if len(ledger) != 2 or tuple(row["replicate_id"] for row in ledger) != ALLOWED_REPLICATE_IDS:
        raise PilotContractError("ledger identity mismatch")
    if len(manifest) != 6 or not validate_record_replay_order(manifest):
        raise PilotContractError("pilot manifest mismatch")
    rational = [
        {
            "agent_id": "A001",
            "clarification_detected_by_plan": True,
            "evidence_strength": 0.80,
            "credibility": 0.75,
            "valence": 0.20,
            "arousal": 0.25,
            "topic_relevance": 0.91,
        },
        {
            "agent_id": "A002",
            "clarification_detected_by_plan": True,
            "evidence_strength": 0.70,
            "credibility": 0.65,
            "valence": 0.30,
            "arousal": 0.20,
            "topic_relevance": 0.88,
        },
    ]
    empathy = [
        {
            "agent_id": "A001",
            "clarification_detected_by_plan": True,
            "evidence_strength": 0.45,
            "credibility": 0.50,
            "valence": 0.70,
            "arousal": 0.62,
            "topic_relevance": 0.86,
        },
        {
            "agent_id": "A002",
            "clarification_detected_by_plan": True,
            "evidence_strength": 0.50,
            "credibility": 0.48,
            "valence": 0.66,
            "arousal": 0.58,
            "topic_relevance": 0.84,
        },
    ]
    pairs = compute_manipulation_pairs(rational, empathy)
    summary = summarize_manipulation_pairs(pairs)
    if summary["MANIPULATION_STRENGTH"] != "PASS":
        raise PilotContractError("offline manipulation self-test should pass")
    if not fallback_counts_pass(
        [
            {"semantic_fallback_used": 0, "plan_fallback_used": 0, "json_parse_failure": 0},
            {"semantic_fallback_used": 0, "plan_fallback_used": 0, "json_parse_failure": 0},
        ]
    ):
        raise PilotContractError("fallback count logic failed")
    return summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline-test", action="store_true")
    parser.add_argument("--execute-real", action="store_true")
    parser.add_argument("--output-dir", default="")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        assert_real_execution_authorized(args)
        if args.preflight:
            print(json.dumps(preflight(), sort_keys=True))
            return 0
        if args.dry_run:
            output_dir = Path(args.output_dir) if args.output_dir else Path(tempfile.mkdtemp())
            print(json.dumps(write_offline_dry_run_artifacts(output_dir), sort_keys=True))
            return 0
        if args.offline_test:
            print(json.dumps(run_offline_self_test(), sort_keys=True))
            return 0
        raise PilotContractError(REAL_MODE_REJECTION)
    except (PilotContractError, ReplicationStartupError) as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
