# GreenConsumer — TASK_005 FMCG v3.2 GABM

当前 canonical scenario：完全虚构的植物奶品牌危机场景 **VerdantCo Oat**。

## 一、现在只认一个人工入口

```powershell
python run_v32.py <command>
```

或等价地：

```powershell
python -m greenconsumer_v32 <command>
```

推荐工作流：

```powershell
# 0. 零API环境检查
python run_v32.py preflight

# 1. 六组v3.2核心测试
python run_v32.py verify

# 2. 完整fake-LLM流程：运行→需求层→分析→画图
python run_v32.py pipeline --llm fake --condition all

# 3. 真实LLM就绪检查（零API调用）
python run_v32.py preflight --real

# 4. 真实LLM工程/演示全过程
python run_v32.py pipeline --llm real --condition all --allow-real-llm

# 5. 查看已经关闭的正式F001-F010状态
python run_v32.py formal-status
```

**`pipeline --llm real` 是新的真实 LLM 工程/演示入口，不是重新开启正式实验。**
正式 F001-F010 已关闭，不允许把新的 demo/engineering run 混入 formal sample。

详细说明见 `docs/architecture/WORKFLOW_V32.md`。

## 二、全过程结构

```text
run_v32.py
   │
   └─ greenconsumer_v32.cli
        │
        ├─ preflight / verify
        │
        ├─ runner
        │    ├─ experiment_config.py
        │    ├─ fmcg_scenario_v32.py
        │    ├─ task005_fmcg_runtime_v32.py
        │    ├─ fake / real LLM router
        │    └─ common-history recording/replay
        │
        ├─ canonical cognitive core
        │    ├─ mechanism_v32_semantics.py
        │    ├─ GreenCognitionV32Plugin.py
        │    ├─ mechanism_v2.py
        │    ├─ mechanism_v31_cognition.py
        │    └─ ConsumerPlanV32Plugin.py
        │
        ├─ social network
        │    ├─ SocialNetworkPlugin.py
        │    ├─ node_selector.py
        │    └─ clarification_injector.py
        │
        ├─ demand
        │    ├─ purchase_mechanism_v31.py
        │    └─ purchase_mechanism_v32.py
        │
        ├─ analysis
        └─ visualization
```

新入口把原来散落在大量 `run_*.py`、`analysis/*.py` 中的日常操作收敛成
`preflight → verify → run/pipeline → analyze → plot → formal-status`。

## 三、正式版本身份

- Scenario: `fmcg-scenario-3.2`
- Formal source HEAD: `ef6567adaafcafcf3b9f6884295f509a05ed727e`
- Post-formal repository consolidation: `e8da7902ba518ac2701abf6ec81b1c7f51171d05`
- Cognitive agents: 20 个平衡 engineering personas
- Horizon: 30 Ticks
- Crisis: Tick 5
- Communication: Content × Channel × Timing = 2 × 2 × 2
- Common control: `NoClarification-Control`
- Conversion support: offline PBC-only cross
- Formal valid replication blocks: F001-F010, 10/10

## 四、核心构念边界

- LLM 只做语义评估，不直接决定购买。
- SN 只由实际 social-feed observation 中的 perceived peer approval 更新。
- 企业澄清和 global news 不直接更新 SN。
- Hub/Random 操作 reach，不自动等于 persuasion 或 purchase。
- conversion support 只通过 PBC 通道进入 demand layer。
- category-purchase opportunity 与 treatment identity 分离。
- 行为端是 repeated focal-brand choice，不是 absorbing first purchase。
- 20 cognitive agents 不是人口代表样本。
- micro-buyers 不是独立 formal replications。

## 五、代码分层

### 新的日常工作流层
- `run_v32.py`
- `greenconsumer_v32/`

### 冻结的科学机制层
- `experiment_config.py`
- `fmcg_scenario_v32.py`
- `task005_fmcg_runtime_v32.py`
- `mechanism_v2.py`
- `mechanism_v31_cognition.py`
- `mechanism_v32_semantics.py`
- `purchase_mechanism_v31.py`
- `purchase_mechanism_v32.py`
- v3.2 AgentKernel plugins

### 正式实验归档
- `reproducibility/formal_v32_n10/`

### 历史开发入口
旧 `run_simulation.py`、`run_formal_launch.py`、pilot/variance runners 等仍保留作
开发审计，但不再作为日常 v3.2 主入口。见 `docs/legacy/RUNNER_INDEX.md`。

## 六、输出

新的 engineering/demo run 统一写入：

```text
results/v32_runs/<run_id>/
├── run_summary.json
├── cognitive_records.csv
├── demand_opportunities.csv
├── choice_curves.csv
├── analysis_condition_summary.csv
├── analysis_demand_summary.csv
├── analysis_summary.json
├── figures/
│   ├── trust_trajectories.png
│   └── repeat_choice_trajectories.png
└── conditions/<exp_id>/
    ├── cognitive_records.csv
    ├── trust_trajectory.csv
    └── llm_audit.jsonl
```

## 七、文档入口

- `docs/architecture/WORKFLOW_V32.md`
- `docs/architecture/CODEBASE_MAP_V32.md`
- `docs/architecture/MODEL_TO_CODE_TRACEABILITY.md`
- `docs/thesis/MODEL_DESIGN_CHAPTER_V32.md`
- `docs/reproducibility/TASK005_V32_FORMAL_CLOSEOUT.md`
- `docs/legacy/LEGACY_BOUNDARY.md`
