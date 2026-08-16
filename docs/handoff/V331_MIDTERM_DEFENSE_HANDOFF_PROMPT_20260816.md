# v3.3.1 中期答辩工作交接包与新对话 Prompt

## 1. 交接身份

| 字段 | 当前值 |
|---|---|
| 项目 | GreenConsumer GABM / `TASK_005_FMCG_V3.3.1` |
| 仓库 | `https://github.com/moore-git-hub/GreenConsumer/` |
| 唯一工作分支 | `refactor/task005-v32-clean-codebase` |
| 本次交接基准 | 远端候选提交 `b73bf83117f6569f8fdca610e139e9b9d235fa4f` 之后的中期交接提交；新对话须以远端实际HEAD为准 |
| 交接日期 | `2026-08-16` |
| 最近用户决定 | 中期答辩约在两周后；Pilot与正式N计算暂缓，但执行方案、合同和代码全部保留，不取消 |
| 当前首要产出 | 中期报告、答辩PPT、逐页讲稿 |
| 禁止动作 | 未经用户重新授权，不运行真实LLM Pilot，不运行正式实验，不填造正式结果 |

本文件是跨对话的唯一启动入口。它不替代代码、协议、结果台账或文献原文；若本文件与版本化合同或代码冲突，以准确Git HEAD上的合同和代码为准，并记录差异。

## 2. 已完成工作的可核验总结

### 2.1 研究设计与模型实现

1. 研究情境已统一为虚构绿色快消品品牌 `VerdantCo Oat` 的绿色信任危机，避免把模拟刺激写成现实品牌事实。
2. 正式处理矩阵已冻结为：

   ```text
   2 Content（Rational-evidence / Emotional-empathy）
   × 2 Channel（Hub / Random）
   × 2 Timing（Immediate / Delayed）
   + 1 common NoClarification-Control
   ```

3. 时间设计已统一：T1–T4共同历史，T5危机，T6即时澄清，T10延迟澄清，T35基线终点；T30/T40仅作为工程稳健性边界。
4. 架构边界已明确：LLM仅将实际观察文本转换为schema约束的语义评价；Trust、Attitude、Subjective norm、purchase intention、发帖、网络传播、renewal opportunity、条件品牌选择和loyalty均由版本化规则更新。显式reasoning不是隐性chain-of-thought；规则触发发帖后，它可以成为UGC文本。
5. 基线网络为单次run内固定的有向BA网络；Hub/Random只改变同等paid-seed数量下的初始节点选择。模型没有网络重连，也没有现实平台校准。
6. 20个engineering personas用于机制覆盖，不是现实消费者样本；每个Agent下25个micro-buyers用于需求replay的数值分辨率，不增加独立样本量。

### 2.2 研究问题、estimand与统计边界

| 对象 | 当前角色 | 精确边界 |
|---|---|---|
| P1 | confirmatory | 八个澄清cell等权平均相对共同Control的Trust恢复/AUC效应 |
| P2 | confirmatory | Rational-evidence与Emotional-empathy两套复合内容框架的边际对比；不识别单个语义成分中介 |
| P3 | secondary/exploratory | T6–T9中Immediate已开始而Delayed尚未开始的早期处理起点差异，不是现实最优响应时点 |
| P4 | network-mechanism descriptive/exploratory | 冻结窗口内企业直接投递reach差异，不是UGC cascade、说服、购买或市场份额 |
| P5 | confirmatory | 已发品类购买机会条件下的焦点品牌预期选择概率，不是实际销量、市场份额或认知Agent的purchase intention |

正式统计单位是完整、独立的replication block。Agent、Agent×Tick、appraisal、provider call、购买机会和micro-buyer均不得作为独立重复单位。

### 2.3 已完成的验证与写作基础

- 完成代码边界、机制、输出schema、provenance、共同历史、处理污染、网络、replay及内部有效性检查的实现基础。
- 完成T30/T35/T40 horizon、Trust OAT/边界/Morris、澄清 `p×lag`、网络拓扑/方向/规模与K、micro-buyer resolution等工程敏感性与稳健性检查。
- 完成selected Real-LLM robustness工程套件记录；其中5个九条件Real-LLM blocks为工程稳健性材料，不属于Pilot或正式样本。
- 完成预选单次Real-LLM run的schema 1.2 cognition package：6张表、3张图、1120行matched-Control Agent对比、manifest/hash/provenance/算术与视觉审计。只可作为“单次工程run的有限描述性机制证据”。
- 用户曾在Windows `Kernel`环境报告旧候选HEAD `b4ba27cd3a770081d1fcaeaf373aa1b6e37b0004`为`129 passed`；该记录证明当时版本的回归状态，不证明后来24-block改造后的候选HEAD已在Windows验证。
- 完成论文写作基础包、第一至第四章正文底稿、第五章空结果报告合同、第六章条件式讨论模板、ODD＋D附录、引用—主张审计、题目—RQ—证据审计和跨章一致性审计。
- 用户提供的七个理论文献包已清点为57份PDF、53份SHA-256去重后的唯一PDF；另审阅5篇同专业硕士论文，仅用于章节结构和写作风格。引用必须定位到真实原文，禁止虚构。

