# v3.3.1 Pilot条件式执行授权记录

## 1. 授权身份

| 字段 | 记录 |
|---|---|
| 用户决定日期 | 2026-08-16 |
| 用户原话 | “检查通过，接受建议，开始” |
| 解释范围 | 接受重新准入建议，并授权在全部前置门禁闭合后执行P001–P006 |
| 当前状态 | `AUTHORIZED_CONDITIONAL_ON_WINDOWS_TESTED_CLEAN_SHA` |
| Pilot执行状态 | `NOT_EXECUTED` |
| 正式实验状态 | `NOT_AUTHORIZED` |

该授权不能脱离`PILOT_REENTRY_FREEZE_PROPOSAL_V331.md`理解。它不授权在旧代码、脏
工作树、不同模型、不同seed或未通过Windows回归的提交上运行，也不授权正式实验。

## 2. 用户接受的边界

| 条件 | 冻结值 |
|---|---|
| `N_max` | 10（正式block预算上限，不是已证明的正式N） |
| Pilot cognitive blocks | P001–P006 |
| provider-call ceiling | 1200次底层语义调用 |
| wall-clock ceiling | 2.0小时 |
| 费用容忍度 | CNY 20，行政边界而非代码可强制的token上限 |
| v3.3.1模型 | `qwen-plus-2025-12-01` |
| temperature | 0.3 |
| prompt | `baseline_exact` |
| replacement seed | 禁止 |

共享`configs/models_config.yaml`继续保留`qwen-plus`，用于不改变已关闭v3.2路径；
v3.3.1 runner在内存中以版本作用域覆盖成上述具体模型。此前五个Real-LLM工程blocks
仍按历史事实记录为滚动别名`qwen-plus`，不追溯性改写其运行元数据。

## 3. 授权生效条件

必须同时满足：

1. 模型固定代码和审计测试已发布到远端分支；
2. 用户在Windows `Kernel`环境对该准确HEAD运行完整pytest并回传PASS；
3. 同一HEAD的零APIplan-only显示N=10、1200次、2小时和具体模型；
4. 远端commit、分支、clean worktree均已记录；
5. 执行前real preflight通过且API key仅由环境变量提供。

满足后从P001开始完整suite；任何block、调用或时间门禁失败均停止且不得替换seed。
Pilot只用于planning variance和OC，不属于正式样本。Pilot完成后若N=10不满足冻结规则，
状态必须为`DESIGN_NOT_FEASIBLE_WITHIN_CAP`，不得根据Pilot结果调MDE或扩大上限。

## 4. 零结果声明

本授权记录产生GABM run=0、provider call=0、有效Pilot observation=0、formal inference=0。
