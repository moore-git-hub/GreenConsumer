# TASK_005 FMCG v3.3 parallel mechanism design

## Status

v3.3 is an **engineering/model-development branch inside the existing clean-code branch**.  It does not alter v3.2 source files and does not extend or reinterpret the closed F001-F010 formal sample.

The purpose of v3.3 is to test three structural changes suggested by the real-LLM engineering diagnostics:

1. less mechanical Trust recovery;
2. non-periodic but reproducible FMCG category-purchase opportunities;
3. clarification reach that is network-dependent without deterministic one-hop saturation.

All new numeric defaults are **engineering assumptions, not empirical estimates**.

## 1. Trust dynamics

v3.2 computes Trust directly from baseline plus repair memory minus crisis memory.  v3.3 preserves those memory stocks but adds:

- separate crisis and repair retention rates;
- partial Trust adjustment to the memory-implied target;
- diminishing marginal repair returns;
- optional amplification of negative crisis-memory increments when the LLM appraises hypocrisy.

The development defaults are declared in `mechanism_v33.TrustDynamicsV33Parameters` and are written into every v3.3 `run_summary.json`.

A `legacy_v32()` parameter profile is supplied so the core Trust-memory transition can be regression-tested against v3.2.

No random Trust noise is added merely to make trajectories visually irregular.

## 2. FMCG renewal demand

v3.2 assigns each micro-buyer one fixed purchase interval and phase.  v3.3 preserves the first opportunity phase, but after every category-purchase opportunity it deterministically re-draws the next interval from the persona's declared interval set (5-7, 7-10, 10-14, or 14-28 days).

This produces a reproducible renewal process rather than a permanent periodic schedule.

Loyalty uses a bounded EWMA:

`L_t = rho * L_(t-1) + (1-rho) * signed_choice`

instead of coefficients whose sum can exceed one.

The TPB intention, persona preference, PBC support and conditional brand-choice utility remain otherwise aligned with v3.2.

## 3. Clarification reach

The communication budget remains K=3 paid seeds.

v3.3 changes exposure realisation:

- public organic exposure: deterministic Bernoulli draw per Agent;
- paid seed exposure: certain at the clarification Tick;
- paid one-hop amplification: deterministic Bernoulli draw over actual seed->successor edges;
- successful one-hop amplified recipients receive the enterprise clarification one Tick later;
- no automatic paid second hop is created.  Further spread must occur through consumers' own UGC and `SocialNetworkPlugin`.

This keeps Hub/Random budget comparability while reducing the mechanical pathway that produced Hub reach near 1.00 in the 20-Agent BA benchmark.

## 4. LLM configuration

v3.3 intentionally keeps the current real-LLM temperature at **0.3** during initial mechanism testing.  Temperature must not be increased merely to make aggregate trajectories look less smooth.

Prompt/temperature sensitivity is a separate validation exercise.

## 5. Recommended ablation sequence

Run zero-API/fake conditions before any real LLM call:

1. verify pure v3.3 unit tests;
2. run one full fake v3.3 block;
3. compare v3.2 and v3.3 Trust trajectories;
4. inspect category-opportunity counts for renewal irregularity;
5. inspect Hub vs Random direct reach for ceiling reduction;
6. only then run one real-LLM v3.3 engineering block.

Do not tune parameters to obtain a preferred strategy ranking.

## 6. Local commands

```powershell
D:\Python\Anaconda\envs\Kernel\python.exe -X utf8 -m pytest tests/test_task005_v33_mechanisms.py -q

D:\Python\Anaconda\envs\Kernel\python.exe -X utf8 run_v33.py preflight

D:\Python\Anaconda\envs\Kernel\python.exe -X utf8 run_v33.py pipeline --llm fake --condition all --support both
```

Only after the fake block passes:

```powershell
D:\Python\Anaconda\envs\Kernel\python.exe -X utf8 run_v33.py preflight --real

D:\Python\Anaconda\envs\Kernel\python.exe -X utf8 run_v33.py pipeline --llm real --condition all --support both --allow-real-llm
```

Every v3.3 run is engineering/demo scope and is not a new formal replication.
