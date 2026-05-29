# Requirements Document

## Introduction

本需求文档定义"内容×渠道×时机"三因子实验系统的功能需求。该系统服务于漂绿（Greenwashing）情境下的传播治理与信任修复研究，通过将"澄清内容设计×放大路径选择×澄清时机"因子化，在预算约束下比较策略组合的速度-稳态-修复三目标权衡，输出帕累托前沿与适用边界，回答"何时应优先采用何种策略"这一核心管理问题。

实验矩阵规模：2（内容）× 2（渠道）× 3（时机）= 12 组，固定种子 42，共 12 次仿真运行。初始 Agent 规模为 10 个（快速迭代阶段），模型输出稳定后可扩展至 50 个。

## Glossary

- **Experiment_Orchestrator**: 批量调度模块，负责遍历实验矩阵、调用仿真核心函数并收集结果
- **Simulation_Core**: 从现有 `run_simulation.py` 提取的可复用仿真核心函数 `run_simulation_core(config)`，接受配置字典并返回结构化结果
- **Experiment_Config**: 实验配置定义模块，声明因子水平、预算约束、种子等参数
- **Clarification_Injector**: 企业澄清信息注入器，根据实验配置在指定 Tick 向指定节点投放澄清内容
- **Node_Selector**: 节点选择器，根据渠道策略（Hub / Random）从社交网络图中选取目标投放节点
- **Pareto_Analyzer**: 帕累托前沿分析与可视化模块，计算三目标空间中的非支配解集并输出图表
- **Content_Factor**: 内容因子，企业澄清信息的设计维度（理性证据型 / 情感共情型）
- **Channel_Factor**: 渠道因子，企业将澄清信息投放到哪类网络节点（Hub / Random）
- **Timing_Factor**: 时机因子，企业在丑闻爆发后何时发布澄清信息（即时 / +3 / 不澄清）
- **T80**: 速度指标，信任从最低点恢复到基线 80% 所需的 Tick 数
- **Steady_State_Score**: 稳态指标，Tick 30 时的最终平均信任分
- **Recovery_Rate**: 修复率指标，Tick 30 时的累计转化率恢复程度（相对于丑闻前峰值）
- **Hub_Node**: 度数（Degree Centrality）最高的网络节点，对应现实中的 KOL
- **Random_Node**: 随机选取的普通网络节点
- **Budget_K**: 每次澄清投放的目标节点数量上限，本实验固定 K=3

## Requirements

### Requirement 1: 仿真核心函数提取

**User Story:** As a researcher, I want a reusable simulation core function extracted from the existing `run_simulation.py`, so that I can programmatically invoke simulations with different configurations without code duplication.

#### Acceptance Criteria

1. THE Simulation_Core SHALL accept a configuration dictionary containing agent count, random seed, total ticks, scandal event definition, and clarification strategy parameters
2. THE Simulation_Core SHALL return a structured result object containing per-tick average trust scores, per-tick buying counts, cumulative buyer set, and per-tick posting counts
3. THE Simulation_Core SHALL initialize the random number generator with the seed specified in the configuration dictionary before constructing agents and network topology
4. THE Simulation_Core SHALL default to 10 agents with the existing Forrester 2026 cluster distribution (40% Dormant, 35% Convenient, 15% Active, 10% Non-Greens)
5. WHEN the Simulation_Core completes execution, THE Simulation_Core SHALL release all model resources and return results without retaining state between invocations

### Requirement 2: 实验配置定义

**User Story:** As a researcher, I want a declarative experiment configuration module, so that I can define the factorial design space in one place and easily modify factor levels.

#### Acceptance Criteria

1. THE Experiment_Config SHALL define Content_Factor with exactly two levels: rational-evidence (理性证据型) and emotional-empathy (情感共情型)
2. THE Experiment_Config SHALL define Channel_Factor with exactly two levels: Hub and Random
3. THE Experiment_Config SHALL define Timing_Factor with exactly three levels: immediate (scandal tick), delay-3 (scandal tick + 3), and no-clarification (control group)
4. THE Experiment_Config SHALL define Budget_K as 3 (number of target nodes per clarification injection)
5. THE Experiment_Config SHALL define the random seed as 42
6. THE Experiment_Config SHALL produce a total of 12 unique factor combinations (2 × 2 × 3)

### Requirement 3: 内容因子设计

**User Story:** As a researcher, I want two distinct clarification content templates, so that I can measure how message framing affects trust recovery dynamics.

#### Acceptance Criteria

1. WHEN Content_Factor is set to rational-evidence, THE Clarification_Injector SHALL generate a message containing quantitative data, third-party audit references, and factual corrections without emotional language
2. WHEN Content_Factor is set to emotional-empathy, THE Clarification_Injector SHALL generate a message containing acknowledgment of consumer feelings, expression of corporate remorse, and commitment to improvement using empathetic tone
3. THE Clarification_Injector SHALL ensure each content template is between 50 and 200 words in English to control for message length confounds

### Requirement 4: 渠道因子与节点选择

**User Story:** As a researcher, I want to target clarification messages to specific network positions, so that I can compare the amplification effectiveness of different seeding strategies.

#### Acceptance Criteria

1. WHEN Channel_Factor is set to Hub, THE Node_Selector SHALL select the top-K nodes ranked by degree centrality from the social network graph
2. WHEN Channel_Factor is set to Random, THE Node_Selector SHALL select K nodes uniformly at random from the social network graph using the experiment seed
3. THE Node_Selector SHALL compute centrality metrics from the BA scale-free network constructed by SocialNetworkPlugin
4. IF the social network graph contains fewer than K nodes, THEN THE Node_Selector SHALL select all available nodes and log a warning

### Requirement 5: 时机因子与澄清注入

