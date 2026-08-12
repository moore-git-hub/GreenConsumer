# TASK_005 v3.2 精简代码库说明

## 删除原则

本分支只保留三类内容：

1. **当前可运行 scientific core**；
2. **统一 engineering/demo workflow**；
3. **已完成 formal N=10 的 reproducibility archive**。

历史开发 runner、pilot/variance runner、旧 formal-v1/v2 launcher、旧 Oatly 分析图、Task001–Task004 大型测试与生成日志不再保留在本分支。Git 历史仍完整保存这些材料，因此删除不会抹除研究开发 provenance。

## 入口与依赖

唯一人工入口：`run_v32.py`。

`greenconsumer_v32/routers.py` 已直接负责 qwen-plus router 构造与资源释放，不再依赖历史 `run_experiments.py`。

`simulation_core.py` 仍保留少量历史命名兼容依赖（`generate_data.py`, `metrics_calculator.py`, `GreenCognitionPlugin.py`, `ConsumerPlanPlugin.py`）。它们暂时保留，因为改写冻结 simulation engine 不属于“代码整理”的必要条件。

### AgentKernel Builder 的最小 bootstrap 配置

`simulation_core.py` 只借用 AgentKernel `Builder` 来生成经过 Pydantic 验证的 AgentConfig。运行时会临时写入 `data/agents/profiles.jsonl`，随后恢复或删除。

当前 v3.2 **不再依赖**：

- `data/relation/relation.jsonl`
- `data/map/agents.jsonl`
- `EasyRelationPlugin`
- `EasySpacePlugin`

社会网络由 `simulation_core.py` 显式创建 `Environment`，再通过 `SocialNetworkPlugin.register_agents(...)` 在内存中构建。因此：

- `configs/simulation_config.yaml` 的 `data` 只保留 `agent_profiles`；
- `configs/environment_config.yaml` 保留合法的空 `components: {}`，仅用于 Builder/Pydantic 配置解析。

`python run_v32.py preflight` 会静态检查这两项，防止未来删除文件后 YAML 仍残留旧路径。

## 不应直接运行的 scientific core

以下模块是被统一 workflow 调用的机制实现，不是人工入口：

- `simulation_core.py`
- `task005_fmcg_runtime_v32.py`
- `mechanism_v2.py`
- `mechanism_v31_cognition.py`
- `mechanism_v32_semantics.py`
- `purchase_mechanism_v3.py`
- `purchase_mechanism_v31.py`
- `purchase_mechanism_v32.py`
- `plugins/.../Green*`
- `plugins/.../*V32*`

## 当前验证最小集

`python run_v32.py verify` 只运行六组当前 v3.2 regression tests。

清理分支创建后必须先在用户 Windows/AgentKernel 环境中运行：

```powershell
python run_v32.py preflight
python run_v32.py verify
python run_v32.py pipeline --llm fake --condition all
```

三步全部通过后，才运行新的 real-LLM engineering/demo。
