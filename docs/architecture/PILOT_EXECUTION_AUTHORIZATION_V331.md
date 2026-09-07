# v3.3.1 Pilot授权与边界记录

## 1. 最新用户决定

| 字段 | 记录 |
|---|---|
| 决定日期 | 2026-08-16 |
| 用户决定 | 取消`N_max`限制，根据科学所需计算Pilot与正式N；随后因中期答辩将真实执行暂缓 |
| 已授权范围 | 修改、测试并发布24-block Pilot与动态正式N计算基础设施 |
| 未授权范围 | 真实LLM Pilot调用、正式实验、结果解释 |
| 当前状态 | `IMPLEMENTATION_COMPLETE; REAL_PILOT_DEFERRED_FOR_MIDTERM_DEFENSE` |
| Pilot observations | 0 |
| Formal blocks | 0 |

该决定在任何有效v3.3.1 Pilot observation产生前作出，不是观察结果后的样本量调整。此前“N=10上限、6-block Pilot、1200 calls、2小时、CNY 20”的授权边界由新科学设计取代；旧记录保留在合同1.0和Git历史中，不得继续作为当前执行依据。

2026-08-16新增调度决定：用户因约两周后进行中期答辩，将真实Pilot与正式N计算暂缓。
这不改变24-block Pilot、动态正式N、种子、estimand、MDE、功效或停止规则，也不构成
真实执行授权。中期答辩后须重新满足第3节全部条件，并由用户作出新的明确授权。

## 2. 当前接受的科学边界

- Pilot为P001–P024，共24个独立cognitive blocks；
- 每个block使用D1–D24进行离线demand replay，共576个P5条件性值；
- P1/P2/P5为确认性family，P3/P4为探索性；
- planning SD取单侧90% SD UCL、最大LOO SD和方差分量合成SD三者最大值；
- 正式N从10向上搜索，不设科研上限；
- 目标为每项single-MDE Holm detection probability≥.90；
- 使用四个预设相关结构场景，并取全部场景在同一N共同通过的最小值；
- Pilot和正式blocks相互独立，Pilot不得并入正式样本；
- 不因结果不理想追加、替换seed、降低MDE、降功效或删除确认性estimand。

## 3. 真实Pilot尚未获准的原因

真实Pilot仍需同时满足：

1. 新候选commit发布到`refactor/task005-v32-clean-codebase`；
2. 用户Windows `Kernel`环境在准确HEAD上完整pytest通过；
3. 零API plan-only核对24 blocks、576 demand realizations、4800 calls、8小时和具体模型；
4. Git工作树clean且HEAD与命令显式值一致；
5. 用户重新确认24-block计划的行政费用容忍度；
6. API key只由环境变量提供。

因此，“确定开始”授权的是本轮代码与协议实施，不是立即消费API。正式实验仍须Pilot完成、`N_required`计算、协议1.1、formal seed ledger和新的明确授权。
