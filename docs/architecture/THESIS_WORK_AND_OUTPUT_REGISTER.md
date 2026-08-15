# Thesis work, evidence and output register

## 1. Objective

This is the operational record connecting repository work to an MBA thesis. It separates four thesis domains—model design, system construction, experiment design and simulation results—and records what exists, what remains planned and what may be claimed. It is not a thesis result table.

Status vocabulary:

- `AVAILABLE`: artifact exists and has an identifiable source;
- `IMPLEMENTED_NOT_RENDERED`: output code exists but no retained source run has yet been processed and visually checked;
- `PLANNED_NOT_EXECUTED`: design exists but the corresponding experiment has not run;
- `NOT_AUTHORIZED`: execution requires an explicit later authorization;
- `DEFERRED_BY_USER`: a planned execution step has been paused without admitting results;
- `HISTORICAL_ONLY`: belongs to the closed v3.2 archive.

## 2. Thesis-section traceability

| Work ID | Thesis domain | Evidence or deliverable | Canonical source | Status | Permitted use now |
|---|---|---|---|---|---|
| W01 | Writing foundation | Research positioning, RQs, theory–mechanism map, chapter skeleton and claim firewall | `docs/thesis/THESIS_WRITING_FOUNDATION_V331.md` | AVAILABLE | Basis for chapter drafting; not an empirical result |
| W02 | Literature/style | Seven-pack source register and five same-major thesis style samples | `docs/thesis/LITERATURE_AND_STYLE_SOURCE_REGISTER.md` | AVAILABLE | Source routing and writing-style constraints; bibliography entries still require item-level verification |
| W03 | Thesis chapter | Chapter 2 literature review and theory draft with inline author–year–title citations | `docs/thesis/CHAPTER_2_LITERATURE_AND_THEORY_DRAFT_V331.md` | AVAILABLE | Working thesis prose; claims remain limited by citation audit |
| W04 | Thesis chapter | Chapter 3 GABM construction draft with equations and design/assumption labels | `docs/thesis/CHAPTER_3_MODEL_AND_METHOD_DRAFT_V331.md` | AVAILABLE | Working thesis prose; no Pilot/formal result implied |
| W05 | Citation audit | Claim–citation–permitted scope–prohibited extrapolation map | `docs/thesis/CITATION_CLAIM_AUDIT_V331.md` | AVAILABLE | Mandatory gate for later revisions and new citations |
| W06 | Thesis chapter | Chapter 4 experiment design and validation draft without formal results | `docs/thesis/CHAPTER_4_EXPERIMENT_AND_VALIDATION_DRAFT_V331.md` | AVAILABLE | Treatment, estimand, Pilot and engineering validation prose; no formal effect claim |
| W07 | Reproducibility appendix | v3.3.1 ODD＋D model and human-decision description | `docs/thesis/APPENDIX_ODD_D_MODEL_DESCRIPTION_V331.md` | AVAILABLE | Reproducibility specification; not validity proof |
| W08 | Thesis chapter | Chapter 5 formal-results reporting template with empty tables, figures and guarded prose | `docs/thesis/CHAPTER_5_RESULTS_REPORTING_TEMPLATE_V331.md` | AVAILABLE | Structure only; no Pilot/formal value, direction or significance exists |
| W09 | Analysis protocol | Pre-Pilot N=10 diagnostics, joint LOBO and exact sign-flip sensitivity | `SMALL_N_DIAGNOSTIC_PROTOCOL_V331.md` | AVAILABLE | Frozen analysis interface; does not prove N=10 feasible and does not replace primary analysis |
| W10 | Design worksheet | P1/P2/P5 threshold provenance and evidence-gap worksheet | `DESIGN_THRESHOLD_JUSTIFICATION_WORKSHEET_V331.md` | AVAILABLE | Thresholds remain design values; managerial justification unresolved |
| W11 | Thesis chapter | Chapter 1 introduction draft with scoped background, RQs, methods and contribution boundaries | `docs/thesis/CHAPTER_1_INTRODUCTION_DRAFT_V331.md` | AVAILABLE | Working thesis prose; no Pilot/formal result implied |
| W12 | Thesis audit | Title–RQ–evidence–contribution consistency and retained formal-execution route | `docs/thesis/TITLE_RQ_CONTRIBUTION_AUDIT_V331.md` | AVAILABLE | Mandatory before Chapter 5 is finalized |
| W13 | Thesis audit | Cross-chapter terminology, RQ, timing, estimand and evidence-status consistency | `docs/thesis/CROSS_CHAPTER_CONSISTENCY_AUDIT_V331.md` | AVAILABLE | Canonical wording gate for Chapters 1–5 |
| W14 | Thesis audit | Chapter 3–4 theory–rule–estimand–claim interface audit | `docs/thesis/CHAPTER_3_4_INTERFACE_AUDIT_V331.md` | AVAILABLE | Mandatory wording and identification gate for Chapters 3–5 |
| M01 | Model design | 2×2×2 + common control conceptual design | `FORMAL_EXPERIMENT_PROTOCOL.md`, `experiment_config.py` | AVAILABLE | Methods: treatment definition |
| M02 | Model design | Semantic→psychological→network→behavior architecture | `MODEL_TO_CODE_TRACEABILITY_V331.md`, `docs/thesis/figures/FIG-MECH-01_v331_mechanism_architecture.svg` | AVAILABLE | Methods: implemented architecture; figure must retain the LLM/non-LLM boundary |
| M03 | Model design | v3.3 Trust dynamics | `mechanism_v33.py`, Decision Log DR-01/05/06 | AVAILABLE | Methods with engineering-assumption boundary |
| M04 | Model design | Clarification diffusion | `clarification_diffusion_v33.py` | AVAILABLE | Methods; p and lag described as frozen assumptions |
| M05 | Model design | Renewal demand and loyalty | `purchase_mechanism_v33.py`, `greenconsumer_v33/demand.py` | AVAILABLE | Methods; M described as numerical resolution |
| S01 | System construction | Version-scoped runtime and schema provenance | `task005_fmcg_runtime_v33.py`, `greenconsumer_v33/runner.py` | AVAILABLE | System implementation chapter |
| S02 | System construction | LLM audit/replay, no-direct-behavior boundary and rule-triggered reuse of explicit appraisal reason as UGC | audited router, reflect/plan plugins, `simulation_core.py` | AVAILABLE | System implementation and internal validity; generated UGC wording is not human content validity |
| S03 | System construction | Tests and engineering verification chain | `tests/`, architecture result records | AVAILABLE | Verification subsection, not formal inference |
| S04 | System construction | Fixed-network state/flow animation | `greenconsumer_v33/network_animation.py` | AVAILABLE | System demonstration with fixed-topology caveat |
| E01 | Experiment design | Primary/secondary estimands and analysis family | `FORMAL_EXPERIMENT_PROTOCOL.md` | AVAILABLE | Formal design section |
| E02 | Experiment design | Pilot seed and replication design with pre-result `N_max=10` | Pilot protocol/contract/code, `PILOT_EXECUTION_CONDITIONS.md` | DEFERRED_BY_USER | Temporarily deferred for thesis drafting, not cancelled; N=10 is not justified as formal N |
| E04 | Experiment design | N=10 small-sample diagnostic and sensitivity rules | `SMALL_N_DIAGNOSTIC_PROTOCOL_V331.md` | AVAILABLE | Apply only if OC gate accepts N=10; results cannot drive method switching |
| E03 | Experiment design | Formal N, seed ledger and frozen analysis SHA | not yet created | NOT_AUTHORIZED | No thesis value may be reported yet |
| R01 | Simulation results | v3.3.1 engineering robustness results | `EXPERIMENT_EVIDENCE_REGISTER.md` and committed result records | AVAILABLE | Robustness/verification appendix with engineering label |
| R02 | Simulation results | Selected Real-LLM robustness | committed Real-LLM result record | AVAILABLE | Engineering robustness only |
| R03 | Simulation results | Pilot variance findings | no valid result exists | DEFERRED_BY_USER | No finding may be stated |
| R04 | Simulation results | v3.3.1 formal P1/P2/P5 results | no result exists | NOT_AUTHORIZED | No finding may be stated |
| R05 | Simulation results | Cognition-evolution tables/figures | preselected `baseline_r1/v331_20260814_230111`, schema 1.2 manifest and `greenconsumer_v33/cognition_outputs.py` | AVAILABLE | Single Real-LLM engineering run; descriptive mechanism/internal-validation evidence only, not formal inference |

