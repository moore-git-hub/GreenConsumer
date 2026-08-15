# Model-to-code traceability — TASK_005 FMCG v3.3.1

## 1. Purpose and evidence boundary

This register maps every current model claim to executable code, recorded output and its permitted thesis use. It supersedes `MODEL_TO_CODE_TRACEABILITY.md` **only for v3.3.1**; the older file remains the traceability record for the closed v3.2 archive.

Rules:

1. A mechanism that cannot be located in canonical code must not be described as implemented.
2. A parameter value is an engineering assumption unless an independently verified empirical source or calibration record is cited.
3. An output field demonstrates implementation or simulated behavior, not real-world validity.
4. v3.2 formal evidence and v3.3.1 engineering/Pilot/formal evidence retain separate identities.

## 2. Model design and system construction

| Layer | Thesis construct or rule | Canonical implementation | Auditable output | Current evidence status |
|---|---|---|---|---|
| Design | 2×2×2 Content × Channel × Timing + common control | `experiment_config.py` | `run_summary.json`, `agent_records.csv` | Implemented; current v3.3.1 formal protocol frozen, formal run not authorized |
| Context | Fictional green FMCG brand, scenario materials and 20 engineering personas | `fmcg_scenario_v32.py` | `agent_records.csv` identity fields | Implemented; personas are mechanism-coverage cases, not population weights |
| Semantic | Valence, arousal, credibility, evidence, relevance, empathy, peer approval, hypocrisy | `mechanism_v32_semantics.py`; `plugins/agent/reflect/GreenCognitionV33Plugin.py` | `agent_thoughts.csv`, `cognitive_records.csv`, LLM audit | Implemented; selected Real-LLM engineering robustness PASS, not external validation |
| Semantic audit | Explicit one-sentence appraisal only | `greenconsumer_v32/runner.py::_agent_thought_rows` | `agent_thoughts.csv` | Implemented; not hidden chain-of-thought |
| Trust | Asymmetric crisis/repair memory, event/quiet partial adjustment, repair saturation, hypocrisy amplifier | `mechanism_v33.py`; `plugins/agent/plan/ConsumerPlanV33Plugin.py` | Trust targets, increments, memory stocks and `trust_final` in `cognitive_records.csv` | Implemented; OAT/boundary/Morris engineering validation completed |
| Attitude | Deterministic bounded attitude update from semantic appraisal | `mechanism_v33.py` | `attitude_att` | Implemented; model-generated state |
| Subjective norm | Peer-only update from actual social observations | `mechanism_v31_cognition.py`; `ConsumerPlanV33Plugin.py` | `subjective_norm_before/after`, social observation count | Implemented; internal-validity checks available |
| PBC | Persona/state input to intention and demand | `ConsumerPlanV33Plugin.py`; `purchase_mechanism_v33.py` | `pbc`, demand records | Implemented; not empirically calibrated |
| Network | Fixed directed BA baseline and social broadcast | `plugins/environment/network/SocialNetworkPlugin.py` | `network_nodes.csv`, `network_edges.csv`, UGC delivery audit | Implemented; topology fixed within a run |
| Targeting | Equal paid-seed allocation with Hub/Random selection | `node_selector.py` | `target_nodes.csv`, targeting audit | Implemented; K is seed allocation, not monetary budget |
| Clarification | Public exposure, lagged paid delivery and probabilistic one-hop amplification | `clarification_diffusion_v33.py`; `task005_fmcg_runtime_v33.py` | exposure plan, reach and effective timeline | Implemented; baseline p=.55, lag=1; engineering sensitivity completed |
| Behavior bridge | TPB-style purchase intention | `purchase_mechanism_v3.py`; `mechanism_v33.py` | `purchase_intention` | Implemented; simulated intention, not observed consumer response |
| Demand | Renewal purchase opportunities, conditional brand choice, bounded-EWMA loyalty | `purchase_mechanism_v33.py`; `greenconsumer_v33/demand.py` | `demand_opportunities.csv`, `choice_curves.csv` | Implemented; M=25 is numerical resolution |
| Runtime | Version-scoped AgentKernel adapter and state restoration | `task005_fmcg_runtime_v33.py` | runtime/code/schema fields in summary and records | Implemented |
| Provenance | Seeds, Git state, schemas, prompt/provider audit and hashes | `greenconsumer_v33/runner.py`; audited router; thesis manifests | `run_summary.json`, audit JSONL, manifests | Implemented for engineering runs |

## 3. Experiment and analysis traceability

| Analysis role | Definition source | Computing code | Evidence status on 2026-08-15 |
|---|---|---|---|
| P1 overall clarification effect on Trust recovery | `FORMAL_EXPERIMENT_PROTOCOL.md` | `greenconsumer_v33/analysis.py`; `pilot_variance.py` | Estimand frozen; v3.3.1 formal estimate not available |
| P2 Rational-evidence vs Emotional-empathy effect on Trust | same | same | Estimand frozen; v3.3.1 formal estimate not available |
| P5 overall clarification effect on expected repeat choice, support absent | same | `greenconsumer_v33/analysis.py`; `pilot_variance.py` | Estimand frozen; v3.3.1 formal estimate not available |
| P3 Immediate vs Delayed | same | `greenconsumer_v33/analysis.py` | Exploratory/mechanism estimand |
| P4 Hub vs Random enterprise reach | same | `greenconsumer_v33/analysis.py` | Exploratory reach estimand; not persuasion or purchase |
| Pilot variance components and planning SD | `TASK_PV01_PILOT_VARIANCE_IMPLEMENTATION.md` | `greenconsumer_v33/pilot_variance.py` | Infrastructure complete; P001–P006 not executed |
| Cognition evolution | this register and `THESIS_WORK_AND_OUTPUT_REGISTER.md` | `greenconsumer_v33/cognition_outputs.py` | Schema 1.2 retained real run verified; limited single-run descriptive engineering evidence only |

## 4. Claim firewall

The following transformations are prohibited in thesis reporting:

- treating LLM appraisal text as direct evidence of real consumer reasoning;
- treating 20 personas or 25 micro-buyers as a population sample;
- treating within-run Agent rows as independent replication blocks;
- calling a fixed-topology animation “network topology evolution”;
- using engineering sensitivity PASS as a formal significance result;
- merging closed v3.2 formal estimates with future v3.3.1 Pilot/formal estimates;
- reporting any planned table or figure as produced before its source run and hash manifest exist.
