# TASK_005 Stage I.5C-4A — Production analysis scope update contract

This stage freezes the production-analysis behavior required **before** editing
`replication_analysis.py`.

## Required post-update scope

- Analysis schema: `1.1`
- Formal valid-block target: `N = 24`
- Confirmatory primary metrics:
  - `final_trust_gain_vs_control`
  - `post_scandal_auc_gain_vs_control`
- Exploratory mechanism metric:
  - `local_trust_effect_did_3`
- Confirmatory Holm families:
  - `strategy_primary_16`
  - `factorial_confirmatory_12`
- Exploratory three-way Holm family:
  - `factorial_three_way_2`
- `local_trust_effect_did_3` receives point summaries and Student-t CIs but no raw
  p-value and no Holm-adjusted p-value.
- P001–P005 are forbidden as formal block IDs.
- Pareto/ranking remain exploratory secondary summaries and use only the two
  confirmatory metrics; local DID cannot drive a composite strategy rank.

## Formal launch status

Freezing this contract does not authorize formal execution.

- `formal_target_n_frozen = true`
- `formal_valid_block_target_n = 24`
- `production_analysis_updated = false`
- `formal_llm_launch_permitted = false`
