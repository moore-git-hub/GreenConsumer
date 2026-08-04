"""TASK_005 seed ledger configuration and CSV utilities.

This module is intentionally limited to deterministic seed derivation and
ledger serialization. It does not import or run simulation, agent, or LLM code.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


REPLICATION_SCHEMA_VERSION = "1.0"
SEED_DERIVATION_VERSION = "sha256-v1"
SEED_NAMESPACE_PREFIX = "task005"
CACHE_SCOPE = "replicate-block-only"
EXECUTION_MODE = "serial-subprocess"
MAX_PARALLEL_BLOCKS = 1
LATEST_POLICY = "disabled"
BLOCK_FAILURE_POLICY = "fail-closed-complete-9"
SEED_MIN = 1
SEED_MAX = 2**32 - 1

MATRIX_VERSION = "3.0"
METRICS_SCHEMA_VERSION = "4.0"
CONDITION_COUNT = 9
CONTROL_EXP_ID = "NoClarification-Control"

LLM_SEED_SUPPORTED_VALUES = (
    "true",
    "false",
    "unknown",
)

EXECUTION_ORDER = (
    "NoClarification-Control",
    "Empathy-Hub-Delayed",
    "Empathy-Hub-Immediate",
    "Empathy-Random-Delayed",
    "Empathy-Random-Immediate",
    "Rational-Hub-Delayed",
    "Rational-Hub-Immediate",
    "Rational-Random-Delayed",
    "Rational-Random-Immediate",
)

LEDGER_FIELDS = (
    "replication_schema_version",
    "seed_derivation_version",
    "master_seed",
    "replicate_index",
    "replicate_id",
    "simulation_seed",
    "requested_llm_seed",
    "llm_seed_supported",
    "matrix_version",
    "metrics_schema_version",
    "condition_count",
    "control_exp_id",
    "execution_order",
    "cache_scope",
    "profile_seed",
    "network_seed",
    "target_seed",
    "python_hash_seed",
    "provider_model",
    "provider_system_fingerprint",
)

_INT_FIELDS = (
    "master_seed",
    "replicate_index",
    "simulation_seed",
    "requested_llm_seed",
    "condition_count",
    "profile_seed",
    "network_seed",
    "target_seed",
    "python_hash_seed",
)

_SEED_FIELDS = (
    "simulation_seed",
    "requested_llm_seed",
    "profile_seed",
    "network_seed",
    "target_seed",
    "python_hash_seed",
)


def _require_int(name: str, value: Any, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _require_seed(name: str, value: Any) -> int:
    seed = _require_int(name, value)
    if not (SEED_MIN <= seed <= SEED_MAX):
        raise ValueError(f"{name} must be in [{SEED_MIN}, {SEED_MAX}]")
    return seed


def derive_seed(
    master_seed: int,
    replicate_index: int,
    namespace: str,
) -> int:
    """Derive a deterministic 32-bit seed using the frozen SHA-256 contract."""
    master = _require_int("master_seed", master_seed, minimum=0)
    index = _require_int("replicate_index", replicate_index, minimum=1)
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace must be a non-empty string")

    payload = (
        f"{SEED_NAMESPACE_PREFIX}|{master}|{index}|{namespace}"
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return (
        1
        + int.from_bytes(digest[:8], "big")
        % (2**32 - 1)
    )


def build_seed_ledger(
    master_seed: int,
    num_replicates: int,
    *,
    llm_seed_supported: str = "unknown",
    provider_model: str = "",
    provider_system_fingerprint: str = "",
) -> list[dict]:
    """Build and validate seed ledger rows for consecutive replicate blocks."""
    master = _require_int("master_seed", master_seed, minimum=0)
    count = _require_int("num_replicates", num_replicates, minimum=1)
    if llm_seed_supported not in LLM_SEED_SUPPORTED_VALUES:
        raise ValueError("llm_seed_supported is invalid")
    if not isinstance(provider_model, str):
        raise ValueError("provider_model must be a string")
    if not isinstance(provider_system_fingerprint, str):
        raise ValueError("provider_system_fingerprint must be a string")

    rows: list[dict] = []
    for replicate_index in range(1, count + 1):
        simulation_seed = derive_seed(master, replicate_index, "simulation")
        requested_llm_seed = derive_seed(master, replicate_index, "llm")
        python_hash_seed = derive_seed(master, replicate_index, "python-hash")
        rows.append(
            {
                "replication_schema_version": REPLICATION_SCHEMA_VERSION,
                "seed_derivation_version": SEED_DERIVATION_VERSION,
                "master_seed": master,
                "replicate_index": replicate_index,
                "replicate_id": f"R{replicate_index:03d}",
                "simulation_seed": simulation_seed,
                "requested_llm_seed": requested_llm_seed,
                "llm_seed_supported": llm_seed_supported,
                "matrix_version": MATRIX_VERSION,
                "metrics_schema_version": METRICS_SCHEMA_VERSION,
                "condition_count": CONDITION_COUNT,
                "control_exp_id": CONTROL_EXP_ID,
                "execution_order": EXECUTION_ORDER,
                "cache_scope": CACHE_SCOPE,
                "profile_seed": simulation_seed,
                "network_seed": simulation_seed,
                "target_seed": simulation_seed,
                "python_hash_seed": python_hash_seed,
                "provider_model": provider_model,
                "provider_system_fingerprint": provider_system_fingerprint,
            }
        )
    return validate_seed_ledger(rows)


def validate_seed_ledger(rows) -> list[dict]:
    """Validate ledger rows and return sorted deep-copied canonical rows."""
    try:
        return _validate_seed_ledger(rows)
    except ValueError:
        raise
    except Exception as exc:  # defensive normalization for contract callers
        raise ValueError(str(exc)) from exc


def _validate_seed_ledger(rows) -> list[dict]:
    if not isinstance(rows, list):
        raise ValueError("rows must be a list")
    if not rows:
        raise ValueError("rows must contain at least one ledger row")
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("each row must be a mapping")

    expected_keys = set(LEDGER_FIELDS)
    original_rows = list(rows)
    for row in original_rows:
        if set(row.keys()) != expected_keys:
            raise ValueError("ledger row keys must exactly match LEDGER_FIELDS")

    sorted_rows = sorted(original_rows, key=lambda row: row["replicate_index"])
    master_seed = None
    replicate_ids: set[str] = set()
    replicate_indexes: set[int] = set()
    simulation_seeds: set[int] = set()
    requested_llm_seeds: set[int] = set()
    python_hash_seeds: set[int] = set()
    canonical_rows: list[dict] = []

    for expected_index, row in enumerate(sorted_rows, start=1):
        row_master = _require_int("master_seed", row["master_seed"], minimum=0)
        if master_seed is None:
            master_seed = row_master
        elif row_master != master_seed:
            raise ValueError("all master_seed values must match")

        replicate_index = _require_int(
            "replicate_index", row["replicate_index"], minimum=1
        )
        if replicate_index != expected_index:
            raise ValueError("replicate_index must be continuous from 1 to N")
        if replicate_index in replicate_indexes:
            raise ValueError("duplicate replicate_index")
        replicate_indexes.add(replicate_index)

        replicate_id = row["replicate_id"]
        expected_replicate_id = f"R{replicate_index:03d}"
        if replicate_id != expected_replicate_id:
            raise ValueError("replicate_id does not match replicate_index")
        if replicate_id in replicate_ids:
            raise ValueError("duplicate replicate_id")
        replicate_ids.add(replicate_id)

        seeds = {field: _require_seed(field, row[field]) for field in _SEED_FIELDS}
        expected_simulation = derive_seed(row_master, replicate_index, "simulation")
        expected_llm = derive_seed(row_master, replicate_index, "llm")
        expected_python_hash = derive_seed(row_master, replicate_index, "python-hash")
        if seeds["simulation_seed"] != expected_simulation:
            raise ValueError("simulation_seed does not match derivation")
        if seeds["requested_llm_seed"] != expected_llm:
            raise ValueError("requested_llm_seed does not match derivation")
        if seeds["python_hash_seed"] != expected_python_hash:
            raise ValueError("python_hash_seed does not match derivation")
        if seeds["profile_seed"] != seeds["simulation_seed"]:
            raise ValueError("profile_seed must equal simulation_seed")
        if seeds["network_seed"] != seeds["simulation_seed"]:
            raise ValueError("network_seed must equal simulation_seed")
        if seeds["target_seed"] != seeds["simulation_seed"]:
            raise ValueError("target_seed must equal simulation_seed")

        if seeds["simulation_seed"] in simulation_seeds:
            raise ValueError("duplicate simulation_seed")
        if seeds["requested_llm_seed"] in requested_llm_seeds:
            raise ValueError("duplicate requested_llm_seed")
        if seeds["python_hash_seed"] in python_hash_seeds:
            raise ValueError("duplicate python_hash_seed")
        simulation_seeds.add(seeds["simulation_seed"])
        requested_llm_seeds.add(seeds["requested_llm_seed"])
        python_hash_seeds.add(seeds["python_hash_seed"])

        if row["replication_schema_version"] != REPLICATION_SCHEMA_VERSION:
            raise ValueError("replication_schema_version mismatch")
        if row["seed_derivation_version"] != SEED_DERIVATION_VERSION:
            raise ValueError("seed_derivation_version mismatch")
        if row["matrix_version"] != MATRIX_VERSION:
            raise ValueError("matrix_version mismatch")
        if row["metrics_schema_version"] != METRICS_SCHEMA_VERSION:
            raise ValueError("metrics_schema_version mismatch")
        condition_count = _require_int("condition_count", row["condition_count"])
        if condition_count != CONDITION_COUNT:
            raise ValueError("condition_count mismatch")
        if row["control_exp_id"] != CONTROL_EXP_ID:
            raise ValueError("control_exp_id mismatch")
        if tuple(row["execution_order"]) != EXECUTION_ORDER:
            raise ValueError("execution_order mismatch")
        if row["cache_scope"] != CACHE_SCOPE:
            raise ValueError("cache_scope mismatch")
        if row["llm_seed_supported"] not in LLM_SEED_SUPPORTED_VALUES:
            raise ValueError("llm_seed_supported is invalid")
        if not isinstance(row["provider_model"], str):
            raise ValueError("provider_model must be a string")
        if not isinstance(row["provider_system_fingerprint"], str):
            raise ValueError("provider_system_fingerprint must be a string")

        canonical_rows.append(
            {
                "replication_schema_version": row["replication_schema_version"],
                "seed_derivation_version": row["seed_derivation_version"],
                "master_seed": row_master,
                "replicate_index": replicate_index,
                "replicate_id": replicate_id,
                "simulation_seed": seeds["simulation_seed"],
                "requested_llm_seed": seeds["requested_llm_seed"],
                "llm_seed_supported": row["llm_seed_supported"],
                "matrix_version": row["matrix_version"],
                "metrics_schema_version": row["metrics_schema_version"],
                "condition_count": condition_count,
                "control_exp_id": row["control_exp_id"],
                "execution_order": tuple(row["execution_order"]),
                "cache_scope": row["cache_scope"],
                "profile_seed": seeds["profile_seed"],
                "network_seed": seeds["network_seed"],
                "target_seed": seeds["target_seed"],
                "python_hash_seed": seeds["python_hash_seed"],
                "provider_model": row["provider_model"],
                "provider_system_fingerprint": row["provider_system_fingerprint"],
            }
        )

    return [{field: row[field] for field in LEDGER_FIELDS} for row in canonical_rows]


def write_seed_ledger_csv(
    rows,
    output_path,
) -> None:
    """Atomically write validated seed ledger rows as UTF-8 CSV."""
    validated = validate_seed_ledger(rows)
    path = Path(output_path)
    parent = path.parent if path.parent != Path("") else Path(".")
    tmp_path: str | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(parent)
        )
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(LEDGER_FIELDS))
            writer.writeheader()
            for row in validated:
                out = {field: row[field] for field in LEDGER_FIELDS}
                out["execution_order"] = json.dumps(
                    list(row["execution_order"]),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                writer.writerow(out)
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass


def read_seed_ledger_csv(
    input_path,
) -> list[dict]:
    """Read a seed ledger CSV and return validated canonical rows."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    try:
        rows: list[dict] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
                raise ValueError("seed ledger CSV header mismatch")
            for raw in reader:
                if None in raw:
                    raise ValueError("seed ledger CSV contains extra columns")
                row = dict(raw)
                for field in _INT_FIELDS:
                    row[field] = int(row[field])
                try:
                    order = json.loads(row["execution_order"])
                except json.JSONDecodeError as exc:
                    raise ValueError("execution_order is not valid JSON") from exc
                if not isinstance(order, list):
                    raise ValueError("execution_order must be a JSON array")
                row["execution_order"] = tuple(order)
                rows.append(row)
        return validate_seed_ledger(rows)
    except FileNotFoundError:
        raise
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(str(exc)) from exc
