# 第二阶段：Reflect 临时状态残留缺陷诊断与修复说明

## 1. 结论

当前正式实验结果存在一个会改变信任轨迹与行为输出的跨 Tick 状态残留缺陷：消费者 Agent 在某一 Tick 接收企业澄清后，若后续 Tick 没有新观察，Reflect 层没有清空 `last_observations` 与 `latest_thought`。Plan 层因而可能在多日内持续把旧澄清识别为“当天仍收到澄清”，并持续把澄清日的即时反应作为当前心理状态输入行为决策。

该问题不是参数取值争议，而是临时状态的生命周期错误。旧实验图表需要降级为调试结果，修复后必须重新运行。

## 2. 程序链条

1. Perceive 层在每个 Tick 没有新消息时会清空 `observations`。
2. Reflect 层在 `observations` 为空时只把 `trust_change_affective` 设为 0，随后直接返回，没有同步清空 `last_observations` 和 `latest_thought`。
3. Plan 层通过 `last_observations` 判断当前 Tick 是否存在企业澄清；若判断为真，则将当天视为非平静日，并把 `quiet_ticks` 重置为 0。
4. 因此，澄清日之后没有新消息的直接目标 Agent 会继续携带旧澄清快照，导致 `quiet_ticks` 无法正常递增。
5. Plan 行为决策又读取 `latest_thought`，使旧澄清反应或旧丑闻反应持续进入后续行为 Prompt。

## 3. 原始数据诊断结果

对现有 8 个实际澄清处理条件进行诊断，每个条件有 3 个直接投放目标，共形成 24 个“目标 Agent × 策略条件”观察单元：

- 14/24 个目标单元在澄清后直至仿真结束，`quiet_ticks` 始终为 0；
- 澄清后 `quiet_ticks=0` 的最长连续区间中位数为 20 Tick；
- 最大连续区间为 24 Tick；
- 澄清日的 `reasoning` 在后续平静日被重复记录累计 346 次；
- Hub 目标为 `Consumer_000`、`Consumer_004`、`Consumer_001`；
- Random 目标为 `Consumer_000`、`Consumer_017`、`Consumer_002`。

这说明状态残留并非极少数异常，而是系统性影响了大部分直接投放目标。

## 4. 对实验结论的影响

### 4.1 澄清时机效应被污染

即时澄清组从 Tick 6 开始暴露于状态残留，延迟澄清组从 Tick 10 开始暴露。两组受到污染的剩余窗口长度不同，因此当前“即时—延迟”差异同时包含真实策略时机差异和状态残留持续时长差异。

### 4.2 渠道效应被污染

Hub 与 Random 选择不同目标节点。目标节点后续能否收到社交消息，决定旧 `last_observations` 是否会被新观察覆盖。因此，渠道差异不仅来自网络覆盖，还受到目标节点状态残留被覆盖概率的影响。

### 4.3 信任恢复指标被污染

Plan 层在 `has_clarification=True` 时不执行普通平静期恢复。状态残留使部分目标节点长期无法进入正常 `quiet_ticks` 递增过程，从而影响终点信任、恢复量、恢复期 AUC 和恢复速度。

### 4.4 行为输出被污染

无新观察日仍使用旧 `latest_thought`，会使购买与发帖决策持续受到此前即时情绪的影响。即使该 Tick 的情绪增量已归零，行为 Prompt 仍不是真正的“日常平静状态”。

## 5. 修复原则

修复只处理临时状态生命周期，不在同一补丁中改变下列理论机制：

- 不移除 Reflect Prompt 中的精确信任分；
- 不改变情绪冲击区间 `[-2.0, +1.5]`；
- 不改变敏感度系数；
- 不改变 shock anchor 提升比例；
- 不改变自然恢复公式；
- 不改变网络结构与投放策略。

无新观察时应执行：

```python
trust_change_affective = 0.0
raw_affective_output = 0.0
affective_was_clipped = False
latest_thought = None
last_observations = []
reflect_primary_source = "None"
reflect_message_sources = []
```

## 6. 修复后的最小验收实验

不应立即运行全部策略，应先运行：

1. 一个无澄清对照组；
2. 一个即时澄清组；
3. 一个延迟澄清组。

验收标准：

- 直接目标在澄清 Tick 的 `quiet_ticks=0`；
- 下一 Tick 无新消息时 `quiet_ticks=1`；
- 之后无新消息时依次递增；
- 无新消息时 `last_observations=[]`；
- 无新消息时 `latest_thought=None`；
- 澄清不会在后续 Tick 被重复识别；
- 无解析错误时，LLM 原始输出、边界处理后输出和类型缩放后输出能够分别追踪。

## 7. 后续顺序

状态残留修复通过后，再依次进行：

1. 修正 Agent 级 `has_clarification` 标记，区分目标、实际接收与间接暴露；
2. 增加 anchor before/lift/after 和消息来源日志；
3. 增加网络边表、节点指标、目标节点表和运行元数据；
4. 冻结指标定义；
5. 决定自然适应、条件修复或双通道恢复的理论版本；
6. 开展多随机种子和替代网络的正式实验。
