# TASK_005 v3.3.1 Clarification Diffusion / Paid-Reach 敏感性计划

**状态：pre-specified before execution**  
**日期：2026-08-13**  
**正式推断：否（engineering robustness）**

## 1. 研究目的

Trust 参数敏感性 Stage A 与 Morris Stage B 已完成。下一阶段检验企业澄清的**付费一跳触达机制**是否依赖单一工程设定，重点考察：

- `paid_edge_probability`：paid seed 沿实际有向网络边成功触达 successor 的概率；
- `paid_delivery_lag`：一跳 paid amplification 相对 t0 的投放时滞。

这两个参数直接对应“Hub / Random channel”处理如何转化为企业 direct reach，并可能进一步影响 Trust 与 repeated brand choice。

## 2. 为什么此阶段优先于继续做 Trust Sobol

本研究核心问题包含传播渠道与网络机制。Trust 参数已通过：

- 18-profile local / structured-boundary sensitivity；
- 80-point Morris global screening；
- 主要 estimand 在预设 Trust envelope 中无方向翻转；
- P4 对 Trust 参数严格不敏感。

因此，下一阶段优先验证传播结构参数，比继续细分 Trust 参数方差贡献更直接对应研究问题。

## 3. 参数性质

当前 baseline：

- `paid_edge_probability = 0.55`；
- `paid_delivery_lag = 1` Tick。

两者均为 development engineering assumptions，不是经验估计值。敏感性分析不将它们解释为现实广告平台的已知到达率或经验时延。

## 4. 预先规定的参数网格

采用完整 `3 × 3` factorial engineering grid：

### Paid edge probability

- Low = `0.30`；
- Baseline = `0.55`；
- High = `0.80`。

### Delivery lag

- Same-Tick = `0`；
- Baseline next-Tick = `1`；
- Two-Tick delay = `2`。

共 9 个 diffusion profiles：

`p ∈ {0.30, 0.55, 0.80} × lag ∈ {0,1,2}`。

该范围是 engineering robustness envelope，不是置信区间。不得根据结果重新定义 baseline 或删除不利组合。

## 5. 固定不变的模型部分

所有 profiles 固定：

- Fake LLM deterministic semantic fixture；
- T35 primary horizon；
- 20 cognitive Agents；
- 25 micro-buyers / Agent；
- BA baseline topology；
- K=3 paid seeds；
- public organic exposure mechanism 不变；
- Trust baseline 参数全部固定；
- simulation seed=`2026081501`；
- LLM seed=`2026081601`；
- demand seed=`2026081701`；
- 2×2×2 + common control；
- persona、刺激文本、conversion support design 全部不变。

唯一变化为 `paid_edge_probability` 与 `paid_delivery_lag`。

## 6. 主要输出

### P4：Hub − Random enterprise direct reach

这是最直接的结构输出。预期：

- 对 `paid_edge_probability` 敏感；
- 在相同 `paid_edge_probability` 下，对 `paid_delivery_lag` 的**最终企业 direct reach**应保持一致，因为 lag 只改变送达时间，不改变已选中的 amplified recipient 集合。

### P3：Immediate − Delayed early Trust

P3 对送达时点可能敏感，因为 T6–T9 是有限早期窗口。lag 增加可能缩短 Immediate treatment 在 early window 内实际作用时间。

### P1 / P5

用于检验结构性 reach 改变是否向 Trust repair 与 repeated choice 传导。

### P2

内容差异不是此阶段主目标，但保留以检测 channel/reach 与 content mechanism 的潜在耦合。

## 7. 实现不变量 / falsification checks

### 7.1 Control trajectory invariance

Control 不接收澄清，因此所有 9 个 diffusion profiles 中 Control 的 T1–T35 cognitive trajectory 必须完全一致。

### 7.2 Pre-treatment invariance

所有 profiles 在 T1–T5 的 treatment-condition key states 必须完全一致。paid reach 参数不能改变危机之前或危机事件本身。

### 7.3 Network invariance

所有 profiles network hash 必须一致。

### 7.4 Reach invariant to lag

对于相同 `paid_edge_probability` 与同一 treatment condition：

`eventual enterprise direct reach(lag=0) = reach(lag=1) = reach(lag=2)`。

若失败，优先判定为实现错误，因为 amplified recipient selection 不应依赖 delivery lag。

### 7.5 Reach monotonicity in edge probability

由于每条 paid edge 使用固定 deterministic draw，且成功条件为 `draw < p`，在相同 network/seed/channel 下：

`reach(p=0.30) <= reach(p=0.55) <= reach(p=0.80)`。

该单调性是实现层 falsification check，而不是经验规律。

### 7.6 Public/seed allocation invariance

K=3、public organic exposure nodes 与 paid seed identities 必须在 probability/lag profiles 中保持不变；只有 successful paid one-hop recipient 集合允许随 `p` 改变。

## 8. 分析策略

本阶段只做工程/结构敏感性：

- 不计算 p-values；
- 不计算现实总体置信区间；
- 不进行 winner selection；
- 不据结果修改 baseline 0.55 / lag=1；
- 报告每个 profile 的 P1/P2/P3/P4/P5/S1；
- 报告 condition-level direct/eventual enterprise reach；
- 以 3×3 heatmap / profile lines 展示参数响应。

## 9. 解释规则

若 P4 随 p 明显变化，这是预期结构敏感性；应报告 Hub advantage 的量级依赖 paid amplification strength。

若 P4 在相同 p 下随 lag 改变，则应先检查代码，因为定义中的 eventual reach 只取 recipient union，不应受配送时点影响。

若 P1/P5 对 p 或 lag 变化明显，则说明网络触达工程设定可以向下游心理/行为输出传导，应在论文中作为 network-mechanism boundary condition 报告。

若 P3 对 lag 高敏感，则说明“即时响应优势”不仅来自 crisis-response timing，还受 paid amplification 到达速度影响，后续正式实验解释应区分 enterprise response time 与 network delivery time。

## 10. 论文可采用的表述

> 为检验渠道效应是否依赖付费扩散机制的单一工程设定，本研究在保持网络、预算、消费者、信任参数与语义输入不变的条件下，对 paid edge delivery probability 与 one-hop delivery lag 进行二维敏感性分析。前者控制 paid seeds 沿实际有向网络边成功触达相邻节点的概率，后者控制成功一跳触达相对企业首次发布的配送时滞。该分析用于识别渠道优势的结构边界条件，不将所设概率或时延解释为现实平台的经验参数。

## 11. 禁止表述

- 0.30/0.55/0.80 是现实平台的经验置信区间；
- lag=1 是现实社交媒体的平均传播时间；
- Fake sensitivity 证明真实平台 Hub 投放一定优于 Random；
- 根据哪一组产生最大 Trust/Purchase 效应重新选择 baseline。

## 12. 下一阶段关系

该阶段完成后，再进入：

1. network size N=20/40/80；
2. fixed-K vs proportional-K；
3. BA / WS / community topology robustness；
4. 最后再处理 Real-LLM prompt/provider stochasticity 与正式 replication 设计。