## 3. Stable output registry

Artifact IDs remain stable even if final thesis table/figure numbering changes.

| Artifact ID | Proposed thesis role | Generated file or source | Unit and interpretation | Status |
|---|---|---|---|---|
| TAB-DESIGN-01 | Run design and provenance | `thesis_outputs/tables/01_run_design.csv` | one completed run | generator available |
| TAB-SEM-01 | Realized semantic manipulation | `04_semantic_manipulation_means.csv` | exposed appraisal records; descriptive | generator available |
| TAB-MECH-01 | Mechanism state by Tick | `08_mechanism_tick_summary.csv` | condition×Tick Agent means | generator available |
| TAB-COG-01 | Verbatim explicit appraisal ledger | `cognition/tables/01_explicit_appraisal_ledger.csv` | actual non-empty explicit appraisal only | AVAILABLE — limited engineering evidence |
| TAB-COG-02 | Cognition state trajectory data | `cognition/tables/02_cognition_tick_summary.csv` | condition×Tick Agent means | AVAILABLE — limited engineering evidence |
| TAB-COG-03 | Pre-specified temporal windows | `cognition/tables/03_cognition_window_summary.csv` | descriptive window means | AVAILABLE — limited engineering evidence |
| TAB-COG-04 | Within-Agent state transitions | `cognition/tables/04_agent_transition_ledger.csv` | Agent-level descriptive differences | AVAILABLE — limited engineering evidence |
| TAB-COG-05 | Transition summary | `cognition/tables/05_transition_summary.csv` | mean/SD across Agents within one run; no inferential SE | AVAILABLE — limited engineering evidence |
| TAB-COG-06 | Control-adjusted Agent recovery contrasts | `cognition/tables/06_control_adjusted_agent_recovery.csv` | same-Agent treatment-minus-Control difference in T5-to-endpoint change; descriptive only | AVAILABLE — limited engineering evidence |
| FIG-COG-01 | Trust/Att/SN/intention trajectories | `cognition/figures/01_cognition_state_trajectories.png` | single-run descriptive Agent means | AVAILABLE — limited engineering evidence |
| FIG-COG-02 | Agent-level control-adjusted transition facets | `cognition/figures/02_recovery_transition_facets.png` | matched treatment-minus-Control changes with all engineered Agents, IQR, median and mean; Agents are not replication blocks | AVAILABLE — limited engineering evidence |
| FIG-COG-03 | Explicit appraisal availability matrix | `cognition/figures/03_explicit_appraisal_availability.png` | condition×Tick record availability, not reasoning quality | AVAILABLE — limited engineering evidence |
| FIG-NET-01 | Network state and information-flow animation | optional GIF from `run_v33_thesis.py` | fixed topology, evolving states/flows | generator available |
| FIG-MECH-01 | Overall mechanism figure | `docs/thesis/figures/FIG-MECH-01_v331_mechanism_architecture.svg` | semantic appraisal→deterministic psychology→fixed-network exposure→repeat choice, with explicit evidence firewall | AVAILABLE — authoritative conceptual SVG; PNG rerender pending after wording correction |
| FIG-ROUTE-01 | Thesis research and technical route | `docs/thesis/figures/FIG-ROUTE-01_v331_thesis_technical_route.svg` | completed/partial/pending stages and execution gates | AVAILABLE — authoritative method SVG; PNG rerender pending after wording correction |
| TAB-PILOT-01 | Pilot variance components | future Pilot output | replication-block planning variance | PLANNED_NOT_EXECUTED |
| TAB-FORMAL-01 | Confirmatory P1/P2/P5 | future formal analysis | replication-block inference | NOT_AUTHORIZED |
| TAB-FORMAL-02 | Confirmatory diagnostics and sensitivity | future formal analysis following `SMALL_N_DIAGNOSTIC_PROTOCOL_V331.md` | all block values, exact sign-flip family and joint LOBO | TEMPLATE_AVAILABLE; DATA_NOT_AUTHORIZED |

