# TASK_005 v3.3.1 Network Topology Robustness Plan

**状态：pre-specified before execution**  
**日期：2026-08-13**  
**正式推断：否（engineering robustness）**

## 1. 研究目的

Paid-reach sensitivity 已表明：在固定 N=20 的当前 BA 网络中，Hub−Random direct reach 始终为正，但其精确幅度会随离散 recipient changes 在 .40/.45 之间变化。由于一个 Agent 在 N=20 时对应 5 个百分点，单一 BA realization 不足以支撑一般化的网络机制结论。

本阶段只改变 **network topology / network realization**，检验：

1. Hub targeting 的 direct-reach advantage 是否依赖单一 BA realization；
2. P1 / P3 / P5 是否在不同受控网络结构下保持相同方向；
3. 网络的 degree heterogeneity、clustering 与 community structure 如何改变 Hub targeting 的相对价值；
4. 当前 BA baseline 的强 Hub 结构是否是 P4 较大的主要来源之一。

## 2. 为什么先固定 N=20，而不是立即改 N=40/80

当前 v3.3.1 使用 20 个显式、审计过的 Engineering Personas。直接增加 cognitive-Agent N 需要重新定义 Persona population construction，并会同时改变：

- Agent composition；
- network size；
- K/N；
- downstream micro-buyer总量；
- LLM调用规模。

这会把“拓扑效应”和“人口规模效应”混在一起。因此本阶段严格保持同一20个Persona，仅改变网络结构。Network-size N=20/40/80 将作为后续独立 Decision Record。

## 3. 预先规定的拓扑族

### A. Barabási–Albert baseline

- `n=20`；
- `m=2`；
- 与现有 SocialNetworkPlugin 完全相同的 BA 建图与有向化规则；
- 作为 heterogeneous-hub baseline。

### B. Watts–Strogatz small-world comparator

- `n=20`；
- `k=4`；
- rewiring probability `beta=0.10`；
- 平均无向度约为4，与 BA baseline 的平均无向度3.6接近；
- 用于比较更均匀度分布、较高局部聚类和短路径结构。

### C. Community stochastic-block comparator

- `n=20`；
- 4个等规模block，每个5个节点；
- `p_in=0.65`；
- `p_out=0.08`；
- 用于形成较明显的社群内连接与有限跨社群边；
- 参数为 engineering comparator，不代表真实平台估计值。

这些具体参数是**受控比较设定**，不是经验校准值。论文中不得将其解释为真实微博/小红书/B站网络的估计参数。

## 4. 有向化规则

为避免同时改变“拓扑族”和“传播方向机制”，所有无向底图使用当前 v3.3.1 相同规则转换为有向图：

> 对每条无向边，高度数端点 → 低度数端点；若底图度数相同，则保留现有实现的确定性 tie branch。

该规则使结构上更中心的节点更像广播源，是当前模型的一部分。本阶段不修改它。

注意：WS/community 中 equal-degree edges 可能比 BA 更多，因此输出必须记录 `equal_degree_tie_edge_share`。该指标用于识别 direction-orientation artifact；它不是 hard failure。如果替代拓扑结果主要由大量 tie edges 驱动，后续应另做 orientation robustness，而不能把差异全部归因于 topology family。

## 5. Network realization seeds

为了避免只比较一张 BA、一张 WS、一张 community 图，预先使用5个独立的**network-only seeds**：

- `2026081501`；
- `2026081502`；
- `2026081503`；
- `2026081504`；
- `2026081505`。

重要：

- simulation/behavior seed仍固定为 `2026081501`；
- LLM seed固定为 `2026081601`；
- demand seed固定为 `2026081701`；
- network seed只影响图生成，不改变行为随机数、public exposure draw、paid-edge delivery draw或Random-target draw。

因此15个 profiles = 3 topology families × 5 network realizations，属于 matched engineering robustness，不是15个现实统计样本。

## 6. 固定部分

所有profile固定：

- Fake LLM deterministic semantic fixture；
- T35；
- 20 cognitive Agents与同一Persona-ID映射；
- 25 micro-buyers/Agent；
- K=3；
- paid edge probability=.55；
- paid delivery lag=1；
- public organic exposure rule；
- frozen baseline Trust parameters；
- 2×2×2 + common control；
- crisis/clarification stimuli；
- conversion-support design。

## 7. 主要输出

### 网络结构指标

每个 topology × seed 输出：

- nodes / directed edges；
- undirected density；
- mean / max out-degree；
- undirected degree coefficient of variation；
- average clustering coefficient；
- average shortest path length（仅connected时）；
- greedy-modularity partition modularity；
- equal-degree tie-edge share；
- network hash。

### 机制 estimands

继续使用现有定义：

- P1：clarification vs Control post-crisis Trust；
- P2：Rational−Empathy Trust；
- P3：Immediate−Delayed early Trust；
- P4：Hub−Random eventual direct enterprise reach；
- P5：clarification vs Control expected repeat choice；
- S1：conversion-support effect。

## 8. Falsification / implementation checks

### Hard checks

1. 每个profile中9个conditions必须使用完全相同network hash；
2. Agent node set必须始终是同一20个`Consumer_000...019`；
3. Random channel 的 K=3 target IDs 必须跨所有topology/network seeds保持不变，因为 Random targeting 使用冻结的 simulation seed，而不是 network seed；
4. public organic exposure node set必须跨所有profiles保持不变；
5. Control、treatment matrix、Trust参数、p=.55、lag=1均不得改变；
6. BA + network_seed=`2026081501` 必须复现已审计 baseline network hash：
   `886be697894ff8f79c4e72be4b778978f9c40390ee5a15dcb1e09b73040281ac`。

### 非hard、但必须报告

- network edge count不同；
- connectivity；
- equal-degree tie share；
- Hub target identity变化；
- P4的跨realization离散范围。

这些是 topology variation 的组成部分，不应被自动判为错误。

## 9. 解释规则

本阶段不计算总体 p-value 或置信区间。每个 topology family 的5个network realizations只用于工程描述：

- min / max / mean；
- sign consistency；
- topology-specific pattern；
- 与网络指标的描述性对应关系。

若P4在某些topology/seed中为0或负，必须报告为结构边界条件，不允许删除该network realization或重新调topology参数。

## 10. 科学依据

- Barabási & Albert (1999) 用增长与优先连接刻画高度异质、Hub突出的网络结构；
- Watts & Strogatz (1998) 提供高聚类与短路径并存的小世界比较框架；
- Holland, Laskey & Leinhardt (1983) 的 stochastic blockmodel 提供基于组间连接概率的社群结构比较思路；
- 本研究使用三类网络是模型结构稳健性比较，不声称任何一种是现实社交平台的唯一真实生成机制。

## 11. 论文可用表述

> 为检验渠道效应是否依赖单一网络结构，研究在保持消费者Persona、传播预算、内容、时机、认知机制与行为随机过程不变的条件下，将网络拓扑分别设为BA、Watts–Strogatz与具有社群结构的随机块模型，并对每类拓扑使用5个预先设定的独立network seeds。该分析旨在检验机制结构稳健性，而非估计现实平台网络参数。

## 12. 禁止表述

- “WS/SBM 参数来源于真实平台校准”；
- “5个network seeds等于现实样本量5”；
- “某拓扑下P4最大，所以该拓扑最真实”；
- “BA网络证明社交媒体天然服从无标度分布”；
- “拓扑敏感性结果自动证明外部效度”。