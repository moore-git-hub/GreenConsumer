# TASK_005 FMCG v3.2 正式实验 Closeout 与论文结果解释

## 1. 正式执行状态

正式批次 `task005-fmcg-v32-formal-n10` 已完成并关闭。冻结的 F001–F010 共 10 个 formal replication blocks 全部有效，计划 N=10 达成；没有 replacement、没有 optional stopping，也没有复用工程阶段 blocks。正式运行共发生 2051 次 provider requests，低于 3000 次总上限。依据冻结规则，不再追加 F011 或任何额外正式 block。

## 2. 确认性结果

确认性 family 仅包含 P1、P2、P5，采用 block-level 双侧 one-sample t-test 对 0 检验，并在这三个指标内使用 Holm FWER 0.05。

### P1：总体澄清对危机后信任的影响

平均效应为 **0.3540 trust points**，普通 95% CI 为 **[0.3078, 0.4002]**，Holm-adjusted p = **9.59e-08**。效应绝对值超过预先冻结的管理意义阈值 MDE=0.15。因此，P1 同时具有确认性统计证据与预设管理意义。

### P2：Rational 与 Empathy 内容框架差异

Rational−Empathy 的平均差异为 **0.0672 trust points**，95% CI 为 **[0.0209, 0.1136]**，Holm-adjusted p = **0.009518**。零差异被拒绝，但平均效应低于 MDE=0.15，因此属于“可统计区分但未达到预设管理意义阈值”的内容框架差异。F001 的该对比为负，其余多数 block 为正，因此不应表述为 Rational 在所有网络/随机实现中均优于 Empathy。

### P5：总体澄清对预期重复品牌选择的影响

平均效应为 **0.01995**，即约 **2.00 个百分点**的 expected repeat-choice probability；95% CI 为 **[0.01658, 0.02333]**，Holm-adjusted p = **6.05e-07**。虽然确认性统计证据明确，但平均效应低于预先冻结的 5 个百分点 MDE，因此行为转化效应属于稳定但管理量级有限的正向变化。

## 3. 探索性机制结果

P3、P4 在正式设计冻结前已明确归为 exploratory/mechanistic，不进入确认性 Holm family，也不计算确认性 p 值。

P3（Immediate−Delayed，T6–T9）的 block-level 平均差异为 **0.5694**，10 个 block 的范围为 **[0.3677, 0.7620]**。这一结果描述性地表明，即时澄清在延迟组尚未接受澄清的早期窗口具有一致的信任保护优势，但不得转写为预注册确认性显著性结论。

P4（Hub−Random clarification reach）的平均差异为 **0.365**，即平均约 **36.5 个百分点**的触达差异；范围为 **[-0.05, 0.70]**。该指标跨 block 波动较大，应解释为网络结构对“实际观察到企业澄清”的触达机制，而不能直接解释为 Hub 对信任或购买的心理说服效应。

## 4. 论文中的核心机制叙事

正式结果支持如下分层解释：企业澄清相对于同期自然恢复的 Control 能够产生较强且达到管理意义阈值的信任恢复效果；内容框架之间存在可统计区分但实践量级有限的差异；即时澄清在危机后的早期窗口表现出明显的机制性优势；Hub 布置通常提高澄清触达但具有较大的网络实现异质性；最终行为端的 expected repeat-choice 变化为稳定正向，但明显小于心理端的信任恢复效应。

## 5. 外推边界

本次正式统计推断量化的是冻结 GABM 内部的 stochastic replication uncertainty。10 个 formal blocks 是 10 个独立仿真实现，而不是 10 名真实消费者；p 值和置信区间不能直接解释为真实消费者总体抽样推断，也不能单独构成现实世界因果效应验证。现实有效性仍需要外部数据、实验、调查或其他经验材料进行交叉验证。

## 6. Closeout 决策

TASK_005 v3.2 正式主实验在 N=10 处关闭。不得因 P2/P5 未达到 MDE 或 P3/P4 的探索性结果而追加 F011、重跑正式 block、替换失败 block 或事后调参。本 closeout 阶段新增 real LLM calls = 0。
