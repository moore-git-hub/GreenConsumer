# TASK_004 Metrics v4.0 Design Baseline

Design version: `design0.1`
Branch: `refactor/task004-metrics`
Repository: `moore-git-hub/GreenConsumer`
Generated from commit: `8bf4037c68454f134995a4efcc38f7ed14f6c54d`

This phase freezes the metrics-system design and acceptance baseline only. It does not implement production metrics. No existing production files, TASK_003 tests, fixtures, plugins, prompts, personas, routing semantics, network generation, or agent behavior may be changed in this phase.

## Scope

TASK_004 implementation may later modify only:

- `metrics_calculator.py`
- `run_experiments.py`
- `simulation_core.py`
- `analysis/plot_experiments.py`
- `analysis/plot_trajectories.py`, only if necessary

TASK_004 must not change:

- `ExperimentConfig` or the 9-condition experiment matrix
- agent trust update, cognition, decision, or message propagation
- persona, prompt, or LLM output schemas
- clarification content, target-node selection, or injection logic
- Recording/Replay semantics
- network structure, random seeds, or simulation timing
- TASK_002/TASK_003 frozen tests and fixtures

## Versions And Constants

Metrics schema is independent from the experiment matrix schema.

- `METRICS_SCHEMA_VERSION = "4.0"`
- `LOCAL_WINDOW_TICKS = 3`
- `EARLY_HORIZON_INTERVALS = 5`
- `RANKING_WEIGHT_STEP = 0.1`
- `NUM_WEIGHT_COMBINATIONS = 66`

The experiment matrix remains version `3.0`; it must not be changed to `4.0`.

## Frozen Public API

`metrics_calculator.py` must expose the following exact public API names. TASK_004 tests must not accept alternate names or compatibility aliases:

- `calculate_final_trust_gain_vs_control(strategy_trust, control_trust, *, scandal_tick: int, clarification_tick: int, total_ticks: int) -> float`
- `calculate_post_scandal_auc_gain_vs_control(strategy_trust, control_trust, *, scandal_tick: int, clarification_tick: int, total_ticks: int) -> float`
- `calculate_local_trust_effect_did_3(strategy_trust, control_trust, *, scandal_tick: int, clarification_tick: int, total_ticks: int) -> float`
- `calculate_early_trust_auc_gain_5(strategy_trust, control_trust, *, scandal_tick: int, clarification_tick: int, total_ticks: int) -> float`
- `calculate_early_trust_gain_slope_5(strategy_trust, control_trust, *, scandal_tick: int, clarification_tick: int, total_ticks: int) -> float`
- `calculate_secondary_harm_depth(strategy_trust, control_trust, *, scandal_tick: int, clarification_tick: int, total_ticks: int) -> float`
- `calculate_negative_gain_tick_count(strategy_trust, control_trust, *, scandal_tick: int, clarification_tick: int, total_ticks: int) -> int`
- `compute_relative_metrics_v4(strategy_trust, control_trust, *, scandal_tick: int, clarification_tick: int, total_ticks: int) -> dict`
- `build_control_metrics_v4()`
- `generate_weight_combinations()`
- `compute_pareto_flags_v4(...)`
- `compute_equal_weight_ranking_v4(...)`
- `compute_ranking_sensitivity_v4(...)`

The seven trajectory metric functions share the same keyword-only tick signature even when a metric does not use every tick argument. `compute_relative_metrics_v4(...)` uses the same signature and must return a `dict` whose keys are exactly the seven v4 fields. Each returned value must be identical to the corresponding standalone metric function result.

`build_control_metrics_v4()` must return a `dict` whose keys are exactly the seven v4 fields. The two global relative metrics are `0`; the five clarification-relative metrics are `None`.

`run_experiments.py` must attach formal v4 metrics to each successful result at:

```python
result["relative_metrics_v4"]
```

v4 fields must not be inserted into the legacy `SimulationMetrics` dataclass. `write_summary_csv` must read official v4 summary fields from `relative_metrics_v4`.

All trajectory metric functions must validate:

- strategy and control lengths are identical
- trajectory length equals `total_ticks`
- `total_ticks` is a positive integer
- tick parameters are valid integers within the trajectory
- all trajectory values are finite real numbers
- strategy and control are never silently truncated by `zip`

