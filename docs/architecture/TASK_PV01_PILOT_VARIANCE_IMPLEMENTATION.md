# TASK-PV01 Pilot variance 基础设施

## 1. 状态与范围

实现状态：`ZERO_API_INFRASTRUCTURE_COMPLETE; PILOT_NOT_EXECUTED; FORMAL_NOT_AUTHORIZED`

本工作包实现 v3.3.1 Pilot 的计划、执行门禁、seed/attempt ledger、方差分解、planning SD 和 Holm operating-characteristic 分析。它不生成 Pilot 结果，不授权 P001–P006，也不启动正式实验。

唯一科学协议是 `FORMAL_EXPERIMENT_PROTOCOL.md`。本文件只说明代码如何兑现协议，不改变 2×2×2+共同 Control、estimand、MDE 或 seed grid。

## 2. 零 API 边界

以下命令不构建 router、不加载 AgentKernel、不读取 API key，也不调用 provider：

```powershell
python run_v33_pilot_variance.py --plan-only

python run_v33_pilot_variance.py `
  --analyze-existing "results\v33_pilot_variance\<suite_id>" `
  --n-max <pre_frozen_cap>
```

`greenconsumer_v33.pilot_variance` 的普通导入路径只依赖离线 I/O、NumPy、pandas、SciPy 和已有 estimand 函数。`runner`、AgentKernel 与真实 router 只在显式 execution function 内延迟导入。

## 3. 真实执行门禁

真实 Pilot 入口必须同时提供：

```powershell
python run_v33_pilot_variance.py `
  --execute-real-pilot `
  --allow-real-llm `
  --n-max <user_approved_cap> `
  --provider-call-ceiling <user_approved_cap> `
  --expected-git-head <clean_frozen_sha>
```

即使命令完整，执行仍要求：

- 当前分支严格等于 `refactor/task005-v32-clean-codebase`；
- Git worktree clean；
- HEAD 严格等于显式传入的 frozen SHA；
- `N_max≥10`；
- provider-call ceiling 为正数；
- provider 调用在每次实际请求前原子计数，达到 ceiling 时 fail closed；
- 任一预登记 block 失败后停止，不生成 replacement seed。

用户已在查看Pilot结果前批准并冻结`N_max=10`，但provider-call ceiling、时间预算、frozen execution SHA和真实Pilot授权仍不存在，因此不得运行该入口。完整状态见`PILOT_EXECUTION_CONDITIONS.md`。

## 4. 方差与样本量规则

| Estimand | Pilot data | 分解 | planning variance |
|---|---|---|---|
| P1 | 3 simulation/network × 2 requested-LLM/provider | balanced two-way method of moments | raw six-block variance 的单侧80%小样本上界 |
| P2 | 同P1 | 同P1 | 同P1 |
| P5 | 3 simulation/network × 2 requested-LLM/provider × 3 offline demand | balanced three-way method of moments | `max(D1六block方差, 非负分量之和)`的单侧80%小样本上界 |

负的 method-of-moments 分量保留在 `raw_variance_component`，planning 时才截断为零。边界零明确标记，不能解释为随机来源不存在。3×2 两向设计只有每格一个观察，interaction 与未解析 provider/runtime 波动不可分离。

若任一 planning variance 为零，状态设为 `VARIANCE_ZERO_UNRESOLVED`，不注入噪声、不借用旧实验方差、不生成正式 N。

Operating-characteristic 模拟：

- 只使用预设 MDE、planning SD 和六 block 的 estimand 相关结构；
- 不使用 Pilot mean、sign 或策略排序；
- 三项均为双侧 one-sample t 检验并执行 Holm step-down；
- 在multivariate-normal planning model下，用相关正态样本均值与Wishart样本协方差联合生成三个相关t统计量；该分布假设只服务于样本量设计，不是Pilot效应结论；
- 每个候选 N、每场景至少 200,000 Monte Carlo replications；
- global-null 以 `.05 + 2×MCSE` 作为数值模拟兼容阈值；Holm 的强 FWER 控制是分析规则，Monte Carlo 值只是实现诊断；
- 在 `10..N_max` 中选择三项 single-MDE marginal detection probability 均≥.80的最小 N；无解则 `DESIGN_NOT_FEASIBLE_WITHIN_CAP`。

## 5. 输出与失败语义

成功 Pilot 至少包含协议列出的八项文件和 SHA-256 manifest，另生成 block validity ledger。失败 attempt 也保留 seed、attempt、已有部分输出、失败摘要和 manifest；不得静默删除。

`selected_formal_n` 只是协议1.1的输入，不是正式执行授权。正式实验仍须新协议、正式 seed ledger、源码/分析 SHA 和用户明确授权。

## 6. 验证

测试文件：`tests/test_task005_v331_pilot_variance.py`

覆盖：冻结 seed grid、plan-only 非执行状态、cap fail-closed、两向/三向方差分量、保守 planning SD、零方差停止、Holm step-down、OC 可复现性，以及零 API 顶层 import contract。
