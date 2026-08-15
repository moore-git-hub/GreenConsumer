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

**状态：executed; engineering PASS**

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

### 执行结果

`llmrob_20260814_230111`完成全部5个预登记Real-LLM blocks，suite status=PASS，process exit code=0。总provider calls为743；`invariant_failures=0`；`prompt_sign_unstable_estimands=0`；`baseline_repeat_sign_unstable_estimands=0`。未计算p-values或confidence intervals，也未进行formal inference；`prompt_selection_permitted=false`。

该结果支持有限的方向稳健性表述：在固定模型、temperature、请求seed、simulation/demand seeds、T35及主体机制的条件下，两种预登记prompt版式/顺序扰动与三次完全相同baseline prompt重复均未导致已报告estimand方向翻转。不得据此断言任意prompt都无影响，也不得把三次重复解释为统计稳定性证明。

### 解释边界

该阶段仅属于selected Real-LLM engineering robustness，不进行p-values、confidence intervals或population inference。不得根据结果选择更有利的prompt、修改temperature、替换seed或重新调主体机制。Prompt sign reversal或semantic manipulation collapse必须作为boundary condition报告。

Baseline继续冻结为`baseline_exact`；不依据本次结果修改prompt profile、temperature、seed、Trust、network或demand参数。

详见：`V331_REAL_LLM_PROMPT_AND_STOCHASTICITY_ROBUSTNESS_PLAN.md`、`V331_REAL_LLM_PROMPT_AND_STOCHASTICITY_ROBUSTNESS_RESULT_20260814.md`。

## DR-20260815-13：v3.3.1正式处理范围与Pilot规划冻结

**状态：treatment and pilot protocol frozen; pilot not executed; formal not authorized**

正式范围固定为`Rational-evidence / Emotional-empathy × Hub / Random × Immediate / Delayed`八个完全交叉策略单元，加一个共同`NoClarification-Control`。不增加Bridge、KOL、独立credibility、独立evidence strength、endorsement或其他正式处理因素。`Rational-evidence`与`Emotional-empathy`是复合文本策略，只允许解释完整内容框架的对比，不允许拆解为单个语义属性的独立因果效应。

确认性family冻结为P1总体澄清Trust、P2内容Trust、P5总体澄清预期重复品牌选择；P3时机和P4企业直接reach保持探索性/机制性。P4不允许解释为说服或购买。正式P5固定`conversion_support=absent`，既有S1仅作为工程机制分离诊断，不形成第四个正式因素。

Pilot预设3个simulation/network seeds×2个requested LLM seeds，共6个完整cognitive blocks，并对每个cognitive history离线交叉3个demand seeds。Pilot只估计planning variance和工程性variance components，不计算正式p-value、不选择策略胜者、不修改机制。正式N将在Pilot后通过预先规定的Holm operating-characteristic规则选择；可执行上限`N_max`必须在Pilot前依据用户批准的provider-call与时间预算冻结，不得根据Pilot结果调整。最终N将写入协议1.1；在此之前`FORMAL_NOT_AUTHORIZED`。

完整规则见：`FORMAL_EXPERIMENT_PROTOCOL.md`。

### TASK-PV01实现更新（Pilot执行前）

**状态：zero-API infrastructure complete; pilot not executed; formal not authorized**

已实现独立`run_v33_pilot_variance.py`与`greenconsumer_v33/pilot_variance.py`：冻结P001–P006和D1–D3，提供seed/attempt/validity合同、provider-call硬上限、clean branch/HEAD门禁、失败即停止且禁止replacement seed、P1/P2两向与P5三向method-of-moments方差分解、保守planning SD以及Holm operating-characteristic模拟。OC在multivariate-normal planning model下使用相关正态样本均值与Wishart样本协方差联合构造相关t统计量；该假设只用于设计，不是Pilot效应结论。普通import、`--plan-only`和`--analyze-existing`均不加载AgentKernel或构建router。

