# TASK_005 Phase 1 Design Baseline: Seed Ledger and Replicate Blocks

Status: frozen acceptance baseline, no production implementation in this phase.

Audit base commit: `255fdececbd5882143861cd6ddae98b0c65b432f`

## 1. Scope

TASK_005 v1.0 defines the seed ledger and replicate block contract for future replication inference. Phase 1 only freezes design and tests. It must not create `replication_config.py`, `run_replications.py`, `replication_analysis.py`, production code, runtime results, or experiment run directories.

The implementation model is:

- one parent replication runner;
- each replicate block launches one independent Python subprocess;
- blocks are strictly serial;
- each block contains the complete 9 condition matrix;
- control runs first and builds that block's private Recording cache;
- the 8 strategies only use the same block cache;
- caches are never shared across blocks;
- each subprocess sets that block's `PYTHONHASHSEED` before startup;
- each block uses one unique `simulation_seed`;
- the 9 conditions within a block share the same `simulation_seed`;
- `results/experiments/latest` synchronization is disabled;
- parallel execution is unsupported.

Module responsibilities are frozen as follows.

`replication_config.py is responsible for`:

- all seed/ledger version constants;
- `EXECUTION_ORDER`;
- `LEDGER_FIELDS`;
- `LLM_SEED_SUPPORTED_VALUES`;
- `derive_seed`;
- `build_seed_ledger`;
- `validate_seed_ledger`;
- `write_seed_ledger_csv`;
- `read_seed_ledger_csv`.

`run_replications.py is responsible for`:

- `BLOCK_STATES`;
- `ALLOWED_TRANSITIONS`;
- `MANIFEST_FIELDS`;
- `REPLICATION_METADATA_FIELDS`;
- `SUBPROCESS_ENV_CONTRACT`;
- `DETERMINISTIC_MOCK_ENV_CONTRACT`;
- `RUN_EXPERIMENTS_ARGS`;
- `LLM_MODES`;
- `validate_block_artifacts`;
- block state, resume, subprocess, and failure handling.

S2-S6 acceptance checks only inspect `replication_config.py`. S7-S11 only inspect `run_replications.py`. Both production modules are intentionally absent in Phase 1, so those groups may fail for missing modules without indicating a test harness error.

Phase 1 baselines allow production modules to be missing. After future production modules appear, T0 must switch from "missing allowed" to syntax checking for `replication_config.py`, `run_replications.py`, and `replication_analysis.py` using a temporary `py_compile` output path. T0 must not fail merely because a legitimate production module exists.

## 2. Frozen Constants

Future `replication_config.py` must define:

```python
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
```

Version dependencies:

```python
MATRIX_VERSION = "3.0"
METRICS_SCHEMA_VERSION = "4.0"
CONDITION_COUNT = 9
CONTROL_EXP_ID = "NoClarification-Control"
```

Future `run_replications.py` must define runner constants and schemas in sections 10-13.

## 3. Execution Order

Every block must use this exact `execution_order`:

1. `NoClarification-Control`
2. `Empathy-Hub-Delayed`
3. `Empathy-Hub-Immediate`
4. `Empathy-Random-Delayed`
5. `Empathy-Random-Immediate`
6. `Rational-Hub-Delayed`
7. `Rational-Hub-Immediate`
8. `Rational-Random-Delayed`
9. `Rational-Random-Immediate`

Forbidden:

- using set iteration order;
- relying on current `generate_experiment_matrix()` iteration order;
- placing the control after strategies;
- reusing a control cache across blocks.

## 4. Seed Derivation

Future `replication_config.py` must provide:

```python
def derive_seed(
    master_seed: int,
    replicate_index: int,
    namespace: str,
) -> int:
    ...
```

Frozen algorithm:

```python
import hashlib

payload = (
    f"task005|{master_seed}|{replicate_index}|{namespace}"
).encode("utf-8")

digest = hashlib.sha256(payload).digest()

seed = (
    1
    + int.from_bytes(digest[:8], "big")
    % (2**32 - 1)
)
```

Constraints:

- `master_seed` must be a non-negative integer;
- `bool` is not accepted as an integer;
- `replicate_index` must be an integer greater than or equal to 1;
- `namespace` must be a non-empty string;
- result must be between `1` and `2**32 - 1`;
- Python `hash()` is forbidden;
- `seed + 1` derivation is forbidden;
- global `random` state is forbidden.

Canonical fixture values for `master_seed = 20260802`:

| replicate | simulation_seed | requested_llm_seed | python_hash_seed |
| --- | ---: | ---: | ---: |
| R001 | 2054889395 | 1403096098 | 1948440462 |
| R002 | 2501312439 | 269099072 | 4123444394 |
| R003 | 3592391985 | 3996138357 | 2321646447 |

## 5. Ledger Fields

Future `replication_config.py` must define `LEDGER_FIELDS` in this exact order:

1. `replication_schema_version`
2. `seed_derivation_version`
3. `master_seed`
4. `replicate_index`
5. `replicate_id`
6. `simulation_seed`
7. `requested_llm_seed`
8. `llm_seed_supported`
9. `matrix_version`
10. `metrics_schema_version`
11. `condition_count`
12. `control_exp_id`
13. `execution_order`
14. `cache_scope`
15. `profile_seed`
16. `network_seed`
17. `target_seed`
18. `python_hash_seed`
19. `provider_model`
20. `provider_system_fingerprint`

v1.0 coupling semantics:

- `profile_seed == simulation_seed`;
- `network_seed == simulation_seed`;
- `target_seed == simulation_seed`;
- `target_seed` is the base seed passed to current `select_target_nodes`;
- current internal fixed offset `+7777` remains unchanged;
- `profile_seed`, `network_seed`, and `target_seed` are lineage aliases, not three independent random streams;
- `python_hash_seed` uses namespace `"python-hash"`;
- `requested_llm_seed` uses namespace `"llm"`;
- `requested_llm_seed` does not guarantee server-side determinism.

`llm_seed_supported` only allows:

- `"true"`
- `"false"`
- `"unknown"`

Before formal real LLM execution it must not default to `"true"`.

## 6. Public API Contract

Future `replication_config.py` must provide:

```python
derive_seed(
    master_seed,
    replicate_index,
    namespace,
) -> int

build_seed_ledger(
    master_seed: int,
    num_replicates: int,
    *,
    llm_seed_supported: str = "unknown",
    provider_model: str = "",
    provider_system_fingerprint: str = "",
) -> list[dict]

validate_seed_ledger(rows) -> list[dict]

write_seed_ledger_csv(
    rows,
    output_path,
) -> None

read_seed_ledger_csv(
    input_path,
) -> list[dict]
```

`build_seed_ledger` rules:

- `num_replicates` must be a positive integer;
- `bool` is not accepted as an integer;
- `replicate_index` increases continuously from 1;
- `replicate_id` uses at least three zero-padded digits: `R001`, `R002`, ..., `R999`, `R1000`;
- `simulation_seed` uses namespace `"simulation"`;
- `requested_llm_seed` uses namespace `"llm"`;
- `python_hash_seed` uses namespace `"python-hash"`;
- profile/network/target seeds equal `simulation_seed`;
- all `simulation_seed` values are unique within the ledger;
- all `requested_llm_seed` values are unique within the ledger;
- all `python_hash_seed` values are unique within the ledger;
- `execution_order` uses the frozen 9 item order;
- `cache_scope` is `"replicate-block-only"`;
- caller input is not mutated.

`validate_seed_ledger` rules:

- input must be a list;
- input must contain at least one row;
- each row must be a mapping;
- keys must exactly equal `LEDGER_FIELDS`;
- all rows must have the same `master_seed`;
- `replicate_index` must be exactly `1..N` without gaps;
- `replicate_id` must match index;
- all three derived seeds must recompute exactly;
- `profile_seed`, `network_seed`, and `target_seed` must equal `simulation_seed`;
- all seeds must be legal integers and must reject bool;
- version, matrix, metrics, condition count, and control id must match constants;
- `execution_order` must exactly match the frozen order;
- `cache_scope` must exactly match;
- `llm_seed_supported` must be in the three-value set;
- provider fields must be strings;
- duplicate `replicate_id` or duplicate seeds are forbidden;
- all errors raise `ValueError`;
- return a deep-copied list sorted by `replicate_index`;
- original rows are not mutated.

## 7. CSV Serialization

`write_seed_ledger_csv`:

- uses UTF-8;
- header is exactly `LEDGER_FIELDS`;
- `execution_order` is written as compact JSON array;
- writes to a temporary file and uses `os.replace` for atomic replacement;
- never writes API keys;
- calls `validate_seed_ledger` before writing.

`read_seed_ledger_csv`:

- missing file raises `FileNotFoundError`;
- header must exactly match `LEDGER_FIELDS`;
- numeric fields are restored as `int`;
- `execution_order` is restored as a tuple or immutable equivalent sequence;
- calls `validate_seed_ledger` after reading;
- write then read must be semantically round-trip identical.

## 8. Block Directory Structure

