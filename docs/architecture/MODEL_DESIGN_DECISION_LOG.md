# GreenConsumer GABM 模型设计决策日志

本文件用于记录从 TASK_005 v3.3.1 起的模型/实验设计变更。目标是保证每一项设计选择都可以在论文中追溯到：研究目的、科学理由、工程实现、验证证据、边界条件和版本身份。

## 使用规则

今后任何会影响模型结构、实验处理、时间尺度、网络规模、参数、LLM prompt、随机过程、输出指标或推断方案的变化，都必须先追加一条 Decision Record，再运行新的正式结果。

每条记录至少包含：

1. `Decision ID / 日期 / 状态`；
2. 研究问题与触发原因；
3. 设计选择；
4. 不改变的部分；
5. 科学与文献依据；
6. 明确标注哪些是 engineering assumptions；
7. 代码路径与版本；
8. 预期影响与可能副作用；
9. 零 API / Fake / Real-LLM 验证计划；
10. sensitivity / falsification / robustness 方案；
11. 是否影响既有 formal 结果；
12. 论文中允许与禁止的表述。

任何“因为效果不显著、图形不好看、策略排序不理想”而提出的修改，必须明确标记为 outcome-driven；在正式冻结之后原则上不允许据此修改主模型。

---

## DR-20260813-01：v3.3 Trust / Reach / Renewal 机制升级

**状态：implemented and engineering-validated**

### 决策

在不修改 v3.2 正式 F001–F010 的前提下，建立并行 v3.3：

- Trust：非对称 crisis/repair memory retention、event/quiet partial adjustment、repair saturation、hypocrisy amplifier；
- Clarification：public Bernoulli exposure、K=3 paid seeds、lagged probabilistic one-hop amplification；
- Demand：renewal category-purchase opportunities、bounded EWMA loyalty；
- 不通过提高 LLM temperature 或向 Trust 直接加随机噪声制造更“自然”的曲线。

### 科学理由

解决旧动态中过强的同步事件脉冲、线性恢复、Hub ceiling 与固定购买周期。修改依据是机制可解释性与模型内部结构问题，而不是为了追求某一预期的显著结果。

### 既有结果影响

v3.2 F001–F010 不得复用为 v3.3 formal inference。

---

## DR-20260813-02：v3.3.1 Social Feed 与审计文本完整性修复

**状态：implemented and Real-LLM re-audited**

### 触发原因

Real-LLM cognition audit 发现 receiving LLM 的 Social Feed 存在 `[:180]` 字符截断，部分 Agent 将代码截断错误理解为“peer message incomplete”。同时，审计 CSV 对 `post_content` / `reasoning` 存在 200/300 字符落盘截断。

### 决策

- 新增版本隔离的 `GreenCognitionV33Plugin`，保留完整 selected peer-post text；
- v3.3 runtime 中恢复完整 reasoning/post audit text；
- 不修改 Trust、Demand、network、temperature 与 treatment；
- 新增完整性测试。

### 科学理由

这是 measurement/input integrity 修复。Social text 截断会实质影响 peer approval、SN、semantic appraisal 和 downstream network dynamics，因此必须在模型冻结前纠正。

### 验证

修复后的 Real-LLM engineering block 中，先前出现的 truncated/incomplete social appraisal artifact 消失，同时 Rational→Evidence、Empathy→Perceived Empathy 和 peer-only SN boundary 保持成立。

---

## DR-20260813-03：有限时间范围改为 T35 baseline

**状态：implemented before new v3.3.1 formal inference**

### 触发原因

工程运行显示 T30 时 Trust 与 repeat-choice trajectories 仍处于恢复/累积过程中。研究对象是有限时域品牌危机修复，而不是要求达到长期稳态。

### 决策

- 1 Tick 定义为 1 simulation day；
- Crisis = T5；
- baseline endpoint = T35；
- T35 对应 crisis 后 30 日；
- T30 / T40 预先规定为 horizon robustness；
- CLI 只允许 `--total-ticks 30/35/40`，防止事后任意选择终点；
- v3.2 历史 30-Tick formal design 保持不变。

### 不改变

- cognitive Agents = 20；
- micro-buyers = 25 / cognitive Agent；
- BA baseline topology；
- Trust v3.3 参数；
- clarification lag/probability；
- Real-LLM model/temperature；
- 2×2×2 + common control treatment matrix。

### 科学依据

- ODD protocol 要求明确描述模型尺度、设计 rationale 与 simulation experiments；
- GABM文献表明小规模生成式 Agent 可用于机制/动态研究，但小 N 不构成网络外部代表性证明；
- T35 不是文献给出的经验最优天数，而是“危机后30日”这一可解释的有限观察窗口；
- 通过预先规定 T30/T40 检验 endpoint sensitivity。

完整说明见 `V331_TIME_HORIZON_AND_SCALE_DESIGN.md`。

### 论文允许表述

“主仿真终点在新的正式模拟前预先设定为 T35，即危机发生后30日，并以T30/T40检验时间范围稳健性。”

### 禁止表述

- “文献证明危机30日内一定恢复”；
- “20个Agent等同于真实消费者样本量20”；
- “T35是根据显著性选出的最佳终点”。