`compute_pareto_flags_v4(rows)` accepts either 9 row mappings including the common control or 8 strategy row mappings. It must automatically exclude `is_control is True`, return exactly 8 new dict rows, preserve each `exp_id`, add `is_pareto: bool`, and return rows sorted by `exp_id` ascending.

`compute_equal_weight_ranking_v4(rows)` returns exactly 8 dict rows containing at least `exp_id`, `final_norm`, `auc_norm`, `local_norm`, `score_equal`, `rank`, and `analysis_role`. `analysis_role` is always `supplementary`. Rows are sorted by `rank` ascending and then `exp_id` ascending. Rank uses average rank for ties.

`compute_ranking_sensitivity_v4(rows)` returns `(sensitivity_rows, robustness_rows)`. `sensitivity_rows` has exactly 528 rows with fields `weight_final`, `weight_auc`, `weight_local`, `exp_id`, `weighted_score`, `rank`, and `top1_credit`, sorted by weight triple ascending and then `rank`, `exp_id`. `robustness_rows` has exactly 8 rows with fields `exp_id`, `top1_share`, `mean_rank`, `median_rank`, `best_rank`, and `worst_rank`, sorted by `exp_id` ascending.

## Computation Ownership And Batch Integration

`simulation_core.py` continues to calculate each experiment's own legacy diagnostics and return the complete trajectory. v4 relative metrics must not be calculated inside a single experiment simulation because every v4 strategy row depends on the unique common control trajectory.

After all 9 experiment conditions finish, `run_experiments.py` must:

- require exactly one successful `NoClarification-Control`
- require exactly 8 successful strategy conditions
- validate all trajectory lengths, `total_ticks`, `scandal_tick`, and finite numeric trajectory values
- batch-compute the 8 strategy rows' v4 metrics against the shared control trajectory
- generate the specified `0` and `None` v4 values for the control row
- write `summary.csv`, ranking outputs, and figures only after v4 metrics have been attached

If the control is missing, duplicated, failed, has an invalid trajectory, or if any strategy trajectory or v4 computation is invalid, this is a postprocess/artifact failure. The batch must finish with `batch_exit_code = 1`, `run_completed = false`, and must not write ranking conclusions that look successful.

`simulation_core.py` should remain unchanged in principle. It may change only if a result-structure field is strictly required for the v4 batch computation.

## Inputs

All ticks are 1-indexed.

- `strategy_trust[t]`: per-tick mean trust trajectory for one strategy condition
- `control_trust[t]`: per-tick mean trust trajectory for the unique common control
- `scandal_tick = 5`
- `clarification_tick = 6` for immediate strategies or `10` for delayed strategies
- `total_ticks = 30`
- `gain(t) = strategy_trust(t) - control_trust(t)`

The unique control condition is `NoClarification-Control`.

## Formal Metrics

### final_trust_gain_vs_control

Endpoint gain:

```text
strategy_trust[total_ticks] - control_trust[total_ticks]
```

For the common control row this value is `0`.

### post_scandal_auc_gain_vs_control

Use the fixed inclusive window `Tick 5` through `Tick 30`, yielding 26 observations and 25 intervals. Integrate `gain(t)` by the trapezoid rule, then divide by the interval count.

```text
auc = trapezoid(gain(scandal_tick), ..., gain(total_ticks)) / (total_ticks - scandal_tick)
```

This is measured in average trust-score gain. It is not divided by 10. It never uses any strategy-specific minimum-trust tick and never varies the integration start across strategies.

If `total_ticks == scandal_tick`, return `gain(scandal_tick)`. If `total_ticks < scandal_tick`, raise `ValueError`.

For the common control row this value is `0`.

### local_trust_effect_did_3

Use exactly three pre ticks and exactly three post ticks:

- pre window: `clarification_tick - 3` through `clarification_tick - 1`
- post window: `clarification_tick` through `clarification_tick + 2`

The post window must include the clarification tick.

```text
(mean(strategy_post) - mean(strategy_pre))
-
(mean(control_post) - mean(control_pre))
```

If either window is incomplete, raise `ValueError`; do not shorten windows or fill values.

