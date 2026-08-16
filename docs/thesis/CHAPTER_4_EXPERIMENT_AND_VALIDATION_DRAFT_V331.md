# 第四章 实验设计与模型验证（v3.3.1无正式结果正文底稿）

## 4.1 本章任务与证据边界

本章说明处理设计、estimand、推断单位、Pilot方差方案、正式分析规则以及已经完成的模型验证。需要首先划定五层证据边界：实现验证回答“代码是否按设计运行”；工程稳健性回答“模型内方向或结构是否依赖某一预设工程条件”；单次Real-LLM描述只展示固定工程run中的状态与异质性；Pilot只回答“在预算上限内是否可能形成可接受的正式重复设计”；正式replication blocks才用于确认性推断。五层证据不能相互替代。

因此，本章可以报告已经完成的实现检查和工程稳健性，但不能报告v3.3.1正式处理效应。P001—P006尚未执行，正式N尚未获得方差证据支持，P1、P2和P5的p值、置信区间及Holm结论均不存在。将工程PASS写成现实消费者效应，会形成直接的证据—结论不匹配。

## 4.2 处理设计

### 4.2.1 因子结构

实验采用2×2×2完全交叉处理，并设置一个共同不澄清组。三个处理因素分别为：

| 因素 | 水平1 | 水平2 | 操作化边界 |
|---|---|---|---|
| Content | Rational-evidence | Emotional-empathy | 两套完整文本框架，不拆解单一语义维度效应 |
| Channel | Hub | Random | 相同企业付费种子节点数量K=3下的节点选择规则 |
| Timing | Immediate | Delayed | 危机后T6与T10，不代表现实最优时间 |

八个处理单元为Rational/Empathy×Hub/Random×Immediate/Delayed。NoClarification-Control不属于Timing的第三个水平，也不进入三因素编码。控制组用于识别八个冻结处理单元等权平均相对于无企业回应的总体模型内差异；该等权权重是预先规定的estimand组成，不代表现实策略采用比例。

### 4.2.2 因果对比的识别条件

每个完整block内九个条件共享Persona面板、危机文本、危机时点、网络拓扑及预处理历史。处理前T1—T4和危机T5必须保持相同；处理差异只能在预设澄清时点后出现。该设计能够识别冻结模型内部的处理对比，但仍依赖以下不可由仿真自身验证的前提：文本框架具有足够构念区分、网络节点选择规则对应所称渠道差异、心理更新函数没有遗漏决定性反向机制，以及共同历史重放没有引入条件特异误差。

内容因素尤其需要收紧解释。Rational-evidence与Emotional-empathy同时改变多个语义特征，故P2只识别复合文本策略差异，不识别credibility、evidence strength、valence、arousal或perceived empathy的独立因果效应。若正文把P2拆成单一语义机制，将超过设计的识别能力。语义操纵检查只能说明两套文本在模型中产生了哪些评价差异，不能把这些事后实现差异升级为独立中介效应。

时机和渠道也有各自的识别限制。T6—T9期间Delayed尚未接受澄清，因此P3本质上是“即时启动相对尚未启动”的早期处理起点对比，而不是两个均已实施策略之间的完整时机效应，更不能估计连续时间响应函数。P4则只比较给定拓扑、K=3、公共暴露和一跳投递规则下的直接企业触达；它不识别UGC级联、说服效果或现实平台投放效率。

## 4.3 Estimand与分析角色

### 4.3.1 信任轨迹标准化曲线下面积（Trust AUC）

对条件c在区间a至b的Agent平均Trust轨迹，标准化梯形面积定义为：

$$AUC_{c,a:b}=\frac{1}{b-a}\sum_{t=a}^{b-1}\frac{\bar T_{c,t}+\bar T_{c,t+1}}{2}.$$

除以区间长度后，AUC仍保持Trust points单位，可以在不同条件间比较，但不应与0—1量纲变量直接比较数值大小。

### 4.3.2 确认性family

确认性family固定为P1、P2和P5：

1. P1为八个澄清单元T6—T35 Trust AUC等权均值减去共同控制组AUC；
2. P2为四个Rational单元AUC等权均值减去四个Empathy单元AUC等权均值；
3. P5为无外部支持（support absent）条件下，八个澄清单元T6—T35购买机会上的焦点品牌条件选择概率等权均值减去共同控制组对应值。

