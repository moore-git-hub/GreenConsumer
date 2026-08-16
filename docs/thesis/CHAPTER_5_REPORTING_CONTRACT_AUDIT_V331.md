# 第五章正式结果报告合同审计（v3.3.1）

## 1. 审计目标与状态

本审计把第三、四章已经冻结的模型接口和estimand边界转换为第五章不可绕过的表头、图注、统计字段和结果句式。审计发生在Pilot和正式结果之前，因此不会根据结果方向修改报告结构。

当前状态为：报告合同v1.1可用；有效Pilot observation=0；正式N尚未确定；正式seed ledger、执行SHA和分析SHA尚未冻结；正式推断未获授权。第五章所有`[[待填]]`继续为空。

## 2. Estimand报告合同

| ID | 必须报告的统计对象 | 允许的核心结论 | 必须同时披露 | 禁止替换概念 |
|---|---|---|---|---|
| P1 | 八个澄清cell等权平均减共同Control的T6—T35 Trust AUC block contrast | 冻结等权策略组合相对不澄清的模型内信任差异 | block分布、不确定性、Holm、阈值与诊断标签 | 现实策略组合权重；“所有澄清策略” |
| P2 | Rational-evidence四cell减Emotional-empathy四cell的等权边际Trust AUC contrast | 两套复合内容框架的模型内平均差异 | 对渠道、时机边际化；交互未作确认性识别 | 单一credibility、evidence、valence、arousal或empathy效应；中介效应 |
| P3 | T6—T9 Immediate已启动减Delayed尚未启动的Trust AUC contrast | 早期处理启动路径差异 | block分布及T6/T10事件定义 | 完整时机效应、连续时间响应、“延迟损失”或最优时机 |
| P4 | 各自`t0..t0+lag`窗口内Hub减Random的企业直接触达比例 | 冻结拓扑、K和投递规则下的直接触达差异 | 拓扑、方向、K/N及lag边界 | UGC级联、说服、Trust、购买、ROI或平台最优 |
| P5 | support absent、T6—T35购买机会上的焦点品牌条件选择概率contrast | 带micro-buyer PBC、偏好和loyalty路径的模型内条件概率变化 | 机会数、概率单位、历史路径依赖、M=25不增加N | 认知层purchase intention、实现复购率、销量或市场份额 |

## 3. 统计报告完整性审计

修订前模板缺少或含糊的字段已作如下处理：

| 风险 | 审稿后果 | 合同修正 |
|---|---|---|
| “95%普通CI”未说明小样本分位数 | 无法复算，且可能被误作正态近似或family-wise区间 | 明确使用block间SD和$t_{N-1}$分位数的95%未调整边际t区间 |
| 只列exact Holm p而未列exact raw p | 与预冻结敏感性协议不完整对应 | 表5-2同时保留exact raw p与exact Holm p |
| 缺少median、IQR、min、max和MAD标记位置 | N=10时无法检查长尾与单block驱动 | 新增附表5-A1及LOBO范围、同方向数和同决策数 |
| P5单位仅写expected share | 容易被读成市场份额或实现购买率 | 改为购买机会条件选择概率，0.05写为5个百分点 |
| P3/P4简称过宽 | 容易产生时机效应或传播效果的越界解释 | 表5-3直接写入时间窗口、未启动状态和直接投递窗口 |
| 语义操纵表没有分母 | 暴露和记录缺失可能被误作中性语义 | 增加可评价观察行数、非空数、可用率和来源类型 |
| 轨迹或语义表直接池化行级记录 | Agent、消息或机会行被误作独立样本，产生伪精确性 | 强制先做block内condition×Tick/source汇总，再跨blocks展示 |

## 4. 图表合同

1. P1、P2、P5图显示全部独立block值、零线、均值、95% t区间及正负设计阈值线；阈值线不得标作管理收益线。
2. Trust、认知层purchase intention和需求层条件选择概率使用不同图题和单位；不得把后二者连接为同一序列。
3. 条件选择概率轨迹同时给出每个Tick的购买机会数；无机会Tick保持缺失，不填零、不插值。
4. P3图注明Immediate在T6已启动而Delayed到T10才启动；P4图注明只统计企业直接观察并集。
5. 单次Real-LLM图继续标注“工程run、非正式样本、Agents不是replication blocks”。
6. 任何cell-level排序只作描述，不新增事后确认性比较。
7. 所有正式轨迹和语义摘要先在block内聚合；Agent、消息、appraisal或micro-buyer行不直接产生跨行标准误。

## 5. 机制讨论合同

每个讨论段按“估计与不确定性—已实现机制—替代解释—文献构念接口—外推边界”组织。理论文献只能帮助解释构念关系，不能证明工程参数、模型生成UGC或现实效应量。

特别地：正P2不能直接归因于证据或共情；正P3不能称为延迟造成损失；正P4不能称为传播、说服或购买优势；正P5不能写成购买意向、复购率、销量或市场份额上升。未拒绝零假设只能说明当前N和模型波动下证据不足，不能证明无效或等效。

## 6. 仍不能通过写作修复的结构性风险

1. P2复合刺激无法识别单一语义机制或确认性交互。
2. P3窗口没有比较两种策略均已实施后的完整恢复路径。
3. P4只覆盖固定网络中的企业直接投递，不能回答消费者级联扩散效率。
4. LLM显式理由可进入UGC传播，但没有真实消费者文本的criterion/content validation。
5. P5条件于未经验校准的购买机会、偏好和loyalty机制。
6. N=10是否满足正式设计仍须由Pilot planning variance和预设operating-characteristic gate决定。

这些问题中，前五项只能通过新增设计或现实校准材料实质改善，不能依靠更强措辞修复；第六项必须恢复Pilot后按冻结规则判定。当前报告合同的作用是防止越界，不是提高证据强度。

## 7. 科研与版本记录

本轮没有填入结果、增加文献、改变处理、estimand、阈值、主分析、参数、prompt或seed。新增GABM run=0、provider call=0、有效Pilot observation=0、formal inference=0。Pilot和正式独立replication blocks继续保留但暂缓执行。
