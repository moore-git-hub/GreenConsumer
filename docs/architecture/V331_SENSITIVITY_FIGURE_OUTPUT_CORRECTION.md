# TASK_005 v3.3.1 敏感性图形标签修正记录

**日期：2026-08-13**  
**性质：post-processing / reporting correction；不修改模型、参数或结果数值**

## 1. 发现的问题

Stage-A Trust sensitivity 原始图实际绘制：

- `low_delta_from_baseline = Y_low - Y_baseline`；
- `high_delta_from_baseline = Y_high - Y_baseline`。

这些量具有正负方向，是 **signed deviations**。原绘图代码却将横轴写为：

`Absolute change in estimand relative to baseline profile`

因此原始 CSV 和点的位置是正确的，但横轴文字不准确。用户生成的 P1/P2/P3/P5 图也清楚显示横轴同时存在负值和正值，进一步确认该问题属于标签错误而非计算错误。

## 2. 修正原则

不重新运行任何 sensitivity experiment，不改变：

- Stage-A 18 profiles；
- baseline；
- estimand 数值；
- Morris design；
- Fake/Real LLM；
- seeds；
- Trust mechanism。

新增纯后处理：

- `greenconsumer_v33/sensitivity_figures.py`；
- `run_v33_sensitivity_figures.py`。

Stage-A 横轴修正为：

`Signed change relative to frozen baseline`

同时将过长的 raw estimand IDs 替换为论文更易读的人类可读标题。Morris 图也使用相同的可读标题，但 `mu*` 仍保持 mean absolute elementary effect 的正确含义。

## 3. 复现方式

Stage A：

```powershell
python run_v33_sensitivity_figures.py `
  "E:\...\results\v33_trust_sensitivity\trust_20260813_110718"
```

Stage B Morris：

```powershell
python run_v33_sensitivity_figures.py `
  "E:\...\results\v33_trust_morris\morris_20260813_113712"
```

程序只读取：

- Stage A：`trust_sensitivity_local_effects.csv`；或
- Stage B：`morris_statistics.csv`。

输出到 `figures_thesis/`，并写 `sensitivity_figure_manifest.json` 明确声明 `model_rerun_performed=false`。

## 4. 论文使用规则

论文和答辩优先使用 `figures_thesis/` 中修正后的图。原始图仍保留在 sensitivity suite 的 `figures/` 中作为工程运行审计历史，不删除、不覆盖。

该修正不能被描述为模型结果发生变化；其性质仅为图表标签和可读性修正。
