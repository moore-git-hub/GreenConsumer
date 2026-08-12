"""TASK_005 mode-adaptive runtime acceptance checks.

This script validates an existing replication batch without running experiments.
It supports both deterministic-mock engineering pilots and single/multi-block
real smoke batches by deriving expectations from replication_metadata.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from replication_config import (  # noqa: E402
    BLOCK_FAILURE_POLICY,
    CACHE_SCOPE,
    CONDITION_COUNT,
    CONTROL_EXP_ID,
    EXECUTION_MODE,
    LEDGER_FIELDS,
    LATEST_POLICY,
    LLM_SEED_SUPPORTED_VALUES,
    MATRIX_VERSION,
    MAX_PARALLEL_BLOCKS,
    METRICS_SCHEMA_VERSION,
    REPLICATION_SCHEMA_VERSION,
    SEED_DERIVATION_VERSION,
    derive_seed,
    read_seed_ledger_csv,
)
from run_replications import (  # noqa: E402
    BATCH_METADATA_FIELDS,
    FAILURE_FIELDS,
    MANIFEST_FIELDS,
    REPLICATION_METADATA_FIELDS,
    validate_block_artifacts,
)


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"(?i)Authorization\s*:?\s*Bearer\s+[^\s,;]+"),
    re.compile(r"(?i)\b(api[_-]?key|password|token|secret)\s*[:=]\s*[^\s,;]+"),
)

UNCLOSED_ROUTER_WARNINGS = (
    "Unclosed client session",
    "Unclosed connector",
    "session was not closed explicitly",
)

LEGACY_UNCLOSED_REPLICATION_ID = "task005-real-smoke-v1"
LEGACY_UNCLOSED_RUN_EXPERIMENTS_SHA256 = (
    "84f56414d09545133494f5399fc8f359"
    "30f6da88954ffa2dfb28774bf33fcf2e"
)


class Recorder:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.warned = 0

    def check(self, label: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"PASS {label}")
        else:
            self.failed += 1
            suffix = f" | {detail}" if detail else ""
            print(f"FAIL {label}{suffix}")

    def warn(self, label: str, detail: str = "") -> None:
        self.warned += 1
        suffix = f" | {detail}" if detail else ""
        print(f"WARN {label}{suffix}")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path, expected_header: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != expected_header:
            raise AssertionError(f"{path.name} header mismatch")
        return list(reader)


def _is_empty_dir(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


def _parse_csv_nonnegative_int(value: str | None, field: str) -> int:
    text = "" if value is None else str(value).strip()
    if not re.fullmatch(r"\d+", text):
        raise ValueError(f"{field} must be a non-negative integer string")
    return int(text)


def _manifest_int(rec: Recorder, row: dict[str, str], field: str, rid: str) -> int | None:
    try:
        return _parse_csv_nonnegative_int(row.get(field), field)
    except ValueError as exc:
        rec.check(f"{rid} manifest {field} integer", False, str(exc))
        return None


def _metadata_int(rec: Recorder, metadata: dict, field: str, *, minimum: int) -> int | None:
    value = metadata.get(field)
    valid = isinstance(value, int) and not isinstance(value, bool) and value >= minimum
    rec.check(f"batch metadata {field}", valid, repr(value))
    return value if valid else None


def _has_secret_pattern(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _validate_log_safety(
    rec: Recorder,
    path: Path,
    *,
    llm_mode: str,
    replication_id: str,
    num_replicates: int,
    replicate_id: str,
    source_file_hashes: dict,
    allow_legacy_unclosed: bool,
) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    rec.check(f"log {path.name} has no credential-like pattern", not _has_secret_pattern(text))
    has_unclosed = any(fragment in text for fragment in UNCLOSED_ROUTER_WARNINGS)
    has_traceback = "Traceback (most recent call last)" in text
    legacy_identity_matches = (
        llm_mode == "real"
        and replication_id == LEGACY_UNCLOSED_REPLICATION_ID
        and num_replicates == 1
        and replicate_id == "R001"
        and source_file_hashes.get("run_experiments.py")
        == LEGACY_UNCLOSED_RUN_EXPERIMENTS_SHA256
    )
    if has_unclosed and allow_legacy_unclosed and legacy_identity_matches:
        rec.warn(f"log {path.name} legacy unclosed router warning", "allowed by explicit frozen identity")
    else:
        rec.check(f"log {path.name} has no unclosed router warning", not has_unclosed)
        if has_unclosed and allow_legacy_unclosed:
            rec.check(
                f"log {path.name} legacy allowance identity",
                False,
                "identity mismatch",
            )
    rec.check(f"log {path.name} has no traceback", not has_traceback)


def _expected_ids(num_replicates: int) -> list[str]:
    return [f"R{idx:03d}" for idx in range(1, num_replicates + 1)]


def validate_runtime_root(root: Path, *, allow_legacy_unclosed: bool) -> Recorder:
    rec = Recorder()
    metadata = _read_json(root / "replication_metadata.json")
    rec.check("batch metadata is object", isinstance(metadata, dict))
    if not isinstance(metadata, dict):
        return rec
    rec.check("batch metadata fields", tuple(metadata.keys()) == BATCH_METADATA_FIELDS)
    rec.check("batch metadata schema_version", metadata.get("schema_version") == REPLICATION_SCHEMA_VERSION)
    rec.check("batch metadata seed_derivation_version", metadata.get("seed_derivation_version") == SEED_DERIVATION_VERSION)
    rec.check("batch metadata matrix_version", metadata.get("matrix_version") == MATRIX_VERSION)
    rec.check("batch metadata metrics_schema_version", metadata.get("metrics_schema_version") == METRICS_SCHEMA_VERSION)
    rec.check("batch metadata condition_count", metadata.get("condition_count") == CONDITION_COUNT)
    rec.check("batch metadata control_exp_id", metadata.get("control_exp_id") == CONTROL_EXP_ID)
    rec.check("batch metadata cache_scope", metadata.get("cache_scope") == CACHE_SCOPE)
    rec.check("batch metadata execution_mode", metadata.get("execution_mode") == EXECUTION_MODE)
    rec.check(
        "batch metadata max_parallel_blocks",
        metadata.get("max_parallel_blocks") == MAX_PARALLEL_BLOCKS == 1,
        repr(metadata.get("max_parallel_blocks")),
    )
    rec.check("batch metadata latest_policy", metadata.get("latest_policy") == LATEST_POLICY)
    rec.check("batch metadata block_failure_policy", metadata.get("block_failure_policy") == BLOCK_FAILURE_POLICY)

    replication_id = metadata.get("replication_id")
    rec.check("batch metadata replication_id", isinstance(replication_id, str) and bool(replication_id))
    master_seed = _metadata_int(rec, metadata, "master_seed", minimum=0)
    num_replicates = _metadata_int(rec, metadata, "num_replicates", minimum=1)
    llm_mode = metadata.get("llm_mode")
    llm_seed_supported = metadata.get("llm_seed_supported")
    provider_model = metadata.get("provider_model")
    provider_fingerprint = metadata.get("provider_system_fingerprint")
    engineering = metadata.get("engineering_acceptance_only")
    rec.check("batch metadata provider_model", isinstance(provider_model, str), repr(provider_model))
    rec.check(
        "batch metadata provider_system_fingerprint",
        isinstance(provider_fingerprint, str),
        repr(provider_fingerprint),
    )
    rec.check(
        "batch metadata llm_seed_supported",
        llm_seed_supported in LLM_SEED_SUPPORTED_VALUES,
        repr(llm_seed_supported),
    )
    if master_seed is None or num_replicates is None:
        return rec

    expected_ids = _expected_ids(num_replicates)
    rec.check("mode supported", llm_mode in ("deterministic-mock", "real"), str(llm_mode))
    rec.check("engineering flag matches mode", engineering is (llm_mode == "deterministic-mock"))

    ledger = read_seed_ledger_csv(root / "seed_ledger.csv")
    rec.check("ledger row count", len(ledger) == num_replicates, str(len(ledger)))
    rec.check("ledger ids", [row["replicate_id"] for row in ledger] == expected_ids)
    for index, row in enumerate(ledger, start=1):
        rec.check(f"{row['replicate_id']} ledger fields", tuple(row.keys()) == LEDGER_FIELDS)
        rec.check(f"{row['replicate_id']} index contiguous", row["replicate_index"] == index)
        rec.check(f"{row['replicate_id']} simulation seed", row["simulation_seed"] == derive_seed(master_seed, index, "simulation"))
        rec.check(f"{row['replicate_id']} llm seed", row["requested_llm_seed"] == derive_seed(master_seed, index, "llm"))
        rec.check(f"{row['replicate_id']} python hash seed", row["python_hash_seed"] == derive_seed(master_seed, index, "python-hash"))
        rec.check(f"{row['replicate_id']} provider model", row["provider_model"] == provider_model)
        rec.check(f"{row['replicate_id']} provider fingerprint", row["provider_system_fingerprint"] == provider_fingerprint)

    manifest = _read_csv(root / "replicate_manifest.csv", MANIFEST_FIELDS)
    rec.check("manifest row count", len(manifest) == num_replicates, str(len(manifest)))
    rec.check("manifest ids", [row["replicate_id"] for row in manifest] == expected_ids)
    ledger_by_id = {row["replicate_id"]: row for row in ledger}
    for row in manifest:
        rid = row["replicate_id"]
        ledger_row = ledger_by_id.get(rid)
        rec.check(f"{rid} manifest has ledger row", ledger_row is not None)
        if ledger_row is None:
            continue

        rec.check(f"{rid} manifest replication_id", row["replication_id"] == replication_id)
        rec.check(f"{rid} manifest replicate_id", row["replicate_id"] == ledger_row["replicate_id"])
        replicate_index = _manifest_int(rec, row, "replicate_index", rid)
        simulation_seed = _manifest_int(rec, row, "simulation_seed", rid)
        requested_llm_seed = _manifest_int(rec, row, "requested_llm_seed", rid)
        python_hash_seed = _manifest_int(rec, row, "python_hash_seed", rid)
        rec.check(f"{rid} manifest replicate_index", replicate_index == ledger_row["replicate_index"])
        rec.check(f"{rid} manifest simulation_seed", simulation_seed == ledger_row["simulation_seed"])
        rec.check(f"{rid} manifest requested_llm_seed", requested_llm_seed == ledger_row["requested_llm_seed"])
        rec.check(f"{rid} manifest llm_seed_supported", row["llm_seed_supported"] == ledger_row["llm_seed_supported"])
        rec.check(f"{rid} manifest python_hash_seed", python_hash_seed == ledger_row["python_hash_seed"])
        rec.check(f"{rid} manifest block_dir", row["block_dir"] == f"blocks/{rid}")

        rec.check(f"{rid} status succeeded", row["status"] == "succeeded")
        attempt_count = _manifest_int(rec, row, "attempt_count", rid)
        subprocess_exit = _manifest_int(rec, row, "subprocess_exit_code", rid)
        condition_success = _manifest_int(rec, row, "condition_success_count", rid)
        condition_errors = _manifest_int(rec, row, "condition_error_count", rid)
        postprocess_errors = _manifest_int(rec, row, "postprocess_error_count", rid)
        rec.check(f"{rid} attempt positive", attempt_count is not None and attempt_count > 0)
        rec.check(f"{rid} subprocess exit", subprocess_exit == 0)
        rec.check(f"{rid} condition success", condition_success == CONDITION_COUNT)
        rec.check(f"{rid} condition errors", condition_errors == 0)
        rec.check(f"{rid} postprocess errors", postprocess_errors == 0)
        rec.check(f"{rid} replay aligned", row["replay_alignment_violated"] == "False")
        rec.check(f"{rid} network", row["network_status"] == "consistent")
        rec.check(f"{rid} validation flag", row["validation_passed"] == "True")
        rec.check(f"{rid} failure fields empty", not (row["failure_stage"] or row["failure_type"] or row["failure_message"]))
        block_dir = root / row["block_dir"]
        validation = validate_block_artifacts(
            block_dir,
            ledger_by_id[rid],
            subprocess_exit_code=0,
        )
        rec.check(f"{rid} artifact validator", validation.get("validation_passed") is True and validation.get("status") == "succeeded")

        block_meta = _read_json(block_dir / "run_metadata.json")
        replication = block_meta.get("replication", {})
        rec.check(f"{rid} replication fields", set(replication.keys()) == set(REPLICATION_METADATA_FIELDS))
        expected_replication = {
            "schema_version": REPLICATION_SCHEMA_VERSION,
            "replication_id": replication_id,
            "replicate_id": rid,
            "replicate_index": ledger_by_id[rid]["replicate_index"],
            "simulation_seed": ledger_by_id[rid]["simulation_seed"],
            "requested_llm_seed": ledger_by_id[rid]["requested_llm_seed"],
            "llm_seed_supported": llm_seed_supported,
            "python_hash_seed": ledger_by_id[rid]["python_hash_seed"],
            "cache_scope": metadata.get("cache_scope"),
            "execution_mode": metadata.get("execution_mode"),
            "latest_policy": metadata.get("latest_policy"),
            "engineering_acceptance_only": engineering,
        }
        for key, expected in expected_replication.items():
            rec.check(f"{rid} replication {key}", replication.get(key) == expected)

        matrix = block_meta.get("experiment_matrix", {})
        metrics = block_meta.get("metrics", {})
        rec.check(f"{rid} matrix version", matrix.get("matrix_version") == MATRIX_VERSION)
        rec.check(f"{rid} control exp_id", matrix.get("control_exp_id") == CONTROL_EXP_ID)
        rec.check(f"{rid} metrics version", metrics.get("schema_version") == METRICS_SCHEMA_VERSION)

        llm = block_meta.get("llm", {})
        hashes = block_meta.get("source_file_hashes", {})
        if llm_mode == "deterministic-mock":
            rec.check(f"{rid} mock engineering flag", engineering is True)
            rec.check(f"{rid} mock llm mode", llm.get("mode") == "deterministic-mock")
            rec.check(f"{rid} mock config_read", llm.get("config_read") is False)
            rec.check(f"{rid} mock config_file", llm.get("config_file") == "not-read")
            rec.check(f"{rid} mock config_sha256", llm.get("config_sha256") == "not-read")
            rec.check(f"{rid} mock api_key", llm.get("api_key_present") == "not-read")
            rec.check(f"{rid} mock config hash", hashes.get("configs/models_config.yaml") == "not-read: deterministic-mock")
        else:
            rec.check(f"{rid} real engineering flag", engineering is False)
            rec.check(f"{rid} real llm mode", llm.get("mode") == "real")
            rec.check(f"{rid} real config file", llm.get("config_file") == "configs/models_config.yaml")
            rec.check(f"{rid} real config sha", isinstance(llm.get("config_sha256"), str) and bool(re.fullmatch(r"[0-9a-f]{64}", llm.get("config_sha256", ""))))
            rec.check(f"{rid} real api key present bool", isinstance(llm.get("api_key_present"), bool))
            rec.check(f"{rid} real requested seed", llm.get("requested_llm_seed") == ledger_by_id[rid]["requested_llm_seed"])
            rec.check(f"{rid} real seed support unchanged", llm.get("llm_seed_supported") == llm_seed_supported)

        for name in ("child_stdout.log", "child_stderr.log"):
            _validate_log_safety(
                rec,
                block_dir / name,
                llm_mode=llm_mode,
                replication_id=replication_id,
                num_replicates=num_replicates,
                replicate_id=rid,
                source_file_hashes=hashes,
                allow_legacy_unclosed=allow_legacy_unclosed,
            )

    failures = _read_csv(root / "replication_failures.csv", FAILURE_FIELDS)
    rec.check("failure ledger empty", len(failures) == 0, str(len(failures)))
    rec.check("work empty", _is_empty_dir(root / "work"))
    rec.check("failures empty", _is_empty_dir(root / "failures"))
    rec.check("batch has no latest", not (root / "latest").exists())
    rec.check("batch has no run timestamp layer", not any(path.name.startswith("run_") for path in root.iterdir()))
    return rec


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--allow-legacy-unclosed-router-warning", action="store_true")
    args = parser.parse_args(argv)
    rec = validate_runtime_root(
        Path(args.runtime_root),
        allow_legacy_unclosed=args.allow_legacy_unclosed_router_warning,
    )
    print("=" * 72)
    print("TASK_005 MODE-ADAPTIVE RUNTIME ACCEPTANCE")
    print("=" * 72)
    print(f"Passed: {rec.passed}")
    print(f"Failed: {rec.failed}")
    print(f"Warned: {rec.warned}")
    return 1 if rec.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