**User Story:** As a researcher, I want to control when clarification messages are injected relative to the scandal event, so that I can measure the effect of response timing on trust recovery.

#### Acceptance Criteria

1. WHEN Timing_Factor is set to immediate, THE Clarification_Injector SHALL inject the clarification message at the same Tick as the scandal event (Tick 5)
2. WHEN Timing_Factor is set to delay-3, THE Clarification_Injector SHALL inject the clarification message exactly 3 Ticks after the scandal event (Tick 8)
3. WHEN Timing_Factor is set to no-clarification, THE Clarification_Injector SHALL not inject any clarification message during the entire simulation run
4. THE Clarification_Injector SHALL deliver the clarification message only to the nodes selected by Node_Selector, not to all agents

### Requirement 6: 澄清信息投放机制

**User Story:** As a researcher, I want clarification messages delivered through the existing social network infrastructure, so that they propagate naturally through the network topology.

#### Acceptance Criteria

1. THE Clarification_Injector SHALL deliver clarification messages to target nodes via the incoming_messages state field, consistent with the existing message delivery mechanism
2. WHEN a target node receives a clarification message, THE target node SHALL process the message through its Perceive-Reflect-Plan pipeline in the same Tick
3. THE Clarification_Injector SHALL tag clarification messages with source type "Enterprise_Clarification" to distinguish them from Global News and Social posts
4. WHEN a target node with social_role "KOL" or "Active User" processes a clarification message, THE target node SHALL have the opportunity to repost the message to its network neighbors in the subsequent Tick via the existing broadcast mechanism

### Requirement 7: 三目标评估指标计算

**User Story:** As a researcher, I want three well-defined outcome metrics computed for each simulation run, so that I can perform multi-objective comparison across strategy combinations.

#### Acceptance Criteria

1. THE Simulation_Core SHALL compute T80 as the number of Ticks from the trust minimum point to the first Tick where average trust reaches 80% of the pre-scandal baseline trust level
2. IF average trust does not reach 80% of baseline within the simulation horizon (30 Ticks), THEN THE Simulation_Core SHALL record T80 as 30 (censored value)
3. THE Simulation_Core SHALL compute Steady_State_Score as the mean trust score across all agents at Tick 30
4. THE Simulation_Core SHALL compute Recovery_Rate as the ratio of cumulative conversion rate at Tick 30 to the peak cumulative conversion rate observed before the scandal event
5. THE Simulation_Core SHALL record the pre-scandal baseline trust as the average trust score at the Tick immediately before the scandal event (Tick 4)

### Requirement 8: 实验批量调度

**User Story:** As a researcher, I want an orchestrator that automatically runs all 12 experiment configurations, so that I can execute the full factorial design without manual intervention.

#### Acceptance Criteria

1. THE Experiment_Orchestrator SHALL iterate over all 12 factor combinations, executing each combination exactly once with seed 42
2. THE Experiment_Orchestrator SHALL store results for each run in a structured format containing the factor combination identifier, T80, Steady_State_Score, and Recovery_Rate
3. THE Experiment_Orchestrator SHALL output a consolidated CSV file with one row per run (12 rows total) containing all factor levels and all three outcome metrics
4. WHEN a single simulation run fails due to an exception, THE Experiment_Orchestrator SHALL log the error, record the run as failed, and continue with the remaining runs
5. THE Experiment_Orchestrator SHALL display progress information showing the current run number out of 12 total runs

### Requirement 9: 帕累托前沿分析与可视化

**User Story:** As a researcher, I want Pareto front analysis across the three objectives, so that I can identify which strategy combinations offer the best trade-offs and derive actionable policy recommendations.

#### Acceptance Criteria

1. THE Pareto_Analyzer SHALL identify all non-dominated solutions in the three-dimensional objective space (minimize T80, maximize Steady_State_Score, maximize Recovery_Rate)
2. THE Pareto_Analyzer SHALL generate a 3D scatter plot showing all 12 strategy combinations with Pareto-optimal points highlighted in a distinct color
3. THE Pareto_Analyzer SHALL generate three 2D projection plots: T80 vs Steady_State_Score, T80 vs Recovery_Rate, and Steady_State_Score vs Recovery_Rate
4. THE Pareto_Analyzer SHALL annotate each point in the plots with its factor combination label (e.g., "Rational-Hub-Immediate")
5. THE Pareto_Analyzer SHALL output a summary table ranking strategy combinations by each individual objective and identifying the Pareto-optimal set
6. THE Pareto_Analyzer SHALL save all plots as PNG files at 300 DPI resolution in the results directory

### Requirement 10: Agent 规模可配置

**User Story:** As a researcher, I want the agent count to be configurable, so that I can start with a small scale for rapid iteration and scale up once the model output is stable.

#### Acceptance Criteria

1. THE Simulation_Core SHALL accept an agent_count parameter in the configuration dictionary with a default value of 10
2. THE Simulation_Core SHALL construct a BA scale-free network matching the specified agent count with m=2
3. WHEN agent_count is set to 10, THE Node_Selector SHALL still identify Hub nodes (highest degree) and Random nodes from the smaller network
4. THE Experiment_Config SHALL expose agent_count as a top-level parameter that can be changed to 50 for the final production run

### Requirement 11: 实验结果可复现性

**User Story:** As a researcher, I want deterministic reproducibility of simulation results, so that I can validate findings and enable peer review.

#### Acceptance Criteria

1. WHEN the same configuration dictionary is provided twice, THE Simulation_Core SHALL produce identical T80, Steady_State_Score, and Recovery_Rate values
2. THE Simulation_Core SHALL set random seeds for Python random, NumPy, and NetworkX graph generation before each run
3. THE Experiment_Orchestrator SHALL log the complete configuration for each run to enable exact reproduction of any individual experiment
