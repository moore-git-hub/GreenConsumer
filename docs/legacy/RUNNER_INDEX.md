# Runner index and legacy boundary

仓库形成过程中保留了多代 runner。为避免误运行，按用途划分如下。

## Current post-formal reproducibility
- `reproducibility/formal_v32_n10/scripts/analyze_task005_fmcg_formal_v32_n10.py`
- `reproducibility/formal_v32_n10/scripts/activate_task005_fmcg_formal_v32_n10.py`
- `reproducibility/formal_v32_n10/scripts/check_task005_fmcg_formal_v32_n10_authorized.py`
- final real-LLM runner identity: SHA256 `4b439e629f957fa552d11df36cf0bd2d4987e2eeac9b0e7d6216c9f16a346db5`

正式主实验已关闭，不应再次运行以追加样本。

## v3.2 engineering / diagnostic
- `run_task005_fmcg_kernel_fake_smoke_v32.py`
- `analysis/task005_fmcg_fake_model_smoke_v32.py`
- `task005_fmcg_fake_router_v32.py`

这些用于结构验证和诊断，不属于 formal sample。

## Superseded formal / pilot runners
以下脚本保留用于开发历史和审计，不得作为 v3.2 N=10 当前正式入口：
- `run_formal_launch.py`
- `run_formal_replications.py`
- `run_task005_real_manipulation_pilot_v1.py`
- `run_task005_real_manipulation_pilot_v2.py`
- `run_task005_real_manipulation_pilot_v3.py`
- `run_task005_real_variance_pilot_v1.py`
- `run_task005_real_variance_pilot_v2.py`
- `run_task005_real_variance_pilot_v3.py`

## Generic / historical simulation entry points
- `run_simulation.py`
- `run_experiments.py`
- `run_replications.py`
- `run_quick_experiment.py`
- `run_clarification_trial.py`

它们可用于历史调试或旧路径，但不定义论文最终 FMCG v3.2 formal design。
