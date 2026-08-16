# TASK_005 FMCG v3.3.1 — output, validation, and network-dynamics layer

## Status

v3.3.1 freezes the v3.3 scientific mechanism and adds only text-integrity,
provenance, validation-evidence, and thesis-output instrumentation.

The following scientific parameters remain unchanged from v3.3:

- Trust: crisis retention 0.98, repair retention 0.96, event adjustment 0.80,
  quiet adjustment 0.18, repair saturation 0.30, hypocrisy weight 0.25;
- clarification: paid edge probability 0.55, delivery lag 1;
- renewal demand and bounded-EWMA loyalty;
- BA network baseline, 20 cognitive Agents, K=3 paid seeds;
- historical retained engineering runs used the `qwen-plus` alias at temperature 0.3;
- future v3.3.1 Pilot/formal runs pin `qwen-plus-2025-12-01` at temperature 0.3, while v3.2 remains unchanged;
- 2×2×2 strategy matrix plus one common control.

All numeric scientific defaults remain engineering assumptions until sensitivity
analysis or empirical calibration supports stronger claims.

## Code-quality fixes before freeze

1. A version-scoped `GreenCognitionV33Plugin` preserves the complete selected
   Social Feed post instead of cutting each post at 180 characters.
2. v3.3.1 audit output preserves complete `post_content` and the requested concise
   LLM `reasoning` string without changing the frozen v3.2 shared audit builder.
3. `ClarificationInjectorV33` handles `delivery_lag=0` correctly; the earlier
   branch order would omit amplified recipients at t0. The default lag remains 1,
   so this latent bug did not change the already audited baseline run.
4. Reach analysis reads the configured delivery lag instead of assuming t0+1.

## Persisted run-level evidence

New v3.3.1 runs persist the actual topology returned by `simulation_core`:

- `network_meta.json`
- `network_nodes.csv`
- `network_edges.csv`
- `target_nodes.csv`
- `clarification_exposure_plan.csv`
- `effective_event_timeline.json`

`run_summary.json` also records code release, Git head/branch/dirty state,
model/temperature, seeds, scientific parameter snapshots, and network hash.
The runner checks that all nine blocked conditions share the same topology.

## Thesis-output command

After an engineering run:

```powershell
python run_v33_thesis.py "results\v33_runs\<run_id>"
```

Optional fixed-topology network-state animation:

```powershell
python run_v33_thesis.py "results\v33_runs\<run_id>" `
  --animate-condition Rational-Hub-Immediate `
  --fps 3
```

The animation is **not topology evolution**. The BA graph is fixed during a run;
the GIF shows evolving Trust, clarification exposure, posting Agents, and UGC
broadcast edges on that fixed topology. A thesis should describe it as a
"fixed-topology network state and information-diffusion animation".

## Thesis tables

`thesis_outputs/tables/` can include:

1. run design/provenance;
2. condition-level outcomes;
3. single-block descriptive estimands;
4. semantic manipulation means;
5. paired Rational–Empathy manipulation checks;
6. segment heterogeneity;
7. Agent heterogeneity;
8. Tick-level mechanism summaries;
9. conversion-support effects;
10. repeat choice by segment;
11. network structural metrics;
12. targeting audit;
13. reconstructed social broadcast deliveries;
14. LLM audit summary.

These outputs remain descriptive for one engineering block. They do not turn
20 Agents or micro-buyers into independent statistical replications.

## Internal-validity evidence

`thesis_outputs/validation/` produces machine-readable and human-readable checks
covering:

- Agent×Tick completeness and uniqueness;
- semantic fallback/provider/parse/schema errors;
- common-history replay misses;
- semantic variable ranges;
- peer-only Subjective Norm boundary;
- Rational-evidence and Empathy manipulation directions;
- control contamination;
- pre-treatment state equality versus the common control;
- demand probability/loyalty/renewal invariants;
- persisted-network internal consistency.

A `PASS` supports a hard implementation/process invariant. `SUPPORTED` for a
semantic manipulation is a descriptive engineering-block direction. Neither
label proves external validity or real-world population effect sizes.

## Figure layer

The thesis post-processor additionally creates mechanism-oriented figures for:

- crisis-memory and repair-memory trajectories;
- realized Rational/Empathy semantic manipulation;
- segment-level Trust heterogeneity;
- UGC posting activity;
- peer-social exposure over time;
- audited directed BA baseline topology;
- conversion-support lift by condition.

The original v3.3.1 descriptive figures remain available separately. The thesis
layer is additive and does not modify simulation output.

## Reproducibility manifest

`thesis_output_manifest.json` stores SHA-256 hashes of available source evidence
and generated thesis outputs. This supports later checks that a figure/table was
produced from the claimed run directory.

## Scientific freeze rule

After v3.3.1 passes the zero-API tests and one matched real-LLM engineering audit,
no scientific parameter should be changed because a result looks weak, strong,
or visually unattractive. Subsequent work should use sensitivity analysis,
network-topology robustness, prompt/LLM robustness, and independent replications.

Any future externally calibrated or structurally changed model must receive a new
version and a new frozen analysis contract rather than silently changing v3.3.1.