“Generator available” does not mean a thesis-ready artifact has been produced. A result artifact becomes available only after its source run is retained, source hashes are recorded and the rendered output is visually inspected.

## 4. Cognition output protocol

The zero-API command is:

```powershell
python run_v33_cognition.py "results\v33_runs\<run_id>"
```

Pre-specified transitions are:

| Transition | Difference | Interpretation |
|---|---:|---|
| Crisis shock | T5 − T4 | within-Agent change at the crisis event |
| Immediate response | T6 − T5 | first post-crisis/immediate-strategy Tick |
| Delayed onset | T10 − T9 | delayed-strategy activation boundary |
| Recovery to endpoint | T35 − T5 for baseline | cumulative within-Agent descriptive change |

For a T30 or T40 robustness run, the observed and summary-declared endpoint replaces T35 and is written to the manifest. No text sentiment coding or new psychological labeling is performed. Empty quiet-Tick reasoning is preserved in the source but excluded from the verbatim ledger; availability is reported separately so missing text cannot be mistaken for neutral reasoning.

## 5. Result admission checklist

Before any generated result enters the thesis:

1. record run ID, code release, Git SHA/dirty state and all seeds;
2. verify the run horizon and full Agent×Tick key alignment;
3. retain source-file SHA-256 hashes and generated-output hashes;
4. identify the evidence class: engineering validation, Pilot planning or formal inference;
5. state the unit of analysis and avoid treating Agents/micro-buyers as replication blocks;
6. visually inspect every figure for truncation, unreadable labels and misleading scales;
7. write the claim no more strongly than the registered evidence permits;
8. register any post-freeze change in the Decision Log before rerunning.

