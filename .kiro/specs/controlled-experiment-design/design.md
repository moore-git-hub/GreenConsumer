# Technical Design Document

## Overview

本设计文档描述"内容×渠道×时机"三因子策略实验系统的技术架构。系统在现有 GreenConsumer GABM 仿真引擎之上构建实验调度层，通过配置驱动的方式实现 12 组策略组合的批量运行与帕累托前沿分析。

核心设计原则：
1. **不侵入现有插件**：所有实验逻辑通过配置注入和外部模块实现，不修改 ConsumerPlanPlugin / GreenCognitionPlugin / SocialNetworkPlugin 的类定义
2. **单一职责**：每个新模块只做一件事（配置定义 / 节点选择 / 澄清注入 / 指标计算 / 帕累托分析）
3. **可复现性**：随机种子在调用链顶层统一设置，向下传递

---

## Architecture

### 文件结构

```
GreenConsumer/
├── run_simulation.py              # 保留原入口（调用 simulation_core）
├── simulation_core.py             # 【新增】可复用仿真核心函数
├── experiment_config.py           # 【新增】实验配置定义（因子水平 + 组合生成）
├── run_experiments.py             # 【新增】实验批量调度入口
├── clarification_injector.py      # 【新增】企业澄清信息注入器
├── node_selector.py               # 【新增】渠道节点选择器
├── metrics_calculator.py          # 【新增】三目标指标计算
├── plot_pareto.py                 # 【新增】帕累托前沿分析与可视化
├── plugins/                       # 现有插件（不修改）
├── configs/                       # 现有配置（不修改）
├── data/                          # 现有数据
└── results/
    └── experiments/               # 【新增】实验结果目录
        ├── summary.csv            # 汇总表（12 行）
        └── comparison/            # 帕累托图表
```

### 调用链

```
run_experiments.py
  │
  ├── experiment_config.py          → 生成 12 个 ExperimentConfig
  │
  └── for each config:
        │
        ├── simulation_core.py      → run_simulation_core(config)
        │     │
        │     ├── generate_data (内联)  → 生成 Agent profiles
        │     ├── SocialNetworkPlugin   → 构建网络（接受 seed + network_type）
        │     ├── 主循环 Tick 1..30
        │     │     ├── 事件注入（ENTERPRISE_STRATEGY）
        │     │     ├── clarification_injector.py → 在指定 Tick 注入澄清
        │     │     │     └── node_selector.py   → 选择目标节点
        │     │     ├── Perceive → Reflect → Plan → Invoke
        │     │     └── 社交路由
        │     │
        │     └── metrics_calculator.py → 计算 T80 / Steady_State / Recovery
        │
        └── 写入 summary.csv
  │
  └── plot_pareto.py                → 读取 summary.csv → 帕累托分析
```

---

## Components

### Component 1: `experiment_config.py`

**对应需求**: Requirement 2, 10

```python
from dataclasses import dataclass
from typing import List
from itertools import product

@dataclass(frozen=True)
class ExperimentConfig:
    """单次实验运行的完整配置"""
    # 因子水平
    content_factor: str      # "rational-evidence" | "emotional-empathy"
    channel_factor: str      # "hub" | "random"
    timing_factor: str       # "immediate" | "delay-3" | "no-clarification"
    
    # 固定参数
    budget_k: int = 3        # 投放节点数
    random_seed: int = 42
    num_agents: int = 10
    total_ticks: int = 30
    scandal_tick: int = 5    # 丑闻爆发 Tick
    
    @property
    def exp_id(self) -> str:
        """唯一实验标识符，如 'Rational-Hub-Immediate'"""
        content_short = "Rational" if self.content_factor == "rational-evidence" else "Empathy"
        channel_short = "Hub" if self.channel_factor == "hub" else "Random"
        timing_short = {"immediate": "Imm", "delay-3": "D3", "no-clarification": "NoClr"}[self.timing_factor]
        return f"{content_short}-{channel_short}-{timing_short}"
    
    @property
    def clarification_tick(self) -> int | None:
        """澄清注入的 Tick，None 表示不澄清"""
        if self.timing_factor == "immediate":
            return self.scandal_tick
        elif self.timing_factor == "delay-3":
            return self.scandal_tick + 3
        return None


def generate_experiment_matrix() -> List[ExperimentConfig]:
    """生成 2×2×3 = 12 个实验配置"""
    content_levels = ["rational-evidence", "emotional-empathy"]
    channel_levels = ["hub", "random"]
    timing_levels  = ["immediate", "delay-3", "no-clarification"]
    
    configs = []
    for content, channel, timing in product(content_levels, channel_levels, timing_levels):
        configs.append(ExperimentConfig(
            content_factor=content,
            channel_factor=channel,
            timing_factor=timing,
        ))
    return configs
```

