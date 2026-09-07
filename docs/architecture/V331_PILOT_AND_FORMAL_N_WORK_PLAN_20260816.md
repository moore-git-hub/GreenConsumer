# v3.3.1 Pilot与正式N工作计划（取消N_max后）

> 当前调度状态（2026-08-16）：`DEFERRED_FOR_MIDTERM_DEFENSE`。用户因约两周后进行
> 中期答辩，决定暂缓真实Pilot和正式N计算。下述科学设计、执行合同、种子身份和
> 门禁完整保留；这不是取消、失败或样本量结论。恢复执行必须重新经过Windows准确
> SHA回归、零API plan-only、费用容忍度确认和用户明确授权。

## 1. 决策基线

本计划在任何有效v3.3.1 Pilot observation产生前冻结。`N_max=10`已取消；Pilot规模由方差估计精度决定，正式N由预注册operating-characteristic规则决定，资源预算只在科学N计算后判断是否可执行。

## 2. 工作计划表

| 阶段 | 任务 | 科学/工程门禁 | 交付物 | 当前状态 |
|---:|---|---|---|---|
| A1 | 冻结Pilot精度准则 | 单侧90% SD UCL膨胀≤25%；不使用效应均值 | 协议1.0.4、DR-34 | 已完成 |
| A2 | 冻结24-block认知网格 | 6 simulation/network×4 requested LLM；P001–P006身份保留 | contract1.1 seed table | 已完成 |
| A3 | 冻结demand replay | D1–D24；明确576值不是独立blocks | contract1.1 demand table | 已完成 |
| A4 | 实现planning SD | max(90% SD UCL, max LOO SD, component-synthesis SD) | `pilot_planning_sd.csv`代码合同 | 已完成 |
| A5 | 实现动态正式N | N≥10；P1/P2/P5 single-MDE Holm power≥.90；四相关场景须在同一N共同通过 | OC与`pilot_formal_n_selection.csv` | 已完成 |
| A6 | 实现长任务保护 | 4800 calls、8小时累计cap；受控中断同seed恢复；失败不可替换 | CLI、attempt ledger、tests | 已完成 |
| A7 | 发布候选代码 | 只允许目标分支；本地零API验证通过 | 远端candidate SHA | 已完成（远端候选`b73bf831...`；恢复前仍须核对届时实际HEAD） |
| G1 | Windows准入 | 准确SHA完整pytest通过；plan-only核对24/576/4800/8 | 用户测试记录、clean SHA | 暂缓至中期答辩后 |
| G2 | 费用确认 | 用户确认24-block行政费用容忍度；不能用调用数伪称精确费用 | 授权记录修订 | 暂缓至中期答辩后 |
| B1 | 执行Pilot | P001–P024全部valid；不换seed；中断按合同恢复 | seed/attempt/validity/estimand ledgers | 暂缓至中期答辩后 |
| B2 | 离线方差分析 | 24个独立blocks；Pilot mean/sign不进入设计 | components、planning SD、manifest | 暂缓至中期答辩后 |
| B3 | 离线OC与N_required | ≥200,000 replications/场景；FWER数值门禁；四场景全通过 | OC curve、selection、summary | 暂缓至中期答辩后 |
| G3 | 资源可行性审查 | 先接受科学`N_required`，再估算calls/time/cost | `FEASIBLE`或`SCIENTIFIC_N_NOT_RESOURCE_FEASIBLE` | 未开始 |
| C1 | 正式协议1.1 | 唯一N、formal IDs/seeds、源码/分析SHA、停止规则 | protocol1.1、formal seed ledger | 未开始 |
| G4 | 正式执行授权 | 用户针对协议1.1明确授权 | authorization record | 未开始 |
| C2 | 正式独立blocks | Pilot blocks不得并入；不得optional stopping | formal outputs与manifest | 未开始 |
| D1 | 论文第五、六章填值 | block级推断；P3/P4仅探索；禁止外推 | 正式表图、结果与讨论 | 未开始 |

## 3. 判定规则

Pilot必须同时有24个PASS attempts和24个PASS validity rows；P5须有576个replay值并覆盖D1–D24。任一planning variance为零或非有限值时停止并记`VARIANCE_ZERO_UNRESOLVED`。

`N_required`是四个相关结构场景在同一候选N上同时通过的最小值；另行报告各场景首个通过N。若资源无法承担，正确结论是`SCIENTIFIC_N_NOT_RESOURCE_FEASIBLE`；禁止回退N=10、把Pilot并入正式样本、降低0.90功效、调整MDE、删除P1/P2/P5或扩大alpha。

## 4. 当前准确状态

```text
CODE/DOC IMPLEMENTATION: COMPLETE LOCALLY
REAL LLM CALLS IN THIS REDESIGN: 0
VALID V3.3.1 PILOT BLOCKS: 0
FORMAL BLOCKS: 0
FORMAL INFERENCE: 0
CURRENT PRIORITY: MIDTERM REPORT -> DEFENSE PPT -> SCRIPT -> CONSISTENCY AUDIT
POST-DEFENSE GATE: VERIFY CURRENT CANDIDATE SHA -> WINDOWS TEST -> COST RECONFIRMATION
```
