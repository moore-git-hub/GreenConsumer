# TASK_005 v3.3.1 时间范围与模型规模设计说明

**状态：pre-formal design freeze / 2026-08-13**  
**适用范围：TASK_005 FMCG GABM v3.3.1**  
**性质：实验设计文档，不改变 Trust、Demand、网络传播或 LLM 语义机制**

## 1. 设计决策摘要

本阶段将 v3.3.1 的主分析时间范围预先规定为 **35 Tick**，并将一个 Tick 解释为一个仿真日。共同危机在 `T5` 发生，因此 `T35` 对应危机发生后的 30 日观察窗口。`T30` 与 `T40` 不作为可以事后择优的替代终点，而被预先规定为时间范围稳健性检查。

当前基准规模保持：

- 20 个显式 GABM cognitive Agents；
- 每个 cognitive Agent 映射 25 个 downstream FMCG micro-buyers；
- BA 有向网络仍为当前 baseline topology；
- Real LLM temperature 仍为 0.3；
- Crisis = T5，Immediate clarification = T6，Delayed clarification = T10；
- 主时间终点 = T35；
- horizon robustness = T30 / T35 / T40。

该决定是在新的 v3.3.1 正式推断开始之前冻结。旧 v3.2 F001–F010 的源码身份、30-Tick历史设计与正式结果不作任何修改或重新解释。

## 2. 为什么主时间范围改为 35 Tick

### 2.1 研究对象是有限时域的危机修复过程，而不是稳态模拟

本研究关注绿色 FMCG 品牌信任危机发生后，企业澄清、社会网络传播、消费者认知更新与重复品牌选择在有限时间内的动态变化。研究问题本身并不要求模型达到长期稳态，因此不以“曲线完全走平”作为停止标准。

ODD protocol 强调，应根据模型目的清楚说明时间尺度、模型过程和模拟实验设计，并记录模型设计 rationale 与 fitness-for-purpose 评价方法。因而，本研究将时间终点作为预先规定的 simulation-experiment design，而不是根据某一次结果的图形形态不断延长运行期。

### 2.2 T35 提供清楚的管理时间解释

当前共同危机发生于 T5。若将一个 Tick 解释为一天，则：

`T35 - T5 = 30 days after crisis`。

因此 T35 可以在论文中直接表述为“危机发生后 30 日观察窗口”。这一选择的主要依据是研究设计可解释性，而不是声称已有文献证明绿色 FMCG 信任必然在 30 日内完成修复。

### 2.3 工程诊断显示 T30 仍处于恢复过程，但该信息只用于冻结前设计

v3.3/v3.3.1 的工程运行中，T30 时 Control 与 treatment trajectories 仍存在持续恢复趋势。该现象提示 30 Tick 可能把主要输出截在恢复过程中。由于这些运行明确属于 engineering/demo，而不是新的正式 replication，因此可以在正式设计冻结前据此改进观察窗口；一旦新的正式实验开始，不再允许依据结果继续修改时间终点。

### 2.4 预先规定 T30/T40 防止 endpoint tuning

将 `30 / 35 / 40` 同时写入设计的目的不是从三个终点中挑选效果最大的一个，而是：

- T35：primary baseline horizon；
- T30：较短观察窗口 robustness；
- T40：较长观察窗口 robustness。

正式结果解释时，T35 为主；T30/T40 只用于检查结论是否对观察窗口敏感。若主要结论在不同 horizon 下发生方向翻转或大幅变化，应报告为时间边界条件，而不能通过重新选择终点消除该现象。

## 3. Agent 数量与模型规模

### 3.1 为什么当前 Real-LLM baseline 保留 20 cognitive Agents

已有生成式 Agent / GABM 研究显示，小规模高成本生成式代理系统可以用于机制研究。例如 Ghaffarzadegan et al. (2024) 的 GABM 教程使用小规模 agents 研究社会规范扩散，并强调多情景与 prompt sensitivity；Park et al. (2023) 的 Generative Agents sandbox 使用 25 个 agents 展示记忆、反思、互动与涌现行为。

这些先例只能说明 20–25 个生成式 agents 在方法上并非异常规模，**不能证明 N=20 对本研究的社会网络结论具有外部代表性**。本研究的 20-Agent baseline 主要服务于高成本的 Real-LLM semantic appraisal 与逐 Agent 审计。

### 3.2 为什么 N=20 对网络一般化仍然偏小

本研究同时比较 Hub 与 Random targeting。20 节点网络中 K=3 seeds 已占 15% 节点，因此少数高 degree 节点可能显著影响 reach。故论文中只能把当前 BA(n=20)解释为一个受控的 heterogeneous-hub baseline，而不能把特定 reach 数值直接推广为真实社交平台效果。

后续网络稳健性阶段预先考虑：

