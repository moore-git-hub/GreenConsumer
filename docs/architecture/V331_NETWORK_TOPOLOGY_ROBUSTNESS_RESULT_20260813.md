# TASK_005 v3.3.1 固定 N 网络拓扑稳健性结果

**日期：2026-08-13**  
**运行：`topology_20260813_153842`**  
**状态：PASS with an explicit channel-boundary finding**  
**范围：Fake-LLM、T35、N=20、5 个预设 network-only seeds / topology；工程稳健性，不是正式推断**

## 1. 设计回顾

本轮保持以下内容冻结：

- 20 个既有 Engineering Personas；
- T35；
- Fake semantic router；
- Trust baseline parameters；
- clarification `paid_edge_probability=.55`、`paid_delivery_lag=1`；
- K=3；
- behavior / LLM / demand seeds；
- 2×2×2 + common control treatment matrix。

仅改变网络底图：

- Barabási–Albert（BA）；
- Watts–Strogatz（WS）；
- community stochastic block model（SBM）。

每类网络使用 5 个事前规定的 network-only seeds：`2026081501`–`2026081505`。

## 2. 实现有效性

`topology_invariants.csv` 共 76 条检查，76/76 PASS：

- baseline BA hash 精确复现；
- 每个 profile 内 9 条件共用同一 network hash；
- 20 个 Agent 节点集合不变；
- Random K=3 目标节点分配不随 topology/network seed 改变；
- public organic exposure IDs 不变；
- clarification baseline 参数冻结。

因此，本轮拓扑比较没有同时混入 Persona、Random-target、public-exposure 或 clarification-parameter 的变化。

## 3. 各拓扑 family 的描述性结果

| Estimand | BA mean [min,max] | WS mean [min,max] | Community mean [min,max] | 跨 family 方向 |
|---|---:|---:|---:|---|
| P1 Overall clarification → post-crisis Trust | 0.2525 [0.2172, 0.3205] | 0.2540 [0.2289, 0.2682] | 0.2204 [0.1919, 0.2418] | 15/15 positive |
| P2 Rational − Empathy Trust | -0.0761 [-0.0858,-0.0687] | -0.0796 [-0.0861,-0.0723] | -0.0670 [-0.0739,-0.0628] | 15/15 negative |
| P3 Immediate − Delayed early Trust | 0.2638 [0.2169,0.3715] | 0.2610 [0.2276,0.2901] | 0.2353 [0.1923,0.2752] | 15/15 positive |
| P4 Hub − Random enterprise reach | 0.4000 [0.25,0.55] | 0.1200 [0.00,0.15] | 0.1700 [0.10,0.30] | BA/community positive；WS 1 realization = 0 |
| P5 Overall clarification → expected repeat choice | 0.01679 [0.01287,0.02376] | 0.01526 [0.01355,0.01696] | 0.01412 [0.01235,0.01629] | 15/15 positive |
| S1 Conversion support | 0.02829 [0.02820,0.02836] | 0.02848 [0.02831,0.02866] | 0.02841 [0.02818,0.02860] | 15/15 positive |

### 3.1 主机制结果的方向稳健

P1、P2、P3、P5、S1 在 15 张预设网络上均未发生方向翻转。

这支持一个有限但重要的模型结论：在当前参数 envelope 与 N=20 机制覆盖面板下，**总体澄清效应、内容 contrast、响应时机 contrast 与 repeat-choice 方向并非只由单一 BA realization 产生。**

该结论仍是 Fake-LLM engineering robustness，不可表述为现实总体效应或统计显著性。

### 3.2 P4 暴露出明确的拓扑边界条件

P4 的 family 结构与其他 estimands 不同：

- BA：5/5 positive，mean = 0.40；
- Community：5/5 positive，mean = 0.17；
- WS：4 positive + 1 zero，mean = 0.12。

因此，“Hub targeting 一定优于 Random targeting”不是 topology-universal conclusion。

更严谨的机制表述是：

> Hub targeting 的直接触达优势依赖网络中是否存在足够的结构异质性，使 top-out-degree 节点与随机节点形成实质性的广播能力差异。

在 degree 更均匀的网络中，Hub 与 Random 的差距可以显著缩小，甚至在某一预设 WS realization 中降为 0。

这不是模型失败，而是 RQ2 渠道策略的结构性边界条件。

## 4. 网络结构指标

### BA

- directed edges：36；
- degree CV：0.523–0.807；
- max out-degree：8–15；
- average shortest path：1.995–2.253；
- greedy modularity：0.270–0.351。

### Watts–Strogatz

- directed edges：40；
- degree CV：0.079–0.237；
- max out-degree：5–7；
- average shortest path：2.400–2.768；
- greedy modularity：0.390–0.465。

### Community SBM

- directed edges：34–40；
- degree CV：0.306–0.451；
- max out-degree：5–8；
- average shortest path：2.321–2.753；
- greedy modularity：0.404–0.481。

因此本轮的三类网络确实生成了不同的结构环境，而不是仅换了 network label。

## 5. Exploratory structure–effect diagnostic

作为**事后描述性诊断**，将 15 张网络的结构指标与 P4 做相关检查，可见：

- degree CV 与 P4：Spearman ρ ≈ +0.856；
- max out-degree 与 P4：ρ ≈ +0.812；
- average shortest path 与 P4：ρ ≈ -0.760；
- greedy modularity 与 P4：ρ ≈ -0.669；
- equal-degree tie-edge share 与 P4：ρ ≈ -0.805。

这些数值只说明在当前 15 个预设网络中，Hub−Random reach contrast 与“度异质性/Hub可分辨性”呈强描述性对应。

**禁止将这些相关系数解释为独立因果效应或显著相关。** 三类 topology 同时改变多个网络性质，且 n=15 仅是工程网络 realizations；若论文需要正式识别哪个结构指标驱动 P4，需要另行设计 matched-network / controlled-topology experiment。

## 6. 对论文的直接意义

### 可以写

> 在固定消费者面板和行为机制的条件下，研究进一步使用 BA、Watts–Strogatz 与社群型随机块网络开展拓扑稳健性检验。总体澄清效应、即时响应优势以及预期重复选择效应在 15 个预设网络 realization 中保持方向一致；但 Hub 相对 Random 的直接触达优势明显依赖网络拓扑。在度分布较均匀的 WS 网络中，该优势显著缩小，并在一个网络 realization 中降为零。这表明渠道策略效果具有网络结构边界，而非无条件成立。

### 不能写

- “BA 网络被证明最符合现实社交媒体”；
- “BA 一定优于 WS / SBM”；
- “Hub 渠道在所有网络中都更有效”；
- “5 个 network seeds 构成现实总体样本”；
- “结构指标与 P4 的相关性证明了因果关系”。

## 7. 下一设计决策

本轮已经证明 N=20 下 P4 存在明显的 0.05 离散步长与 realization dependence。下一步不再继续增加 topology family，而转向：

**Network size × targeting budget robustness**。

预先计划：

- N = 20 / 40 / 80；
- BA generative rule 固定（m=2）；
- 同时比较 fixed K=3 与 proportional K≈15% 两种预算制度；
- 采用 nested、balanced、non-cloned Persona panel，使 N 的变化不等同于简单复制 20 个相同 prompt；
- 保持 T35、Trust、clarification、Fake LLM、25 micro-buyers/Agent 与行为随机机制冻结。

详细计划见 `V331_NETWORK_SIZE_AND_BUDGET_ROBUSTNESS_PLAN.md`。
