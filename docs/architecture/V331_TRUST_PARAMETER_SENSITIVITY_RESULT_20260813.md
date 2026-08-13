# TASK_005 v3.3.1 Trust 参数敏感性 Stage A 结果记录

**日期：2026-08-13**  
**来源运行：`trust_20260813_110718`**  
**状态：PASS（engineering/local-boundary sensitivity）**  
**正式推断：否**

## 1. 总体结论

Stage A 共运行 18 个预先规定的 Trust parameter profiles：1 个 baseline、14 个 OAT low/high profiles、3 个 structured boundary profiles。所有运行均采用 Fake LLM、T35、20 cognitive Agents、25 micro-buyers/Agent、相同 BA baseline topology、相同 treatment matrix 与相同三类 seeds。

本轮所有实现不变量均通过：

- `PRECRISIS_INVARIANCE`：18/18 PASS；
- `NETWORK_HASH_INVARIANCE`：18/18 PASS；
- `P4_DIRECT_REACH_INVARIANCE`：18/18 PASS；
- 总 invariant failures = 0。

因此，参数注入没有污染危机前状态、网络结构或企业直接触达机制。

在 18 个 profiles 中，P1、P2、P3、P4、P5 和 S1 的方向均未发生翻转。该结果支持“在本轮预先规定的局部/边界参数范围内，主要描述性机制方向不是由某一个单点 Trust 参数设定独占驱动”。这一结论不能替代全局敏感性分析，也不能解释为真实消费者参数的经验稳健性。

## 2. Baseline descriptive estimands

| Estimand | Baseline | 解释边界 |
|---|---:|---|
| P1 clarification − control Trust | +0.250271 trust points | 单 Fake engineering block 描述值 |
| P2 Rational − Empathy Trust | −0.079291 trust points | 单 Fake engineering block；不可外推 Real LLM 内容优劣 |
| P3 Immediate − Delayed early Trust | +0.249996 trust points | exploratory timing contrast |
| P4 Hub − Random direct enterprise reach | +0.450000 | reach only；不表示 persuasion / purchase |
| P5 clarification − control expected repeat choice | +0.017007 | 约 +1.70 percentage points，描述值 |
| S1 conversion support present − absent | +0.028358 | 约 +2.84 percentage points，描述值 |

## 3. P1：总体信任修复的局部敏感性

P1 在全部 18 个 profiles 中保持正向，完整范围约为：

`+0.205933` 至 `+0.303092` trust points。

OAT 中影响幅度最大的参数为：

1. `repair_retention`：low/high 相对 baseline 分别约 −0.035563 / +0.046991；
2. `empathy_repair_weight`：约 −0.044338 / +0.044342；
3. `event_adjustment`：约 −0.023076 / +0.030405。

`quiet_adjustment`、`crisis_retention` 的局部影响明显更小；`hypocrisy_weight` 与 `repair_saturation` 对 P1 的本轮局部影响很弱。

解释：总体 Trust 修复最需要在 Stage B 中重点关注 repair-memory persistence、关系性 empathy repair channel 与 event-response speed，而不是据此重新调整 baseline 参数。

## 4. P2：内容框架差异主要受 empathy repair weight 驱动

P2 baseline 为 `−0.079291` trust points；18 个 profiles 中始终为负，完整范围约为：

`−0.119461` 至 `−0.039130`。

OAT 中最敏感的参数是 `empathy_repair_weight`：

- low：P2 ≈ −0.039130；
- baseline：P2 ≈ −0.079291；
- high：P2 ≈ −0.119461。

其次为 `repair_retention`，而 `hypocrisy_weight`、`crisis_retention` 对 P2 几乎没有局部影响。

这说明 Fake semantic fixture 下的 Rational−Empathy Trust contrast 与模型中 empathy relational-repair pathway 的参数化高度相关。该结果应被解释为机制敏感性，而不能据此声称“Empathy 在现实中一定优于 Rational”。Real LLM 单 block 曾出现更小且方向可变的内容contrast，因此内容框架结论必须与 Real-LLM robustness 分开处理。

## 5. P3：即时响应优势主要受 event adjustment 控制

