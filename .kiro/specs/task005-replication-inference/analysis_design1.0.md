# TASK_005 Stage I.1C：复制分析与统计推断契约 v1.0

状态：候选冻结基线。该阶段只冻结设计与机器可读契约，不实现 `replication_analysis.py`，不运行正式统计推断，不启动新的真实 LLM block。

设计输入锚点：

- Git HEAD：`1447fea7e7669e6828a5e21b0c49fb07f38310bb`
- Stage H.2 证据 ZIP SHA256：`0E8D0D8C8D627FFA1DEB409538C5ECD2927821CDBBAC43352A0B5A3FE07D3F6F`
- Stage I.1B 输入 ZIP SHA256：`78EEDD31B0B84F41870D0B002C1AB898DBAF98F5E963AD97165FFF868BBC3435`
- Stage I.0 缺失值契约：`I0-NA-01`

## 1. 推断单位与数据资格

主要推断的独立单位是完整的 `replication block`。

以下对象不得作为独立样本：

- Agent；
- Tick；
- 单次 LLM 调用；
- 同一 block 内的 8 个策略条件；
- 同一 block 内的网络节点或社群。

一个 block 只有同时满足以下条件，才进入正式分析：

1. `replicate_manifest.csv` 中最终状态为 `succeeded`；
2. 只使用该 block 的最终成功 attempt；
3. `validation_passed=True`；
4. `condition_success_count=9`；
5. `batch_exit_code=0`；
6. `run_completed=True`；
7. 1 个 Control 和 8 个策略条件全部存在；
8. 以 `exp_id` 连接条件，不依赖 CSV 行序；
9. 三个主指标在全部策略行中为有限数值；
10. Control 行仅允许 `local_trust_effect_did_3` 为空。

任何条件缺失、重复、非有限或身份不一致时，整个 block 退出主要分析。禁止保留该 block 的部分策略行形成不平衡样本，禁止插补。

中断、失败和无效 attempt 必须保留在审计历史中，但不得进入效果估计。

## 2. Pilot、smoke 与 formal 的边界

- `task005-real-smoke-v2` 仅为工程重复运行参照，不并入任何 pilot 或 formal 样本。
- `task005-real-pilot-v1` 是工程 pilot，不并入 formal 样本。
- formal 必须使用新的 `replication_id`、新的预注册 `master_seed` 和独立 seed ledger。
- 当前 3-block pilot 只用于工程波动和样本量可行性诊断，不产生显著性、稳定排名或策略优劣结论。

## 3. 主指标与方向

三个主指标均定义为“越大越好”：

1. `final_trust_gain_vs_control`
2. `post_scandal_auc_gain_vs_control`
3. `local_trust_effect_did_3`

Control 条件固定为：

```text
NoClarification-Control
```

Control 的 `local_trust_effect_did_3` 是结构性“不适用”，必须为空；Control 不进入策略效果估计。

## 4. 策略级估计对象

对 8 个策略条件和 3 个主指标分别估计跨 block 平均效果，共 24 个策略级 estimand：

```text
theta(strategy, metric)
    = E_block[metric(strategy, block)]
```

由于三个主指标已按同 block Control 构造，策略级数值本身就是 block 内配对效果。不得再次把策略行和 Control 行当作两个独立样本。

每个 estimand 必须报告：

- `n_planned_blocks`
- `n_attempted_blocks`
- `n_valid_blocks`
- `n_failed_blocks`
- `mean`
- `sample_sd`
- `standard_error`
- `ci_level`
- `ci_low`
- `ci_high`
- `median`
- `q1`
- `q3`
- `iqr`
- `min`
- `max`
- `raw_p_value`
- `holm_p_value`
- `multiplicity_family`
- `estimand_status`

主要区间为跨 block 均值的双侧 95% Student-t 置信区间：

```text
mean ± t_(0.975, n-1) × sample_sd / sqrt(n)
```

