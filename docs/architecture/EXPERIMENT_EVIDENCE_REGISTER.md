# GreenConsumer 实验结果证据台账

## 0. 台账身份

| 字段 | 值 |
|---|---|
| 版本 | `1.0` |
| 建立日期 | `2026-08-15` |
| 当前分支 | `refactor/task005-v32-clean-codebase` |
| 当前模型主线 | `TASK_005 FMCG v3.3.1` |
| 用途 | 论文结果引用、版本边界与可复核性审计 |
| 新实验运行 | `0` |
| 新真实LLM调用 | `0` |

本台账登记用户补充的五份既有实验材料，并将其与仓库中的版本化结果记录、Git commit 和可用原始证据对应。登记不等于把叙述性总结升级为原始数据，也不改变 `FORMAL_EXPERIMENT_PROTOCOL.md` 的 treatment、estimand、Pilot 或正式执行规则。

## 1. 证据等级

| 等级 | 定义 | 论文用途 |
|---|---|---|
| A | 仓库内冻结合同、block-level数据、结果表、manifest/SHA及closeout均可用 | 可作为对应版本的主要计算证据 |
| B | 仓库内有已提交结果记录、run ID、设计、数值和原始文件SHA，但当前checkout不含完整原始结果目录 | 可作工程验证结果记录；重新计算需找回匹配原始目录 |
| C | 用户提供的叙述性总结，可与A/B证据交叉核对 | 只作证据导航和写作线索，不独立支撑数值主张 |
| D | 问题、计划或过渡记录，没有完成运行与结果字段 | 不得称为实验结果；只能定位后续正式结果 |

证据优先级固定为 `A > B > C > D`。若叙述性文件与版本化合同、结果表或原始输出冲突，以可审计的版本化证据为准，并记录冲突，不做静默合并。

## 2. 用户补充材料审查

### E01 Clarification diffusion / paid-reach sensitivity

| 字段 | 审查结果 |
|---|---|
| 用户文件 | `HUB优势导致的即时澄清效果.md` |
| 用户文件SHA-256 | `49a6b3ce0bb0620294f88b063b6f51a4ad0a6726c0305aac7be96fd3e093ecda` |
| 模型/范围 | v3.3.1；Fake LLM；engineering sensitivity |
| 匹配仓库记录 | `V331_CLARIFICATION_DIFFUSION_SENSITIVITY_RESULT_20260813.md` |
| 结果记录commit | `4553a069ab95a484e274f0030c9cd848086eed3d` |
| 来源run | `clarification_20260813_151145` |
| 证据等级 | B（仓库结果记录）+ C（用户总结） |
| 一致性 | 核心数值、84/84 invariants、P1–P5方向和P4离散性均一致 |

允许使用的受限结论：

- 在预设 `p={.30,.55,.80}`、`lag={0,1,2}` 的 Fake-LLM工程网格中，P1、P3、P4、P5保持正向，P2保持负向；
- 固定 `p` 时，delivery lag主要改变到达时间而非eventual direct-recipient set；P3随lag增加而减小，支持“delivery speed是早期时机机制的边界条件”；
- Hub与Random自身reach可随p非递减，但Hub−Random差值不必单调；
- reach参数变化可以传导到Trust和expected repeat choice，但 `reach ≠ persuasion ≠ purchase`。

禁止使用：把 `.55` 写成经验最优概率、把lag=0写成现实最优时机、把 `.40–.45` 写成真实平台固定渠道优势，或把9 profiles当作总体统计样本。

### E02 Network size × paid-seed allocation

| 字段 | 审查结果 |
|---|---|
| 用户文件 | `Hub优势来源？固定预算扩大市场后，Hub策略能否保持结构效率？保持15%预算比例时，渠道优势是否随网络规模稳定.md` |
| 用户文件SHA-256 | `4c9bbffe3714a408f8121647c66b6600873dd724d427c5eaa75a95a1dcad1ead` |
| 模型/范围 | v3.3.1；Fake LLM；engineering size/allocation robustness |
| 匹配仓库记录 | `V331_NETWORK_SIZE_AND_BUDGET_ROBUSTNESS_RESULT_20260813.md` |
| 结果记录commit | `077612e57d79842e2587d8f83d71879a001a6c06` |
| 来源run | `size_20260813_164031` |
| 证据等级 | B + C |
| 一致性 | 25 profiles、109/109 invariants、family means和解释边界一致 |

允许使用的受限结论：

- 在测试的有向BA网络族中，固定K=3时，N增大伴随paid-seed比例下降及触达/澄清效应稀释；
- K/N保持15%时，Hub direct reach维持在较高水平，P1/P3/P5的描述性均值维持或增大；
- P4仍为正，但因Random reach也提高，Hub−Random差值没有随Hub reach同步扩大；
- N40/N80结果说明N20的方向并非仅由5个百分点reach粒度造成。

术语必须写成“固定paid-seed数量”与“同比paid-seed配置”。K不是货币营销预算，15%不是经验最优预算比例；N40/N80 Persona panel也不是现实人口样本。

