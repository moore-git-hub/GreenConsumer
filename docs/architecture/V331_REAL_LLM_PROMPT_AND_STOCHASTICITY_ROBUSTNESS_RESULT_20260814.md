# TASK_005 v3.3.1 Real-LLM Prompt and Practical-Stochasticity Robustness — Result Record

**Date:** 2026-08-14  
**Run:** `llmrob_20260814_230111`  
**Status:** engineering PASS  
**Inference:** descriptive engineering robustness only; no p-values, confidence intervals, or population inference

## 1. Verified execution facts

The pre-specified selected Real-LLM robustness suite completed all five unique blocks:

```text
baseline_r1
compact_r1
schema_first_r1
baseline_r2
baseline_r3
```

The suite retained the frozen settings:

- model: `qwen-plus`;
- temperature: `0.3`;
- requested LLM seed: `2026081601`;
- simulation seed: `2026081501`;
- demand seed: `2026081701`;
- horizon: `T35`;
- baseline prompt profile: `baseline_exact`.

The user-run summary reports:

- `status = PASS`;
- `profiles_run = 5`;
- `provider_calls_total = 743`;
- `invariant_failures = 0`;
- `prompt_sign_unstable_estimands = 0`;
- `baseline_repeat_sign_unstable_estimands = 0`;
- `baseline_repeats = 3`;
- `p_values_computed = false`;
- `confidence_intervals_computed = false`;
- `formal_inference_performed = false`;
- `prompt_selection_permitted = false`.

The process exited normally with exit code 0.

## 2. Prompt-layout robustness

The prompt-layout comparison used the three pre-specified profiles:

```text
baseline_exact
compact_separator
schema_first
```

The suite summary reports zero sign-unstable estimands across the prompt-profile comparison. Because the suite PASS criterion also requires zero implementation invariant failures, the result supports a bounded statement that the observed estimand directions were not reversed by these two pre-specified layout/order perturbations under the frozen Real-LLM configuration.

This is **limited prompt-layout robustness**, not evidence that arbitrary prompt wording is irrelevant. The experiment deliberately preserved lexical content and changed only separator/layout/order structure.

## 3. Practical provider/runtime stochasticity

The exact frozen baseline prompt was run three times:

```text
baseline_r1
baseline_r2
baseline_r3
```

All three retained the same requested model seed, model, temperature, simulation seed, demand seed, treatments, network baseline, and horizon. The suite summary reports zero sign-unstable estimands across these three baseline repeats.

This supports direction-level robustness to the observed practical provider/runtime non-determinism in these three engineering repeats. It does **not** establish statistical reproducibility, because three repeats are descriptive only and the requested provider seed is not treated as a guarantee of deterministic output.

## 4. Implementation integrity

The suite ended with:

```text
invariant_failures = 0
status = PASS
```

Under the pre-specified implementation, the invariant layer checks include run PASS status, zero semantic fallback events, zero common-history replay misses, frozen Real-LLM settings, preservation of the whitespace-insensitive lexical multiset, and the required prompt-transform role for baseline versus non-baseline profiles.

Therefore this run is treated as a valid engineering robustness execution rather than an implementation-failure case.

## 5. Generated evidence archive

The suite directory is:

```text
results/v33_llm_robustness/llmrob_20260814_230111
```

The implementation writes the following principal suite-level evidence tables:

- `llm_robustness_profiles.csv`;
- `llm_robustness_estimands.csv`;
- `llm_robustness_semantics.csv`;
- `prompt_transform_audit.csv`;
- `prompt_profile_stability.csv`;
- `baseline_stochasticity.csv`;
- `llm_robustness_invariants.csv`.

Eight descriptive figures were generated for prompt-layout and baseline-repeat robustness of P1, P2, P3, and P5.

## 6. Scientific interpretation boundary

Allowed interpretation:

> 在固定qwen-plus、temperature=0.3、请求seed、仿真seed、需求seed、T35、处理矩阵及主体机制的条件下，三个预设prompt版式以及三次完全相同基准prompt运行均未导致已报告estimand方向翻转；因此模型结论在本次受控prompt版式扰动和实际provider/runtime随机性范围内表现出有限的方向稳健性。

Not allowed:

- “三次重复证明LLM输出具有统计稳定性”；
- “requested seed保证LLM完全可重复”；
- “prompt对结果没有影响”；
- “选择表现最好的prompt作为最终模型”；
- “Real-LLM robustness证明真实消费者外部效度”；
- 将该工程suite的5个blocks当作正式population inference样本。

## 7. Frozen decision

The scientific baseline remains `baseline_exact`; no prompt profile, temperature, seed, Trust parameter, network setting, or demand parameter is selected or modified based on the observed outcomes.

The completed Real-LLM robustness stage closes the currently pre-specified LLM-specific engineering robustness step. The next methodological task should be separately pre-registered before execution, with priority on pilot variance estimation and formal replication-block planning rather than further outcome-driven prompt or mechanism tuning.