双侧 one-sample t 检验仅作为补充，零假设为平均 block 效果等于 0。区间估计和效果大小优先于显著性标签。

退化情况：

- 全部值恰为 0：均值、区间均为 0，原始 p 值为 1；
- 方差为 0 且均值非 0：区间退化为该均值，原始 p 值为 0，并标记 `degenerate_nonzero`;
- `n_valid_blocks < 2`：只报告可用描述值，不计算 SD、SE、CI 或 p 值，状态为 `insufficient_n`；
- formal 模式下若 `n_valid_blocks < preregistered_target_valid_blocks`，状态必须为 `formal_incomplete`，不得输出正式结论。

## 5. 2×2×2 因子 contrast

策略矩阵采用固定 effect coding：

| 因子 | `+1` 水平 | `-1` 水平 |
| --- | --- | --- |
| Content | Empathy | Rational |
| Channel | Hub | Random |
| Timing | Immediate | Delayed |

对每个 block、每个主指标，先计算 7 个 factorial effects：

- `Content`
- `Channel`
- `Timing`
- `Content_x_Channel`
- `Content_x_Timing`
- `Channel_x_Timing`
- `Content_x_Channel_x_Timing`

对任一 contrast：

```text
effect(block)
    = sum(sign(condition) × metric(condition, block)) / 4
```

其中 `sign(condition)` 是对应 effect-code 乘积。该缩放使主效应等于 `+1` 水平平均值减去 `-1` 水平平均值，二阶和三阶效应是同一尺度上的差中之差。

必须先在每个 block 内计算 contrast，再跨 block 汇总。禁止把 8 个策略行直接作为相互独立的回归样本。

前 6 个 contrast（3 个主效应和 3 个二阶交互）为 confirmatory factorial family；三阶交互固定为 exploratory。

## 6. 多重检验

显著性水平固定为双侧 `alpha=0.05`。

Holm step-down 校正分为两个预注册 family：

1. `strategy_primary_24`：8 个策略 × 3 个主指标，共 24 个策略级零假设；
2. `factorial_confirmatory_18`：6 个 confirmatory factorial effects × 3 个主指标，共 18 个零假设。

三阶交互的 3 个检验必须报告原始 p 值和 `exploratory` 标签，可另外报告一个 `factorial_three_way_3` Holm 校正结果，但不得作为 confirmatory 结论。

禁止：

- 按观察到的结果临时拆分或合并 family；
- 用未校正 p 值形成正式显著性结论；
- 仅凭 `p < 0.05` 替代效应大小、区间和机制解释；
- 以排名结果决定需要检验的策略。

## 7. Pareto 与排名稳定性

### 7.1 正式 Pareto

对每个策略计算三个主指标的跨 block 均值。所有指标均按“越大越好”处理。

策略 A 支配策略 B，当且仅当：

- A 在三个指标上均不低于 B；
- A 至少在一个指标上严格高于 B。

浮点比较容差固定为 `1e-12`。不被任何其他策略支配的策略属于正式 Pareto 集。

Pareto 集是主要多目标结论；不得强制从 Pareto 集中选出唯一“最优策略”。

### 7.2 block bootstrap

bootstrap 必须以完整 block 为重采样单位。每次抽取 block 后，必须同时保留该 block 的 8×3 效果向量，禁止逐策略或逐指标独立重采样。

固定参数：

```text
bootstrap_iterations = 20000
bootstrap_ci_level = 0.95
bootstrap_seed_namespace = task005|replication-analysis|rank-bootstrap|v1.0
```

每次 bootstrap 计算：

- 8 个策略的三指标均值；
- Pareto 集；
- 等权综合得分；
- 平均秩与并列第一信用。

等权得分的归一化规则：

1. 在当次 bootstrap 样本中，按指标对 8 个策略均值进行 min-max 归一化；
2. 若某指标的 8 个策略均值极差不超过 `1e-12`，该指标对全部策略统一记为 `0.5`；
3. 三个指标归一化值取算术平均；
4. 得分越高，排名越前；
5. 并列策略采用平均秩；
6. 并列第一时，`top1_credit=1/k`。

