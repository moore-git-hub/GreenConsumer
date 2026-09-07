# TASK_005 v3.3.1 网络规模 × 投放预算稳健性计划

**状态：pre-specified engineering robustness plan**  
**日期：2026-08-13**  
**正式推断：否**

## 1. 研究目的

固定 N=20 的 topology robustness 已显示：

- P1/P2/P3/P5 的方向在 BA / WS / community 网络中较稳定；
- P4 Hub−Random enterprise reach 对 topology 和具体 network realization 明显敏感；
- N=20 时 1 个 cognitive Agent = 5% reach，因此 P4 存在明显的有限规模离散化。

下一阶段回答两个不同问题：

1. **system-size robustness**：将 cognitive network 从 N=20 扩展到 N=40 / 80 后，主要 estimand 的方向与幅度是否发生结构性变化？
2. **budget-scaling robustness**：如果企业预算保持 K=3 不变，与保持投放比例 K/N≈15% 相比，Hub−Random 的渠道优势如何变化？

这两个问题不能混在一起，因为单纯增大 N 会机械地降低固定 K 的投放比例。

## 2. 为什么必须把 size 与 budget 分开

baseline 为：

```text
N = 20
K = 3
K/N = 0.15
```

若只把 N 增大而继续 K=3：

```text
N=40 -> K/N=0.075
N=80 -> K/N=0.0375
```

此时 observed effect 同时包含：

- 网络规模变化；
- 企业 paid-seed coverage share 下降。

因此设计两种预算制度：

### Regime A — fixed-budget

```text
N=20: K=3
N=40: K=3
N=80: K=3
```

解释为：企业可支付的核心种子节点数量固定。

### Regime B — proportional-budget

保持 baseline 15% paid-seed share：

```text
N=20: K=3
N=40: K=6
N=80: K=12
```

解释为：企业投放资源随目标网络规模同比例扩大。

N=20/K=3 是两个 regime 的共同 baseline，只运行一次。

## 3. 预设 profile 网格

Network sizes：

```text
N = 20 / 40 / 80
```

Network-only seeds：

```text
2026081501
2026081502
2026081503
2026081504
2026081505
```

Topology 暂时只使用 BA，`m=2`。

每个 network seed 的唯一 profiles：

```text
N20-K3
N40-K3
N40-K6
N80-K3
N80-K12
```

因此总 profile 数：

```text
5 profiles × 5 network seeds = 25 profiles
```

每个 profile 仍运行同一 2×2×2 + common control 条件矩阵。

**不允许运行完成后因为某个 N/K 结果更“理想”而更换 baseline。**

## 4. Persona population expansion

### 4.1 为什么不能简单复制 20 个 Agent

如果 N=40/80 只是把原 20 个 persona prompt 复制 2/4 次，在 deterministic Fake LLM 下，同 prompt + 同 observed text 容易产生高度同步的 semantic appraisal，造成伪异质性不足。

因此使用 **nested balanced mechanism-coverage panel**，而不是 clone replication。

### 4.2 Candidate universe

保留当前 EngineeringPersona 的六个显式 categorical dimensions：

- green orientation：4 levels；
- category-purchase frequency：4 levels；
- prior brand relationship：3 levels；
- price sensitivity：3 levels；
- availability friction：3 levels；
- social posting role：2 levels。

理论 candidate universe：

```text
4 × 4 × 3 × 3 × 3 × 2 = 864 unique combinations
```

这不是人口抽样框，也不代表现实比例，只是 mechanism-coverage design space。

### 4.3 Nested rule

- N20 必须精确等于当前冻结的 20 个 Engineering Personas；
- N40 包含完整 N20，再加入 20 个不重复 attribute tuples；
- N80 包含完整 N40，再加入 40 个不重复 attribute tuples。

因此：

```text
Panel20 ⊂ Panel40 ⊂ Panel80
```

共享 Agent IDs `Consumer_000 ...` 的 persona 内容不得因更大 N 而改变。

### 4.4 Composition-preserving rule

N40/N80 的 categorical marginal proportions 固定为 baseline N20 mechanism panel 的整数倍，而不是重新估计人口比例。

例如 baseline green orientation 为 5/5/5/5，因此：

```text
N40 -> 10/10/10/10
N80 -> 20/20/20/20
```

其他 dimensions 同理。

候选选择采用 deterministic greedy coverage algorithm：

1. 只从尚未使用的 unique tuple 中选择；
2. 不允许超过该 N 的预设 marginal target；
3. 优先补足相对缺口最大的 categorical levels；
4. 次级目标最大化尚少见的 pairwise categorical combinations；
5. 最终 tie 使用 lexicographic order，确保跨机器可复现。

这套算法的目标是**隔离 system size**，不是制造“更真实”的消费者人口。

