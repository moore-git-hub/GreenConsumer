# TASK_005 FMCG Purchase-Demand Redesign Contract 3.1

**Status:** frozen before any v3.1 replay output is produced.

**Scope:** option A only: an Oatly-like plant-based-milk/FMCG repeat-choice
scenario. This contract does not apply to new-energy-vehicle adoption.

## Why v3.0 is insufficient

Contract 3.0 correctly separated category-purchase opportunities from focal-brand
choice, but it remained a construct-only bridge. It did not model four mechanisms
required for an FMCG repeat-choice interpretation:

1. heterogeneity in purchase frequency, baseline control and brand preference;
2. state dependence (loyalty, repertoire membership and switching persistence);
3. the direct intention-to-behaviour role of perceived behavioural control (PBC);
4. a separately identified enterprise action that reduces purchase friction.

The frozen variance-v3 data additionally show that the old behavioural display is
under-resolved: one condition contains only 20 cognitive agents and roughly 70
post-crisis weekly opportunities per block. A mean probability contrast below one
percentage point therefore corresponds to fewer than one additional realised
choice and can easily produce visually identical curves even when latent
intentions differ.

## Scientific structure

The v3.1 demand layer separates:

1. **semantic appraisal and network diffusion**, retained from the 20 cognitive
   GABM agents;
2. **TPB motivational state**, represented by Att, SN, PBC and brand trust;
3. **category-purchase incidence**, generated independently of treatment;
4. **conditional focal-brand choice**, represented by a binary random-utility
   decision against a composite competing alternative;
5. **state dependence**, represented by a bounded loyalty stock updated only at
   purchase occasions;
6. **conversion support**, represented by a prospectively crossed, non-semantic
   purchase-friction intervention that changes PBC but not trust, Att or SN.

This decomposition follows the distinction between purchase timing, brand choice
and quantity in Gupta (1988), and the state-dependence/loyalty logic of Guadagni
and Little (1983). PBC enters both intention and behaviour because Ajzen (1991)
allows PBC, together with intention, to predict behavioural achievement. These
sources justify the structure, not the numerical parameter values.

## Two population levels

- The 20 existing GABM agents remain the cognitive/network units. Their LLM
  appraisals are not duplicated or treated as 500 independent observations.
- Each cognitive agent is projected onto 25 deterministic micro-buyers for a
  standardised 500-buyer demand display. Micro-buyers inherit the cognitive
  trajectory but receive treatment-invariant preference, PBC, loyalty and
  purchase-frequency heterogeneity.
- The micro layer improves event resolution only. The replication block remains
  the inferential unit; micro-buyers are never counted as independent
  replications, respondents or observed consumers.
- Results are reported per 1,000 category-purchase occasions, not as a forecast
  of Oatly's real market share.

## Frozen opportunity and heterogeneity design

- One Tick is one day.
- Purchase intervals are deterministically allocated from 5, 7, 10 and 14 days.
- Opportunity interval and phase depend only on block seed and micro-buyer ID.
- The same micro-buyer has the same opportunities in every communication and
  facilitation condition.
- Each 25-member archetype cohort receives a balanced normal-quantile grid with
  exactly symmetric latent offsets. Hash-derived cyclic permutations prevent the
  same rank ordering across constructs without changing cohort means.
- Reference logit-scale standard deviations are 0.60 for baseline brand
  preference, 0.40 for baseline PBC and 0.60 for initial loyalty.
- These distributions are uncalibrated modelling assumptions. The fixed
  sensitivity values are 0.00, the reference value, and 1.00 for preference;
  0.00, 0.40 and 0.80 for PBC; and 0.00, 0.60 and 1.00 for initial loyalty.

## Frozen conditional-choice equation

At a purchase opportunity, micro-buyer *i* has

`logit(p_it) = logit(I_it) + preference_i + beta_PBC(PBC_it - PBC_i0) + beta_L L_it`.

- `I_it` is recomputed from the recorded Att, SN, trust and current PBC using the
  frozen v2 extended-TPB equation.
- `preference_i` is treatment invariant.
- `beta_PBC` has fixed sensitivity values 0.00, 1.00 and 1.50; reference 1.00.
- `beta_L` has fixed sensitivity values 0.00, 0.50 and 1.00; reference 0.50.
- Initial loyalty is treatment invariant. At each category-purchase occasion it
  is updated as `clip(0.85 * L + 0.20 * (2 * choice - 1), -1, 1)`.
- The choice draw is a common random number derived only from block seed,
  micro-buyer ID and Tick. Treatment identity never enters the draw.

The reference setting is an illustrative structural stress test, not an
empirical calibration and not a formal-analysis parameter set.

## Frozen conversion-support factor

The new factor is a hypothetical, explicitly disclosed **purchase-friction
support package**: a time-limited trial voucher with verified retail
availability. It is crossed with every communication condition, including the
no-clarification control.

- Levels: absent versus present.
- Exposure: universal and deterministic in the standardised demand population.
- Active period: Ticks 6--19 inclusive.
- PBC signal sensitivity values: 0.20, 0.35 and 0.50; reference 0.35.
- While active, `PBC_it = PBC_i0 + signal * (1 - PBC_i0)`; otherwise
  `PBC_it = PBC_i0`.
- Facilitation cannot change semantic scores, trust, Att or SN.
- Communication cannot directly change PBC or the opportunity schedule.

The bundle is a single managerial intervention; its trial and availability
components cannot be interpreted separately. Its numerical signal must be
empirically calibrated or retained as sensitivity analysis before a formal run.

## Outcomes and curves

The retired cumulative-ever-buyer curve must not be used. Report instead:

- expected focal-brand choice share at category-purchase occasions;
- realised focal-brand choice share in a trailing 7-day window;
- incremental focal-brand choices per 1,000 category-purchase occasions versus
  the matched no-clarification condition;
- communication-only, facilitation-only and combined effects;
- their difference-in-differences interaction;
- segment-level effects and post-crisis recovery time, when estimable.

The expected curve diagnoses the mechanism. The realised curve displays event
variation. Neither is observed sales data.

## Prospective structural acceptance rules

Acceptance is independent of p-values and desired effect magnitude.

1. Opportunities and initial micro-buyer attributes must be identical across
   matched conditions.
2. Before Tick 5, all matched curves must be identical within floating-point
   tolerance.
3. Communication must alter demand only through recorded psychological states;
   facilitation must alter demand only through PBC.
4. The crisis must reduce mean expected choice relative to the matched
   pre-crisis baseline in the reference replay; failure indicates a
   construct-direction error.
5. The no-effect parameter setting must collapse exactly to the intention-only
   bridge, proving that the new layer does not contain a hidden winner.
6. Increasing facilitation signal or PBC weight must be weakly monotone for a
   fixed state and draw, but the realised aggregate need not be monotone because
   loyalty paths may diverge.
7. No p-value, power estimate, optional stopping rule or target minimum effect is
   permitted in this replay.
8. Similar communication-only purchase curves remain an admissible finding. A
   model version cannot pass merely because its curves separate.

## Integrity and formal boundary

- Existing v2/variance-v3 rows are diagnostic replay inputs only and cannot
  enter v3.1 formal inference.
- No real LLM call is authorised by this contract.
- No v3.1 production-path promotion is authorised by this contract.
- Before a new engineering pilot: correct the SN measurement, add all v3.1 audit
  fields, run the Windows-Kernel regression suite, freeze a calibration or
  sensitivity plan, create a new seed ledger and obtain version-specific human
  execution authorisation.