## 6. Work log entry — 2026-08-15

Added v3.3.1 model-to-code traceability and a stable thesis output registry. Implemented offline cognition-evolution post-processing, a CLI, source/output hash manifest and zero-API synthetic tests. No GABM run, provider call, Pilot observation, formal estimate or new empirical conclusion was produced in this work package. Real-run rendering and visual QA remain pending.

Pre-publication validation executed in the Linux work environment: 85 tests that do not require AgentKernel passed, including all 18 tests added for TASK-PV01 and cognition outputs. Nine AgentKernel-dependent test files could not be collected because `agentkernel_standalone` is unavailable in this environment; they remain assigned to the Windows `Kernel` environment and are not recorded as passed or failed assertions. Python compilation and `git diff --check` passed. This validation produced no simulation observations or provider calls.

Windows full-suite validation then produced 123 passes and one Tk/Tcl canvas-creation failure in sensitivity-figure post-processing. The v3.3.1 file-writing plot modules were hardened to force Matplotlib's non-interactive `Agg` backend before importing `pyplot`, and a backend contract test was added. Local forced-`TkAgg` reproduction confirmed the module overrides the GUI backend and both Stage-A and Morris synthetic replots complete. This is a system portability fix only; it changes no scientific data, model state, parameter, estimand or reported result. Based on the user's retained Windows terminal output, remote commit `ab74a2e2cdba3029ae2f623fa0fb8f49128f6df1` then passed the complete suite: 125 passed in 5.04 seconds. The additional test is the new backend contract; Windows full-suite revalidation is complete.

For the first real cognition rendering, the source was selected before viewing cognition trajectories: clean Real-LLM `baseline_exact` run `baseline_r1/v331_20260814_230111` at source Git HEAD `f52c97fcdf88efd0df2bec01e80bac2f63d9233b`. Baseline repeats and prompt perturbations are excluded from selection to avoid outcome-dependent cherry-picking. The cognition manifest was hardened before rendering to record source-run Git provenance, post-processor Git provenance and SHA-256 hashes of both analysis code files. Real rendering and visual QA remain pending.

The first local rendering attempt exposed a real-schema collision: both source CSVs contained semantic audit columns, while the synthetic fixture had represented them only on the thoughts side. The attempt stopped before manifest creation and produced no inference. The merge now namespaces thoughts-side audit fields internally, with output semantics unchanged, and a conflicting-value regression fixture verifies the intended source. Seven direct cognition tests pass; real rendering must be retried from a clean patched commit.

After that repair, the preselected real run successfully produced five tables and three figures with a PASS payload and no formal inference. Admission was nevertheless withheld at visual QA: the recovery heatmap used one raw scale for Trust (0–10) and three 0–1 variables, so its color intensity invited invalid cross-unit comparisons; the trajectory and availability plots also placed too much decoding burden on nine arbitrary colors and overlapping lines. The generator now uses factorial visual encodings for trajectories, variable-unit recovery facets, and a condition×Tick appraisal-availability matrix. Synthetic rendering and visual inspection passed. The original heatmap is superseded and excluded from the manifest. The same preselected real run must be rerendered from a clean commit before any cognition artifact changes to `AVAILABLE` or any empirical pattern is admitted to the thesis.

The real rerender at postprocessor commit `353ea074aef1c2b0aecca7e26e1b54457eb9b77b` produced schema 1.1 outputs whose uploaded PNG/CSV hashes matched the manifest exactly. The Tick summary contained the complete 9×35 panel (315 rows), the transition summary contained 9×4×7 cells (252 rows), common history was numerically identical through T5, and transition means reconciled to Tick means within floating-point tolerance. Agent-ledger review then verified 720/720 expected condition×Agent×transition rows, identical Agent sets, no duplicate keys and exact aggregation to the summary (maximum discrepancy `1.11e-16`).

