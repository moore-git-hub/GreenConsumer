# v3.3.1 Pilot执行条件冻结记录

## 1. 当前状态

```text
N_MAX_FROZEN_10
PROVIDER_CALL_CEILING_FROZEN_1200
TIME_BUDGET_FROZEN_2_HOURS
COST_TOLERANCE_ACCEPTED_CNY_20_ADMINISTRATIVE
LLM_MODEL_FROZEN_QWEN_PLUS_2025_12_01
EXECUTION_SHA_NOT_FROZEN
PILOT_AUTHORIZED_CONDITIONAL_ON_WINDOWS_TESTED_CLEAN_SHA
PILOT_NOT_EXECUTED
FORMAL_NOT_AUTHORIZED
```

本文件记录Pilot执行前的用户选择。用户于2026-08-16接受1200次调用、2小时、
CNY 20行政费用容忍度和固定模型方案A，并同意在新代码通过Windows全量测试且
clean SHA被记录后开始P001–P006。这是有前置条件的Pilot授权，不是当前即可执行的
授权，也不是正式实验授权；旧SHA上的测试通过不能替代模型固定提交的回归测试。

## 2. 已冻结条件

| 条件 | 冻结值 | 决策日期 | 解释 |
|---|---:|---|---|
| 正式replication-block上限 `N_max` | 10 | 2026-08-15 | 用户在查看v3.3.1 Pilot结果前选择；属于计算与费用约束 |
| Pilot provider-call ceiling | 1200 | 2026-08-16 | 每次底层语义调用前硬检查；到限即停止且不替换seed |
| Pilot wall-clock ceiling | 2.0小时 | 2026-08-16 | 当前block受剩余suite时间约束；到时失败停止 |
| 可接受费用 | CNY 20 | 2026-08-16 | 行政容忍度，非程序化token费用停止器 |
| v3.3.1 Real-LLM模型 | `qwen-plus-2025-12-01` | 2026-08-16 | Pilot结果前固定具体版本；v3.2路径保持`qwen-plus` |
| Pilot seed grid | P001–P006 | 原协议 | 3×2完整cognitive blocks；禁止replacement |

`N_max=10`不是“Pilot样本量”。Pilot仍为预登记的P001–P006六个完整cognitive blocks，并对每个历史离线交叉D1–D3三个demand seeds。

`N_max=10`也不是已经由方差证据证明的正式N。由于协议要求正式N满足`N≥10`，该上限把Pilot后的可行候选限制为唯一值10：

- 若P1、P2、P5在保守planning SD和冻结MDE下的边际检出概率均达到.80，则协议1.1可冻结正式N=10；
- 若任一确认性estimand不达标，状态必须记为`DESIGN_NOT_FEASIBLE_WITHIN_CAP`；
- 不得根据Pilot均值扩大N、降低MDE、删除estimand、改变Holm family或把Pilot blocks并入正式样本。

## 3. 剩余执行门禁

| 条件 | 当前状态 | 执行前必须记录的值 |
|---|---|---|
| clean execution SHA | 未冻结 | 远端commit、分支和clean证明 |
| 新模型固定提交的Windows测试 | 未完成 | 完整pytest输出和准确HEAD |
| real preflight/API可用性 | 待执行前确认 | 不产生科学block的配置检查 |
| 条件式Pilot授权 | 已记录但尚未生效 | 以上门禁全部通过后才允许从P001开始 |

任一条件缺失时，真实Pilot入口必须fail closed。

重新准入依据见`PILOT_REENTRY_FREEZE_PROPOSAL_V331.md`，用户接受记录见
`PILOT_EXECUTION_AUTHORIZATION_V331.md`。模型、调用、时间和行政费用边界已经冻结；
当前唯一关键缺口是新的候选执行SHA尚未通过用户Windows环境的完整回归。

## 4. 后续记录顺序

按以下顺序恢复：

1. 发布包含具体模型固定和审计测试的新候选commit；
2. 用户在Windows `Kernel`环境对该准确HEAD运行完整pytest和零API plan-only；
3. 测试通过后记录远端clean execution SHA，使条件式Pilot授权生效；
4. 在同一clean SHA上通过real preflight后，从P001开始执行P001–P006；
5. Pilot完成后按协议OC规则判断N=10是否可行，不进行结果导向调参；
6. 正式实验仍需协议1.1、独立正式seed ledger及新的明确授权。