---

## DR-20260813-04：Runtime horizon guard 单元测试与重依赖隔离

**状态：implemented; local re-verification pending**

### 触发原因

T35 runtime guard 修复后，首版回归测试为了验证 `run_scenario_v33()` 能接受 T35，直接 `import simulation_core` 并 monkeypatch 主运行函数。该导入会加载 AgentKernel 的 embedding / Hugging Face 依赖树。在同一 pytest 进程中出现 Hugging Face HTTP client 生命周期冲突，导致测试报 `Cannot send a request, as the client has been closed`；同时产生对 sentence-transformers 模型的网络 HEAD 重试。

该失败发生在测试基础设施层，不是 T35 scientific mechanism、Trust、Demand 或 horizon guard 本身的失败。

### 决策

- 将 runtime 参数约束抽取为纯函数 `_validate_runtime_config_v331()`；
- `run_scenario_v33()` 在任何 `simulation_core` 重依赖导入之前调用这一纯函数；
- horizon guard 单元测试只测试该唯一验证路径，不再导入 `simulation_core`；
- 单元测试继续覆盖：T30/T35/T40允许、T31拒绝、20 Agents约束、T5 crisis约束、version-scoped router约束。

### 科学与工程理由

Unit test 应只验证自身目标。Runtime guard 是一个确定性的实验设计不变量，不需要初始化 embedding 模型或发起任何外部网络请求。把重依赖副作用混入guard测试会降低可复现性，并可能把第三方HTTP生命周期错误误判成模型错误。

### 不改变

本修复不改变：

- 任何心理/传播/购买机制；
- T35主终点与T30/T40 horizon grid；
- Agent数量；
- 随机种子；
- Fake/Real LLM输出；
- 正式推断计划。

### 验证要求

本地重新运行 `test_task005_v331_runtime_horizon_guard.py` 后应不再触发 Hugging Face 网络访问，并全部PASS。随后再执行完整Fake horizon suite；完整suite属于end-to-end integration test，与纯guard unit test分层处理。

---

## DR-20260813-05：Trust 参数敏感性 Stage A

**状态：pre-specified and implemented; execution pending**

### 触发原因

`mechanism_v33.py` 明确将 crisis/repair retention、event/quiet adjustment、repair saturation、hypocrisy weight 与 empathy repair weight 标记为 development engineering assumptions，而非真实消费者总体参数。新的正式 inference 前必须检验主要结果是否由某一个单点参数设定驱动。

### 决策

先实施 **Stage A local/boundary sensitivity**，不直接宣称全局敏感性：

- 固定 Fake LLM、T35、20 cognitive Agents、25 micro-buyers、BA topology、处理矩阵与三个 seeds；
- 对 7 个 Trust 参数分别设置 pre-specified low / baseline / high；
- 加入 `retention_symmetric_097`、`retention_reversed_096_098` 和 `legacy_v32_transition` 三个结构边界 profile；
- baseline + 14 OAT + 3 structured boundaries，共 18 个 profile；
- 不允许根据 Stage A 结果改变冻结 baseline 来获得更有利的效应。

完整参数范围和论文表述见 `V331_TRUST_PARAMETER_SENSITIVITY_PLAN.md`。

### 实现边界

新增 Trust parameter injection hook，但默认仍严格等于 `DEFAULT_TRUST_PARAMETERS`。普通 `run_v33.py` 不暴露任意参数输入；只有专门的 `run_v33_trust_sensitivity.py` 使用显式 profile，因此 sensitivity 不会悄悄改变基准运行。

### Falsification / invariant checks

- Trust profile 不得改变 T1–T4 pre-crisis key states；
- network hash 必须跨 profile 一致；
- P4 direct enterprise reach 必须跨 Trust profile 一致；
- non-baseline run 必须在 provenance 中标识为 `explicit-sensitivity-profile`。

任一不变量失败时先判为实现错误，不进行科学解释。

### 方法依据

- Thiele, Kurth & Grimm (2014) 将 sensitivity analysis 视为 ABM 开发与分析的重要组成，用于理解参数变化对模型输出与机制解释的影响；
- Stage A OAT 仅用于 range verification 与局部/边界筛查；
- Stage B 预先计划 Morris elementary-effects global screening；必要时再对关键参数使用 variance-based first/total effects。

### 禁止表述

- OAT low/high 是经验置信区间；
- Stage A 已经证明全局参数稳健性；
- 根据敏感性结果重新选择“效果最好”的baseline参数；
- Fake LLM参数敏感性等价于Real LLM外部效度。

---

## 后续预登记决策队列

下列项目尚未形成结果，进入下一阶段时应分别新增 Decision Record：

- Trust-parameter sensitivity Stage B（Morris/global screening）；
- `paid_edge_probability` / lag sensitivity；
- network size N=20/40/80；
- fixed-K 与 proportional-K targeting budget；
- BA / WS / community topology robustness；
- micro-buyers 10/25/50；
- prompt sensitivity / LLM stochasticity；
- v3.3.1 pilot variance estimation 与正式 replication-block 数量；
- confirmatory estimands / MDE / multiplicity procedure 的新 formal freeze。