在任何Pilot结果产生前，明确global-null Monte Carlo门槛为`.05 + 2×MCSE`。原因是Holm规则本身提供strong FWER control，而有限次数Monte Carlo估计会围绕.05随机波动；该阈值仅用于检验实现与理论规则是否兼容，不能被写成新的显著性标准，也不得依据未来Pilot结果修改。正式N仍只使用预设MDE与保守planning SD，不使用Pilot mean、sign或策略排序。

当前没有获批`N_max`、provider-call ceiling、clean frozen execution SHA或真实LLM执行授权，故P001–P006仍为`PLANNED_NOT_EXECUTED`。

## DR-20260815-14：实验结果证据层级与跨版本使用边界

**状态：evidence register established; no experiment rerun; no inference change**

用户补充了五份既有实验叙述材料。核对后，clarification diffusion、network size/paid-seed allocation和Trust Stage-A/Morris总结与仓库中已提交的v3.3.1结果记录一致；网络拓扑补充文件本身只包含研究问题和执行前检查，不构成结果，论文引用必须改用`V331_NETWORK_TOPOLOGY_ROBUSTNESS_RESULT_20260813.md`；`预实验结果.md`属于v3.2 Variance10与N=10设计沿革，不能替代当前v3.3.1 Pilot。

证据优先级固定为：仓库冻结合同/原始数据/manifest > 仓库版本化结果记录与原始文件SHA > 用户叙述性总结 > 问题/计划记录。v3.2 F001–F010保持closed formal archive；v3.3.1 sensitivity/topology/size/Real-LLM结果保持engineering validation。不同版本不得合并估计、共同计算p值或互相补足正式N。当前v3.3.1协议只继承v3.2中预先存在的P1/P2/P5角色和量纲一致MDE，不继承其Variance10方差或N。

完整审查与论文使用边界见`EXPERIMENT_EVIDENCE_REGISTER.md`。本次登记新增模型运行=0、真实LLM调用=0、正式推断=0。

---

## DR-20260815-15：论文追踪体系与认知演化后处理口径

**状态：zero-API implementation complete; real-run rendering pending; no scientific-model change**

为使代码工作可以严谨进入论文的模型设计、系统构建、实验设计和仿真结果章节，新增v3.3.1 model-to-code traceability及稳定的工作/表图artifact登记。登记状态明确区分artifact存在、生成器已实现但尚未渲染、计划未执行与未获授权，禁止把planned output写成已有结果。

认知演化后处理固定使用两类已落盘记录：`cognitive_records.csv`提供显式机制状态，`agent_thoughts.csv`提供模型按schema返回的一句显式appraisal及其语义字段。`reasoning`只原样登记，不进行新的情绪/主题编码，不解释为隐藏chain-of-thought，也不作为现实消费者认知证据。

时间变化比较在查看新结果前固定为T5−T4、T6−T5、T10−T9以及T终点−T5。输出为单run的Agent均值、within-Agent差和Agent间描述性SD，不计算p值、置信区间或formal standard error；正式推断单位仍是未来的replication block。输入必须通过summary horizon一致性、Agent×Tick键一一对应、无重复和完整面板检查，manifest记录输入与输出SHA-256。

实现文件为`greenconsumer_v33/cognition_outputs.py`、`run_v33_cognition.py`和对应zero-API tests。当前只完成synthetic fixture验证，尚未对保留的真实v3.3.1 run生成和视觉审查表图。因此进度台账仍将“Agent cognition evolution论文输出”记为部分完成，不报告任何认知演化结果。

本次变更修改科学参数=0、GABM run=0、provider call=0、Pilot observation=0、formal inference=0。

详见：`MODEL_TO_CODE_TRACEABILITY_V331.md`、`THESIS_WORK_AND_OUTPUT_REGISTER.md`。

---

## DR-20260815-16：论文绘图统一使用无界面Matplotlib后端

**状态：implemented and Windows full-suite validated; no scientific-model change**

Windows `Kernel`环境首次全量复验得到123项通过、1项失败。唯一失败发生在`test_stage_a_replot_is_postprocessing_only`创建Matplotlib画布时：自动选择的`TkAgg`依赖不完整的Tk/Tcl安装，尚未进入数据绘图、估计量计算或断言比较。因此该失败属于绘图运行环境兼容性，不构成模型机制、统计分析或既有结果失败。

