# TASK_005 v3.3.1 Runtime Horizon Guard 修复记录

**日期：2026-08-13**  
**性质：实现一致性修复，不改变科学机制**

## 1. 触发错误

在运行：

```powershell
python run_v33_horizon_sensitivity.py
```

时，T35/T40 horizon 进入 `task005_fmcg_runtime_v33.py` 后被旧的 v3.3.1 runtime guard 拒绝：

```text
ValueError: scenario-v3.3.1 requires crisis Tick 5 and a 30-Tick horizon
```

根因是 runtime 中仍保留旧条件：

```python
if int(config.scandal_tick) != 5 or int(config.total_ticks) != 30:
```

该条件与已经冻结的新实验设计 `T30/T35/T40` 不一致。

## 2. 修复

runtime 现在从 `greenconsumer_v33.config` 读取：

```python
DEFAULT_CRISIS_TICK = 5
HORIZON_ROBUSTNESS_TICKS = (30, 35, 40)
```

并分别验证：

```python
config.scandal_tick == DEFAULT_CRISIS_TICK
config.total_ticks in HORIZON_ROBUSTNESS_TICKS
```

因此：

- T30：允许，用于短 horizon robustness；
- T35：允许，为 baseline primary horizon；
- T40：允许，用于长 horizon robustness；
- 其他 horizon：拒绝，避免在正式冻结后任意试探终点。

runtime 输出中新增：

- `runtime_total_ticks`；
- `runtime_horizon_grid`。

## 3. 科学解释

该修复只移除一个与新 experiment design 冲突的旧软件保护条件，不修改：

- Trust transition；
- semantic appraisal；
- social network；
- clarification diffusion；
- demand mechanism；
- treatment matrix；
- random seeds；
- Real-LLM temperature。

因此不能把此次修复描述为模型调参，也不能把修复后的结果与修复前 T30 formal results 混为同一正式样本。

## 4. 回归测试

新增：

`tests/test_task005_v331_runtime_horizon_guard.py`

零 API 回归检查：

1. T31 被拒绝；
2. T35 可通过 runtime guard 并进入 simulation core；
3. T40 可通过 runtime guard；
4. runtime provenance 正确记录 30/35/40 grid。

该测试专门防止未来又误恢复 `total_ticks == 30` 的旧硬编码。

## 5. 对前一轮审计的修正

此前 `V331_H35_IMPLEMENTATION_AUDIT.md` 已识别 Demand、Analysis、Visualization、Thesis Outputs 的 T30 遗留，但遗漏了 runtime 顶层 guard。此次实际运行暴露了这一遗漏。

因此当前工作原则修正为：除了静态检查 `range(1,31)`、T30 filter 等数据路径，还必须实际执行至少一次目标 horizon 的 end-to-end Fake smoke，才能把“horizon implementation audit”标记为完成。

在 T30/T35/T40 Fake horizon suite 全部完成、prefix invariance 通过之前，T35 implementation 状态应保持为 **implementation candidate / not yet fully verified**。