Replication batch directory:

```text
results/replications/<replication_id>/
```

It contains:

- `seed_ledger.csv`
- `replicate_manifest.csv`
- `replication_metadata.json`
- `replication_failures.csv`
- `blocks/`
- `work/`
- `failures/`

Successful block directories:

```text
blocks/R001/
blocks/R002/
```

Subprocess first writes:

```text
work/R001.attempt_001/
```

Only after complete validation may it be atomically moved to:

```text
blocks/R001/
```

Failed or interrupted artifacts move to:

```text
failures/R001/attempt_001/
```

Successful `blocks/R001` must never be overwritten.

## 9. Block Success Contract

A block is `succeeded` only when all conditions hold:

- directory exists;
- `run_metadata.json` exists and is parseable;
- `replication` block matches the ledger row field by field;
- `experiment_matrix.matrix_version == "3.0"`;
- `condition_count == 9`;
- `metrics.schema_version == "4.0"`;
- `batch_exit_code == 0`;
- `run_completed is true`;
- `replay_alignment_violated is false`;
- network status is `consistent`;
- `summary.csv` has exactly 9 rows;
- exactly 1 control and 8 strategies;
- v4 fields satisfy TASK_004 contracts;
- `ranking_sensitivity.csv` has 528 rows;
- `ranking_robustness.csv` has 8 rows;
- `fig1` through `fig6` exist and are non-empty;
- `errors.log` does not exist;
- `network_inconsistency_report.json` does not exist;
- subprocess exit code is 0.

If any item fails:

- the block must not enter paired analysis;
- status is only `failed` or `invalid`;
- failed condition rows must not be deleted and analyzed as if complete;
- no successful manifest row may be fabricated.

## 10. Block State Machine

States:

- `planned`
- `running`
- `succeeded`
- `failed`
- `invalid`
- `interrupted`

Allowed transitions:

- `planned -> running`
- `running -> succeeded`
- `running -> failed`
- `running -> invalid`
- `running -> interrupted`
- `failed -> running` only with explicit retry
- `invalid -> running` only with explicit retry
- `interrupted -> running` only with explicit retry

Forbidden:

- `succeeded -> running`;
- overwriting `succeeded`;
- treating `running` as success;
- silently deleting failure evidence.

Resume rules:

- existing verified `succeeded` block is skipped;
- missing block is run;
- existing `running` block with no live process is marked `interrupted`;
- `failed`/`invalid`/`interrupted` rerun only with explicit `--retry-failed`;
- retry increments `attempt_index`;
- successful block is never rerun.

## 11. Subprocess Contract

Future `run_replications.py` must launch subprocesses with an argv list, never by shell string concatenation.

The argv list requirement is normative: subprocess commands must be constructed as a list of exact arguments. Shell string concatenation, shell interpolation, and API-key-bearing command logs are forbidden.

Each block subprocess environment includes at least:

- `PYTHONUTF8=1`
- `PYTHONIOENCODING=utf-8`
- `PYTHONHASHSEED=<ledger python_hash_seed>`
- `MPLBACKEND=Agg`
- `TOKENIZERS_PARALLELISM=false`

`deterministic-mock` mode additionally includes:

- `HF_HUB_OFFLINE=1`
- `TRANSFORMERS_OFFLINE=1`
- `HF_DATASETS_OFFLINE=1`
- `HF_HUB_DISABLE_TELEMETRY=1`

Future `run_experiments.py` entry or equivalent implementation must support:

- `--replication-id`
- `--replicate-id`
- `--replicate-index`
- `--simulation-seed`
- `--requested-llm-seed`
- `--llm-seed-supported`
- `--python-hash-seed`
- `--output-dir`
- `--no-latest`
- `--llm-mode`

`llm-mode` only allows:

- `real`
- `deterministic-mock`

Constraints:

- `real` mode must fail when configuration or provider is unavailable;
- it must not automatically downgrade to mock;
- `deterministic-mock` metadata must set `engineering_acceptance_only=true`;
- `deterministic-mock` results must not be used as thesis evidence;
- commands, ledgers, manifests, and logs must not contain API keys;
- `MAX_PARALLEL_BLOCKS` is fixed at 1;
- requested parallelism greater than 1 must fail.

## 12. Block Metadata

Future `run_metadata.json` adds an independent `replication` block:

Future `run_replications.py` must define `REPLICATION_METADATA_FIELDS` in this exact order:

1. `schema_version`
2. `replication_id`
3. `replicate_id`
4. `replicate_index`
5. `simulation_seed`
6. `requested_llm_seed`
7. `llm_seed_supported`
8. `python_hash_seed`
9. `cache_scope`
10. `execution_mode`
11. `latest_policy`
12. `engineering_acceptance_only`

```json
{
  "schema_version": "1.0",
  "replication_id": "...",
  "replicate_id": "R001",
  "replicate_index": 1,
  "simulation_seed": 2054889395,
  "requested_llm_seed": 1403096098,
  "llm_seed_supported": "unknown",
  "python_hash_seed": 1948440462,
  "cache_scope": "replicate-block-only",
  "execution_mode": "serial-subprocess",
  "latest_policy": "disabled",
  "engineering_acceptance_only": true
}
```

Requirements:

- independent from `experiment_matrix` and `metrics`;
- never writes API keys;
- subprocess actual `config.random_seed` must equal `simulation_seed`;
- all 9 condition `random_seed` values must be identical;
- whether `requested_llm_seed` was accepted by provider is recorded separately;
- `unknown` is never rewritten to `true`.

## 13. Manifest Contract

`replicate_manifest.csv` has one row per replicate block.

Primary key:

- `replicate_id`

`MANIFEST_FIELDS` is the v1.0 exact ordered CSV schema. It has the following 22 fields in exact order; adding fields later requires a `replication_schema_version` upgrade:

- `replication_id`
- `replicate_id`
- `replicate_index`
- `simulation_seed`
- `requested_llm_seed`
- `llm_seed_supported`
- `python_hash_seed`
- `status`
- `attempt_count`
- `block_dir`
- `started_at`
- `finished_at`
- `subprocess_exit_code`
- `condition_success_count`
- `condition_error_count`
- `postprocess_error_count`
- `replay_alignment_violated`
- `network_status`
- `validation_passed`
- `failure_stage`
- `failure_type`
- `failure_message`

Future `run_replications.py` must provide:

```python
def validate_block_artifacts(
    block_dir,
    ledger_row,
    *,
    subprocess_exit_code: int,
) -> dict:
    ...
```

The returned dict must contain at least:

- `validation_passed`
- `status`
- `condition_success_count`
- `condition_error_count`
- `postprocess_error_count`
- `replay_alignment_violated`
- `network_status`
- `failure_stage`
- `failure_type`
- `failure_message`

`validate_block_artifacts` must not mutate `ledger_row`.

Rules:

- one row represents a block, not a condition;
- `succeeded` requires `validation_passed=True`;
- `succeeded` requires `condition_success_count=9`;
- `failure_message` must not contain API keys;
- writes are atomic;
- success must never be inferred from directory existence alone.

## 14. Non-Goals

Phase 1 does not freeze:

- formal concrete block count;
- whether pilot merges into formal;
- real LLM seed support conclusion;
- parallel implementation;
- independent profile/network/target variance decomposition;
- cross-block statistical model implementation;
- bootstrap iteration count;
- p-value threshold;
- formal strategy ranking.

## 15. Acceptance Baseline

`tests/test_task005_replication_inference.py` is a standalone executable script. It does not require pytest, network, real LLM, AgentKernel stubs, production file modification, dependency installation, or experiment runs.

The fixture `tests/fixtures/task005/seed_ledger_cases.json` has fixture schema v1.0 and exactly 35 invalid cases. Every invalid case must be a JSON object with a unique non-empty `case_id` and an allowed non-empty `category`. Adding, removing, or renaming invalid cases requires updating this acceptance baseline and the fixture schema/version together.

Groups:

- `T0-syntax`
- `S0-fixture`
- `S1-design-contract`
- `S2-version-constants`
- `S3-seed-derivation`
- `S4-ledger-build-validation`
- `S5-ledger-csv-roundtrip`
- `S6-execution-order-cache-scope`
- `S7-block-state-resume`
- `S8-subprocess-spec`
- `S9-block-artifact-contract`
- `S10-failure-policy`
- `S11-provenance-secret-safety`
- `S12-task003-task004-invariance`
- `S13-runtime-pilot`

Phase 1 expectations:

- `T0-syntax` has `FAIL=0`;
- `S0-fixture` has `FAIL=0`;
- `S1-design-contract` has `FAIL=0`;
- `S12-task003-task004-invariance` has `FAIL=0`;
- `S13-runtime-pilot` has exactly one warning when `--runtime-root` is not supplied;
- `S2` through `S11` may fail only because future production APIs are not implemented;
- wrapper exceptions are always FAIL and must print real exception details;
- stderr remains empty;
- final summary is always printed;
- exit code is 1 when any FAIL exists, otherwise 0.