### 2.4 尚未完成且不得伪装为完成

| 事项 | 当前事实 |
|---|---|
| v3.3.1有效Pilot blocks | `0` |
| v3.3.1正式N | 尚未计算 |
| v3.3.1正式blocks | `0` |
| v3.3.1正式统计推断 | `0` |
| 现实消费者/网络/购买数据校准 | 不存在 |
| 外部有效性证明 | 不存在 |
| 中期报告模板、PPT模板、答辩时长等 | 待用户提供 |

## 3. Pilot与正式N暂缓但保留的冻结方案

本次暂缓只是日程优先级调整，不是设计撤销、Pilot失败或样本量结论。

1. Pilot保持P001–P024共24个独立cognitive blocks，即6个simulation/network seeds×4个requested LLM seeds；P001–P006身份保留。
2. 每个cognitive block离线交叉D1–D24，形成576个P5条件性replay值；独立Pilot单位仍是24，不是576。
3. planning SD保持为三者最大值：单侧90% SD上置信界、最大leave-one-cognitive-block-out SD、非负方差分量合成SD。
4. 正式N从10向上搜索，不设科研上限；四个预设相关结构场景必须在同一N同时满足P1/P2/P5 single-MDE Holm检出概率≥.90及global-null数值FWER门禁。
5. 科学N先算，资源可行性后评估。资源不足只能记录为`SCIENTIFIC_N_NOT_RESOURCE_FEASIBLE`，不能降功效、调MDE、删确认性estimand、把Pilot并入正式样本或把行政预算包装为科学N。
6. 当前执行保护为4800次累计provider calls、8小时累计wall-clock、同suite/同SHA/同seed受控恢复；失败或validity失败不得换seed。
7. 恢复执行前仍需：准确远端SHA的Windows全量pytest、零API plan-only核对、clean tree、24-block费用容忍度重新确认和用户新的明确真实Pilot授权。

权威文件：

- `docs/architecture/V331_PILOT_AND_FORMAL_N_WORK_PLAN_20260816.md`
- `docs/architecture/task_pv01_pilot_variance_contract1.1.json`
- `docs/architecture/FORMAL_EXPERIMENT_PROTOCOL.md`
- `docs/architecture/PILOT_EXECUTION_CONDITIONS.md`
- `docs/architecture/PILOT_EXECUTION_AUTHORIZATION_V331.md`

## 4. 中期材料的证据使用规则

### 4.1 中期报告和答辩中可以呈现

- 研究背景、管理问题、理论链路、研究问题和GABM方法选择；
- 语义评价—心理状态—社会传播—重复选择的四层架构；
- 2×2×2+Control设计、时间线、P1–P5定义和证据分层；
- 已完成的代码verification、provenance和工程稳健性矩阵；
- 单次Real-LLM cognition图作为机制运行示例，图题和口头说明必须明确“单次工程run、描述性、非总体推断”；
- Pilot与正式N的预注册式计算方案以及中期后执行路线；
- 模型限制、外部校准缺失及后续工作。

### 4.2 绝不能写成当前结论

- “理性/共情、Hub/Random、即时/延迟中某方案显著更优”；
- “Hub提高了购买”或“P4证明消费者级联扩散”；
- “P5代表销量、市场份额或绿色产品总体采纳”；
- “20个Agent或25个micro-buyers构成现实样本”；
- “工程PASS证明模型真实有效或具有外部有效性”；
- “历史v3.2 N=10/N=58就是v3.3.1正式N”；
- 任何不存在的p值、置信区间、样本量、文献、调查或企业数据。

中期阶段建议统一证据标签：`设计与实现证据`、`工程稳健性证据`、`单次工程run描述`、`计划中的Pilot/正式推断`。不得省略标签。

## 5. 中期报告、PPT与讲稿的具体工作计划

