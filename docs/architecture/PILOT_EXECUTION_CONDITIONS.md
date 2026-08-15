# v3.3.1 Pilot执行条件冻结记录

## 1. 当前状态

```text
N_MAX_FROZEN_10
PROVIDER_CALL_CEILING_NOT_FROZEN
TIME_BUDGET_NOT_FROZEN
EXECUTION_SHA_NOT_FROZEN
PILOT_NOT_AUTHORIZED
PILOT_DEFERRED_NOT_CANCELLED_2026_08_16
FORMAL_NOT_AUTHORIZED
```

本文件记录Pilot执行前的用户选择，不构成P001–P006执行授权。用户于2026-08-16
决定先完成论文基础章节；Pilot与正式独立replication blocks不取消。重新执行时仍需新的明确授权和当时的完整门禁。

## 2. 已冻结条件

| 条件 | 冻结值 | 决策日期 | 解释 |
|---|---:|---|---|
| 正式replication-block上限 `N_max` | 10 | 2026-08-15 | 用户在查看v3.3.1 Pilot结果前选择；属于计算与费用约束 |

`N_max=10`不是“Pilot样本量”。Pilot仍为预登记的P001–P006六个完整cognitive blocks，并对每个历史离线交叉D1–D3三个demand seeds。

`N_max=10`也不是已经由方差证据证明的正式N。由于协议要求正式N满足`N≥10`，该上限把Pilot后的可行候选限制为唯一值10：

- 若P1、P2、P5在保守planning SD和冻结MDE下的边际检出概率均达到.80，则协议1.1可冻结正式N=10；
- 若任一确认性estimand不达标，状态必须记为`DESIGN_NOT_FEASIBLE_WITHIN_CAP`；
- 不得根据Pilot均值扩大N、降低MDE、删除estimand、改变Holm family或把Pilot blocks并入正式样本。

## 3. 尚未冻结条件

| 条件 | 当前状态 | 执行前必须记录的值 |
|---|---|---|
| provider-call ceiling | 未冻结 | 正整数硬上限及估算依据 |
| 最大运行时间 | 未冻结 | 小时数及中断规则 |
| clean execution SHA | 未冻结 | 远端commit、分支和clean证明 |
| provider/model配置 | 协议已有基线，执行前仍需确认 | model、temperature、prompt profile和API可用性 |
| 真实Pilot授权 | 未授予 | 用户明确授权P001–P006及费用边界 |

任一条件缺失时，真实Pilot入口必须fail closed。

## 4. 后续记录顺序

当前不继续执行；论文基础章节稳定后，按以下顺序恢复：

1. 估算P001–P006在当时调用合同下的最大provider calls和时间；
2. 用户冻结provider-call ceiling和时间预算；
3. 完成最终preflight与Windows全量测试；
4. 记录当时的clean execution SHA；
5. 用户另行明确授权后才执行P001–P006；
6. Pilot完成后按协议OC规则判断N=10是否可行，不进行结果导向调参。
