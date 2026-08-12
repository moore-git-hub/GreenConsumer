# TASK_005 Stage I.5C-2 离线 Operating-Characteristic 校准设计 1.0

## 1. 目的与边界

本阶段只冻结离线 OC 校准设计，不执行真实 LLM，不开始 formal 数据收集，也不冻结 formal N。

父级冻结锚点为 `c1c29bcd21f18693d1d8a9fb2fde23f18a06e876`。

输入设计依据：

- Stage I.1C 原始分析契约；
- Stage I.5C-0 五 block 精度稳定性证据；
- Stage I.5C-1 分析范围修订。

P001–P005 仍全部属于 engineering pilot，只允许用于离线方差、相关结构与运行可行性校准，不能并入 future formal sample。

## 2. 修订后的确认性范围

确认性主要指标仅保留：

1. `final_trust_gain_vs_control`
2. `post_scandal_auc_gain_vs_control`

确认性估计量共 28 个：

- strategy-primary：8 strategy × 2 metric = 16；
- confirmatory factorial：6 contrast × 2 metric = 12。

`local_trust_effect_did_3` 已在 Stage I.5C-1 调整为探索性机制指标，不进入本次确认性样本量选择。

## 3. Holm family

保留 Stage I.1C 的“跨指标、按估计量类型组成 family”的结构，只删除 local-DID 对应成员：

- `strategy_primary_16`：16 个 strategy-primary estimand；
- `factorial_confirmatory_12`：12 个 confirmatory factorial estimand。

每个 family 独立采用 Holm，family alpha = 0.05，双侧检验。

不把两个 family 再合并为 28 项总 family，也不拆成 metric-specific families。

## 4. 被校准的正式检验规则

每个 estimand 采用：

- independent unit = replication block；
- two-sided one-sample Student-t test against 0；
- 95% Student-t mean CI；
- Holm-adjusted p-value；
- effect size 与 CI 优先于 p-value 解释。

OC 校准必须模拟这套规则，而不是另造一种正式检验方法。

## 5. 五 block 残差生成器

从 Stage I.5C-0 的 P001–P005 × 28 estimand 矩阵构造校准基础。

步骤固定为：

1. 对每个 estimand 在 P001–P005 上减去五 block 均值；
2. 得到 5 个 28 维 centered residual vectors；
3. 每个 synthetic block 以“完整 28 维 residual vector”为单位有放回抽样；
4. 每个抽中的完整 block residual vector 再乘以一个独立 Rademacher 符号 `+1/-1`；
5. 同一个符号必须作用于该 synthetic block 的全部 28 个坐标；
6. 最后乘方差压力倍数 `1.0 / 1.5 / 2.0`。

禁止逐 estimand 独立重采样，因为那会破坏工程 pilot 中的跨估计量相关结构。

Observed engineering mean 和 observed effect direction 都不得作为 synthetic truth。

## 6. Effect scenarios

### 6.1 Global null

全部 28 个确认性 estimand 的真实均值为 0。

用途：

- family-wise error；
- 95% CI coverage。

这是 hard-gate scenario。

### 6.2 Single-signal d = 0.50

一次只激活一个 estimand，其真实绝对效应固定为该 estimand **full-five-block sample SD 的 0.50 倍**；其余确认性 estimand 全部为 0。

28 个 estimand 轮流成为唯一 active signal。

仅作为 descriptive moderate-power sensitivity，不作为 formal N 的 hard gate。

### 6.3 Single-signal d = 0.80

同样一次只激活一个 estimand，但真实绝对效应为该 estimand full-five-block sample SD 的 0.80 倍。

28 个 estimand 轮流激活。

方向统一取正只是约定；由于正式检验是双侧，该约定不使用 engineering pilot 的观察方向。

在 variance multiplier = 1.0 下，该情景是 power hard gate。

### 6.4 Dense d = 0.50

28 个确认性 estimand 同时取各自 baseline SD 的 `+0.50` 倍。