P1和P5是对八种策略单元等权后的模型内总体澄清对比，不对应现实企业策略组合的经验权重。P2则是对渠道及时机等权边际化后的复合内容对比；若存在内容×渠道或内容×时机异质性，P2可能掩盖条件差异，而当前协议没有冻结确认性交互estimand。

P5使用每次品类购买机会上的模型条件选择概率均值，而不是已实现选择（realized choices）。该概率叠加微型购买者偏好和既往忠诚，忠诚又由此前已实现选择更新，因此P5条件于模型生成的历史路径。它不是现实购买率、销量或无条件市场份额；M=25只是需求层数值分辨率。

### 4.3.3 探索性与机制性estimand

P3比较Immediate与Delayed在T6—T9的Trust AUC，用于刻画即时澄清已经启动而延迟澄清尚未启动时的早期处理起点差异。它不回答T10之后两种策略的完整恢复差异，也不能直接写成“延迟造成的损失”。P4比较Hub与Random在各自企业投递窗口t0至t0+lag内的直接企业触达比例。P4不包含下游UGC说服或购买，故Hub提高reach不能直接推出Trust或repeat choice提高。P3和P4不进入确认性Holm family，也不使用显著性语言。

## 4.4 Replication block、随机来源与推断单位

一个完整replication block是在一套预先登记的simulation/network seed、requested LLM seed及demand seed下完成全部九个认知条件与support-absent需求输出的不可拆分单位。每个block先计算P1—P5，再在block之间进行正式分析。

以下对象均不是独立正式样本：20个认知Agent、Agent×Tick记录、LLM provider calls、每个Agent下的25个微型购买者以及同一认知历史上的多个需求重放。把这些行当成独立观测会破坏独立性假设，使所得标准误缺少相应的抽样依据。

模型包含三类主要随机来源：simulation/network随机性、requested-seed与provider/runtime共同形成的LLM波动，以及离线demand随机性。当前runner尚未完全拆分simulation seed与network seed，因此Pilot只能估计联合simulation/network分量，不能声称独立识别网络方差。

## 4.5 Pilot方差设计

> 当前执行状态：用户于2026-08-16已接受Pilot预算、具体模型并作出条件式授权；仍须由新模型固定提交通过Windows全量测试和clean-SHA冻结后方可执行。以下内容是预先形成的设计方案，不代表Pilot已经执行，也不形成正式N或结果。

### 4.5.1 目的与网格

Pilot预设3个simulation/network seeds×2个requested LLM seeds，共6个完整认知blocks，即P001—P006。每个认知历史再使用3个预设demand seeds进行离线重放，产生18个P5 realizations。后者共享认知历史，只用于需求层方差分解，不构成18个独立blocks。

Pilot均值、符号和策略排序不得用于修改机制、选择prompt、改变estimand或调整MDE。Pilot只用于估计P1、P2、P5的planning variance、检查正式runner和validity gate，并判断预算上限内的设计是否可行。

### 4.5.2 方差分解及其局限

P1和P2采用3×2平衡网格的两向矩估计，分解simulation/network、requested LLM/provider以及二者交互加未解析runtime波动。P5在3×2×3网格中进一步分离offline-demand分量。由于每个单元只有一个观测，交互与残差不能完全区分；负方差分量被有界到零只是一种planning处理，不能证明该随机来源不存在。

规划方差不使用Pilot均值。P1和P2以六个block值的样本方差为基础；P5取D1 block方差与有界方差分量和中的较大值；随后使用df=5的单侧80%卡方上界因子形成保守planning SD。该做法减少根据Pilot结果选择较小N的空间，但六个blocks仍会导致方差估计高度不稳定。

## 4.6 正式样本量门禁与统计分析

### 4.6.1 预设设计阈值

P1、P2和P5的预设阈值分别为0.15 Trust points、0.15 Trust points和0.05选择概率比例（5个百分点；机器输出单位标签为`expected-choice share`）。这些数值目前只能称为“预先设定的设计阈值”，不能称为已由企业决策数据证明的“管理上重要差异”。若论文希望使用后者，需要额外提供管理决策依据。

### 4.6.2 N_max=10的含义