P3 baseline 为 `+0.249996` trust points；全部 profiles 中保持正向，完整范围约：

`+0.158504` 至 `+0.380851`。

OAT 中 `event_adjustment` 的影响最明显：

- low：≈ +0.158504；
- baseline：≈ +0.249996；
- high：≈ +0.380851。

其次为 `empathy_repair_weight` 和 `quiet_adjustment`。

这一结果符合机制结构：P3 测量 T6–T9 的早期 Immediate−Delayed Trust 差异，因此事件发生时 Trust 向目标状态调整的速度理应直接影响该 contrast。Stage B 必须检查这一强局部效应在多参数共同变化时是否仍然成立。

## 6. P4：直接触达对 Trust 参数严格不敏感

P4 在全部 18 个 profiles 中均严格为：

`0.450000`。

这与模型分层设计一致：P4 只由 targeting、network topology 与 enterprise delivery window 决定，不包含 Trust persuasion。该结果同时构成代码实现层面的 construct-separation evidence。

## 7. P5：重复品牌选择保持正向且幅度变化较小

P5 baseline 为 `+0.017007`，全部 profiles 范围约：

`+0.015906` 至 `+0.018360`。

影响最大的参数仍为：

1. `repair_retention`；
2. `empathy_repair_weight`；
3. `event_adjustment`。

但绝对变化仅约 0.001–0.002 的 expected choice share 量级。这支持当前 demand layer 没有把 Trust 参数的小幅变化机械放大成巨大的重复购买差异。

## 8. S1：conversion-support effect 基本独立于 Trust 参数

S1 baseline 为 `+0.028358`，全部 profiles 范围约：

`+0.028289` 至 `+0.028500`。

绝对变化非常小。该结果支持 conversion support 主要作为 PBC / demand-side facilitation channel，而不是 Trust-parameter-dependent communication effect。

## 9. Structured boundary profiles

| Profile | P1 | P2 | P3 | P4 | P5 | S1 |
|---|---:|---:|---:|---:|---:|---:|
| retention symmetric .97/.97 | +0.275084 | −0.086124 | +0.256807 | 0.450000 | +0.017609 | +0.028444 |
| retention reversed .96/.98 | +0.303092 | −0.093977 | +0.263576 | 0.450000 | +0.018360 | +0.028414 |
| legacy v3.2 transition boundary | +0.263909 | −0.081397 | +0.358440 | 0.450000 | +0.017269 | +0.028289 |

三种结构边界均未改变主要 estimand 的符号方向。这说明当前描述性方向并非仅依赖“crisis memory 必须比 repair memory 更持久”这一单一假设。不过 legacy transition 对 P3 的提升较明显，说明 timing contrast 对 Trust adjustment architecture 本身仍具有结构敏感性。

## 10. Stage A 可以支持与不能支持的结论

### 可以支持

- 参数注入路径通过实现不变量验证；
- 在预先规定的 local/boundary envelope 内，P1/P2/P3/P4/P5/S1 均未发生方向翻转；
- P1/P5 对 repair retention、empathy repair weight 和 event adjustment 更敏感；
- P2 对 empathy repair weight 尤其敏感；
- P3 对 event adjustment 尤其敏感；
- P4 与 Trust 参数分离；
- conversion support 对 Trust 参数变化相对稳定。

### 不能支持

- Stage A 已经证明全局参数稳健性；
- OAT sensitivity 可以识别参数交互；
- Low/High 是真实消费者参数的经验置信区间；
- Fake LLM 下 P2 为负意味着现实中 Empathy 必然优于 Rational；
- 可以根据结果把 baseline 改成效果更强的参数组合。

## 11. 下一步

Stage A 已达到预先设定的筛查目的。下一步进入 **Stage B Morris elementary-effects global screening**，在同一参数范围内随机化多条 elementary-effect trajectories，计算每个参数对 P1/P2/P3/P5 的 `mu*`、`mu` 与 `sigma`：

- `mu*`：总体影响强度；
- `mu`：平均有方向 elementary effect；
- `sigma`：非线性和/或参数交互的迹象。

Stage B 继续使用 Fake LLM 与固定网络/seed，不用于 calibration，也不允许修改冻结 baseline。
