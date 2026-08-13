# TASK_005 v3.3.1 Real-LLM Prompt and Practical-Stochasticity Robustness Plan

**Status:** pre-specified before execution  
**Date:** 2026-08-13  
**Scope:** selected Real-LLM engineering robustness; not formal inference

## 1. Trigger

The main Fake-LLM structural robustness chain has covered horizon, Trust parameters, clarification diffusion, topology, edge orientation, network size / paid-seed allocation, and downstream micro-buyer numerical resolution. The remaining central uncertainty is specific to the semantic appraisal layer: whether model conclusions are excessively sensitive to prompt layout or to practical provider/runtime non-determinism.

Prior engineering evidence already showed that nominally identical Real-LLM runs can produce different semantic outputs even when a requested seed is supplied. Therefore requested seed must not be treated as a guarantee of deterministic provider output.

## 2. Frozen baseline

All selected Real-LLM blocks retain:

- model: `qwen-plus`;
- temperature: `0.3`;
- requested LLM seed: `2026081601`;
- simulation seed: `2026081501`;
- demand seed: `2026081701`;
- T35 finite horizon;
- 20 cognitive Agents;
- 25 micro-buyers / cognitive Agent;
- frozen BA baseline topology and K=3;
- clarification `p=.55`, `lag=1`;
- frozen Trust v3.3 parameters;
- 2×2×2 communication matrix + common control;
- control-first common-history replay within each block.

No prompt profile or repeated run may be selected as a replacement baseline based on favorable outcomes.

## 3. Prompt-layout robustness profiles

The frozen scientific prompt remains `baseline_exact`. Two pre-specified robustness profiles change only static layout/order while preserving the same lexical content (whitespace-insensitive token multiset):

1. `baseline_exact`: current v3.3.1 prompt, byte-for-byte unchanged;
2. `compact_separator`: removes only the blank separator between context and instruction/schema blocks;
3. `schema_first`: moves the unchanged instruction/schema block before the unchanged context block.

The profiles do **not** change persona text, memories, observed information, schema field names, peer-only approval rule, or the prohibition on LLM purchase/brand-choice/posting decisions.

A dedicated prompt-transform audit records original/transformed hashes and verifies lexical-multiset preservation for every provider prompt.

## 4. Practical stochasticity design

Three independent full Real-LLM blocks use the exact same `baseline_exact` prompt and the exact same requested model/simulation/demand seeds:

```text
baseline_r1
baseline_r2
baseline_r3
```

Because the nominal settings are identical, any between-run variation is interpreted as **practical provider/runtime stochasticity or non-determinism**, not as statistical sampling from a real consumer population.

The first baseline block also serves as the anchor for the three-profile prompt comparison, so the complete suite contains five unique blocks:

```text
baseline_r1
compact_r1
schema_first_r1
baseline_r2
baseline_r3
```

## 5. Outcomes

The suite reports the existing descriptive estimands without changing their definitions:

- P1 overall clarification → post-crisis Trust;
- P2 Rational − Empathy post-crisis Trust;
- P3 Immediate − Delayed early Trust;
- P4 Hub − Random direct enterprise reach;
- P5 overall clarification → expected repeat choice;
- S1 conversion-support effect.

It also records clarification-exposure semantic means for credibility, evidence strength, perceived empathy, valence, arousal and topic relevance.

## 6. Hard implementation checks

Every block must satisfy:

- run status PASS;
- zero semantic fallback events;
- zero common-history replay misses;
- Real-LLM path at temperature .3 and T35;
- baseline prompt provider calls unchanged by the transform wrapper;
- non-baseline prompt profiles transformed on every provider call;
- whitespace-insensitive lexical multiset preserved for every transformed prompt.

Failure of these checks is an implementation failure, not a substantive robustness result.

## 7. Interpretation rules

### Prompt-layout robustness

The three prompt profiles are compared descriptively. If P1/P2/P3/P5 retain direction and semantic manipulation retains the intended Rational→evidence / Empathy→empathy structure, this supports limited prompt-layout robustness.

If an estimand changes sign or the manipulation collapses, the result must be reported as a prompt boundary condition. The analyst may not choose whichever prompt produces the preferred strategy ranking.

### Practical stochasticity

The three baseline repeats are summarized by mean, descriptive SD, min/max/range and sign stability. With only three engineering repeats, no p-values, confidence intervals or population inference are permitted.

A wide practical range would motivate more formal replication-block planning; it would not justify lowering temperature or tuning the prompt after observing outcomes.

## 8. Execution safety

Real provider calls are gated behind two explicit CLI flags. The zero-API plan can be inspected first:

```powershell
python run_v33_llm_robustness.py --plan-only
```

Actual execution requires:

```powershell
python run_v33_llm_robustness.py --execute-real --allow-real-llm
```

The complete plan contains five full 9-condition Real-LLM engineering blocks. Actual provider-call count is runtime-dependent; users should inspect the plan and API budget before execution.

## 9. Thesis wording boundary

Allowed:

> 在保持模型、温度、随机种子和实验处理不变的条件下，研究进一步比较语义评价提示的预设版式扰动，并重复运行完全相同的基准提示，以区分提示版式敏感性与实际LLM调用的运行随机性。

Not allowed:

- “三次重复证明LLM输出具有统计稳定性”；
- “requested seed保证LLM完全可重复”；
- “选择表现最好的prompt作为最终模型”；
- “Real-LLM engineering robustness等同于真实消费者外部效度”。

## 10. Code mapping

- `greenconsumer_v33/prompt_profiles.py` — prompt transforms and prompt-level audit;
- `greenconsumer_v33/llm_robustness.py` — five-block selected Real-LLM suite;
- `run_v33_llm_robustness.py` — explicit plan/execute gate;
- `tests/test_task005_v331_llm_robustness.py` — zero-API profile/contract tests.