---

### Component 2: `node_selector.py`

**对应需求**: Requirement 4

```python
import networkx as nx
import random
from typing import List

def select_target_nodes(graph: nx.Graph, channel: str, k: int, seed: int) -> List[str]:
    """
    根据渠道策略选择 K 个目标节点。
    
    Args:
        graph: 社交网络图（节点 ID 为 Agent ID 字符串）
        channel: "hub" 或 "random"
        k: 投放节点数
        seed: 随机种子（仅 random 策略使用）
    
    Returns:
        选中的 Agent ID 列表
    """
    nodes = list(graph.nodes())
    if len(nodes) <= k:
        return nodes
    
    if channel == "hub":
        # 按度数降序排列，取 top-K
        degree_sorted = sorted(graph.degree(), key=lambda x: x[1], reverse=True)
        return [node_id for node_id, _ in degree_sorted[:k]]
    
    elif channel == "random":
        rng = random.Random(seed)
        return rng.sample(nodes, k)
    
    else:
        raise ValueError(f"Unknown channel: {channel}")
```

---

### Component 3: `clarification_injector.py`

**对应需求**: Requirement 3, 5, 6

```python
from typing import List, Optional

# 澄清内容模板（50-200 词，英文）
CONTENT_TEMPLATES = {
    "rational-evidence": (
        "Official Statement from Oatly: We acknowledge the concerns raised about our investment partners. "
        "Here are the verified facts: (1) Our carbon footprint has been independently audited by Bureau Veritas, "
        "showing a 73% reduction compared to dairy milk per liter. (2) We have committed $50M to a new "
        "Sustainability Accountability Fund with quarterly public reporting. (3) Our supply chain is now "
        "100% certified by the Rainforest Alliance. We invite scrutiny — all audit reports are available "
        "at oatly.com/transparency. Numbers don't lie."
    ),
    "emotional-empathy": (
        "A message from Oatly's team: We hear you. We understand the anger and the feeling of betrayal. "
        "You trusted us to be different, and we let you down. We are deeply sorry. The truth is, we made "
        "a difficult choice under financial pressure, and we should have been transparent from day one. "
        "We are not perfect, but we are committed to earning back your trust — not with words, but with "
        "actions. Starting today, we are restructuring our investor relationships and publishing monthly "
        "impact reports. We owe you that honesty."
    ),
}


class ClarificationInjector:
    """企业澄清信息注入器"""
    
    def __init__(self, config):
        self.content_factor = config.content_factor
        self.clarification_tick = config.clarification_tick  # None = 不澄清
        self.target_nodes: List[str] = []  # 由外部设置
    
    def should_inject(self, current_tick: int) -> bool:
        """当前 Tick 是否需要注入澄清"""
        if self.clarification_tick is None:
            return False
        return current_tick == self.clarification_tick
    
    def get_message(self) -> dict:
        """获取澄清消息包"""
        content = CONTENT_TEMPLATES[self.content_factor]
        return {
            "source": "Enterprise_Clarification",
            "content": content,
            "type": "clarification"
        }
    
    async def inject(self, agents, current_tick: int):
        """向目标节点注入澄清消息"""
        if not self.should_inject(current_tick):
            return
        
        msg = self.get_message()
        injected_count = 0
        
        for ag in agents:
            if ag.agent_id in self.target_nodes:
                state_plugin = ag.get_component("state")._plugin
                s_data = getattr(state_plugin, "state_data", 
                                 getattr(state_plugin, "_state_data", {}))
                inbox = s_data.get("incoming_messages", [])
                await state_plugin.set_state("incoming_messages", list(inbox) + [msg])
                injected_count += 1
        
        if injected_count > 0:
            print(f"💊 [Clarification] Tick {current_tick} | "
                  f"Content={self.content_factor} | "
                  f"Injected to {injected_count} nodes: {self.target_nodes}")
```

