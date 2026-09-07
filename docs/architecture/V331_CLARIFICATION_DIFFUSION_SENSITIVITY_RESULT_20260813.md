# TASK_005 v3.3.1 Clarification Diffusion / Paid-Reach 敏感性结果

**日期：2026-08-13**  
**来源运行：`clarification_20260813_151145`**  
**状态：PASS（Fake-LLM engineering robustness）**  
**正式推断：否；参数校准：否；外部效度证明：否**

## 1. 设计与实现验证

本轮严格沿用预先登记的 `3 × 3` 网格：

- `paid_edge_probability ∈ {0.30, 0.55, 0.80}`；
- `paid_delivery_lag ∈ {0, 1, 2}`；
- baseline=`p=.55, lag=1`；
- Fake LLM、T35、20 cognitive Agents、25 micro-buyers/Agent、BA baseline topology、K=3、Trust baseline 参数、三个随机种子、处理矩阵、persona 与刺激文本均固定。

共运行 9 个 diffusion profiles。`clarification_sensitivity_invariants.csv` 中 84/84 checks PASS：

- network hash invariance：9/9；
- target-node allocation invariance：9/9；
- common-control trajectory invariance：9/9；
- pre-treatment T1–T5 invariance：9/9；
- eventual enterprise reach lag-invariance：24/24；
- eventual enterprise reach monotonicity in `p`：24/24。

因此，参数注入没有污染网络拓扑、目标节点分配、Control trajectory 或处理前历史；在固定 `p` 时，lag 只改变到达时点而没有改变最终 enterprise recipient set；在固定 lag 时，单个 channel-condition 的 eventual direct enterprise reach 随 `p` 非递减。

## 2. 主要 estimands：完整 3×3 结果

### P1：Overall clarification − Control post-crisis Trust

| paid edge p | lag=0 | lag=1 | lag=2 |
|---:|---:|---:|---:|
| .30 | 0.256534 | 0.240490 | 0.236914 |
| .55 | 0.271090 | **0.250271** | 0.247291 |
| .80 | 0.314867 | 0.279614 | 0.282550 |

全网格均为正。总体上，提高 paid-edge delivery probability 会增强信任修复；same-Tick paid delivery 通常产生更大的 P1。需要注意，`p=.80` 时 lag=2 略高于 lag=1，因此不能声称 long-horizon P1 对 lag 存在严格单调关系。该小幅非单调可以由后续 UGC、Trust memory 与静默恢复路径共同作用，属于动态系统结果，而不是 eventual reach 差异，因为同一 `p` 下 eventual recipient set 已验证完全一致。

### P2：Rational − Empathy post-crisis Trust

| paid edge p | lag=0 | lag=1 | lag=2 |
|---:|---:|---:|---:|
| .30 | -0.074674 | -0.076179 | -0.073138 |
| .55 | -0.077957 | **-0.079291** | -0.076243 |
| .80 | -0.087789 | -0.088627 | -0.085671 |

9/9 profiles 均保持负向。因此，在当前 deterministic Fake semantic fixture 与冻结 Trust 结构下，Rational−Empathy contrast 的方向不依赖单一 `p=.55/lag=1` 设定。但该方向仍不能推广为现实消费者中的内容策略优劣；Real-LLM semantic/prompt robustness 仍需独立验证。

### P3：Immediate − Delayed early Trust（T6–T9）

| paid edge p | lag=0 | lag=1 | lag=2 |
|---:|---:|---:|---:|
| .30 | 0.284575 | 0.239134 | 0.200130 |
| .55 | 0.306851 | **0.249996** | 0.206881 |
| .80 | 0.375334 | 0.282581 | 0.227132 |

P3 在 9/9 profiles 中均为正，并呈现非常清晰的结构：

- 在相同 `p` 下，lag 越短，Immediate−Delayed early Trust contrast 越大；
- 在相同 lag 下，更高 `p` 通常扩大 early timing contrast。

这与 P3 的理论窗口 T6–T9 一致：企业一跳放大越快，越多消费者在延迟策略尚未启动前已经接收到即时澄清。因此这一结果主要支持“delivery speed 是 early timing mechanism 的边界条件”，而不是现实时间最优值的经验估计。

### P4：Hub − Random eventual direct enterprise reach

| paid edge p | lag=0 | lag=1 | lag=2 |
|---:|---:|---:|---:|
| .30 | 0.40 | 0.40 | 0.40 |
| .55 | **0.45** | **0.45** | **0.45** |
| .80 | 0.40 | 0.40 | 0.40 |

P4 在所有 9 个 profiles 中都保持正向，但不是随 `p` 单调增加。这里不是 reach monotonicity 失败，而是因为 P4 是两个均随 `p` 变化的 channel reach 之差。

