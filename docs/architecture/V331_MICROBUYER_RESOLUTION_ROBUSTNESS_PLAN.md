# TASK_005 v3.3.1 Micro-Buyer Resolution Robustness Plan

**Status:** pre-specified downstream-demand engineering robustness  
**Date:** 2026-08-13  
**Formal inference:** no

## 1. Trigger

The baseline demand layer represents each cognitive Agent with 25 deterministic micro-buyers. This is an engineering discretization used to represent within-persona heterogeneity in preference, PBC and loyalty; it is not a survey sample size and the micro-buyers are not independent statistical respondents.

After Trust, horizon, clarification diffusion, topology, orientation and cognitive-network-size checks, the remaining downstream question is whether P5/S1 materially depend on choosing 25 rather than a coarser/finer micro-cohort resolution.

## 2. Research question

Holding the **entire cognitive GABM trajectory fixed**, how sensitive are downstream expected repeat-choice estimands to:

```text
micro-buyers per cognitive Agent M ∈ {10, 25, 50}
```

The baseline remains M=25 regardless of the result.

## 3. Why this is demand-only

Micro-buyer count enters only `simulate_demand()` through `DemandParameters(micro_buyers_per_archetype=M)`. It does not enter:

- LLM semantic appraisal;
- Trust / Att / SN updates;
- network topology;
- enterprise clarification exposure;
- P1/P2/P3/P4.

Therefore rerunning the cognitive GABM would waste computation and would confound numerical demand resolution with new upstream stochastic history. This suite must reuse frozen cognitive records and rerun only the downstream demand layer.

## 4. Source cognitive blocks

Use the five N=20/K=3 BA cognitive blocks produced by the already completed network-size suite `size_20260813_164031` (or an explicitly supplied equivalent size-suite directory).

For each network-only seed:

```text
2026081501 … 2026081505
```

the identical nine-condition cognitive trajectories are reused for M=10/25/50.

This yields 15 demand-resolution profiles without any LLM/API execution.

## 5. Important construction detail

`build_scenario_micro_cohort()` uses balanced normal quantiles whose locations depend on `micro_count`. Therefore M=10 is **not** treated as a literal prefix/sample subset of M=25 or M=50.

The three M values are alternative deterministic quadrature/discretization resolutions over the same persona-level latent distributions. A prefix-invariance test would be scientifically inappropriate here.

## 6. Frozen components

- cognitive records exactly reused;
- N=20 Engineering Personas;
- BA network realization for each source seed;
- T35;
- Trust baseline;
- clarification p=.55 / lag=1 / public exposure rate=.25;
- conversion-support definition;
- demand seed;
- renewal purchase process;
- choice equation;
- bounded EWMA loyalty;
- persona-to-demand ordinal mappings;
- treatment matrix.

Only `micro_buyers_per_cognitive_agent` changes.

## 7. Primary outputs

The only scientific estimands expected to vary are:

- P5 — overall clarification effect on expected repeat choice;
- S1 — conversion-support effect on expected repeat choice.

P1/P2/P3/P4 are carried through as implementation invariants and must be exactly unchanged within each source network seed.

Also output:

- total T6–T35 purchase opportunities;
- expected focal-brand choice share;
- realized focal-brand choice share (secondary Monte-Carlo diagnostic only);
- absolute and relative M10/M50 deviations from frozen M25;
- sign stability across M;
- opportunity count per cognitive Agent.

## 8. Hard implementation checks

### M1 — source suite integrity

The supplied size suite must be PASS with zero invariant failures and contain exactly five N20/K3 source cognitive blocks.

### M2 — no upstream recomputation

The suite reads existing `cognitive_records.csv` and must not invoke AgentKernel, Hugging Face or an LLM router.

### M3 — baseline M25 reproduction

For every network seed, demand rerun at M=25 must reproduce source P5 and S1 to numerical tolerance (`abs(diff) <= 1e-12`).

### M4 — upstream estimand invariance

For each network seed:

```text
P1/P2/P3/P4(M10) = P1/P2/P3/P4(M25) = P1/P2/P3/P4(M50)
```

within numerical tolerance.

### M5 — buyer-count integrity

Each cognitive Agent must generate exactly M unique buyer IDs under each resolution.

## 9. Interpretation rules

This is a **numerical-resolution robustness check**, not statistical power analysis.

Allowed:

> P5/S1 are stable or resolution-sensitive over the pre-specified M=10/25/50 demand discretizations.

Not allowed:

- “50 buyers is statistically more representative”;
- “25 observations per Agent is an empirical sample size”;
- interpreting micro-buyers as independent replication units;
- selecting M based on which value produces the preferred effect.

The independent unit in future formal GABM inference remains the replication block, not micro-buyers.

## 10. Decision rule

M=25 remains frozen regardless of outcome. If M25 and M50 are close while signs remain stable, 25 can be retained as a computationally efficient discretization. If large differences or sign changes occur, report the demand-resolution boundary and investigate the numerical cohort construction before formal freeze; do not simply move to the result-preferred M.
