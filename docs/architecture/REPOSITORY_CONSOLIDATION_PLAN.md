# GreenConsumer v3.2 代码库收尾与整理方案

## 总体判断
模型功能开发已经结束；当前阶段属于 post-formal code freeze / repository closeout，不再进行机制调参或新增正式仿真。

## 当前仓库还需收尾的三件事
1. 顶层 `README.md` 仍以旧 `run_simulation.py` 为主入口，需要改成 TASK_005 FMCG v3.2 的 canonical 入口。
2. root-level 文件混合 legacy scenario、mechanism-v2、v3.1/v3.2 demand redesign 和 formal-v1/v2 历史脚本，需要建立 canonical/legacy 边界。
3. N=10 正式 runner、analysis、authorization、closeout artifacts 需要作为 post-formal reproducibility archive 归档。

## 整理原则
- 整理，不改机制。
- 不删除 legacy evidence。
- 不移动冻结源码，直到 formal release snapshot 完整保存。
- 不再追加 F011+。
- 不把 engineering/pilot blocks 混入 formal N。
- 结果文件与源码分离。

## 论文—代码映射

| 论文构件 | Canonical code |
|---|---|
| 实验矩阵 | `experiment_config.py` |
| FMCG 情境与 Agent 画像 | `fmcg_scenario_v32.py` |
| 语义变量 | `mechanism_v32_semantics.py` |
| LLM 语义评估 | `GreenCognitionV32Plugin.py` |
| Trust/Att/记忆 | `mechanism_v2.py` |
| SN | `mechanism_v31_cognition.py` |
| Extended TPB intention | `purchase_mechanism_v3.py` |
| 重复购买机会与品牌选择 | `purchase_mechanism_v31.py` |
| Persona→demand 映射 | `purchase_mechanism_v32.py` |
| 社会网络 | `SocialNetworkPlugin.py` |
| Hub/Random | `node_selector.py` |
| 澄清注入与 reach | `clarification_injector.py` |
| v3.2 runtime isolation | `task005_fmcg_runtime_v32.py` |
| LLM audit | `task005_fmcg_audited_router_v32.py` |
| 正式估计 | `analyze_task005_fmcg_formal_v32_n10.py` |

这张表建议进入论文附录或复现材料。
