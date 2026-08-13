# TASK_005 v3.3.1 Trust 参数敏感性 Stage B：Morris Elementary Effects 计划

**状态：pre-specified before execution**  
**日期：2026-08-13**  
**正式推断：否（global screening / engineering robustness）**

## 1. 进入 Stage B 的理由

Stage A 已完成 18 个预先规定的 local/boundary profiles，并满足：

- 54/54 implementation invariants PASS；
- P1/P2/P3/P4/P5/S1 在 Stage-A envelope 内无方向翻转；
- P1/P5 对 repair retention、empathy repair weight、event adjustment 较敏感；
- P2 对 empathy repair weight 尤其敏感；
- P3 对 event adjustment 尤其敏感；
- P4 对 Trust 参数严格不敏感。

Stage A 仍属于 OAT / structured-boundary screening，不能识别多参数同时变化下的非线性与交互。因此 Stage B 使用 Morris elementary-effects method 在七维参数空间中进行全局 screening。

## 2. 方法依据

Morris (1991) 提出 elementary-effects screening，用较低模型评估成本识别复杂计算模型中的重要输入因素。对于每个输入，沿随机轨迹多次计算单步 elementary effect。

本研究报告：

- `mu`：有方向 elementary effects 的均值；
- `mu_star`：elementary effects 绝对值的均值，用于衡量总体影响强度；
- `sigma`：elementary effects 的标准差，用于识别非线性和/或参数交互迹象。

`mu_star` 的使用遵循 Campolongo, Cariboni & Saltelli (2007) 对 Morris screening 的改进思想。`sigma` 较大不能单独区分“非线性”和“交互”，论文中只能表述为二者至少之一的迹象。

Stage B 是 global screening，不是参数 calibration，也不是 variance decomposition。若需要一阶/总效应方差贡献，应在后续对筛出的关键参数另行实施 variance-based analysis。

## 3. 参数空间

Stage B 使用与 Stage A 完全相同的 engineering robustness bounds，不因 Stage A 输出重新调整区间：

| 参数 | Lower | Upper |
|---|---:|---:|
| `crisis_retention` | 0.96 | 0.99 |
| `repair_retention` | 0.94 | 0.98 |
| `event_adjustment` | 0.60 | 1.00 |
| `quiet_adjustment` | 0.10 | 0.30 |
| `repair_saturation` | 0.00 | 0.60 |
| `hypocrisy_weight` | 0.00 | 0.50 |
| `empathy_repair_weight` | 0.25 | 0.75 |

这些 bounds 是 engineering robustness envelopes，不是经验分布、先验分布或真实消费者参数置信区间。

## 4. Morris 设计

预先固定：

- 参数维度 `k = 7`；
- grid levels `p = 6`；
- normalized step `Delta = p / [2(p-1)] = 0.6`；
- trajectories `r = 10`；
- 每条 trajectory 包含 `k+1 = 8` 个点；
- 每个参数在每条 trajectory 中恰好改变一次；
- 每个参数因此获得 10 个 elementary effects；
- design seed 固定为 `2026081801`。

理论上共需要 80 个 trajectory-point evaluations。若不同 trajectories 产生完全相同的七维参数点，程序只运行一次模型并复用确定性 Fake 输出；复用只降低计算冗余，不改变 elementary-effect design。

Stage B 不采用“运行完后删除不理想轨迹”或“继续增加轨迹直到排序满意”的 optional design expansion。若未来需要提高 Morris ranking precision，必须另建版本化 Decision Record，并以预先规定的新 trajectory count 整体重跑。

## 5. 参数归一化与实际值映射

Morris trajectory 在 `[0,1]^7` 中生成。对参数 j：

`theta_j = lower_j + x_j * (upper_j - lower_j)`。

Elementary effect 按 normalized input 计算：

`EE_j = [Y(x + Delta e_j) - Y(x)] / Delta`

或负向 step 的对应有符号形式。

使用 normalized input 的目的，是让不同物理尺度参数的 `mu_star` 在同一个 estimand 内可比较。

## 6. 固定不变的模型部分

每一个 Morris evaluation 均固定：

- Fake LLM / deterministic semantic fixture；
- T35 primary horizon；
- 20 cognitive Agents；
- 25 micro-buyers / Agent；
- BA baseline topology；
- K=3；
- paid edge probability=0.55；
- paid delivery lag=1；
- simulation seed=2026081501；
- LLM seed=2026081601；
- demand seed=2026081701；
- 2×2×2 + common control；
- persona、刺激文本、conversion-support design。

