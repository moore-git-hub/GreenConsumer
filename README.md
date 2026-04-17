# GreenConsumer（GABM 绿色消费仿真）

本仓库是一个基于 **Agent-Kernel（`agentkernel_standalone`）** 的多智能体仿真工程，用于研究“绿色消费/漂绿信息冲击/社交网络扩散”场景：

- 消费者被建模为 Agent（含画像、状态、感知、认知反思、计划决策、执行）
- 环境包含社交网络（NetworkX），支持邻居广播扩散
- 仿真输出包含微观行为日志、认知日志、宏观指标与可视化图谱

## 目录结构（简版）

- `run_simulation.py`：**主入口**，启动仿真并自动生成 `results/` 输出
- `configs/`：YAML 配置（agents / environment / system / models / simulation）
- `data/`：初始化数据（画像、关系、空间映射等）
- `plugins/`：核心逻辑（Agent 插件与环境插件）
- `results/`：仿真输出（CSV/PNG/JSON/GIF 等，建议不提交）
- `logs/`：运行日志（建议不提交）

## 快速开始

### 1) 环境准备

本项目依赖 `agentkernel_standalone`。你有两种常见方式：

- **方式 A（本地源码方式）**：确保本仓库的相对路径下存在 `../../packages/agentkernel-standalone`  
  `run_simulation.py` 会尝试自动将其加入 `sys.path`。
- **方式 B（pip 安装方式）**：在你的 Python 环境中安装 Agent-Kernel Standalone（以你的实际包名/镜像源为准）。

此外，`run_simulation.py` 还会用到：`numpy`、`pandas`、`networkx`、`matplotlib`、`pyyaml` 等。

### 2)（可选）配置 LLM

编辑 `configs/models_config.yaml`。

注意：该文件可能包含**明文 api_key**，不建议提交到 git；更推荐使用环境变量/本地私有配置（配合 `.gitignore` 或本地覆盖文件）。

如果模型配置读取失败，程序会自动回退到 **Mock Router**，仍可完成仿真流程（但认知/决策将是固定的 mock 输出）。

### 3) 运行仿真

在仓库根目录执行：

```bash
python run_simulation.py
```

### 4) 查看输出

运行完成后会在 `results/` 生成时间戳文件，例如：

- `simulation_log_YYYYMMDD_HHMMSS.csv`：每 tick、每 agent 的动作/信任/漂绿感知等
- `thoughts_log_*.csv`：认知反思输出（reasoning、trust_change、importance…）
- `macro_metrics_*.csv`：宏观指标（AvgTrust、ConversionRate、PostCount…）
- `network_graph_*.json`：社交网络拓扑（node-link）
- `macro_analysis_*.png`：信任与转化率耦合图（含关键干预事件标注）

## 配置入口说明

`configs/simulation_config.yaml` 是“总入口配置”，它会指向其他配置文件，并声明数据路径键：

- agent profiles：`data/agents/profiles.jsonl`
- relation/map：`data/relation/relation.jsonl`、`data/map/agents.jsonl`

Agent 模板与组件顺序在 `configs/agents_config.yaml` 中定义（profile/state/perceive/reflect/plan/invoke）。

