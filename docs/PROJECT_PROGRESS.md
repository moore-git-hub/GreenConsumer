# GreenConsumer GABM 项目进度台账

## 1. 台账口径

更新时间：`2026-08-15`

当前分支：`refactor/task005-v32-clean-codebase`

审查基准 HEAD：`7d7a4e595969d6912995c7b7d068144b28d92771`

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
| 15 | Pilot variance执行 | 未开始 | 无Pilot结果 | 先冻结预算、clean SHA并获得明确授权 |
| 16 | 正式N与正式seed ledger | 未开始 | N仍待Pilot | Pilot后按冻结OC规则确定 |
| 17 | v3.3.1正式runner与分析包 | 未开始 | 当前runner仅engineering/demo | 添加测试、合同和SHA冻结 |
| 18 | v3.3.1正式实验 | 未开始 | `FORMAL_NOT_AUTHORIZED` | 协议1.1和明确授权 |
| 19 | 固定拓扑网络状态/传播动画 | 已完成 | `greenconsumer_v33/network_animation.py` | 论文中不得称拓扑演化 |
| 20 | Agent cognition evolution论文输出 | 部分完成 | `cognition_outputs.py`、CLI、tests；显式appraisal与状态轨迹设计已实现 | 在一个保留的真实v3.3.1 run上生成、核对hash并完成视觉QA；不推断隐性CoT |
| 21 | 语义→心理→网络→行为机制总图 | 未开始 | 只有机制诊断图 | 制作与代码traceability一致的论文图 |
| 22 | 论文正文与文献证据映射 | 部分完成 | 第二轮机制统一版、既有文献主题 | 消除旧版本漂移并挂接原始文献 |
| 23 | TASK-PV01零API基础设施 | 已完成 | `pilot_variance.py`、独立CLI、合同、tests | 用户冻结预算并另行授权后才可执行Pilot |
| 24 | 实验结果证据台账与版本分层 | 已完成 | `EXPERIMENT_EVIDENCE_REGISTER.md`；结果记录commits；v3.2 archive | 正式写作时按已建立的table/figure registry持续登记 |
| 25 | 论文工作—证据—表图追踪体系 | 已完成 | `MODEL_TO_CODE_TRACEABILITY_V331.md`、`THESIS_WORK_AND_OUTPUT_REGISTER.md` | 任何新run或正文表图进入论文时同步更新 |

当前计数：

```text
已完成：18
部分完成：2
未开始：5
阻塞：0（当前容器已执行不依赖AgentKernel的测试85项并全部通过；9个测试文件因缺少`agentkernel_standalone`无法收集，仍须在Windows Kernel环境完成全量复验）
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

当前Git checkout中没有持久化这些文献包的完整PDF/Bib元数据；本次工作区已重新出现用户提供的理论文献zip，但尚未完成逐篇解包、书目去重和原文核验。因此现阶段仍不能仅凭主题名称重建作者、年份、题名或DOI。后续论文写作必须遵守：

1. 优先使用用户原始文献包；
2. 包外引用明确标记“包外引用”；
3. 无法核验的理论主张标记“此处需要补充材料”；
4. 不把工程参数写成文献估计值；
5. 不用一般性文献替代模型具体识别条件。

## 6. 下一门槛

真实实验执行的下一门槛固定为：

```text
TASK-PV01-EXEC：在用户批准的成本/时间边界内冻结N_max、
provider-call ceiling和clean execution SHA，并决定是否授权P001-P006。
```

零API基础设施已完成。下一门槛不是继续增加设计因素，而是由用户在真实执行前批准并冻结`N_max`、provider-call ceiling和clean execution SHA；未获得明确真实LLM执行授权前，不运行 P001–P006。

在不触发真实LLM的论文输出工作中，下一步是从已保留且版本匹配的v3.3.1 run目录生成 cognition outputs，核验manifest与图形可读性；在此完成前，项目只记录“生成器已实现”，不记录任何认知演化结果。
