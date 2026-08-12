# Kiro Handoff — Phase 1 and Phase 2

> Historical handoff only. For the current TASK_005 formal-v2 state and release
> boundary, use `GABM_HANDOFF.md`. This file must not be treated as the active
> execution instruction.

## Purpose

This package aligns two completed audits with the local GreenConsumer repository:

- Phase 1: model consistency and experiment-validity audit.
- Phase 2: transient state-residue diagnosis and proposed patch.

The package does not automatically overwrite production code.

## Contents

```text
.kiro/steering/greenconsumer-research.md
docs/audit/phase1_model_consistency_audit.md
docs/audit/phase2_state_residue_diagnosis.md
docs/kiro_tasks/TASK_001_state_reset.md
docs/decisions/model_change_log.md
handoff/state_reset_v1/
```

## Required order

1. Commit or stash existing local work.
2. Create branch `audit/state-reset-v1`.
3. Copy this package into the repository root.
4. Open the repository root in Kiro.
5. Confirm that `.kiro/steering/greenconsumer-research.md` is loaded.
6. Ask Kiro to read `TASK_001_state_reset.md` and inspect actual local code.
7. Require Kiro to show a diff before applying changes.
8. Run the minimum acceptance experiments.
9. Update the model change log.
10. Commit only after acceptance criteria pass.

## One-time Kiro prompt

```text
Read the workspace steering file and these documents first:

#docs/audit/phase1_model_consistency_audit.md
#docs/audit/phase2_state_residue_diagnosis.md
#docs/kiro_tasks/TASK_001_state_reset.md
#docs/decisions/model_change_log.md

Then inspect the actual repository implementation of GreenCognitionPlugin,
ConsumerPlanPlugin, Perceive, and the experiment runner.

Execute TASK_001 only. Do not overwrite from the handoff patch blindly.
First compare the proposed patch with current local code, explain the exact
root cause, list files to change, and show the planned diff. Do not change
the trust formula, prompts, parameters, network, factors, or metrics in this
task. After implementation, run the minimum acceptance checks and update
the model change log with commands and observed results.
```

## Git workflow

```powershell
git status
git switch -c audit/state-reset-v1
git add .kiro docs handoff
git commit -m "docs(audit): add phase 1 and phase 2 Kiro handoff"
```

Apply the code fix in a second commit:

```powershell
git add <changed-code-files> docs/decisions/model_change_log.md
git commit -m "fix(reflect): reset transient cognition state on empty observations"
```

Keeping documentation and behavior changes in separate commits makes review and rollback easier.
