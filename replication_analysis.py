"""Deterministic block-level replication analysis for TASK_005.

The module is intentionally offline.  It treats a complete replication block
as the sole independent statistical unit and validates every block before
analysis.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import scipy as _scipy
    from scipy.stats import t as _student_t
except ImportError as exc:  # fail closed: exact frozen tests require Student-t
    raise ImportError("replication_analysis requires scipy") from exc


ANALYSIS_SCHEMA_VERSION = "1.1"
CONFIRMATORY_PRIMARY_METRICS = (
    "final_trust_gain_vs_control",
    "post_scandal_auc_gain_vs_control",
)
EXPLORATORY_MECHANISM_METRICS = (
    "local_trust_effect_did_3",
)
ALL_ANALYSIS_METRICS = (
    *CONFIRMATORY_PRIMARY_METRICS,
    *EXPLORATORY_MECHANISM_METRICS,
)
PRIMARY_METRICS = CONFIRMATORY_PRIMARY_METRICS
CONTROL_EXP_ID = "NoClarification-Control"
STRATEGY_EXP_IDS = (
    "Empathy-Hub-Delayed",
    "Empathy-Hub-Immediate",
    "Empathy-Random-Delayed",
    "Empathy-Random-Immediate",
    "Rational-Hub-Delayed",
    "Rational-Hub-Immediate",
    "Rational-Random-Delayed",
    "Rational-Random-Immediate",
)
FACTORIAL_CONTRASTS = (
    "Content",
    "Channel",
    "Timing",
    "Content_x_Channel",
    "Content_x_Timing",
    "Channel_x_Timing",
    "Content_x_Channel_x_Timing",
)
CONFIRMATORY_CONTRASTS = FACTORIAL_CONTRASTS[:6]
DEFAULT_BOOTSTRAP_ITERATIONS = 20000
PARETO_TOLERANCE = 1e-12
FORMAL_TARGET_VALID_BLOCKS = 24
ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL = (
    "P001",
    "P002",
    "P003",
    "P004",
    "P005",
)

_OUTPUT_FILES = (
    "replicate_runs.csv",
    "paired_effects.csv",
    "factorial_contrasts.csv",
    "strategy_estimates.csv",
    "factorial_estimates.csv",
    "formal_pareto.csv",
    "ranking_bootstrap.csv",
    "analysis_metadata.json",
    "analysis_validation.json",
)


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _require_sequence(value: Any, name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a non-string sequence")
    return value


def _bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no", ""}:
        return False
    raise ValueError(f"{name} is not boolean: {value!r}")


def _int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer: {value!r}") from exc
    return result


def _finite_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite: {value!r}")
    return result


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return [dict(row) for row in reader]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_json_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _git_head(start: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=start,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot compute a quantile of an empty sequence")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _normalise_preregistration(preregistration: Mapping[str, Any]) -> dict[str, Any]:
    config = dict(_require_mapping(preregistration, "preregistration"))
    schema = str(config.get("analysis_schema_version", "")).strip()
    if schema != ANALYSIS_SCHEMA_VERSION:
        raise ValueError(
            f"analysis_schema_version must be {ANALYSIS_SCHEMA_VERSION}"
        )

    formal_id = str(config.get("formal_replication_id", "")).strip()
    if not formal_id:
        raise ValueError("formal_replication_id is required")

    target = _int(config.get("target_valid_blocks"), "target_valid_blocks")
    maximum = _int(config.get("max_attempted_blocks"), "max_attempted_blocks")
    if target != FORMAL_TARGET_VALID_BLOCKS:
        raise ValueError(
            f"target_valid_blocks must be exactly {FORMAL_TARGET_VALID_BLOCKS}"
        )
    if maximum < target:
        raise ValueError("invalid target/max block counts")

    metrics = tuple(config.get("primary_metrics", ()))
    if metrics != CONFIRMATORY_PRIMARY_METRICS:
        raise ValueError("primary_metrics do not match the frozen contract")
    exploratory_metrics = tuple(config.get("exploratory_metrics", ()))
    if exploratory_metrics != EXPLORATORY_MECHANISM_METRICS:
        raise ValueError("exploratory_metrics do not match the frozen contract")

    control = str(config.get("control_exp_id", "")).strip()
    if control != CONTROL_EXP_ID:
        raise ValueError("control_exp_id does not match the frozen contract")

    strategies = tuple(config.get("strategy_exp_ids", ()))
    if strategies != STRATEGY_EXP_IDS:
        raise ValueError("strategy_exp_ids do not match the frozen contract")

    alpha = _finite_float(config.get("alpha"), "alpha")
    ci_level = _finite_float(config.get("ci_level"), "ci_level")
    if not 0.0 < alpha < 1.0 or not 0.0 < ci_level < 1.0:
        raise ValueError("alpha and ci_level must be in (0, 1)")

    iterations = _int(
        config.get("bootstrap_iterations", DEFAULT_BOOTSTRAP_ITERATIONS),
        "bootstrap_iterations",
    )
    if iterations < 1:
        raise ValueError("bootstrap_iterations must be positive")

    seed = _int(config.get("bootstrap_seed", 0), "bootstrap_seed")
    excluded = tuple(str(item) for item in config.get("excluded_replication_ids", ()))

    config.update(
        {
            "formal_replication_id": formal_id,
            "target_valid_blocks": target,
            "max_attempted_blocks": maximum,
            "primary_metrics": list(CONFIRMATORY_PRIMARY_METRICS),
            "exploratory_metrics": list(EXPLORATORY_MECHANISM_METRICS),
            "all_analysis_metrics": list(ALL_ANALYSIS_METRICS),
            "control_exp_id": CONTROL_EXP_ID,
            "strategy_exp_ids": list(STRATEGY_EXP_IDS),
            "alpha": alpha,
            "ci_level": ci_level,
            "bootstrap_iterations": iterations,
            "bootstrap_seed": seed,
            "excluded_replication_ids": list(excluded),
        }
    )
    return config


def _validate_condition_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    replicate_id: str,
) -> list[dict[str, Any]]:
    if len(rows) != 9:
        raise ValueError(f"{replicate_id}: expected 9 condition rows")

    copied = [dict(_require_mapping(row, "condition row")) for row in rows]
    ids = [str(row.get("exp_id", "")).strip() for row in copied]
    if any(not item for item in ids):
        raise ValueError(f"{replicate_id}: blank exp_id")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{replicate_id}: duplicate exp_id")

    expected = {CONTROL_EXP_ID, *STRATEGY_EXP_IDS}
    if set(ids) != expected:
        raise ValueError(f"{replicate_id}: condition set mismatch")

    controls = [
        row
        for row in copied
        if _bool(row.get("is_control", False), "is_control")
    ]
    if len(controls) != 1:
        raise ValueError(f"{replicate_id}: expected exactly one control")
    if str(controls[0].get("exp_id", "")).strip() != CONTROL_EXP_ID:
        raise ValueError(f"{replicate_id}: control identity mismatch")

    by_id = {str(row["exp_id"]).strip(): row for row in copied}
    control = by_id[CONTROL_EXP_ID]
    for metric in CONFIRMATORY_PRIMARY_METRICS:
        control[metric] = _finite_float(
            control.get(metric), f"{replicate_id}/{CONTROL_EXP_ID}/{metric}"
        )
    local_metric = EXPLORATORY_MECHANISM_METRICS[0]
    if not _is_blank(control.get(local_metric)):
        raise ValueError(
            f"{replicate_id}: control local DID must be structurally blank"
        )
    control[local_metric] = None
    control["is_control"] = True

    for exp_id in STRATEGY_EXP_IDS:
        row = by_id[exp_id]
        if _bool(row.get("is_control", False), "is_control"):
            raise ValueError(f"{replicate_id}/{exp_id}: strategy marked control")
        row["is_control"] = False
        for metric in ALL_ANALYSIS_METRICS:
            row[metric] = _finite_float(
                row.get(metric), f"{replicate_id}/{exp_id}/{metric}"
            )

        content, channel, timing = exp_id.split("-")
        supplied = (
            str(row.get("content", content)).strip(),
            str(row.get("channel", channel)).strip(),
            str(row.get("timing", timing)).strip(),
        )
        if supplied != (content, channel, timing):
            raise ValueError(f"{replicate_id}/{exp_id}: factor labels mismatch")
        row["content"] = content
        row["channel"] = channel
        row["timing"] = timing

    ordered = [by_id[CONTROL_EXP_ID]]
    ordered.extend(by_id[exp_id] for exp_id in STRATEGY_EXP_IDS)
    return ordered


def load_valid_replication_blocks(
    batch_root: str | os.PathLike[str],
    preregistration: Mapping[str, Any],
) -> dict[str, Any]:
    """Load final successful blocks and reject any incomplete block as a unit."""

    root = Path(batch_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    config = _normalise_preregistration(preregistration)

    metadata = _read_json(root / "replication_metadata.json")
    batch_id = str(metadata.get("replication_id", "")).strip()
    if not batch_id:
        raise ValueError("replication metadata lacks replication_id")
    if batch_id in set(ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL):
        raise ValueError(f"forbidden engineering batch: {batch_id}")
    if batch_id in set(config["excluded_replication_ids"]):
        raise ValueError(f"excluded engineering batch: {batch_id}")
    if batch_id != config["formal_replication_id"]:
        raise ValueError(
            "batch replication_id does not match formal preregistration"
        )

    manifest_rows = _read_csv(root / "replicate_manifest.csv")
    if not manifest_rows:
        raise ValueError("replicate manifest is empty")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in manifest_rows:
        rid = str(row.get("replicate_id", "")).strip()
        if not rid:
            raise ValueError("manifest row lacks replicate_id")
        grouped[rid].append(row)

    final_manifest_rows: list[dict[str, str]] = []
    for rid, rows in grouped.items():
        # A manifest may retain several attempts.  Prefer the largest
        # attempt_count, then the largest replicate_index, without using
        # effect values.
        rows_sorted = sorted(
            rows,
            key=lambda row: (
                _int(row.get("attempt_count", 0), "attempt_count"),
                _int(row.get("replicate_index", 0), "replicate_index"),
            ),
        )
        final_manifest_rows.append(rows_sorted[-1])

    final_manifest_rows.sort(
        key=lambda row: (
            _int(row.get("replicate_index"), "replicate_index"),
            str(row.get("replicate_id", "")),
        )
    )

    valid_blocks: list[dict[str, Any]] = []
    excluded_blocks: list[dict[str, Any]] = []

    for manifest in final_manifest_rows:
        rid = str(manifest["replicate_id"]).strip()
        reasons: list[str] = []
        try:
            if rid in set(ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL):
                raise ValueError(
                    f"forbidden engineering replicate_id: {rid}"
                )
            if str(manifest.get("replication_id", "")).strip() != batch_id:
                raise ValueError("manifest replication_id mismatch")
            if str(manifest.get("status", "")).strip() != "succeeded":
                raise ValueError("final manifest status is not succeeded")
            if _int(
                manifest.get("subprocess_exit_code"),
                "subprocess_exit_code",
            ) != 0:
                raise ValueError("nonzero subprocess exit")
            if _int(
                manifest.get("condition_success_count"),
                "condition_success_count",
            ) != 9:
                raise ValueError("condition_success_count is not 9")
            if _int(
                manifest.get("condition_error_count"),
                "condition_error_count",
            ) != 0:
                raise ValueError("condition errors present")
            if _int(
                manifest.get("postprocess_error_count"),
                "postprocess_error_count",
            ) != 0:
                raise ValueError("postprocess errors present")
            if _bool(
                manifest.get("replay_alignment_violated"),
                "replay_alignment_violated",
            ):
                raise ValueError("replay alignment violated")
            if str(manifest.get("network_status", "")).strip() != "consistent":
                raise ValueError("network status is not consistent")
            if not _bool(
                manifest.get("validation_passed"),
                "validation_passed",
            ):
                raise ValueError("validation did not pass")

            block_dir_value = str(manifest.get("block_dir", "")).strip()
            block_dir = (root / block_dir_value).resolve()
            try:
                block_dir.relative_to(root)
            except ValueError as exc:
                raise ValueError("block_dir escapes batch root") from exc
            if not block_dir.is_dir():
                raise FileNotFoundError(block_dir)

            block_metadata = _read_json(block_dir / "run_metadata.json")
            replication = _require_mapping(
                block_metadata.get("replication", {}),
                "run metadata replication",
            )
            if str(replication.get("replication_id", "")).strip() != batch_id:
                raise ValueError("run metadata replication_id mismatch")
            metadata_rid = str(replication.get("replicate_id", "")).strip()
            if metadata_rid in set(ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL):
                raise ValueError(
                    f"forbidden engineering run metadata replicate_id: "
                    f"{metadata_rid}"
                )
            if metadata_rid != rid:
                raise ValueError("run metadata replicate_id mismatch")
            replicate_index = _int(
                replication.get("replicate_index"), "replicate_index"
            )
            if replicate_index != _int(
                manifest.get("replicate_index"), "manifest replicate_index"
            ):
                raise ValueError("replicate_index mismatch")
            if _int(
                block_metadata.get("batch_exit_code"), "batch_exit_code"
            ) != 0:
                raise ValueError("run metadata batch exit is nonzero")
            if not _bool(
                block_metadata.get("run_completed"), "run_completed"
            ):
                raise ValueError("run not completed")
            if _bool(
                block_metadata.get("replay_alignment_violated"),
                "replay_alignment_violated",
            ):
                raise ValueError("run metadata replay alignment violated")
            network = _require_mapping(
                block_metadata.get("network", {}), "network"
            )
            if str(network.get("status", "")).strip() != "consistent":
                raise ValueError("run metadata network is not consistent")

            conditions = _validate_condition_rows(
                _read_csv(block_dir / "summary.csv"),
                replicate_id=rid,
            )
            valid_blocks.append(
                {
                    "formal_replication_id": batch_id,
                    "replicate_id": rid,
                    "replicate_index": replicate_index,
                    "attempt_index": _int(
                        replication.get(
                            "attempt_index",
                            manifest.get("attempt_count", 1),
                        ),
                        "attempt_index",
                    ),
                    "block_dir": str(block_dir),
                    "summary_path": str(block_dir / "summary.csv"),
                    "metadata_path": str(block_dir / "run_metadata.json"),
                    "manifest": dict(manifest),
                    "metadata": block_metadata,
                    "conditions": conditions,
                }
            )
        except (FileNotFoundError, TypeError, ValueError, KeyError) as exc:
            reasons.append(f"{type(exc).__name__}: {exc}")
            excluded_blocks.append(
                {
                    "formal_replication_id": batch_id,
                    "replicate_id": rid,
                    "replicate_index": manifest.get("replicate_index", ""),
                    "reason": " | ".join(reasons),
                }
            )

    valid_blocks.sort(
        key=lambda row: (int(row["replicate_index"]), row["replicate_id"])
    )
    excluded_blocks.sort(
        key=lambda row: (
            int(row["replicate_index"])
            if str(row.get("replicate_index", "")).isdigit()
            else 10**18,
            str(row["replicate_id"]),
        )
    )

    counts = {
        "manifest_rows": len(manifest_rows),
        "attempted": len(final_manifest_rows),
        "valid": len(valid_blocks),
        "excluded": len(excluded_blocks),
        "failed": sum(
            str(row.get("status", "")).strip() == "failed"
            for row in final_manifest_rows
        ),
        "interrupted": sum(
            str(row.get("status", "")).strip() == "interrupted"
            for row in final_manifest_rows
        ),
    }
    if counts["valid"] < config["target_valid_blocks"]:
        formal_sample_status = "incomplete"
    elif counts["valid"] == config["target_valid_blocks"]:
        formal_sample_status = "exact_complete"
    else:
        formal_sample_status = "overcomplete"
    surplus_valid_blocks = max(0, counts["valid"] - config["target_valid_blocks"])
    formal_complete = counts["valid"] == config["target_valid_blocks"]
    return {
        "formal_replication_id": batch_id,
        "preregistration": config,
        "valid_blocks": valid_blocks,
        "excluded_blocks": excluded_blocks,
        "counts": counts,
        "formal_sample_status": formal_sample_status,
        "surplus_valid_blocks": surplus_valid_blocks,
        "formal_complete": formal_complete,
        "formal_inference_permitted": formal_complete,
    }


def build_replicate_runs(
    valid_blocks: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    blocks = _require_sequence(valid_blocks, "valid_blocks")
    output: list[dict[str, Any]] = []
    seen_blocks: set[str] = set()
    for block_value in blocks:
        block = dict(_require_mapping(block_value, "valid block"))
        rid = str(block.get("replicate_id", "")).strip()
        if not rid or rid in seen_blocks:
            raise ValueError("replicate IDs must be nonblank and unique")
        seen_blocks.add(rid)
        index = _int(block.get("replicate_index"), "replicate_index")
        conditions = _validate_condition_rows(
            _require_sequence(block.get("conditions", ()), "conditions"),
            replicate_id=rid,
        )
        for row in conditions:
            output_row = {
                "formal_replication_id": block.get(
                    "formal_replication_id", ""
                ),
                "replicate_id": rid,
                "replicate_index": index,
                "attempt_index": block.get("attempt_index", ""),
                "exp_id": row["exp_id"],
                "is_control": bool(row["is_control"]),
                "content": row.get("content", ""),
                "channel": row.get("channel", ""),
                "timing": row.get("timing", ""),
            }
            for metric in ALL_ANALYSIS_METRICS:
                output_row[metric] = row.get(metric)
            output.append(output_row)

    order = {CONTROL_EXP_ID: 0}
    order.update(
        {exp_id: position + 1 for position, exp_id in enumerate(STRATEGY_EXP_IDS)}
    )
    output.sort(
        key=lambda row: (
            int(row["replicate_index"]),
            str(row["replicate_id"]),
            order[str(row["exp_id"])],
        )
    )
    keys = [(row["replicate_id"], row["exp_id"]) for row in output]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate replicate-run key")
    return output


def build_paired_effects(
    replicate_runs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = [dict(_require_mapping(row, "replicate run")) for row in _require_sequence(replicate_runs, "replicate_runs")]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("replicate_id", "")).strip()].append(row)

    output: list[dict[str, Any]] = []
    for rid, group in grouped.items():
        if not rid:
            raise ValueError("blank replicate_id")
        validated = _validate_condition_rows(group, replicate_id=rid)
        index_values = {
            _int(row.get("replicate_index"), "replicate_index")
            for row in group
        }
        if len(index_values) != 1:
            raise ValueError(f"{rid}: inconsistent replicate_index")
        index = next(iter(index_values))
        by_id = {row["exp_id"]: row for row in validated}
        for exp_id in STRATEGY_EXP_IDS:
            row = by_id[exp_id]
            output_row = {
                "formal_replication_id": next(
                    (
                        item.get("formal_replication_id", "")
                        for item in group
                        if item.get("formal_replication_id", "") != ""
                    ),
                    "",
                ),
                "replicate_id": rid,
                "replicate_index": index,
                "exp_id": exp_id,
                "content": row["content"],
                "channel": row["channel"],
                "timing": row["timing"],
            }
            for metric in ALL_ANALYSIS_METRICS:
                output_row[metric] = _finite_float(
                    row[metric], f"{rid}/{exp_id}/{metric}"
                )
            output.append(output_row)

    output.sort(
        key=lambda row: (
            int(row["replicate_index"]),
            str(row["replicate_id"]),
            STRATEGY_EXP_IDS.index(str(row["exp_id"])),
        )
    )
    keys = [(row["replicate_id"], row["exp_id"]) for row in output]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate paired-effect key")
    return output


def _factor_signs(exp_id: str) -> dict[str, int]:
    if exp_id not in STRATEGY_EXP_IDS:
        raise ValueError(f"unknown strategy exp_id: {exp_id}")
    content, channel, timing = exp_id.split("-")
    c = 1 if content == "Empathy" else -1
    h = 1 if channel == "Hub" else -1
    t = 1 if timing == "Immediate" else -1
    return {
        "Content": c,
        "Channel": h,
        "Timing": t,
        "Content_x_Channel": c * h,
        "Content_x_Timing": c * t,
        "Channel_x_Timing": h * t,
        "Content_x_Channel_x_Timing": c * h * t,
    }


def compute_factorial_contrasts(
    paired_effects: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = [dict(_require_mapping(row, "paired effect")) for row in _require_sequence(paired_effects, "paired_effects")]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("replicate_id", "")).strip()].append(row)

    output: list[dict[str, Any]] = []
    for rid, group in grouped.items():
        if len(group) != 8:
            raise ValueError(f"{rid}: expected 8 paired strategy rows")
        by_id = {str(row.get("exp_id", "")).strip(): row for row in group}
        if set(by_id) != set(STRATEGY_EXP_IDS) or len(by_id) != len(group):
            raise ValueError(f"{rid}: incomplete or duplicate strategy set")
        indices = {
            _int(row.get("replicate_index"), "replicate_index")
            for row in group
        }
        if len(indices) != 1:
            raise ValueError(f"{rid}: inconsistent replicate_index")
        index = next(iter(indices))

        for metric in ALL_ANALYSIS_METRICS:
            values = {
                exp_id: _finite_float(
                    by_id[exp_id].get(metric), f"{rid}/{exp_id}/{metric}"
                )
                for exp_id in STRATEGY_EXP_IDS
            }
            for contrast_name in FACTORIAL_CONTRASTS:
                value = sum(
                    _factor_signs(exp_id)[contrast_name] * values[exp_id]
                    for exp_id in STRATEGY_EXP_IDS
                ) / 4.0
                output.append(
                    {
                        "replicate_id": rid,
                        "replicate_index": index,
                        "metric": metric,
                        "contrast_name": contrast_name,
                        "contrast_value": value,
                        "confirmatory": (
                            metric in CONFIRMATORY_PRIMARY_METRICS
                            and contrast_name in CONFIRMATORY_CONTRASTS
                        ),
                    }
                )

    output.sort(
        key=lambda row: (
            int(row["replicate_index"]),
            str(row["replicate_id"]),
            ALL_ANALYSIS_METRICS.index(str(row["metric"])),
            FACTORIAL_CONTRASTS.index(str(row["contrast_name"])),
        )
    )
    keys = [
        (row["replicate_id"], row["metric"], row["contrast_name"])
        for row in output
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate factorial contrast key")
    return output


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    values = list(_require_sequence(p_values, "p_values"))
    if not values:
        raise ValueError("p_values must not be empty")
    parsed = [_finite_float(value, "p_value") for value in values]
    if any(value < 0.0 or value > 1.0 for value in parsed):
        raise ValueError("p_values must lie in [0, 1]")

    order = sorted(range(len(parsed)), key=lambda index: (parsed[index], index))
    adjusted_sorted: list[float] = []
    running = 0.0
    total = len(parsed)
    for rank, index in enumerate(order):
        candidate = min(1.0, (total - rank) * parsed[index])
        running = max(running, candidate)
        adjusted_sorted.append(running)
    result = [0.0] * total
    for index, adjusted in zip(order, adjusted_sorted):
        result[index] = adjusted
    return result


def _inferential_summary(
    values: Sequence[float],
    *,
    ci_level: float,
    target_valid_blocks: int,
) -> dict[str, Any]:
    parsed = [_finite_float(value, "estimand value") for value in values]
    n = len(parsed)
    if n == 0:
        raise ValueError("estimand has no values")

    mean = statistics.fmean(parsed)
    median = statistics.median(parsed)
    q1 = _quantile(parsed, 0.25)
    q3 = _quantile(parsed, 0.75)
    result: dict[str, Any] = {
        "n_valid_blocks": n,
        "mean": mean,
        "median": median,
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "min": min(parsed),
        "max": max(parsed),
    }

    if n < 2:
        status = (
            "formal_incomplete"
            if n < target_valid_blocks
            else "formal_overcomplete"
        )
        result.update(
            {
                "sample_sd": None,
                "standard_error": None,
                "ci_level": ci_level,
                "ci_low": None,
                "ci_high": None,
                "raw_p_value": None,
                "estimand_status": status,
            }
        )
        return result

    sample_sd = statistics.stdev(parsed)
    standard_error = sample_sd / math.sqrt(n)
    alpha = 1.0 - ci_level
    critical = float(_student_t.ppf(1.0 - alpha / 2.0, n - 1))

    if sample_sd == 0.0:
        ci_low = mean
        ci_high = mean
        raw_p = 1.0 if mean == 0.0 else 0.0
        base_status = "degenerate_zero" if mean == 0.0 else "degenerate_nonzero"
    else:
        half = critical * standard_error
        ci_low = mean - half
        ci_high = mean + half
        statistic = mean / standard_error
        raw_p = float(
            2.0 * _student_t.sf(abs(statistic), n - 1)
        )
        base_status = "complete"

    if n < target_valid_blocks:
        status = "formal_incomplete"
        raw_p = None
    elif n > target_valid_blocks:
        status = "formal_overcomplete"
        raw_p = None
    else:
        status = base_status
    result.update(
        {
            "sample_sd": sample_sd,
            "standard_error": standard_error,
            "ci_level": ci_level,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "raw_p_value": raw_p,
            "estimand_status": status,
        }
    )
    return result


def aggregate_strategy_estimands(
    paired_effects: Sequence[Mapping[str, Any]],
    analysis_config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    config = _normalise_preregistration(analysis_config)
    rows = [dict(_require_mapping(row, "paired effect")) for row in _require_sequence(paired_effects, "paired_effects")]
    block_ids = sorted({str(row.get("replicate_id", "")) for row in rows})
    output: list[dict[str, Any]] = []

    for exp_id in STRATEGY_EXP_IDS:
        for metric in ALL_ANALYSIS_METRICS:
            values = [
                _finite_float(row.get(metric), f"{exp_id}/{metric}")
                for row in rows
                if str(row.get("exp_id", "")) == exp_id
            ]
            if len(values) != len(block_ids):
                raise ValueError(f"incomplete strategy estimand: {exp_id}/{metric}")
            summary = _inferential_summary(
                values,
                ci_level=config["ci_level"],
                target_valid_blocks=config["target_valid_blocks"],
            )
            if metric in CONFIRMATORY_PRIMARY_METRICS:
                analysis_tier = "confirmatory_primary"
                confirmatory = True
                reporting = True
                family = "strategy_primary_16"
            else:
                analysis_tier = "exploratory_mechanistic"
                confirmatory = False
                reporting = False
                family = None
                summary["raw_p_value"] = None
            output.append(
                {
                    "exp_id": exp_id,
                    "metric": metric,
                    "analysis_tier": analysis_tier,
                    "confirmatory": confirmatory,
                    "p_value_reporting_permitted": reporting,
                    "n_planned_blocks": config["target_valid_blocks"],
                    "n_attempted_blocks": len(block_ids),
                    "n_valid_blocks": summary["n_valid_blocks"],
                    "n_failed_blocks": max(0, len(block_ids) - summary["n_valid_blocks"]),
                    **summary,
                    "holm_p_value": None,
                    "multiplicity_family": family,
                }
            )

    confirmatory_positions = [
        index
        for index, row in enumerate(output)
        if row["multiplicity_family"] == "strategy_primary_16"
    ]
    raw = [output[index]["raw_p_value"] for index in confirmatory_positions]
    if all(value is not None for value in raw):
        adjusted = holm_adjust(raw)
        for index, value in zip(confirmatory_positions, adjusted):
            output[index]["holm_p_value"] = value
    return output


def aggregate_factorial_estimands(
    factorial_contrasts: Sequence[Mapping[str, Any]],
    analysis_config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    config = _normalise_preregistration(analysis_config)
    rows = [dict(_require_mapping(row, "factorial contrast")) for row in _require_sequence(factorial_contrasts, "factorial_contrasts")]
    block_ids = sorted({str(row.get("replicate_id", "")) for row in rows})
    output: list[dict[str, Any]] = []

    for metric in ALL_ANALYSIS_METRICS:
        for contrast_name in FACTORIAL_CONTRASTS:
            values = [
                _finite_float(row.get("contrast_value"), "contrast_value")
                for row in rows
                if str(row.get("metric", "")) == metric
                and str(row.get("contrast_name", "")) == contrast_name
            ]
            if len(values) != len(block_ids):
                raise ValueError(
                    f"incomplete factorial estimand: {metric}/{contrast_name}"
                )
            summary = _inferential_summary(
                values,
                ci_level=config["ci_level"],
                target_valid_blocks=config["target_valid_blocks"],
            )
            if metric in EXPLORATORY_MECHANISM_METRICS:
                analysis_tier = "exploratory_mechanistic"
                confirmatory = False
                reporting = False
                family = None
                summary["raw_p_value"] = None
            elif contrast_name in CONFIRMATORY_CONTRASTS:
                analysis_tier = "confirmatory_primary"
                confirmatory = True
                reporting = True
                family = "factorial_confirmatory_12"
            else:
                analysis_tier = "exploratory_secondary"
                confirmatory = False
                reporting = True
                family = "factorial_three_way_2"
            output.append(
                {
                    "metric": metric,
                    "contrast_name": contrast_name,
                    "analysis_tier": analysis_tier,
                    "confirmatory": confirmatory,
                    "p_value_reporting_permitted": reporting,
                    "n_planned_blocks": config["target_valid_blocks"],
                    "n_attempted_blocks": len(block_ids),
                    "n_valid_blocks": summary["n_valid_blocks"],
                    "n_failed_blocks": max(0, len(block_ids) - summary["n_valid_blocks"]),
                    **summary,
                    "holm_p_value": None,
                    "multiplicity_family": family,
                }
            )

    for family in ("factorial_confirmatory_12", "factorial_three_way_2"):
        positions = [
            index
            for index, row in enumerate(output)
            if row["multiplicity_family"] == family
        ]
        raw = [output[index]["raw_p_value"] for index in positions]
        if all(value is not None for value in raw):
            adjusted = holm_adjust(raw)
            for index, value in zip(positions, adjusted):
                output[index]["holm_p_value"] = value
    return output


def compute_formal_pareto(
    strategy_estimates: Sequence[Mapping[str, Any]],
    *,
    tolerance: float = PARETO_TOLERANCE,
) -> list[dict[str, Any]]:
    tol = _finite_float(tolerance, "tolerance")
    if tol < 0.0:
        raise ValueError("tolerance must be nonnegative")
    rows = [dict(_require_mapping(row, "strategy estimate")) for row in _require_sequence(strategy_estimates, "strategy_estimates")]
    values: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        exp_id = str(row.get("exp_id", "")).strip()
        metric = str(row.get("metric", "")).strip()
        if not exp_id:
            raise ValueError("invalid Pareto row identity")
        if metric in EXPLORATORY_MECHANISM_METRICS:
            continue
        if metric not in CONFIRMATORY_PRIMARY_METRICS:
            raise ValueError("invalid Pareto row identity")
        if metric in values[exp_id]:
            raise ValueError("duplicate Pareto strategy/metric key")
        values[exp_id][metric] = _finite_float(row.get("mean"), "mean")

    if not values:
        raise ValueError("no strategies for Pareto analysis")
    for exp_id, metric_values in values.items():
        if set(metric_values) != set(CONFIRMATORY_PRIMARY_METRICS):
            raise ValueError(f"{exp_id}: incomplete Pareto metric vector")

    output: list[dict[str, Any]] = []
    for exp_id in sorted(values):
        dominated_by: list[str] = []
        target = values[exp_id]
        for other_id, other in values.items():
            if other_id == exp_id:
                continue
            weakly_better = all(
                other[metric] >= target[metric] - tol
                for metric in CONFIRMATORY_PRIMARY_METRICS
            )
            strictly_better = any(
                other[metric] > target[metric] + tol
                for metric in CONFIRMATORY_PRIMARY_METRICS
            )
            if weakly_better and strictly_better:
                dominated_by.append(other_id)
        row = {
            "exp_id": exp_id,
            "is_pareto": not dominated_by,
            "dominated_by_count": len(dominated_by),
            "dominated_by": ",".join(sorted(dominated_by)),
            "pareto_tolerance": tol,
            "analysis_tier": "exploratory_secondary",
            "metric_basis": ",".join(CONFIRMATORY_PRIMARY_METRICS),
        }
        for metric in CONFIRMATORY_PRIMARY_METRICS:
            row[metric] = target[metric]
        output.append(row)
    return output


def _average_ranks(
    scores: Mapping[str, float],
    *,
    tolerance: float = 1e-15,
) -> dict[str, float]:
    ordered = sorted(scores, key=lambda item: (-scores[item], item))
    ranks: dict[str, float] = {}
    position = 0
    while position < len(ordered):
        end = position + 1
        while (
            end < len(ordered)
            and abs(scores[ordered[end]] - scores[ordered[position]])
            <= tolerance
        ):
            end += 1
        average_rank = ((position + 1) + end) / 2.0
        for index in range(position, end):
            ranks[ordered[index]] = average_rank
        position = end
    return ranks


def bootstrap_rank_stability(
    paired_effects: Sequence[Mapping[str, Any]],
    analysis_config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    config = dict(_require_mapping(analysis_config, "analysis_config"))
    iterations = _int(
        config.get("bootstrap_iterations", DEFAULT_BOOTSTRAP_ITERATIONS),
        "bootstrap_iterations",
    )
    if iterations < 1:
        raise ValueError("bootstrap_iterations must be positive")
    seed = _int(config.get("bootstrap_seed", 0), "bootstrap_seed")
    metrics = tuple(config.get("primary_metrics", CONFIRMATORY_PRIMARY_METRICS))
    if metrics != CONFIRMATORY_PRIMARY_METRICS:
        raise ValueError("bootstrap primary metric set mismatch")
    tolerance = _finite_float(
        config.get("pareto_tolerance", PARETO_TOLERANCE),
        "pareto_tolerance",
    )

    rows = [dict(_require_mapping(row, "paired effect")) for row in _require_sequence(paired_effects, "paired_effects")]
    by_block: dict[str, dict[str, tuple[float, float]]] = defaultdict(dict)
    for row in rows:
        rid = str(row.get("replicate_id", "")).strip()
        exp_id = str(row.get("exp_id", "")).strip()
        if not rid or not exp_id:
            raise ValueError("blank bootstrap identity")
        if exp_id in by_block[rid]:
            raise ValueError("duplicate bootstrap block/strategy key")
        by_block[rid][exp_id] = tuple(
            _finite_float(row.get(metric), f"{rid}/{exp_id}/{metric}")
            for metric in CONFIRMATORY_PRIMARY_METRICS
        )

    block_ids = sorted(by_block)
    if not block_ids:
        raise ValueError("bootstrap input has no blocks")
    strategies = sorted(next(iter(by_block.values())))
    if not strategies:
        raise ValueError("bootstrap input has no strategies")
    strategy_set = set(strategies)
    if any(set(block) != strategy_set for block in by_block.values()):
        raise ValueError("bootstrap requires a complete strategy vector per block")

    rng = random.Random(seed)
    pareto_counts = {exp_id: 0.0 for exp_id in strategies}
    top1_credit = {exp_id: 0.0 for exp_id in strategies}
    rank_samples = {exp_id: [] for exp_id in strategies}
    sample_size = len(block_ids)

    for _ in range(iterations):
        sampled = [rng.choice(block_ids) for _ in range(sample_size)]
        means: dict[str, dict[str, float]] = {
            exp_id: {} for exp_id in strategies
        }
        for metric_index, metric in enumerate(CONFIRMATORY_PRIMARY_METRICS):
            for exp_id in strategies:
                means[exp_id][metric] = statistics.fmean(
                    by_block[rid][exp_id][metric_index] for rid in sampled
                )

        pareto_rows = []
        for exp_id in strategies:
            for metric in CONFIRMATORY_PRIMARY_METRICS:
                pareto_rows.append(
                    {
                        "exp_id": exp_id,
                        "metric": metric,
                        "mean": means[exp_id][metric],
                    }
                )
        pareto = compute_formal_pareto(
            pareto_rows, tolerance=tolerance
        )
        for row in pareto:
            if row["is_pareto"]:
                pareto_counts[row["exp_id"]] += 1.0

        normalised = {exp_id: [] for exp_id in strategies}
        for metric in CONFIRMATORY_PRIMARY_METRICS:
            metric_values = [means[exp_id][metric] for exp_id in strategies]
            low = min(metric_values)
            high = max(metric_values)
            if high - low <= tolerance:
                for exp_id in strategies:
                    normalised[exp_id].append(0.5)
            else:
                for exp_id in strategies:
                    normalised[exp_id].append(
                        (means[exp_id][metric] - low) / (high - low)
                    )
        scores = {
            exp_id: statistics.fmean(normalised[exp_id])
            for exp_id in strategies
        }
        ranks = _average_ranks(scores)
        best = max(scores.values())
        winners = [
            exp_id
            for exp_id, score in scores.items()
            if abs(score - best) <= 1e-15
        ]
        credit = 1.0 / len(winners)
        for exp_id in winners:
            top1_credit[exp_id] += credit
        for exp_id in strategies:
            rank_samples[exp_id].append(ranks[exp_id])

    output = []
    for exp_id in strategies:
        ranks = rank_samples[exp_id]
        output.append(
            {
                "exp_id": exp_id,
                "pareto_probability": pareto_counts[exp_id] / iterations,
                "top1_probability": top1_credit[exp_id] / iterations,
                "mean_rank": statistics.fmean(ranks),
                "median_rank": statistics.median(ranks),
                "rank_interval_low": _quantile(ranks, 0.025),
                "rank_interval_high": _quantile(ranks, 0.975),
                "top1_credit_sum": top1_credit[exp_id],
                "bootstrap_iterations": iterations,
                "analysis_tier": "exploratory_secondary",
                "metric_basis": ",".join(CONFIRMATORY_PRIMARY_METRICS),
            }
        )
    return output


def plan_precision_sample_size(
    pilot_effects: Sequence[Mapping[str, Any]],
    sample_size_config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    config = dict(_require_mapping(sample_size_config, "sample_size_config"))
    ci_level = _finite_float(config.get("ci_level"), "ci_level")
    if not 0.0 < ci_level < 1.0:
        raise ValueError("ci_level must be in (0, 1)")
    n_min = _int(config.get("n_min"), "n_min")
    n_max = _int(config.get("n_max"), "n_max")
    if n_min < 2 or n_max < n_min:
        raise ValueError("invalid n_min/n_max")
    half_widths = dict(
        _require_mapping(config.get("half_widths", {}), "half_widths")
    )

    effects = [dict(_require_mapping(row, "pilot effect")) for row in _require_sequence(pilot_effects, "pilot_effects")]
    if not effects:
        raise ValueError("pilot_effects must not be empty")
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    alpha = 1.0 - ci_level

    for row in effects:
        metric = str(row.get("metric", "")).strip()
        if not metric or metric in seen:
            raise ValueError("pilot metric must be nonblank and unique")
        seen.add(metric)
        sd = _finite_float(row.get("pilot_sd"), "pilot_sd")
        if sd < 0.0:
            raise ValueError("pilot_sd must be nonnegative")
        if metric not in half_widths:
            raise ValueError(f"missing half-width for {metric}")
        half_width = _finite_float(half_widths[metric], "half_width")
        if half_width <= 0.0:
            raise ValueError("half_width must be positive")

        required_n: int | None = None
        achieved: float | None = None
        if sd == 0.0:
            required_n = n_min
            achieved = 0.0
        else:
            for n in range(n_min, n_max + 1):
                critical = float(
                    _student_t.ppf(1.0 - alpha / 2.0, n - 1)
                )
                width = critical * sd / math.sqrt(n)
                if width <= half_width:
                    required_n = n
                    achieved = width
                    break
        output.append(
            {
                "metric": metric,
                "pilot_sd": sd,
                "half_width": half_width,
                "ci_level": ci_level,
                "n_min": n_min,
                "n_max": n_max,
                "required_n": required_n,
                "achieved_half_width": achieved,
                "feasible": required_n is not None,
            }
        )
    return output


def _csv_fieldnames(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if not rows:
        raise ValueError("cannot write an empty CSV")
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(str(key))
    return fields


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = _csv_fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_replication_analysis(
    batch_root: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    preregistration: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate, analyse and atomically publish one formal batch."""

    batch = Path(batch_root).resolve()
    output = Path(output_dir).resolve()
    if output.exists():
        raise FileExistsError(output)
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)

    loaded = load_valid_replication_blocks(batch, preregistration)
    config = loaded["preregistration"]
    runs = build_replicate_runs(loaded["valid_blocks"])
    paired = build_paired_effects(runs)
    contrasts = compute_factorial_contrasts(paired)
    strategy = aggregate_strategy_estimands(paired, config)
    factorial = aggregate_factorial_estimands(contrasts, config)
    pareto = compute_formal_pareto(
        strategy, tolerance=float(config.get("pareto_tolerance", PARETO_TOLERANCE))
    )
    ranking = bootstrap_rank_stability(
        paired,
        {
            "bootstrap_iterations": config["bootstrap_iterations"],
            "bootstrap_seed": config["bootstrap_seed"],
            "primary_metrics": list(CONFIRMATORY_PRIMARY_METRICS),
            "pareto_tolerance": float(
                config.get("pareto_tolerance", PARETO_TOLERANCE)
            ),
        },
    )

    counts = dict(loaded["counts"])
    formal_complete = bool(loaded["formal_complete"])
    formal_sample_status = str(loaded["formal_sample_status"])
    surplus_valid_blocks = int(loaded["surplus_valid_blocks"])
    source_path = Path(__file__).resolve()
    metadata = {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "formal_replication_id": loaded["formal_replication_id"],
        "git_commit": _git_head(source_path.parent),
        "formal_preregistration_sha256": _canonical_json_sha256(config),
        "analysis_source_sha256": _sha256(source_path),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "scipy_version": _scipy.__version__,
        "primary_metrics": list(CONFIRMATORY_PRIMARY_METRICS),
        "confirmatory_primary_metrics": list(CONFIRMATORY_PRIMARY_METRICS),
        "exploratory_mechanism_metrics": list(EXPLORATORY_MECHANISM_METRICS),
        "all_analysis_metrics": list(ALL_ANALYSIS_METRICS),
        "control_exp_id": CONTROL_EXP_ID,
        "strategy_exp_ids": list(STRATEGY_EXP_IDS),
        "factorial_contrasts": list(FACTORIAL_CONTRASTS),
        "confirmatory_holm_families": {
            "strategy_primary_16": 16,
            "factorial_confirmatory_12": 12,
        },
        "exploratory_holm_families": {
            "factorial_three_way_2": 2,
        },
        "local_did_confirmatory": False,
        "engineering_blocks_forbidden_in_formal": list(
            ENGINEERING_BLOCK_IDS_FORBIDDEN_IN_FORMAL
        ),
        "pareto_ranking_analysis_tier": "exploratory_secondary",
        "pareto_ranking_metric_basis": list(CONFIRMATORY_PRIMARY_METRICS),
        "formal_llm_launch_permitted": False,
        "alpha": config["alpha"],
        "ci_level": config["ci_level"],
        "bootstrap_iterations": config["bootstrap_iterations"],
        "bootstrap_seed": config["bootstrap_seed"],
        "planned_blocks": config["target_valid_blocks"],
        "formal_target_valid_blocks": config["target_valid_blocks"],
        "formal_sample_status": formal_sample_status,
        "surplus_valid_blocks": surplus_valid_blocks,
        "attempted_blocks": counts["attempted"],
        "valid_blocks": counts["valid"],
        "failed_blocks": counts["failed"],
        "invalid_blocks": counts["excluded"],
        "interrupted_blocks": counts["interrupted"],
        "pilot_included": False,
        "smoke_included": False,
        "formal_complete": formal_complete,
        "formal_inference_permitted": formal_complete,
        "input_hashes": {
            "replicate_manifest.csv": _sha256(
                batch / "replicate_manifest.csv"
            ),
            "replication_metadata.json": _sha256(
                batch / "replication_metadata.json"
            ),
            "summaries": {
                block["replicate_id"]: _sha256(
                    Path(block["summary_path"])
                )
                for block in loaded["valid_blocks"]
            },
        },
    }
    validation = {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "formal_replication_id": loaded["formal_replication_id"],
        "confirmatory_primary_metrics": list(CONFIRMATORY_PRIMARY_METRICS),
        "exploratory_mechanism_metrics": list(EXPLORATORY_MECHANISM_METRICS),
        "confirmatory_holm_families": {
            "strategy_primary_16": 16,
            "factorial_confirmatory_12": 12,
        },
        "exploratory_holm_families": {
            "factorial_three_way_2": 2,
        },
        "local_did_confirmatory": False,
        "pareto_rank_local_did": False,
        "formal_llm_launch_permitted": False,
        "formal_complete": formal_complete,
        "formal_inference_permitted": formal_complete,
        "target_valid_blocks": config["target_valid_blocks"],
        "formal_target_valid_blocks": config["target_valid_blocks"],
        "formal_sample_status": formal_sample_status,
        "surplus_valid_blocks": surplus_valid_blocks,
        "attempted_blocks": counts["attempted"],
        "valid_blocks": counts["valid"],
        "excluded_blocks": counts["excluded"],
        "failed_blocks": counts["failed"],
        "interrupted_blocks": counts["interrupted"],
        "all_output_files_present": True,
        "excluded_details": loaded["excluded_blocks"],
    }

    temp_dir = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=str(parent))
    )
    try:
        _write_csv(temp_dir / "replicate_runs.csv", runs)
        _write_csv(temp_dir / "paired_effects.csv", paired)
        _write_csv(temp_dir / "factorial_contrasts.csv", contrasts)
        _write_csv(temp_dir / "strategy_estimates.csv", strategy)
        _write_csv(temp_dir / "factorial_estimates.csv", factorial)
        _write_csv(temp_dir / "formal_pareto.csv", pareto)
        _write_csv(temp_dir / "ranking_bootstrap.csv", ranking)
        _write_json(temp_dir / "analysis_metadata.json", metadata)
        _write_json(temp_dir / "analysis_validation.json", validation)

        missing = [name for name in _OUTPUT_FILES if not (temp_dir / name).is_file()]
        if missing:
            raise RuntimeError(f"analysis output is incomplete: {missing}")
        os.replace(temp_dir, output)
    except BaseException:
        if temp_dir.exists():
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    return {
        "output_dir": str(output),
        "formal_complete": formal_complete,
        "formal_inference_permitted": formal_complete,
        "valid_blocks": counts["valid"],
        "files": list(_OUTPUT_FILES),
    }
