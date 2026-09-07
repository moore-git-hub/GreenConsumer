# GreenConsumer TASK_005 v3.3.1 正式实验协议

## 0. 协议身份

| 字段 | 冻结值 |
|---|---|
| 协议版本 | `1.0.4` |
| 协议日期 | `2026-08-16` |
| 代码分支 | `refactor/task005-v32-clean-codebase` |
| 协议起草时 HEAD | `7d7a4e595969d6912995c7b7d068144b28d92771` |
| 模型版本 | `TASK_005_FMCG_V3.3.1` |
| 当前状态 | `PILOT_DESIGN_24_BLOCKS_FROZEN; N_MAX_CANCELLED; EXECUTION_SHA_AND_COST_RECONFIRMATION_PENDING; PILOT_NOT_EXECUTED; FORMAL_NOT_AUTHORIZED` |
| 论文用途 | 工商管理硕士论文的正式实验准备与方法审计 |

本协议冻结 v3.3.1 的处理矩阵、研究问题、estimand、推断单位、Pilot 方差设计、失败规则与正式样本量选择规则。用户已接受24-block Pilot和取消正式`N_max`的科学修订；真实执行仍须新候选SHA通过Windows完整回归、clean SHA落盘并重新确认行政费用边界。正式实验仍未授权。

### 0.1 Pilot规模与正式N修订记录

用户于2026-08-16在任何有效v3.3.1 Pilot observation产生前取消`N_max=10`。科学所需正式N不得再被预算上限截断：先按第7节计算`N_required`，再单独判断资源可行性。Pilot由原3×2扩展为6个simulation/network seeds×4个requested LLM seeds，共24个独立cognitive blocks；P001–P006身份保留，P007–P024补全网格。每个block离线交叉24个demand seeds，共576个P5条件性realizations，但独立推断单位仍只有24个cognitive blocks。

24-block规模依据方差估计精度而非效应均值选择：单侧90%卡方SD上界膨胀因子在n=24时约为1.245，低于预设25%容忍界；n=6时约为1.762。Pilot operational caps暂按4800次provider calls和8小时实现，但CNY费用容忍度须在真实执行前重新确认。这些运行限额不得解释为正式N的科学上限。

### 0.3 Pilot前模型版本修订记录

协议1.0.3在任何有效Pilot block产生前，把v3.3.1 Real-LLM模型由滚动别名固定为
`qwen-plus-2025-12-01`。共享YAML和v3.2 runner继续保持`qwen-plus`，避免改写已关闭
的v3.2执行路径；v3.3.1在router构造时只作内存内版本覆盖。此前五个Real-LLM
稳健性blocks按历史运行元数据继续记为`qwen-plus`，不得追溯性重标为具体版本。

### 0.2 小样本诊断修订记录（历史触发条件）

`SMALL_N_DIAGNOSTIC_PROTOCOL_V331.md`最初针对N=10冻结。取消`N_max`后，其中全block披露、Q-Q图、MAD影响提示、联合leave-one-block-out与sign-flip/Holm敏感性仍保留；N≤20时完整枚举，N>20时使用预先冻结的Monte Carlo次数和种子。主分析仍为本协议8.1节的双侧one-sample t-test与Holm family。P1/P2/P5阈值仍为0.15/0.15/0.05，管理依据缺口未解决，当前不得称为管理上重要差异。

## 1. 科学范围与版本边界

研究情境冻结为虚构绿色 FMCG 品牌 `VerdantCo Oat` 的植物奶漂绿危机与企业澄清。研究目标是在受控 GABM 中识别澄清内容、网络投放渠道和澄清时机对信任恢复、企业直接触达及预期重复品牌选择的模型内影响。

本研究不复刻现实市场，也不把 20 个 cognitive Agents 或每个 Agent 下的 micro-buyers 解释为现实消费者样本。v3.3.1 的正式推断范围仅限：在冻结模型、冻结处理、冻结分析规则和预先生成随机种子的条件下，estimand 在独立 replication blocks 之间的不确定性。

以下版本边界不可突破：

- v3.2 的 F001–F010 是已关闭的历史正式样本，不得复用、扩展或合并进入 v3.3.1；
- 已完成的 Fake、Real-LLM robustness、敏感性和网络稳健性运行均属于 engineering validation，不是 v3.3.1 Pilot 或正式样本；
- Pilot 只用于方差和 operating-characteristic 规划，不用于正式效应检验；
- 正式实验开始后，不得因效应大小、方向、显著性或图形表现修改机制、prompt、参数、estimand、MDE 或样本量。

