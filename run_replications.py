"""TASK_005 replicate block static contracts and artifact validation.

This Stage B module is intentionally limited to constants and a read-only
artifact validator. It does not launch subprocesses or run experiments.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from replication_config import (
    BLOCK_FAILURE_POLICY,
    CACHE_SCOPE,
    CONDITION_COUNT,
    CONTROL_EXP_ID,
    EXECUTION_MODE,
    EXECUTION_ORDER,
    LEDGER_FIELDS,
    LATEST_POLICY,
    MATRIX_VERSION,
    MAX_PARALLEL_BLOCKS,
    METRICS_SCHEMA_VERSION,
    REPLICATION_SCHEMA_VERSION,
)


BLOCK_STATES = (
    "planned",
    "running",
    "succeeded",
    "failed",
    "invalid",
    "interrupted",
)

ALLOWED_TRANSITIONS = frozenset(
    {
        ("planned", "running"),
        ("running", "succeeded"),
        ("running", "failed"),
        ("running", "invalid"),
        ("running", "interrupted"),
        ("failed", "running"),
        ("invalid", "running"),
        ("interrupted", "running"),
    }
)

MANIFEST_FIELDS = (
    "replication_id",
    "replicate_id",
    "replicate_index",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "python_hash_seed",
    "status",
    "attempt_count",
    "block_dir",
    "started_at",
    "finished_at",
    "subprocess_exit_code",
    "condition_success_count",
    "condition_error_count",
    "postprocess_error_count",
    "replay_alignment_violated",
    "network_status",
    "validation_passed",
    "failure_stage",
    "failure_type",
    "failure_message",
)

REPLICATION_METADATA_FIELDS = (
    "schema_version",
    "replication_id",
    "replicate_id",
    "replicate_index",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "python_hash_seed",
    "cache_scope",
    "execution_mode",
    "latest_policy",
    "engineering_acceptance_only",
)

SUBPROCESS_ENV_CONTRACT = (
    "PYTHONUTF8=1",
    "PYTHONIOENCODING=utf-8",
    "PYTHONHASHSEED=<ledger python_hash_seed>",
    "MPLBACKEND=Agg",
    "TOKENIZERS_PARALLELISM=false",
)

DETERMINISTIC_MOCK_ENV_CONTRACT = (
    "HF_HUB_OFFLINE=1",
    "TRANSFORMERS_OFFLINE=1",
    "HF_DATASETS_OFFLINE=1",
    "HF_HUB_DISABLE_TELEMETRY=1",
)

RUN_EXPERIMENTS_ARGS = (
    "--replication-id",
    "--replicate-id",
    "--replicate-index",
    "--simulation-seed",
    "--requested-llm-seed",
    "--llm-seed-supported",
    "--python-hash-seed",
    "--output-dir",
    "--no-latest",
    "--llm-mode",
)

LLM_MODES = ("real", "deterministic-mock")

V4_FIELDS = (
    "final_trust_gain_vs_control",
    "post_scandal_auc_gain_vs_control",
    "local_trust_effect_did_3",
    "early_trust_auc_gain_5",
    "early_trust_gain_slope_5",
    "secondary_harm_depth",
    "negative_gain_tick_count",
)

SUMMARY_REQUIRED_FIELDS = (
    "exp_id",
    "content_factor",
    "channel_factor",
    "timing_factor",
    "is_control",
    "trust_gain_vs_control",
    *V4_FIELDS,
)

RANKING_SENSITIVITY_FIELDS = (
    "weight_final",
    "weight_auc",
    "weight_local",
    "exp_id",
    "weighted_score",
    "rank",
    "top1_credit",
)

RANKING_ROBUSTNESS_FIELDS = (
    "exp_id",
    "top1_share",
    "mean_rank",
    "median_rank",
    "best_rank",
    "worst_rank",
)

FIGURE_FILES = (
    "fig1_main_effects.png",
    "fig2_interactions.png",
    "fig3_pareto.png",
    "fig4_ranking.png",
    "fig5_clarification_diagnosis.png",
    "fig6_ranking_sensitivity.png",
)


def validate_block_artifacts(
    block_dir,
    ledger_row,
    *,
    subprocess_exit_code: int,
) -> dict:
    """Validate one completed replicate block without mutating inputs."""
    if not isinstance(ledger_row, Mapping):
        raise ValueError("ledger_row must be a mapping")
    if not isinstance(subprocess_exit_code, int) or isinstance(
        subprocess_exit_code, bool
    ):
        raise ValueError("subprocess_exit_code must be an integer")
    missing = [field for field in LEDGER_FIELDS if field not in ledger_row]
    if missing:
        raise ValueError("ledger_row missing required fields")

    ledger = dict(ledger_row)
    block_path = Path(block_dir)
    if subprocess_exit_code != 0:
        return _failed_exit_code(subprocess_exit_code)
    if not block_path.is_dir():
        return _invalid(
            "block-directory",
            "BlockDirectoryMissing",
            "block directory is missing",
        )

    forbidden = _validate_forbidden_artifacts(block_path)
    if forbidden is not None:
        return forbidden

    metadata_result, metadata = _load_json_object(
        block_path / "run_metadata.json",
        "run-metadata",
        "RunMetadata",
    )
    if metadata_result is not None:
        return metadata_result

    result = _validate_run_metadata(metadata, ledger)
    if result is not None:
        return result
    result, strategy_ids = _validate_summary(block_path / "summary.csv")
    if result is not None:
        return result
    result = _validate_ranking_sensitivity(
        block_path / "ranking_sensitivity.csv",
        strategy_ids,
    )
    if result is not None:
        return result
    result = _validate_ranking_robustness(
        block_path / "ranking_robustness.csv",
        strategy_ids,
    )
    if result is not None:
        return result
    result = _validate_figures(block_path)
    if result is not None:
        return result

    return {
        "validation_passed": True,
        "status": "succeeded",
        "condition_success_count": 9,
        "condition_error_count": 0,
        "postprocess_error_count": 0,
        "replay_alignment_violated": False,
        "network_status": "consistent",
        "failure_stage": "",
        "failure_type": "",
        "failure_message": "",
    }


def _base_result(
    *,
    validation_passed: bool,
    status: str,
    failure_stage: str,
    failure_type: str,
    failure_message: str,
    condition_success_count: int = 0,
    condition_error_count: int = 0,
    postprocess_error_count: int = 0,
    replay_alignment_violated: bool = False,
    network_status: str = "",
) -> dict:
    return {
        "validation_passed": validation_passed,
        "status": status,
        "condition_success_count": condition_success_count,
        "condition_error_count": condition_error_count,
        "postprocess_error_count": postprocess_error_count,
        "replay_alignment_violated": replay_alignment_violated,
        "network_status": network_status,
        "failure_stage": failure_stage,
        "failure_type": failure_type,
        "failure_message": _sanitize_failure_message(failure_message),
    }


def _failed_exit_code(exit_code: int) -> dict:
    return _base_result(
        validation_passed=False,
        status="failed",
        failure_stage="subprocess",
        failure_type="SubprocessExitCode",
        failure_message=f"subprocess exited with code {exit_code}",
    )


def _invalid(stage: str, failure_type: str, message: str) -> dict:
    return _base_result(
        validation_passed=False,
        status="invalid",
        failure_stage=stage,
        failure_type=failure_type,
        failure_message=message,
    )


def _sanitize_failure_message(message: str) -> str:
    text = str(message)
    patterns = (
        r"sk-[A-Za-z0-9_-]+",
        r"Bearer\s+[A-Za-z0-9._-]+",
        r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*[^,\s;]+",
    )
    for pattern in patterns:
        text = re.sub(pattern, r"\1=<redacted>" if "(" in pattern else "<redacted>", text)
    return text[:240]


def _load_json_object(
    path: Path,
    stage: str,
    failure_prefix: str,
) -> tuple[dict | None, dict[str, Any]]:
    if not path.is_file():
        return (
            _invalid(stage, f"{failure_prefix}Missing", f"{path.name} is missing"),
            {},
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return (
            _invalid(stage, f"{failure_prefix}InvalidJson", f"{path.name} is invalid JSON"),
            {},
        )
    if not isinstance(data, dict):
        return (
            _invalid(stage, f"{failure_prefix}NotObject", f"{path.name} must be a JSON object"),
            {},
        )
    return None, data


def _validate_run_metadata(metadata: Mapping[str, Any], ledger: Mapping[str, Any]) -> dict | None:
    if metadata.get("batch_exit_code") != 0:
        return _invalid("run-metadata", "BatchExitCode", "batch_exit_code must be 0")
    if metadata.get("run_completed") is not True:
        return _invalid("run-metadata", "RunIncomplete", "run_completed must be true")

    matrix = metadata.get("experiment_matrix")
    if not isinstance(matrix, Mapping):
        return _invalid("experiment-matrix", "ExperimentMatrixMissing", "experiment_matrix must be an object")
    if matrix.get("matrix_version") != MATRIX_VERSION:
        return _invalid("experiment-matrix", "MatrixVersionMismatch", "matrix_version must be 3.0")
    if matrix.get("condition_count") != CONDITION_COUNT:
        return _invalid("experiment-matrix", "ConditionCountMismatch", "condition_count must be 9")
    if matrix.get("control_exp_id") != CONTROL_EXP_ID:
        return _invalid("experiment-matrix", "ControlExpIdMismatch", "control exp_id mismatch")
    if matrix.get("replay_alignment_violated") is not False:
        return _invalid("experiment-matrix", "ReplayAlignmentViolation", "replay alignment must be false")

    metrics = metadata.get("metrics")
    if not isinstance(metrics, Mapping):
        return _invalid("metrics", "MetricsMissing", "metrics must be an object")
    if metrics.get("schema_version") != METRICS_SCHEMA_VERSION:
        return _invalid("metrics", "MetricsSchemaMismatch", "metrics schema_version must be 4.0")

    network = metadata.get("network_consistency")
    if not isinstance(network, Mapping):
        return _invalid("network", "NetworkConsistencyMissing", "network_consistency must be an object")
    if network.get("status") != "consistent":
        return _invalid("network", "NetworkInconsistent", "network status must be consistent")

    replication = metadata.get("replication")
    if not isinstance(replication, Mapping):
        return _invalid("replication-metadata", "ReplicationMetadataMissing", "replication must be an object")
    if not set(REPLICATION_METADATA_FIELDS) <= set(replication):
        return _invalid("replication-metadata", "ReplicationMetadataFields", "replication metadata fields missing")

    replicate_index = replication.get("replicate_index")
    if not isinstance(replicate_index, int) or isinstance(replicate_index, bool):
        return _invalid(
            "replication-metadata",
            "ReplicateIndexInvalid",
            "replicate_index must be a non-boolean integer",
        )

    engineering_flag = replication.get("engineering_acceptance_only")
    if not isinstance(engineering_flag, bool):
        return _invalid(
            "replication-metadata",
            "EngineeringAcceptanceFlag",
            "engineering_acceptance_only must be boolean",
        )

    expected_pairs = {
        "schema_version": REPLICATION_SCHEMA_VERSION,
        "replicate_id": ledger["replicate_id"],
        "replicate_index": ledger["replicate_index"],
        "simulation_seed": ledger["simulation_seed"],
        "requested_llm_seed": ledger["requested_llm_seed"],
        "llm_seed_supported": ledger["llm_seed_supported"],
        "python_hash_seed": ledger["python_hash_seed"],
        "cache_scope": CACHE_SCOPE,
        "execution_mode": EXECUTION_MODE,
        "latest_policy": LATEST_POLICY,
    }
    if not isinstance(replication.get("replication_id"), str) or not replication.get("replication_id"):
        return _invalid("replication-metadata", "ReplicationIdInvalid", "replication_id must be non-empty")
    for key, expected in expected_pairs.items():
        if replication.get(key) != expected:
            return _invalid("replication-metadata", "ReplicationMetadataMismatch", f"replication {key} mismatch")
    if replication.get("cache_scope") != ledger["cache_scope"]:
        return _invalid("replication-metadata", "ReplicationCacheScopeMismatch", "cache_scope must match ledger")
    return None


def _validate_summary(path: Path) -> tuple[dict | None, set[str]]:
    rows_result, rows = _read_csv_rows(path, "summary", "summary.csv")
    if rows_result is not None:
        return rows_result, set()
    header = set(rows[0].keys()) if rows else set()
    if not set(SUMMARY_REQUIRED_FIELDS) <= header:
        return _invalid("summary", "SummaryFieldsMissing", "summary required fields missing"), set()
    if len(rows) != CONDITION_COUNT:
        return _invalid("summary", "SummaryRowCount", "summary must contain 9 rows"), set()

    exp_ids = [row.get("exp_id", "") for row in rows]
    if any(not exp_id for exp_id in exp_ids) or len(set(exp_ids)) != len(exp_ids):
        return _invalid("summary", "SummaryExpIdInvalid", "summary exp_id values must be unique"), set()
    if set(exp_ids) != set(EXECUTION_ORDER):
        return _invalid("summary", "SummaryExecutionOrderMismatch", "summary exp_id set mismatch"), set()

    control_rows = []
    strategy_rows = []
    combos = set()
    for row in rows:
        is_control = _parse_bool(row.get("is_control"))
        if is_control is None:
            return _invalid("summary", "SummaryControlFlagInvalid", "is_control must be explicit boolean"), set()
        if is_control:
            control_rows.append(row)
        else:
            strategy_rows.append(row)
            combo = (
                row.get("content_factor"),
                row.get("channel_factor"),
                row.get("timing_factor"),
            )
            combos.add(combo)

        trust_gain = _parse_finite(row.get("trust_gain_vs_control"))
        final_gain = _parse_finite(row.get("final_trust_gain_vs_control"))
        auc_gain = _parse_finite(row.get("post_scandal_auc_gain_vs_control"))
        if trust_gain is None or final_gain is None or auc_gain is None:
            return _invalid("summary", "SummaryNumericInvalid", "global summary metrics must be finite"), set()
        if abs(trust_gain - final_gain) > 1e-12:
            return _invalid("summary", "SummaryAliasMismatch", "trust gain aliases must match"), set()

        if is_control:
            if abs(trust_gain) > 1e-12 or abs(final_gain) > 1e-12 or abs(auc_gain) > 1e-12:
                return _invalid("summary", "SummaryControlGlobalMetrics", "control global metrics must be 0"), set()
            for field in V4_FIELDS[2:]:
                if not _is_empty(row.get(field)):
                    return _invalid("summary", "SummaryControlTimeMetrics", "control time metrics must be empty"), set()
        else:
            for field in V4_FIELDS:
                if _parse_finite(row.get(field)) is None:
                    return _invalid("summary", "SummaryStrategyMetricInvalid", "strategy v4 metrics must be finite"), set()

    if len(control_rows) != 1 or control_rows[0].get("exp_id") != CONTROL_EXP_ID:
        return _invalid("summary", "SummaryControlCount", "summary must contain one control row"), set()
    control = control_rows[0]
    if (
        control.get("content_factor") != "not-applicable"
        or control.get("channel_factor") != "not-applicable"
        or control.get("timing_factor") != "no-clarification"
    ):
        return _invalid("summary", "SummaryControlFactors", "control factors mismatch"), set()
    expected_combos = {
        (content, channel, timing)
        for content in ("rational-evidence", "emotional-empathy")
        for channel in ("hub", "random")
        for timing in ("immediate", "delayed")
    }
    if combos != expected_combos or len(strategy_rows) != 8:
        return _invalid("summary", "SummaryStrategyFactorMatrix", "strategies must form full 2x2x2 matrix"), set()
    return None, {row["exp_id"] for row in strategy_rows}


def _read_csv_rows(path: Path, stage: str, name: str) -> tuple[dict | None, list[dict[str, str]]]:
    if not path.is_file():
        return _invalid(stage, f"{stage.title().replace('-', '')}Missing", f"{name} is missing"), []
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception:
        return _invalid(stage, f"{stage.title().replace('-', '')}InvalidCsv", f"{name} is invalid CSV"), []
    if reader.fieldnames is None:
        return _invalid(stage, f"{stage.title().replace('-', '')}HeaderMissing", f"{name} header is missing"), []
    if any(None in row for row in rows):
        return _invalid(stage, f"{stage.title().replace('-', '')}ExtraColumns", f"{name} contains extra columns"), []
    return None, rows


def _validate_ranking_sensitivity(path: Path, strategy_ids: set[str]) -> dict | None:
    result, rows = _read_csv_rows(path, "ranking-sensitivity", "ranking_sensitivity.csv")
    if result is not None:
        return result
    header = tuple(rows[0].keys()) if rows else tuple()
    if header != RANKING_SENSITIVITY_FIELDS:
        return _invalid("ranking-sensitivity", "RankingSensitivityHeader", "ranking_sensitivity header mismatch")
    if len(rows) != 528:
        return _invalid("ranking-sensitivity", "RankingSensitivityRowCount", "ranking_sensitivity must contain 528 rows")

    groups: dict[tuple[float, float, float], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("exp_id") not in strategy_ids:
            return _invalid("ranking-sensitivity", "RankingSensitivityExpId", "ranking_sensitivity exp_id mismatch")
        numbers = {
            field: _parse_finite(row.get(field))
            for field in (
                "weight_final",
                "weight_auc",
                "weight_local",
                "weighted_score",
                "rank",
                "top1_credit",
            )
        }
        if any(value is None for value in numbers.values()):
            return _invalid("ranking-sensitivity", "RankingSensitivityNumeric", "ranking_sensitivity values must be finite")
        weights = (
            numbers["weight_final"],
            numbers["weight_auc"],
            numbers["weight_local"],
        )
        if abs(sum(weights) - 1.0) > 1e-12:
            return _invalid("ranking-sensitivity", "RankingSensitivityWeights", "weights must sum to 1")
        groups[weights].append(row)

    if len(groups) != 66:
        return _invalid("ranking-sensitivity", "RankingSensitivityWeightCount", "ranking_sensitivity must contain 66 weight groups")
    for group_rows in groups.values():
        ids = {row["exp_id"] for row in group_rows}
        if ids != strategy_ids or len(group_rows) != 8:
            return _invalid("ranking-sensitivity", "RankingSensitivityGroup", "each weight group must contain 8 strategies")
        top1_sum = sum(_parse_finite(row.get("top1_credit")) or 0.0 for row in group_rows)
        if abs(top1_sum - 1.0) > 1e-12:
            return _invalid("ranking-sensitivity", "RankingSensitivityTop1Credit", "top1_credit must sum to 1")
    return None


def _validate_ranking_robustness(path: Path, strategy_ids: set[str]) -> dict | None:
    result, rows = _read_csv_rows(path, "ranking-robustness", "ranking_robustness.csv")
    if result is not None:
        return result
    header = tuple(rows[0].keys()) if rows else tuple()
    if header != RANKING_ROBUSTNESS_FIELDS:
        return _invalid("ranking-robustness", "RankingRobustnessHeader", "ranking_robustness header mismatch")
    if len(rows) != 8:
        return _invalid("ranking-robustness", "RankingRobustnessRowCount", "ranking_robustness must contain 8 rows")
    ids = [row.get("exp_id") for row in rows]
    if set(ids) != strategy_ids or len(set(ids)) != 8:
        return _invalid("ranking-robustness", "RankingRobustnessExpId", "ranking_robustness exp_id mismatch")
    for row in rows:
        for field in RANKING_ROBUSTNESS_FIELDS[1:]:
            if _parse_finite(row.get(field)) is None:
                return _invalid("ranking-robustness", "RankingRobustnessNumeric", "ranking_robustness values must be finite")
    return None


def _validate_figures(block_path: Path) -> dict | None:
    figures_dir = block_path / "figures"
    for name in FIGURE_FILES:
        path = figures_dir / name
        if not path.is_file() or path.stat().st_size <= 0:
            return _invalid("figures", "FigureMissing", f"{name} is missing or empty")
    return None


def _validate_forbidden_artifacts(block_path: Path) -> dict | None:
    if (block_path / "errors.log").exists():
        return _invalid("forbidden-artifacts", "ErrorsLogPresent", "errors.log must not exist")
    if (block_path / "network_inconsistency_report.json").exists():
        return _invalid(
            "forbidden-artifacts",
            "NetworkInconsistencyReportPresent",
            "network inconsistency report must not exist",
        )
    return None


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if value in (0, 1):
            return bool(value)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized in ("True", "true", "1"):
            return True
        if normalized in ("False", "false", "0"):
            return False
    return None


def _parse_finite(value: Any) -> float | None:
    if isinstance(value, bool) or _is_empty(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")
