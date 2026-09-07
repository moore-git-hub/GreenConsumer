# TASK_005 FMCG v3.2 — Clean Workflow

## 1. 唯一入口

所有人工操作都从仓库根目录的 `run_v32.py` 开始：

```powershell
python run_v32.py preflight
python run_v32.py verify
python run_v32.py pipeline --llm fake --condition all
python run_v32.py preflight --real
python run_v32.py pipeline --llm real --condition all --allow-real-llm
python run_v32.py formal-status
```

其他 Python 文件是被入口调用的模块，不应当作为日常人工 runner。

## 2. 全过程调用链

```text
run_v32.py
  ↓
greenconsumer_v32.cli
  ├─ preflight.py
  ├─ verification.py
  └─ runner.py
       ↓
     experiment_config.py
       ↓
     fmcg_scenario_v32.py
       ↓
     routers.py
       ├─ deterministic fake
       └─ qwen-plus real + audit + replay
       ↓
     task005_fmcg_runtime_v32.py
       ↓
     simulation_core.py
       ↓
     AgentKernel plugins
       ├─ GreenPerceivePlugin
       ├─ GreenCognitionV32Plugin
       ├─ ConsumerPlanV32Plugin
       └─ SocialNetworkPlugin
       ↓
     mechanism_v2 + mechanism_v31_cognition
       ↓
     demand.py
       ↓
     purchase_mechanism_v31/v32
       ↓
     analysis.py
       ↓
     visualization.py
```

## 3. Real LLM 安全门

真实 LLM 只有在同时满足以下条件时才会启动：

1. `--llm real`
2. `--allow-real-llm`
3. `preflight --real` 能检测到 `DASHSCOPE_API_KEY`
4. `configs/models_config.yaml` 仍是 qwen-plus / temperature 0.3 / key placeholder

没有任何“real 失败后自动 fallback 到 fake”的行为；失败会显式停止。

## 4. LLM 的角色

LLM 只负责：

```text
Persona + Memory + Actual Observations
     → semantic appraisal
```

包括 valence、arousal、credibility、evidence、empathy、peer approval 等。

LLM 不直接：
- 修改 Trust/Att/SN/PBC；
- 决定购买；
- 创建购买机会；
- 改变网络；
- 进行正式统计推断。

## 5. common-history replay

运行全部 9 条件时，NoClarification-Control 首先记录 treatment 前 LLM 响应。每个策略条件在自己的 clarification tick 之前严格重放同一历史；cache miss 会 fail closed，不会偷偷重新调用 provider。

## 6. Formal archive

F001-F010 已完成并关闭。`formal-status` 只是读取 `reproducibility/formal_v32_n10/`，clean workflow 不含正式实验 launcher。
