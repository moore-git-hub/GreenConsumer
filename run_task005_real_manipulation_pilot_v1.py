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

# The pilot runner must protect its own import path from HuggingFace /
# Transformers metadata lookups. Use assignment, not setdefault, so parent
# env values such as HF_HUB_OFFLINE=0 cannot weaken offline preparation tests.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import yaml

from experiment_config import generate_experiment_matrix
from replication_config import (
    build_seed_ledger,
    write_seed_ledger_csv,
)
from run_experiments import (
    ReplicationStartupError,
    TASK005_LLM_API_KEY_ENV,
    TASK005_LLM_API_KEY_PLACEHOLDER,
    _is_placeholder_secret,
)
from simulation_core import MECHANISM_RECORDS_FIELDS


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
    "semantic_evidence_strength",
    "semantic_credibility",
    "semantic_valence",
    "semantic_arousal",
)
REQUIRED_SEMANTIC_SOURCE_FIELDS = (
    "semantic_evidence_strength",
    "semantic_credibility",
    "semantic_valence",
    "semantic_arousal",
    "semantic_topic_relevance",
    "semantic_hypocrisy_perceived",
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


def assert_mechanism_schema_alignment() -> None:
    missing = set(REQUIRED_SEMANTIC_SOURCE_FIELDS) - set(MECHANISM_RECORDS_FIELDS)
    if missing:
        raise PilotContractError(f"mechanism schema missing semantic fields: {sorted(missing)}")


def _detected_rows(rows: list[Mapping], label: str) -> list[Mapping]:
    seen: set[str] = set()
    detected = []
    for row in rows:
        agent_id = str(row.get("agent_id", ""))
        if not agent_id:
            raise PilotContractError(f"{label} row missing agent_id")
        if agent_id in seen:
            raise PilotContractError(f"duplicate agent_id in {label}: {agent_id}")
        seen.add(agent_id)
        if _truthy(row.get("clarification_detected_by_plan")):
            for field in REQUIRED_SEMANTIC_SOURCE_FIELDS:
                if field not in row:
                    raise PilotContractError(f"{label} row missing {field}")
            detected.append(row)
    return detected


def matched_agent_ids(rational_rows: list[Mapping], empathy_rows: list[Mapping]) -> list[str]:
    rational_ids = {str(row["agent_id"]) for row in _detected_rows(rational_rows, "rational")}
    empathy_ids = {str(row["agent_id"]) for row in _detected_rows(empathy_rows, "empathy")}
    if rational_ids != empathy_ids:
        raise PilotContractError("matched Rational/Empathy reach sets differ")
    return sorted(rational_ids)


def compute_manipulation_pairs(
    replicate_id: str,
    rational_rows: list[Mapping],
    empathy_rows: list[Mapping],
) -> list[dict]:
    assert_mechanism_schema_alignment()
    if replicate_id not in ALLOWED_REPLICATE_IDS:
        raise PilotContractError("replicate_id must be R001 or R002")
    agent_ids = matched_agent_ids(rational_rows, empathy_rows)
    r_by_id = {str(row["agent_id"]): row for row in _detected_rows(rational_rows, "rational")}
    e_by_id = {str(row["agent_id"]): row for row in _detected_rows(empathy_rows, "empathy")}
    pairs: list[dict] = []
    for agent_id in agent_ids:
        r = r_by_id[agent_id]
        e = e_by_id[agent_id]
        pairs.append(
            {
                "replicate_id": replicate_id,
                "agent_id": agent_id,
                "D_evidence": (
                    _float(r["semantic_evidence_strength"])
                    - _float(e["semantic_evidence_strength"])
                ),
                "D_credibility": (
                    _float(r["semantic_credibility"])
                    - _float(e["semantic_credibility"])
                ),
                "D_valence": _float(e["semantic_valence"]) - _float(r["semantic_valence"]),
                "D_arousal": _float(e["semantic_arousal"]) - _float(r["semantic_arousal"]),
                "rational_topic_relevance": _float(r["semantic_topic_relevance"]),
                "empathy_topic_relevance": _float(e["semantic_topic_relevance"]),
                "rational_hypocrisy_perceived": bool(r["semantic_hypocrisy_perceived"]),
                "empathy_hypocrisy_perceived": bool(e["semantic_hypocrisy_perceived"]),
            }
        )
    return pairs


def summarize_manipulation_by_block(pairs: list[Mapping]) -> dict:
    if not pairs:
        raise PilotContractError("no matched manipulation pairs")
    by_rep: dict[str, list[Mapping]] = {}
    for row in pairs:
        by_rep.setdefault(str(row.get("replicate_id", "")), []).append(row)
    if set(by_rep) != set(ALLOWED_REPLICATE_IDS):
        raise PilotContractError("manipulation pairs must contain exactly R001 and R002")

    per_replicate: dict[str, dict] = {}
    all_blocks_direction_pass = True
    for replicate_id in ALLOWED_REPLICATE_IDS:
        rows = by_rep[replicate_id]
        dims = {}
        for dim in ("D_evidence", "D_credibility", "D_valence", "D_arousal"):
            values = [_float(row[dim]) for row in rows]
            mean_value = statistics.fmean(values)
            dims[dim] = {"mean": mean_value, "passes_direction": mean_value > 0}
            if mean_value <= 0:
                all_blocks_direction_pass = False
        per_replicate[replicate_id] = {"dimensions": dims}

    pooled = _summarize_pooled_pairs(pairs)
    pooled["per_replicate"] = per_replicate
    pooled["all_blocks_direction_pass"] = all_blocks_direction_pass
    pooled["DIRECTION_GATE"] = "PASS" if all_blocks_direction_pass else "FAIL"
    return pooled


def _summarize_pooled_pairs(pairs: list[Mapping]) -> dict:
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
    rational_topic_mean = statistics.fmean(
        _float(row["rational_topic_relevance"]) for row in pairs
    )
    empathy_topic_mean = statistics.fmean(
        _float(row["empathy_topic_relevance"]) for row in pairs
    )
    topic_group_mean_diff = abs(rational_topic_mean - empathy_topic_mean)
    summary["rational_topic_relevance_mean"] = rational_topic_mean
    summary["empathy_topic_relevance_mean"] = empathy_topic_mean
    summary["topic_relevance_group_mean_abs_diff"] = topic_group_mean_diff
    summary["topic_relevance_paired_abs_mean_diff_supplementary"] = statistics.fmean(
        abs(_float(row["rational_topic_relevance"]) - _float(row["empathy_topic_relevance"]))
        for row in pairs
    )
    summary["topic_relevance_warning"] = (
        "TOPIC_RELEVANCE_IMBALANCE"
        if topic_group_mean_diff > TOPIC_RELEVANCE_WARNING_THRESHOLD
        else ""
    )
    summary["rational_hypocrisy_perceived_rate"] = statistics.fmean(
        1.0 if row["rational_hypocrisy_perceived"] else 0.0 for row in pairs
    )
    summary["empathy_hypocrisy_perceived_rate"] = statistics.fmean(
        1.0 if row["empathy_hypocrisy_perceived"] else 0.0 for row in pairs
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
        _semantic_input_row("A001", 0.80, 0.75, 0.20, 0.25, 0.91, False),
        _semantic_input_row("A002", 0.70, 0.65, 0.30, 0.20, 0.88, True),
    ]
    empathy = [
        _semantic_input_row("A001", 0.45, 0.50, 0.70, 0.62, 0.86, True),
        _semantic_input_row("A002", 0.50, 0.48, 0.66, 0.58, 0.84, True),
    ]
    pairs = []
    for replicate_id in ALLOWED_REPLICATE_IDS:
        pairs.extend(compute_manipulation_pairs(replicate_id, rational, empathy))
    summary = summarize_manipulation_by_block(pairs)
    if summary["MANIPULATION_STRENGTH"] != "PASS":
        raise PilotContractError("offline manipulation self-test should pass")
    if summary["DIRECTION_GATE"] != "PASS":
        raise PilotContractError("offline direction gate should pass")
    if not fallback_counts_pass(
        [
            {"semantic_fallback_used": 0, "plan_fallback_used": 0, "json_parse_failure": 0},
            {"semantic_fallback_used": 0, "plan_fallback_used": 0, "json_parse_failure": 0},
        ]
    ):
        raise PilotContractError("fallback count logic failed")
    return summary


def _semantic_input_row(
    agent_id: str,
    evidence: float,
    credibility: float,
    valence: float,
    arousal: float,
    topic: float,
    hypocrisy: bool,
) -> dict:
    return {
        "agent_id": agent_id,
        "clarification_detected_by_plan": True,
        "semantic_evidence_strength": evidence,
        "semantic_credibility": credibility,
        "semantic_valence": valence,
        "semantic_arousal": arousal,
        "semantic_topic_relevance": topic,
        "semantic_hypocrisy_perceived": hypocrisy,
    }


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