正式排名稳定性输出：

- `pareto_probability`
- `top1_probability`
- `mean_rank`
- `median_rank`
- `rank_interval_low`
- `rank_interval_high`
- `top1_credit_sum`
- `bootstrap_iterations`

`rank_interval` 使用 bootstrap rank 的 2.5% 和 97.5% 分位数。等权排名是次要综合诊断，不能覆盖 Pareto 结果。

TASK_004 单次 run 的 66 组权重敏感性结果只作为补充诊断，不进入正式 top1 概率定义。

## 8. 样本量规划与 formal 启动门

正式 block 数在 Stage I.5 单独冻结。本设计冻结算法和启动门，但不从当前 3-block pilot 直接宣称最终 N。

对每个主指标，候选精度半宽沿用 Phase 0 的标准方案：

| 主指标 | 候选 95% CI 半宽 |
| --- | ---: |
| `final_trust_gain_vs_control` | 0.020 |
| `post_scandal_auc_gain_vs_control` | 0.300 |
| `local_trust_effect_did_3` | 0.015 |

Stage I.5 的 `s_j` 必须取该指标全部 confirmatory estimand 中的最大 pilot sample SD，至少覆盖：

- 8 个策略级 estimand；
- 6 个 confirmatory factorial contrast。

对每个指标，寻找满足以下条件的最小整数 `n_j`：

```text
t_(0.975, n_j-1) × s_j / sqrt(n_j) <= h_j
```

然后：

```text
N_target = max(n_j)
```

Stage I.5 还必须冻结：

- `N_min`
- `N_max`
- `target_valid_blocks`
- `max_attempted_blocks`
- `formal_replication_id`
- `formal_master_seed`
- replacement seed-index 规则
- 预算与最长运行时间
- pilot SD 来源和输入 SHA256

若计算得到的 `N_target > N_max`，不得静默截断为 `N_max`。必须在启动前选择并记录以下一种处理：

1. 增加预算和 `N_max`；
2. 放宽预注册精度半宽；
3. 将相应指标降为探索性；
4. 不启动 formal。

当前 3-block pilot 尚不满足最终 N 冻结条件，原因包括：

- pilot 仅有 3 个独立 block；
- 当前输入没有完整 block-level factorial contrast SD；
- `local_trust_effect_did_3` 已表现出显著工程波动；
- 同 seed 重复运行存在符号变化。

因此，在 Stage I.5 通过前，formal real-LLM batch 保持禁止启动。

## 9. 失败、替换与停止规则

formal 必须预注册目标有效 block 数和最大尝试 block 数。

- 运行只因工程状态继续或停止，不得依据效果、p 值、CI、Pareto 或排名停止；
- 失败或中断 block 不进入效果估计；
- 需要替换时，只能使用 seed ledger 中下一个尚未使用的 replicate index；
- 不得复用失败 block 的最终分析身份伪装成新独立 block；
- 达到目标有效 block 数后停止；
- 达到最大尝试数仍不足目标时，formal 状态为 `incomplete`，仅允许描述性报告；
- 必须同时报告 planned、attempted、valid、failed、invalid 和 interrupted 数量。

## 10. 分析输出契约

正式 `replication_analysis.py` 至少输出：

| 文件 | 行单位 | 主键 |
| --- | --- | --- |
| `replicate_runs.csv` | block × condition | `replicate_id + exp_id` |
| `paired_effects.csv` | block × strategy | `replicate_id + exp_id` |
| `factorial_contrasts.csv` | block × metric × contrast | `replicate_id + metric + contrast_name` |
| `strategy_estimates.csv` | strategy × metric | `exp_id + metric` |
| `factorial_estimates.csv` | metric × contrast | `metric + contrast_name` |
| `formal_pareto.csv` | strategy | `exp_id` |
| `ranking_bootstrap.csv` | strategy | `exp_id` |
| `analysis_metadata.json` | batch | `formal_replication_id` |
| `analysis_validation.json` | batch | `formal_replication_id` |