唯一变化为七维 Trust parameter vector。

## 7. 主要分析输出

对 P1/P2/P3/P5 报告 Morris：

- `mu`；
- `mu_star`；
- `sigma`；
- `sigma / mu_star`（只作为描述性辅助比率，不设机械分类阈值）；
- `rank_mu_star`。

同时保留 P4 与 S1 作为 mechanism-separation diagnostics：

- P4 理论上应得到 `mu_star = 0`；
- S1 应相对低敏感，若出现较大 Trust-parameter Morris effect，需要检查 demand-channel separation。

## 8. 实现不变量 / falsification checks

### 8.1 Morris design validity

每条 trajectory 必须：

- 有 8 个点；
- 七个参数各改变一次；
- normalized step 的绝对值严格为 0.6；
- 所有 normalized coordinates 位于 `[0,1]`；
- 所有实际参数位于预先规定 bounds。

### 8.2 Pre-crisis invariance

所有 unique evaluations 的 T1–T4 key cognitive states 必须完全一致。Trust sensitivity 不应改变危机前、无事件时的基线状态。

### 8.3 Network invariance

所有 evaluations 的 network hash 必须一致。

### 8.4 P4 invariance

所有 evaluations 的 P4 direct enterprise reach 必须相同；其 Morris elementary effects 应为 0。

### 8.5 Provenance

非 baseline parameter vectors 必须在 run summary 中标记为 `explicit-sensitivity-profile`，完整 Trust parameters 必须持久化。

任一硬不变量失败，Stage B 总体状态为 FAIL，并停止科学解释。

## 9. 结果解释规则

### 9.1 `mu_star`

同一个 estimand 内，较大的 `mu_star` 表示该参数在本轮 global screening 范围内具有更强的平均绝对影响。

不得跨不同单位的 estimands 直接比较 `mu_star` 数值。

### 9.2 `mu`

`mu` 保留平均方向信息。如果 `mu_star` 大但 `mu` 接近 0，通常表示不同轨迹中 elementary effects 方向存在抵消。

### 9.3 `sigma`

较大的 `sigma` 表示 elementary effects 随参数空间位置明显变化，可由非线性、参数交互或两者共同造成。Morris screening 本身不能区分二者。

### 9.4 不允许调 baseline

无论 Morris ranking 如何，当前 frozen baseline 不因 Stage B 结果改变。Stage B 的作用是识别边界条件、决定后续重点 robustness / variance-based analysis，而不是寻找最有利的参数组合。

## 10. 论文可直接采用的表述

> 在局部与结构边界敏感性分析基础上，本研究进一步采用 Morris elementary-effects 方法对信任动态中的七项工程参数实施全局筛查。各参数首先映射至预先规定的标准化区间，在六水平网格上生成十条随机轨迹，每条轨迹依次改变全部七个参数，并据此计算 elementary effects。研究使用 elementary effects 绝对值均值 `mu*` 衡量总体影响强度，以均值 `mu` 表示平均方向，并以标准差 `sigma` 判断模型响应是否存在明显非线性和/或参数交互迹象。该分析用于机制稳健性与因素筛查，不用于参数估计或模型校准。

## 11. 禁止表述

- `mu_star` 是参数对现实消费者行为的因果效应；
- `sigma` 可以唯一证明参数交互；
- Morris ranking 等同于 variance-based Sobol total-effect ranking；
- Fake LLM Morris screening 证明 Real LLM 外部有效性；
- 根据 Morris 排名重新调 baseline 以提高显著性。

## 12. 文献

1. Morris, M. D. (1991). Factorial Sampling Plans for Preliminary Computational Experiments. *Technometrics*, 33(2), 161–174. DOI: 10.1080/00401706.1991.10484804.
2. Campolongo, F., Cariboni, J., & Saltelli, A. (2007). An effective screening design for sensitivity analysis of large models. *Environmental Modelling & Software*, 22(10), 1509–1518. DOI: 10.1016/j.envsoft.2006.10.004.
3. Saltelli, A., Annoni, P., Azzini, I., Campolongo, F., Ratto, M., & Tarantola, S. (2010). Variance based sensitivity analysis of model output. Design and estimator for the total sensitivity index. *Computer Physics Communications*, 181(2), 259–270. DOI: 10.1016/j.cpc.2009.09.018.
