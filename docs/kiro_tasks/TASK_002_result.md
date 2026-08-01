# TASK_002 — agent_records Observability (schema v2.0)

## Status

Code applied. Acceptance test **PASSED** — 270 assertions executed, 268 PASS,
0 FAIL, 2 WARN, exit code 0.

- Test: `tests/test_task002_observability.py`
- Evidence: `results/task002_validation/20260801_101156/`
- Authoritative design: `.kiro/specs/agent-records-observability/design.md` (round 5)

## Goal and scope

Upgrade `agent_records` from a 21-column result snapshot into a 60-column
**auditable evidence chain**, and add run-level provenance so that every number in
thesis chapters 5–6 can be traced back to *which code, which prompt, which network,
and which message was actually observed*.

Two governing principles, both enforced by the acceptance test rather than by review:

1. **Observability only, behavior unchanged.** Every expression participating in trust
   computation is preserved verbatim; all new fields are side-channel output.
2. **Recording must not be replaced by inference.** `network_type`,
   `clarification_content_type`, `global_event_received`, `effective_event_timeline`
   and `top_p` must come from the real graph branch, the real observed message, the
   real runtime state and the real config file. Missing values are recorded as
   `"unknown"` / `"missing:*"` / `""` — never filled with a plausible default, and
   never derived from a tick-vs-constant comparison.

Explicitly out of scope: prompts, personas, formulas, parameters, the experiment
matrix, and metric definitions.

## Provenance

| Item | Value |
|---|---|
| Baseline fixture commit | `70d225c53826e2571867e72e1425177370f62b52` — *test(observability): freeze pre-task002 behavior baseline* |
| Fixture `generated_from_commit` | `1861003e08c6cca98cca340338feaffa120555d4` (pre-TASK_002 code state) |
| HEAD before implementation | `ba90ff247f7b4daa14d44881f882fed0a51785af` — *docs(observability): finalize TASK_002 technical design* |
| Branch | `audit/task002-observability` |
| Test harness SHA-256 | `721e55ef34dcc177e9c0fb82868cdd8accdce545303ea7b21946e3e14ee9c9d1` |
| Acceptance run | `results/task002_validation/20260801_101156/` |

The fixture was generated **before** any production diff was applied, on a clean
production tree, and committed to lock the baseline. The harness hash is recorded
inside the fixture and re-verified during acceptance: the test file defines the entire
input (router responses, scenario constants, compared fields), so changing it would
silently turn the zero-tolerance comparison into a comparison of two different
experiments.

## Files changed (5 production files)

| # | File | Nature of change |
|---|---|---|
| 1 | `clarification_injector.py` | `content_factor` added to the message packet; new `last_injected_ids` receipt. `inject()` signature and `-> int` return type unchanged |
| 2 | `plugins/environment/network/SocialNetworkPlugin.py` | 3 pure-audit attributes (`network_type` / `network_params` / `network_fallback_reason`) assigned inside the real graph-construction branches; 2 read-only exporters. Graph logic untouched |
| 3 | `plugins/agent/plan/ConsumerPlanPlugin.py` | Audit variables and unrounded `*_raw` fields added to `plan_result` and to the fallback path; stage ④ key `clarification_detected_by_plan` |
| 4 | `simulation_core.py` | schema v2.0 constants + 7 pure functions; runtime audit collection (8b/8c), injection-receipt capture, record construction via `build_agent_record()`, per-tick total backfill, 6 new return keys |
| 5 | `run_experiments.py` | 60-field schema assertion, 5 new output artifacts, run-level network consistency verification with refusal path, per-experiment timing/router instrumentation, git dirty flag |

No other production file, test file, fixture, or config file was modified.

## agent_records schema v2.0 — 60 unique fields

Single source of truth: `simulation_core.AGENT_RECORDS_FIELDS`, asserted at import
time for both count and uniqueness, asserted again in `write_agent_records_csv`, and
verified against the actually written CSV header by the acceptance test.