## 2. 研究问题

### RQ1：澄清内容

在其他处理维度保持平衡时，理性证据型澄清与情感共情型澄清对危机后信任恢复的模型内效应有何差异？

`Rational-evidence` 与 `Emotional-empathy` 均为复合内容策略。P2 只能识别两类完整文本框架的总体差异，不能拆解为证据强度、可信度、情绪效价、唤醒或共情的独立因果效应。

### RQ2：投放渠道

在相同 paid-seed 预算下，Hub 投放与 Random 投放对企业澄清直接触达范围有何差异，该结构差异是否伴随信任和重复品牌选择轨迹的描述性变化？

Hub 只表示基于当前有向网络出度的结构性选点。Hub 增加 reach 不等于增加说服、信任或购买；其作用边界依赖网络拓扑、边方向和 hub distinguishability。

### RQ3：澄清时机

在其他处理维度保持平衡时，即时澄清与延迟澄清对危机早期信任轨迹有何差异？

Immediate 和 Delayed 是预设时间窗口，不代表现实世界中普适的最优响应时点。

### 总体澄清效应

共同 `NoClarification-Control` 用于估计八个冻结澄清处理单元等权平均相对于不澄清的总体模型内效应。该等权平均是预先规定的模型内汇总，不代表现实企业采用八类策略的频率或混合比例。控制组不是 timing 的第三个水平，不进入 2×2×2 因子编码。

## 3. 正式处理矩阵

正式设计仅包含 Content × Channel × Timing 三个二元因素以及一个共同控制组，不增加 Bridge、KOL、独立 credibility、独立 evidence strength、endorsement 或其他正式处理因素。

| 条件 ID | Content | Channel | Timing | 澄清 Tick | Paid seeds K |
|---|---|---|---|---:|---:|
| `Rational-Hub-Immediate` | rational-evidence | hub | immediate | 6 | 3 |
| `Rational-Hub-Delayed` | rational-evidence | hub | delayed | 10 | 3 |
| `Rational-Random-Immediate` | rational-evidence | random | immediate | 6 | 3 |
| `Rational-Random-Delayed` | rational-evidence | random | delayed | 10 | 3 |
| `Empathy-Hub-Immediate` | emotional-empathy | hub | immediate | 6 | 3 |
| `Empathy-Hub-Delayed` | emotional-empathy | hub | delayed | 10 | 3 |
| `Empathy-Random-Immediate` | emotional-empathy | random | immediate | 6 | 3 |
| `Empathy-Random-Delayed` | emotional-empathy | random | delayed | 10 | 3 |
| `NoClarification-Control` | not-applicable | not-applicable | no-clarification | 无 | 0 |

八个策略单元完全交叉且等权。八单元结果可以逐格描述，但本协议不新增确认性交互 estimands；未在正式执行前通过协议修订冻结的交互分析只能标记为探索性。

## 4. 冻结模型设置

| 层面 | 冻结设置 | 解释边界 |
|---|---|---|
| 时间 | Crisis=T5；Immediate=T6；Delayed=T10；endpoint=T35 | 1 Tick 定义为 1 simulation day；不是现实最优窗口估计 |
| Cognitive Agents | N=20 | mechanism-coverage panel，不是现实样本量 |
| Demand resolution | M=25 micro-buyers/Agent | numerical resolution，不是独立统计样本 |
| Network | 有向 BA baseline | Hub 效应依赖当前拓扑与方向定义 |
| Paid targeting | K=3 | 等 seed-count 预算，不代表货币预算 |
| Paid amplification | edge probability=.55；delivery lag=1 | engineering assumptions，已做敏感性分析但未经验校准 |
| Trust | v3.3.1 asymmetric memory、partial adjustment、repair saturation、hypocrisy amplifier | 参数为 engineering assumptions |
| Demand | renewal purchase opportunities；bounded-EWMA loyalty | 未经验校准 |
| Real LLM | `qwen-plus-2025-12-01`；temperature=.3；prompt=`baseline_exact` | LLM 只执行语义 appraisal，不直接决定购买；v3.2路径不变 |
| Conversion support | 正式 P5 固定为 `absent` | 不构成第四个正式因子；present 仅保留为既有工程诊断 |

以上设置只能因预先记录的实现缺陷、测量完整性问题或不可执行性而修改。任何修改必须先写入 `MODEL_DESIGN_DECISION_LOG.md`，生成新协议版本，并说明旧 Pilot/正式结果是否作废。

## 5. Estimands 与分析角色