用户已在查看Pilot结果前冻结正式replication-block预算上限N_max=10。由于协议要求正式N不低于10，当前唯一预算候选是N=10。只有当保守planning SD下P1、P2和P5在各自阈值处的边际检出概率均不低于0.80时，才能发布协议1.1并冻结正式N=10；否则必须记录DESIGN_NOT_FEASIBLE_WITHIN_CAP。

N_max=10不是已证明的正式样本量。更严厉的审稿风险在于：即使operating-characteristic计算通过，N=10下block-level t统计量仍可能对异常block和分布偏离敏感。为避免看到结果后选择方法，本研究已在Pilot前冻结小样本诊断协议：主分析仍为双侧one-sample t-test与Holm校正；同时完整展示10个block值、Q-Q图和MAD影响提示，执行10次联合leave-one-block-out，并对每项estimand完整枚举2^10=1024种符号组合形成exact sign-flip敏感性family。置换推断依赖零假设下相应的数据变换不变性，sign-flip在此具体依赖block contrasts关于零的符号可交换/对称条件，因此其结果不被包装为无条件优于t-test（Ernst，2004，《Permutation Methods: A Basis for Exact Inference》）。

诊断只用于披露脆弱性。通过validity gate的极端block不得删除，Shapiro–Wilk不作为方法切换门禁，LOBO的N=9结果不得替代N=10主分析。若主分析拒绝而exact sign-flip或LOBO不一致，结果仍报告主分析决定，但必须标记为`PRIMARY_SUPPORTED_BUT_DIAGNOSTICALLY_FRAGILE`。

### 4.6.3 多重检验

P1、P2和P5采用Holm step-down控制family-wise alpha=0.05（Holm，1979，《A Simple Sequentially Rejective Multiple Test Procedure》）。每项报告有效block数、均值、SD、SE、95%普通置信区间、原始p值、Holm调整p值、决策和预设阈值。未拒绝零假设不能写成“证明没有效应”，统计显著也不能写成现实市场有效。

## 4.7 有效block与失败处理

正式block必须同时满足：九个认知条件完整；每个条件20×35=700条唯一Agent×Tick记录；九条件共享topology hash；共同历史零miss；semantic fallback、parse error、schema error和硬不变量失败均为零；控制组无企业澄清污染；处理前状态相等；Trust、SN、概率、loyalty及renewal time均在边界内；P1—P5可重建；Git、配置、prompt、模型、temperature和全部seeds可追溯。

技术失败只能使用完全相同的seeds、代码和配置重启，并保留原attempt记录。完整输出但未通过validity gate的block不得静默删除或换seed。正式阶段不允许按中期效应、p值或曲线排序提前停止，也不允许增加F(N+1)。

## 4.8 模型验证框架

### 4.8.1 实现验证

实现验证覆盖Agent×Tick完整性、共同历史、事件时序、处理污染、变量边界、网络落盘一致性、需求机会与loyalty约束、schema及provenance。ODD要求将实体、状态、过程、调度、初始化和输入明确记录，以提高可复现性，但完成ODD并不等于模型有效（Grimm等，2020，《The ODD protocol for describing agent-based and other simulation models: A second update to improve clarity, replication, and structural realism》）。

### 4.8.2 工程敏感性与稳健性

工程验证采用预设参数或结构扰动，检查实现不变量、estimand方向和结构边界。Morris elementary-effects用于七项Trust参数的全局筛查，其作用是识别总体影响强度及非线性/交互迹象，而不是估计现实参数分布（Morris，1991，《Factorial Sampling Plans for Preliminary Computational Experiments》）。当前参数区间是engineering envelope，不是经验置信区间。

### 4.8.3 校准与外部验证

ABM校准方法对模型规模、经验目标、计算预算和识别条件敏感（Platt，2020，《A comparison of economic agent-based model calibration methods》；Grazzini、Richiardi、Tsionas，2017，《Bayesian estimation of agent-based models》）。本研究尚未使用现实消费者面板、平台网络、危机后信任时间序列或品牌购买数据校准。因此，当前已完成验证属于verification和engineering robustness，不属于macro-validity或现实预测验证。

## 4.9 已完成工程验证及其允许结论