---

### Component 4: `metrics_calculator.py`

**对应需求**: Requirement 7

```python
from dataclasses import dataclass
from typing import List

@dataclass
class SimulationMetrics:
    """单次仿真运行的三目标评估结果"""
    t80: int                    # 恢复到基线 80% 的 Tick 数（越小越好）
    steady_state_score: float   # Tick 30 最终平均信任（越高越好）
    recovery_rate: float        # 转化率恢复程度（越高越好）
    
    # 辅助信息
    trust_min: float            # 信任最低点
    trust_min_tick: int         # 最低点所在 Tick
    baseline_trust: float       # 丑闻前基线信任


def compute_metrics(trust_trajectory: List[float], 
                    conversion_trajectory: List[float],
                    scandal_tick: int,
                    total_ticks: int) -> SimulationMetrics:
    """
    从逐 Tick 的信任和转化率轨迹计算三目标指标。
    
    Args:
        trust_trajectory: 长度为 total_ticks 的平均信任分列表（index 0 = Tick 1）
        conversion_trajectory: 长度为 total_ticks 的累计转化率列表
        scandal_tick: 丑闻爆发 Tick（1-indexed）
        total_ticks: 总 Tick 数
    """
    # 基线信任：丑闻前一 Tick（Tick 4，index 3）
    baseline_idx = scandal_tick - 2  # Tick 4 → index 3
    baseline_trust = trust_trajectory[baseline_idx] if baseline_idx >= 0 else trust_trajectory[0]
    
    # 信任最低点（丑闻后）
    post_scandal = trust_trajectory[scandal_tick - 1:]  # 从丑闻 Tick 开始
    trust_min = min(post_scandal)
    trust_min_tick = trust_trajectory.index(trust_min) + 1  # 转为 1-indexed
    
    # T80：从最低点恢复到基线 80% 的时间
    target_trust = baseline_trust * 0.8
    t80 = total_ticks  # 默认：未恢复（censored）
    for i in range(trust_min_tick - 1, total_ticks):
        if trust_trajectory[i] >= target_trust:
            t80 = i + 1 - trust_min_tick  # 从最低点算起的 Tick 数
            break
    
    # 稳态信任：Tick 30 的平均信任
    steady_state_score = trust_trajectory[-1]
    
    # 修复率：Tick 30 转化率 / 丑闻前峰值转化率
    pre_scandal_peak = max(conversion_trajectory[:scandal_tick - 1]) if scandal_tick > 1 else 0.0
    final_conversion = conversion_trajectory[-1]
    recovery_rate = final_conversion / pre_scandal_peak if pre_scandal_peak > 0 else 0.0
    
    return SimulationMetrics(
        t80=t80,
        steady_state_score=round(steady_state_score, 3),
        recovery_rate=round(min(recovery_rate, 2.0), 3),  # cap at 200%
        trust_min=round(trust_min, 3),
        trust_min_tick=trust_min_tick,
        baseline_trust=round(baseline_trust, 3),
    )
```

---

### Component 5: `simulation_core.py`

**对应需求**: Requirement 1, 11

从现有 `run_simulation.py` 提取核心逻辑为 `async def run_simulation_core(config: ExperimentConfig) -> dict`。

关键变更点：
1. 接受 `ExperimentConfig` 参数替代硬编码值
2. 在主循环中插入 `ClarificationInjector.inject()` 调用
3. 收集逐 Tick 的 `trust_trajectory` 和 `conversion_trajectory`
4. 运行结束后调用 `compute_metrics()` 计算三目标
5. 返回结构化结果字典

```python
async def run_simulation_core(config: ExperimentConfig) -> dict:
    """
    可复用仿真核心函数。
    
    Returns:
        {
            "exp_id": str,
            "config": dict,
            "metrics": SimulationMetrics,
            "trust_trajectory": List[float],
            "conversion_trajectory": List[float],
        }
    """
    # 1. 设置随机种子
    random.seed(config.random_seed)
    np.random.seed(config.random_seed)
    
    # 2. 生成 Agent（内联调用 generate_profiles 逻辑）
    # 3. 构建网络（传入 seed）
    # 4. 初始化 ClarificationInjector + NodeSelector
    # 5. 主循环（在事件注入后插入澄清注入）
    # 6. 计算指标
    # 7. 返回结果
```