所有 estimands 先在单个完整 replication block 内计算，再以 block 为正式统计单位。Agent、Agent×Tick、condition 内消息、provider call 和 micro-buyer 均不得作为独立推断单位。

### 5.1 确认性 family

确认性 family 固定为 P1、P2、P5，共三项。

#### P1：总体澄清对危机后 Trust 的影响

```text
P1 = mean(AUC_T6:T35 of eight clarification cells)
     - AUC_T6:T35 of common control
```

AUC 使用完整 T6–T35 Tick 序列的标准化梯形面积，单位为 Trust points。

#### P2：内容框架对危机后 Trust 的影响

```text
P2 = mean(AUC_T6:T35 of four Rational-evidence cells)
     - mean(AUC_T6:T35 of four Emotional-empathy cells)
```

P2 是复合文本框架对比，不允许解释为 evidence strength、credibility 或 emotion 的独立效应。

#### P5：总体澄清对预期重复品牌选择的影响

```text
P5 = mean(expected focal-brand choice share, eight clarification cells,
          conversion_support=absent, T6:T35)
     - corresponding common-control value
```

P5 使用模型概率生成的 expected choice share。realized choices 只作为描述性一致性检查，不替代 P5，也不把 micro-buyers 当作独立样本。

### 5.2 探索性/机制性 estimands

#### P3：即时相对延迟的危机早期 Trust

```text
P3 = mean(AUC_T6:T9 of four Immediate cells)
     - mean(AUC_T6:T9 of four Delayed cells)
```

P3 只刻画延迟策略尚未启动前的模型内早期窗口，不进行确认性显著性声明。

#### P4：Hub 相对 Random 的企业直接触达

```text
P4 = mean(eventual direct-enterprise reach of four Hub cells)
     - mean(eventual direct-enterprise reach of four Random cells)
```

reach 定义为配置窗口 `t0..t0+lag` 内直接观察到企业澄清的 cognitive Agents 并集比例，不包含下游 UGC 说服或购买。P4 不计算确认性 p-value。

### 5.3 既有工程诊断的处置

`S1_CONVERSION_SUPPORT_EXPECTED_REPEAT_CHOICE_V33` 不进入本次正式 treatment matrix、确认性 family 或正式样本量规划。既有 support-present 结果只能作为工程机制分离证据，不得被写成新增的第四个正式因素。

## 6. Pilot 方差设计

### 6.1 Pilot 目的

Pilot 只用于：

- 估计 P1、P2、P5 的 block-level planning variance；
- 描述 simulation/network、requested-LLM/provider 和 offline-demand 三类随机来源对结果波动的相对贡献；
- 选择正式 replication-block 数量；
- 验证正式 runner、seed ledger、block validity 和分析代码的可执行性。

Pilot 禁止计算或报告正式 p-value、置信区间、显著性、策略胜者或论文实证结论。Pilot 的均值、符号和策略排序不得用于修改模型或选择 estimand。

### 6.2 Pilot cognitive grid

Pilot cognitive grid预设为6个simulation/network seeds×4个requested LLM seeds，共24个完整cognitive blocks。simulation/network seeds为`2026081501..2026081506`，requested LLM seeds为`2026081601..2026081604`。P001–P006保留协议1.0中的原始配对和ID，P007–P024补全剩余18个交叉单元；完整逐行映射以`task_pv01_pilot_variance_contract1.1.json`为机器可读唯一来源。

这一交叉设计用于工程性方差分解，不把24个Pilot blocks当作正式样本。requested seed不被视为provider完全确定性的保证；LLM分量应解释为requested-seed与实际provider/runtime variability的合成波动。Pilot规模不由观察效应、显著性或策略排序决定。

当前 baseline runner 未把 network seed 与 simulation seed 完全拆分，因此 Pilot 只能估计联合的 simulation/network 分量，不能声称单独识别 network variance。

### 6.3 Demand-only 交叉

每个已完成的cognitive block使用24个预设demand seeds进行离线demand replay：

```text
D1..D24 = 2026081701..2026081724
```

由此得到24×24=576个P5 demand realizations，但同一cognitive block内的24个replays共享cognitive history，不能作为576个独立replication blocks。它们只用于估计demand-layer variance component；正式P5 planning variance必须以24个cognitive blocks为独立层级，并报告方差分量模型依赖性。

### 6.4 Pilot 输出

Pilot 实现必须至少生成：