| 验证模块 | 设计与完成状态 | 允许结论 | 禁止结论 |
|---|---|---|---|
| Horizon | T30/T35/T40均PASS；prefix invariance failure=0 | 时间范围传递与过去轨迹不受未来horizon污染；T35继续作为预设终点 | 已证明三个horizon效应量稳定 |
| Trust Stage A | 18个预设OAT/边界profiles；不变量全PASS | 局部/边界范围内主要描述性方向未翻转；识别高敏感参数 | 参数已经验校准 |
| Trust Morris | 7参数、10 trajectories、80个points；240/240实现不变量PASS | 七维engineering envelope内方向稳定；P2对empathy repair pathway敏感，P3早期起点对比对event adjustment敏感 | 80个points是现实样本；参数排序是现实因果贡献 |
| Clarification | p=.30/.55/.80×lag=0/1/2共9 profiles；84/84不变量PASS | paid reach speed改变P3早期起点对比；P4依赖触达结构 | p=.55和lag=1是现实最优值 |
| Topology | BA、WS、Community各5张网络；76/76不变量PASS | P1/P2/P3/P5方向在15张预设网络中稳定；P4具有拓扑边界 | BA代表真实平台；15张网络支持总体推断 |
| Orientation | 3 topology×5 seeds×3等度边方向规则，共45 profiles；241/241检查PASS | BA与Community的P4较稳定；WS中P4可降至零或反向，显示方向定义边界 | 任一方向规则是现实真值 |
| Network size/K | N=20/40/80、fixed K与15% proportional allocation，共25 profiles；109/109检查PASS | fixed K随规模扩大产生覆盖稀释；结果依赖K/N | 15%为最优货币预算；N=80代表人口 |
| Micro-buyer | 5个认知历史×M10/M25/M50，共15 profiles | P5/S1未发生方向翻转；上游P1—P4与M分离 | M=25为经验样本量；未归档数值可定量引用 |
| Real-LLM robustness | 3种预设prompt版式＋3次baseline重复，共5个unique blocks、743 provider calls；不变量失败为0 | 在受控版式扰动和三次实际runtime波动中未观察到estimand方向翻转 | prompt无关、统计稳定、真实消费者有效 |

这些工程结果说明模型并非只在一个单点配置下运行，但也暴露了结构性依赖：内容对比对显式共情修复权重敏感；时机对事件调整率敏感；渠道直接触达同时依赖拓扑、边方向和K/N。后一类发现不是需要掩盖的“瑕疵”，而是正式结论必须携带的适用条件。

## 4.10 当前未解决的验证缺口

第一，语义评价缺少与现实消费者编码或量表的criterion validation。LLM能够在部分受控实验中复现人类模式，也可能产生系统性偏差（Aher、Arriaga、Kalai，2023，《Using large language models to simulate multiple humans and replicate human subject studies》）。三次provider重复和两种版式扰动不足以解决这一问题。进一步地，当前实现会在规则判定发帖后，将LLM显式评价理由复用为UGC正文，形成模型生成文本的网络反馈；该接口需要单独的内容审计，不能仅凭schema合规证明其具有现实UGC效度。

第二，Persona面板用于机制覆盖，没有人口权重；网络是受控拓扑，没有真实follower/followee或信息流方向数据；需求层没有植物奶扫描面板校准。这些缺口限制外部效度，而不是靠增加Fake-LLM运行数量可以修复。

第三，N_max=10可能使正式设计在预设阈值下不可行。若Pilot后出现该结论，它是研究设计的真实失败模式，不应通过提高效应、减少family、放宽power或重新定义MDE来消除。N=10的诊断与敏感性规则虽已在结果前冻结，但不能补偿检出概率不足。

第四，P1/P2/P5的0.15/0.15/0.05仍缺少企业决策、可比经验效应或测量分辨率依据。目前只能称为预先设定的设计阈值。即使正式均值达到阈值，也不能自动写为“具有管理意义”；相关依据必须在`DESIGN_THRESHOLD_JUSTIFICATION_WORKSHEET_V331.md`中补齐并经决策日志准入。

## 4.11 本章小结

本章冻结了处理、estimand、推断单位、Pilot方差方案和正式分析门禁，并把已经完成的工程验证与尚不存在的正式推断分开报告。现有证据支持模型实现、若干方向稳健性和明确结构边界；不支持现实消费者效应量、平台最优投放或经验参数有效性。Pilot已获条件式授权但尚未执行，正式独立replication blocks仍未授权；在结果生成前，本文只继续整理既有工程证据与方法文本。
