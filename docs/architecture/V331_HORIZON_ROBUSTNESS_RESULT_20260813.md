# TASK_005 v3.3.1 时间范围稳健性工程结果记录（2026-08-13）

**Run suite:** `horizon_20260813_104033`  
**性质:** Fake-LLM finite-horizon engineering robustness  
**正式推断:** 否  
**主终点选择:** T35 仍为预先冻结的 primary endpoint；T30/T40 只作为 boundary-condition checks。

## 1. 输入条件

三个运行仅改变总仿真时长：

- T30；
- T35；
- T40。

共同保持：

- simulation seed = `2026081501`；
- requested LLM seed = `2026081601`；
- demand seed = `2026081701`；
- Fake LLM；
- 20 cognitive Agents；
- 25 micro-buyers / cognitive Agent；
- v3.3.1 Trust / Reach / Renewal mechanism；
- 同一实验矩阵与网络生成设计。

## 2. 运行结果

三个 horizon 均完成完整 9-condition analysis：

| Horizon | Analysis window | Status |
|---|---|---|
| T30 | T6–T30 | PASS |
| T35 | T6–T35 | PASS |
| T40 | T6–T40 | PASS |

所有 analysis 均明确：

- `formal_inference_performed = false`；
- `p_values_computed = false`；
- `confidence_intervals_computed = false`；
- `formal_reuse_permitted = false`；
- `external_validity_claimed = false`。

## 3. Prefix invariance

自动检查结果：

`prefix_invariance_failures = 0`

因此：

- T30 与 T35 的共同历史没有出现 horizon-induced backward contamination；
- T30 与 T40 的共同历史没有出现 horizon-induced backward contamination；
- T35 与 T40 的共同历史没有出现 horizon-induced backward contamination。

该结果支持一个软件实现层面的强不变量：在随机种子与机制不变时，延长未来运行时间没有改变已经发生的过去认知轨迹。

注意：这是 implementation verification，不是现实外部有效性证明。

## 4. 当前可以得出的结论

可以确认：

1. T30/T35/T40 三个预设 finite horizons 均能完整运行；
2. cognitive → demand → analysis 的时间范围传递链已经工作；
3. horizon extension 不会反向改变既有认知历史；
4. T35 可以继续作为 pre-specified primary endpoint。

仅依据当前 `horizon_summary.json` **尚不能判断** P1/P2/P5 的效应方向和幅度在 T30/T35/T40 是否稳定，因为该 summary 不包含 `horizon_stability.csv` 的具体 estimand values。效应层面的 horizon robustness 应基于：

- `horizon_estimands.csv`；
- `horizon_stability.csv`；
- P1/P2/P5 horizon figures。

若任何 contrast 出现 sign reversal，应报告为时间边界条件，而不是改变 T35 主终点。

## 5. 工程日志尾部 HTTP close 信息

运行结束后出现的 `httpcore.connection close.started / close.complete` 为第三方 HTTP client 生命周期日志；在 suite 已返回 `status = PASS`、三个 analysis 均 PASS 且 `prefix_invariance_failures = 0` 的情况下，不构成模型失败证据。

## 6. 下一阶段

按预登记顺序进入 `Trust parameter sensitivity Stage A`：

- 仅使用 Fake LLM；
- T35 固定；
- baseline + 14 OAT profiles + 3 structured boundary profiles；
- 不进行参数校准；
- 不允许根据结果重新选择 baseline；
- 必须通过 pre-crisis、network hash 与 P4 direct-reach invariants。

详细设计见：

`docs/architecture/V331_TRUST_PARAMETER_SENSITIVITY_PLAN.md`
