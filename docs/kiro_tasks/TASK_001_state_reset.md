# TASK_001 — Fix transient cognitive-state persistence

## Status

Pending local inspection and implementation by Kiro.

## Background

The phase-2 audit found that when a Tick has no new observations, the Reflect layer
sets only `trust_change_affective = 0.0` and returns. It may leave
`last_observations` and `latest_thought` from an earlier Tick.

The Plan layer uses `last_observations` to detect clarification and uses
`latest_thought` in the behavior-decision prompt. This can cause an old
clarification to be treated as a current clarification for multiple later Ticks.

Read before editing:

- `docs/audit/phase1_model_consistency_audit.md`
- `docs/audit/phase2_state_residue_diagnosis.md`
- `handoff/state_reset_v1/README.md`
- `handoff/state_reset_v1/plugins/agent/reflect/GreenCognitionPlugin.py`

## Objective

Correct the lifecycle of transient Reflect state without changing substantive
behavioral mechanisms.

## Required workflow

1. Locate the repository's actual `GreenCognitionPlugin.py`.
2. Compare it with the proposed patch. Do not overwrite the file blindly.
3. On a no-observation Tick, reset at least:
   - `trust_change_affective = 0.0`
   - `raw_affective_output = 0.0`
   - `affective_was_clipped = False`
   - `latest_thought = None`
   - `last_observations = []`
   - `reflect_primary_source = "None"`
   - `reflect_message_sources = []`
4. Check every downstream reader of these fields.
5. Add or retain enough logging to verify current-Tick state.
6. Run a syntax/import check.
7. Run one no-clarification condition, one immediate condition, and one delayed condition.
8. Record results in `docs/decisions/model_change_log.md`.

## Prohibited changes in this task

Do not change:

- trust recovery formula;
- `shock_anchor` mechanism;
- type sensitivity coefficients;
- clarification anchor-lift ratios;
- Reflect Prompt content;
- LLM output scale;
- network construction;
- content/channel/timing experiment design;
- metric definitions.

## Acceptance criteria

For a directly targeted Agent:

1. Clarification Tick: `quiet_ticks == 0`.
2. Next Tick with no new information: `quiet_ticks == 1`.
3. Later quiet Ticks increment normally.
4. Empty-observation Tick has:
   - `last_observations == []`;
   - `latest_thought is None`;
   - `trust_change_affective == 0.0`.
5. Clarification is not repeatedly detected on later Ticks.
6. Existing Plan and Invoke stages still execute.
7. No JSON parsing or import regression is introduced.

## Deliverables

Kiro should provide:

- files changed;
- unified diff;
- test/run commands;
- acceptance evidence;
- unresolved risks;
- suggested commit message.

Suggested commit:

`fix(reflect): reset transient cognition state on empty observations`