---

### Component 6: `run_experiments.py`

**对应需求**: Requirement 8

```python
async def main():
    configs = generate_experiment_matrix()  # 12 个配置
    results = []
    
    for i, config in enumerate(configs, 1):
        print(f"\n{'='*50}")
        print(f"[{i}/{len(configs)}] Running: {config.exp_id}")
        print(f"{'='*50}")
        
        try:
            result = await run_simulation_core(config)
            results.append(result)
        except Exception as e:
            print(f"❌ Failed: {config.exp_id} — {e}")
            results.append({"exp_id": config.exp_id, "error": str(e)})
    
    # 写入 summary.csv
    write_summary_csv(results)
    
    # 生成帕累托分析
    analyze_pareto(results)
```

---

### Component 7: `plot_pareto.py`

**对应需求**: Requirement 9

帕累托支配判定逻辑：

```python
def is_dominated(a: SimulationMetrics, b: SimulationMetrics) -> bool:
    """判断 a 是否被 b 支配（b 在所有目标上都不差于 a，且至少一个严格更好）"""
    # 目标方向：T80 越小越好，Steady_State 越大越好，Recovery 越大越好
    better_or_equal = (
        b.t80 <= a.t80 and
        b.steady_state_score >= a.steady_state_score and
        b.recovery_rate >= a.recovery_rate
    )
    strictly_better = (
        b.t80 < a.t80 or
        b.steady_state_score > a.steady_state_score or
        b.recovery_rate > a.recovery_rate
    )
    return better_or_equal and strictly_better
```

可视化输出：
- `pareto_3d.png`：三维散点图，帕累托前沿点用红色标注
- `pareto_t80_vs_steady.png`：T80 vs 稳态信任 二维投影
- `pareto_t80_vs_recovery.png`：T80 vs 修复率 二维投影
- `pareto_steady_vs_recovery.png`：稳态信任 vs 修复率 二维投影
- `strategy_ranking.csv`：策略排名表

---

## Data Models

### 实验结果数据流

```
ExperimentConfig (输入)
    ↓
run_simulation_core()
    ↓
SimulationResult (输出)
    ├── exp_id: str
    ├── config: ExperimentConfig
    ├── metrics: SimulationMetrics
    │     ├── t80: int
    │     ├── steady_state_score: float
    │     └── recovery_rate: float
    ├── trust_trajectory: List[float]  (30 个值)
    └── conversion_trajectory: List[float]  (30 个值)
```

### summary.csv 格式

| Column | Type | Description |
|--------|------|-------------|
| exp_id | str | 实验标识符 |
| content_factor | str | 内容因子水平 |
| channel_factor | str | 渠道因子水平 |
| timing_factor | str | 时机因子水平 |
| t80 | int | 恢复速度（Ticks） |
| steady_state_score | float | 稳态信任分 |
| recovery_rate | float | 修复率 |
| trust_min | float | 信任最低点 |
| baseline_trust | float | 丑闻前基线 |
| is_pareto_optimal | bool | 是否为帕累托最优 |

---

## Key Design Decisions

1. **澄清注入时机在主循环中的位置**：在全局事件注入之后、Perceive 执行之前注入，确保澄清消息在同一 Tick 被 Agent 感知和处理。

2. **不修改 SocialNetworkPlugin 的 register_agents()**：网络类型切换通过在 `simulation_core.py` 中直接构建图并赋值给 `net_plugin.graph` 实现，不改变插件接口。

3. **Agent 数量默认 10 个**：快速迭代阶段使用小规模，`ExperimentConfig.num_agents` 可随时调整为 50。

4. **单种子设计**：初始阶段固定 seed=42，验证模型行为后再扩展为多种子重复运行。

5. **澄清消息的二次传播**：目标节点收到澄清后，如果 Plan 层决定 `is_posting=True`，其帖子会通过现有的社交路由机制自然传播给邻居，无需额外代码。
