# TASK_005 v3.3.1 网络等度边方向稳健性结果

**日期：2026-08-13**  
**运行：`orientation_20260813_162126`**  
**状态：engineering PASS with directed-channel boundary**  
**正式推断：否；Fake LLM；T35**

## 1. 目的

固定 N=20 的 topology robustness 发现 Watts–Strogatz 网络中 Hub−Random 企业直接触达优势明显弱于 BA，并且 WS 存在大量 equal-degree edges。由于冻结 v3.3.1 的有向化规则对等度边使用 NetworkX edge iteration 的 first endpoint 作为 source，本轮在**完全相同的无向底图**上比较三种预先登记的 tie rules，以判断 P4 较弱是否主要是无向结构结果，还是被等度边方向规则显著驱动。

比较规则：

- `legacy_first_endpoint`：冻结 baseline；
- `reverse_first_endpoint`：仅反转所有等度边方向；
- `hash_balanced`：以 network seed + canonical endpoint IDs 的 SHA-256 确定等度边方向，与 edge iteration order 无关。

三类拓扑 × 5 network-only seeds × 3 tie rules，共 45 个完整 2×2×2 + control profiles。

## 2. 实现与证伪检查

本轮 `orientation_invariants.csv` 共 241 项检查，全部 PASS：

- baseline BA + seed 2026081501 + legacy rule 精确复现冻结 network hash；
- 对同一 topology × network seed，三种 orientation 的 node set 与 unordered edge set 完全相同；
- 所有 unequal-degree edges 的方向完全不变；
- 所有发生方向变化的边均为 equal-degree ties；
- Random K=3 target allocation 不变；
- public organic allocation 不变；
- p=.55、lag=1 等 clarification baseline 参数不变。

因此本轮差异可归因于预先规定的 equal-degree orientation rule，而不是底图、Agent、Random target 或处理参数发生变化。

## 3. P4 主要结果

P4 定义为 configured enterprise-delivery window 内：

`Hub eventual enterprise reach − Random eventual enterprise reach`。

五张网络的均值如下：

| topology | Legacy | Reverse ties | Hash-balanced ties |
|---|---:|---:|---:|
| BA | 0.40 | 0.39 | 0.40 |
| Watts–Strogatz | 0.12 | 0.05 | 0.14 |
| Community SBM | 0.17 | 0.19 | 0.18 |

### BA

五张 BA 无向网络在三种 tie rules 下 P4 均保持正向。每张网络的 P4 变化范围为 0–0.05；家族均值约为 0.39–0.40。BA 的 Hub advantage 对 equal-degree orientation rule 基本稳定。

### Community SBM

五张 Community 无向网络在三种规则下 P4 也全部保持正向。单图 P4 变化范围最大为 0.10；家族均值为 0.17–0.19。Community 的 Hub advantage 幅度低于 BA，但方向对 tie rule 稳定。

### Watts–Strogatz

WS 对 tie rule 最敏感。五张无向网络中有两张出现 sign instability：

- seed 2026081502：legacy = 0.00，reverse = −0.05，hash-balanced = +0.15；
- seed 2026081504：legacy = +0.15，reverse = 0.00，hash-balanced = +0.10。

其余三张 WS 网络在三种规则下均保持正向。家族均值从 legacy 的 0.12 降至 reverse 的 0.05，hash-balanced 为 0.14。

因此，WS 中“Hub 比 Random 的直接触达优势较弱”具有一定无向结构基础——即便采用 iteration-order-independent 的 hash-balanced rule，均值仍明显低于 BA；但是**P4 的符号在部分具体 WS realization 中不具 orientation-rule 稳健性**。

## 4. 为什么 WS 更容易受到 orientation rule 影响

当前预设网络中 equal-degree tie-edge share：

- BA：约 2.8%–5.6%；
- Community：约 7.7%–25.7%；
- WS：约 30%–80%。

WS 为近似规则网络，大量端点具有相同 undirected degree。改变等度边方向不会改变无向拓扑，但会显著重排 out-degree；而当前 Hub targeting 以 out-degree 识别结构中心，因此在 WS 中 tie rule 能影响 Hub seed set 及其一跳 paid amplification reach。