### E03 Trust Stage A 与 Morris Stage B

| 字段 | 审查结果 |
|---|---|
| 用户文件 | `参数局部边界敏感性.md` |
| 用户文件SHA-256 | `bea8bd1612e78fef6a93406ffa198cc92fc071978196e8aa2ba8e72fae27ed1f` |
| 模型/范围 | v3.3.1；Fake LLM；engineering parameter sensitivity |
| 匹配仓库记录 | `V331_TRUST_PARAMETER_SENSITIVITY_RESULT_20260813.md`；`V331_TRUST_PARAMETER_MORRIS_RESULT_20260813.md` |
| 结果记录commits | `a92ba3fcff76ffeff9d05e5bf31276298b2c5fe5`；`7d61a8809818c1ac827acd4cc3767664fc702828` |
| 来源runs | `trust_20260813_110718`；`morris_20260813_113712` |
| 证据等级 | B + C |
| 一致性 | Stage-A baseline、54/54 checks、参数排序与Morris设计身份一致 |

用户文件是形成最终Morris结果记录之前的过渡总结，其“仍需上传Morris statistics”的下一步表述已经过期。仓库最终记录已包含80个unique evaluations、50/50 design checks、240/240 implementation invariants及完整 `mu* / mu / sigma` 排名。

允许使用的受限结论：

- P1/P5主要对repair retention、empathy repair weight和event adjustment敏感；
- P2对显式empathy repair pathway高度模型依赖；
- P3主要受event adjustment影响；
- P4对Trust参数严格不敏感，构成模型内部构念分离证据；
- `repair_saturation`在当前单次修复结构和预设参数范围内影响较弱，但不能据此断言该机制无效。

这些是条件于engineering parameter envelope的模型敏感性结果，不是参数校准、真实消费者估计或Empathy现实优越性的证据。

### E04 v3.2 Variance10、MDE与N=10设计沿革

| 字段 | 审查结果 |
|---|---|
| 用户文件 | `预实验结果.md` |
| 用户文件SHA-256 | `7353e79fef697883ce1cf958407826c60d5f550d861b37f44dea4d8d371de5ba` |
| 模型/范围 | 历史v3.2 Variance10与正式样本量决策，不是v3.3.1 Pilot |
| 匹配仓库证据 | `reproducibility/formal_v32_n10/` |
| 最终设计合同 | `task005_fmcg_v32_n10_design_power_check1.0.json` |
| 合同SHA-256 | `c06dc93f191f5edcb10f932e4c3dddc522e6a0f778a1d28443d25b34fba71572` |
| 证据等级 | A（最终v3.2合同/正式archive）+ C（历史规划总结） |

该文件同时包含两个阶段：先按五个primary估计得到由P4驱动的条件性N=58，随后在预算上限N=10下，于正式执行前把P1/P2/P5冻结为确认性family、P3/P4冻结为探索性/机制性。仓库A类证据确认最终采用的是后三指标确认性N=10设计，而不是N=58五指标设计；v3.2正式F001–F010已经完成并关闭。

对当前v3.3.1唯一可继承的内容是：

- P1/P2/P5的确认性角色与P3/P4的探索性角色具有历史设计依据；
- P1=.15、P2=.15、P5=.05可作为预先存在的量纲一致设计阈值；
- 这些阈值不是文献估计值或现实管理校准值。

严禁：把v3.2 Variance10当作v3.3.1 Pilot、把v3.2 planning SD/N直接套入v3.3.1、合并v3.2 F001–F010与未来v3.3.1 blocks，或把历史N=58写成当前正式样本量。

用户补充文件中的部分Variance10原始SD/相关系数未在当前v3.2 reproducibility archive中逐项保留；最终planning SD、确认性family、OC和N=10合同可核验。论文若要报告那些中间SD/相关系数，必须找回与v3.2 endpoint完全匹配的原始Variance10输出及manifest，不能只引用叙述文件。

当前会话中另有`task005-real-variance-pilot.zip`，但其中最新`task005-real-variance-pilot-v3`使用旧`P5_OVERALL_CLARIFICATION_PURCHASE`端点，单block为T30的5,400条mechanism rows，且其reported SD/相关矩阵与E04的repeat-choice Variance10数值不一致。因此该zip是更早的历史Pilot版本，**不能**作为E04中repeat-choice方差数值的原始证据。把名称相近但endpoint不同的Pilot包混用，会构成不可接受的版本错误。

### E05 Network topology问题记录

| 字段 | 审查结果 |
|---|---|
| 用户文件 | `网络拓扑是否导致结果变化.md` |
| 用户文件SHA-256 | `7c4ef08f798c371dbe7957ab33383a6c3d43a32c9186fa16fc8fadc0fd47ceef` |
| 文件性质 | 研究问题/执行前检查提示，不包含run ID、完成状态、数值表或invariants |
| 证据等级 | D |
| 对应最终结果 | `V331_NETWORK_TOPOLOGY_ROBUSTNESS_RESULT_20260813.md` |
| 结果记录commit | `769508e83966a1853c1839c48c19b64e756a7dff` |
| 来源run | `topology_20260813_153842` |
| 最终结果证据等级 | B |

