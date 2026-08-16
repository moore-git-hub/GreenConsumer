# v3.3.1 Pilot执行条件冻结记录

## 1. 当前状态

```text
FORMAL_N_CAP_CANCELLED
PILOT_GRID_FROZEN_P001_P024
OFFLINE_DEMAND_GRID_FROZEN_D1_D24
PROVIDER_CALL_CEILING_IMPLEMENTED_4800
TIME_BUDGET_IMPLEMENTED_8_HOURS
COST_TOLERANCE_RECONFIRMATION_REQUIRED
LLM_MODEL_FROZEN_QWEN_PLUS_2025_12_01
EXECUTION_SHA_NOT_FROZEN
PILOT_NOT_EXECUTED
FORMAL_NOT_AUTHORIZED
```

用户于2026-08-16在任何有效v3.3.1 Pilot observation产生前取消`N_max=10`，接受先计算科学所需N、再评估资源可行性的原则，并同意实施24-block Pilot基础设施。旧合同1.0作为历史记录保留；当前机器可读合同为`task_pv01_pilot_variance_contract1.1.json`。

## 2. 科学冻结条件

| 条件 | 当前值 | 解释 |
|---|---:|---|
| Pilot cognitive blocks | 24 | 6个simulation/network seeds×4个requested LLM seeds；独立Pilot单位 |
| Pilot IDs | P001–P024 | P001–P006保留旧身份；P007–P024补全网格；禁止replacement seed |
| Offline demand seeds | D1–D24 | 每个cognitive block离线replay；576个P5值不是576个独立block |
| Planning SD | 三规则取最大 | 单侧90% SD UCL、最大leave-one-block-out SD、方差分量合成SD |
| Confirmatory family | P1、P2、P5 | P3、P4继续为secondary/exploratory |
| MDE | .15、.15、.05 | 预设设计阈值；管理意义依据仍待补充 |
| 功效目标 | 每项≥.90 | single-MDE场景；Holm FWER=.05 |
| 正式N | 动态计算 | 从N=10向上搜索；取四种冻结相关结构在同一N同时通过的最小值 |
| 科研上限 | 无 | 预算不能截断`N_required`的计算 |

Pilot n=24的直接依据是方差估计精度：单侧90%卡方SD上界因子约1.245，低于预设25%膨胀容忍界；n=6对应约1.762，不能支撑稳定的正式N规划。Pilot均值、方向、显著性和策略排序均不参与该选择。

## 3. 运行边界与待确认项

| 条件 | 实现值/状态 | 执行含义 |
|---|---|---|
| provider-call ceiling | 4800 | 按历史约148.6 calls/block×24并保留约34.6%余量；每次底层调用前检查 |
| wall-clock ceiling | 8小时 | 按历史6-block约2小时线性扩展；累计跨恢复会话计算 |
| 行政费用容忍度 | 未重新确认 | 原CNY 20只覆盖旧6-block计划，不得自动外推 |
| v3.3.1模型 | `qwen-plus-2025-12-01` | v3.2继续使用`qwen-plus` |
| clean execution SHA | 未冻结 | 必须是本修订发布后的远端commit |
| Windows完整pytest | 未完成 | 必须针对准确候选SHA通过 |
| Pilot真实执行 | 未授权 | 上述门禁闭合前不得运行 |
| 正式实验 | 未授权 | Pilot后协议1.1和独立formal seed ledger另行授权 |

4800次与8小时是防失控的operational ceilings，不是保证足够的成本预测，也不限制正式N。达到任一限额必须fail closed；不能增加seed或把不完整block计入Pilot。

## 4. 中断恢复边界

新入口支持`--resume-real-pilot <suite_dir>`。它只允许恢复经`finally`完整写入结束时间、但状态仍为`RUNNING`的受控中断block，并要求相同clean Git SHA、模型、全部seed和累计provider/time预算。每次底层provider调用前把累计计数写入attempt ledger。无法证明最终wall-clock checkpoint的强制杀进程、已标记`FAIL*`或validity失败的suite均不可恢复，也不得换seed。

## 5. 下一道门禁

1. 发布本修订的候选SHA；
2. 用户在Windows `Kernel`环境对该准确SHA运行完整pytest与零API plan-only；
3. 用户明确新的费用容忍度，确认4800次/8小时运行边界；
4. 记录clean execution SHA后，才允许从P001开始真实Pilot；
5. Pilot完成后离线计算`N_required`；若资源不足，登记`SCIENTIFIC_N_NOT_RESOURCE_FEASIBLE`，不得降低统计标准；
6. 正式执行仍须协议1.1、独立formal seeds和新的明确授权。
