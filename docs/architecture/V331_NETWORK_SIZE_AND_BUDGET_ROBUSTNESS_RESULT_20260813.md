# TASK_005 v3.3.1 Network Size × Paid-Seed Allocation Robustness — Result Record

**Date:** 2026-08-13  
**Run:** `size_20260813_164031`  
**Status:** engineering PASS  
**Inference:** descriptive engineering robustness only; no p-values, confidence intervals, population inference, or parameter selection

## 1. Purpose

This suite tests whether the v3.3.1 BA-network conclusions are artifacts of the small N=20 cognitive-agent baseline and separates two distinct scaling regimes:

1. **fixed paid-seed count:** K=3 at N=20/40/80;
2. **proportional paid-seed share:** K/N=15%, i.e. K=3/6/12.

The terminology is intentionally restricted to **paid-seed allocation**. It is not a complete monetary-budget model because the enterprise public-exposure component remains frozen at `public_exposure_rate_fixed=.25`; therefore K must not be interpreted as total communication spend.

## 2. Frozen design

- topology: directed BA, m=2, frozen legacy orientation rule;
- network sizes: N=20, 40, 80;
- five pre-specified network-only seeds: 2026081501–2026081505;
- T35;
- Fake LLM;
- Trust baseline parameters;
- clarification p=.55, lag=1, public-exposure rate=.25;
- 25 micro-buyers per cognitive Agent;
- treatment matrix unchanged;
- demand / simulation / LLM seeds unchanged.

The N20 profile is shared by both allocation regimes. Unique profiles per network seed are N20-K3, N40-K3, N40-K6, N80-K3, N80-K12, yielding 25 profiles total.

## 3. Persona-scale implementation checks

The larger cognitive populations are not clones of the original 20 prompts.

- Panel20 is an exact prefix of Panel40;
- Panel40 is an exact prefix of Panel80;
- Panel80 contains 80 unique categorical persona tuples;
- categorical marginal proportions are preserved exactly across N=20/40/80.

Examples of preserved margins include green orientation 25% per four-level group, purchase frequency 25% per four-level group, prior-brand relationship 50/25/25, price sensitivity 50/25/25, availability friction 35/30/35, and social-posting role 35/65.

These are engineering mechanism-coverage proportions, not estimates of the FMCG population.

## 4. Implementation validation

`size_invariants.csv` contains **109/109 PASS** and no failures.

Hard checks include:

- frozen N20 baseline network hash reproduction;
- Panel20 ⊂ Panel40 ⊂ Panel80;
- no N80 persona clones;
- exact network-node set for each N;
- all nine conditions within a profile share one network hash;
- paid-seed count integrity for every treatment condition;
- clarification p=.55 / lag=1 frozen;
- shared N20 T1–T5 cognitive prefix equality for the common seed-2026081501 comparisons.

Therefore the size/budget contrasts are not explained by accidental treatment-matrix, baseline-parameter, or node-set changes.

## 5. Main estimands across five BA realizations

### 5.1 Family means

| N | paid-seed regime | K | P1 Trust | P2 Rational−Empathy | P3 Immediate−Delayed | P4 Hub−Random reach | P5 repeat choice | S1 support |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 20 | shared baseline | 3 | 0.25247 | -0.07612 | 0.26376 | 0.4000 | 0.016787 | 0.028289 |
| 40 | fixed K | 3 | 0.22679 | -0.07049 | 0.24256 | 0.2500 | 0.013931 | 0.027530 |
| 40 | proportional 15% | 6 | 0.28276 | -0.08707 | 0.30406 | 0.3350 | 0.017922 | 0.027554 |
| 80 | fixed K | 3 | 0.20413 | -0.06098 | 0.23527 | 0.2200 | 0.013511 | 0.027459 |
| 80 | proportional 15% | 12 | 0.29643 | -0.08663 | 0.33682 | 0.3275 | 0.019803 | 0.027481 |

All five network realizations preserve the expected direction for every estimand in every size/allocation family: P1/P3/P4/P5/S1 positive and P2 negative.

### 5.2 Fixed K=3: dilution under network growth

When K stays at 3, the paid-seed share falls mechanically:

- N20: 15%;
- N40: 7.5%;
- N80: 3.75%.

Consistent with that dilution, mean Hub eventual enterprise reach falls from .760 at N20 to .625 at N40 and .545 at N80. Mean P4 falls from .400 to .250 and .220. P1 falls from .2525 to .2268 and .2041; P5 falls from .01679 to .01393 and .01351.

The key interpretation is not that a larger market intrinsically weakens clarification. Rather, a **fixed number of paid seed nodes covers a shrinking fraction of a growing sparse BA network**, while the public-exposure component remains fixed by rate.

### 5.3 Proportional K/N=15%: clarification effectiveness is maintained or strengthened

With K/N held at 15%, mean Hub direct-enterprise reach is approximately stable/high across size:

- N20 K3: .760;
- N40 K6: .785;
- N80 K12: .7925.

Mean P1 increases to .2828 at N40 and .2964 at N80. Mean P3 increases to .3041 and .3368. Mean P5 increases to .01792 and .01980.

Thus the positive clarification and repeat-choice mechanisms are not dependent on N=20. Their magnitude, however, is strongly conditional on how paid-seed allocation scales with network size.

### 5.4 Hub advantage remains positive but the contrast does not scale one-for-one with reach

Under proportional allocation, Random reach also rises (.360 at N20, .450 at N40, .465 at N80). Consequently P4 decreases from .400 to .335/.3275 even while Hub reach itself rises slightly.

This is an important construct distinction:

`Hub reach > Random reach` can remain true while the **difference** between them becomes smaller because both channels improve when the number of paid seeds grows.

Accordingly P4 must continue to be interpreted as a channel contrast, not as overall clarification effectiveness.

## 6. Network-scale properties

With BA m=2, increasing N keeps mean undirected degree near four while density falls approximately as expected for a sparse growing network. Reach granularity improves from 1/20=.05 to 1/40=.025 and 1/80=.0125. Across the realized graphs, average shortest-path length increases and the absolute maximum out-degree grows, while the maximum-out-degree share is not fixed.

This resolves an important concern from the N=20 topology experiment: the positive BA Hub advantage remains present when the 5-percentage-point reach granularity of N20 is reduced.

## 7. Scientific interpretation

### Supported engineering claims

The suite supports the following bounded statements:

1. P1/P2/P3/P5 direction is robust across N=20/40/80 in the tested BA family and both paid-seed allocation regimes.
2. BA Hub−Random enterprise-reach advantage remains positive in all 25 pre-specified size/allocation profiles.
3. Fixed K=3 exhibits scale dilution as K/N shrinks.
4. Maintaining K/N=15% preserves high Hub reach and maintains or increases the magnitude of the overall clarification and downstream expected-repeat-choice effects.
5. The N20 result is not explained solely by coarse 5-percentage-point reach granularity.

### Not supported

The suite does **not** establish that:

- 15% is an empirically optimal advertising budget share;
- K is a monetary budget;
- N=80 represents the real consumer population;
- larger networks causally improve persuasion in real markets;
- the engineering persona marginals represent population frequencies;
- Fake-LLM scale robustness establishes persona-sensitive Real-LLM semantic robustness.

## 8. Important limitation: Fake semantic appraisal

The nested N40/N80 panels improve network, initial-state, and demand heterogeneity coverage, but Fake-LLM semantic appraisal is not a substitute for persona-sensitive Real-LLM cognition. Therefore this experiment validates **model scale and paid-seed allocation structure**, not empirical population heterogeneity in language interpretation.

Selected Real-LLM robustness remains necessary later in the validation chain.

## 9. Decision

**Close Network Size × Paid-Seed Allocation robustness as engineering PASS.**

Do not retune N, K, p, lag, or BA parameters based on these results. Keep the scientific baseline at N20/K3 for computationally controlled mechanism experiments, while using the N40/N80 results as scale/budget boundary evidence.

The next low-cost validation stage should target the downstream numerical discretization itself: **micro-buyers per cognitive Agent = 10 / 25 / 50**, holding the cognitive trajectories fixed and rerunning only the demand layer. This separates demand-cohort resolution from LLM/network uncertainty and checks whether P5/S1 depend materially on the engineering baseline of 25 micro-buyers.
