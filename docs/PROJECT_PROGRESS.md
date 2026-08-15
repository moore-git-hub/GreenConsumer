# GreenConsumer GABM 项目进度台账

## 1. 台账口径

更新时间：`2026-08-15`

当前分支：`refactor/task005-v32-clean-codebase`

审查基准 HEAD：`ce736f442c74bef404940f6dcaf8009c4015a1da`

状态定义：

- **已完成**：代码或文档已经存在，并有可定位的测试、结果记录或冻结决策；
- **部分完成**：已有数据或基础实现，但尚未达到论文/正式实验交付门槛；
- **未开始**：尚无对应实现或正式证据；
- **阻塞**：已开始但受缺失依赖、权限、材料或前置决策阻止。

本台账不使用未经加权的“总体完成百分比”。不同事项的科学权重和工作量不同，简单百分比会制造虚假精确性。

## 2. 当前冻结范围

正式处理矩阵固定为：

```text
Rational-evidence / Emotional-empathy
× Hub / Random
× Immediate / Delayed
+ one common NoClarification-Control
```

不增加 Bridge、KOL、独立 credibility、独立 evidence strength、endorsement 或其他正式处理因素。

## 3. 可核验交付物

| ID | 交付物 | 状态 | 主要证据 | 下一门槛 |
|---:|---|---|---|---|
| 01 | 精简代码分支与版本边界 | 已完成 | `CLEAN_CODEBASE_V32.md`、Git历史 | 正式冻结时记录新HEAD |
| 02 | VerdantCo Oat绿色FMCG情境 | 已完成 | `fmcg_scenario_v32.py` | 论文统一替换旧Oatly表述 |
| 03 | 2×2×2+共同Control矩阵 | 已完成 | `experiment_config.py` | 不再扩展正式因素 |
| 04 | v3.3 Trust机制 | 已完成 | `mechanism_v33.py`、DR-20260813-01 | 保持参数冻结 |
| 05 | v3.3澄清扩散 | 已完成 | `clarification_diffusion_v33.py` | 保持p=.55、lag=1 |
| 06 | v3.3 renewal demand | 已完成 | `purchase_mechanism_v33.py`、`greenconsumer_v33/demand.py` | 正式P5固定support absent |
| 07 | T30/T35/T40 horizon robustness | 已完成 | horizon plan/result、Decision Log | T35作为正式endpoint |
| 08 | Trust OAT/边界/Morris | 已完成 | sensitivity plan/result | 不再无止境扩展 |
| 09 | Clarification p×lag sensitivity | 已完成 | clarification plan/result | 作为工程边界证据 |
| 10 | Network topology/orientation/size | 已完成 | network系列plan/result | Hub结论限定边界 |
| 11 | Micro-buyer resolution | 已完成 | micro-buyer plan/result | M=25保持numerical resolution解释 |
| 12 | Selected Real-LLM robustness | 已完成 | `llmrob_20260814_230111`结果记录 | 不作为正式样本 |
| 13 | Provenance、网络和内部有效性输出 | 已完成 | `V331_OUTPUT_AND_VALIDATION.md` | 正式runner复用并加固 |
| 14 | 正式处理、estimand与Pilot协议v1.0 | 已完成 | `FORMAL_EXPERIMENT_PROTOCOL.md` | 保持处理与分析规则冻结 |
| 15 | Pilot variance执行 | 未开始 | `N_max=10`已在结果前冻结；无Pilot结果 | 继续冻结provider-call ceiling、时间预算、clean SHA并获得明确授权 |
| 16 | 正式N与正式seed ledger | 未开始 | N仍待Pilot | Pilot后按冻结OC规则确定 |
| 17 | v3.3.1正式runner与分析包 | 未开始 | 当前runner仅engineering/demo | 添加测试、合同和SHA冻结 |
| 18 | v3.3.1正式实验 | 未开始 | `FORMAL_NOT_AUTHORIZED` | 协议1.1和明确授权 |
| 19 | 固定拓扑网络状态/传播动画 | 已完成 | `greenconsumer_v33/network_animation.py` | 论文中不得称拓扑演化 |
| 20 | Agent cognition evolution论文输出 | 已完成 | 预选Real-LLM run的schema 1.2真实产物已完成provenance、9项输出hash、完整面板、matched-Control算术与视觉审计；用户确认clean commit上的认知直接测试和Windows全量测试均通过 | 仅作为单次工程run的有限描述性证据；不把Agents当重复块、不推断隐性CoT、不作策略排名或总体推断 |
| 21 | 语义→心理→网络→行为机制总图 | 已完成 | `docs/thesis/figures/FIG-MECH-01_v331_mechanism_architecture.svg/.png`；与model-to-code traceability逐层对齐 | 论文排版时只调整编号和尺寸，不改变机制 |
| 22 | 论文正文与文献证据映射 | 部分完成 | 基础包、来源台账、第二章正文底稿、第三章正文底稿及`CITATION_CLAIM_AUDIT_V331.md`已建立；七包57份/53份唯一PDF、5篇同专业硕士论文、4项中文核心文献和4项包外补充文献已登记 | 完成第四章前半部分、ODD附录及后续章节；继续按需核验新增文献 |
| 23 | TASK-PV01零API基础设施 | 已完成 | `pilot_variance.py`、独立CLI、合同、tests | 用户冻结预算并另行授权后才可执行Pilot |
| 24 | 实验结果证据台账与版本分层 | 已完成 | `EXPERIMENT_EVIDENCE_REGISTER.md`；结果记录commits；v3.2 archive | 正式写作时按已建立的table/figure registry持续登记 |
| 25 | 论文工作—证据—表图追踪体系 | 已完成 | `MODEL_TO_CODE_TRACEABILITY_V331.md`、`THESIS_WORK_AND_OUTPUT_REGISTER.md` | 任何新run或正文表图进入论文时同步更新 |