这说明当前模型中渠道策略不只依赖“无向网络类型”，还依赖 directed social relation 的定义。缺乏真实 follower/followee 或信息流方向数据时，不能把任何单一 orientation rule 当成经验真值。

## 5. 其他 estimands 的方向稳定性

45 个 orientation profiles 中：

- P1 Overall clarification → post-crisis Trust：45/45 positive，范围约 0.1909–0.3209；
- P2 Rational − Empathy post-crisis Trust：45/45 negative，范围约 −0.0867 至 −0.0620；
- P3 Immediate − Delayed early Trust：45/45 positive，范围约 0.1923–0.3715；
- P5 Overall clarification → expected repeat choice：45/45 positive，范围约 0.00960–0.02385；
- S1 conversion support：45/45 positive，约 0.02813–0.02866；
- P4：42 positive、2 zero、1 negative。

因此 orientation uncertainty 主要集中在渠道直接触达 contrast P4，而不是推翻总体澄清、响应时机或下游 repeat-choice 的方向。

## 6. 对前一轮 topology robustness 的修正

前一轮可以保留以下结论：

1. BA 中 Hub targeting 的直接触达优势明显且较稳定；
2. Community 中 Hub advantage 较小但仍保持正向；
3. WS 中 Hub advantage 总体较弱。

但必须修正过强表述：

> 不能把某一张 WS legacy directed realization 的 P4 视为稳定的 topology-only effect。

更准确的论文表述为：

> Hub targeting 的直接触达优势具有显著结构边界。在具有较强 degree heterogeneity 的 BA 网络中，该优势对等度边方向规则保持稳定；在近似规则的 WS 网络中，由于大量等度边使 out-degree centrality 对有向化规则更敏感，Hub−Random 的局部优势可能减弱至零或发生符号变化。因此，渠道结构效应同时受到无向拓扑异质性与有向信息流定义的约束。

## 7. 对下一阶段 Network Size × Budget 的决定

本轮不要求改变冻结 BA baseline orientation。原因：

- BA 五张 N=20 网络的 P4 对三种 tie rules 全部保持正向；
- BA equal-degree tie share 很低；
- Network-size suite 的目标是检验 N 与 K/N，而不是重新选择 orientation rule。

因此恢复执行已经预登记的 `V331_NETWORK_SIZE_AND_BUDGET_ROBUSTNESS_PLAN.md`：

- BA m=2；
- N = 20 / 40 / 80；
- 5 network-only seeds；
- fixed K=3 与 proportional K/N=15%（K=3/6/12）；
- nested non-cloned Persona panels；
- Fake LLM，T35；
- baseline orientation 继续使用 frozen legacy rule。

Network-size 输出中应继续记录 degree heterogeneity 与 reach granularity；若 N40/N80 的 BA equal-degree tie share 或 P4 行为出现异常，再单独追加大 N orientation boundary check，而不是事后改变主 orientation rule。

## 8. 论文表述边界

### 可以写

> 在固定无向网络的情况下，BA 与 Community 网络中的 Hub 触达优势对三种预先设定的等度边方向规则保持正向；Watts–Strogatz 网络中则有两个 realization 出现符号不稳定，表明近似规则网络中的渠道优势更依赖有向关系定义。

### 不能写

- “hash-balanced 是真实社会网络方向”；
- “WS 中 Random 一定优于 Hub”；
- “45 profiles 是45个现实独立样本”；
- “orientation robustness 证明 BA 是真实平台的最佳网络模型”；
- 根据本轮 P4 最大值重新选择 baseline tie rule。

## 9. 证据文件

- `orientation_summary.json`
- `orientation_profiles.csv`
- `orientation_estimands.csv`
- `orientation_reach.csv`
- `orientation_network_metrics.csv`
- `orientation_invariants.csv`
- `orientation_p4_stability.csv`
- `P4_ORIENTATION_ROBUSTNESS.png`

本结果属于工程稳健性与结构边界证据，不进行 p 值、置信区间或外部总体推断。
