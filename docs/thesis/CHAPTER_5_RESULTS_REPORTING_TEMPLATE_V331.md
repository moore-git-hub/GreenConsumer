# 第五章 仿真结果与机制讨论（正式结果报告模板）

## 5.1 本章任务与结果准入边界

> **当前状态：模板已冻结，Pilot未执行，正式实验未获授权，正式结果为零。**

本章模板用于在v3.3.1正式实验完成后按预先规定的顺序报告结果。模板中的`[[待填]]`只能由通过validity gate、具备完整seed与hash provenance、且来自协议1.1冻结分析代码的正式replication blocks填入。不得以既有Fake运行、工程稳健性运行、单次Real-LLM认知运行或Pilot均值填充正式结果位置。

结果报告遵循“样本流转与数据质量—确认性结果—探索性机制—有限描述性认知证据—工程稳健性—理论讨论”的顺序。先呈现估计值与不确定性，再作理论解释；不得根据曲线外观、单个Agent或单个block先宣布策略胜者。

### 5.1.1 结果准入清单

| 项目 | 正式填写位置 | 准入条件 |
|---|---|---|
| 协议版本 | `[[protocol_version]]` | 必须为冻结正式N和seed ledger后的1.1或更高预登记版本 |
| 执行代码SHA | `[[execution_sha]]` | clean worktree，且与执行授权一致 |
| 分析代码SHA | `[[analysis_sha]]` | 在正式结果生成前冻结 |
| 有效block数 | `[[N_valid]]` | 只能计入通过全部validity gate的完整九条件blocks |
| 尝试与失败记录 | `[[attempt_ledger_path]]` | 包括技术重启、无效block及原因，不得静默删除 |
| 结果hash manifest | `[[manifest_path]]` | 原始输出、分析表与图均可追溯 |
| 正式推断状态 | `[[inference_status]]` | 未完成全部门禁时保持`NOT_AUTHORIZED` |

## 5.2 正式样本流转、数据质量与区组描述

### 5.2.1 Block流转

**表5-1 正式replication blocks流转表（空表）**

| 项目 | 数量 | 说明 |
|---|---:|---|
| 协议1.1计划blocks | `[[N_planned]]` | 冻结值 |
| 已启动唯一block IDs | `[[N_started]]` | 不把技术重试重复计数 |
| 技术失败attempts | `[[N_technical_attempts]]` | 保留相同seed重启记录 |
| 完成但validity gate失败blocks | `[[N_invalid]]` | 逐项列明失败原因 |
| 有效正式blocks | `[[N_valid]]` | 应与正式分析输入一致 |
| 未执行/中止blocks | `[[N_not_completed]]` | 说明是否触发协议停止条件 |

正文模板：

> 正式实验依据协议`[[版本]]`计划执行`[[N_planned]]`个独立replication blocks。最终`[[N_valid]]`个blocks通过全部有效性门禁，`[[N_invalid]]`个完整blocks未被准入，原因见`[[附录/表号]]`。所有技术重试沿用原seed和冻结代码，并保留在attempt ledger中。以下推断以完整block为统计单位；Agent、Agent×Tick、provider call及micro-buyer均未作为独立样本。

### 5.2.2 Block值透明披露

对P1、P2和P5分别绘制全部block值，不隐藏零值、极端值或方向相反值。

- **图5-1**：P1全部block值、均值、95%普通CI与零线；
- **图5-2**：P2全部block值、均值、95%普通CI与零线；
- **图5-3**：P5全部block值、均值、95%普通CI与零线；
- **附图5-A1—A3**：三项estimand的Q-Q图与leave-one-block-out结果。

图注必须注明：点代表独立replication blocks；横/纵轴保留各estimand原单位；设计阈值线不代表经验效应或现实决策收益。

## 5.3 确认性结果：P1、P2与P5

### 5.3.1 主分析表

**表5-2 确认性estimands的block-level主分析与预设诊断（空表）**

