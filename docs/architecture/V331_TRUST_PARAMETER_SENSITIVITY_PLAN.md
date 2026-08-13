# TASK_005 v3.3.1 Trust 参数敏感性分析计划

**状态：pre-specified before execution**  
**日期：2026-08-13**  
**正式推断：否（engineering robustness / mechanism sensitivity）**

## 1. 目的

v3.3.1 的 Trust 动态参数均为 development engineering assumptions，而不是由真实消费者微观数据估计得到的总体参数。因此，在进入新的正式 replication 之前，需要检验主要机制结论是否高度依赖某一组单点参数。

本阶段的目标不是寻找“效果最大”的参数组合，也不是重新校准模型，而是回答：

1. P1（澄清 vs Control Trust）是否对合理参数扰动保持方向与量级上的基本稳定；
2. P2（Rational − Empathy）是否特别依赖 empathy repair、repair saturation 或记忆衰减假设；
3. P3（Immediate − Delayed）是否主要由 event/quiet adjustment 设定驱动；
4. P5（repeat choice）是否只是 Trust 参数变化的机械放大；
5. P4（Hub − Random direct enterprise reach）是否在 Trust 参数变化下保持不变；若 P4 改变，应优先视为实现错误，因为 P4 的定义不含 Trust persuasion；
6. 哪些参数值得进入下一阶段的全局敏感性分析。

## 2. 方法原则

### 2.1 分两阶段，而不是一次性把所有参数组合穷举

**Stage A：局部/边界敏感性（本轮实施）**

采用 baseline + one-factor-at-a-time low/high + 少量结构边界 profile。目的为：

- 检查参数注入和输出链正确性；
- 识别对结果特别敏感的参数；
- 检查当前参数范围是否产生明显异常或边界效应；
- 为后续全局敏感性确定合理参数范围。

Stage A 不是全局敏感性分析，不能据此声称已完整识别参数交互。

**Stage B：全局敏感性（后续）**

在 Stage A 验证范围后，优先采用 Morris elementary-effects screening；若计算成本允许，再对关键参数使用 variance-based / Sobol-type analysis。Morris 方法适合中等维度计算模型的因素筛选，并通过随机化 elementary effects 比单一路径 OAT 更充分地探索输入空间；variance-based 方法可进一步分解一阶效应与总效应，但计算成本更高。

## 3. Stage A 参数范围

所有范围均为 **engineering robustness envelopes**，不是经验置信区间，也不声称由文献直接给出。

| 参数 | Baseline | Low | High | 机制含义 |
|---|---:|---:|---:|---|
| `crisis_retention` | 0.98 | 0.96 | 0.99 | 危机记忆保留速度 |
| `repair_retention` | 0.96 | 0.94 | 0.98 | 修复记忆保留速度 |
| `event_adjustment` | 0.80 | 0.60 | 1.00 | 有新信息时 Trust 向目标状态调整速度 |
| `quiet_adjustment` | 0.18 | 0.10 | 0.30 | 无新信息时 Trust 渐进调整速度 |
| `repair_saturation` | 0.30 | 0.00 | 0.60 | 重复修复的边际递减强度 |
| `hypocrisy_weight` | 0.25 | 0.00 | 0.50 | perceived hypocrisy 对负面记忆增量的放大 |
| `empathy_repair_weight` | 0.50 | 0.25 | 0.75 | 企业澄清中 perceived empathy 的关系性修复权重 |

### 3.1 为什么 retention 的上下界不完全对称

Retention 越接近 1，记忆持续性越强。Baseline 已处于高 retention 区间，因此使用 0.96–0.99 / 0.94–0.98 作为开发性扰动范围，目的在于比较“较快遗忘—基准—较慢遗忘”，而不是构造形式上对称但心理意义不清的 ±固定百分点。

### 3.2 结构边界 profiles

除 OAT 外，预先加入：

1. `retention_symmetric_097`：crisis = repair = 0.97；
2. `retention_reversed_096_098`：repair memory 比 crisis memory 更持久；
3. `legacy_v32_transition`：使用 `TrustDynamicsV33Parameters.legacy_v32()`，作为机制边界参照，不作为替代 baseline。

这些 profiles 用于检验“危机记忆更持久”这一非对称假设和 partial-adjustment 机制是否主导结论。

## 4. 固定不变的实验条件

Stage A 每一个 profile 均固定：

- Fake LLM / temperature = 0；
- T35 baseline horizon；
- 20 cognitive Agents；
- 25 micro-buyers / cognitive Agent；
- BA baseline topology；
- K=3；
- paid edge probability = 0.55；
- paid delivery lag = 1；
- 同一 simulation / LLM / demand seeds；
- 同一 2×2×2 + Control treatment matrix；
- 同一 persona、刺激文本、conversion-support design。

因此 Stage A 中唯一设计变化为 Trust parameter profile。

