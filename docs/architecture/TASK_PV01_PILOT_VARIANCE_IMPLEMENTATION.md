# TASK-PV01 Pilot variance 基础设施1.1

## 1. 状态与范围

实现状态：`24_BLOCK_DESIGN_IMPLEMENTED; DYNAMIC_FORMAL_N_IMPLEMENTED; PENDING_WINDOWS_TESTED_CLEAN_SHA; NO_VALID_PILOT_BLOCK; FORMAL_NOT_AUTHORIZED`

本工作包实现v3.3.1 Pilot的计划、真实执行门禁、中断恢复、seed/attempt ledger、方差分解、conservative planning SD和Holm operating-characteristic分析。它不生成Pilot结果，不调用provider，也不授权正式实验。科学规则以`FORMAL_EXPERIMENT_PROTOCOL.md`1.0.4和`task_pv01_pilot_variance_contract1.1.json`为准。

## 2. 零API入口

以下命令不构建router、不加载AgentKernel、不读取API key：

```powershell
python -X utf8 .\run_v33_pilot_variance.py --plan-only `
  --provider-call-ceiling 4800 `
  --max-wall-clock-hours 8

python -X utf8 .\run_v33_pilot_variance.py `
  --analyze-existing "results\v33_pilot_variance\<suite_id>"
```

`--analyze-existing`不再接受或需要`--n-max`。科学N由已完成Pilot的planning SD和冻结OC规则动态求得。

## 3. 真实执行与恢复门禁

新suite入口：

```powershell
python -X utf8 .\run_v33_pilot_variance.py `
  --execute-real-pilot `
  --allow-real-llm `
  --provider-call-ceiling 4800 `
  --max-wall-clock-hours 8 `
  --expected-git-head <windows_tested_clean_sha>
```

仅在技术中断后恢复同一suite：

```powershell
python -X utf8 .\run_v33_pilot_variance.py `
  --resume-real-pilot "results\v33_pilot_variance\<suite_id>" `
  --allow-real-llm `
  --provider-call-ceiling 4800 `
  --max-wall-clock-hours 8 `
  --expected-git-head <same_windows_tested_clean_sha>
```

两条真实入口都要求正确分支、clean worktree、准确HEAD、具体模型`qwen-plus-2025-12-01`和正的调用/时间cap。恢复只跳过已PASS blocks并重启经受控中断、具有最终时间checkpoint且状态为`RUNNING`的同seed block；provider calls和wall-clock跨会话累计。每次provider调用前先持久化累计计数。无法核验最终时间的强制杀进程、任何`FAIL*`或validity失败都不可恢复、不可replacement。

## 4. Pilot规模与方差规则

| Estimand | Pilot data | 方差分解 | planning SD |
|---|---|---|---|
| P1 | 6 simulation/network×4 requested-LLM/provider | balanced two-way MOM | 三规则最大值 |
| P2 | 同P1 | 同P1 | 同P1 |
| P5 | 6×4×24 offline demand | balanced three-way MOM | 同P1；D1的24个block用于block SD，全部replay用于component synthesis |

三规则为：

1. block SD的单侧90%卡方上置信界；
2. 最大leave-one-cognitive-block-out SD；
3. 非负method-of-moments方差分量合成值的平方根。

负分量保留在`raw_variance_component`，合成时截断为零并标记boundary。零planning variance记为`VARIANCE_ZERO_UNRESOLVED`，不借用旧研究方差、不注入噪声。576个P5 replay仅是条件性测量，独立Pilot n始终为24。

## 5. 动态正式N

OC只使用预设MDE、planning SD和相关结构，不使用Pilot mean/sign/ranking。每个候选N与相关场景使用相关正态样本均值和Wishart样本协方差构造三个联合t统计量，执行双侧Holm step-down：

- 从N=10逐整数向上搜索，无科研`N_max`；
- 四个相关场景：Pilot相关50%收缩、独立、等相关+.50、等相关−.25；
- P1/P2/P5各自single-MDE检出概率均须≥.90；
- global-null empirical FWER须≤`.05+2×MCSE`；
- 每场景至少200,000 replications；
- 各相关场景分别记录首个通过N；最终`N_required`为全部场景在同一候选N同时通过的最小值，避免Monte Carlo波动下把“各自曾经通过”误当作“同一N共同通过”。

输出新增`pilot_formal_n_selection.csv`。`scientifically_required_formal_n`只供协议1.1和资源评估使用，不等于正式执行授权。

## 6. 验证范围

`tests/test_task005_v331_pilot_variance.py`覆盖24×24 seed合同、零API plan、运行cap、跨恢复累计预算、replay计数、router不被猴子补丁替换、两向/三向方差分量、90% UCL＋LOO规则、零方差停止、Holm、四相关场景OC可复现性、模型版本隔离和机器合同一致性。