| Estimand | 有效N | Mean | SD | SE | 95%普通CI | Raw p | Holm p | Holm decision | 预设设计阈值 | 阈值分类 | Exact sign-flip Holm p | LOBO符号稳定 | LOBO Holm决策变化 | 证据标签 |
|---|---:|---:|---:|---:|---|---:|---:|---|---:|---|---:|---|---|---|
| P1 | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ , ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | 0.15 Trust points | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` |
| P2 | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ , ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | 0.15 Trust points | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` |
| P5 | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ , ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | 0.05 expected-choice share | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` |

表注：主分析为双侧one-sample t-test versus 0，三项p值采用Holm step-down控制family-wise alpha=.05（Holm，1979，《A Simple Sequentially Rejective Multiple Test Procedure》）。Exact sign-flip为独立的预设敏感性family，不替换主分析；其置换参考分布和适用条件见`SMALL_N_DIAGNOSTIC_PROTOCOL_V331.md`（Ernst，2004，《Permutation Methods: A Basis for Exact Inference》）。

### 5.3.2 写作句式：必须按观察结果选择，不能提前补方向

**情形A：主分析拒绝且预设敏感性一致**

> P`[[编号]]`的block-level平均对比为`[[mean和单位]]`，95%普通置信区间为`[[下限，上限]]`。其Holm调整p值为`[[p]]`，在三项确认性family中`[[拒绝/不拒绝]]`零假设。Exact sign-flip Holm结果为`[[ ]]`，leave-one-block-out分析显示`[[符号与决策稳定性]]`，故本结果标记为`[[证据标签]]`。该结论仅指冻结模型和预设随机来源下的模型内对比。

**情形B：主分析拒绝但诊断不一致**

> P`[[编号]]`的主分析达到Holm拒绝标准，但exact sign-flip或leave-one-block-out结果未保持一致，因此标记为`PRIMARY_SUPPORTED_BUT_DIAGNOSTICALLY_FRAGILE`。正文同时报告不一致位置，不将其写为稳健策略优势，也不依据敏感性结果更换主检验。

**情形C：主分析未拒绝**

> P`[[编号]]`的Holm调整p值为`[[p]]`，本研究未在预设family-wise alpha下拒绝零假设。该结果表示现有N与模型波动下证据不足，不等于证明效应为零。估计值、区间、预设设计阈值分类及敏感性结果仍完整报告。

### 5.3.3 设计阈值的解释

阈值分类与显著性结论必须分开。`|mean|≥阈值`只能写为“达到或超过预先设定的设计阈值”，不能自动写为“具有管理意义”；`|mean|<阈值`也不能写成等效性结论。本研究未预设等效性界值或非劣效检验。

## 5.4 探索性与机制性结果：P3和P4

**表5-3 探索性estimands的block-level描述统计（空表）**

| Estimand | N | Mean | SD | Median | IQR | Min | Max | 对应图 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| P3：Immediate−Delayed早期Trust AUC | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[图号]]` |
| P4：Hub−Random直接企业触达 | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[图号]]` |

P3和P4不计算确认性p值，不进入Holm family，不使用“显著”“支持假设”或“无效”等语言。P4只反映直接企业触达；即使其数值较大，也不能代替Trust或expected-choice结果。有限种子节点选择会改变潜在影响范围，但覆盖并不自动等于复杂行为扩散或购买改善（Kempe、Kleinberg、Tardos，2003，《Maximizing the Spread of Influence through a Social Network》；Centola、Macy，2007，《Complex Contagions and the Weakness of Long Ties》）。

## 5.5 条件轨迹与语义操纵检查

### 5.5.1 正式条件轨迹

建议图表位置：

- **图5-4**：九条件Trust均值轨迹，标记T5、T6和T10；
- **图5-5**：九条件purchase intention轨迹；
- **图5-6**：expected focal-brand choice share轨迹；
- **表5-4**：八策略单元与控制组的T5、T6、T10、T35描述统计。

轨迹图必须显示block间不确定性或全部block细线，不能只绘制跨block均值造成确定性错觉。单元格排序属于描述性结果，不构成新增确认性比较。

### 5.5.2 Realized semantic appraisal

**表5-5 处理条件下已观察语义评价的操纵检查（空表）**

| 条件/因素 | 有appraisal记录数 | Credibility | Evidence strength | Empathy | Valence | Arousal | Hypocrisy | 解释边界 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | `[[ ]]` | LLM结构化评价，不是消费者量表 |

操纵检查回答文本框架在运行中是否产生可观察的语义区分，不把某个语义维度的差异解释为P2的独立中介效应。双过程理论可说明论据与来源线索可能进入不同加工路径，但当前模型未直接识别系统加工或启发式加工潜变量（Chaiken，1980，《Heuristic versus systematic information processing and the use of source versus message cues in persuasion》）。

## 5.6 单次Real-LLM认知证据的独立呈现

预选工程run的FIG-COG-01—03与TAB-COG-01—06只能放入“实现与机制示例”子节，并在标题或图注明示“单次Real-LLM工程run；非正式样本”。允许描述显式appraisal可用率、Agent均值轨迹及同一Agent相对控制的异质性；禁止计算跨Agent标准误、p值或将20个engineering personas外推为消费者总体。

LLM Agent研究表明自然语言Agent可用于受控行为模拟，但复现部分人类模式并不自动建立现实行为有效性（Aher、Arriaga、Kalai，2023，《Using large language models to simulate multiple humans and replicate human subject studies》）。因此，本节只作为审计和机制可见性材料，不用于替代5.3节的正式区组推断。

## 5.7 工程稳健性与正式结果的关系

**表5-6 工程稳健性—正式结果边界汇总（模板）**

| 模块 | 已有工程证据 | 与正式结果共同解释的方式 | 不允许的推断 |
|---|---|---|---|
| Trust参数 | OAT、边界、Morris | 说明正式结果对冻结engineering envelope的敏感边界 | 参数已被现实数据校准 |
| 澄清扩散 | p×lag profiles | 说明timing/reach依赖投递速度 | p=.55、lag=1现实最优 |
| 网络 | topology、orientation、N/K | 说明P4及下游效应的结构适用条件 | BA或Hub代表现实平台最优方案 |
| Micro-buyer | M=10/25/50 | 说明P5对需求数值分辨率的工程稳定性 | M增加正式样本量 |
| Real-LLM | prompt版式与runtime重复 | 说明schema和方向在有限工程扰动下可运行 | LLM无偏或等同真实消费者 |

Morris方法用于多参数全局筛查而非现实参数贡献估计（Morris，1991，《Factorial Sampling Plans for Preliminary Computational Experiments》）。ABM验证与校准仍受经验目标、模型识别和计算预算限制；工程稳健性不能替代现实数据校准（Platt，2020，《A comparison of economic agent-based model calibration methods》；Grazzini、Richiardi、Tsionas，2017，《Bayesian estimation of agent-based models》）。

## 5.8 机制讨论的证据链

讨论段落必须按“观察结果—模型机制—文献接口—替代解释—边界”展开，而不是只重复数值。

| 讨论主题 | 只在相应结果存在时使用的理论接口 | 必须保留的替代解释 |
|---|---|---|
| 内容框架 | Chaiken（1980）《Heuristic versus systematic information processing and the use of source versus message cues in persuasion》；Berger、Milkman（2012）《What makes online content viral?》；Lewicki、Brinsfield（2017）《Trust repair》 | 两套文本同时改变多个语义维度；P2不能拆成单一credibility或empathy效应 |
| 回应时机 | Yao等（2019）《The quicker, the better? The antecedents and consequences of response timing strategy in the aftermath of a corporate crisis》；Kim、Dirks、Cooper（2009）《The repair of trust: A dynamic bilateral perspective and multilevel conceptualization》 | T6/T10是设计窗口；事件调整率决定模型内早期路径 |
| 投放渠道 | Barabási、Albert（1999）《Emergence of scaling in random networks》；Kempe、Kleinberg、Tardos（2003）《Maximizing the Spread of Influence through a Social Network》；Centola、Macy（2007）《Complex Contagions and the Weakness of Long Ties》 | Hub效果依赖拓扑、边方向、K/N及传播机制；reach不等于说服 |
| 重复品牌选择 | Ajzen（1991）《The theory of planned behavior》；Guadagni、Little（1983）《A Logit Model of Brand Choice Calibrated on Scanner Data》 | P5是模型expected share；没有现实扫描面板校准 |
| GABM有效性 | Aher、Arriaga、Kalai（2023）《Using large language models to simulate multiple humans and replicate human subject studies》；Adornetto等（2025）《Simulating Human Behavior with Large Language Models: A Systematic Review of Agent-Based Approaches》 | 语义评价尚无消费者criterion validation；工程复现不等于外部有效 |

### 5.8.1 讨论段落模板

> P`[[编号]]`显示`[[只陈述估计与不确定性]]`。在冻结模型内部，该结果可能通过`[[对应已实现机制]]`形成。`[[作者，年份，题名]]`为这一机制提供构念层解释，但并不验证本研究的具体参数或现实效应量。另一种解释是`[[结构、文本复合、随机波动或测量边界]]`。因此，本研究可支持的结论限定为`[[模型内结论]]`，不能扩展为`[[现实最优/总体因果/个体心理真值]]`。

## 5.9 本章小结（待正式结果后填写）

本节只按P1、P2、P5、P3和P4顺序总结已经报告的证据，不引入新检验。建议结构为：

1. `[[P1确认性结论与脆弱性标签]]`；
2. `[[P2确认性结论与复合内容边界]]`；
3. `[[P5确认性结论与expected-choice边界]]`；
4. `[[P3/P4探索性机制]]`；
5. `[[工程稳健性与外部有效性限制]]`。

无论结果方向如何，均不得将“未拒绝”写成“证明无效”，不得将单次工程run或Agent异质性替代正式block推断，也不得在本章首次引入未预登记的确认性比较。
