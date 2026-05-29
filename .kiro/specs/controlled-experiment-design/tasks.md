# Implementation Tasks

## Task 1: 创建 experiment_config.py

- [x] 创建 `experiment_config.py`，定义 `ExperimentConfig` dataclass（content_factor, channel_factor, timing_factor, budget_k, random_seed, num_agents, total_ticks, scandal_tick）
- [x] 实现 `exp_id` 属性，生成唯一标识符如 "Rational-Hub-Imm"
- [x] 实现 `clarification_tick` 属性，根据 timing_factor 计算澄清注入 Tick（immediate→5, delay-3→8, no-clarification→None）
- [x] 实现 `generate_experiment_matrix()` 函数，生成 2×2×3=12 个 ExperimentConfig 实例
- [x] 添加字段验证：content_factor ∈ {"rational-evidence", "emotional-empathy"}，channel_factor ∈ {"hub", "random"}，timing_factor ∈ {"immediate", "delay-3", "no-clarification"}

### Requirements Addressed
- Requirement 2: 实验配置定义

---

## Task 2: 创建 node_selector.py

- [x] 创建 `node_selector.py`，实现 `select_target_nodes(graph, channel, k, seed)` 函数
- [x] Hub 策略：按 degree centrality 降序排列，取 top-K 节点
- [x] Random 策略：使用指定 seed 的 `random.Random` 实例随机采样 K 个节点
- [x] 边界处理：当图节点数 < K 时，返回全部节点并打印警告

### Requirements Addressed
- Requirement 4: 渠道因子与节点选择

---

## Task 3: 创建 clarification_injector.py

- [x] 创建 `clarification_injector.py`，定义 `CONTENT_TEMPLATES` 字典（rational-evidence / emotional-empathy 两个模板，各 50-200 词英文）
- [x] 实现 `ClarificationInjector` 类，构造函数接受 ExperimentConfig
- [x] 实现 `should_inject(current_tick)` 方法，判断当前 Tick 是否需要注入
- [x] 实现 `get_message()` 方法，返回带 source="Enterprise_Clarification" 的消息字典
- [x] 实现 `async inject(agents, current_tick)` 方法，向 target_nodes 列表中的 Agent 信箱注入消息
- [x] 注入时打印日志：Tick、内容类型、注入节点数

### Requirements Addressed
- Requirement 3: 内容因子设计
- Requirement 5: 时机因子与澄清注入
- Requirement 6: 澄清信息投放机制

---

## Task 4: 创建 metrics_calculator.py

- [x] 创建 `metrics_calculator.py`，定义 `SimulationMetrics` dataclass（t80, steady_state_score, recovery_rate, trust_min, trust_min_tick, baseline_trust）
- [x] 实现 `compute_metrics(trust_trajectory, conversion_trajectory, scandal_tick, total_ticks)` 函数
- [x] T80 计算：从信任最低点开始，找到首次达到 baseline×0.8 的 Tick，未达到则记为 30
- [x] Steady_State_Score：取 trust_trajectory 最后一个值
- [x] Recovery_Rate：Tick 30 转化率 / 丑闻前峰值转化率，cap 在 2.0

### Requirements Addressed
- Requirement 7: 三目标评估指标计算

---

## Task 5: 创建 simulation_core.py（从 run_simulation.py 提取）

- [x] 创建 `simulation_core.py`，定义 `async def run_simulation_core(config: ExperimentConfig) -> dict`
- [x] 从 `run_simulation.py` 提取核心逻辑：Agent 初始化、网络构建、主循环、数据结算
- [x] 在函数开头设置随机种子：`random.seed(config.random_seed)`, `np.random.seed(config.random_seed)`
- [x] Agent 数量使用 `config.num_agents`（内联调用 generate_profiles 逻辑，不写文件）
- [x] 网络构建时传入 `seed=config.random_seed`
- [x] 在主循环的事件注入之后、Perceive 之前，插入 `clarification_injector.inject(agents, tick)` 调用
- [x] 收集逐 Tick 的 `trust_trajectory`（平均信任）和 `conversion_trajectory`（累计转化率）
- [x] 主循环结束后调用 `compute_metrics()` 计算三目标
- [x] 返回结构化字典：`{"exp_id", "config", "metrics", "trust_trajectory", "conversion_trajectory"}`
- [x] 确保函数执行完毕后不保留全局状态（Agent/网络/Router 全部释放）

### Requirements Addressed
- Requirement 1: 仿真核心函数提取
- Requirement 10: Agent 规模可配置
- Requirement 11: 实验结果可复现性

---

## Task 6: 更新 run_simulation.py 为薄包装

- [ ] 修改 `run_simulation.py` 的 `run()` 函数，改为调用 `run_simulation_core(default_config)`
- [ ] 默认配置使用 E1 Baseline 参数（BA 网络、RAG 开启、遗忘曲线开启、10 Agent、no-clarification）
- [ ] 保留 `if __name__ == "__main__"` 入口，确保原有的独立运行方式不受影响
- [ ] 保留原有的 CSV 输出和 `analyze_results()` 后置分析逻辑

### Requirements Addressed
- Requirement 1: 仿真核心函数提取（向后兼容）

---

## Task 7: 创建 run_experiments.py（批量调度）

- [x] 创建 `run_experiments.py`，实现 `async def main()` 入口
- [x] 调用 `generate_experiment_matrix()` 获取 12 个配置
- [x] 顺序遍历每个配置，调用 `run_simulation_core(config)`
- [x] 打印进度：`[1/12] Running: Rational-Hub-Imm`
- [x] 异常处理：单次失败时捕获异常、记录错误、继续后续运行
- [x] 收集所有结果，调用 `write_summary_csv(results)` 写入 `results/experiments/summary.csv`
- [x] 所有运行完成后调用 `plot_pareto.py` 的分析函数

### Requirements Addressed
- Requirement 8: 实验批量调度

---

## Task 8: 创建 plot_pareto.py（帕累托分析）

- [x] 创建 `plot_pareto.py`，实现帕累托支配判定函数 `is_dominated(a, b)`
- [x] 实现 `find_pareto_front(results)` 函数，返回非支配解集
- [x] 生成 3D 散点图（T80 × Steady_State × Recovery），帕累托点红色高亮
- [x] 生成 3 个 2D 投影图（T80 vs Steady, T80 vs Recovery, Steady vs Recovery）
- [x] 每个点标注 exp_id 标签
- [x] 标注干预事件时间点（Tick 1/5/10）
- [x] 输出策略排名表 `strategy_ranking.csv`（按各目标排序 + 帕累托最优标记）
- [x] 所有图表保存为 300 DPI PNG 到 `results/experiments/comparison/`

### Requirements Addressed
- Requirement 9: 帕累托前沿分析与可视化

---

## Task 9: 集成测试与验证

- [ ] 运行 `python run_experiments.py`，确认 12 次仿真全部完成无报错
- [ ] 验证 `results/experiments/summary.csv` 包含 12 行数据，所有指标非空
- [ ] 验证帕累托图表已生成（4 张 PNG + 1 个 CSV）
- [ ] 验证可复现性：相同 seed 运行两次，结果完全一致
- [ ] 验证 `python run_simulation.py` 仍可独立运行（向后兼容）
- [ ] 清理临时验证脚本（`_verify_*.py`）

### Requirements Addressed
- Requirement 11: 实验结果可复现性
- 全部需求的集成验证
