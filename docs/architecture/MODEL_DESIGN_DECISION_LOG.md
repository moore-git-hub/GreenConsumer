# GreenConsumer GABM 模型设计决策日志

本文件记录 TASK_005 v3.3.1 起所有会影响模型结构、实验处理、时间尺度、网络、参数、LLM prompt、随机过程、输出指标或推断方案的设计决策。目标是让论文中的每一项模型选择都可追溯到：研究目的、科学理由、工程实现、验证证据、边界条件和版本身份。

## 使用规则

每个新阶段必须在产生正式结果前记录：Decision ID、触发原因、设计选择、不改变部分、科学依据、engineering assumptions、代码路径、预期影响、验证/证伪方案、对既有结果的影响以及论文允许/禁止表述。

任何“因为效果不显著、图形不好看、策略排序不理想”而提出的修改必须明确标记为 outcome-driven；正式冻结后原则上不得据此修改主模型。

---

## DR-20260813-01：v3.3 Trust / Reach / Renewal 机制升级

**状态：implemented and engineering-validated**

建立并行 v3.3，不修改 v3.2 F001–F010：Trust采用非对称 crisis/repair memory、event/quiet partial adjustment、repair saturation 与 hypocrisy amplifier；Clarification采用Bernoulli public exposure、K=3 seeds及lagged probabilistic one-hop amplification；Demand采用renewal purchase opportunities和bounded EWMA loyalty。不得通过提高LLM temperature或给Trust直接加噪声制造曲线。v3.2正式样本不得复用于v3.3 inference。

---

## DR-20260813-02：v3.3.1 Social Feed 与审计文本完整性修复

**状态：implemented and Real-LLM re-audited**

Real-LLM审计发现receiving LLM的Social Feed存在`[:180]`输入截断，同时post/reasoning落盘存在200/300字符截断。新增版本隔离的`GreenCognitionV33Plugin`并恢复完整审计文本。该修改属于measurement/input integrity修复，不改变Trust、Demand、network、temperature或treatment。修复后truncated/incomplete social artifact消失，Rational→Evidence、Empathy→Perceived Empathy和peer-only SN boundary保持成立。

---

## DR-20260813-03：有限时间范围改为T35 baseline

**状态：implemented; finite-horizon engineering suite PASS**

1 Tick定义为1 simulation day；Crisis=T5；主终点=T35，即危机后30日；T30/T40预先规定为horizon robustness。v3.2历史30-Tick正式设计保持不变。Fake T30/T35/T40 nested suite通过，`prefix_invariance_failures=0`。禁止把T35解释为文献证明的现实最优恢复时长，也不得将20 Agents解释为现实样本量。

详见：`V331_TIME_HORIZON_AND_SCALE_DESIGN.md`、`V331_HORIZON_ROBUSTNESS_PLAN.md`、`V331_HORIZON_ROBUSTNESS_RESULT_20260813.md`。

---

## DR-20260813-04：Runtime horizon guard 测试隔离

**状态：implemented and re-verified**

首版T35 guard测试误触发AgentKernel/Hugging Face重依赖。runtime约束被抽成纯函数`_validate_runtime_config_v331()`，unit test不再为整数配置检查触发外部模型初始化；full Fake horizon suite承担end-to-end integration verification。科学机制不变。

---

## DR-20260813-05：Trust 参数敏感性 Stage A

**状态：executed; PASS**

Fake LLM、T35、20 Agents、25 micro-buyers、BA、处理矩阵与三个seeds固定；七个Trust参数按预设low/baseline/high，加3个structured boundary profiles，共18 profiles。54/54 implementation invariants PASS；P1/P2/P3/P4/P5/S1无方向翻转；P1/P5对`repair_retention`、`empathy_repair_weight`、`event_adjustment`较敏感；P2主要受`empathy_repair_weight`影响；P3主要受`event_adjustment`影响；P4始终0.45。Stage A只支持local/boundary robustness。

详见：`V331_TRUST_PARAMETER_SENSITIVITY_PLAN.md`、`V331_TRUST_PARAMETER_SENSITIVITY_RESULT_20260813.md`。

---

## DR-20260813-06：Trust 参数敏感性 Stage B — Morris global screening

**状态：executed; PASS**

采用预先登记Morris design：k=7、p=6、normalized Delta=.6、r=10、80 unique evaluations。Design validation 50/50 PASS，implementation invariants 240/240 PASS，P4对全部Trust参数`mu_star=0`。在七维engineering envelope内：P1 80/80正、P2 80/80负、P3 80/80正、P5 80/80正。P1/P5主要由`repair_retention`、`empathy_repair_weight`、`event_adjustment`驱动；P2主要由`empathy_repair_weight`驱动；P3主要由`event_adjustment`驱动。`sigma`只解释为非线性和/或交互迹象，不用于断言具体交互对。

当前不继续把Sobol作为主流程：Trust结构已通过OAT + structured boundaries + Morris global screening；如导师后续要求first/total variance decomposition，再对筛出的关键参数另立Decision Record。

