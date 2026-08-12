# TASK_005 FMCG v3.2 clean workflow

本文件定义当前面向研究者与 PyCharm 的唯一工作流。冻结的科学机制文件保留原路径，以维持正式实验可复现性；新的 `greenconsumer_v32/` 只负责把全过程整理成清晰入口。

## 1. 唯一入口

```powershell
python run_v32.py <command>
```

等价：

```powershell
python -m greenconsumer_v32 <command>
```

## 2. 全过程

```text
preflight
   ↓
verify (6 groups of v3.2 tests)
   ↓
run / pipeline
   ├─ ExperimentConfig
   ├─ v3.2 scenario/personas/stimuli
   ├─ fake or real LLM router
   ├─ semantic audit
   ├─ common-history recording/replay when condition=all
   ├─ AgentKernel cognitive simulation
   ├─ Trust / Att / peer-only SN / PBC
   ├─ social network diffusion
   └─ offline FMCG demand cross
   ↓
analyze
   ↓
plot
   ↓
results/v32_runs/<run_id>
```

## 3. 零调用预检

```powershell
python run_v32.py preflight
```

真实 LLM 就绪检查：

```powershell
python run_v32.py preflight --real
```

两者都不会调用外部 API。真实模式只验证 qwen-plus 配置与 `DASHSCOPE_API_KEY` 是否可用；Windows 下会尝试从 user-scope 环境变量桥接到当前进程，但不会打印 key。

## 4. 核心测试

```powershell
python run_v32.py verify
```

按顺序运行：

- `tests/test_task005_fmcg_scenario_v32.py`
- `tests/test_task005_purchase_mechanism_v3.py`
- `tests/test_task005_purchase_mechanism_v31.py`
- `tests/test_task005_purchase_mechanism_v32.py`
- `tests/test_task005_fmcg_runtime_v32.py`
- `tests/test_task005_fmcg_audited_router_v32.py`

该命令不调用真实 LLM。

## 5. 推荐的第一次完整运行：fake LLM

```powershell
python run_v32.py pipeline --llm fake --condition all
```

一步执行：preflight → 9条件认知仿真 → offline demand → 描述分析 → v3.2画图。

如果只想运行、不自动分析画图：

```powershell
python run_v32.py run --llm fake --condition all
```

## 6. 新的真实 LLM 入口

先运行：

```powershell
python run_v32.py preflight --real
```

全过程真实 LLM engineering/demo：

```powershell
python run_v32.py pipeline --llm real --condition all --allow-real-llm
```

只执行仿真：

```powershell
python run_v32.py run --llm real --condition all --allow-real-llm
```

显式 `--allow-real-llm` 用于防止 PyCharm 误点导致真实 API 调用。

如果只想低成本演示一个条件：

```powershell
python run_v32.py pipeline --llm real --condition NoClarification-Control --allow-real-llm
```

单独运行一个 strategy condition 也允许，但由于同一次调用中没有 control，因此不具有 `condition=all` 的 within-run common-history replay。

## 7. 分析与可视化

已有 run 可单独分析：

```powershell
python run_v32.py analyze results\v32_runs\<run_id>
```

已有 run 可单独画图：

```powershell
python run_v32.py plot results\v32_runs\<run_id>
```

新的图只面向 v3.2 数据，不再调用旧 `analysis/plot.py` 中的 Oatly/Blackstone 历史场景标签。

## 8. 正式实验归档

```powershell
python run_v32.py formal-status
```

该命令只读取 `reproducibility/formal_v32_n10/` 中已经完成的 F001-F010 证据，不启动任何新的正式 replication。

## 9. 代码职责

`greenconsumer_v32/config.py`：新工作流参数和condition顺序。  
`preflight.py`：依赖、模型配置、真实LLM key就绪检查。  
`verification.py`：六组v3.2核心测试。  
`routers.py`：fake/real router、common-history recording/replay、审计包装。  
`runner.py`：全过程认知仿真调度。  
`demand.py`：认知轨迹之后的FMCG购买机会与重复品牌选择。  
`analysis.py`：engineering/demo描述性分析。  
`visualization.py`：v3.2专用Trust和repeat-choice图。  
`formal.py`：只读正式实验归档状态。  
`cli.py`：统一命令行。  
`run_v32.py`：PyCharm最直观的唯一入口。

## 10. 科研边界

新 package 是 orchestration layer，不修改正式实验绑定的核心机制。它继续调用 `experiment_config.py`、`fmcg_scenario_v32.py`、`task005_fmcg_runtime_v32.py`、`mechanism_v2.py`、`mechanism_v31_cognition.py`、`mechanism_v32_semantics.py`、`purchase_mechanism_v31.py`、`purchase_mechanism_v32.py` 以及 v3.2 plugins。

新的真实 LLM run 属于 engineering/demo，不得追加到已经关闭的 F001-F010 formal sample。
