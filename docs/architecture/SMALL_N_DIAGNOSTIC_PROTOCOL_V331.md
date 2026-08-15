# v3.3.1 N=10小样本诊断与敏感性协议

## 1. 协议身份

| 字段 | 冻结值 |
|---|---|
| 状态 | `FROZEN_PRE_PILOT; DIAGNOSTIC_ONLY; PRIMARY_ANALYSIS_UNCHANGED` |
| 冻结日期 | `2026-08-15` |
| 适用对象 | 协议1.1正式N被接受为10时的P1、P2、P5 block-level分析 |
| 不适用对象 | Pilot均值检验、P3/P4确认性检验、Agent或micro-buyer推断 |
| 主分析 | 双侧one-sample t-test versus 0；P1/P2/P5采用Holm step-down |
| 正式执行状态 | `PILOT_NOT_EXECUTED; FORMAL_NOT_AUTHORIZED` |

本协议在查看v3.3.1 Pilot和正式结果前固定N=10下的分布、异常block、leave-one-block-out和exact sign-flip报告规则。它不把N=10改写为已经充分的正式样本量，也不改变`FORMAL_EXPERIMENT_PROTOCOL.md`中的主分析。只有Pilot的保守operating-characteristic规则通过，协议1.1才可接受正式N=10；否则本协议不会被用于“挽救”不可行设计。

## 2. 设计原则

1. **不进行结果驱动的方法切换。** 主分析不根据正态性检验、异常值标记、p值或效应方向切换为其他检验。
2. **诊断用于披露脆弱性，不用于删除数据。** 完整且通过validity gate的block不得因数值极端而排除。
3. **所有block值可见。** P1、P2、P5各自报告10个原始block-level contrasts。
4. **主分析与敏感性family分开。** t-test/Holm是唯一确认性决策；exact sign-flip/Holm是预设敏感性结论。
5. **不把小样本非拒绝解释为零效应。** 不实施未预设的等效或非劣效推断。

## 3. 主分析保持不变

对estimand $k\in\{P1,P2,P5\}$的10个有效block值$x_{ik}$，计算：

$$\bar{x}_k=\frac{1}{N}\sum_{i=1}^{N}x_{ik},\qquad
t_k=\frac{\bar{x}_k}{s_k/\sqrt{N}},\qquad N=10.$$

采用双侧one-sample t-test versus 0，报告mean、SD、SE、95%普通t区间、raw p和Holm-adjusted p。Holm程序用于三项确认性family并控制family-wise alpha=.05（Holm，1979，《A Simple Sequentially Rejective Multiple Test Procedure》）。

Shapiro–Wilk或其他小样本正态性检验不作为主分析门禁：在N=10时“不拒绝正态”不能证明分布适合t检验，而“拒绝正态”也不能触发事后更换主方法。若计算该统计量，只能放入诊断附表，不参与决策。

## 4. 全部block分布与影响披露

每个确认性estimand必须生成：

- 全部10个block值的点图、零线、均值和95%普通CI；
- Q-Q图；
- mean、SD、median、IQR、min、max；
- 每个block的leave-one-block-out均值与主分析结果；
- median/MAD稳健距离作为影响提示。

稳健距离定义为：

$$r_i=\frac{|x_i-\operatorname{median}(x)|}{1.4826\times MAD}.$$

当$MAD>0$且$r_i>3.5$时标记`INFLUENTIAL_VALUE_FLAG`；当$MAD=0$时，所有偏离median的值均单独列出并标记`MAD_ZERO_NONMEDIAN_FLAG`。标记只触发文字披露和溯源检查，不触发删除。只有独立于结果数值的validity gate失败才可以使block不准入。

## 5. Leave-one-block-out脆弱性分析

对每个$j=1,\ldots,10$，同时删除第$j$个block在P1、P2、P5上的整行，使用剩余9个blocks重复三项t-test和Holm校正。不得分别为不同estimand删除不同block。

每项报告：

- 10个LOBO均值的最小值和最大值；
- 10个LOBO均值中与全样本均值符号相同的数量；
- 10个LOBO Holm decisions中与全样本decision相同的数量；
- 导致符号翻转或Holm decision变化的block IDs；
- 全样本均值是否主要由单一block驱动。

LOBO的N=9结果是脆弱性诊断，不是新的正式样本，也不允许把其中最有利的一次作为报告结果。正式N=10若缺少有效block，必须按正式协议处理，不能用LOBO结果替代。

