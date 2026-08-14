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

保持同一20个Engineering Personas、Fake LLM、T35、25 micro-buyers/Agent、K=3、p=.55、lag=1、Trust baseline、simulation/LLM/demand seeds与处理矩阵不变，仅改变network topology与独立network-only seed。BA、WS和Community SBM各5张网络，共15 profiles。

`topology_20260813_153842`：76/76 invariants PASS，baseline BA hash精确复现。P1、P2、P3、P5、S1在15张网络上均保持方向；P4出现拓扑边界：BA 5/5 positive（mean=.40），Community 5/5 positive（mean=.17），WS为4 positive + 1 zero（mean=.12）。因此“Hub一定优于Random”不允许作为无条件结论，只能写为依赖degree heterogeneity / hub distinguishability的结构性优势。

详见：`V331_NETWORK_TOPOLOGY_ROBUSTNESS_PLAN.md`、`V331_NETWORK_TOPOLOGY_ROBUSTNESS_RESULT_20260813.md`。

---

## DR-20260813-09：Network size × paid-seed allocation robustness

**状态：executed; engineering PASS**

### 设计

仅使用BA m=2，N=20/40/80，各5个network-only seeds。比较：

- fixed paid-seed count K=3；
- proportional paid-seed share K/N=15%，即K=3/6/12。

N20/K3为共同baseline，共25 unique profiles。注意这里的“预算”只代表paid-seed allocation，不是完整货币预算；`public_exposure_rate_fixed=.25`始终冻结。

### Persona扩展

使用nested balanced mechanism-coverage panel，而非复制原20人：Panel20为冻结20 Persona；Panel20 ⊂ Panel40 ⊂ Panel80；N80含80个唯一categorical persona tuples；六维categorical marginals在N20/40/80保持完全相同比例。这些比例是engineering mechanism coverage，不是现实人口权重。

### 验证

`size_20260813_164031`：109/109 invariants PASS；baseline N20 hash复现、panel prefix/no-clone、node set、K完整性、每run网络hash一致、clarification p=.55/lag=1冻结、shared N20 T1–T5 prefix均通过。

### 结果

5张BA网络的family means：

- N20/K3：P1=.25247，P3=.26376，P4=.4000，P5=.016787；
- N40/K3：P1=.22679，P3=.24256，P4=.2500，P5=.013931；
- N40/K6：P1=.28276，P3=.30406，P4=.3350，P5=.017922；
- N80/K3：P1=.20413，P3=.23527，P4=.2200，P5=.013511；
- N80/K12：P1=.29643，P3=.33682，P4=.3275，P5=.019803。

所有families的5/5 realizations均保持P1/P3/P4/P5/S1正、P2负。

固定K时K/N随N增大而稀释，Hub mean reach从.760降至.625/.545，P1/P5相应减弱；保持K/N=15%时Hub mean reach为.760/.785/.7925，总体clarification与P5保持或增强。Random reach也随proportional K增加，因此P4差值不需要与Hub reach同方向单调变化。

### 决策

N20的BA Hub优势不是5个百分点reach粒度的纯artifact；在N40/N80仍保持正向。主科学baseline继续保留N20/K3用于受控机制实验，N40/N80作为规模与paid-seed allocation边界证据，不依据结果改动baseline。

详见：`V331_NETWORK_SIZE_AND_BUDGET_ROBUSTNESS_PLAN.md`、`V331_NETWORK_SIZE_AND_BUDGET_ROBUSTNESS_RESULT_20260813.md`。

---

## DR-20260813-10：Equal-degree edge orientation robustness

**状态：executed; engineering PASS with WS sign-instability boundary**

Topology suite显示WS具有30%–80%的equal-degree tie-edge share。为排除WS较弱P4只是tie-breaking artifact，在同一15张预设无向底图上比较`legacy_first_endpoint`、`reverse_first_endpoint`、`hash_balanced`三种规则，共45 profiles。

`orientation_20260813_162126`中241/241 invariants PASS。P4 family mean：BA legacy=.40/reverse=.39/hash=.40，Community=.17/.19/.18，WS=.12/.05/.14。BA和Community的5/5无向图全部保持P4正向；WS有2张出现sign instability。不能把WS单一legacy P4解释为稳定topology-only effect；缺乏真实follower/followee方向数据时，tie rule仍是engineering assumption。

该结果不改变冻结BA baseline orientation。

详见：`V331_NETWORK_ORIENTATION_ROBUSTNESS_PLAN.md`、`V331_NETWORK_ORIENTATION_ROBUSTNESS_RESULT_20260813.md`。

---

## DR-20260813-11：Micro-buyer numerical-resolution robustness

**状态：executed; engineering PASS**

### 触发原因

