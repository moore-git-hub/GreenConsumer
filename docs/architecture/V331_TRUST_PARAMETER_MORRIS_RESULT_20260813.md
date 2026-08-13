# TASK_005 v3.3.1 Trust 参数敏感性 Stage B：Morris 结果记录

**日期：2026-08-13**  
**来源运行：`morris_20260813_113712`**  
**状态：PASS（Fake-LLM global screening / engineering robustness）**  
**正式推断：否；参数校准：否；外部效度证明：否**

## 1. 设计与实现验证

本轮严格沿用预先登记的 Morris 设计：7 个 Trust 参数、6 levels、标准化步长 `Delta=0.6`、10 条 trajectories、每条 8 个 points，因此总计 80 个 trajectory points。实际产生 80 个 unique model evaluations；每个 parameter × estimand 得到 10 个 elementary effects。

实现验证全部通过：

- Morris design validation：50/50 PASS；
  - trajectory point count：10/10 PASS；
  - each parameter changed once：10/10 PASS；
  - normalized step = 0.6：10/10 PASS；
  - points on six-level grid：10/10 PASS；
  - parameter bounds：10/10 PASS；
- implementation invariants：240/240 PASS；
  - pre-crisis T1–T4 invariance：80/80 PASS；
  - network hash invariance：80/80 PASS；
  - P4 direct enterprise reach invariance：80/80 PASS；
- P4 的七个 Trust 参数 `mu_star` 均严格为 0。

因此，Stage B 的参数变化没有污染危机前状态、网络拓扑或企业直接触达层。

## 2. 80 个全局参数点上的输出方向

在本轮七维 engineering robustness envelope 内，80 个 unique parameter vectors 得到：

| Estimand | Minimum | Maximum | Direction over 80 evaluations |
|---|---:|---:|---|
| P1 Overall clarification − Control Trust | +0.155769 | +0.336351 | 80/80 positive |
| P2 Rational − Empathy Trust | −0.135570 | −0.030954 | 80/80 negative |
| P3 Immediate − Delayed early Trust | +0.109621 | +0.404284 | 80/80 positive |
| P4 Hub − Random direct enterprise reach | +0.450000 | +0.450000 | constant |
| P5 clarification − Control expected repeat choice | +0.014574 | +0.019215 | 80/80 positive |
| S1 conversion support present − absent | +0.028291 | +0.028541 | 80/80 positive |

该结果比 Stage-A OAT 更强地支持：在预先设定的七维参数空间中，P1/P2/P3/P5 的**描述性方向**没有因多个 Trust 参数同时变化而翻转。这里的 80 points 是 Morris design points，不是统计独立现实样本，因此不得将“80/80”解释为人口概率或显著性。

## 3. P1：总体信任修复

按 `mu_star` 排名：

| Rank | Parameter | mu | mu_star | sigma | sigma / mu_star |
|---:|---|---:|---:|---:|---:|
| 1 | repair_retention | +0.084872 | 0.084872 | 0.016961 | 0.200 |
| 2 | empathy_repair_weight | +0.080892 | 0.080892 | 0.010422 | 0.129 |
| 3 | event_adjustment | +0.053825 | 0.053825 | 0.031867 | 0.592 |
| 4 | quiet_adjustment | −0.018985 | 0.019984 | 0.016085 | 0.805 |
| 5 | crisis_retention | −0.010061 | 0.010061 | 0.008086 | 0.804 |
| 6 | hypocrisy_weight | −0.001839 | 0.001868 | 0.002243 | 1.201 |
| 7 | repair_saturation | −0.000380 | 0.000380 | 0.000070 | 0.185 |

`repair_retention` 与 `empathy_repair_weight` 的 elementary effects 在 10 条 trajectories 中方向一致且 `sigma/mu_star` 较低，说明它们在本轮参数空间中是较稳定的主导修复通道。`event_adjustment` 仍位列第三，但其 `sigma/mu_star≈0.59`，表明事件响应速度的边际影响随参数空间位置变化更明显，可能包含非线性和/或与其他 Trust 参数的交互。