审计确认v3.3.1绘图模块均只将图形写入PNG/GIF，不提供交互式`plt.show()`界面。现统一在导入`pyplot`前显式设置`Agg`后端，并增加后端合同测试。该变更不修改输入CSV、指标、参数、随机种子、估计量或图中数值，只消除Tk/Tcl GUI依赖并提高Windows/headless环境下的可复现性。

本地以`MPLBACKEND=TkAgg`进行反向兼容测试时，模块成功强制切换为`Agg`，Stage-A与Morris三项直接测试通过，Python编译与`git diff --check`通过。依据用户提供的本地终端输出，远端commit `ab74a2e2cdba3029ae2f623fa0fb8f49128f6df1`随后在Windows `Kernel`环境执行全量`pytest -q`，结果为125项全部通过、用时5.04秒。测试总数比修复前的124项多1项，来源是本次新增的无界面后端合同测试，不是删除失败测试或改变既有断言。Windows全量复验门槛据此关闭。

本次修复新增模型运行=0、真实LLM调用=0、Pilot观测=0、正式推断=0。

---

## DR-20260815-17：认知演化源run选择与后处理代码provenance

**状态：source run pre-selected; provenance hardening implemented; rendering pending**

本地结果发现共识别5个clean Real-LLM、T35、9条件的v3.3.1完整run，另有1个dirty单条件smoke run和1个dirty Fake-LLM run。论文认知演化输出在查看轨迹结果前固定使用`llmrob_20260814_230111/profiles/baseline_r1/v331_20260814_230111`：它是预登记`baseline_exact`的首次运行，源Git HEAD为`f52c97fcdf88efd0df2bec01e80bac2f63d9233b`且worktree clean。不得在`baseline_r1/r2/r3`、`compact_r1`和`schema_first_r1`之间根据生成图形选择更有利的run；后四者只保留为prompt/stochasticity工程稳健性证据。

生成真实表图前发现原manifest只记录源文件与输出文件SHA，不能单独识别后处理代码版本。现新增源运行Git provenance、后处理Git provenance，以及`greenconsumer_v33/cognition_outputs.py`和`run_v33_cognition.py`的SHA-256与字节数。该补强不修改源run、心理状态、统计口径或图中数值。真实生成时后处理worktree必须clean，manifest中的postprocessor SHA必须与执行分支相符。

本次仅完成候选筛选、provenance代码与合成测试：新增GABM run=0、provider call=0、Pilot observation=0、formal inference=0。真实表图仍须用户在本地ignored results目录运行并回传manifest和三张PNG进行视觉审查。

---

## DR-20260815-18：真实认知schema重名字段兼容修复

**状态：implemented and regression-tested; real rendering retry pending**

首次对预选`baseline_r1/v331_20260814_230111`执行零API认知后处理时，在生成任何manifest或结果结论前失败。原因是真实`cognitive_records.csv`与`agent_thoughts.csv`都包含`semantic_observation_present`、`semantic_social_observation_count`和`semantic_fallback_used`等审计字段；合成fixture此前只在thoughts侧包含这些列。pandas合并后自动生成`_x/_y`列名，而聚合器仍引用无后缀列，触发`KeyError`。

修复将`agent_thoughts.csv`中的5个审计字段先重命名为内部`thought_audit__*`字段，再与认知状态合并；公开输出列名与指标口径不变。选择thoughts侧是因为这些比率定义为显式appraisal/observation audit availability，而非心理状态重复列。回归fixture现故意在cognitive侧加入冲突值，验证聚合器仍使用thoughts侧审计来源。7项认知后处理直接测试、Python编译和格式检查通过。

失败运行没有修改源run、没有调用LLM、没有生成Pilot观测或正式推断。真实表图仍须在补丁提交后的clean worktree重跑，旧失败尝试不得登记为结果。

---

