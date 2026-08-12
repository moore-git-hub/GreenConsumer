# TASK_005 Stage I.5C-3E — Formal valid-block target freeze

## Frozen decision

- Formal valid-block target: **N = 24**
- Candidate grid: 12 / 16 / 20 / 24 / 30 / 40
- Decision rule: smallest candidate passing all frozen Stage I.5C-2 hard gates
- Stage I.5C-3D diagnostic selection: **24**
- N=40 feasibility decision: not required
- Engineering blocks P001–P005: excluded from the formal sample
- Therefore, the formal study requires **24 new valid formal replication blocks**; failed/invalid attempts do not count toward this target.

## Evidence anchors

- Stage I.5C-3D evidence ZIP SHA256: `35C07EF4C75C31639B90514CAA9D0719E2DBD7B600337758F5297296A3AA5BD5`
- `oc_summary.json` SHA256: `0153DE41E50D884FB086F28141A35A1C22E56D222E4428AD567EEC36356F6E5B`
- Execution HEAD: `cabac740b68c1da11cbd2fa212b631bfc83706e4`

## Confirmatory scope

The formal confirmatory scope contains exactly two primary metrics:

1. `final_trust_gain_vs_control`
2. `post_scandal_auc_gain_vs_control`

This yields 28 confirmatory estimands split into:

- `strategy_primary_16`
- `factorial_confirmatory_12`

`local_trust_effect_did_3` remains exploratory/mechanistic. It is excluded from formal sample sizing, confirmatory Holm adjustment, and confirmatory significance claims.

## Interpretation boundary

The `d = 0.80` OC scenario is a standardized design-sensitivity benchmark, not a substantive SESOI. The OC result supports the operating-characteristic adequacy of N=24 under the frozen simulation design; it is not substantive evidence that the real intervention effect equals d=0.80 or any other simulated effect.

## Launch gate

Freezing N=24 does **not** authorize formal LLM execution. Before formal launch:

- production `replication_analysis.py` must be updated and reviewed so confirmatory inference uses the amended 16/12 Holm families;
- `local_trust_effect_did_3` must be excluded from confirmatory Holm/inference;
- a formal launch contract and formal block/seed identity contract must be frozen;
- engineering P001–P005 must not be reused as formal blocks.

Current state:

- `formal_target_n_frozen = true`
- `formal_valid_block_target_n = 24`
- `formal_llm_launch_permitted = false`
- `formal_inference_permitted_with_current_replication_analysis_py = false`