**60 = 21 v1.0-compatible + 39 new audit fields.**

| Group | Count | Fields |
|---|---|---|
| Identity & schema | 6 | `schema_version`, `exp_id`, `tick`, `agent_id`, `cluster_type`, `social_role` |
| Experiment factors | 4 | `content_factor`, `channel_factor`, `timing_factor`, `clarification_tick_config` |
| v1.0 trust chain | 7 | `trust_score`, `baseline_trust`, `trust_after_decay`, `affective_change`, `shock_anchor`, `quiet_ticks`, `decay_lambda` |
| High-precision trust audit | 13 | `previous_trust_raw`, `baseline_trust_raw`, `trust_after_decay_raw`, `affective_change_raw`, `trust_score_raw`, `shock_anchor_before_raw`, `shock_anchor_after_raw`, `decay_rate_raw`, `sensitivity_multiplier`, `trust_clipped_at_bound`, `anchor_update_branch`, `clr_anchor_lift_ratio`, `clr_lift_raw` |
| System 1 / Reflect audit | 7 | `raw_affective_output`, `trust_change_affective_used`, `affective_was_clipped`, `reflect_primary_source`, `reflect_message_sources`, `observation_count`, `observation_sources` |
| Behavioral decision | 5 | `is_buying`, `is_posting`, `post_content`, `plan_reason`, `plan_fallback_used` |
| Cognitive output | 3 | `hypocrisy_perceived`, `importance`, `reasoning` |
| Global event + clarification audit | 10 | `has_global_event`, `global_event_scheduled`, `global_event_received`, `has_clarification`, `is_clarification_target`, `clarification_injected`, `clarification_received`, `clarification_detected_by_plan`, `clarification_content_type`, `is_quiet_day` |
| Network & tick totals | 5 | `out_degree`, `in_degree`, `tick_posts_total`, `tick_buys_total`, `cumulative_buyers` |

Precision policy: v1.0 columns keep `round(x, 4)` exactly as before; audit columns use
`round(x, 12)` for high-precision recomputation, sourced from **unrounded** floats held
in `plan_result`. The 12-decimal CSV representation is **not** claimed to be a lossless
float64 round-trip — behavior invariance does not depend on it (see below).
Values that do not apply are written as `""`, never as `0`.

`trust_after_decay` appears exactly once; the high-precision variant is a
differently-named column `trust_after_decay_raw`. This is the structural fix for the
original duplicate-column defect.

## v1.0 compatibility

All 21 v1.0 columns are retained with unchanged names, unchanged values and unchanged
precision. Their **relative order is preserved** — positions in v2.0 are
2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16, 17, 38, 39, 40, 43, 44, 45, 46, 49, 60
(strictly increasing), so any analysis script reading by column name works unchanged.

Scripts reading by positional index must be updated, since new columns are interleaved.
The audited consumers (`analysis/plot_experiments.py`, `analysis/plot_trajectories.py`,
`analysis/analyze.py`, `analysis/plot_trial.py`) read `summary.csv` / `trajectories.csv`
or read by column name, so they are unaffected.

Two renames were made **before any v2.0 data was ever written**, so they carry no
compatibility debt: `is_target_node` → `is_clarification_target`, and
`has_clarification_observed` → `clarification_detected_by_plan`. Both old names are
asserted absent by the acceptance test.

`has_global_event` is kept as a v1.0 alias of `global_event_scheduled` and marked
deprecated (planned removal in schema v3.0).

## Clarification four-stage evidence chain

Four independent columns, each answering a different question from a single legitimate
source. None may substitute for another:

| Stage | Field | Question | Only legal source |
|---|---|---|---|
| ① selected | `is_clarification_target` | Was this Agent chosen as a delivery target? | `injector.target_nodes` |
| ② written | `clarification_injected` | Did the injector actually write into its inbox this tick? | `injector.last_injected_ids` (receipt) |
| ③ received | `clarification_received` | Did this Agent actually observe the clarification? | recorder reads `last_observations` |
| ④ detected | `clarification_detected_by_plan` | Did the Plan layer actually recognise it and branch on it? | `plan_result` |

Diagnosable breaks this makes visible: ①T②F = injector never fired that tick;
②T③F = message entered the inbox but never reached the observation stream (inbox
throttling / perceive filtering); ③T④F = Agent received it but Plan failed to classify
it. `has_clarification` is retained separately as the **config-level claim**
("configuration says a clarification is injected this tick"), forming a
claim-versus-fact pair with the four stages.

The receipt is read as `injector.last_injected_ids` directly rather than through a
`getattr` fallback: if the receipt attribute were ever missing, the run must fail loudly
instead of silently degrading to "nobody was injected this tick", which would set stage
② to False everywhere while still passing.

Acceptance evidence: five deliberately inconsistent stage combinations
`(T,T,T,T)`, `(T,F,F,F)`, `(T,T,F,F)`, `(T,T,T,F)`, `(F,F,T,T)` are all reachable,
which is only possible if no field is derived from another.

## Global event: scheduled vs received

- `global_event_scheduled` — whether the **runtime** event timeline schedules an event
  this tick (a scheduling fact).
- `global_event_received` — whether `source == "Global News"` actually appears in that
  Agent's `last_observations`.

Deriving `received` from `tick in ENTERPRISE_STRATEGY` is forbidden: scheduling does not
prove delivery, since inbox throttling and perceive filtering can truncate it. Two
counterexamples are asserted: an event tick where the Agent observed nothing
(`scheduled=True, received=False`), and a quiet tick where the Agent did observe
Global News (`scheduled=False, received=True`).

`_observed_source_present()` takes an **observation list**, not `state_data`, so the
decision of *which snapshot to read* can only be made at the single call site inside
`build_agent_record`. There is no `observations` fallback: `observations` is the
perceive-side accumulator and may hold cross-tick residue, which would repaint "not
observed this tick" as "observed". `observation_count`, `observation_sources`,
`clarification_received` and `global_event_received` all reuse one `last_observations`
snapshot taken once, so a record with `observation_count = 0` but
`clarification_received = True` is structurally impossible.

## Run-level network consistency verification

`network_nodes.csv` and `network_edges.csv` describe **topology**, which is fully
determined by `(num_agents, random_seed)`. All 12 configurations use `(20, 42)`, so
writing the same graph 12 times would be pure redundancy and would invite meaningless
`exp_id`-grouped aggregation. They are therefore **run-level static files** with no
`exp_id` column, and no `is_clarification_target` column — target identity varies per
experiment, so keeping it in a run-level file would let 12 different target sets
overwrite each other with the result decided by write order.

That "one network per run" premise is **verified, not assumed**.
`verify_single_network()` groups all successful experiments by `network_hash`, then
re-compares node and edge rows line by line (the hash covers topology only, while the
node table also carries `cluster_type` / `social_role`). `source_exp_id` is the
lexicographically smallest successful `exp_id`, making the choice of representative
deterministic.