For the common control row this value is `None`.

### early_trust_auc_gain_5

Use the fixed event-relative window `clarification_tick` through `clarification_tick + 5`, yielding 6 observations and 5 intervals. Integrate `gain` by the trapezoid rule and divide by `5`.

```text
early_auc = trapezoid(gain(c), ..., gain(c + 5)) / 5
```

If the window exceeds `total_ticks`, raise `ValueError`.

For the common control row this value is `None`.

### early_trust_gain_slope_5

Use relative time `h = 0, 1, 2, 3, 4, 5` and fit an ordinary least-squares line to:

```text
gain(clarification_tick + h)
```

The slope is computed deterministically with pure Python or NumPy. It must not depend on SciPy. It must not use a strategy minimum or a dynamic window.

For the common control row this value is `None`.

### secondary_harm_depth

Over `clarification_tick` through `total_ticks`:

```text
min(0.0, min(gain))
```

The result is always `<= 0`. A value of `0` means no negative gain relative to the common control occurred.

For the common control row this value is `None`.

### negative_gain_tick_count

Over `clarification_tick` through `total_ticks`, count ticks with:

```text
gain < -1e-9
```

For the common control row this value is `None`.

## Control Row Semantics

The unique common control row must write:

- `final_trust_gain_vs_control = 0`
- `post_scandal_auc_gain_vs_control = 0`

The following fields must be empty/`None` for the common control because no unique `clarification_tick` exists:

- `local_trust_effect_did_3`
- `early_trust_auc_gain_5`
- `early_trust_gain_slope_5`
- `secondary_harm_depth`
- `negative_gain_tick_count`

Analysis code must allow these fields to be empty only on the control row. All 8 strategy rows must contain finite numeric values for every v4 metric.

## Legacy Diagnostic Fields

For TASK_003 regression compatibility, the following legacy fields remain temporarily in `summary.csv`:

- `delta_recovery`
- `auc_post_scandal`
- `recovery_speed`
- `steady_state_score`
- `recovery_rate`
- `t50`
- `t80`
- `trust_min`
- `trust_min_tick`
- `baseline_trust`
- `clarification_effect`
- `trust_gain_vs_control`

These are legacy diagnostics only. They must not be used for TASK_004 Pareto analysis, main effects, interaction effects, or composite ranking. `trust_gain_vs_control` is only the legacy endpoint-difference alias. The formal TASK_004 endpoint field is `final_trust_gain_vs_control`.

For every row where both fields are present, `trust_gain_vs_control` must be numerically identical to `final_trust_gain_vs_control`; the former remains only a legacy alias.

## Pareto And Ranking

Primary Pareto analysis uses exactly these three v4 objectives:

- `final_trust_gain_vs_control`
- `post_scandal_auc_gain_vs_control`
- `local_trust_effect_did_3`

All three are higher-is-better. Only the 8 strategy conditions participate. The common control must not enter the Pareto candidate set.

Equal-weight composite ranking is supplementary:

```text
score_equal = (final_norm + auc_norm + local_norm) / 3
```

Normalization is performed only within the 8 strategies. If all 8 strategy values for a metric are identical, that metric's normalized value is `0.5` for every strategy.

Weight sensitivity is supplementary. Generate every weight triple:

```text
w1, w2, w3 in {0.0, 0.1, ..., 1.0}
w1 + w2 + w3 = 1.0
```

There must be exactly 66 combinations. For each combination, compute `weighted_score`, `rank`, and `top1_credit` for each of the 8 strategies. If there is a tie for first, split `top1_credit` equally among tied strategies so each weight combination sums to `1.0`.

Weights must be generated with integer triples `i, j, k` and divided by `10`, with `i + j + k = 10`, to avoid floating-point enumeration drift. First-place ties use a fixed tolerance of `1e-12`. `top1_share` is the sum of a strategy's `top1_credit` over all 66 combinations divided by `66`. Ranks use average rank for ties. Equal-score display order uses `exp_id` ascending as the secondary sort key. Pareto remains the primary analysis; all ranking outputs are supplementary and must record `analysis_role = "supplementary"` or an equivalent frozen field.

Outputs:

`ranking_sensitivity.csv`

