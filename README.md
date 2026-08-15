# GreenConsumer — TASK_005 FMCG GABM

本分支是论文模型的**精简可运行代码库**。当前研究代码分成两个严格区分的层次：

- **v3.2 frozen formal archive**：已经完成并关闭的 F001–F010 正式实验；科学源码身份保持不变；
- **v3.3.1 engineering freeze candidate**：在 v3.2 之后进行的机制改进、真实 LLM 验证、敏感性/稳健性与论文输出准备，不得冒充原 v3.2 formal 结果。

历史 pilot、variance、旧 Oatly 可视化、Task001–Task004 开发代码已从本分支主工作流删除；仍可从 Git 历史追溯。

## 1. 当前工程入口

当前正式实验准备文件：

- `docs/architecture/FORMAL_EXPERIMENT_PROTOCOL.md`：冻结2×2×2+共同Control、estimands、Pilot方差设计和执行门禁；
- `docs/PROJECT_PROGRESS.md`：可核验的已完成、部分完成和未完成工作台账。
- `docs/architecture/EXPERIMENT_EVIDENCE_REGISTER.md`：区分v3.2正式archive、v3.3.1工程结果、用户叙述总结与计划记录，防止论文引用时跨版本混用。
- `docs/architecture/MODEL_TO_CODE_TRACEABILITY_V331.md`：把当前模型规则、代码、输出和证据边界逐项对应；
- `docs/architecture/THESIS_WORK_AND_OUTPUT_REGISTER.md`：按模型设计、系统构建、实验设计、仿真结果登记工作与论文表图状态。

协议当前状态为`PILOT_NOT_EXECUTED; FORMAL_NOT_AUTHORIZED`。以下入口仍然只用于engineering/demo或历史复核。

### TASK-PV01：Pilot variance（当前只允许零 API）

```powershell
# 只打印冻结的P001-P006、D1-D3和分析规则；不写结果、不调用LLM
python run_v33_pilot_variance.py --plan-only

# 未来仅对已经完整执行的Pilot目录做离线分析
python run_v33_pilot_variance.py `
  --analyze-existing "results\v33_pilot_variance\<suite_id>" `
  --n-max <pre_frozen_cap>
```

真实Pilot入口还要求`--execute-real-pilot --allow-real-llm`、用户批准的`N_max`与provider-call ceiling、clean worktree和精确Git SHA。当前没有执行授权，不得运行P001–P006。实现合同见`docs/architecture/TASK_PV01_PILOT_VARIANCE_IMPLEMENTATION.md`。

### v3.3.1：后续研究使用

```powershell
python run_v33.py preflight --real

# 零 API 工程验证
python run_v33.py pipeline --llm fake --condition all --support both

# 一个真实 LLM engineering block
python run_v33.py pipeline --llm real --condition all --support both --allow-real-llm
```

真实 LLM 默认仍使用 `qwen-plus`、temperature `0.3`。新的运行属于 engineering/demo，不得加入已经关闭的 F001–F010。

### 论文数据与内部有效性证据输出

对一个已经完成的 v3.3.1 run：

```powershell
python run_v33_thesis.py "results\v33_runs\<run_id>"
```

单独生成可审计的 Agent cognition evolution 表图（纯离线、零 API）：

```powershell
python run_v33_cognition.py "results\v33_runs\<run_id>"
```

该输出中的 `reasoning` 只按原文登记显式的一句 appraisal，不代表隐藏思维链，也不进行新的文本情绪/主题编码。轨迹和变化量是单次运行描述性结果，不是总体推断。

生成固定拓扑上的网络状态/信息传播 GIF：

```powershell
python run_v33_thesis.py "results\v33_runs\<run_id>" `
  --animate-condition Rational-Hub-Immediate `
  --fps 3
```

> 当前 BA 网络拓扑在一次 run 内不发生结构变化。因此 GIF 展示的是 **固定网络上的 Trust、企业澄清暴露、UGC 发帖和传播边的动态变化**，不能称为“网络拓扑演化”。

### v3.2：只用于复核历史正式实验与兼容性

```powershell
python run_v32.py preflight
python run_v32.py verify
python run_v32.py formal-status
```

## 2. v3.3.1 科学结构

```text
Persona + Memory + Actual Observations
                 ↓
       Real/Fake LLM semantic appraisal
                 ↓
valence / arousal / credibility / evidence /
empathy / peer approval / hypocrisy / reasoning
                 ↓
Trust v3.3: asymmetric memory + partial adjustment
Att / peer-only SN / PBC
                 ↓
probabilistic clarification reach + Social UGC diffusion
                 ↓
renewal FMCG category-purchase opportunity
                 ↓
conditional brand choice + bounded-EWMA loyalty
                 ↓
descriptive analysis / internal-validity evidence / thesis outputs
```

LLM **不直接决定购买**。Trust/Att/SN/PBC、传播以及 FMCG 重复品牌选择由显式机制代码执行。

## 3. v3.3.1 与 v3.3 的关系

v3.3.1 不改变已验收的 v3.3 主体科学参数。它主要完成：