- `pilot_seed_ledger.csv`；
- `pilot_attempt_ledger.csv`；
- `pilot_block_estimands.csv`；
- `pilot_demand_estimands.csv`；
- `pilot_variance_components.csv`；
- `pilot_planning_sd.csv`；
- `pilot_operating_characteristics.csv`；
- `pilot_formal_n_selection.csv`；
- `pilot_summary.json`；
- 每项文件的 SHA-256 manifest。

方差分解必须同时报告 raw component、占总方差比例、估计方法和小样本不稳定性警告。若某个分量被估计为边界零，不得解释为该随机来源不存在。

## 7. 正式样本量选择规则

### 7.1 Managerial MDE

为避免根据 v3.3.1 Pilot 结果事后改变效应门槛，暂沿用历史 v3.2 中在结果分析前冻结的量纲一致阈值：

| Estimand | Managerial MDE |
|---|---:|
| P1 | 0.15 Trust points |
| P2 | 0.15 Trust points |
| P5 | 0.05 expected-choice share |

这些 MDE 是研究设计阈值，不是经验估计或文献事实。论文中若要将其称为“管理上重要”，必须补充管理决策依据；在该依据尚未完成前，应写为“预先设定的设计阈值”。不得因 Pilot 均值偏小或偏大而修改。

### 7.2 Operating-characteristic 规则

正式N从满足`N≥10`的整数中向上搜索，不设科研样本量上限。逐N同时检验全部预设相关结构场景，并把所有场景在同一N上同时符合以下条件的最小值作为`N_required`；另行报告各场景首个通过N：

1. P1、P2、P5在各自single-MDE场景下的边际检出概率均不低于.90；
2. 三项确认性检验使用 Holm step-down，family-wise alpha=.05；
3. Holm规则提供理论上的strong FWER control；global-null Monte Carlo只作实现兼容性诊断，其经验FWER不高于`.05 + 2×MCSE`，避免把有限Monte Carlo误差误判为规则失效；
4. planning SD逐estimand取以下三者最大值：block SD的单侧90%卡方上置信界、最大leave-one-cognitive-block-out SD、非负method-of-moments方差分量合成值的平方根；不使用Pilot均值或符号；
5. Monte Carlo operating-characteristic 模拟次数不少于 200,000/场景，并冻结随机种子；
6. 相关结构场景固定为：50%向单位阵收缩的Pilot相关矩阵、单位阵、等相关+0.50、等相关−0.25；不得只选择产生较小N的场景；
7. `N_required`计算完成后才进行provider calls、时间和费用可行性审查；资源不足时记录`SCIENTIFIC_N_NOT_RESOURCE_FEASIBLE`并修改执行计划，不得降低功效门槛、删减确认性estimand或把预算写成科学上限。

保守 planning SD 的具体计算实现必须在 Pilot 分析代码中预先锁定并测试。至少同时报告原始 Pilot SD 与小样本不确定性调整后的 planning SD；不得选择产生更小 N 的估计量。

正式N确定后，须发布协议`1.1`，写入唯一`N_required`、正式block IDs、正式seed ledger、provider-call ceiling、冻结源码SHA和正式分析代码SHA。协议`1.1`之前禁止正式执行。

## 8. 正式统计分析规则

### 8.1 确认性分析

- 对 P1、P2、P5 分别在 replication-block 层面进行双侧 one-sample t-test versus 0；
- 使用 Holm step-down 控制三项 family-wise error rate=.05；
- 报告有效 block 数、mean、SD、SE、95% ordinary CI、raw p、Holm-adjusted p、Holm decision、MDE 和设计阈值分类；
- 按`SMALL_N_DIAGNOSTIC_PROTOCOL_V331.md`报告全部block值、Q-Q、影响提示、联合leave-one-block-out和预设sign-flip/Holm敏感性；置换参考分布的有效性依赖相应不变性条件（Ernst，2004，《Permutation Methods: A Basis for Exact Inference》）；
- 诊断结果不替代主分析，不触发删除有效block或在多个方法中选择有利结果；主分析与敏感性不一致时必须标记为diagnostically fragile；
- 不能把“未拒绝零假设”写成“证明无效”，也不能把统计显著写成现实市场外部有效性。

### 8.2 探索性分析

P3、P4 报告各 block 值、mean、SD、median、IQR、min、max及轨迹/触达图，不计算确认性 p-value，不进入 Holm family，不使用显著性语言。

八个策略单元、消费者 segment、Agent 和网络节点层面的差异均为描述性或异质性探索。不得把单个 Agent、Agent×Tick 或 micro-buyer 层面的标准误写成正式不确定性。

## 9. Block 定义与有效性