## 5. 网络生成规则

本阶段只使用 BA：

```text
m = 2
```

保持同一个 generative rule，而不是保持固定 density。

随着 N 增大，edge count 按 BA 规则自然增加，density 会下降；这是 system-size scaling 的一部分，不进行结果驱动的密度校准。

Direction rule 与 v3.3.1 baseline 一致：

```text
higher undirected degree -> lower undirected degree
```

等度边继续使用现有 deterministic tie branch。

## 6. 其他冻结项

- T35；
- crisis T5；
- Trust baseline parameters；
- `paid_edge_probability=.55`；
- `paid_delivery_lag=1`；
- public exposure rate parameter 不变；
- Fake LLM；
- behavior seed / LLM seed / demand seed 不变；
- 25 micro-buyers per cognitive Agent；
- renewal demand mechanism；
- content/timing/channel treatment matrix；
- clarification texts；
- conversion-support mechanism。

## 7. 主要 estimands

沿用：

- P1：overall clarification → post-crisis Trust；
- P2：Rational − Empathy Trust；
- P3：Immediate − Delayed early Trust；
- P4：Hub − Random enterprise reach；
- P5：overall clarification → expected repeat choice；
- S1：conversion support → expected repeat choice。

另外新增 size-specific diagnostics：

- direct reach granularity `1/N`；
- Hub / Random eventual reach separately；
- `max_out_degree / N`；
- degree CV；
- average shortest path；
- paid seed share `K/N`；
- public exposure realized share；
- category opportunities per Agent（而不是总数 alone）。

## 8. Falsification / implementation checks

### V1 — N20 baseline exact reproduction

`N20-K3-network_seed2026081501` 必须复现当前 frozen BA baseline hash 与主要 Fake baseline outputs。

### V2 — nested Persona prefix

```text
Panel20 == Panel40[:20]
Panel40 == Panel80[:40]
```

### V3 — no persona clones

在每个 panel 内，六个 categorical attributes 的完整 tuple 必须唯一。

### V4 — marginal composition target

N40/N80 的每个 categorical dimension 必须精确达到由 N20 比例扩展得到的 integer target counts。

### V5 — shared-Agent pre-treatment prefix

对于 shared Agent IDs，在相同 network seed 下，T1–T5 的 non-social / pre-treatment key states 不得仅因未来存在额外节点而被提前改变。

若该检查失败，应先确定是否存在网络在危机前产生 social feed；不能直接把差异解释为“size effect”。

### V6 — within-profile topology identity

每个 size-budget profile 的9个条件必须共享同一 network hash。

### V7 — budget integrity

```text
fixed:       K = 3
proportional: K = round(0.15*N) = 3/6/12
```

Control 仍必须 K=0。

### V8 — clarification parameters frozen

所有 profiles 保持 `.55 / lag=1`。

### V9 — demand scale consistency

Demand layer 必须使用实际 persona panel，而不是历史固定 20 人列表；每个 cognitive Agent 继续对应 25 个 micro-buyers。

## 9. 解释规则

### 可以报告

- effect direction 是否随 N 改变；
- fixed K 下 Hub advantage 是否随 N 稀释；
- proportional K 是否恢复/维持 channel contrast；
- reach granularity 是否随 N 增大而降低；
- P1/P3/P5 是否对 N 与 K/N 敏感。

### 禁止报告

- “80 Agents 更接近真实消费者总体，因此一定更有效”；
- “N80 就等于样本量80”；
- “N 越大越真实”；
- “选择产生最大效果的 N 作为正式模型”；
- “这些 mechanism-coverage persona proportions 是真实市场份额”。

## 10. 与既有 literature / GABM 规范的关系

ABM 中 system size 本身可能影响 collective outcomes，因此应单独做 size sensitivity，而不能把单一 N 当作自然常数。GABM 文献也强调对 persona distributions、prompts 与场景输入进行 sensitivity testing，而不是把一次小规模运行当作现实总体估计。

本研究因此把 N=20/40/80 定义为**模型尺度稳健性**，不是统计样本扩容。

## 11. 输出计划

```text
results/v33_network_size_sensitivity/size_YYYYMMDD_HHMMSS/
├── size_profiles.csv
├── persona_panels.csv
├── persona_marginal_balance.csv
├── size_estimands.csv
├── size_network_metrics.csv
├── size_reach.csv
├── size_family_summary.csv
├── size_invariants.csv
├── size_summary.json
└── figures/
```

图形至少包括：

1. P1 vs N，按 budget regime 分线；
2. P3 vs N；
3. P4 vs N；
4. P5 vs N；
5. Hub/Random reach separately vs N；
6. reach granularity / max-out-degree share diagnostic。