That Agent-level review showed that a mean-only recovery figure concealed extensive zero mass and directionally heterogeneous responses. Because this was learned after viewing the retained run, the revised display is explicitly post-result descriptive visualization, not a preregistered confirmatory estimand. Schema 1.2 therefore retains the raw T5-to-endpoint mean/SD/min/max table, adds an auditable same-Agent treatment-minus-Control recovery table, and replaces only FIG-COG-02's display with all Agent contrasts plus IQR, median and mean. No standard errors, confidence intervals, p-values or strategy ranking are produced.

The final clean schema-1.2 rerender used postprocessor commit `ce736f442c74bef404940f6dcaf8009c4015a1da` and the same preselected source run. The manifest records six tables and three figures. Independent review closed the complete nine-output hash chain; table 6 contains all 8×20×7 matched treatment cells with no missing or duplicate keys, and its arithmetic and source-ledger reconstruction agree within `1.665e-16`. Figure 2 passed visual QA with variable-specific axes, all Agent points, IQR, median, mean, direction counts and the non-replication warning. The user then confirmed that both requested Windows `Kernel` regression commands passed on the clean code commit; counts and timing were not supplied in that confirmation and are therefore not asserted here.

R05 and TAB/FIG-COG-01–06/01–03 are now `AVAILABLE` only as limited, single-run Real-LLM engineering evidence. This admission permits descriptive mechanism and internal-validation statements tied to the retained run. It does not authorize formal inference, external validity, causal strategy ranking, hidden-chain-of-thought interpretation or treatment of the 20 engineered Agents as replication blocks. This closure generated no new GABM run, provider call, Pilot observation or formal estimate.

## 7. Work log entry — 2026-08-15: thesis writing foundation package

Created the v3.3.1 thesis writing foundation and the literature/style source register. The source audit located seven user literature packs containing 57 PDFs (53 unique after SHA-256 deduplication) and five same-major master's theses used only for structure and style. Core English bibliography entries are admitted only after PDF and publisher/journal cross-check; unresolved Chinese metadata remains explicitly pending rather than inferred from filenames.

Rebuilt the two conceptual figures from the older draw.io material. `FIG-MECH-01` removes obsolete KOL/Bridge and arbitrary allocation details, makes the LLM responsible only for schema-constrained semantic appraisal, and leaves psychological updates, diffusion and purchase choice deterministic and auditable. `FIG-ROUTE-01` separates completed engineering verification, the not-yet-executed Pilot and unauthorized formal inference. The user froze `N_max=10` before Pilot results; this is recorded as a budget cap, not as achieved formal N. This work generated no simulation run, provider call, Pilot observation or formal estimate.

## 8. Work log entry — 2026-08-15: citation-aware Chapter 2 and Chapter 3 drafts

Created the Chapter 2 literature/theory draft, Chapter 3 GABM construction draft and a claim-level citation audit. Citations appear at the relevant claims in author–year–title form. Four Chinese papers were admitted after PDF-level metadata and abstract verification; four supplemental sources on repeat brand choice, influence maximization and complex contagion were admitted from official publisher/journal pages and explicitly marked as out-of-pack sources.

The drafts separate construct-level literature support from study design and engineering assumptions. In particular, N=20, M=25, T5/T6/T10/T35, K=3, amplification probability, lag, Trust parameters, intention coefficients and `N_max=10` are not presented as literature-derived estimates. No Pilot or formal experiment was executed, and no empirical strategy ranking, p-value or external-validity claim was created.

## 9. Work log entry — 2026-08-15: Chapter 4 design/validation draft and ODD＋D appendix

Created the no-formal-results portion of Chapter 4 and a code-aligned ODD＋D appendix. Chapter 4 freezes the treatment matrix, AUC/choice/reach estimands, replication-block unit, 3×2 cognitive Pilot grid, 3-seed offline-demand replay, planning-SD rule, Holm family and validity gate. Completed horizon, Trust, clarification, topology, orientation, network-size/K, micro-buyer and selected Real-LLM checks are reported only as implementation or engineering evidence.

The ODD＋D appendix records purpose, entities, scales, scheduling, design concepts, initialization, inputs, submodels and human-decision assumptions, and maps each section to canonical code/output files. It explicitly states that Agents do not optimize a long-run objective, the network does not rewire, LLM appraisal is not human measurement, and the model has no empirical population/network calibration.