| 阶段 | 工作内容 | 输入材料 | 交付物 | 完成门槛 |
|---:|---|---|---|---|
| M0 | 接收并解析学校中期报告模板、答辩PPT模板/参考和评分要求 | 用户待提供材料 | 模板字段清单、页数/时长/必填项表 | 不遗漏学校必填项 |
| M1 | 建立“模板栏目—论文底稿—代码/结果证据”映射 | 本文件第7节权威来源 | 中期证据矩阵 | 每项陈述可追溯到文件或文献 |
| M2 | 冻结中期题目、RQ和贡献口径 | 题目审计、导师意见、最新用户决定 | 一页定位决策 | 题目不大于当前证据；未决项显式标注 |
| M3 | 撰写中期报告初稿 | 章节1–4、工程结果、未来计划 | 符合模板的完整报告 | 结果分层、引用到位、无虚构、无正式推断越界 |
| M4 | 设计答辩叙事与PPT | 报告初稿、模板、允许使用的图 | 建议12–15页或按校规调整的PPT | 一页一结论；图表可读；时间预算匹配 |
| M5 | 编写逐页讲稿 | 最终PPT、答辩时长 | 逐页讲稿、转场句、时间标记 | 总时长留10%缓冲，不念图表细节 |
| M6 | 准备问答 | 导师意见、方法边界、未完成工作 | 高频问题与证据化回答 | 能解释为何尚无正式结论、为何用GABM、如何定N |
| M7 | 三件套一致性审计 | 报告、PPT、讲稿 | 术语/数值/引用/图号审计表 | 版本、时间点、样本单位、证据等级完全一致 |
| M8 | 答辩后恢复科研主线 | 中期反馈、冻结Pilot方案 | 更新决策日志并重新进入Pilot gate | 新授权前仍不调用真实LLM |

### 建议PPT故事线（收到模板后调整）

1. 标题与一句话研究问题；
2. 现实管理情境与研究动机；
3. 文献中的三个结构性断点；
4. 研究问题与研究边界；
5. 为什么采用GABM以及LLM职责边界；
6. 四层机制架构图；
7. Agent、网络、时间线与处理矩阵；
8. P1–P5与统计单位；
9. verification与可复现性；
10. 工程敏感性/稳健性矩阵；
11. 单次Real-LLM cognition示例（明确非正式推断）；
12. 当前完成度、证据缺口与限制；
13. Pilot与动态正式N方案；
14. 两周后至论文定稿的时间表；
15. 阶段性贡献与请导师指导的问题。

## 6. 用户下一次需要提供的材料

### 必需

1. 学校/学院中期报告官方模板，优先提供原始`.docx`；
2. 中期答辩PPT官方模板及一至两份可参考的往届材料；
3. 答辩日期、个人陈述时长、PPT页数或文件大小限制、评分表/必答栏目；
4. 当前报备的正式论文题目、专业名称、导师姓名等封面字段；
5. 现有“部分导师意见”之后的最新导师反馈；
6. 中期报告是否必须包含已发表成果、开题完成情况、进度偏差、经费或伦理说明。

### 如有则提供

- 学院logo、配色或保密要求；
- 希望重点展示或避免展示的三张cognition图；
- 用户本人希望答辩重点强调的创新点；
- 最新参考文献或导师指定必引文献。

以下材料原则上不必重复上传：当前GitHub仓库中的论文底稿和协议；此前七个文献包、同专业硕士论文包、研究问题、导师意见及旧框架图。如果新对话无法访问这些材料，再按缺失清单补充，不能凭文件名猜测内容。

## 7. 新对话必须先读的权威文件

按顺序读取，不能只读本交接文件：

1. `docs/PROJECT_PROGRESS.md`
2. `docs/handoff/V331_MIDTERM_DEFENSE_HANDOFF_PROMPT_20260816.md`
3. `docs/thesis/THESIS_WRITING_FOUNDATION_V331.md`
4. `docs/thesis/TITLE_RQ_CONTRIBUTION_AUDIT_V331.md`
5. `docs/thesis/FULL_THESIS_RQ_EVIDENCE_CLAIM_AUDIT_V331.md`
6. `docs/architecture/EXPERIMENT_EVIDENCE_REGISTER.md`
7. `docs/architecture/V331_PILOT_AND_FORMAL_N_WORK_PLAN_20260816.md`
8. `docs/thesis/LITERATURE_AND_STYLE_SOURCE_REGISTER.md`
9. 第一至第四章正文底稿，以及第五、六章模板；
10. 用户届时提供的中期报告和PPT模板。

如需报告具体工程数值，再读取相应`*_RESULT_*.md`。不得从图像视觉估计数值，不得把叙述文件当成原始数据。

## 8. 可直接复制到新对话的完整Prompt

