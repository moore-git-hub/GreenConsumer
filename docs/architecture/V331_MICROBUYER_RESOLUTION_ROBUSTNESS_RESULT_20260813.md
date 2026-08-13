# TASK_005 v3.3.1 Micro-buyer Numerical-Resolution Robustness — Result Record

**Date:** 2026-08-13  
**Run:** `micro_20260813_190453`  
**Status:** engineering PASS  
**Inference:** descriptive engineering robustness only; no p-values/CI/formal inference

## 1. Verified execution facts

The completed suite reused five already-completed N20/K3 BA cognitive histories from `size_20260813_164031` and reran only the downstream demand discretization at:

```text
M = 10 / 25 / 50 micro-buyers per cognitive Agent
```

This produced 15 demand-resolution profiles (5 network histories × 3 resolutions). The source network-size suite itself was recorded as `PASS`.

The user-run summary reports:

- `status = PASS`;
- `profiles_run = 15`;
- `p5_sign_unstable_networks = 0`;
- `s1_sign_unstable_networks = 0`;
- `parameter_selection_permitted = false`;
- no p-values or formal inference.

In the implementation, suite `PASS` is conditional on zero hard invariant failures. These hard checks include source-suite integrity, exact M25 reproduction of source P5/S1 to `1e-12`, upstream P1–P4 invariance across M, exact buyer counts/unique IDs, and provenance hashes for reused cognitive histories.

## 2. Scientific interpretation

The completed engineering suite supports two bounded statements:

1. **Direction robustness:** across the five reused BA cognitive histories, changing downstream deterministic micro-buyer resolution from M10 to M25 to M50 did not reverse the sign of either P5 (overall clarification effect on expected repeat choice) or S1 (conversion-support effect on expected repeat choice).
2. **Layer separation:** because suite PASS requires P1–P4 to remain unchanged across M, the demand-resolution experiment did not feed back into upstream Trust/content/timing/channel estimands.

This does **not** establish that M25 is an empirically calibrated population sample size. Micro-buyers are deterministic downstream numerical integration/discretization units, not statistically independent consumers.

## 3. Frozen decision

The scientific baseline remains:

```text
25 micro-buyers per cognitive Agent
```

M10 and M50 are numerical-resolution robustness probes only. No result-dependent selection of M is permitted.

## 4. Quantitative table still required before thesis citation

The summary JSON supplied to the audit establishes PASS/sign stability but does not contain the actual P5/S1 magnitudes or M10−M25 / M50−M25 deviations. Before this result is cited quantitatively in the thesis, archive and review:

- `microbuyer_family_summary.csv`;
- `microbuyer_stability.csv`;
- `microbuyer_invariants.csv`;
- `microbuyer_demand_diagnostics.csv`;
- three generated figures.

Until those files are ingested, the result record should be used only for the verified PASS/sign-stability statements above.

## 5. Consequence for the workflow

The principal Fake-LLM structural robustness chain is now sufficiently developed across:

- finite horizon;
- Trust parameters (OAT/boundary + Morris);
- clarification reach/lag;
- topology;
- equal-degree orientation;
- network size / paid-seed allocation;
- downstream micro-buyer numerical resolution.

The next priority is therefore LLM-specific robustness rather than adding further engineering parameter grids: prompt-layout sensitivity, practical provider stochasticity, and selected Real-LLM robustness blocks.