- `weight_final`
- `weight_auc`
- `weight_local`
- `exp_id`
- `weighted_score`
- `rank`
- `top1_credit`

`ranking_robustness.csv`

- `exp_id`
- `top1_share`
- `mean_rank`
- `median_rank`
- `best_rank`
- `worst_rank`

Ranks may use average rank for ties. Display order must be deterministic, with `exp_id` as the secondary sort key.

## Figure Outputs

TASK_004 analysis freezes these figure filenames:

- `fig1_main_effects.png`
- `fig2_interactions.png`
- `fig3_pareto.png`
- `fig4_ranking.png`
- `fig5_clarification_diagnosis.png`
- `fig6_ranking_sensitivity.png`

## Latest Managed Artifacts

`run_experiments.py` must treat the following TASK_004 outputs as managed files when synchronizing the `latest` snapshot:

- `ranking_sensitivity.csv`
- `ranking_robustness.csv`
- `figures/fig1_main_effects.png`
- `figures/fig2_interactions.png`
- `figures/fig3_pareto.png`
- `figures/fig4_ranking.png`
- `figures/fig5_clarification_diagnosis.png`
- `figures/fig6_ranking_sensitivity.png`

Together with the existing managed outputs, these files must be cleared or overwritten from the current run. Stale ranking or figure artifacts from an earlier run must not remain in `latest`.

## Run Metadata

`run_metadata.json` must add an independent `metrics` block:

```json
{
  "metrics": {
    "schema_version": "4.0",
    "primary_objectives": [
      "final_trust_gain_vs_control",
      "post_scandal_auc_gain_vs_control",
      "local_trust_effect_did_3"
    ],
    "post_scandal_window": {
      "start": "scandal_tick",
      "end": "total_ticks",
      "integration": "trapezoid",
      "normalization": "divide_by_interval_count"
    },
    "local_did": {
      "pre_ticks": 3,
      "post_ticks": 3,
      "post_includes_clarification_tick": true
    },
    "early_window": {
      "horizon_intervals": 5,
      "observations": 6
    },
    "ranking": {
      "pareto_primary": true,
      "equal_weight_supplementary": true,
      "weight_sensitivity_step": 0.1,
      "weight_combination_count": 66
    }
  }
}
```

Analysis entry points must fail closed unless all of the following are true:

- `experiment_matrix.matrix_version == "3.0"`
- `experiment_matrix.condition_count == 9`
- `metrics.schema_version == "4.0"`

## Test Baseline

`tests/test_task004_metrics.py` is a cross-platform executable Python script. It must not use `cfile=os.devnull` in py_compile checks; temporary compile output must use `tempfile` paths.

Test groups:

- T0 syntax checks
- S1 metrics version and constants
- S2 fixed post-scandal AUC
- S3 endpoint gain
- S4 local DID
- S5 early fixed-window AUC
- S6 early gain slope
- S7 secondary harm
- S8 common control output semantics
- S9 summary schema
- S10 analysis fail-closed gates
- S11 Pareto uses only 8 strategies and 3 v4 objectives
- S12 equal-weight ranking
- S13 weight sensitivity
- S14 plotting entry points
- S15 runtime artifacts
- S16 behavior invariance

Because production v4 metrics are not implemented in this phase, the test script may report expected FAIL items. It must run to completion and report every item without `ImportError`, `SyntaxError`, or harness failure.

## Fixture Baseline

`tests/fixtures/task004/metric_cases.json` contains deterministic synthetic trajectories only. It does not reference real LLM results and must not use `run_20260802_113349` as thesis data.

Fixture cases:

- `identical_strategy_control`
- `constant_plus_one_after_scandal`
- `immediate_local_step`
- `delayed_local_step`
- `linear_early_gain`
- `secondary_harm_case`

Each case stores:

- `scandal_tick`
- `clarification_tick`
- `total_ticks`
- `strategy_trust`
- `control_trust`
- expected metrics
- generation notes

## Frozen Hashes

These hashes freeze TASK_003 behavior and mechanism files at TASK_004 start. They must not change during TASK_004.