## 4. P2：Rational − Empathy 内容差异

排名：

1. `empathy_repair_weight`：`mu_star=0.073252`，`mu=-0.073252`；
2. `repair_retention`：`0.026208`；
3. `event_adjustment`：`0.008681`；
4. `quiet_adjustment`：`0.007827`；
5–7. 其余参数影响很弱。

`empathy_repair_weight` 的 10 个 elementary effects 全部为负且 `sigma/mu_star≈0.128`。这再次说明 Fake semantic fixture 下的 Rational−Empathy contrast 高度依赖模型中显式定义的 empathy relational-repair pathway。

**解释边界：** 这是结构敏感性证据，不意味着现实消费者中 Empathy 一定优于 Rational。Real-LLM 内容框架结果必须单独进行 prompt / provider stochasticity robustness。

## 5. P3：即时响应相对延迟响应

排名：

| Rank | Parameter | mu_star | sigma / mu_star |
|---:|---|---:|---:|
| 1 | event_adjustment | 0.204444 | 0.282 |
| 2 | empathy_repair_weight | 0.106604 | 0.135 |
| 3 | quiet_adjustment | 0.041002 | 0.560 |
| 4 | hypocrisy_weight | 0.019003 | 0.597 |
| 5 | crisis_retention | 0.016537 | 0.398 |
| 6 | repair_retention | 0.005541 | 0.262 |
| 7 | repair_saturation | 0.000502 | 0.181 |

`event_adjustment` 是 P3 的明确首要敏感参数，符合机制结构：P3 只看 T6–T9，而 Delayed treatment 尚未进入，因此事件发生后 Trust 向目标状态调整的速度直接决定 early timing contrast 的幅度。

## 6. P5：重复品牌选择

排名与 P1 高度一致：

1. `repair_retention`：`mu_star=0.002158`；
2. `empathy_repair_weight`：`0.002060`；
3. `event_adjustment`：`0.001467`；
4. `quiet_adjustment`：`0.000506`；
5. `crisis_retention`：`0.000315`；
6. `hypocrisy_weight`：`0.000041`；
7. `repair_saturation`：`0.000010`。

80 个 global screening points 中 P5 始终为正，范围约为 +1.46 至 +1.92 percentage points。说明在当前 engineering envelope 内，Trust 参数共同变化会改变重复选择效应的幅度，但没有造成方向翻转，也没有出现下游 demand layer 对 Trust 扰动的异常放大。

## 7. P4 与 S1：构念分离证据

### P4

所有 Trust 参数：

`mu = mu_star = sigma = 0`。

且所有 80 evaluations 中 P4 恒为 `0.45`。这构成较强的内部 construct-separation evidence：企业 direct reach 由 targeting/network/delivery 决定，不被 Trust persuasion 参数反向改变。

### S1

S1 全部 80 evaluations 的范围仅为 `0.028291–0.028541`。虽然 Morris 在 S1 内部仍能给出参数相对排序，但所有绝对影响都非常小；因此不能因为 `hypocrisy_weight` 在 S1 中 rank 1 就称其为“重要的 conversion-support 参数”。更适当的解释是：conversion support 仍主要是 PBC/demand-side facilitation channel，对 Trust 参数变化整体弱敏感。

## 8. `sigma` 的解释

本轮中，部分次要参数出现较高 `sigma/mu_star`，尤其当 `mu_star` 本身接近 0 时。该比率会因分母很小而被放大，因此不能机械按比率阈值认定“强交互”。

较值得关注的是：

- P1/P5 的 `event_adjustment`：影响强度较高，同时 `sigma/mu_star≈0.57–0.59`；
- P2 的 `repair_retention`：`≈0.42`；
- P3 的 `quiet_adjustment`：`≈0.56`。