详见：`V331_TRUST_PARAMETER_MORRIS_PLAN.md`、`V331_TRUST_PARAMETER_MORRIS_RESULT_20260813.md`。

---

## DR-20260813-07：Clarification Diffusion / Paid-Reach 敏感性

**状态：executed; PASS**

固定Fake LLM、T35、20 Agents、25 micro-buyers、BA、K=3、Trust baseline、三个seeds与处理矩阵，仅改变`paid_edge_probability ∈ {.30,.55,.80}`与`paid_delivery_lag ∈ {0,1,2}`，共9 profiles。`clarification_20260813_151145`中84/84 implementation/falsification checks PASS。P1/P3/P4/P5在9/9 profiles中正，P2在9/9中负；固定p时P3随lag增加而系统减小；S1几乎不受reach参数影响。Hub与Random自身reach随p非递减，但Hub−Random contrast并不要求对p单调。N=20导致reach以5个百分点为最小粒度之一。

详见：`V331_CLARIFICATION_DIFFUSION_SENSITIVITY_PLAN.md`、`V331_CLARIFICATION_DIFFUSION_SENSITIVITY_RESULT_20260813.md`。

---

## DR-20260813-08：Network topology robustness at fixed N=20

**状态：executed; PASS with channel-boundary finding**

### 设计

保持同一20个Engineering Personas、Fake LLM、T35、25 micro-buyers/Agent、K=3、p=.55、lag=1、Trust baseline、simulation/LLM/demand seeds与处理矩阵不变，仅改变network topology与独立network-only seed。

- BA：n=20,m=2；
- Watts–Strogatz：n=20,k=4,beta=.10；
- Community SBM：4×5 blocks，p_in=.65，p_out=.08；
- 每类5个预设network seeds，共15 profiles。

### 验证与结果

`topology_20260813_153842`：76/76 invariants PASS，baseline BA hash精确复现。P1、P2、P3、P5、S1在15张网络上均保持方向；P4则出现明显拓扑边界：BA 5/5 positive（mean=.40），Community 5/5 positive（mean=.17），WS为4 positive + 1 zero（mean=.12）。因此“Hub一定优于Random”不再允许作为无条件结论，只能写为依赖degree heterogeneity / hub distinguishability的结构性优势。

事后描述性诊断显示，当前15张网络中P4与degree CV、max out-degree呈较强正对应，与average path length、modularity、equal-degree tie share呈负对应；该诊断不作因果或显著性解释。

详见：`V331_NETWORK_TOPOLOGY_ROBUSTNESS_PLAN.md`、`V331_NETWORK_TOPOLOGY_ROBUSTNESS_RESULT_20260813.md`。

---

## DR-20260813-09：Network size × targeting budget robustness

**状态：pre-specified; implementation scaffold added; execution pending**

### 触发原因

固定N=20的topology suite表明P4对network realization敏感，且reach存在1/N=5%的离散粒度。需要判断主要结论是否依赖小网络规模，同时避免把“增加N”与“降低K/N”混为一个变化。

### 设计

仅使用BA m=2，network size设为N=20/40/80，使用5个network-only seeds。比较两种预算制度：

- fixed K=3；
- proportional K/N=15%，即K=3/6/12。

N20/K3为两种制度的共同baseline，因此每个seed只运行5个唯一profiles：N20-K3、N40-K3、N40-K6、N80-K3、N80-K12，共25 profiles。

### Persona扩展

不得简单复制20个prompt。新增nested balanced mechanism-coverage panel：

- N20精确保留冻结20 Persona；
- N40包含完整N20；
- N80包含完整N40；
- 六维categorical tuple在panel内必须唯一；
- N40/N80的marginal proportions按N20机制面板整数倍扩展；
- candidate universe为4×4×3×3×3×2=864种显式组合；
- deterministic greedy rule在不超出marginal target的前提下优先补足缺口并提高pairwise coverage。

这些比例仍是engineering mechanism coverage，不是现实市场人口权重。

### 固定部分

T35、Trust、clarification p=.55/lag=1、Fake LLM、25 micro-buyers/Agent、behavior/LLM/demand seeds、刺激文本与处理矩阵全部冻结。

### Hard checks

- N20 baseline hash复现；
- Panel20 ⊂ Panel40 ⊂ Panel80；
- no persona clones；
- categorical marginals达到预设target；
- shared N20 Agents的T1–T5认知前缀检查；
- 每个profile内9条件同一network hash；
- K完整性；
- clarification baseline参数冻结；
- Demand必须实际使用对应N的persona panel。

详见：`V331_NETWORK_SIZE_AND_BUDGET_ROBUSTNESS_PLAN.md`。

---

## 后续预登记队列

- network size × budget 结果记录；
- 必要时network orientation robustness / matched-metric topology experiment；
- micro-buyers 10/25/50；
- prompt sensitivity / LLM stochasticity；
- Real-LLM selected robustness blocks；
- v3.3.1 pilot variance estimation与正式replication-block数量；
- confirmatory estimands / MDE / multiplicity的新formal freeze。
