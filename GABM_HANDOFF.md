# GABM current handoff

## Current decision

TASK_005 formal-v2 is **paused and not released for execution**. A post-pilot
construct audit found that its P5 endpoint is not a defensible causal purchase
measure: it includes pre-treatment purchases, repeatedly trials purchase on
every Tick, uses an absorbing first-purchase state in an existing-customer FMCG
scenario, and reaches a high control ceiling. Formal-v2 remains unexecuted.

A parallel purchase-demand v3.1 contract was frozen before replay and has passed
its offline structural gates. It separates condition-invariant category
opportunities, conditional brand choice, loyalty state, micro-buyer
heterogeneity and a separately crossed conversion-support/PBC factor. It is not
promoted into the active mechanism-v2 path and does not authorize a new real-LLM
pilot.

The user selected option A (FMCG repeat choice). A subsequent alignment audit
found that the old variance-v3 LLM stimuli describe generic fictional
"VerdantCo everyday products", not plant-based milk, and the old personas omit
category frequency and brand-relationship state. Therefore the replay is
structural debugging evidence only. Scenario 3.2 now freezes one consistent,
wholly fictional plant-based-milk case (VerdantCo Oat) before any new LLM output.

Scenario 3.2 is now implemented on a versioned parallel path. It supplies the
product-aligned profiles and stimuli, a strict peer-approval semantic schema,
SN updates based only on actual social observations, a retired legacy purchase
endpoint, a persona-aligned repeat-choice layer, PBC-only conversion support,
opportunity-level audit fields and both pure-offline and AgentKernel 9 x 2 fake
smoke entry points. The deterministic offline smoke passed all 16 frozen gates.
The AgentKernel smoke could not run in the current Linux container because both
`networkx` and `agentkernel_standalone` are absent; it remains a required gate in
the frozen Windows environment.

The completed 10-block real-LLM variance pilot has now also passed a descriptive
visual face-validity review with strict scope locks. This review added no model
calls and does not authorize formal execution.

```text
TASK_005_ENVIRONMENT_BASELINE=FINAL_FROZEN_WITH_DISCLOSED_RESIDUE
SCOPE=PROSPECTIVE_TASK005_FORMAL_V2_ONLY
SOURCE_BRANCH=redesign/task005-mechanism-v2
SOURCE_HEAD=e9926ebfbc25d06ccbaaac895a3b32a1f8eaa54e
AGENTKERNEL_RELEASE=agentkernel-standalone==1.1.0
FORMAL_V2_BATCH_ID=task005-formal-v2
FORMAL_V2_ATTEMPT_BLOCKS=46
FORMAL_V2_MASTER_SEED=2026081101
FORMAL_V2_EXECUTED=false
FORMAL_V2_AUTHORIZED=false
REAL_LLM_CALLS_DURING_RELEASE_REVIEW=0
VISUAL_ACCEPTANCE_SOURCE=task005-real-variance-pilot-v3
VISUAL_ACCEPTANCE=PASS_WITH_SCOPE_LOCK
REAL_LLM_CALLS_DURING_VISUAL_REVIEW=0
P4_CLAIM_SCOPE=REACH_ONLY
P5_PREVIEW=LOW_RESPONSE_NOT_A_RETUNING_TARGET
PURCHASE_V2_ENDPOINT=RETIRED_AS_CAUSAL_PURCHASE_ESTIMAND
PURCHASE_V31_STAGE=STRUCTURAL_REPLAY_PASS_SCENARIO_VALIDITY_NOT_ESTABLISHED
PURCHASE_V3_REAL_LLM_CALLS=0
FINAL_PRODUCT_SCENARIO=FICTIONAL_FMCG_PLANT_BASED_MILK_V32
FORMAL_V2_DISPOSITION=DO_NOT_EXECUTE_WHILE_V32_REDESIGN_IS_ACTIVE
SCENARIO_V32_REAL_LLM_AUTHORIZED=false
SCENARIO_V32_IMPLEMENTATION=COMPLETE_PARALLEL_PATH
SCENARIO_V32_OFFLINE_SMOKE=PASS_16_OF_16
SCENARIO_V32_KERNEL_SMOKE=BLOCKED_MISSING_DEPENDENCIES
SCENARIO_V32_COGNITIVE_ROWS=5400
SCENARIO_V32_DEMAND_OPPORTUNITY_ROWS=28782
SCENARIO_V32_FAKE_SEMANTIC_CALLS=489
SCENARIO_V32_REAL_LLM_CALLS=0
```

The authoritative preauthorization verdict is
`.kiro/specs/task005-replication-inference/formal_v2_preauthorization_review1.0.json`.

## What has passed

- The managerially defined MDEs were frozen before reading variance-pilot
  effects.
- The official variance source is `task005-real-variance-pilot-v3` with 10/10
  passing blocks.
- Prospective power requires N values of 5, 6, 11, 46 and 8 for P1-P5;
  `P4_CHANNEL_REACH` determines the exact N=46 design.
- The five-estimand Holm operating-characteristic simulation has empirical
  global-null FWER 0.04588.
- The 46-row formal-v2 seed ledger reconstructs exactly and has zero collisions
  against 120 checked pilot seed records.
- The prospective environment is frozen at Python 3.12.12 and
  `agentkernel-standalone==1.1.0`; the runtime package matches the official
  v1.1.0 wheel.