`analysis_metadata.json` 必须记录：

- analysis schema/version；
- Git commit；
- formal replication ID；
- formal preregistration SHA256；
-输入 manifest、seed ledger 和每个最终 summary 的 SHA256；
- 主指标、factor coding、alpha、CI 方法；
- Holm family；
- bootstrap 次数和 seed；
- planned、attempted、valid、failed、invalid、interrupted block 数；
- pilot/smoke 排除声明；
- 是否达到 formal 启动与完成门；
- Python 和关键统计依赖版本；
- 生成时间。

所有 CSV 和 JSON 写入必须采用临时文件加原子替换。不得更新 `results/experiments/latest`。

## 11. 生产 API 候选契约

后续实现至少提供：

```python
load_valid_replication_blocks(batch_root, preregistration)
build_replicate_runs(valid_blocks)
build_paired_effects(replicate_runs)
compute_factorial_contrasts(paired_effects)
aggregate_strategy_estimands(paired_effects, analysis_config)
aggregate_factorial_estimands(factorial_contrasts, analysis_config)
holm_adjust(p_values)
compute_formal_pareto(strategy_estimates, tolerance=1e-12)
bootstrap_rank_stability(paired_effects, analysis_config)
plan_precision_sample_size(pilot_effects, sample_size_config)
run_replication_analysis(batch_root, output_dir, preregistration)
```

所有公共函数必须验证类型、重复主键、缺失值、有限值、block 完整性和配置版本，并采用 fail-closed 行为。

## 12. 测试基线要求

Stage I.2 必须先冻结合成 fixture 和独立验收脚本，再实现生产模块。测试至少覆盖：

1. block 是唯一重采样与推断单位；
2. 只选择最终成功 attempt；
3. 任何部分 block 被拒绝；
4. Control 的 local DID 仅允许结构性空值；
5. 策略任一主指标空值或非有限值被拒绝；
6. 以 `exp_id` 配对，行序变化不影响结果；
7. 7 个 2×2×2 contrast 的符号与缩放；
8. 24 和 18 两个 Holm family；
9. t CI、退化方差和 `n<2`；
10. Pareto 支配、并列和浮点容差；
11. block bootstrap 不拆散 8×3 向量；
12. bootstrap 固定 seed 可复现；
13. 并列第一信用和平均秩；
14. formal 未达到目标 block 数时禁止正式结论；
15. pilot 和 smoke 不得混入 formal；
16. 输出 schema、主键、排序和原子写入；
17. 分析过程不调用网络、不调用真实 LLM、不修改运行结果和 latest。

## 13. 非目标

Stage I.1C 不执行：

- `replication_analysis.py` 生产实现；
- 正式样本量最终数值冻结；
- 新的真实 LLM pilot 或 formal block；
- 对当前 3-block pilot 的显著性检验；
- 当前策略的正式排名或优劣结论；
- 结果驱动的指标、family、权重或停止规则调整。

## 14. 方法依据

- 配对结构以同一 block 内的差值或 contrast 为分析对象；
- Student-t 区间和 one-sample t 检验用于跨独立 block 的平均配对效果；
- Holm step-down 用于预注册 family 的 FWER 控制；
- bootstrap 以完整 block 为重采样单位，用于非线性 Pareto 与排名稳定性统计量。

参考：

- Holm, S. (1979). A Simple Sequentially Rejective Multiple Test Procedure. *Scandinavian Journal of Statistics*, 6(2), 65–70.
- Efron, B., & Tibshirani, R. (1985). The Bootstrap Method for Assessing Statistical Accuracy. *Behaviormetrika*, 12, 1–35.
- DiCiccio, T. J., & Tibshirani, R. (1987). Bootstrap Confidence Intervals and Bootstrap Approximations. *Journal of the American Statistical Association*, 82(397), 163–170.
