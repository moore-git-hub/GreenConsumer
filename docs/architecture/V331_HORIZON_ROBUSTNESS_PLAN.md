# TASK_005 v3.3.1 时间范围稳健性分析计划

**状态：pre-specified engineering robustness plan**  
**日期：2026-08-13**  
**正式推断：否**

## 1. 目的

本分析只回答一个问题：模型的描述性机制结论是否过度依赖仿真终止时点。

主终点已经预先冻结为 T35，即危机 T5 后 30 个仿真日。T30 和 T40 仅作为较短/较长观察窗口，不允许根据效应大小选择其中任意一个替换 T35。

## 2. 设计

三个运行使用完全相同的：

- Fake semantic router；
- simulation seed；
- requested LLM seed；
- demand seed；
- 20 cognitive Agents；
- 25 micro-buyers/Agent；
- BA baseline topology；
- treatment matrix；
- Trust/Reach/Demand mechanism parameters。

唯一变化为：

- T30；
- T35；
- T40。

由于 Fake router 与随机种子固定，这三个运行构成 nested finite-horizon engineering checks，而不是三个统计独立 replication blocks。

## 3. 第一层检查：prefix invariance

如果 horizon 是纯粹的“未来运行时长”，则把 T30 延长到 T35/T40 不应改变 T1–T30 的任何已经发生的认知状态。类似地，T35 与 T40 的 T1–T35 历史应完全一致。

自动检查：

- T30 vs T35：T1–T30 `cognitive_records.csv` exact equality；
- T30 vs T40：T1–T30 exact equality；
- T35 vs T40：T1–T35 exact equality。

任一失败均视为实现错误，而不是“敏感性结果”。这类失败提示未来 horizon 通过某种非预期路径反向影响了过去状态，必须先修代码再讨论科学结果。

## 4. 第二层检查：estimand horizon sensitivity

对每个 horizon 重新计算单 block descriptive estimands：

- P1：总体澄清 vs Control 的 post-crisis Trust；
- P2：Rational − Empathy 的 post-crisis Trust；
- P3：Immediate − Delayed 的 T6–T9 early Trust；
- P4：Hub − Random enterprise direct reach；
- P5：总体澄清 vs Control 的 expected repeat choice；
- S1：conversion support present − absent。

其中 P1/P2/P5 的积分/平均窗口随 endpoint 改为 `T6–T_end`；P3 与 P4 的定义不随总 horizon 改变。

## 5. 解释规则

不设置“哪个 horizon 效果最大就采用哪个”的选择机制。

分析重点是：

1. effect direction 是否稳定；
2. effect magnitude 随 horizon 的范围；
3. P2 等接近零的contrast是否容易发生符号变化；
4. 长期 Trust repair 是否使处理差异逐渐衰减；
5. repeat-choice cumulative effects 是否随观察窗口持续累积。

若某个结果出现 horizon-dependent sign reversal，应作为时间边界条件报告，而不是通过修改主 endpoint 消除。

## 6. 为什么先使用 Fake LLM

该阶段的目标是验证“时间范围”这一仿真实验设计，而不是重新检验LLM语义操控。使用 deterministic Fake router 可以：

- 将差异归因于 horizon；
- 进行 exact prefix-invariance 检查；
- 不消耗真实 API；
- 避免 temperature=0.3 的 provider stochasticity 混入时间范围诊断。

只有当 Fake horizon 检查通过后，才讨论是否有必要用少量 Real-LLM blocks 检验长期语义/UGC路径。

## 7. 自动输出

运行：

```powershell
python run_v33_horizon_sensitivity.py
```

生成：

```text
results/v33_horizon_sensitivity/horizon_YYYYMMDD_HHMMSS/
├── T30/<run>/...
├── T35/<run>/...
├── T40/<run>/...
├── prefix_invariance.csv
├── horizon_estimands.csv
├── horizon_stability.csv
├── horizon_summary.json
└── figures/
    ├── P1_....png
    ├── P2_....png
    └── P5_....png
```

## 8. 论文表述边界

可以写：

> 为检验主要结果是否依赖仿真终止时点，研究在保持模型机制、网络、处理和随机种子不变的条件下，将总观察窗口分别设为 T30、T35 与 T40。T35 为预先设定的主终点，T30 与 T40 仅用于时间范围稳健性检验。

不能写：

- “三个 horizon 是三个独立样本”；
- “选择效应最大的 horizon 作为正式结果”；
- “Fake horizon stability 证明 Real LLM 外部有效性”；
- “曲线走平意味着现实消费者已经恢复信任”。