Three additional method references—Holm multiple testing, Morris screening and ODD＋D—were verified and added to the citation audit. Two unresolved pre-execution risks are now visible in the thesis package: N=10 small-sample diagnostic rules remain to be frozen, and the three design thresholds still lack a real managerial-effect justification. This writing package changed no scientific mechanism, parameter, treatment, estimand, prompt, seed or execution contract. New GABM run=0, provider call=0, Pilot observation=0, formal inference=0.

## 10. Work log entry — 2026-08-15: Chapter 5 template and pre-Pilot analysis interfaces

Created a Chapter 5 reporting template that reserves separate positions for block flow, P1/P2/P5 confirmation, P3/P4 description, trajectories, realized semantic manipulation, single-run cognition evidence and engineering robustness. All formal cells remain empty placeholders; no direction, p-value, strategy winner or formal finding was generated.

Froze the N=10 diagnostic interface before Pilot results. The primary two-sided one-sample t-test and Holm family remain unchanged. Each estimand must show all ten block values, distribution and influence diagnostics, ten joint leave-one-block-out analyses and a separately Holm-adjusted exact sign-flip sensitivity family based on all 1024 sign assignments. Valid extreme blocks cannot be deleted; disagreement is reported as fragility rather than resolved by choosing the favorable method. Ernst (2004) was verified from the official journal page and added to the source and claim registers.

Created a threshold worksheet showing that P1/P2=0.15 Trust points and P5=0.05 expected-choice share are inherited pre-result design values, not established managerial-effect thresholds. The worksheet defines acceptable enterprise, empirical and measurement evidence and keeps the justification status unresolved. This package changed no mechanism, treatment, estimand, main threshold, prompt or seed and generated GABM run=0, provider call=0, Pilot observation=0 and formal inference=0.

## 11. Work log entry — 2026-08-16: Chapter 1–2 structural revision

Revised Chapters 1 and 2 around a stricter problem–gap–method chain. Chapter 1 now frames the problem as green-claim trust repair under limited communication timing and network-seeding decisions, states that surveys and experiments remain indispensable for empirical validity, and assigns GABM only the roles of mechanism integration and counterfactual computation. RQ3 was narrowed from an unsupported search for dependency conditions to a pre-specified timing contrast plus direction checks under engineering perturbations. The TPB passage no longer claims a theoretical extension.

Chapter 2 now identifies three structural breaks rather than claiming a topic vacancy: separation among exposure, appraisal, trust, intention and repeat choice; the trade-off between compound-text representation and mechanism auditability; and the distinction between within-run output rows and independent replication. The P2 compound-stimulus limitation is recorded as a structural identification boundary that cannot be repaired by post hoc semantic regressions. No literature was added, and no existing source was used to justify an engineering parameter.

This writing revision changed no model, treatment, estimand, parameter, prompt, seed or execution contract. New GABM run=0, provider call=0, Pilot observation=0 and formal inference=0.

## 12. Work log entry — 2026-08-16: Chapter 3–4 interface audit

Audited the Chapter 3 model description and Chapter 4 estimands directly against the executable interfaces. The audit corrected three substantive wording mismatches: LLM appraisal reason can become UGC text only after a rule-triggered posting event; the demand layer does not use one default seven-Tick renewal interval; and cognitive-layer purchase intention is not identical to the micro-buyer conditional choice probability, which also reflects micro-buyer PBC, preference offset and the realized prior-choice loyalty path.

The five estimands now carry explicit identification limits. P1/P2/P5 use pre-frozen equal cell weights rather than an observed strategy mix. P2 compares compound message frameworks and does not identify semantic-component mediation or unregistered interactions. P3 is an early treatment-onset contrast over T6–T9, not a complete timing-response function. P4 is direct enterprise reach within the frozen delivery window, not UGC cascade, persuasion or purchase. P5 is opportunity-conditional expected focal-brand choice, not realized sales, market share or the cognitive Agent's intention state.

The corrected boundary is synchronized across Chapters 1–4, the writing foundation, ODD＋D appendix, cross-chapter and model-to-code registers, and the two conceptual SVG sources. Existing PNG exports retain the earlier wording and are marked for later Windows CJK-font rerender; they are not authoritative for the revised text. No literature, model rule, treatment, estimand, parameter, prompt, seed or execution contract changed. New GABM run=0, provider call=0, Pilot observation=0 and formal inference=0.