Baseline demand layer使用25 micro-buyers/cognitive Agent表示persona内部preference/PBC/loyalty异质性。Micro-buyers不是独立统计样本，25是engineering numerical resolution，需要验证P5/S1是否依赖该离散化。

### 设计

复用已经完成的`size_20260813_164031`中5个N20/K3 BA cognitive blocks，不重跑AgentKernel/LLM。只重新运行downstream demand：

```text
M = 10 / 25 / 50 micro-buyers per cognitive Agent
```

共5 network histories × 3 resolutions = 15 demand profiles。M25始终是冻结baseline。

`build_scenario_micro_cohort()`的balanced normal quantile位置依赖micro_count，因此M10/M25/M50应解释为不同deterministic quadrature resolutions，而不是nested samples；不得做micro-buyer prefix-invariance解释。

### Hard checks

- source size suite PASS / zero invariant failures；
- 不调用simulation_core/AgentKernel/LLM；
- M25必须逐network seed精确复现source P5/S1（1e-12 tolerance）；
- P1/P2/P3/P4在M10/25/50内必须不变；
- 每个Persona生成准确且唯一的M个buyer IDs。

### 执行结果

`micro_20260813_190453`完成15个demand-resolution profiles（5个冻结N20/K3 BA cognitive histories × M10/M25/M50），suite status=PASS。P5与S1在全部5个network histories中均未出现resolution-induced sign reversal；suite PASS同时要求M25逐network seed精确复现source P5/S1、P1–P4跨M严格不变、buyer count/ID integrity及source provenance检查通过。

该结果只支持numerical-resolution robustness与layer-separation，不支持将25 micro-buyers解释为现实消费者样本量或经验校准值。Baseline继续冻结为M=25，不依据结果选择M。

### 解释边界

该阶段是numerical-resolution robustness，不是power analysis。微观买家不得作为正式推断独立单位；未来正式GABM推断单位仍是replication block。无论结果如何，不允许选择产生更有利P5的M。

详见：`V331_MICROBUYER_RESOLUTION_ROBUSTNESS_PLAN.md`、`V331_MICROBUYER_RESOLUTION_ROBUSTNESS_RESULT_20260813.md`。

---

## DR-20260813-12：Real-LLM prompt-layout 与 practical stochasticity robustness

**状态：pre-specified; zero-API validation PASS; execution pending**

### 触发原因

Fake-LLM structural robustness链已经覆盖有限时间范围、Trust参数、clarification reach/lag、network topology、equal-degree orientation、network size/paid-seed allocation以及micro-buyer numerical resolution。下一阶段只检验LLM semantic appraisal layer对prompt版式和实际provider/runtime non-determinism的敏感性。

### 冻结设计

保持以下内容不变：

- `qwen-plus`；
- temperature = `0.3`；
- requested LLM seed = `2026081601`；
- simulation seed = `2026081501`；
- demand seed = `2026081701`；
- T35；
- N=20 cognitive Agents；
- M=25 micro-buyers/Agent；
- frozen BA baseline、K=3；
- clarification p=.55、lag=1；
- frozen v3.3 Trust parameters；
- 2×2×2 treatments + common control；
- control-first common-history replay。

Prompt profiles预先固定为：

1. `baseline_exact`；
2. `compact_separator`；
3. `schema_first`。

Practical stochasticity重复为：

- `baseline_r1`；
- `baseline_r2`；
- `baseline_r3`。

完整suite共5个unique Real-LLM blocks：

- `baseline_r1`；
- `compact_r1`；
- `schema_first_r1`；
- `baseline_r2`；
- `baseline_r3`。

### 执行前验证

Zero-API tests：25/25 PASS。

`run_v33_llm_robustness.py --plan-only`：

- status = PLAN_ONLY；
- profiles_count = 5；
- baseline_repeats = 3；
- real_llm_calls_started = false。

Real-LLM preflight：

- Python 3.12.13；
- dependency check PASS；
- model config verified；
- builder bootstrap verified；
- DashScope API key present；
- external API calls = 0；
- real LLM calls = 0。

### 解释边界

该阶段仅属于selected Real-LLM engineering robustness，不进行p-values、confidence intervals或population inference。不得根据结果选择更有利的prompt、修改temperature、替换seed或重新调主体机制。Prompt sign reversal或semantic manipulation collapse必须作为boundary condition报告。

详见：`V331_REAL_LLM_PROMPT_AND_STOCHASTICITY_ROBUSTNESS_PLAN.md`。

---

## 后续预登记队列

- Real-LLM prompt-layout / practical stochasticity结果记录；
- 必要时 matched-metric topology experiment；
- v3.3.1 pilot variance estimation与正式replication-block数量；
- confirmatory estimands / MDE / multiplicity的新formal freeze。