# GreenConsumer 状态残留修复补丁 v1

## 修复对象

替换仓库中的：

`plugins/agent/reflect/GreenCognitionPlugin.py`

## 已定位的问题

当前 Reflect 层在 `observations` 为空时仅将 `trust_change_affective` 设为 0，未清空：

- `last_observations`
- `latest_thought`

Plan 层随后通过 `last_observations` 判断当天是否收到企业澄清。因此，一名 Agent 在澄清日之后若没有收到新消息，仍会在后续 Tick 持续被识别为 `has_clarification=True`，使 `quiet_ticks` 长期保持为 0。同时，行为决策 Prompt 会持续读取澄清日或丑闻日的旧 `latest_thought`。

这不是理论参数问题，而是跨 Tick 临时状态没有失效的程序错误。修复会改变既有实验轨迹，因此旧图表不能继续作为正式结果，必须重跑。

## 安装方式

1. 备份原文件。
2. 将本目录中的 `plugins/agent/reflect/GreenCognitionPlugin.py` 覆盖到仓库同路径。
3. 先运行语法检查：

```bash
python -m py_compile plugins/agent/reflect/GreenCognitionPlugin.py
```

4. 先运行 1 个无澄清组和 1 个即时澄清组进行小规模验证，不要立即重跑全部策略。

## 验收标准

对于直接接收澄清的 Agent：

- 澄清 Tick：`quiet_ticks == 0`；
- 下一 Tick 无新消息：`quiet_ticks == 1`；
- 后续无新消息：按 2、3、4……递增；
- `last_observations` 不再残留澄清消息；
- `latest_thought` 在无新观察日为 `None`，Plan 使用日常状态而非旧即时反应；
- 新增日志能够区分 LLM 原始输出与边界处理后的 Reflect 输出。

## 诊断旧数据

```bash
python diagnostics/diagnose_state_residue.py \
  --agent-records results/experiments/latest/agent_records.csv \
  --summary results/experiments/latest/summary.csv \
  --output-dir results/experiments/latest/diagnostics
```

## 本补丁暂不处理

- 是否移除 Reflect Prompt 中的精确信任分；
- 自然恢复、条件恢复或双通道恢复的理论选择；
- 12 个标签改为 8 个处理组加 1 个公共对照；
- 网络拓扑与 Hub/Random 匹配；
- 指标口径重构。

这些事项应在状态残留修复验证通过后分阶段处理，避免同时改变多个机制而无法归因。