| Path | SHA-256 |
| --- | --- |
| `tests/test_task003_experiment_matrix.py` | `04805fc714fb494444fc0fdcd01a4e4ea976ac2bd906864aaa0b23ff655572e1` |
| `tests/fixtures/task003/pre_task003_behavior_trace.json` | `5465bc6f18fcf6232294409fff0c5e5f318b750bf4863254eee6600f0a03984e` |
| `experiment_config.py` | `8b33b2f9032fbf44542dc4efd2d6cc947323dc2e2b8e438cb2f914ce0c9fe87d` |
| `node_selector.py` | `744e30edf0c097304bbe36635e53fab2afc4a05337f47a61990064c7e2e5d1a7` |
| `clarification_injector.py` | `1ea6eea856915bcd91b31d35d11d4f43d6eaa2390634b1c36ac0681227c00e5b` |
| `generate_data.py` | `e2a885e0fd83d222b51d857e2ee7fac12c0c4b32704c2d7c23ae00ef6652cb0a` |
| `plugins/agent/invoke/EasyInvokePlugin.py` | `991e247b635bff26c52c59c8bccc58dcfee060dbb8820749242a97705a1ea1a5` |
| `plugins/agent/invoke/GreenInvokePlugin.py` | `28841e45ac285f623a9ffeeb564c750de9a7923027a9015f8caece49ca817839` |
| `plugins/agent/perceive/EasyPerceivePlugin.py` | `2133a8ce854f756f1916383b212b29f4f7f727de424e42bf5fdaf5170b837b66` |
| `plugins/agent/perceive/GreenPerceivePlugin.py` | `807b3e1f0793a05b1cef4fc7711fe1dcf492af62f30b2514e3cb67271cfff0ff` |
| `plugins/agent/plan/ConsumerPlanPlugin.py` | `2bd69f541a9722e397f239f647cd856a77190e133e1dec664455f09910f0d2f4` |
| `plugins/agent/plan/EasyPlanPlugin.py` | `3825772590d5e382e6f791453fb2dfbbaeaa51c85dd034a77c2419ad70fa1282` |
| `plugins/agent/profile/EasyProfilePlugin.py` | `cd2c99d26aaa5f2ec93218203e447f0fe60cd4ddf8b13fa3612315cd78ce5fe4` |
| `plugins/agent/profile/GreenProfilePlugin.py` | `53577f0be121b20e25c25c61edceac0bbf4bf807c5687fbeb1ecb7775b684441` |
| `plugins/agent/reflect/EasyReflectPlugin.py` | `feb7fb2405d8e2daf8101460666313bd946afbe3ad5aa6f126433ab489bd45e2` |
| `plugins/agent/reflect/GreenCognitionPlugin.py` | `e8fca6927152b01c0db11d148c243eb9de63ecd5e6ddae7df6b6b25ec71be705` |
| `plugins/agent/reflect/MemoryManager.py` | `dcbafe4a6bdd2063488b51a9faca7b218310073e03921f9e50d5354252a82494` |
| `plugins/agent/state/EasyStatePlugin.py` | `3cba7af98dbf9de4e1fdb4ed4eea06581943662dd30fcc978db6b86af9c1b91f` |
| `plugins/agent/state/GreenStatePlugin.py` | `b4f5281f133a95638a64fb19f60cbd74c96bbb2e3457deb873fe25c55943a61c` |

## TASK_004 Mutable Baseline Hashes

These files may change during later TASK_004 implementation, but their phase-start hashes are recorded here:

| Path | SHA-256 |
| --- | --- |
| `metrics_calculator.py` | `0083ef7ac4c25c1ce3cdbb85f134df290ad0d7bb0e11132cc4356123b84c5c2b` |
| `run_experiments.py` | `3df58ddbadfc07494c7734344e9b0afb35beaefb67f9d3d8511edaa7e70be4bb` |
| `simulation_core.py` | `2450edcd1629a13d157ec46013f8d1032431387dfd1f4ecddf6bdbdfc6d68cc9` |
| `analysis/plot_experiments.py` | `b0193804b59c33bdcb216df44e2098ec9b8317e0a1facbc2c19c004fab7248c1` |
| `analysis/plot_trajectories.py` | `793e78d43df692b802ca2d71d08b7a6076f0aa001a1b28c5528d529921582d30` |
