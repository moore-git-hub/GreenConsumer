# Thesis work, evidence and output register

## 1. Objective

This is the operational record connecting repository work to an MBA thesis. It separates four thesis domains—model design, system construction, experiment design and simulation results—and records what exists, what remains planned and what may be claimed. It is not a thesis result table.

Status vocabulary:

- `AVAILABLE`: artifact exists and has an identifiable source;
- `IMPLEMENTED_NOT_RENDERED`: output code exists but no retained source run has yet been processed and visually checked;
- `PLANNED_NOT_EXECUTED`: design exists but the corresponding experiment has not run;
- `NOT_AUTHORIZED`: execution requires an explicit later authorization;
- `HISTORICAL_ONLY`: belongs to the closed v3.2 archive.

## 2. Thesis-section traceability

| Work ID | Thesis domain | Evidence or deliverable | Canonical source | Status | Permitted use now |
|---|---|---|---|---|---|
| M01 | Model design | 2×2×2 + common control conceptual design | `FORMAL_EXPERIMENT_PROTOCOL.md`, `experiment_config.py` | AVAILABLE | Methods: treatment definition |
| M02 | Model design | Semantic→psychological→network→behavior architecture | `MODEL_TO_CODE_TRACEABILITY_V331.md` | AVAILABLE | Methods: implemented architecture; final mechanism figure still pending |
| M03 | Model design | v3.3 Trust dynamics | `mechanism_v33.py`, Decision Log DR-01/05/06 | AVAILABLE | Methods with engineering-assumption boundary |
| M04 | Model design | Clarification diffusion | `clarification_diffusion_v33.py` | AVAILABLE | Methods; p and lag described as frozen assumptions |
| M05 | Model design | Renewal demand and loyalty | `purchase_mechanism_v33.py`, `greenconsumer_v33/demand.py` | AVAILABLE | Methods; M described as numerical resolution |
| S01 | System construction | Version-scoped runtime and schema provenance | `task005_fmcg_runtime_v33.py`, `greenconsumer_v33/runner.py` | AVAILABLE | System implementation chapter |
| S02 | System construction | LLM audit/replay and no-direct-purchase boundary | audited router, reflect/plan plugins | AVAILABLE | System implementation and internal validity |
| S03 | System construction | Tests and engineering verification chain | `tests/`, architecture result records | AVAILABLE | Verification subsection, not formal inference |
| S04 | System construction | Fixed-network state/flow animation | `greenconsumer_v33/network_animation.py` | AVAILABLE | System demonstration with fixed-topology caveat |
| E01 | Experiment design | Primary/secondary estimands and analysis family | `FORMAL_EXPERIMENT_PROTOCOL.md` | AVAILABLE | Formal design section |
| E02 | Experiment design | Pilot seed and replication design | Pilot protocol/contract/code | PLANNED_NOT_EXECUTED | Methods as preregistered plan only |
| E03 | Experiment design | Formal N, seed ledger and frozen analysis SHA | not yet created | NOT_AUTHORIZED | No thesis value may be reported yet |
| R01 | Simulation results | v3.3.1 engineering robustness results | `EXPERIMENT_EVIDENCE_REGISTER.md` and committed result records | AVAILABLE | Robustness/verification appendix with engineering label |
| R02 | Simulation results | Selected Real-LLM robustness | committed Real-LLM result record | AVAILABLE | Engineering robustness only |
| R03 | Simulation results | Pilot variance findings | no result exists | PLANNED_NOT_EXECUTED | No finding may be stated |
| R04 | Simulation results | v3.3.1 formal P1/P2/P5 results | no result exists | NOT_AUTHORIZED | No finding may be stated |
| R05 | Simulation results | Cognition-evolution tables/figures | `greenconsumer_v33/cognition_outputs.py` | IMPLEMENTED_NOT_RENDERED | Methods/output capability only; no empirical pattern claim yet |

## 3. Stable output registry

Artifact IDs remain stable even if final thesis table/figure numbering changes.

| Artifact ID | Proposed thesis role | Generated file or source | Unit and interpretation | Status |
|---|---|---|---|---|
| TAB-DESIGN-01 | Run design and provenance | `thesis_outputs/tables/01_run_design.csv` | one completed run | generator available |
| TAB-SEM-01 | Realized semantic manipulation | `04_semantic_manipulation_means.csv` | exposed appraisal records; descriptive | generator available |
| TAB-MECH-01 | Mechanism state by Tick | `08_mechanism_tick_summary.csv` | condition×Tick Agent means | generator available |
| TAB-COG-01 | Verbatim explicit appraisal ledger | `cognition/tables/01_explicit_appraisal_ledger.csv` | actual non-empty explicit appraisal only | IMPLEMENTED_NOT_RENDERED |
| TAB-COG-02 | Cognition state trajectory data | `cognition/tables/02_cognition_tick_summary.csv` | condition×Tick Agent means | IMPLEMENTED_NOT_RENDERED |
| TAB-COG-03 | Pre-specified temporal windows | `cognition/tables/03_cognition_window_summary.csv` | descriptive window means | IMPLEMENTED_NOT_RENDERED |
| TAB-COG-04 | Within-Agent state transitions | `cognition/tables/04_agent_transition_ledger.csv` | Agent-level descriptive differences | IMPLEMENTED_NOT_RENDERED |
| TAB-COG-05 | Transition summary | `cognition/tables/05_transition_summary.csv` | mean/SD across Agents within one run; no inferential SE | IMPLEMENTED_NOT_RENDERED |
| FIG-COG-01 | Trust/Att/SN/intention trajectories | `cognition/figures/01_cognition_state_trajectories.png` | single-run descriptive Agent means | IMPLEMENTED_NOT_RENDERED |
| FIG-COG-02 | T5-to-endpoint transition facets | `cognition/figures/02_recovery_transition_facets.png` | variable-specific-unit panels of single-run mean within-Agent change; cross-panel bar lengths are not comparable | IMPLEMENTED_NOT_RENDERED |
| FIG-COG-03 | Explicit appraisal availability matrix | `cognition/figures/03_explicit_appraisal_availability.png` | condition×Tick record availability, not reasoning quality | IMPLEMENTED_NOT_RENDERED |
| FIG-NET-01 | Network state and information-flow animation | optional GIF from `run_v33_thesis.py` | fixed topology, evolving states/flows | generator available |
| FIG-MECH-01 | Overall mechanism figure | not yet created | semantic→psychological→network→behavior | planned |
| TAB-PILOT-01 | Pilot variance components | future Pilot output | replication-block planning variance | PLANNED_NOT_EXECUTED |
| TAB-FORMAL-01 | Confirmatory P1/P2/P5 | future formal analysis | replication-block inference | NOT_AUTHORIZED |

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