1. Social Feed 不再在接收者 LLM 前被 `[:180]` 截断；
2. v3.3.1 audit 保存完整 `post_content` 与简短 `reasoning`；
3. 修复 `delivery_lag=0` 时 amplified recipients 被遗漏的潜在分支错误（默认 lag 仍为 1，因此不改变当前基准运行）；
4. Reach 分析读取实际 configured lag，不再硬编码 `t0+1`；
5. 持久化真实网络拓扑、targeting/exposure、Git provenance；
6. 增加论文表格、内部有效性证据、机制图和网络动态图输出。

主体参数仍为 engineering assumptions，必须通过敏感性分析检验；不是现实总体估计值。

## 4. 关键文件

```text
GreenConsumer/
├── run_v33.py                         # v3.3.1 cognition/demand workflow
├── run_v33_thesis.py                  # 论文输出、验证证据、网络动画
├── run_v33_cognition.py               # 零API认知演化表图与hash manifest
├── run_v33_pilot_variance.py           # Pilot plan/offline analysis/显式执行门禁
│
├── greenconsumer_v33/
│   ├── cli.py
│   ├── runner.py                      # 9条件调度 + provenance/network audit
│   ├── demand.py
│   ├── analysis.py                    # 单block描述性 estimands
│   ├── pilot_variance.py               # seed合同、方差分解、planning SD、Holm OC
│   ├── visualization.py               # 基础v3.3.1图
│   ├── thesis_outputs.py              # 论文表格/验证证据/扩展图
│   ├── cognition_outputs.py           # 显式appraisal与心理状态演化后处理
│   └── network_animation.py           # 固定拓扑上的状态与传播动态图
│
├── mechanism_v33.py                   # Trust v3.3
├── purchase_mechanism_v33.py          # renewal + bounded EWMA loyalty
├── clarification_diffusion_v33.py     # probabilistic/lagged enterprise reach
├── task005_fmcg_runtime_v33.py        # isolated v3.3.1 AgentKernel adapter
│
├── plugins/agent/reflect/
│   └── GreenCognitionV33Plugin.py      # complete peer-message semantic appraisal
│
├── experiment_config.py               # 2×2×2 + common control
├── fmcg_scenario_v32.py               # shared fictional FMCG scenario/personas
├── simulation_core.py                 # shared AgentKernel engine (v3.2 provenance kept)
├── plugins/environment/network/
│   └── SocialNetworkPlugin.py          # fixed directed BA topology + UGC broadcast
├── tests/
└── reproducibility/formal_v32_n10/     # immutable v3.2 F001-F010 evidence archive
```

## 5. v3.3.1 输出目录

```text
results/v33_runs/<run_id>/
├── run_summary.json
├── cognitive_records.csv
├── agent_records.csv
├── agent_thoughts.csv
├── demand_opportunities.csv
├── choice_curves.csv
│
├── network_meta.json
├── network_nodes.csv
├── network_edges.csv
├── target_nodes.csv
├── clarification_exposure_plan.csv
├── effective_event_timeline.json
│
├── analysis_condition_summary.csv
├── analysis_demand_summary.csv
├── single_block_estimands.csv
├── clarification_reach_v33.csv
├── figures_v33/
│
└── thesis_outputs/
    ├── tables/
    ├── validation/
    ├── figures/
    ├── animations/
    ├── cognition/
    └── thesis_output_manifest.json
```

`thesis_outputs/validation/` 中的 PASS/SUPPORTED 只代表实现、构念操控或过程一致性证据。**不等于模型已经通过现实消费者外部效度验证。**

## 6. 论文可用的自动输出

当前后处理器可以自动生成：

- run design / Git / seed / parameter provenance；
- 条件结果表与单block estimands；
- Rational–Empathy 语义操控检验；
- consumer segment / Agent 异质性；
- Trust、Att、SN、PBC、crisis/repair memory 的逐 Tick 机制表；
- conversion support 与重复品牌选择分层结果；
- 网络结构指标与 Hub/Random targeting audit；
- LLM provider/replay/schema/fallback 审计；
- Subjective Norm peer-only 边界检验；
- pre-treatment common-history 一致性；
- demand probability / loyalty / renewal hard invariants；
- UGC broadcast delivery table；
- 固定网络上的状态与传播 GIF。

详细规范见：

```text
docs/architecture/V331_OUTPUT_AND_VALIDATION.md
```

## 7. 真实 LLM 与密钥

配置保存在 `configs/models_config.yaml`。Git 中只保存：

```yaml
api_key: "__FROM_ENV_DASHSCOPE_API_KEY__"
```

真实 key 必须来自环境变量 `DASHSCOPE_API_KEY`，不会写回配置或结果文件。

## 8. 正式实验身份

- Formal scientific source HEAD: `ef6567adaafcafcf3b9f6884295f509a05ed727e`
- Formal batch: `task005-fmcg-v32-formal-n10`
- Valid blocks: F001–F010 = 10/10
- F011+: forbidden for that closed formal design

正式证据归档在 `reproducibility/formal_v32_n10/`。v3.3.1 是后续机制与验证版本，若未来进行新的正式推断，必须重新冻结设计、参数、源码身份与分析契约，不能沿用旧 v3.2 formal inference 身份。

## 9. 冻结原则

v3.3.1 通过工程与内部有效性检查后，不再因为某次结果偏弱、偏强或图形不好看而修改主体科学参数。后续工作应转向 sensitivity analysis、network-topology robustness、prompt/LLM robustness 和独立 replication。