## DR-20260815-19：认知演化图形的量纲安全与因子编码

**状态：redesign implemented and synthetic visual QA passed; final real rerender pending**

修复schema后，预选的clean Real-LLM `baseline_r1/v331_20260814_230111`成功生成5表3图，manifest payload为PASS且明确`formal_inference_performed=false`。首次视觉审查在形成任何论文结论前发现三个表达问题：九条条件轨迹仅靠独立颜色区分；事件线没有清晰说明；最重要的是，恢复热图把0–10量纲的Trust和0–1量纲的Attitude、Subjective norm、Purchase intention放入同一原始数值色标，色彩强度不允许跨变量解释。

现将条件编码固定为实验因子而非九种任意颜色：内容框架由颜色表示，传播渠道由实线/虚线表示，时机由圆/方标记表示，共同Control使用黑色；T5/T6/T10明确标记为Crisis/Immediate/Delayed。恢复热图被永久替换为四个保留变量原单位的水平条形分面，并在图下注明不得跨面板比较条长。显式appraisal折线图改为condition×Tick availability matrix，以减少大量重合线，并继续明确其测量的是记录可用率而非reasoning质量。

本次重设计不修改源CSV、Agent状态、transition定义、均值、任何科学参数、随机种子或推断口径。旧文件`02_recovery_transition_heatmap.png`被标记为superseded，不得用于论文；新manifest只登记`02_recovery_transition_facets.png`。最终状态仍为`IMPLEMENTED_NOT_RENDERED`，直到用户在clean新commit上对同一个预选run重新生成并回传新manifest、三张新图和数值表完成审核。

本次新增GABM run=0、provider call=0、Pilot observation=0、formal inference=0。

---

## DR-20260815-20：Agent异质性与Control调整的认知恢复展示

**状态：limited descriptive evidence admitted; clean real rerender, independent artifact audit and Windows regression gate passed**

### 触发原因与审计结果

用户回传schema 1.1 manifest、三张图、Tick/transition summary与完整`04_agent_transition_ledger.csv`。上传文件的字节数和SHA-256均与manifest一致；source run继续是预先固定的clean `baseline_r1/v331_20260814_230111`，后处理commit为clean `353ea074aef1c2b0aecca7e26e1b54457eb9b77b`。Agent ledger含720/720条预期记录（9 conditions×20 Agents×4 transitions），无缺失键或重复键，所有condition×transition均为同一20个Agent；其mean/SD/min/max与`05_transition_summary.csv`最大差异为`1.11e-16`，T4→T5 crisis change逐Agent跨条件完全相同。

完整分布显示，原始均值分面虽然数值正确，但掩盖了大量零contrast、长尾以及同一条件内的方向异质性。尤其Random渠道的matched treatment-minus-Control contrast常集中在少数被触达Agent上，mean不能单独展示这种extensive-margin机制。因此原均值图可保留为表5中的描述性汇总，但不再作为正文主要机制图。

### 决策

Schema升级为`task005_fmcg_v331_cognition_outputs1.2`。新增`06_control_adjusted_agent_recovery.csv`，对每个处理条件、同一Agent和每个state记录：处理条件的T5→endpoint change、Control的同期间change及二者之差。FIG-COG-02使用这一matched contrast，显示全部Agent点、IQR、median、mean和正/零/负计数；四个panel保留各自单位。该配对依赖固定Persona/Agent身份与已经验证的common-history合同。

本决策是在查看schema 1.1真实分布后作出的post-result descriptive visualization adjustment，不是预登记confirmatory estimand，不允许用于p-value、置信区间、稳定策略排名或population inference。Agents仍不是独立replication blocks。所有原始transition定义、表5均值、模型参数、状态、随机种子和源run保持不变。

### 最终准入记录

