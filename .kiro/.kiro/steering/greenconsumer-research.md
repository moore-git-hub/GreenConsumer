---
inclusion: always
---

# GreenConsumer research and code collaboration rules

This workspace is a master's thesis GABM project about consumer trust recovery after greenwashing scandals.

## Sources of truth

Use the following priority order:

1. Current repository code: actual implementation facts.
2. Raw experiment outputs: actual run results.
3. Audit reports: identified defects, validity limits, and required checks.
4. Thesis text: intended theoretical explanation.
5. Literature evidence: justification and boundary conditions.

Do not silently reconcile contradictions. Report them before changing code.

## Mandatory references

#[[file:docs/audit/phase1_model_consistency_audit.md]]
#[[file:docs/audit/phase2_state_residue_diagnosis.md]]
#[[file:docs/kiro_tasks/TASK_001_state_reset.md]]
#[[file:docs/decisions/model_change_log.md]]

## Core constraints

- Use the term GABM consistently.
- Do not force clarification responses to be positive.
- Do not add a directional positive floor to LLM outputs.
- Persona describes who the agent is, not what event occurred.
- Events must enter through incoming_messages.
- Do not alter trust formulas, sensitivity coefficients, anchor-lift ratios,
  network topology, prompts, or experiment factors in the same commit as a bug fix
  unless the task explicitly requires it.
- Every code change must include:
  - reason,
  - affected files,
  - validation command,
  - observed result,
  - thesis chapters affected.
- Old experiment figures are development evidence only until the state-residue bug
  is fixed and experiments are rerun.

## Current active task

Execute TASK_001 only. First inspect the actual local files and compare them with
the proposed patch. Do not overwrite blindly. Produce a diff, run the minimum
acceptance experiment, and update the model change log.
