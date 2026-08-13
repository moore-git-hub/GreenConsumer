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

**状态：implemented and finite-horizon engineering suite PASS**

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

### 验证结果

Fake T30/T35/T40 nested horizon suite 已通过，`prefix_invariance_failures=0`。因此延长未来运行时间没有反向改变既有历史状态。T35 保持 primary endpoint；T30/T40 仅用于 endpoint robustness。

完整说明见：

- `V331_TIME_HORIZON_AND_SCALE_DESIGN.md`；
- `V331_HORIZON_ROBUSTNESS_PLAN.md`；
- `V331_HORIZON_ROBUSTNESS_RESULT_20260813.md`。

### 禁止表述

- “文献证明危机30日内一定恢复”；
- “20个Agent等同于真实消费者样本量20”；
- “T35是根据显著性选出的最佳终点”。

---

## DR-20260813-04：Runtime horizon guard 单元测试与重依赖隔离

**状态：implemented and re-verified**

### 触发原因

T35 runtime guard 修复后，首版回归测试为验证 `run_scenario_v33()` 能接受 T35，直接 `import simulation_core` 并触发 AgentKernel embedding / Hugging Face 依赖树。测试因此出现 HTTP client 生命周期错误，而非 scientific mechanism 错误。

### 决策

- runtime约束抽取为纯函数 `_validate_runtime_config_v331()`；
- 在任何 `simulation_core` 重依赖导入之前验证；
- unit test 不再为整数/配置guard触发外部模型初始化；
- full Fake horizon suite另作为 end-to-end integration verification。

### 不改变

心理、传播、购买机制、T35设计、Agent数量、随机种子、Fake/Real LLM输出与推断计划均不改变。

---

## DR-20260813-05：Trust 参数敏感性 Stage A

**状态：executed; PASS**

### 触发原因

`mechanism_v33.py` 将 crisis/repair retention、event/quiet adjustment、repair saturation、hypocrisy weight 与 empathy repair weight 明确标记为 development engineering assumptions，而非总体经验参数。正式 inference 前需要检验主要结果是否由某一单点设定驱动。

### 设计

- Fake LLM、T35、20 cognitive Agents、25 micro-buyers、BA topology、处理矩阵与三个 seeds 全部固定；
- 七个 Trust 参数分别使用预先规定 low / baseline / high；
- 加入 `retention_symmetric_097`、`retention_reversed_096_098`、`legacy_v32_transition`；
- baseline + 14 OAT + 3 structured boundaries = 18 profiles；
- 不允许根据结果重新选择 baseline。

### 结果

`trust_20260813_110718`：

- 18 profiles 全部完成；
- 54/54 implementation invariants PASS；
- invariant failures = 0；
- P1/P2/P3/P4/P5/S1 在全部 profiles 中均无方向翻转；
- P1/P5 对 `repair_retention`、`empathy_repair_weight`、`event_adjustment` 较敏感；
- P2 对 `empathy_repair_weight` 最敏感；
- P3 对 `event_adjustment` 最敏感；
- P4 在所有 profiles 中严格保持 0.45，符合 Trust 与 direct reach 的机制分离；
- S1 对 Trust 参数变化很弱。

完整结果见：

- `V331_TRUST_PARAMETER_SENSITIVITY_PLAN.md`；
- `V331_TRUST_PARAMETER_SENSITIVITY_RESULT_20260813.md`。

### 解释边界

Stage A 只支持 local/boundary robustness；不能识别多参数交互，也不能把 low/high 解释为现实参数置信区间。

---

## DR-20260813-06：Trust 参数敏感性 Stage B — Morris global screening

**状态：pre-specified and implemented; execution pending**

### 触发原因

Stage A 无方向翻转，但 OAT 无法判断多参数同时变化下的非线性与交互迹象。需要在同一预先规定 parameter envelope 内进行全局 screening。

### 设计

采用 Morris elementary effects：

- `k=7` Trust parameters；
- `p=6` levels；
- normalized `Delta=0.6`；
- `r=10` random trajectories；
- 每条 trajectory 8 points；
- 每个参数每条 trajectory 恰改变一次；
- design seed=`2026081801`；
- 相同参数点允许复用确定性 Fake evaluation；
- 不允许结果出来后删除轨迹、追加轨迹或调整 parameter bounds。

主要统计量：

- `mu`：平均有方向 elementary effect；
- `mu_star`：平均绝对 elementary effect，用于同一 estimand 内全局筛查排序；
- `sigma`：非线性和/或参数交互迹象；
- `sigma/mu_star`：仅作描述性辅助，不设机械分类阈值。

### 固定部分

Fake LLM、T35、20 cognitive Agents、25 micro-buyers、BA topology、K=3、paid edge probability、delivery lag、三个 seeds、treatment matrix、persona 与刺激文本全部保持冻结。

### 实现不变量

- Morris轨迹结构、grid、step、bounds必须全部PASS；
- 所有 evaluations 的 T1–T4 key states一致；
- network hash一致；
- P4 direct reach一致且 Morris `mu_star=0`；
- 参数provenance完整。

### 科学依据

- Morris (1991) elementary-effects screening；
- Campolongo, Cariboni & Saltelli (2007) 使用 `mu_star` 改进因素重要性筛查；
- Morris `sigma` 只能提示非线性/交互，不能唯一分解二者；
- 若需要 first/total variance effects，再对筛出的关键参数单独设计 variance-based analysis。

完整说明见 `V331_TRUST_PARAMETER_MORRIS_PLAN.md`。

### 禁止表述

- Morris ranking 是真实消费者参数的因果重要性；
- `sigma` 单独证明某两个参数存在交互；
- Morris 等同于 Sobol variance decomposition；
- 根据 Morris 排名重新调 baseline。

---

## 后续预登记决策队列

- Stage-B Morris 结果记录；
- 必要时对关键 Trust 参数实施 variance-based first/total-effect analysis；
- `paid_edge_probability` / lag sensitivity；
- network size N=20/40/80；
- fixed-K 与 proportional-K targeting budget；
- BA / WS / community topology robustness；
- micro-buyers 10/25/50；
- prompt sensitivity / LLM stochasticity；
- v3.3.1 pilot variance estimation 与正式 replication-block 数量；
- confirmatory estimands / MDE / multiplicity procedure 的新 formal freeze。