用户在clean postprocessor commit `ce736f442c74bef404940f6dcaf8009c4015a1da`上对同一预选run完成schema 1.2真实重生成。manifest记录9项输出；新图2与表6的上传文件SHA-256分别为`fd8ddcd35208eb32ba4fd4ce05805ad2ab3c48cc0d251de5848f49a1d9f57cf6`和`225be16469ccb329d8a9cfd7a9796f721c8dfb1c1d763d35ad80a024fd233676`，其余7项输出hash与已独立审计的schema 1.1文件保持一致。manifest明确`formal_inference_performed=false`、`external_validity_claimed=false`和`text_coding_performed=false`。

表6含1120行（8 treatments×20 Agents×7 states），无缺失键、重复键或Agent集合漂移；每个Agent-state的Control change在8个处理条件中完全相同，`condition_delta - control_delta - control_adjusted_delta`及其对源Agent ledger的最大重构误差均为`1.665e-16`。图2视觉审查确认四个panel保留变量各自单位，完整显示20个Agent、零线、IQR、median、mean与正/零/负计数，且页脚明确Agents不是replication blocks。全部9项输出的manifest hash链据此闭合。

用户随后确认既定的认知直接测试和Windows `Kernel`全量测试在该clean代码commit上均通过；本轮没有回传测试数量或用时，因此本记录不补写未观察值。最终准入结论为`DESCRIPTIVE_EVIDENCE = ADMISSIBLE_WITH_LIMITATIONS`：仅允许描述这一固定单次Real-LLM工程run中的轨迹、可用率和Agent异质性；`FORMAL_INFERENCE = NOT_AUTHORIZED`，不得报告p-value、置信区间、稳定策略排名或总体外推。

本阶段新增GABM run=0、provider call=0、Pilot observation=0、formal inference=0。

---

## DR-20260815-21：论文写作基础包、框架图重构与Pilot预算上限

**状态：writing foundation available; `N_max=10` frozen; Pilot not executed; formal not authorized**

用户提供七个理论文献包、五篇同专业硕士论文、旧版框架图、研究问题和导师意见，要求先完成论文写作基础包，并在之后冻结Pilot执行条件时采用N=10。材料清点得到57份PDF，4组重复，SHA-256去重后为53份唯一PDF。文献台账只准入可由PDF原文及出版社/期刊页面核验的书目信息和主张；硕士论文仅用于学习章节结构、标题层级、图表说明与中文论证风格，不作为理论事实的替代证据，也不复制其表述。

新增`docs/thesis/THESIS_WRITING_FOUNDATION_V331.md`和`docs/thesis/LITERATURE_AND_STYLE_SOURCE_REGISTER.md`，固定研究定位、研究问题—estimand映射、理论—机制链、论文六章结构、证据等级和claim firewall。旧图中的KOL/Bridge、任意内容配比和T30口径被移除；新机制图明确LLM只执行schema约束的语义评价，Trust/Attitude/Subjective norm/intention、固定网络扩散和重复选择继续由可审计规则更新。新技术路线图区分已完成工程验证、尚未执行Pilot和未获授权的正式推断，避免将计划误画成结果。

用户给出的“N选取为10”在科学协议中解释为Pilot结果揭示前冻结正式replication-block上限`N_max=10`，而不是宣称Pilot规模为10或正式N已经获得统计依据。P001–P006六个Pilot blocks不变；由于formal N的候选范围原为`10..N_max`，当前唯一候选为N=10。Pilot后只有当预设Holm operating-characteristic规则下P1、P2、P5的marginal detection probability均达到.80时，协议1.1才可冻结formal N=10；否则必须登记`DESIGN_NOT_FEASIBLE_WITHIN_CAP`，不得提高上限、放宽门槛或依据结果重设MDE。

provider-call ceiling、时间预算、clean execution SHA和真实Pilot授权仍未冻结，因此本决策不授权P001–P006。本工作包新增GABM run=0、provider call=0、Pilot observation=0、formal inference=0。

---

## 后续预登记队列

- `N_max=10`已冻结；用户仍需冻结provider-call ceiling、时间预算与clean execution SHA，再明确授权执行P001–P006；
- Pilot完成后冻结正式N、正式seed ledger、源码/分析SHA与协议1.1；
- 必要时 matched-metric topology experiment，但不得挤占正式实验准备主线。
