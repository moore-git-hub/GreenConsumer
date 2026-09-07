# TASK_005 v3.3.1 网络等度边方向稳健性计划

**状态：pre-specified engineering robustness plan**  
**日期：2026-08-13**  
**正式推断：否**

## 1. 触发原因

固定 N=20 的 topology robustness 已经发现：

- BA 的 equal-degree tie-edge share 约为 2.8%–5.6%；
- Community SBM 约为 7.7%–25.7%；
- Watts–Strogatz 高达 30%–80%。

当前有向化规则对不等度边定义明确：

```text
higher undirected degree -> lower undirected degree
```

但对等度边，历史实现使用 NetworkX edge iteration 中的 first endpoint 作为 source。该规则在 BA 中影响较小，但在近似正则的 WS 网络中可能决定大量边的方向，从而影响 out-degree、Hub 选点和 P4 Hub−Random reach contrast。

因此，在把“WS 中 Hub 优势较弱”写成论文结构边界前，必须确认该结论不是 equal-degree tie-breaking implementation artifact。

## 2. 研究问题

在保持**完全相同的无向底图**时，仅改变等度边的方向决策，主要 estimands 尤其 P4 是否稳定？

## 3. 预设 tie rules

对每张已预设的 BA / WS / Community undirected graph 比较：

1. `legacy_first_endpoint`
   - 冻结 v3.3.1 baseline；
   - 等度边使用历史 first-endpoint 方向。
2. `reverse_first_endpoint`
   - 只把等度边的历史方向全部反转；
   - 用作 deterministic boundary rule。
3. `hash_balanced`
   - 只对等度边，按 `SHA256(network_seed, sorted endpoint IDs)` 决定方向；
   - 与 NetworkX edge iteration order 无关；
   - 不是现实校准，只是中性的 deterministic robustness rule。

不等度边在三种规则下必须完全一致。

## 4. Profile 网格

沿用 topology robustness 的 15 张预设无向网络：

```text
3 topology families × 5 network-only seeds
```

每张无向网络使用 3 个 tie rules，因此：

```text
15 × 3 = 45 directed network profiles
```

每个 profile 继续运行 2×2×2 + common control。

## 5. 冻结项

- N=20；
- 同一 20 Engineering Personas；
- T35；
- Fake LLM；
- K=3；
- p=.55；
- lag=1；
- Trust baseline；
- demand mechanism与25 micro-buyers/Agent；
- simulation / LLM / demand seeds；
- treatment matrix；
- topology生成参数；
- network-only seeds。

## 6. Hard falsification checks

### O1 — baseline reproduction

BA + network seed 2026081501 + `legacy_first_endpoint` 必须继续精确复现 frozen baseline network hash。

### O2 — undirected substrate invariance

对同一 topology + network seed，三种 tie rules 的 unordered edge set 必须完全相同。

### O3 — unequal-degree direction invariance

所有 degree(u) != degree(v) 的边在三种 tie rules 下必须保持同一方向。

### O4 — changed edges subset of tie edges

任何 orientation difference 必须只发生在 degree(u) == degree(v) 的边。

### O5 — Agent / Random target / public exposure invariance

- node set不变；
- Random K=3目标节点不变；
- public organic exposure IDs不变。

Hub目标节点允许变化，因为out-degree本来就是被检验的结构后果。

### O6 — mechanism parameters frozen

Trust、p=.55、lag=1、K=3均不得改变。

## 7. 主要输出

- P1 / P2 / P3 / P4 / P5 / S1；
- Hub reach 与 Random reach separately；
- max out-degree；
- out-degree CV；
- equal-degree tie count/share；
- 各 tie rule 相对 legacy 的 P4 change；
- 每张无向图上 P4 的 sign stability。

## 8. 解释规则

### 若 P4 对 tie rule 稳定

可以加强表述：

> WS / community 中 Hub−Random reach差异的缩小主要来自无向结构本身，而非等度边任意定向规则。

### 若 P4 对 tie rule 明显变化或翻转

必须报告：

> 渠道优势不仅依赖无向拓扑，也依赖有向关系定义；当前模型无法在缺乏真实 follower/followee 方向数据时把某一 orientation rule 视为经验真值。

此时不能用 WS 的单一 legacy P4 结果作为稳定渠道结论。

## 9. 与下一阶段的顺序

Network-size × budget 代码可以保留，但**在本orientation check完成前不建议运行其完整25-profile suite**。原因是先关闭当前已识别的方向规则实现不确定性，可以避免把一个明确的 topology-audit 问题拖入后续尺度解释。

完成 orientation robustness 后，再恢复执行 `V331_NETWORK_SIZE_AND_BUDGET_ROBUSTNESS_PLAN.md`。