这些结果说明关键参数的 elementary effect 在不同参数空间位置存在一定变化，但 Morris 本身不能把这种变化唯一分解为非线性或具体参数交互。

## 9. Stage A 与 Stage B 的一致性

两阶段结论高度一致：

- P1 / P5：`repair_retention`、`empathy_repair_weight`、`event_adjustment` 为主要敏感参数；
- P2：`empathy_repair_weight` 明显第一；
- P3：`event_adjustment` 明显第一；
- P4：对 Trust 参数严格不敏感；
- `repair_saturation` 在当前单次修复结构下整体影响很弱。

因此 Stage A 的局部排序不是单纯由 baseline 附近单点造成，Stage B 在多参数共同变化下给出了相同的主要机制排序。

## 10. 是否继续做 Sobol / variance decomposition

当前建议：**不把 Sobol 作为主流程的下一步。**

理由：

1. 本论文核心研究问题不是估计 Trust engineering parameters 的精确方差贡献；
2. Stage A + Morris 已经覆盖 local、structured-boundary 与 global-screening 三类参数稳健性证据；
3. 主要 estimand 在整个 Morris envelope 中均未方向翻转；
4. 下一阶段更直接对应研究问题的是企业触达机制、network size 与 topology robustness；
5. Sobol first/total effects 需要大量额外模型评估，且当前 parameter bounds 仍是 engineering envelopes，不是经验概率分布。

若后续导师/审稿人明确要求“量化关键 Trust 参数的一阶与总方差贡献”，可针对 `repair_retention`、`empathy_repair_weight`、`event_adjustment`，必要时加入 `quiet_adjustment`，单独建立新的 variance-based Decision Record；届时其结论必须表述为**条件于所设 engineering distributions 的模型输出方差分解**。

## 11. 论文可采用的结论

> 在局部敏感性分析基础上，本研究进一步采用 Morris elementary-effects 方法对七项信任动态参数实施全局筛查。80 个预先生成的七维参数组合均通过危机前状态、网络拓扑及触达层不变量检验。结果表明，总体信任修复与重复品牌选择主要受修复记忆保持、同理性修复权重和事件响应速度影响；内容框架差异主要受同理性修复权重影响；即时响应优势则主要受事件响应速度影响。所有 Morris 参数组合中，总体澄清效应、即时响应效应与重复选择效应均保持既定方向，而企业直接触达对 Trust 参数严格不敏感。该结果支持模型主要机制在预设工程参数范围内具有结构稳健性，但不构成现实参数校准或外部效度证明。

## 12. 证据文件 SHA-256

- `morris_design.csv`: `6e2f6bf2f48e98dd2d5f6322cd8201a9db1f700bc7c1fc2ab945cc8c24610b8b`
- `morris_design_validation.csv`: `93cc2bb246ad2d098d51ae4c53782e4d14c79d1175d0620664a196f04a9ac286`
- `morris_elementary_effects.csv`: `cd0ac8b0d3014918757f6396055f69d7b1e05a76e85c409083b6296aa8fd1080`
- `morris_evaluation_outputs.csv`: `795fe2584caae9c4c79873e444581c6eb147b7f2c6e9ef36beb42c9eb5f0904e`
- `morris_invariants.csv`: `a88246580c18c73256a763e1a832025f26b2a6e6b08607ff9eeb77a990cbcd4c`
- `morris_statistics.csv`: `2671c4246677338fb1a1c4a12e0c45d04416737d520ef709d8a4c6dc0e05efa3`

## 13. 下一阶段

Trust 参数敏感性主流程至此关闭。下一阶段转向 **Clarification diffusion / paid-reach robustness**，优先检验：

- `paid_edge_probability`；
- `paid_delivery_lag`；
- 其对 P4 reach、P1/P3 Trust 与 P5 repeat choice 的传导；
- 随后再进入 network size 与 topology robustness。