- network size：N = 20 / 40 / 80；
- fixed-budget：不同 N 下保持 K=3；
- proportional-budget：保持 K/N = 0.15；
- topology：BA / WS / community network。

规模扩展优先使用 Fake/Replay/固定语义输入进行结构性敏感性检查；只有当网络规模显著改变 Trust 或 repeat-choice 机制结论时，再选择有限的 Real-LLM robustness blocks。

## 4. Downstream micro-buyers

基准仍保持每个 cognitive Agent 25 个 micro-buyers，即 20 × 25 = 500 个下游需求单元/condition。该层不代表统计独立样本，而是用于生成 category opportunity、brand choice 与 loyalty dynamics。

后续 demand-size sensitivity 预先考虑 `10 / 25 / 50 micro-buyers per cognitive Agent`。若 P5 与 conversion-support 结果在该范围内稳定，可支持行为结果不依赖某一个任意的 micro-buyer 数量。

## 5. 统计独立单位

Agent 数量与统计 replication 数必须严格区分。正式推断的独立单位仍应是 **replication block**，而不是 cognitive Agents 或 micro-buyers。增加网络节点或 micro-buyers不能替代独立 replication。

v3.3.1 新正式实验的 replication 数应在 pilot/variance estimation 后，根据 P1/P2/P5 的 block-level variance、目标 MDE 与置信区间精度预先确定，然后冻结，不采用 optional stopping。

## 6. 论文可直接采用的时间设计表述

> 本研究采用有限时域 GABM 对品牌绿色信任危机后的动态修复过程进行模拟。每一 Tick 表示一个仿真日，危机事件在 T5 发生，即时澄清在 T6 注入，延迟澄清在 T10 注入。为覆盖危机后的中期恢复过程并形成具有管理解释的观察窗口，主仿真终点预先设定为 T35，即危机发生后 30 日。为检验结论是否依赖终止时点，另以 T30 与 T40 作为预先设定的时间范围稳健性检查。上述时间范围在新的正式模拟开始前冻结，后续不依据效应大小、显著性或图形形态调整主终点。

## 7. 假设、证据与边界

| 项目 | 当前性质 | 可作何种表述 |
|---|---|---|
| 1 Tick = 1 day | 模型时间尺度定义 | 可作为仿真设计说明，不是经验估计 |
| T35 = crisis + 30 days | 由时间定义直接得到 | 可作为管理观察窗口 |
| 20 cognitive Agents | 计算/审计与机制研究基准 | 不代表真实总体样本量 |
| 25 micro-buyers/Agent | demand-layer engineering design | 需 sensitivity，不代表真实抽样 |
| T30/T35/T40 | pre-specified horizon grid | 用于 endpoint robustness |
| N=20/40/80 | planned network-size robustness | 尚未形成实证结果 |

## 8. 文献依据

1. Grimm, V., Railsback, S. F., Vincenot, C. E., et al. (2020). The ODD Protocol for Describing Agent-Based and Other Simulation Models: A Second Update to Improve Clarity, Replication, and Structural Realism. *Journal of Artificial Societies and Social Simulation*, 23(2), 7. DOI: 10.18564/jasss.4259.
2. Ghaffarzadegan, N., Majumdar, A., Williams, R., & Hosseinichimeh, N. (2024). Generative agent-based modeling: an introduction and tutorial. *System Dynamics Review*, 40, e1761. DOI: 10.1002/sdr.1761.
3. Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative Agents: Interactive Simulacra of Human Behavior. *UIST 2023*. DOI: 10.1145/3586183.3606763.
4. Adam, N. R. (1983). Achieving a Confidence Interval for Parameters Estimated by Simulation. *Management Science*, 29(7), 856–866. DOI: 10.1287/mnsc.29.7.856. 本文用于支持后续以目标精度规划 simulation observations/replications 的方法思想，不用于证明 35 Tick 是经验最优时长。

## 9. 代码映射

- `greenconsumer_v33/config.py`：35-Tick baseline 与 30/35/40 horizon grid；
- `greenconsumer_v33/cli.py`：`--total-ticks {30,35,40}`；
- `greenconsumer_v33/runner.py`：将 horizon 写入 ExperimentConfig，并在 `run_summary.json` 持久化完整 time-design provenance；
- `tests/test_task005_v331_time_design.py`：零 API 检查 baseline 与 pre-specified horizon grid。

## 10. 冻结规则

从新的正式 v3.3.1 replication 开始后：

1. 不因 T35 效果不显著而改 T30/T40 为主终点；
2. 不因图形未走平而继续延长 horizon；
3. 不因某一 horizon 产生更有利的策略排序而重新定义主分析；
4. horizon sensitivity 的差异本身作为模型边界条件报告；
5. 任何后续模型设计变化必须进入 `MODEL_DESIGN_DECISION_LOG.md`，记录科学理由、代码范围、预期影响、验证方式与版本身份。