## 5. 预先规定的输出

每个 profile 输出完整 v3.3.1 run，然后统一汇总：

- `trust_sensitivity_profiles.csv`：参数设计矩阵；
- `trust_sensitivity_estimands.csv`：P1–P5、S1；
- `trust_sensitivity_local_effects.csv`：每个参数 low/high 相对 baseline 的变化；
- `trust_sensitivity_invariants.csv`：实现不变量；
- `trust_sensitivity_summary.json`；
- P1 / P2 / P3 / P5 参数敏感性图。

## 6. 实现不变量 / falsification checks

### 6.1 Pre-crisis invariance

Trust 参数变化不得改变危机发生前 T1–T4 的状态。不同 profile 的 T1–T4 应在关键状态变量上完全一致。

若失败，视为参数注入或运行隔离错误。

### 6.2 Network invariance

所有 profile 的 network hash 必须一致。

### 6.3 P4 direct reach invariance

P4 定义为企业直接触达窗口中的 Hub − Random reach，不包含 persuasion / Trust / downstream UGC。因此 Trust 参数变化不应改变 P4。

若 P4 变化，优先视为实现错误，而不是 Trust sensitivity。

### 6.4 Baseline provenance

`baseline` profile 必须与冻结的 `DEFAULT_TRUST_PARAMETERS` 完全一致；所有非 baseline run 必须在 `run_summary.json` 中标记 `trust_parameter_role = explicit-sensitivity-profile`。

## 7. 结果解释规则

不以显著性为目标，本阶段不计算 p-value 或正式 CI。

对每一 estimand 报告：

- baseline value；
- low/high delta from baseline；
- low–high span；
- 是否发生 sign reversal；
- structured boundary profiles 的变化。

特别注意：P2 baseline 可能接近零，因此不得使用相对百分比变化作为主要敏感性指标，否则分母接近零会夸大结果；使用 absolute Trust-point delta 和 sign stability 更合适。

若某参数导致 P1/P3/P5 方向频繁翻转，应报告为机制结论对该参数高度敏感；不能通过重新选择 baseline 参数消除。

## 8. 与全局敏感性的关系

Stage A 只用于 range verification 与 local/boundary screening。正式论文中如果要声称“参数重要性排序”或“模型对参数不确定性总体稳健”，必须进一步进行 Stage B global sensitivity。

Stage B 计划：

- 首选 Morris elementary effects，对 7 个参数进行全局 screening；
- 根据 `mu*` 与 `sigma` 识别主效应强度与非线性/交互迹象；
- 对最敏感的少数参数，再考虑 variance-based first-order / total-effect indices；
- 全局分析继续优先使用 Fake/Replay 固定语义层，避免 LLM stochasticity 与参数不确定性混杂；
- Real LLM robustness 单独处理。

## 9. 文献与方法依据

1. Thiele, J. C., Kurth, W., & Grimm, V. (2014). Facilitating Parameter Estimation and Sensitivity Analysis of Agent-Based Models: A Cookbook Using NetLogo and R. *Journal of Artificial Societies and Social Simulation*, 17(3), 11. DOI: 10.18564/jasss.2503. 该文强调 sensitivity analysis 是 ABM 开发和分析的重要组成，用于理解参数变化对模型输出和机制解释的影响。
2. Morris, M. D. (1991). Factorial Sampling Plans for Preliminary Computational Experiments. *Technometrics*, 33(2), 161–174. DOI: 10.1080/00401706.1991.10484804. 用于 Stage B 的 elementary-effects screening 方法依据。
3. Saltelli, A., Annoni, P., Azzini, I., Campolongo, F., Ratto, M., & Tarantola, S. (2010). Variance based sensitivity analysis of model output. Design and estimator for the total sensitivity index. *Computer Physics Communications*, 181(2), 259–270. DOI: 10.1016/j.cpc.2009.09.018. 用于后续 variance-based global sensitivity 的方法依据。

## 10. 论文可直接采用的表述

> 鉴于信任动态中的记忆保留、状态调整、修复边际递减与伪善放大参数主要属于模型工程假设，本研究在正式推断前实施参数敏感性分析。首先，在固定网络、语义输入、实验处理和随机种子的条件下，对各参数设置预先规定的低值、基准值和高值，并加入记忆对称、记忆方向反转及 legacy transition 等结构边界情景，以识别对主要结果影响较大的参数和潜在边界条件。该阶段用于局部与边界敏感性筛查，不将单因素结果解释为全局参数重要性；在此基础上，再采用全局 screening 方法检验参数空间中的非线性与交互影响。

## 11. 禁止表述

- “Low/High 是真实消费者参数的置信区间”；
- “OAT 已证明模型对所有参数组合稳健”；
- “某参数敏感，因此应重新调成能得到显著结果的数值”；
- “Fake LLM 参数敏感性等价于 Real LLM 外部有效性”。
