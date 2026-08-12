# TASK_005 FMCG Scenario 3.2.1 Offline Runtime Contract

**Status:** frozen before any scenario-3.2 runtime output.

This contract implements, but does not replace, `fmcg_scenario_contract3.2`.
It authorises one deterministic fake-model smoke test and no real LLM call.

## Matrix and seed

- Cognitive matrix: the existing eight communication conditions plus one common
  no-clarification control.
- Demand cross: conversion support absent versus present for every cognitive
  condition, producing 9 x 2 = 18 demand conditions.
- Conversion support is evaluated offline from the same cognitive trajectory;
  it cannot duplicate or alter semantic-model calls.
- Diagnostic seed: `53201`.
- Cognitive agents: 20 frozen engineering personas.
- Demand buyers: 25 deterministic micro-buyers per cognitive persona (500 in
  total), used for event resolution rather than as independent replications.
- Horizon: 30 Ticks; crisis at Tick 5; conversion support active at Tick 6--19.

## Persona-to-demand mapping

The following ordinal codings are engineering assumptions, not estimates.

- Purchase-frequency strata use integer intervals within their stated ranges:
  5--7, 7--10, 10--14 and 14--28 days.
- Prior focal-brand relationship sets the conditional-choice preference centre
  to `+0.65` (loyal), `0` (repertoire) or `-0.65` (non-user).
- The corresponding loyalty latent centre is `+1.10`, `0` or `-1.10`.
- Low/medium/high price sensitivity contributes `+0.25/0/-0.25` on the baseline
  PBC logit scale.
- Low/medium/high availability friction contributes `+0.25/0/-0.25` on the same
  scale.
- Within-persona heterogeneity and all remaining demand coefficients retain the
  prospectively specified v3.1 reference values and sensitivity obligation.

These magnitudes cannot support population prevalence or market-share claims.

## Runtime separation

- Scenario profiles, Tick-5 crisis, clarification templates, semantic plugin and
  plan plugin are injected only inside a versioned context and restored after
  each run.
- The active mechanism-v2 path and historical outputs remain unchanged.
- Subjective norm may update only when an actual social-feed observation has a
  valid `perceived_peer_approval` value. News and enterprise statements alone
  must leave SN unchanged.
- The AgentKernel plan records no purchase. Repeat focal-brand choice is computed
  by the downstream demand layer only.
- Conversion support may change current PBC only. Trust, Att, SN, opportunity
  timing and semantic calls are inherited unchanged from the paired absent arm.

## Required audit outputs

- one cognitive mechanism row per agent per Tick, including peer approval and
  SN before/after;
- one demand audit row per realised category-purchase opportunity, including
  persona fields, PBC, intention, choice probability/draw, loyalty before/after
  and realised choice;
- one Tick-level curve row for every one of the 18 demand conditions;
- one machine-readable gate report with file hashes.

## Acceptance gates

1. Exactly nine cognitive and eighteen demand conditions are present.
2. All cognitive conditions contain 600 unique agent-Tick rows with no semantic
   or plan fallback.
3. The effective event timeline contains only the fictional VerdantCo Oat crisis
   at Tick 5, and every profile is product-aligned.
4. Peer approval is null without social observations and numeric in `[0,1]`
   with social observations; SN changes only in the latter case.
5. The legacy cumulative-purchase endpoint is retired and remains zero.
6. The category-opportunity schedule and random choice draws are condition
   invariant; all 18 conditions align exactly before Tick 5.
7. Conversion support changes demand PBC only within Tick 6--19 and does not
   alter cognitive trust, Att or SN.
8. Repeat choices occur, all probabilities remain in bounds, and the same seed
   reproduces the demand audit exactly.
9. The isolated runtime restores the active v2 profile builder, stimuli,
   templates and plugin registry after execution.

No gate requires a positive, significant or minimum-sized treatment effect.
No p-value, MDE, winner selection, formal reuse or real-LLM authorisation is
permitted by this contract.
