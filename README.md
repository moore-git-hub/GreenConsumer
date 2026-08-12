# GreenConsumer — TASK_005 FMCG v3.2 GABM

本分支是论文模型的**精简可运行代码库**。历史 pilot、variance、旧 formal runner、旧 Oatly 可视化、Task001–Task004 开发代码已从本分支删除；它们仍可在 Git 历史和旧分支中追溯。

## 1. 唯一入口

```powershell
python run_v32.py <command>
```

等价：

```powershell
python -m greenconsumer_v32 <command>
```

常用命令：

```powershell
# 零 API 环境检查
python run_v32.py preflight

# 六组当前 v3.2 核心测试
python run_v32.py verify

# 推荐：完整 fake-LLM 流程
python run_v32.py pipeline --llm fake --condition all

# 真实 LLM 就绪检查（仍为 0 次 API 调用）
python run_v32.py preflight --real

# 真实 qwen-plus engineering/demo 全流程
python run_v32.py pipeline --llm real --condition all --allow-real-llm

# 查看已经关闭的正式 F001-F010
python run_v32.py formal-status
```

**真实 LLM 新运行属于 engineering/demo，不会、也不得加入已经关闭的 formal N=10。**

## 2. 代码结构

```text
GreenConsumer/
├── run_v32.py                    # 唯一人工入口
│
├── greenconsumer_v32/            # 工作流层
│   ├── cli.py                    # 命令行调度
│   ├── config.py                 # 运行参数/条件顺序
│   ├── preflight.py              # 依赖、模型、API key 零调用检查
│   ├── verification.py           # 六组当前 v3.2 测试
│   ├── routers.py                # fake/real LLM + audit + replay
│   ├── runner.py                 # 9 条件认知仿真总调度
│   ├── demand.py                 # FMCG opportunity/choice/loyalty
│   ├── analysis.py               # engineering/demo 描述分析
│   ├── visualization.py          # v3.2 专用画图
│   ├── formal.py                 # 已完成正式实验只读状态
│   └── io.py                     # CSV/JSON 工具
│
├── experiment_config.py          # 2×2×2 + common control
├── fmcg_scenario_v32.py          # VerdantCo Oat / personas / stimuli
├── task005_fmcg_runtime_v32.py   # v3.2 AgentKernel 隔离适配器
│
├── mechanism_v32_semantics.py    # LLM semantic schema
├── mechanism_v2.py               # Trust / Att / memory core
├── mechanism_v31_cognition.py    # peer-only SN
│
├── purchase_mechanism_v3.py      # extended-TPB 基础函数
├── purchase_mechanism_v31.py     # FMCG repeat-choice 核心
├── purchase_mechanism_v32.py     # v3.2 persona→demand 映射
│
├── simulation_core.py            # AgentKernel 仿真引擎/审计核心
├── node_selector.py              # Hub / Random
├── clarification_injector.py     # 企业澄清触达
├── task005_fmcg_audited_router_v32.py
├── task005_fmcg_fake_router_v32.py
│
├── plugins/                      # 仅保留当前运行所需 Green/V32 plugins
├── configs/models_config.yaml    # qwen-plus；key 只从环境变量读取
├── tests/                        # 仅保留六组当前 v3.2 核心测试
│
├── docs/                         # 架构、论文、复现文档
└── reproducibility/formal_v32_n10/
                                   # 已完成 F001-F010 的不可变证据归档
```

### 为什么仍保留 `generate_data.py`、`metrics_calculator.py` 和两个旧名 Plugin？

它们目前仍被冻结的 `simulation_core.py` 作为 **compatibility/bootstrap dependency** 导入。clean branch 暂不重写 `simulation_core.py` 的科学运行路径，以避免“为了目录美观”无意改变已经完成正式实验的模型逻辑。它们不是人工入口。

## 3. 全过程

```text
run_v32.py
  ↓
preflight
  ↓
verify
  ↓
ExperimentConfig + v3.2 scenario
  ↓
fake / real qwen-plus router
  ↓
GreenCognitionV32Plugin
  ↓
semantic appraisal
  ↓
Trust / Att / peer-only SN / PBC
  ↓
SocialNetworkPlugin + UGC diffusion
  ↓
30-Tick cognitive trajectories
  ↓
offline FMCG demand
  ↓
category opportunity → brand choice → loyalty
  ↓
descriptive analysis
  ↓
v3.2 plots
```

## 4. 真实 LLM

配置保存在 `configs/models_config.yaml`，当前模型为 `qwen-plus`、temperature 0.3。Git 中只保存：

```yaml
api_key: "__FROM_ENV_DASHSCOPE_API_KEY__"
```

真实 key 必须来自环境变量 `DASHSCOPE_API_KEY`，不会写回配置或输出文件。

LLM 的职责仅是：

```text
Persona + Memory + Actual Observations
                 ↓
       semantic appraisal
                 ↓
valence / arousal / credibility / evidence /
empathy / peer approval / hypocrisy / reasoning
```

LLM **不直接决定购买**。Trust/Att/SN/PBC 更新、社会传播和 FMCG 重复品牌选择由显式机制代码执行。

## 5. 输出

新运行只写入：

```text
results/v32_runs/<run_id>/
```

`results/` 已被 Git 忽略，不应提交。

## 6. 正式实验身份

- Formal scientific source HEAD: `ef6567adaafcafcf3b9f6884295f509a05ed727e`
- Formal batch: `task005-fmcg-v32-formal-n10`
- Valid blocks: F001–F010 = 10/10
- F011+: forbidden

正式结果归档在 `reproducibility/formal_v32_n10/`。本 clean branch 只是后续工程整理，不会改变原正式实验源码身份。