当前计数：

```text
已完成：20
部分完成：1
未开始：4
阻塞：0（schema 1.2代码commit `ce736f442c74bef404940f6dcaf8009c4015a1da`的两项指定Windows `Kernel`测试由用户确认均通过；本轮未回传测试数量和用时，故不补写未观察值）
```

## 4. 论文稿与当前代码的版本漂移

仓库中的“第二轮机制统一版”可保留 PSSS 理论框架、生成式语义评估—确定性状态更新、内容—渠道—时机主线和模型外推边界，但以下表述已经落后于当前实现：

| 论文旧稿表述 | 当前事实 | 处置 |
|---|---|---|
| Oatly/现实品牌语境 | 虚构品牌 `VerdantCo Oat` | 论文统一为虚构情境，避免未经授权的品牌事实主张 |
| N=40或旧Persona配额 | N=20 Engineering Personas | 按当前场景与代码重写 |
| T30 baseline | T35 baseline；T30/T40 robustness | 第四、五章统一时间设计 |
| 旧shock_anchor/fatigue Trust叙事 | v3.3 asymmetric memory、partial adjustment、repair saturation、hypocrisy | 按 `mechanism_v33.py` 重写公式与文字 |
| 语义指标未单独输出 | 当前输出valence、arousal、credibility、evidence、relevance、empathy、peer approval、hypocrisy | 按v3.3.1 schema更正 |
| 旧即时/延迟Tick | Crisis=T5、Immediate=T6、Delayed=T10 | 全文统一 |
| 企业澄清可能与危机同Tick | 当前Immediate为危机后1 Tick | 不得继续写“同一时间步同时接收” |

上述漂移不说明旧稿“无效”，但旧稿不能作为当前代码事实的证据。论文方法章节最终版必须通过 model-to-code traceability 审计。

## 5. 文献与资料证据台账

用户此前提供的论文与资料应继续服务于以下证据模块：

- 竞争信息场、情绪效价×唤醒、可信线索与负面信息不对称；
- 简单传染、复杂传染、重复暴露和社会强化；
- 同质性、选择偏差、强弱关系、结构洞、桥接、回音室与极化；
- 算法推荐暴露和BA/WS/ER/社群网络适用边界；
- ODD、ODD+D、ABM verification and validation；
- pattern-oriented modeling、敏感性、校准与复现；
- face validity、micro-validity、macro-validity；
- generative explanation 与 model docking/cross-model comparison。

本次已解包并清点用户提供的七个理论文献包：共57份PDF，4组重复，SHA-256去重后为53份唯一PDF；另审阅5篇同专业硕士论文以提取章节、标题层级、图表注释和结果讨论风格。核心英文文献已用PDF原文和出版社/期刊页面交叉核验；四项进入当前正文的中文文献已完成作者、年份、题名及出版身份核验，其余中文来源仍按需要逐篇处理。详细清单、核验状态和章节路由见`docs/thesis/LITERATURE_AND_STYLE_SOURCE_REGISTER.md`。后续论文写作必须遵守：

1. 优先使用用户原始文献包；
2. 包外引用明确标记“包外引用”；
3. 无法核验的理论主张标记“此处需要补充材料”；
4. 不把工程参数写成文献估计值；
5. 不用一般性文献替代模型具体识别条件。

第二章与第三章正文底稿已在对应句段使用“作者、年份、题名”引用，并通过`docs/thesis/CITATION_CLAIM_AUDIT_V331.md`记录每项来源的允许用途和禁止外推。论文正文事项仍保持“部分完成”，因为第四章、ODD附录、第五章正式结果和第六章尚未完成；不以已写两章虚增总体完成度。

## 6. 下一门槛

真实实验执行的下一门槛固定为：

```text
TASK-PV01-EXEC：在已冻结N_max=10的前提下，继续冻结
provider-call ceiling、时间预算和clean execution SHA，并决定是否授权P001-P006。
```

零API基础设施已完成。用户已在查看Pilot结果前冻结`N_max=10`；该值是正式replication-block预算上限，不是Pilot规模，也不是已证明的正式样本量。下一门槛不是继续增加设计因素，而是冻结provider-call ceiling、时间预算和clean execution SHA；未获得明确真实LLM执行授权前，不运行P001–P006。若Pilot后的预设operating-characteristic规则在N=10时不能同时满足三项确认性检出概率门槛，则记录`DESIGN_NOT_FEASIBLE_WITHIN_CAP`，不得事后提高N或放宽标准。

不触发真实LLM的认知输出工作包已经关闭：预选的同一v3.3.1 run已生成schema 1.2产物，manifest中的9项输出均完成独立hash复核；`06_control_adjusted_agent_recovery.csv`的1120行完整，matched-Control算术与源Agent ledger在浮点容差内一致；三张图完成视觉审查；用户确认clean代码commit上的认知直接测试和Windows全量测试均通过。该产物仅升级为单次Real-LLM工程run的有限描述性证据，不升级为Pilot或正式推断，不形成稳定策略排名。