因此，用户文件本身不得列为“网络拓扑实验结果”；应由仓库最终结果记录替代。最终记录支持：P1/P2/P3/P5在15张预设网络上保持方向，但P4存在明确拓扑边界——WS一张realization中Hub−Random reach等于0。Hub优势依赖degree heterogeneity和hub distinguishability，不是topology-universal结论。

最终记录中的结构指标—P4 Spearman相关只属于事后描述性诊断。由于topology family同时改变多项结构属性且n=15，不能写成独立因果识别；若论文要识别具体网络指标的因果贡献，需要另行预登记matched-network实验。目前不将其加入正式主线。

## 3. 论文研究问题证据映射

| 论文问题 | 当前可用证据 | 可支持的叙述 | 仍不能回答 |
|---|---|---|---|
| RQ1 内容策略 | Trust Stage A/Morris；selected Real-LLM prompt/provider robustness；未来v3.3.1正式P2 | 内容contrast具有明确模型依赖性，尤其依赖empathy repair pathway | 现实消费者中Rational或Empathy谁更优；单独evidence strength的因果效应 |
| RQ2 Hub/Random渠道 | diffusion p×lag；BA/WS/SBM topology；orientation；N20/40/80与K配置；未来正式P4描述值 | Hub direct-reach优势依赖结构异质性；fixed K存在规模稀释；reach与说服/购买必须分离 | 15%最优预算；任意平台上的普遍Hub优势；某一网络指标的独立因果贡献 |
| RQ3 Immediate/Delayed时机 | diffusion lag sensitivity；Trust event-adjustment sensitivity；未来v3.3.1 P3 | 早期时机contrast受delivery speed和Trust调整速度共同约束 | 现实企业最优响应小时数；长期效果必然严格随lag单调 |
| 行为结果P5 | clarification、Trust、topology、size、micro-buyer工程稳健性；未来v3.3.1正式P5 | 上游澄清机制可以传导至expected repeat choice，且numerical resolution已检查 | 现实购买率、市场份额、消费者总体平均处理效应 |

## 4. 结果使用规则

1. v3.3.1 Fake-LLM敏感性与网络实验统一写为 **engineering robustness / boundary evidence**，不写p值、置信区间或总体显著性。
2. v3.2 F001–F010是独立、关闭的历史正式实验。若论文使用其结果，必须明确标注模型版本和closed formal status，不得与v3.3.1合并估计。
3. 当前论文主模型若确定为v3.3.1，则最终确认性结论只能来自协议1.1后新生成的v3.3.1正式blocks；现有v3.3.1工程结果只进入方法验证和边界条件章节。
4. 对同一发现存在用户总结与仓库结果记录时，正文数值引用仓库结果记录；用户总结只作写作导航。
5. 没有原始文件或manifest时，不新增小数位、不重建分布、不计算新显著性、不声称“复现”。
6. 跨版本方向相似只能写成描述性一致，不能pool、meta-analyze或当作独立重复验证，因为机制、endpoint、horizon和运行合同发生过变化。

## 5. 当前证据缺口

| 缺口 | 风险 | 处置优先级 |
|---|---|---:|
| v3.3.1 sensitivity/topology/size完整原始结果目录未在当前checkout | 现有结果可由committed record与SHA定位，但不能现场逐行重算 | 高：正式写作前恢复匹配run目录或建立审计归档 |
| 用户E04中的部分Variance10中间SD/相关矩阵缺少当前archive逐项映射 | 若引用这些中间值，审稿人无法从当前archive直接复算 | 中：不影响已冻结v3.2 N10合同；引用前补原始artifact |
| E05用户文件不是结果 | 若直接列入“已完成实验”，会夸大证据 | 已修复：改用仓库最终topology result |
| 工程结果与正式结果尚未形成论文表号/章节号映射 | 容易在写作中混淆验证和推断 | 高：论文结果框架阶段建立table/figure registry |
| v3.3.1 Pilot与正式实验尚未执行 | 不能形成当前主模型的正式统计结论 | 依协议门禁推进，不得用旧结果替代 |

## 6. 当前审查结论

五份补充材料没有改变正式2×2×2+共同Control设计，也不构成新增正式实验。它们显著增强了既有工程结果的叙事可追溯性，其中E01–E03与仓库结果高度一致，E04解释v3.2设计沿革，E05必须由仓库最终结果替代。

当前最有学术价值、也最容易被审稿人接受的机制结论不是“Hub始终最好”或“即时澄清一定最好”，而是：

> 澄清策略效应由内容修复通道、信息到达速度和网络结构共同约束。Hub的直接触达优势依赖网络结构异质性，并受paid-seed配置与网络规模共同影响；即时相对延迟的早期信任差异则同时受delivery speed与Trust event-adjustment机制影响。上述证据目前主要属于冻结GABM内部的工程稳健性与边界识别，尚不能替代v3.3.1正式replication inference或现实数据验证。
