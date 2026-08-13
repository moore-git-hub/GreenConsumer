# TASK_005 v3.3.1 T35 实现审计记录

**日期：2026-08-13**  
**状态：code audit completed; local zero-API verification pending**  
**范围：时间范围实现与论文输出链，不改变科学机制参数**

## 1. 审计目的

在将主观察窗口从 T30 预先调整为 T35 后，对代码中所有可能仍隐含 `T30` 的运行、需求、分析、可视化与论文输出路径进行审查，避免出现“认知仿真运行至 T35，但下游需求或统计仍只处理到 T30”的不一致。

该审计属于 experiment-design implementation verification，不依据策略效应方向或显著性调整模型。

## 2. 审计中发现的问题

### 2.1 Downstream demand 仍固定循环至 T30

旧 `greenconsumer_v33/demand.py` 使用：

```python
for tick in range(1, 31):
```

因此即使 cognitive GABM 已运行至 T35/T40，FMCG category opportunity、repeat choice 与 loyalty 仍会在 T30 截止。这会造成不同模块时间范围不一致，并使 P5/S1 的 horizon robustness 失真。

**修复：** 从 `cognitive_records` 的完整 Tick 集合解析 realized horizon，要求 Tick 连续且每个 Persona-Tick 状态齐全，然后运行 `1..T_end`。Demand rows 与 curves 同时记录 `total_ticks` provenance。

**科学含义：** 只修复时间范围传递，不改变 renewal process、choice probability、loyalty 或 conversion-support 机制。

### 2.2 Analysis 仍使用固定 T6–T30

旧 v3.3.1 analysis 的 P1/P2/P5/S1 与 condition/demand summary 使用 T30 硬编码。

**修复：** `analysis.py` 从 `run_summary.json` 读取 `total_ticks`，并与 realized cognitive max Tick 交叉检查；P1/P2/P5/S1 使用 `T6–T_end`。P3 保持 T6–T9，P4 保持 configured enterprise-delivery window，因为两者的理论定义不依赖总运行时长。

### 2.3 Visualization 的 repeat-choice 图仍固定至 T30

旧 plotting loop 使用 `range(1, 31)`。

**修复：** 所有 v3.3.1 plots 使用 realized `end_tick`，图题和 manifest 显式记录时间范围。

### 2.4 Thesis outputs 仍有大量 T30-specific filters

为避免直接大幅修改已经通过早期工程审计的 legacy `thesis_outputs.py`，新增：

`greenconsumer_v33/thesis_outputs_finite_horizon.py`

新模块复用 horizon-neutral helper，并重新实现：

- endpoint-aware condition outcomes；
- segment / Agent heterogeneity；
- conversion support / demand segment summaries；
- T30/T35/T40 checkpoint table；
- V16 time-horizon provenance validation；
- dynamic endpoint figures。

`run_v33_thesis.py` 已改为调用该 finite-horizon postprocessor。

### 2.5 Network animation 文档仍称 30-Tick GIF

动画本身已经使用 records 中实际 Tick 集合，并不存在运行逻辑 T30 截断；仅 docstring 与说明滞后。

**修复：** 更新为“完整 realized Tick horizon 的固定拓扑状态/信息流动画”。

## 3. 新增防错机制

### 3.1 v3.3.1 独立实验配置

新增 `greenconsumer_v33/config.py`，避免修改冻结 v3.2 的历史默认值：

```text
DEFAULT_TOTAL_TICKS = 35
HORIZON_ROBUSTNESS_TICKS = (30, 35, 40)
```

CLI 只允许上述三个 horizon，防止正式结果产生后任意试探其他终点。

### 3.2 Provenance

新的 `run_summary.json` 将保存：

- total_ticks；
- Tick unit；
- crisis Tick；
- post-crisis observation days；
- baseline horizon；
- pre-specified horizon grid；
- horizon role。

### 3.3 Prefix invariance

新增 Fake-LLM horizon suite，要求：

- T30 与 T35 的 T1–T30 cognitive history 完全一致；
- T30 与 T40 的 T1–T30 完全一致；
- T35 与 T40 的 T1–T35 完全一致。

如果失败，按实现错误处理，不解释为科学“敏感性”。

### 3.4 Demand prefix invariance

新增零 API test，要求在相同 cognitive prefix 与 demand seed 下：

- 独立 T30 demand run；
- T35 demand run 的 T1–T30 prefix；

除 `total_ticks` provenance 字段外完全相同。

## 4. 新增/修改代码

- `greenconsumer_v33/config.py`
- `greenconsumer_v33/cli.py`
- `greenconsumer_v33/runner.py`
- `greenconsumer_v33/demand.py`
- `greenconsumer_v33/analysis.py`
- `greenconsumer_v33/visualization.py`
- `greenconsumer_v33/thesis_outputs_finite_horizon.py`
- `greenconsumer_v33/network_animation.py`
- `greenconsumer_v33/horizon_sensitivity.py`
- `run_v33_thesis.py`
- `run_v33_horizon_sensitivity.py`

新增测试：

- `test_task005_v331_time_design.py`
- `test_task005_v331_horizon_outputs.py`
- `test_task005_v331_horizon_sensitivity.py`
- `test_task005_v331_demand_horizon.py`

## 5. 未改变的科学机制

本次实现修正不改变：

- Trust crisis/repair transition parameters；
- Att / SN / PBC 机制；
- LLM prompt semantic schema；
- Real-LLM model 与 temperature=0.3；
- BA baseline 建图机制；
- Hub / Random treatment；
- paid edge probability / delivery lag baseline；
- renewal interval generation规则；
- brand-choice equation 与 bounded EWMA loyalty；
- 2×2×2 + common control 实验矩阵。

因此，这是“同一科学模型的时间范围实现一致性修复”，而不是根据结果重新调参。

## 6. 验收规则

在开始下一类 sensitivity 前必须依次通过：

1. Python compile；
2. 全部 v3.3/v3.3.1 zero-API tests；
3. Fake T30/T35/T40 horizon suite；
4. `prefix_invariance.csv` 无 FAIL；
5. T35 run 的 cognitive / demand / curve / analysis / thesis outputs 全部延伸至 T35；
6. 任何 horizon sign reversal 作为边界条件记录，不允许重新选择主终点。

## 7. 论文可用结论边界

通过上述检查后，可以声称：

> 模型在软件实现层面保持了不同有限观察窗口之间的历史前缀一致性，且认知、需求、分析和可视化模块采用同一实现时间范围。

不能由此声称：

- 35 日是现实消费者信任恢复的经验最优期限；
- horizon invariance 证明模型具有现实外部有效性；
- Fake-LLM robustness 等价于真实 LLM 结果稳健性。