## 6. Exact sign-flip敏感性分析

### 6.1 计算规则

对每项estimand的观察统计量$T_{obs}=|\bar{x}|$，枚举全部$2^{10}=1024$种符号向量$s\in\{-1,+1\}^{10}$，计算：

$$T_s=\left|\frac{1}{10}\sum_{i=1}^{10}s_i x_i\right|.$$

双侧exact p值定义为满足$T_s\ge T_{obs}$的符号向量比例。由于完整枚举，不添加Monte Carlo伪计数。浮点比较采用分析合同中冻结的绝对容差，并同时保存枚举计数、总排列数和软件版本。

置换方法通过在零假设下允许的数据变换构造参考分布；其精确性依赖相应不变性/可交换性条件（Ernst，2004，《Permutation Methods: A Basis for Exact Inference》）。本研究的sign-flip敏感性具体依赖block contrasts在零假设下关于零的符号可交换/对称条件。该条件不能由N=10数据充分验证，因此本方法只作为并列敏感性，不能被描述为无条件优于t-test。

### 6.2 多重校正与报告

P1、P2、P5的三个exact p值另行组成一个敏感性family，并采用同一Holm step-down。不得把t-test raw p与sign-flip p混在同一个Holm排序中。报告：exact raw p、exact Holm p、敏感性decision及其与主分析decision是否一致。

## 7. 证据标签

证据标签只描述统计稳定性，不替代估计值和边界说明。

| 标签 | 预设判定 |
|---|---|
| `PRIMARY_AND_SENSITIVITY_CONCORDANT` | 主分析Holm拒绝；exact sign-flip Holm同样拒绝且方向一致；10次LOBO均值均保持方向；10次LOBO Holm decision均保持拒绝 |
| `PRIMARY_SUPPORTED_BUT_DIAGNOSTICALLY_FRAGILE` | 主分析Holm拒绝，但exact sign-flip不一致、LOBO发生符号翻转或任一LOBO Holm decision不再拒绝 |
| `PRIMARY_NOT_REJECTED` | 主分析Holm不拒绝；无论敏感性结果如何均不得升级为确认性支持 |

如主分析不拒绝而sign-flip敏感性拒绝，仍使用`PRIMARY_NOT_REJECTED`并报告`SENSITIVITY_DISCORDANT`。如主分析拒绝而敏感性脆弱，论文必须保留“diagnostically fragile”表述，不得选择性省略。

## 8. 设计阈值与统计结论分离

对每项estimand另行报告$|\bar{x}|$是否达到预设设计阈值。该分类不进入p值或Holm计算，也不改变证据标签：

- `AT_OR_ABOVE_PRESET_DESIGN_THRESHOLD`；
- `BELOW_PRESET_DESIGN_THRESHOLD`。

在缺少现实管理依据时不得将前者改写为“具有管理意义”。置信区间跨越阈值、零值或两者时，必须如实披露；本研究没有预设最小效应检验，因此不能由区间推出等效性。

## 9. 禁止的事后处置

正式结果生成后禁止：

- 因Q-Q图、Shapiro p值或个别block改变主检验；
- 删除极端但有效的block；
- 在ordinary t、Welch、Wilcoxon、bootstrap、trimmed mean或sign-flip之间挑选最有利结果；
- 将bootstrap区间当作N=10下的“稳健救援”；若未来预先增加bootstrap，只能作为描述性附录且须在正式执行前修订协议；
- 将P3/P4或单元格比较临时纳入确认性family；
- 用LOBO中最有利的N=9结果替代N=10主分析；
- 把未拒绝零假设写成无效或等效。

## 10. 实现与审计门槛

在协议1.1发布前，正式分析代码必须通过至少以下零结果测试：

1. exact sign-flip在N=10时枚举数固定为1024；
2. 手工小样本fixture可复算exact p值；
3. Holm在主family和敏感性family中分别计算；
4. LOBO固定生成10个三estimand联合删除结果；
5. 行顺序改变不影响结果；
6. 无效、缺失、重复block ID导致硬失败；
7. 所有block值、flag和decision写入机器可读表；
8. 输出记录execution SHA、analysis SHA、protocol version和输入hash。

本协议当前只冻结规则，不授权实现产生Pilot或正式观察，也不授权任何provider call。