一个正式 replication block 是在一套预先登记的 simulation/network、requested LLM 和 demand seeds 下完成全部九个 cognitive conditions 及 support-absent demand 输出的不可拆分执行单元。

正式 block 只有满足以下全部条件才有效：

- 九个 cognitive conditions 全部完成；
- 每个 condition 有 20×35=700 条唯一 Agent×Tick 记录，总计 6,300 条；
- 同一 block 内九个条件共享冻结 topology hash；
- common-history replay 在预处理窗口内零 miss；
- semantic fallback、parse error、schema error 和 invariant hard failure 均为零；
- 控制组无企业澄清污染；
- 处理前 state equality 与 event timeline 检查通过；
- Trust、SN、probability、loyalty 和 renewal-time 边界检查通过；
- P1–P5 均可从完整原始记录重建；
- 运行时 Git 工作树干净，HEAD、配置、prompt、model、temperature、seeds和参数快照均已落盘；
- 没有把 API key、凭据或未授权个人数据写入结果。

## 10. 失败、重启与停止规则

- Pilot 或正式执行均不得用新 seed 替换结果不理想的 block；
- 因进程中断、网络错误或 provider 故障导致 block 未产生有效输出时，只允许以完全相同的 seeds、源码和配置进行技术性重启；原失败 attempt 必须保留在 attempt ledger；
- 已产生完整输出但未通过 validity gate 的 block 不得静默删除或替换；
- 正式阶段的最大 attempt 数等于协议 1.1 冻结的正式 block 数；不得增加 F(N+1)；
- 不进行基于中期效应、p-value、置信区间或曲线排序的 optional stopping；
- 若有效 block 数低于计划 N，只分析有效的冻结 attempts，并明确标记 `planned_N_not_achieved=true`。

## 11. 证据、文献与论文写作规则

本协议与论文方法章节必须区分三类证据：

1. **实现证据**：unit/integration tests、schema/invariant checks、provenance 与 replay audit；
2. **工程验证证据**：horizon、Trust、clarification、network、orientation、size、micro-buyer 和 selected Real-LLM robustness；
3. **正式推断证据**：协议 1.1 冻结后产生的独立 replication blocks。

三类证据不得相互替代。工程 PASS 不等于统计推断、参数校准、外部效度或现实消费者效应。

用户此前提供的文献材料将用于以下证据接口：竞争信息与情绪机制、复杂/简单传播、同质性与选择偏差、强弱关系、结构洞与桥接、回音室与极化、算法推荐暴露、网络拓扑，以及 ODD/ODD+D、ABM verification and validation、pattern-oriented modeling、敏感性、校准、复现、face/micro/macro validity、generative explanation 和 model docking。

当前仓库未保存这些原始文献包的完整 PDF/Bib 元数据。因此本协议不生成作者—年份引用。论文写作前必须把每一项方法或理论主张映射到用户提供的原始文献；无法核验出处时统一标记“此处需要补充材料”，不得凭记忆补写作者、年份、题名、DOI或结论。

## 12. 论文允许与禁止表述

允许：

- “在冻结 GABM 和预设随机种子范围内……”；
- “block-level estimand 的均值/不确定性表明……”；
- “Hub 提高企业直接触达，但下游信任或购买效应需单独检验……”；
- “结果属于模型内生成机制证据，不直接代表现实消费者总体。”

禁止：

- “20 Agents 代表现实消费者样本”；
- “micro-buyers 提高了正式样本量”；
- “requested LLM seed 保证完全确定性”；
- “Hub 必然优于 Random”；
- “reach 等同于说服、信任修复或购买”；
- “Rational-evidence 识别了 evidence strength 的独立效应”；
- “工程稳健性 PASS 证明外部有效性”；
- “不显著证明没有效应”；
- 将 Fake/Pilot/robustness 输出写成正式论文实证结果。

## 13. 执行门禁

在以下文件和状态全部存在前，真实 LLM Pilot 不得执行：

- Pilot runner 与零 API 测试；
- `pilot_seed_ledger.csv`；
- Pilot attempt/validity contract；
- 已实现的4800次provider-call与8小时累计wall-clock门禁；
- 用户重新确认24-block计划的行政费用容忍度；
- 条件式Pilot授权记录；
- Windows完整回归通过并已冻结的clean Git HEAD；
- `python run_v33.py preflight --real` PASS；
- 结果目录与 manifest 写出测试 PASS。

在协议 1.1、正式 seed ledger、正式 runner/analysis SHA 和明确正式执行授权出现前，正式实验不得执行。
