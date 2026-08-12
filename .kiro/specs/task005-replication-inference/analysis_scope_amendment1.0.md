# TASK_005 Stage I.5C-1 分析范围修订 1.0

## 1. 修订时点与依据

本修订发生在任何 formal 数据收集之前。P001–P005 均属于 engineering pilot，不计入 formal 样本。

修订依据仅包括：

- engineering pilot 的方差；
- 预设精度目标下的样本量可行性；
- 真实运行时间与工程可行性。

本修订不使用效应方向、策略排名、p 值或显著性结果作为依据。

Stage I.5C-0 的五 block 诊断显示：

- `final_trust_gain_vs_control`：精度诊断 N=4；
- `post_scandal_auc_gain_vs_control`：精度诊断 N=3；
- `local_trust_effect_did_3`：精度诊断 N=105。

其中 local DID 是唯一把总体精度诊断规模推高到不可接受水平的指标。该结果只用于研究设计可行性判断，不作为策略效果推断。

## 2. 指标地位修订

### 2.1 确认性主要指标

继续保留：

1. `final_trust_gain_vs_control`
2. `post_scandal_auc_gain_vs_control`

每个指标保留 8 个 strategy-primary estimands 与 6 个 confirmatory factorial estimands。

修订后确认性范围共：

- 16 个 strategy estimands；
- 12 个 factorial estimands；
- 合计 28 个 confirmatory estimands。

### 2.2 探索性机制指标

`local_trust_effect_did_3` 调整为探索性机制指标。

仍保留：

- 8 个 strategy estimands；
- 6 个 factorial estimands；
- block-level 分布；
- 点估计与置信区间；
- 敏感性诊断；
- 明确标注为 exploratory 的机制解释。

但它：

- 不进入确认性 Holm family；
- 不用于决定 formal N；
- 不允许形成确认性显著性声明；
- 不允许用确认性 p 值支持主要研究结论。

## 3. Engineering pilot 与 formal 样本隔离

P001、P002、P003、P004、P005 全部排除在 formal 样本之外。

这些 block 只可用于方差估计、工程可行性和离线 operating-characteristic calibration。不得与后续 formal block 合并形成最终确认性检验样本。

## 4. Formal N 门禁

当前不冻结 formal N。

下一阶段只考察以下候选有效 block 数：

`12 / 16 / 20 / 24 / 30 / 40`

禁止直接采用 N=4；也禁止直接把五-block precision diagnostic 的 N=105 当作 formal N。

候选 N 的最终选择必须经过离线 operating-characteristic calibration。校准设计必须在运行前先冻结，至少包括：

- 数据生成场景；
- 方差压力场景；
- multiplicity family；
- Holm 程序；
- Monte Carlo 次数；
- coverage 判据；
- FWER 判据；
- power 判据；
- 稳定性判据；
- 从候选集合选择 N 的确定规则。

## 5. 当前门禁

- formal target N：未冻结；
- formal LLM launch：禁止；
- formal data collection：尚未开始；
- 下一阶段：Stage I.5C-2，仅冻结离线 OC calibration 设计；
- Stage I.5C-2 不允许真实 LLM 调用。