```text
你将接手我的GreenConsumer GABM硕士论文项目，并优先帮助我在约两周内完成中期报告、答辩PPT和逐页讲稿。请不要依赖上一段对话的隐藏记忆，而要以GitHub仓库和我本次提供的材料为准。

仓库：https://github.com/moore-git-hub/GreenConsumer/
唯一工作分支：refactor/task005-v32-clean-codebase

第一步请先核对该分支的实际HEAD和工作树，再依次完整阅读：
1. docs/PROJECT_PROGRESS.md
2. docs/handoff/V331_MIDTERM_DEFENSE_HANDOFF_PROMPT_20260816.md
3. docs/thesis/THESIS_WRITING_FOUNDATION_V331.md
4. docs/thesis/TITLE_RQ_CONTRIBUTION_AUDIT_V331.md
5. docs/thesis/FULL_THESIS_RQ_EVIDENCE_CLAIM_AUDIT_V331.md
6. docs/architecture/EXPERIMENT_EVIDENCE_REGISTER.md
7. docs/architecture/V331_PILOT_AND_FORMAL_N_WORK_PLAN_20260816.md
8. docs/thesis/LITERATURE_AND_STYLE_SOURCE_REGISTER.md
9. docs/thesis/CHAPTER_1_INTRODUCTION_DRAFT_V331.md至CHAPTER_6_DISCUSSION_AND_CONCLUSION_TEMPLATE_V331.md，以及APPENDIX_ODD_D_MODEL_DESCRIPTION_V331.md。

当前用户决定：由于两周后进行中期答辩，真实Pilot和正式N计算暂缓，但不取消。24-block Pilot、24 demand seeds、planning SD、四相关场景动态正式N、4800-call/8-hour门禁及恢复方案全部保留。未经我重新明确授权，不得运行真实LLM、Pilot或正式实验，也不得修改冻结的科学设计。

必须维持的事实边界：
- 当前主版本为TASK_005_FMCG_V3.3.1，虚构品牌VerdantCo Oat；
- 处理为2×2×2+共同NoClarification-Control；T5危机、T6即时、T10延迟、T35终点；
- P1/P2/P5为确认性，P3/P4为探索性；完整独立replication block才是统计单位；
- 20个engineering personas和每Agent 25个micro-buyers均不是现实独立样本；
- v3.3.1有效Pilot blocks=0，正式N尚未计算，正式blocks=0，正式推断=0；
- 既有Fake-LLM敏感性、网络稳健性和5个Real-LLM robustness blocks属于工程证据；预选单次Real-LLM cognition package只属于有限描述性证据；
- 不得宣称某内容、渠道或时机策略显著更优，不得把P4写成UGC cascade或购买，不得把P5写成销量/市场份额；
- 不得把历史v3.2 N=10或N=58套用到v3.3.1；
- 所有引用必须真实可核验，在对应句段标注“作者、年份、标题”，禁止虚构文献。优先使用我之前提供的七个文献包；缺证据时明确告诉我需要补充什么。

你的工作顺序：
A. 读取我随后上传的中期报告模板、答辩PPT模板/参考、评分要求和最新导师意见；
B. 先提交“模板栏目—现有论文底稿—代码/结果证据—缺口”的映射表，不立刻编造正文；
C. 给出中期题目/RQ/贡献的证据匹配建议，特别处理当前题目可能大于P4直接reach和P5条件选择证据的风险；未经我确认不要静默改题；
D. 撰写完整中期报告，明确区分设计与实现、工程稳健性、单次工程run描述和未来正式推断；
E. 按答辩时长制作PPT，建议一页一结论，并优先使用仓库中的机制架构图、技术路线图和经审计的cognition图；
F. 为最终PPT写逐页讲稿、转场句、时间预算和高频问答；
G. 最后执行报告—PPT—讲稿的术语、数值、引用、图号和证据等级一致性审计。

开始时只需：
1. 告诉我你核对到的分支HEAD与项目事实；
2. 列出你已经收到和仍缺少的答辩材料；
3. 给出中期三件套的具体工作计划与第一个待我确认的内容。

我接下来会提供：中期报告官方模板、PPT模板/参考、答辩时长和规则、当前报备题目、最新导师意见。没有这些材料时可以整理证据和大纲，但不要定稿格式或虚构学校要求。
```

## 9. 交接后的第一个用户确认点

收到模板后，新对话首先需要用户确认两项，而不是立刻铺开写作：

1. 中期答辩继续使用当前暂定题目，还是采用证据范围更稳妥的题目候选《基于GABM的绿色快消品品牌信任危机沟通机制研究》；
2. 单次Real-LLM cognition图是否进入中期PPT。若进入，只能放在“模型运行示例/阶段性工程结果”，不得放在“正式研究结论”。

## 10. 当前零增量声明

本交接工作仅整理项目事实、优先级和写作路线：

```text
NEW GABM RUNS: 0
NEW REAL-LLM PROVIDER CALLS: 0
VALID V3.3.1 PILOT BLOCKS: 0
FORMAL BLOCKS: 0
FORMAL INFERENCE: 0
SCIENTIFIC DESIGN CHANGES: 0
```
