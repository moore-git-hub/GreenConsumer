# TASK_005 FMCG v3.2 formal N=10 reproducibility archive

## Identity
- Formal batch: `task005-fmcg-v32-formal-n10`
- Model source branch: `redesign/task005-mechanism-v2`
- Model source HEAD: `ef6567adaafcafcf3b9f6884295f509a05ed727e`
- Frozen formal attempts: F001-F010
- Valid blocks: 10/10
- Replacement: none
- Optional stopping: none
- F011+: forbidden under the frozen design

## Directory
- `scripts/`: formal analysis / authorization-check code and exact runner provenance hash
- `contracts/`: seed ledger, scope, runtime, launch, power and execution-authorization contracts
- `evidence/`: machine-readable formal summaries, block estimands, confirmatory/exploratory outputs and closeout record

## Security and closeout
The live activation token is intentionally NOT archived. The formal real-LLM runner is recorded by immutable SHA256 in `scripts/README.md` and the frozen contracts; the completed formal experiment is closed and this post-formal repository is not a new execution authorization.

## Interpretation boundary
The ten blocks quantify stochastic replication uncertainty within the frozen GABM. They are not ten human respondents and do not provide population-sampling inference for real consumers.