- The v3 trajectories are exactly aligned before treatment, show the crisis at
  Tick 5 and the intended Immediate/Delayed onsets at Tick 6/Tick 10, remain
  within bounds, and are non-degenerate. The visual checkpoint is recorded in
  `task005_visual_acceptance_result1.0.json`.
- Purchase-demand v3.1 passes all structural gates: condition-invariant
  opportunity schedules, exact pre-treatment alignment, crisis-direction check,
  no-effect collapse, no direct communication-to-PBC path and zero added LLM
  calls.
- The standardised demand display increases post-crisis choice occasions from a
  mean 71.7 to 1,601.3 per condition, reducing realised-curve granularity from
  1.395 to 0.062 percentage points without changing expected communication
  effects.
- In the uncalibrated reference replay, average communication-only uplift is
  6.72 choices per 1,000 occasions; the conversion-support reference effect is
  38.31 per 1,000 and varies materially across frozen sensitivity settings. No
  p-values or formal claims are permitted.
- Scenario-v3.2 pure unit tests pass 34/34. The deterministic 9 x 2 smoke passes
  16/16 structural gates with nine cognitive conditions, eighteen demand
  conditions, 5,400 cognitive rows and 28,782 audited purchase opportunities.
- The scenario-v3.2 output is byte-reproducible on a full rerun; an independent
  CSV reconstruction matches all eighteen condition summaries and all declared
  output hashes.
- The active v2 files (`simulation_core.py`, `mechanism_v2.py`, the old
  clarification injector and old cognition/plan plugins) have no diff against
  HEAD. All scenario-v3.2 changes remain parallel and version-scoped.

## Visual-review scope locks

- The review is descriptive only: no p-values, formal inference, winner
  selection, or change to the frozen MDEs, N=46 or P1-P5 family.
- P5 shows low purchase response in the pilot. A future null or weak result must
  be reported rather than tuned away.
- P4 establishes channel reach only; the pilot does not justify claiming that
  Hub placement improves trust or purchase conversion.
- Both content conditions have a saturated hypocrisy flag in the manipulation
  pilot, so the current design cannot identify differential hypocrisy mediation.

## Why execution remains blocked

1. P5's cumulative first-purchase construct is invalid for the selected FMCG
   repeat-choice scenario. Formal-v2 must not be executed and later patched.
2. The old effective stimuli are generic VerdantCo messages rather than a
   product-aligned FMCG case; old trajectories cannot validate scenario-v3.2
   purchase effects.
3. `task005_formal_design2.0.json` records the Windows CRLF digest of the seed
   ledger, while the Git-normalized file uses LF. The content is unchanged, but
   the byte-hash contract is not cross-platform.
4. `run_formal_launch.py` and `run_formal_replications.py` still implement the
   superseded formal-v1 cohort: N=24, seed 2026080801.
5. `replication_analysis.py` still implements the legacy strategy/factorial
   families, not the frozen P1-P5 confirmatory family.
6. The active regression manifest is still scoped to variance-v2 readiness and
   does not certify a formal-v2 launcher or P1-P5 analyser.
7. The legacy launcher requires a superseded branch and its old authorization
   cannot be reused.
8. Scenario-v3.2's pure offline gate has passed, but its actual AgentKernel
   lifecycle gate has not executed in this container: `networkx` and
   `agentkernel_standalone` are missing. The 34 scenario/purchase unit tests pass;
   full TASK_005 discovery starts 42 tests, with 31 passing and 11 import errors
   caused by those missing dependencies. No assertion failure was observed.

The line-ending incident is recorded in
`.kiro/specs/task005-replication-inference/formal_design2.0_line_ending_incident1.0.json`.

## Next implementation task

Run `run_task005_fmcg_kernel_fake_smoke_v32.py` in the frozen Windows Kernel
environment with `networkx` and `agentkernel-standalone==1.1.0`. The script is
hard-wired to the deterministic fake router and cannot make a real LLM call. It
must produce a 9 x 2 PASS and the full Windows regression suite must pass before
any real-LLM step.

Only after those gates pass should a new version-specific engineering-pilot
contract be drafted. That later contract must freeze independent seeds, call and
cost ceilings, stop rules, semantic schema, manipulation checks, output hashes
and a small visual acceptance set. It then requires new human authorization;
no v1/v2/v3 or formal authorization may be reused.

The construct diagnosis is recorded in
`.kiro/specs/task005-replication-inference/task005_purchase_construct_diagnosis1.0.json`.
The v3.1 structural replay is recorded in
`task005_purchase_demand_v31_replay1.0.json`. The scenario mismatch is recorded
in `fmcg_scenario_alignment_review1.0.json`, and the new boundary is frozen in
`fmcg_scenario_contract3.2.{md,json}`. Runtime assumptions and offline gates are
frozen in `fmcg_runtime_contract3.2.1.{md,json}`; implementation state is in
`task005_fmcg_v32_implementation_checkpoint1.0.json`. All new code remains
parallel to the active production path.

No real LLM call may be made until the scenario is fixed, the corresponding
production mechanism and analysis are frozen, Windows-Kernel regression tests
pass, and a new version-specific human authorization exists. All earlier formal
authorizations are non-reusable.

## Historical boundary

`KIRO_HANDOFF.md` describes the earlier Phase 1/Phase 2 state-reset handoff and
is retained as historical evidence. It is not the current TASK_005 execution
instruction.