实际 eventual direct enterprise reach 为：

| p | Hub | Random | Hub−Random |
|---:|---:|---:|---:|
| .30 | .75 | .35 | .40 |
| .55 | .80 | .35 | .45 |
| .80 | .85 | .45 | .40 |

因此，Hub 与 Random 自身都满足 recipient-set nesting / reach monotonicity；在 `p=.80` 时 Random 也新增了 recipient，导致 contrast 从 .45 回到 .40。

该离散跳跃同时暴露出 N=20 网络的有限分辨率：一个 Agent 即对应 0.05 reach。故下一阶段必须检验网络 realization / topology / network size，而不能把 .40/.45 当作真实市场中的精确渠道优势。

### P5：Overall clarification − Control expected repeat choice

| paid edge p | lag=0 | lag=1 | lag=2 |
|---:|---:|---:|---:|
| .30 | 0.017390 | 0.015954 | 0.015001 |
| .55 | 0.019050 | **0.017007** | 0.015977 |
| .80 | 0.024089 | 0.020588 | 0.020268 |

9/9 profiles 均为正。Paid delivery probability 和较短 delivery lag 的影响不仅停留在 reach 层，也通过 Trust / psychological-state updates 传递到了 downstream expected repeated brand choice。Baseline +1.70 percentage points 不是唯一能产生正向 P5 的参数点。

### S1：Conversion support present − absent

S1 在整个网格中只从约 0.02817 变化至 0.02836，远小于 P1/P3/P5 对 reach 参数的变化。这符合 conversion-support 作为独立 PBC/demand channel 的模型设计：改变危机澄清 paid reach 不应大幅改变 conversion-support 自身的附加效应。

## 3. 主要科学结论

本轮支持以下模型内部结论：

1. **Hub direct-reach advantage 不依赖单一 `p=.55` 设定。** P4 在 `.30/.55/.80` 下均为正；但其精确幅度对有限网络中的离散 recipient changes 敏感。
2. **Paid reach speed 对 early timing mechanism 很重要。** P3 对 lag 呈稳定梯度，same-Tick amplification 的即时策略优势最大。
3. **Reach probability 会向下游行为传导。** P1 与 P5 在较高 `p` 下总体增大，说明传播结构参数不仅改变“看见了多少人”，也改变之后的 Trust 与 expected repeat choice。
4. **Long-horizon Trust 不必对 lag 严格单调。** 同一 eventual recipient set 在不同到达时点可通过后续 UGC 与记忆路径产生小幅非单调差异，因此“最终reach相同”不等于“动态心理结果相同”。
5. **当前 P4 的离散性强化了网络稳健性需求。** N=20 时一个节点就是5个百分点，下一步应优先检验网络 realization 与 topology，再讨论扩大 cognitive-Agent N。

## 4. 不能据此声称

- `p=.55` 是现实平台中经过校准的最佳 paid delivery probability；
- `lag=0` 是现实企业一定应该采用的最优响应延迟；
- Hub 比 Random 在真实社交平台上固定高 40–45 个百分点；
- Fake-LLM 结果证明现实消费者中 Empathy 一定优于 Rational；
- 9个 profiles 是9个现实统计独立样本或可用于总体 p-value。

## 5. 原始证据文件身份

用户提供并核验的本轮原始汇总文件：

- `clarification_sensitivity_estimands.csv` — SHA-256 `a0437667fba2b6cec76c559c2f15f156a365d37ff2809b2404833d8dd8624e67`；
- `clarification_sensitivity_invariants.csv` — SHA-256 `4ec19bdd7b89bfc8c844d6027c976e81ab45d767e9a9c6e65a563c1ac2ab8c73`；
- `clarification_sensitivity_profiles.csv` — SHA-256 `75dc4fbfd5922d3276bf3ab9e7e69d2fa65e3c81c3981a2946fb9956c26823fa`；
- `clarification_sensitivity_reach.csv` — SHA-256 `71c79dcb1f560cd964d8d8a45e6ef75b021bb7779795be9e0629d233ba118377`。

## 6. 下一阶段

由于本轮已经说明 paid reach 参数本身不是单点脆弱性，下一步不再继续细调 `p/lag`。优先进入 **network topology robustness at fixed N=20**：保持同一20个Persona、K=3、p=.55、lag=1、Trust参数和Fake semantics，只改变受控网络拓扑，比较 BA / Watts–Strogatz / community-block network 下的 P4、P1、P3、P5 与网络结构指标。

Network-size N=20/40/80 将作为后续单独阶段，因为扩大 cognitive-Agent N 涉及 Persona population construction，不应与 topology change 同时修改。