Failure behaviour is fail-closed: on `inconsistent` or `unavailable`, **neither CSV is
written — not even a header** (an empty header file would be read downstream as "the
network is empty"), `network_inconsistency_report.json` is written with `hash_groups`,
per-experiment `random_seed` / `num_agents` / `network_type` / `network_params` and a
remedy note, the condition is appended to `errors.log`, `run_metadata.network_consistency`
records the verdict, and the process exits with code **3** — after all other artifacts
and figures have been safely written, so an audit-contract violation never destroys
experiment evidence. When `verify_single_network()` is not called at all, the metadata
records `not_verified`, never `consistent`.

`network_hash` covers sorted nodes **and** sorted edges, so adding an isolated node
changes the fingerprint; hashing edges alone would miss it.

## Output artifacts (six regular products)

| Artifact | Content | Granularity | Row carries `exp_id`? |
|---|---|---|---|
| `agent_records.csv` | 60-column auditable evidence chain | experiment: Agent × Tick | yes |
| `target_nodes.csv` | target identity + factors + `selection_metric` / `metric_value` / `rank` | experiment: Agent (targets only) | yes |
| `experiment_metadata.jsonl` | 18 fields: factors, seed, budget, target nodes, network fingerprint, effective timeline, timing, router/cache counters, status | experiment: one line per `exp_id` | yes |
| `network_nodes.csv` | 5 columns: `agent_id`, `cluster_type`, `social_role`, `out_degree`, `in_degree` | **run-level: one copy** | no |
| `network_edges.csv` | 3 columns: `source_agent_id`, `target_agent_id`, `is_directed` | **run-level: one copy** | no |
| `run_metadata.json` | source/prompt/persona hashes, LLM sampling params, git (incl. `is_dirty`), network consistency verdict, effective event timelines | run-level | — |

A seventh file, `network_inconsistency_report.json`, appears **only** when the
run-level network premise is falsified. All artifacts are mirrored into `latest/`
behind an existence guard, so a refused file stays missing rather than becoming an
empty placeholder.

`target_nodes.csv` is the single home for target identity and selection rationale.
For the `random` channel, `selection_metric = "random_sample"`, `metric_value = ""`
and `rank = ""` — `0` is forbidden there because it cannot be distinguished from a
node whose out-degree genuinely is 0.

`experiment_metadata.jsonl` records `started_at` / `finished_at` (timestamps taken
outside `_run_with_patch`, so they never enter the simulation), `router_role`,
`recording_cache_size` (recording group = produced size, replay group = consumed size)
and `replay_miss_count` (`""` for the recording group where it does not apply, so it
stays distinguishable from `0` = "replayed with zero misses"). Failed experiments also
carry `config.to_dict()`, so a failing run still records which factor combination,
seed and budget produced it — the very information needed to reproduce it.

## effective_event_timeline source

`ENTERPRISE_STRATEGY` is patched in place by `run_experiments._run_with_patch` to keep
only the Tick 5 scandal. The timeline is therefore snapshotted **inside
`run_simulation_core` at runtime**, while the patch is active, and returned with the
result. `run_metadata.json` only ever reads it back from the result.

The previous `"global_event_ticks": sorted(ENTERPRISE_STRATEGY.keys())` line was
removed: rebuilding the timeline after the run finished could not reflect the actual
patch and was coupled to patch-restore ordering. Failed experiments record `[]` plus an
explicit source note, never a fallback to the constant. The acceptance test asserts the
key is absent and that the recorded timeline is `[5]` — i.e. *not* the 4 ticks of the
unpatched constant.

## Acceptance results

```
EXITCODE = 0
Total    = 270
Passed   = 268
Failed   = 0
Warned   = 2
ALL ACCEPTANCE CRITERIA PASSED
```

Evidence directory: `results/task002_validation/20260801_101156/`
(`task002_verdicts.json`, `behavior_diff.csv`, `validation.log`)

Coverage: T1 syntax, T2 no duplicate fieldnames, T3 60 unique fields and v1.0 order,
T4 record field set and single-snapshot consistency, T5 precision, T6 run metadata,
T7 network branch fidelity, T8 hash sensitivity, T9 target-node semantics,
T10 behavior invariance, T11 clarification content type, T12 import hygiene,
T13 stage independence, T14 injection receipt, T15 run-level network artifacts and
18-field metadata, T16 effective timeline, T17 fixture provenance and harness lock.

## Behavior invariance

12 traces (3 scenarios × 4 cluster types), 100 tick snapshots, **500 per-field
comparison points**, zero tolerance, all equal. `behavior_diff.csv` contains only its
header.

The comparison reads **unrounded runtime state** (`state_data["trust_score"]`,
`state_data["shock_anchor"]`, `plan_result[...]` in memory) and compares with `==`.
It never passes through CSV serialization and does not depend on any decimal-rounding
convention. Fixture and current run use the same collection function, so both sides
are collected identically.

Unchanged mechanisms, confirmed by the invariance result: Agent execution order;
Perceive → Reflect → Plan → Invoke ordering; clarification injection timing; graph
construction and node selection; the trust update formula; `shock_anchor` branch
conditions; `quiet_ticks` logic; random number call count and ordering.

## Constraints honoured

- **No real LLM was invoked.** The acceptance test uses a deterministic mock router
  keyed on stable prompt markers, performs no network access, and disables
  `sentence_transformers` before importing plugins so the existing `ImportError`
  fallback in `MemoryManager` is taken and no SBERT model is loaded.
- **No prompt, persona, formula, parameter, experiment matrix or metric definition was
  modified.** Verified by `git diff --name-only`: only the 5 production files appear.
  `GreenCognitionPlugin.py`, `GreenPerceivePlugin.py`, `GreenInvokePlugin.py`,
  `experiment_config.py`, `node_selector.py`, `metrics_calculator.py`,
  `generate_data.py` and `configs/models_config.yaml` are untouched.
- `configs/models_config.yaml` has no `top_p` key, so the metadata records
  `"unknown"` rather than assuming `1.0`. `api_key` is never written to any artifact;
  only `api_key_present` is recorded.

## Two WARN items (neither affects the verdict)

1. **Fixture production-file hashes are provenance-only.**
   `baseline_file_sha256` records the pre-TASK_002 hashes of
   `ConsumerPlanPlugin.py`, `GreenCognitionPlugin.py` and `GreenInvokePlugin.py`.
   `ConsumerPlanPlugin.py` **is expected to change** — the diff modifies it. The test
   therefore only asserts the entries exist and are 64-hex, writes the current hashes
   into `task002_verdicts.json` for manual tracing, and does **not** require equality.
   This is the opposite judgement direction from `test_harness_sha256`, which must match
   exactly: the production files are the subject under test (change = working as
   intended), while the harness is the input definition (change = the experiment
   condition was swapped).

2. **Pre-existing unused imports in `simulation_core.py`.**
   `asyncio` and `networkx as nx` have no usage site, and `generate_data` re-exports
   four symbols kept only for reference. These are **pre-existing** and unrelated to
   TASK_002. Removing them would widen the diff and add behavior risk for no
   observability gain, so they are recorded as WARN and left for a separate cleanup
   task. TASK_002 itself added only imports that are genuinely used
   (`simulation_core`: `hashlib`; `run_experiments`: `hashlib`, `json`, `platform`,
   `subprocess`) and introduced no `time` import — all timestamps use `datetime`.

## Conclusion

**TASK_002 PASSED.** `agent_records` schema v2.0 (60 unique fields) is in place, the
clarification four-stage chain and the global-event scheduled/received split are
recorded independently from their real sources, the run-level network premise is
verified rather than assumed, and behavior invariance is proven against a committed
pre-implementation baseline with 500 zero-tolerance comparison points.

Thesis impact: chapters 5–6 must be regenerated from a v2.0 run; historical 21-column
outputs remain valid as v1.0 data and can be distinguished by the absence of the
`schema_version` column.

## Next steps

1. Commit the 5 production files together with this result document.
2. Run one full 12-experiment end-to-end pass (criterion A4) to confirm the six
   artifacts, the 60-column header, the 12-line metadata file and `latest/`
   synchronisation, and that exit code is 0 with no inconsistency report.
3. Optionally clean up the pre-existing unused imports as a separate task.

## Commit

- SHA: (to be filled after git commit)
- Message: `feat(observability): add agent_records schema v2.0 audit trail`
