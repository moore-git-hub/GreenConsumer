# Model-to-code traceability — TASK_005 FMCG v3.2

| 论文/模型构件 | Canonical code | 作用 |
|---|---|---|
| 实验矩阵 | `experiment_config.py` | Content × Channel × Timing + common control |
| FMCG 情境与画像 | `fmcg_scenario_v32.py` | VerdantCo Oat、20 personas、危机/澄清/支持材料 |
| 语义 schema | `mechanism_v32_semantics.py` | 语义字段及 peer-approval 严格校验 |
| LLM 语义评估 | `plugins/agent/reflect/GreenCognitionV32Plugin.py` | 仅解释实际 observations，不直接决策购买 |
| Trust / Att / memory | `mechanism_v2.py` | 心理状态核心转移与记忆衰减 |
| Subjective Norm | `mechanism_v31_cognition.py` | SN 只由真实 social observations 的 peer approval 更新 |
| v3.2 Plan | `plugins/agent/plan/ConsumerPlanV32Plugin.py` | 整合认知状态、TPB intention 与发帖 |
| 网络拓扑 | `plugins/environment/network/SocialNetworkPlugin.py` | 有向 BA 网络与社会广播 |
| Hub / Random | `node_selector.py` | 等预算渠道种子选择 |
| 澄清 reach | `clarification_injector.py` | public / paid seed / one-hop exposure |
| TPB intention bridge | `purchase_mechanism_v3.py` | extended-TPB intention 函数来源 |
| FMCG repeat-choice core | `purchase_mechanism_v31.py` | opportunity、choice、loyalty、PBC facilitation |
| Persona→demand | `purchase_mechanism_v32.py` | v3.2 画像到 demand layer 的透明工程映射 |
| v3.2 runtime | `task005_fmcg_runtime_v32.py` | version-scoped patch 与运行后恢复 |
| LLM audit | `task005_fmcg_audited_router_v32.py` | prompt/response hash 与 schema audit |
| Formal runner provenance | `reproducibility/formal_v32_n10/scripts/README.md` | 冻结正式 runner SHA 与 closeout 边界 |
| Formal analysis | `reproducibility/formal_v32_n10/scripts/analyze_task005_fmcg_formal_v32_n10.py` | P1/P2/P5 Holm confirmatory + P3/P4 exploratory |
| Formal closeout | `reproducibility/formal_v32_n10/evidence/` | 正式统计结果与关闭记录 |

## Traceability rule
论文中的任何机制性表述应能定位到本表中的代码模块；无法定位的机制不得在论文中描述为已实现模型规则。
