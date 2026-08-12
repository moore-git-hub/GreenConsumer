# GreenConsumer TASK_005 FMCG v3.2 代码库结构图

## 当前状态
TASK_005 FMCG scenario v3.2 的核心模型、工程验证、真实 LLM 方差阶段、N=10 正式实验与正式分析均已完成。正式实验绑定的模型源代码 HEAD 为 `ef6567adaafcafcf3b9f6884295f509a05ed727e`。

不建议为了目录美观直接移动或重命名冻结源码。正式实验已经绑定源码身份与哈希，第一轮整理应采用“canonical path + 文档索引 + legacy 边界 + reproducibility archive”，物理迁移应放到后续独立重构阶段。

## Canonical v3.2 模型链

### 实验矩阵与情境
- `experiment_config.py`：2×2×2 Content × Channel × Timing + `NoClarification-Control`
- `fmcg_scenario_v32.py`：VerdantCo Oat、20个 engineering personas、危机与澄清材料

### 语义认知层
- `mechanism_v32_semantics.py`：严格语义 schema
- `plugins/agent/reflect/GreenCognitionV32Plugin.py`：LLM 只做语义评估，不直接决定购买

### 心理状态转移层
- `mechanism_v2.py`：Trust、Att、危机记忆、修复记忆、情绪映射
- `mechanism_v31_cognition.py`：peer-only SN
- `plugins/agent/plan/ConsumerPlanV32Plugin.py`：连接语义、心理状态、TPB intention 与发帖

### 社会网络与触达
- `plugins/environment/network/SocialNetworkPlugin.py`：BA 底图与有向传播
- `node_selector.py`：Hub/Random 等预算节点选择
- `clarification_injector.py`：public organic + paid seed + one-hop amplification

### FMCG 重复选择层
- `purchase_mechanism_v31.py`：购买机会、条件品牌选择、loyalty、PBC facilitation
- `purchase_mechanism_v32.py`：persona→demand 映射
- `purchase_mechanism_v3.py`：早期 construct-valid bridge，保留为历史机制来源

### v3.2 runtime 与审计
- `task005_fmcg_runtime_v32.py`：version-scoped runtime patch 与恢复
- `task005_fmcg_audited_router_v32.py`：prompt/response hash、schema、seed、model、temperature 审计

### 正式实验层
正式 N=10 的最终再现材料应统一归档：
- `run_task005_fmcg_formal_v32_n10.py`
- `activate_task005_fmcg_formal_v32_n10.py`
- `analyze_task005_fmcg_formal_v32_n10.py`
- formal contracts / seed ledger / closeout manifest

旧 `run_formal_launch.py`、`run_formal_replications.py` 属于 superseded formal-v1/v2，不得作为当前 v3.2 入口。

## 推荐逻辑结构

```text
GreenConsumer/
├── README.md
├── [frozen canonical v3.2 Python modules at current paths]
├── plugins/
├── analysis/
├── tests/
├── configs/
├── docs/
│   ├── architecture/CODEBASE_MAP_V32.md
│   ├── thesis/MODEL_DESIGN_CHAPTER_V32.md
│   ├── reproducibility/TASK005_V32_FORMAL_CLOSEOUT.md
│   ├── decisions/
│   └── legacy/LEGACY_BOUNDARY.md
├── .kiro/specs/task005-replication-inference/
└── results/   # generated outputs, not source
```

## 物理目录重构的条件
只有在保存完整 formal source/runtime/analysis snapshot 后，才考虑迁移到 `src/greenconsumer/`。迁移后必须修改 imports，并重跑 v3.2 unit tests、fake AgentKernel smoke 和 zero-LLM replay，同时明确“重构代码与正式实验 source HEAD 不同，但目标是机制等价”。

对学位论文而言，优先保证可复现性和审计链完整，而不是为了 Python packaging 的形式美观改变已经完成正式实验的路径。
