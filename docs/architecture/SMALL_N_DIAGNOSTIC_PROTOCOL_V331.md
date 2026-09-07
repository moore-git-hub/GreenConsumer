# v3.3.1 正式N诊断与敏感性协议

## 1. 协议身份

| 字段 | 冻结值 |
|---|---|
| 状态 | `REVISED_PRE_PILOT_FOR_DYNAMIC_N; DIAGNOSTIC_ONLY; PRIMARY_ANALYSIS_UNCHANGED` |
| 初次冻结 | 2026-08-15，原N=10版本 |
| 动态N修订 | 2026-08-16，在有效Pilot observation前 |
| 适用对象 | 协议1.1冻结`N_required`后的P1、P2、P5 block-level分析 |
| 主分析 | 双侧one-sample t-test versus 0；P1/P2/P5采用Holm step-down |
| 正式执行状态 | `PILOT_NOT_EXECUTED; FORMAL_NOT_AUTHORIZED` |

本协议不决定正式N，也不改变主分析。只有P001–P024完成并按预设OC计算`N_required`后，协议1.1才可冻结具体N。本协议不能用于挽救功效不足或资源不可行的设计。

## 2. 设计原则

1. 主分析不根据正态性检验、异常值标记、p值或效应方向切换方法。
2. 完整且通过validity gate的block不得因数值极端而排除。
3. P1、P2、P5各自披露全部$N=N_{required}$个block-level contrasts。
4. t-test/Holm是唯一确认性decision；sign-flip/Holm是独立敏感性family。
5. 不把非拒绝解释为零效应、等效或非劣效。

## 3. 主分析

对estimand $k\in\{P1,P2,P5\}$的$N$个有效block值$x_{ik}$计算：

$$\bar{x}_k=\frac{1}{N}\sum_{i=1}^{N}x_{ik},\qquad
t_k=\frac{\bar{x}_k}{s_k/\sqrt{N}},\qquad N=N_{required}.$$

采用双侧one-sample t-test versus 0，报告mean、SD、SE、95%普通边际t区间、raw p和Holm-adjusted p。Holm用于三项确认性family并控制family-wise alpha=.05（Holm，1979，《A Simple Sequentially Rejective Multiple Test Procedure》）。

Shapiro–Wilk或其他正态性检验不作为主分析门禁：“不拒绝正态”不能证明分布适合t检验，“拒绝正态”也不能触发事后更换主方法。

## 4. 全block披露和影响提示

每项必须生成全部$N$个block值的点图、零线、均值与95%普通CI、Q-Q图，以及mean、SD、median、IQR、min和max。每个block计算leave-one-block-out均值和median/MAD稳健距离：

$$r_i=\frac{|x_i-\operatorname{median}(x)|}{1.4826\times MAD}.$$

当$MAD>0$且$r_i>3.5$时标记`INFLUENTIAL_VALUE_FLAG`；当$MAD=0$时，所有偏离median的值标记`MAD_ZERO_NONMEDIAN_FLAG`。标记只触发披露和溯源检查，不触发删除。

## 5. 联合leave-one-block-out

对每个$j=1,\ldots,N$，同时删除第$j$个block在P1、P2、P5上的整行，用剩余$N-1$个blocks重复三项t-test和Holm。不得按estimand选择不同删除对象。

每项报告$N$个LOBO均值范围、与全样本均值同方向次数、与全样本Holm decision相同次数，以及导致符号或decision变化的block IDs。LOBO是脆弱性诊断，不是替代正式样本。

## 6. Sign-flip敏感性

观察统计量为$T_{obs}=|\bar{x}|$，对符号向量$s\in\{-1,+1\}^{N}$计算：

$$T_s=\left|\frac{1}{N}\sum_{i=1}^{N}s_i x_i\right|.$$

- 当$N\le20$时枚举全部$2^N$种符号组合，报告exact p；
- 当$N>20$时使用固定种子`2026081901`和1,000,000次符号向量Monte Carlo抽样，以$(b+1)/(R+1)$计算p，并报告MCSE；此时必须称`Monte Carlo sign-flip p`，不得称exact p。

P1/P2/P5的三个sign-flip p值另行组成敏感性family并执行Holm，不得与主分析raw p混合排序。sign-flip的有效性依赖block contrasts在零假设下关于零的符号可交换/对称条件（Ernst，2004，《Permutation Methods: A Basis for Exact Inference》）；该条件不能由有限样本充分验证，因此它不是无条件优于t-test的替代方法。

## 7. 证据标签

| 标签 | 预设判定 |
|---|---|
| `PRIMARY_AND_SENSITIVITY_CONCORDANT` | 主分析Holm拒绝；sign-flip Holm同样拒绝且方向一致；全部LOBO保持方向与拒绝decision |
| `PRIMARY_SUPPORTED_BUT_DIAGNOSTICALLY_FRAGILE` | 主分析Holm拒绝，但sign-flip不一致、LOBO符号翻转或任一LOBO不再拒绝 |
| `PRIMARY_NOT_REJECTED` | 主分析Holm不拒绝；敏感性不得将其升级为确认性支持 |

每项还单独报告$|\bar{x}|$是否达到预设设计阈值，但阈值分类不进入p值、Holm或证据标签，也不得在缺少现实依据时称为“管理意义”。

## 8. 禁止的事后处置

- 因Q-Q图、Shapiro p值或个别block改变主检验；
- 删除极端但有效的block；
- 在t、Wilcoxon、bootstrap、trimmed mean或sign-flip间挑选最有利结果；
- 临时把P3/P4或单元格比较纳入确认性family；
- 用最有利的$N-1$ LOBO结果替代正式N主分析；
- 把未拒绝写成无效或等效。

## 9. 实现门槛

协议1.1发布前，正式分析代码必须验证：$N\le20$时枚举数为$2^N$；$N>20$时固定1,000,000次和指定种子；主family与敏感性family分别Holm；LOBO固定生成$N$个联合删除结果；行顺序不影响输出；无效、缺失或重复block ID硬失败；所有值、flag、decision、SHA和输入hash落盘。

本协议不授权任何provider call、Pilot或正式执行。