仅报告 family discovery sensitivity，不用于选择 formal N。

## 7. Candidate N

仅评估：

`12 / 16 / 20 / 24 / 30 / 40`

禁止插值出 18、22、25 等未冻结候选。

也禁止重新把 precision-only 的 N=4 或 local-DID 的 N=105 直接当作 formal N。

## 8. Monte Carlo 规模

Primary calibration 使用两个独立、确定性 stream：

- Stream A seed = `202608071`
- Stream B seed = `202608072`
- 每个 scenario × variance multiplier × candidate N × stream：20,000 iterations。

所有二项比例同时报告 Wilson 95% Monte Carlo interval。

不得根据第一次校准结果临时增加 iteration 数来“修正”临界结果。

Leave-one-engineering-block-out sensitivity：

- 共 5 个 LOO residual libraries；
- 每 cell 5,000 iterations；
- 只作为 pilot-uncertainty sensitivity，不是自动 hard gate。

## 9. Hard gates

一个 candidate N 只有在 **两个 primary stream 都通过**以下条件时才算通过。

### 9.1 Null FWER

对 `strategy_primary_16` 与 `factorial_confirmatory_12` 分别计算 global-null family FWER。

在 `1.0x / 1.5x / 2.0x` 下均要求：

- FWER point estimate ≤ 0.055；
- Wilson 95% upper bound ≤ 0.060。

### 9.2 95% CI coverage

在 `1.0x / 1.5x / 2.0x` 下：

- 28 estimand 平均 coverage ≥ 0.945；
- 最差单 estimand coverage ≥ 0.930。

### 9.3 Single-signal d=0.80 Holm power

仅在 baseline `1.0x` variance 下作为 hard gate。

28 个 estimand 轮流成为唯一 active signal，要求：

- 最低 Holm-adjusted active-estimand rejection probability ≥ 0.800；
- 对应最差项 Wilson 95% lower bound ≥ 0.780。

`1.5x / 2.0x` 下的 power 必须报告，但不作为自动 hard gate，因为这些场景故意让固定绝对 signal 的 standardized effect 下降。

### 9.4 Monte Carlo stream stability

两个 primary stream 在候选 N 上的关键摘要差异不得超过：

- family FWER：0.015；
- mean coverage：0.015；
- minimum single-signal d=0.80 power：0.020。

## 10. Sample-size selection rule

从 `12 / 16 / 20 / 24 / 30 / 40` 中选择 **通过全部 hard gates 的最小 N**。

若两个 stream 对“最小通过 N”不同：

- 取两者中较大的候选 N；
- 但该 N 的 combined hard-gate summary 仍必须通过；
- 否则不选择 N。

运营上：

- preferred ceiling = 30；
- absolute candidate ceiling = 40。

若最小通过 N = 40，不自动冻结 formal N，必须再做一次明确的成本/时间可行性决策。

若所有候选都失败，则 formal target N 保持未冻结，formal launch 继续禁止，不允许通过放宽结果解释临时越过门禁。

OC calibration 的输出本身也不自动冻结 formal N。

## 11. 不允许决定 N 的输出

以下内容不得参与 candidate N 选择：

- exploratory local DID；
- Pareto membership；
- strategy rank；
- bootstrap top-1 probability；
- engineering pilot observed direction；
- engineering pilot p-value。

## 12. 下一阶段

Stage I.5C-3：

- 先实现 OC runner；
- 先通过 synthetic fixture acceptance；
- 再运行完整离线 calibration；
- 禁止网络访问；
- 禁止真实 LLM；
- 输入 evidence 必须 immutable；
- 输出目录必须拒绝覆盖；
- 必须支持 deterministic replay。

另外，当前 `replication_analysis.py` 仍编码修订前的 3 primary metrics、`strategy_primary_24` 和 `factorial_confirmatory_18`。在 future formal inference 前必须单独实现并审查 scope update；当前禁止直接拿它做修订后的 formal inference。
