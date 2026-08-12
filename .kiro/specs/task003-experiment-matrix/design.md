# TASK_003 — 实验矩阵重构技术设计（Design，第 4 版：验收判据定向修正）

| 项 | 值 |
|---|---|
| 任务 | TASK_003 实验矩阵重构：12 伪条件 → 9 实质条件 |
| 阶段 | 设计（只读审查 + 本文档），**未应用任何 diff、未运行任何真实 LLM 实验** |
| 变更性质 | 实验设计（因子词表 + 矩阵 + 运行编排 + 分析口径） |
| 目标矩阵版本 | `EXPERIMENT_MATRIX_VERSION = "3.0"`（条件数 9） |
| 前置任务 | TASK_001 PASS、TASK_002 PASS（`agent_records` schema v2.0 / **60 字段**） |
| 分支 | `refactor/task003-experiment-matrix`（已 tracked 到 origin） |
| HEAD | `c8558d5 docs(observability): finalize TASK_002 records` |
| 上游提交 | `e37967f docs(observability): finalize TASK_002 records`、`96907fe feat(observability): add auditable agent and run records` |
| 工作树状态（设计阶段） | 已跟踪文件**无修改**；5 个生产文件无 staged / unstaged / untracked 变更。本文档提交后（§12.1 第 1 步），未跟踪项为 `tests/test_task003_experiment_matrix.py`（第 5 步才提交）与 `.kiro/specs/**/.config.kiro` |
| 本文档已核实的源文件 | `experiment_config.py`、`run_experiments.py`、`simulation_core.py`、`clarification_injector.py`、`node_selector.py`、`metrics_calculator.py`、`analysis/plot_experiments.py`、`analysis/plot_trajectories.py`、`tests/test_task002_observability.py` |
| 本次设计提交范围 | `.kiro/specs/task003-experiment-matrix/design.md` |

> 本文档中所有引用的行号与代码文本均取自上述文件的**当前工作树内容**（逐行读取于本次设计会话）。
> 凡无法从代码确证的事实，一律显式标注「**待核实**」。

## 修订说明（第 1 版 → 第 2 版）

第 1 版在上一次会话被取消前写出，其行号核实与下游影响分析全部保留复用。本轮按用户强制裁定作以下 6 处不可讨论的修订：

| # | 第 1 版 | 第 2 版（本轮裁定） | 影响范围 |
|---|---|---|---|
| R-1 | `timing_factor = "delayed"`，未统一表述延迟长度 | 保持 `"delayed"`，并在全文固定表述为**延迟澄清 = 丑闻发生后 5 个 Tick，即当前配置下 Tick 10** | §4、§6、§7 |
| R-2 | 哨兵值 `"not_applicable"`（下划线） | 哨兵值 `"not-applicable"`（**连字符**）；常量**名**仍为 `NOT_APPLICABLE` | §3、§6、§10、§12、§13 全文 |
| R-3 | exp_id 用 `Imm` / `Del` 缩写，对照为 `Control-` 前缀形式 | exp_id 用**完整词** `Immediate` / `Delayed`；对照固定为 `NoClarification-Control` | §2、§5、§6、§7、§12、§13 |
| R-4 | 录制组 = 4 个重复对照之一（`…-NoClr`），其余 11 组回放 | 录制组 = **唯一共同对照**；8 个策略组各自回放至**其首次处理 Tick 之前**（immediate 止于 Tick 5，delayed 止于 Tick 9） | §7、§8 |
| R-5 | 统计口径散落在「决策 7」 | 统计语义并入 §6：共同对照**只**参与 `any clarification vs common control`，**不进入** 2×2×2 均值 | §6 |
| R-6 | 缺 §10–§15（会话被取消，文档在「决策 10」处截断） | 补齐并重排为规定的 15 节顺序 | 全文结构 |

第 1 版「决策二」（为何采用 `delayed` 而非 `delay-5`）的论证与本轮裁定一致，**原文保留**，见附录 A。

## 修订说明（第 2 版 → 第 3 版）

本轮为**增量定向补正**：除下表 6 项外，其余章节（Kiro Spec Compatibility Map 兼容层、§1–§7、§11、§15、附录 A/B）保留原文，不重写、不移动。

| # | 第 2 版 | 第 3 版（本轮补正） | 影响范围 |
|---|---|---|---|
| R-7 | §10.2 标题与主框架为「一处不可避免的破坏：`tests/test_task002_observability.py` 将无法再执行」 | 改为**「历史验收工具冻结与当前回归覆盖迁移」**。TASK_002 测试与 fixture **永久冻结**、作为提交状态的历史验收证据保留；TASK_003 在**应用生产 diff 之前**新增自己的测试与 pre-TASK_003 fixture 并**承接**长期契约。冻结后该文件不再纳入常规回归执行集，这是**设计决定**而非缺陷 | §10.2 整节重写；§9 第 8 行、§12 / S18、§14 R1 与「不可回滚项」同步 |
| R-8 | Replay 窗口内 miss = 计数 + 打印 + `errors.log`，**仍降级调用真实 Router 继续跑** | 改为 **fail-closed**：窗口内 miss ⇒ `miss_count += 1` 后**立即 `raise ReplayAlignmentError`**，**禁止 fallback 到真实 Router**；该实验进入失败分支，轨迹不进入 `summary.csv` 有效行、不参与任何对比；失败元数据保留 `config` / `error_type` / `run_audit`（TASK_002 / R12）；所有产物与图表落盘后再 `SystemExit(4)` | §8.3、§8.4、§8.5、§13.2、§14（R5/R9）、§7.1 原则 3、§12 / S10 |
| R-9 | S15 主要证据 = `trajectories.csv` 的 `avg_trust` 逐 Tick 相等 | S15 主要证据改为 `agent_records` 的**逐 Agent 逐 Tick 精确比较**（键 `tick` + `agent_id`；字段 `trust_score_raw`、`shock_anchor_after_raw`、`quiet_ticks`、`is_buying`、`is_posting`）；`avg_trust` **降级为汇总检查**，不得作为唯一证据；明确排除 4 个按设计必然不同的字段 | §12 / S15、§8.6、Compatibility Map 的 Property 7 措辞 |
| R-10 | 无 pre-TASK_003 基线流程 | 新增 §12.1：**不可调换的 7 步顺序**（提交 design → 建测试 → 洁净树生成 fixture → fixture 记录溯源四项 + harness 哈希 + 行为轨迹 + 生产文件哈希 → 单独提交 → 冻结 → 才允许应用生产 diff），复用 TASK_002 已验证的洁净前置检查、`git_is_dirty` 为 bool、`test_harness_sha256` 完全相同、`git merge-base --is-ancestor` 四道机制 | 新增 §12.1；§14.2 回滚方案引用 |
| R-11 | 实施清单含 6 个生产文件（含 `clarification_injector.py` 的可选防御性 `raise`） | 生产文件收窄为 **5 个**：`experiment_config.py`、`run_experiments.py`、`simulation_core.py`、`analysis/plot_experiments.py`、`analysis/plot_trajectories.py`。**`clarification_injector.py` 本任务完全不修改** | §9、§13、§15 第 4 项、§6.3、§14.2 提交粒度 |
| R-12 | 验收编号 S1–S17 | 扩展为 **S1–S18**：S15 = 逐 Agent 处理前路径对齐、S16 = 运行期产物、S17 = legacy 闸门、S18 = TASK_002 核心契约承接与 pre-TASK_003 行为不变性；每项标注「离线 / 运行期」 | §12 验收表 + 新增 S 编号总表 |

## 修订说明（第 3 版 → 第 4 版）

本轮为**验收判据的定向修正**，不触碰矩阵设计本身：§1–§11、§13–§15 与附录 A/B 全部保留原文。修正集中在 §12（验收测试设计），新增 §12.3–§12.6。

| # | 第 3 版 | 第 4 版（本轮裁定） | 影响范围 |
|---|---|---|---|
| R-13 | S5 断言「全库不存在 `delay-3` / `delay-5`」 | 改为**5 个面的定向检查**（AST + 符号白名单）：当前矩阵配置、`STRATEGY_TIMING_LEVELS`、当前 `exp_id`、`experiment_config` 活跃因子常量、`analysis` 当前图例·分组·时点映射。旧标签在 `LEGACY_*` 常量、legacy 检测逻辑、测试反例、文档中**允许存在** | §12.2 / S5、新增 §12.3 |
| R-14 | S8 用子串方式扫全库 | 改为只检查**生产 Python 的 AST 精确字符串字面量** `"not_applicable"` 是否被用作当前字段值。`NOT_APPLICABLE`（标识符）、`"not_applicable_value"`（不同字面量）、文档文字、测试反例一律不得误判 | §12.2 / S8、新增 §12.3 |
| R-15 | S10 断言 `divergent_cache` / `record_after_divergence` 属性必须不存在 | 删除这两条实现绑定断言，改为**行为契约 5 条**：窗口内命中真实 Router 调用数 0；窗口内 miss 则 `miss_count+1` + 抛 `ReplayAlignmentError` + 真实 Router 调用数 0；窗口外正常调用；窗口外不增加 `miss_count`；**所有路径都不得修改共同对照基线 cache** | §12.2 / S10、新增 §12.3 |
| R-16 | S13 要求生产代码存在名为 `_strategy_rows` 的函数 | 删除命名要求，改为**功能检查**：输入 8 策略 + 1 对照，分析入口实际只使用 8 个策略行；对照不进入主效应与交互；`is_control=False` 却带 `not-applicable` 必须抛错。不限定 helper 名称或内部组织方式 | §12.2 / S13、新增 §12.3 |
| R-17 | 两种运行模式（生成 fixture / 全量验收），运行目录自动发现 | 拆为**三种模式**：`--generate-fixture`（只生成 fixture，不跑 S1–S18，不要求新矩阵已实施）、`--offline-only`（离线项，S15/S16 记 WARN，明确输出 `NOT A FULL ACCEPTANCE`）、`--runtime-dir PATH`（正式验收，缺文件/缺行/版本不符一律 FAIL，**绝不回退读 `results/latest`**，仅 `Failed == 0` 才退出 0） | 新增 §12.4 |
| R-18 | 未规定正式验收目录的来源 | 明确：正式验收目录必须由**确定性 Mock Router** 产生；不使用真实 LLM；不得使用历史 12 条件目录；不得用手工拼接的 CSV 伪造端到端证据 | 新增 §12.5 |
| R-19 | 洁净检查依赖单条 `git status --porcelain` | 明确为**三项独立检查**：unstaged production diff、staged production diff、production 路径未跟踪文件。`tests` / `docs` / `.kiro` / `results` 仍排除，以避免流程死锁 | §12.1 第 3 步、新增 §12.6 |
| R-20 | fixture 语义未收边 | 明确：pre-TASK_003 fixture 只证明「TASK_003 实施未改变既有信任更新、`shock_anchor`、`quiet_ticks` 与行为决策机制」。它**不是**旧 12 条件矩阵正确性的证明，**不要求**旧 `ExperimentConfig` 接受 `delayed` 或 `not-applicable` | 新增 §12.6 |
| R-21 | 标题仍写「第 3 版」；元数据写「唯一可写文件」；洁净检查的措辞把 `design.md` 与测试文件都当作「未提交」；S13 的探测范围与正式验收判定未收边 | 提交前的自洽修正：①标题改为「第 4 版：验收判据定向修正」；②元数据行改为「本次设计提交范围」；③§12.1 / §12.6 明确 `--generate-fixture` 时的四条仓库状态（**design.md 已提交**、测试文件未提交、fixture 未提交且尚不存在、5 个生产文件三类变更均为空），`git_is_dirty == True` 的来源改述为「测试文件按流程尚未提交」；④§12.3.4 增补探测范围**六条硬约束**（含 `obj.__module__ == module.__name__`）与**按运行模式分档**的判定表：正式验收下依赖不可用即 FAIL | 标题、元数据表、§12.1、§12.2 / S13、§12.3.4、§12.6.1、新增 §12.6.1.1 |

### 修订说明补充（第 4 版 · 代码级审查后的四项阻断修复）

测试文件的代码级审查发现四处会**让验收在不该通过时通过**的缺陷。它们的共同性质是「判据存在但不起作用」，因此列为 fixture 冻结前的阻断项。

| # | 阻断缺陷 | 为什么这是阻断级 | 修复 | 影响范围 |
|---|---|---|---|---|
| R-22 | **S13 不区分运行模式**：`check_s13_domain_gate(v)` 在依赖不可用时一律 WARN | 正式验收会在「从未验证过分析口径」的情况下报告通过。§12.3.4 已规定分档，但代码未落实 | 改为 `check_s13_domain_gate(v, formal)`：`status == "unavailable"` 时 `formal=False` → WARN，`formal=True` → **FAIL**。并且 `_probe_analysis_gate` 的候选判定改为**两项同时满足**才返回 `ok`：只满足「9 行 → 8 策略行」而反例不抛错的**半成品闸门不得提前返回**，必须继续检查后续候选，最终在 detail 中列出这些半成品 | §12.2 / S13、§12.3.4 |
| R-23 | **S15 用 `table[key] = value` 静默覆盖重复行** | 「同一 `(exp_id, tick, agent_id)` 出现两行」这种产物缺陷会完全隐形：后写入者胜出，逐值比较照样通过。而重复行意味着某个 Agent 被重复结算，是最危险的情形之一 | 先构造 `key_counts` / `key_to_rows`，断言每个键出现次数**恰好为 1**；任意 `count != 1` 立即 FAIL 并**停止后续逐值比较**（拒绝在键不唯一的数据上给出「对齐通过」的结论）。处理前区间（immediate → Tick 1–5，delayed → Tick 1–9）逐条验证 5 项判据：①键集合与对照完全相等；②无缺失 Agent；③无额外 Agent；④每键恰好一行；⑤5 字段逐字相等。**明确不得**用 S16 的总行数断言替代键唯一性检查——行数正确而键重复（配套某键缺失）完全可能 | §12.2 / S15、新增 §12.5.2 |
| R-24 | **S16 的退出码只是 WARN** | 产物齐备但批次以退出码 4 结束（存在 Replay 对齐违约）时，报告仍显示通过。靠「人工观察进程退出码」等于没有验收 | 新增 `run_metadata.json` 的两个**机器可读**字段契约 `batch_exit_code` / `run_completed`（语义见 §12.5.1）；正式验收要求 `batch_exit_code == 0` 且 `run_completed is True`。测试中的「退出码仅 WARN」实现已删除，正式模式下缺字段或值不符**必须 FAIL** | §12.2 / S16、新增 §12.5.1 |
| R-25 | **S18 缺 fixture 时一律 WARN** | 正式验收会在没有任何行为基线的情况下通过，而行为不变性恰恰是 fixture 存在的唯一理由 | 改为 `check_s18_handover_and_invariance(v, formal)`：fixture 不存在或不可读时 `formal=False` → WARN，`formal=True` → **FAIL**。正式模式下七项任一不成立均 FAIL：fixture 存在且可读、`test_harness_sha256` 匹配、`generated_from_commit` 有效且为 HEAD 祖先、`git_is_dirty` 为 bool、`compared_fields` 匹配、TASK_002 冻结哈希匹配、行为轨迹零差异 | §12.2 / S18、§12.4 |
| — | 报告把「正式模式但验收失败」标记为 full acceptance | `is_full_acceptance` 直接取 `formal`，与 FAIL 数无关 | 改为 `formal and v.n_fail == 0`，并另记 `is_formal_mode` 保留模式信息 | §12.4 |
| R-26 | **S13 只用 `set(out["exp_id"])` 判定候选** | 集合会把重复行折叠掉。一个返回 16 行（每个策略 exp_id 各两行）的函数，其 exp_id 集合与期望完全相等，因此会被判为「闸门已实现」——而下游的主效应均值会因重复行被算错 | 候选判定改为**六项同时满足**：①`len(out) == 8`；②`exp_id` 列长度 == 8；③`exp_id` 无重复；④集合恰为 `EXPECTED_STRATEGY_EXP_IDS`；⑤不含 `NoClarification-Control`；⑥错标 `not-applicable` 输入必须抛错。集合相等但行数或唯一性不合格的候选记为 **invalid candidate** 并**继续检查后续候选**，不得返回 `ok`；`no_gate` 的 detail 分别列出 invalid 与 filter_only 两类半成品 | §12.2 / S13、§12.3.4 |
| R-27 | **S15 只能发现 `count > 1`，发现不了 `count == 0`** | 键唯一性检查的期望值来自实际数据自身。若某个 Agent 或某个 Tick 的记录**整体缺失**，期望也跟着缺失，缺失就永远不可见——这恰恰是「某组实验少跑了一个 Agent」的形态 | 新增**绝对预期键空间**（§12.5.3）：由三个**外部**来源的笛卡尔积构造 `expected_keys` —— 9 个 `EXPECTED_EXP_IDS` × `Tick 1..total_ticks`（来自 `run_metadata` 的 `config.total_ticks`）× `network_nodes.csv` 的 `agent_id` 集合。逐值比较**之前**断言六项：`len(network_agent_ids) == num_agents`、`actual_keys == expected_keys`、`missing_keys` 为空、`extra_keys` 为空、每个 `expected_key` 的 `count` 恰为 1、`duplicate_keys` 为空。任一失败立即停止逐值比较。排序异常键时使用**安全 key 函数**（`None` 统一转字符串），避免畸形 CSV 触发 `TypeError` 而丢失整份验收报告。原有的处理前窗口比较保留为**第二层**，不能代替绝对键空间检查 | §12.2 / S15、新增 §12.5.3 |
| R-28 | **`baseline_file_sha256` 只记录、从不使用** | 三个 Agent 插件直接决定行为轨迹，而 TASK_003 明确不修改它们（§15 第 1–3 项）。只记录不校验等于没有约束：插件被改动后，比对会以「行为差异」的形式失败，但报告无法指出「输入本身变了」这一根因；若改动恰好不影响本组场景，还会完全通过 | S18 新增第 ⑤ 组断言：字段存在且为 dict；键集合恰为 `BASELINE_HASHED_FILES` 三项；每个记录值是 64 位 SHA-256（`"missing:..."` 或空值不得冒充已知哈希）；每个记录值**等于当前文件的 SHA-256**。offline 与 formal 两种模式下，fixture 存在而哈希不符**同样 FAIL**（这不是「不可判定」，而是「证据表明输入已变」） | §12.2 / S18 |
| R-29 | **只检查工作树 clean，无法锚定「TASK_003 生产 diff 尚未应用」**；且 fixture 可被静默覆盖 | 这是整条基线流程最致命的漏洞：只要有人把 TASK_003 的生产改动**提交**掉，工作树就是干净的，三路检查全部通过，fixture 会被当作 pre 状态记录下来——此后 pre/post 比较变成 post/post 自比，**永远通过**。覆盖一份已冻结的 fixture 同样是不可逆的证据破坏 | 新增 40 位常量 `PRE_TASK003_BASE_COMMIT`（= `git rev-parse c8558d5` = `c8558d57f501dd32d483a2b2d939a06129554365`）与 `assert_pre_task003_generation_state(root)`，**在 `collect_behavior_trace()` 之前**执行，七项全部必须成立（见 §12.6.1.2）。核心是第 6 项：`git diff --quiet PRE_TASK003_BASE_COMMIT..HEAD -- <PRODUCTION_PATHS>`，其语义是**HEAD 与 `PRE_TASK003_BASE_COMMIT` 在 `PRODUCTION_PATHS` 上的树内容完全一致，不存在净文件差异**——**不得仅检查当前工作树是否 clean**。fixture 新增 `production_baseline_commit` 与 `fixture_generation_guard_version = "2.0"`，由 S18 第 ⑥ 组断言校验。最终落盘改为**排他创建** `open(FIXTURE_PATH, "x")`，`FileExistsError` → 明确输出禁止覆盖并退出码 2，原 fixture 不被修改 | 新增 §12.6.1.2、§12.6.1.3、§12.1、§12.2 / S18 |
| R-30 | **S13 只证明「存在一个正确的过滤函数」，不证明它被调用**；且入口发现按源码字面量筛选会漏检 | 函数存在而无人调用时，主效应与交互照旧把共同对照算进均值——恰恰是 §1.2 要消灭的核心缺陷。「找到一个正确候选即通过」的逻辑对这种情形完全无效。而「源码里直接出现 `content_factor` 等字面量」这一筛选条件会漏掉**通用包装入口**（列名由参数传入）与**间接委托入口**（转调私有函数完成聚合），这两类恰恰是闸门最容易被绕过的地方 | S13 新增**集成验证**（见 §12.3.5）：`_probe_analysis_gate` 返回 `candidate_name`；对 `run_experiments.py` 实际调用的**全部** `plot_experiments` 入口做运行期探测，**不按源码字面量筛选**。每个入口记录①是否调用 candidate 闸门、②是否对含因子列的 DataFrame 执行 `groupby` / `pivot` / `pivot_table`。产生因子聚合的入口必须 candidate 调用次数 > 0 且聚合输入满足五项（`len == 8`、`exp_id` 列长度 == 8、唯一数 == 8、集合恰为 8 个策略 id、不含对照）；未产生因子聚合的入口登记为 `not-factorial-entry` 并在报告中列出，**不静默跳过** | 新增 §12.3.5、§12.2 / S13 |
| R-31 | **未被探测到的入口可以中性通过 S13** | 第一版把 `not-probeable-signature`（签名不匹配）、`entry-error`（孤立调用抛异常）、以及「运行期没观测到聚合」一律记为 WARN 且不判 FAIL。于是任何**绕过闸门的入口只要在孤立调用中抛个异常**，就能以中性状态逃过验收；而「没观测到聚合」与「不可能聚合」是两件事，前者只是没触发到 | 每个被实际调用的入口必须获得**终局判定**，只有两个合格状态：`factorial-entry-pass`（观测到因子聚合 + candidate 被调用 + 所有聚合输入均为 8 个唯一策略行且不含对照）与 `not-factorial-entry`（**必须有机器证据**：静态可达性证明其调用链内不存在 `groupby` / `pivot` / `pivot_table`，且无 `getattr` 动态派发）。`entry-error`、`unknown-not-proven`、`not-probeable-signature` **一律 FAIL**。探测方式改为**按生产调用序列与数据流重放**（见 §12.3.5），从根上消除孤立调用造成的假 `entry-error`。「至少一个入口正确聚合」**不得**代替「所有实际因子入口均正确」——两条都是必要条件 | §12.2 / S13、§12.3.5 |
| R-32 | **排他创建成功后写入失败会留下半成品 fixture** | `open(path, "x")` 只保证「创建时文件不存在」。创建成功之后的 `write` 若因磁盘写满、编码错误或 `KeyboardInterrupt` 中断，磁盘上就留下一个**半写的 JSON**。它会让下一次生成因 `FileExistsError` 被拒（fixture 被永久卡死），更糟的是可能被误当作有效基线 | 落盘流程补齐失败清理（见 §12.6.1.3）：①最终文件 `write` → `flush` → `os.fsync`；②写入后**重新 `json.load` 最终文件**；③`FileExistsError` → 退出码 2、原 fixture 不变；④**其它任何异常**（含 `BaseException`）→ 若本次已创建最终文件则立即删除该文件，再删除临时文件，退出码 2；⑤只有全部成功后才删除临时文件并报告生成完成。**绝不让写入异常留下部分 JSON 文件** | §12.6.1.3 |

> **表内的取代关系**：R-31 取代 R-30 关于「未产生因子聚合的入口只登记不判 FAIL」的处置。现行规则以 §12.3.5.2 与 §12.2 / S13 为准：**每个被实际调用的入口都必须达到 `factorial-entry-pass` 或 `not-factorial-entry` 两个合格终局之一**，`not-probeable-signature` / `entry-error` / `unknown-not-proven` 一律 FAIL。R-30 行保留其原文，仅作修订历史。

**本轮只更新设计契约与测试预期，不修改 `run_experiments.py`。** `batch_exit_code` / `run_completed` 的生产实现属 TASK_003 实施阶段（§9 第 2 行的变更清单），在实施完成之前，S16 的这两条断言在正式模式下会 FAIL——这是预期的，符合 §12.1 第 2 步「测试先于实现定稿」。

---

# Kiro Spec Compatibility Map

> 本节仅为格式检查器提供模板小节的导航映射。**规范性内容全部在下方编号的 §1–§15 中**，
> 本节不定义任何新规则、不重复任何接口定义、不重复任何 unified diff。

## Overview

TASK_003 将旧的 12 标签矩阵重构为 **8 个澄清策略条件 + 1 个共同对照 = 9 个唯一配置**。
旧矩阵把唯一的对照复制成 4 份并给每份贴上 content/channel 标签，构成伪因子。

规范性详细内容见 **§1**（问题诊断）、**§2**（新 9 条件矩阵表）、**§15**（明确不修改的机制）。

## Architecture

总体结构由五个部分组成：`ExperimentConfig`（因子词表与校验）、矩阵生成、
Recording/Replay 运行编排、`simulation_core` 的对照守卫、以及分析端的对照过滤。

详细内容见 **§2**（矩阵）、**§7**（Recording/Replay 时序）、**§9**（文件清单）、**§10**（TASK_002 兼容性）。

## Components and Interfaces

组件与对应正文位置：

| 组件 | 正文位置 |
|---|---|
| `experiment_config.py` | §3–§5 |
| `run_experiments.py` | §7–§8 |
| `simulation_core.py` | §9 |
| `clarification_injector.py`（**本任务不修改**） | §6.3、§15 第 4 项 |
| `analysis` 脚本 | §9 |
| 验收测试 | §12 |

## Data Models

`ExperimentConfig` 的合法值、组合级约束、`exp_id`、`clarification_tick`、`is_control`
以及矩阵版本定义见 **§3–§6**。

TASK_002 `agent_records` schema v2.0 的兼容性见 **§10**。

## Correctness Properties

以下 7 条均为下方正文已定义内容的**引用**，非新增规则。可机器判定的完整验收性质见 **§12**（S1–S18）。

> **需求编号映射约定**：本规格为 Design-First，`requirements.md` 尚未生成。
> 下列 `Validates: Requirements N.M` 中的 `N` 对应用户下达的 7 项强制裁定
> （1 = 时机因子命名、2 = 共同对照编码、3 = 新矩阵、4 = exp_id 命名、
> 5 = Recording/Replay 设计原则、6 = 统计设计、7 = 兼容性要求），
> `M` 为该裁定下的子条目序号。生成 `requirements.md` 时按此映射对齐即可。

### Property 1: 矩阵基数唯一

**Validates: Requirements 3.1**

矩阵恰好 9 个唯一配置。规范定义见 §2，验收见 §12 / S1、S3。

### Property 2: 共同对照唯一

**Validates: Requirements 2.1, 3.2**

共同对照恰好 1 个，不可被复制。规范定义见 §3.2、§6.1，验收见 §12 / S2。

### Property 3: 策略条件完整交叉

**Validates: Requirements 3.1**

8 个策略条件构成完整 2×2×2（content × channel × timing）。规范定义见 §2，验收见 §12 / S2。

### Property 4: 共同对照不进入内部因子对比

**Validates: Requirements 6.1**

共同对照只参与 `any clarification vs common control`，不进入 2×2×2 的任何主效应或交互均值。
规范定义见 §6.4，验收见 §12 / S14。

### Property 5: immediate 首次处理 Tick 为 6

**Validates: Requirements 1.1**

规范定义见 §4（`scandal_tick + IMMEDIATE_OFFSET_TICKS`），验收见 §12 / S4。

### Property 6: delayed 首次处理 Tick 为 10

**Validates: Requirements 1.2**

延迟澄清 = 丑闻后 5 个 Tick。规范定义见 §4（`scandal_tick + DELAYED_OFFSET_TICKS`），验收见 §12 / S4。

### Property 7: 处理前轨迹与共同对照前缀逐值相等

**Validates: Requirements 5.2, 5.3**

每个策略组自身澄清前的轨迹等于共同对照的对应前缀（immediate → Tick 1–5，delayed → Tick 1–9），
判据为 `agent_records` 的**逐 Agent 逐 Tick 精确比较**（`avg_trust` 仅作汇总检查）。
规范定义与成立边界见 §7.4，判据细则见 §8.6，验收见 §12 / S15。

## Error Handling

非法 `ExperimentConfig` 组合、Replay 窗口内 miss（**fail-closed，抛 `ReplayAlignmentError`**）、
网络不一致、legacy 数据混入、以及产物版本不匹配的处理，分别见 **§3**、**§8**、**§11**、**§14**。

## Testing Strategy

S1–S18 验收测试、静态检查、确定性 Mock Router、逐 Agent 处理前轨迹相等性断言、
pre-TASK_003 行为不变性基线流程（§12.1），以及禁止真实 LLM 的要求，见 **§12**。

> This compatibility map is navigational only. Sections 1–15 contain the
> normative TASK_003 design. If wording appears to differ, the numbered
> sections govern.

---

## 1. 当前 12 标签矩阵的问题诊断

### 1.1 `delay-3` 名称与实现不一致（已核实）

`experiment_config.py`：

- L13：`VALID_TIMING_FACTORS  = {"immediate", "delay-3", "no-clarification"}`
- L66（docstring 自我承认）：`- delay-3:          丑闻后第 5 天（scandal_tick + 5），与 immediate 拉开足够间隔`
- L70–L74：

```python
        if self.timing_factor == "immediate":
            return self.scandal_tick + 1
        elif self.timing_factor == "delay-3":
            return self.scandal_tick + 5   # 从 +3 改为 +5，增强时机主效应的区分度
        return None
```

`scandal_tick` 默认 5（L30），因此 `delay-3` 的实际注入 Tick 为 **10**，即 `scandal + 5`。
标签宣称 3 天，实现是 5 天。**标签是论文图表与 CSV 的主键之一**，因此这是一个会直接写进论文的事实错误。

已核实的下游污染（三处都在按 `delay-3` 的**字面数字**重建时间轴，而非读取 `clarification_tick`）：

| 文件 | 行 | 当前代码 | 实际值 | 结论 |
|---|---|---|---|---|
| `analysis/plot_trajectories.py` | L73 | `clr_tick = {"immediate": scandal_tick, "delay-3": scandal_tick + 3}.get(timing)` | 应为 6 / 10 | 标注错位（immediate 画在 5，延迟画在 8） |
| `analysis/plot_trajectories.py` | L230 | `clr_tick = {"immediate": 5, "delay-3": 8}.get(timing)` | 应为 6 / 10 | 同上 |
| `analysis/plot_trajectories.py` | L287 | `clr_relative = {"immediate": 0, "delay-3": 3}.get(timing)` | 应为 +1 / +5 | 同上 |
| `analysis/plot_experiments.py` | L39 | `TIMING_LABELS = {… "delay-3": "Delay-3d" …}` | 实为 delay-5d | 图例文字错误 |

这四处是「把数字写进标签字符串」这一决策的**必然代价**：数字一旦进入标签，就会被复制到每一个字符串匹配点，而这些副本不会随 `clarification_tick` 的修改同步。

**`delay-3` 与 `delay-5` 在本设计中均不得作为采用值。** 下文出现 `delay-3` 之处，一律是对**已废弃历史标签**的引用（诊断与 legacy 判定必需）；`delay-5` 仅在附录 A 作为**被否方案**出现。

### 1.2 伪因子：4 个 NoClr 标签污染 content / channel 主效应（已核实）

`experiment_config.py` L83–L100：`product(content_levels, channel_levels, timing_levels)` = 2×2×3 = **12** 个配置，其中 4 个是 `timing_factor="no-clarification"`，各自仍携带 content/channel 标签。按 L52–L59 的拼接规则（L56：`timing_map = {"immediate": "Imm", "delay-3": "D3", "no-clarification": "NoClr"}`），这 4 个历史 `exp_id` 为
`Rational-Hub-NoClr` / `Rational-Random-NoClr` / `Empathy-Hub-NoClr` / `Empathy-Random-NoClr`（**均为已废弃历史标签**）。

**因果论证（为什么这会污染主效应估计）**

设 $Y$ 为恢复指标，$C\in\{\text{Rational},\text{Empathy}\}$、$H\in\{\text{Hub},\text{Random}\}$、$T$ 为时机。

1. **对照组的 content/channel 不是处理（treatment），而是标签。**
   在 `no-clarification` 条件下，`ClarificationInjector.should_inject()` 恒为 `False`（`clarification_injector.py`：`if self.clarification_tick is None: return False`），
   因此 `get_message()` 从不被调用，`CONTENT_TEMPLATES[content_factor]` 从不被读取——**没有任何一条澄清消息进入任何 inbox**。
   `channel_factor` 虽然仍在 `simulation_core.py` L638 触发 `select_target_nodes(...)`，但选出的节点只被标记为 target，不接收任何消息。
   也就是说：4 个对照条件的**数据生成过程完全相同**，其 $C$、$H$ 取值对 $Y$ 的因果效应恒等于 0（结构上为 0，不是「估计为 0」）。

2. **主效应估计因此被系统性稀释。**
   `analysis/plot_experiments.py` L110（`_bar_group`）的实现是 `grouped = df.groupby(factor_col)[metric_col].agg(['mean','std'])`，即 content 主效应 = 对 `content_factor` 取边际均值。在 12 条件矩阵下：

$$\widehat{\Delta}_C=\frac{1}{6}\sum_{T,H} Y_{\text{Rational}}-\frac{1}{6}\sum_{T,H} Y_{\text{Empathy}}$$

   其中 $T=$ 对照的 2+2 个单元对分子分母贡献的是**同一个数据生成过程**的两次实现。
   若不存在 LLM 采样噪声，这 2 个单元的差为 0，于是真实的内容效应被乘以 $2/3$（6 个单元中只有 4 个携带效应）——**方向不变、幅度被压缩 1/3**。
   若存在采样噪声（本项目存在：`RecordingRouter`/`ReplayRouter` 只对齐澄清前路径），这 2 个单元的差是**纯噪声**，被当作「内容效应的一次观测」计入均值，同时抬高 `std`（图 1 的 errorbar 直接来自它）。channel 主效应同理。

3. **交互项被结构性地写坏。**
   `plot_heatmap_interactions`（L162–L171）对 `('content_factor','timing_factor')` 与 `('channel_factor','timing_factor')` 建 pivot。
   两个对照单元在因果上必须相等，任何非零差都是噪声；而 pivot 会把它显示成一个「内容 × 时机交互」的色块。读者无法从图上区分「交互」与「噪声」。

4. **对照基线被切成两份，进一步放大问题。**
   `run_experiments.py` L120–L127 的 `ctrl_baseline` 按 **channel** 分组取对照终值：

```python
    ctrl_baseline: dict = {}   # channel → final_trust
    for r in results:
        if "error" in r:
            continue
        if r["config"].get("timing_factor") == "no-clarification":
            channel = r["config"].get("channel_factor", "hub")
            final_trust = r["trust_trajectory"][-1] if r.get("trust_trajectory") else 0.0
            ctrl_baseline[channel] = round(final_trust, 4)
```

   即 `trust_gain_vs_control`（L149–L151）用「同渠道的对照」作基线。但对照的 channel 无因果意义，
   于是 Hub 策略组和 Random 策略组被**两条只差噪声的不同基线**归一化——渠道主效应里混入了「两个基线之差」这一纯噪声量。
   注意该字典按 channel 覆写，2 个同 channel 的对照中**后写入者胜出**，取哪一个取决于结果列表顺序，这本身也是不可复现的。

**结论：4 个对照标签不是「冗余」，而是会同时（a）稀释 content/channel 主效应、（b）伪造 content×timing / channel×timing 交互、（c）把对照基线随机化的三重缺陷。**

### 1.3 其他已核实的关联缺陷（本任务顺带修复）

| # | 位置 | 事实 | 影响 |
|---|---|---|---|
| D1 | `run_experiments.py` L132–L141 | `summary.csv` 表头 16 列，错误行写 `writer.writerow([r["exp_id"]] + ["ERROR"] * 16)` = **17 格** | 任一实验失败即列数不齐，pandas 读取时错位/报错。**既存缺陷** |
| D2 | `run_experiments.py` L954–L955 | 调用 `_pt_traj.plot_timing_effect` / `_pt_traj.plot_content_channel`，而 `analysis/plot_trajectories.py` 实际定义的是 `plot_timing_comparison`（L79）/ `plot_content_channel_comparison`（L123） | `AttributeError` 被 L961 的 `except Exception` 吞掉 → **全部轨迹图静默缺失**。**既存缺陷** |
| D3 | `run_experiments.py` L732–L738 | 录制组固定为 `no-clarification + hub + rational-evidence`，依赖 4 个重复对照标签中的一个 | 新矩阵下该组合不再存在，必须重写（§7） |
| D4 | `run_experiments.py` L800 | `clr_tick = config.clarification_tick if config.clarification_tick else config.total_ticks + 1` —— 魔法值 `total_ticks + 1` 只为让无澄清组「全程回放」 | 新矩阵下唯一对照就是录制组，该分支及魔法值应彻底删除（§7.3） |

---

## 2. 新 9 条件完整矩阵表

固定参数（全部 9 条件相同，取自 `experiment_config.py` L26–L30）：
`random_seed=42`、`num_agents=20`、`total_ticks=30`、`scandal_tick=5`。
`budget_k`：策略条件 3；**共同对照 0**（理由见 §3.4）。

| # | exp_id | content_factor | channel_factor | timing_factor | clarification_tick | budget_k | 角色 |
|---|---|---|---|---|---|---|---|
| 1 | `Rational-Hub-Immediate` | `rational-evidence` | `hub` | `immediate` | **6** | 3 | 策略 |
| 2 | `Rational-Hub-Delayed` | `rational-evidence` | `hub` | `delayed` | **10** | 3 | 策略 |
| 3 | `Rational-Random-Immediate` | `rational-evidence` | `random` | `immediate` | **6** | 3 | 策略 |
| 4 | `Rational-Random-Delayed` | `rational-evidence` | `random` | `delayed` | **10** | 3 | 策略 |
| 5 | `Empathy-Hub-Immediate` | `emotional-empathy` | `hub` | `immediate` | **6** | 3 | 策略 |
| 6 | `Empathy-Hub-Delayed` | `emotional-empathy` | `hub` | `delayed` | **10** | 3 | 策略 |
| 7 | `Empathy-Random-Immediate` | `emotional-empathy` | `random` | `immediate` | **6** | 3 | 策略 |
| 8 | `Empathy-Random-Delayed` | `emotional-empathy` | `random` | `delayed` | **10** | 3 | 策略 |
| 9 | `NoClarification-Control` | `not-applicable` | `not-applicable` | `no-clarification` | **None**（落盘为 `""`） | 0 | **共同对照（唯一）** |

- 策略条件 = 8 = 2 × 2 × 2，完全交叉、平衡。
- 共同对照 = 1，**不带任何 content/channel 标签**，因此不可能进入 content/channel 的边际均值。
- `immediate = scandal_tick + 1 = 6`；`delayed = scandal_tick + 5 = 10`，即**延迟澄清 = 丑闻发生后 5 个 Tick，当前配置下为 Tick 10**。两个偏移量只以常量形式存在于 `experiment_config.py`，**不出现在任何标签字符串中**。
- 9 个 `exp_id` 全部使用完整词元；`Imm` / `D3` / `Del` / `NoClr` 等缩写一律废弃。

---

## 3. ExperimentConfig 合法值与验证规则（含组合级校验）

### 3.1 三层词表

```python
# 常量**名**用下划线：Python 标识符不允许出现连字符。
# 常量**值**必须是连字符形式 "not-applicable"。
NOT_APPLICABLE = "not-applicable"

CONTENT_LEVELS         = ("rational-evidence", "emotional-empathy")   # 真实水平
CHANNEL_LEVELS         = ("hub", "random")                            # 真实水平
STRATEGY_TIMING_LEVELS = ("immediate", "delayed")                     # 真实水平
CONTROL_TIMING         = "no-clarification"                           # 对照专用
CONTROL_EXP_ID         = "NoClarification-Control"                    # 对照专用

# 字段级合法值 = 真实水平 ∪ {NOT_APPLICABLE}
VALID_CONTENT_FACTORS = set(CONTENT_LEVELS) | {NOT_APPLICABLE}
VALID_CHANNEL_FACTORS = set(CHANNEL_LEVELS) | {NOT_APPLICABLE}
VALID_TIMING_FACTORS  = set(STRATEGY_TIMING_LEVELS) | {CONTROL_TIMING}
```

**关于「名」与「值」的显式说明（实施时最易混淆之处）**

| 层 | 写法 | 允许的形式 | 说明 |
|---|---|---|---|
| Python 常量名 | `NOT_APPLICABLE` | 下划线 | 标识符语法不允许连字符，**这是唯一允许出现下划线的地方** |
| 常量的值 | `"not-applicable"` | **连字符** | 落盘到 CSV / JSONL 的字面量 |
| 数据文件中的取值 | `not-applicable` | **连字符** | `agent_records.csv`、`experiment_metadata.jsonl`、`summary.csv`、`trajectories.csv` |

选连字符的**额外理由**：content / channel 的真实水平本身就是连字符风格（`rational-evidence`、`emotional-empathy`），哨兵值用连字符与同列其它取值的风格一致；混用下划线会在同一列内出现两种命名风格，给下游按分隔符切词的脚本埋一个不必要的分支。

**关键点：`CONTENT_LEVELS` 与 `VALID_CONTENT_FACTORS` 是两个不同的常量，且下游必须区分使用。**

- 需要「因子水平」的地方（主效应分组、交互 pivot、图例、模板查表）用 `CONTENT_LEVELS` / `CHANNEL_LEVELS` / `STRATEGY_TIMING_LEVELS`。
- 需要「字段合法性」的地方（`__post_init__`、CSV 值域校验）用 `VALID_*`。

这样 `not-applicable` 在类型层面就**不是一个因子水平**，任何遍历 `CONTENT_LEVELS` 的循环都不可能把它当成 Rational/Empathy 的一部分。

模块级断言（导入期即失败，不留给运行期）：

```python
assert all(not any(ch.isdigit() for ch in lv) for lv in STRATEGY_TIMING_LEVELS)
assert NOT_APPLICABLE == "not-applicable" and "_" not in NOT_APPLICABLE
assert NOT_APPLICABLE not in (set(CONTENT_LEVELS) | set(CHANNEL_LEVELS)
                              | set(STRATEGY_TIMING_LEVELS) | {CONTROL_TIMING})
assert not any(tok in CONTROL_EXP_ID for tok in ("Rational", "Empathy", "Hub", "Random"))
```

### 3.2 组合级校验规则（互斥的两条规则）

字段级检查无法表达本约束：`not-applicable` 对策略条件非法、对共同对照必需。合法性是**组合级**的。
`__post_init__` 分三段：

```pascal
段一（字段级）：
  REQUIRE content_factor ∈ VALID_CONTENT_FACTORS
  REQUIRE channel_factor ∈ VALID_CHANNEL_FACTORS
  REQUIRE timing_factor  ∈ VALID_TIMING_FACTORS
  REQUIRE num_agents > 0 AND total_ticks > 0 AND budget_k >= 0

段二（组合级）：
  IF timing_factor == CONTROL_TIMING THEN          // is_control
      REQUIRE content_factor == NOT_APPLICABLE     // 值为 "not-applicable"
      REQUIRE channel_factor == NOT_APPLICABLE
      REQUIRE budget_k == 0
  ELSE                                             // 策略条件
      REQUIRE content_factor ∈ CONTENT_LEVELS      // 显式拒绝 "not-applicable"
      REQUIRE channel_factor ∈ CHANNEL_LEVELS      // 显式拒绝 "not-applicable"
      REQUIRE budget_k > 0
  END IF

段三（自洽性）：
  IF clarification_tick IS NOT NULL THEN
      REQUIRE scandal_tick < clarification_tick <= total_ticks
  END IF
```

段三是新增的自洽检查：它使「改了 `scandal_tick` 或 `DELAYED_OFFSET_TICKS` 导致澄清落在仿真窗口外」这种错误在构造时就报错，而不是在指标计算阶段产出一条静默无澄清的曲线。

被组合级规则**明确拒绝**的错误编码（各对应一条验收断言，§12 / S6）：

| 错误编码 | 拒绝理由 |
|---|---|
| `content_factor=""`（空串） | 空串与「字段缺失 / 读取失败」不可区分 |
| `content_factor=None` | `None` 在 CSV 里写成空串，同上；且破坏 `str` 字段类型 |
| 对照携带 `rational-evidence` / `emotional-empathy` / `hub` / `random` | 正是 §1.2 要消灭的伪因子 |
| 策略条件携带 `not-applicable` | 澄清必须有真实内容与真实渠道 |
| 生成多个 `no-clarification` 配置 | 唯一共同对照不可被复制（§7 原则 1） |

### 3.3 派生属性

| 属性 | 语义 | 下游用途 |
|---|---|---|
| `is_control: bool` | `timing_factor == CONTROL_TIMING` | **下游一律用它判断对照，禁止再写 `== "no-clarification"` 字符串比较** |
| `exp_id: str` | §5 | CSV 主键 |
| `clarification_tick: Optional[int]` | §4 | 注入时机、回放边界、指标诊断 |

`is_control` 的引入是对「下游字符串匹配风险」的正面回答：任何未来的时机标签重命名都只影响 `experiment_config.py` 一处，`run_experiments.py` 与 `analysis/` 只依赖布尔属性 / `is_control` 列。

### 3.4 为什么共同对照强制 `budget_k == 0`

`budget_k=3` 对一个不投放的条件是第四个伪参数：`experiment_metadata.jsonl` 的 `budget_k` 列会声称「预算 3 个节点」，而实际投放 0 个。按 TASK_002 既定约定（`""` = 不适用，`0` = 真实的零），此处 **0 是真实值**（真的投放了 0 个节点），不是「不适用」，因此写 `0` 而非 `""` 是正确的。

**行为等价性（已核实，重要）**：把对照的选点跳过、`budget_k` 置 0，**不改变任何仿真行为**：

- `node_selector.select_target_nodes` 的 `random` 分支使用 `rng = random.Random(seed + 7777)`（**局部实例**），不触碰全局 `random` / `numpy` 随机流；`hub` 分支纯确定性。因此跳过该调用对 RNG 序列无影响。
- `injector.inject()` 在 `clarification_tick is None` 时于 `should_inject()` 即返回 `False`，`target_nodes` 是否为空不影响任何分支。
- `simulation_core.py` L704「澄清当天改写 `current_news`」的代码块以 `if injected_count > 0:` 为守卫，对照恒不进入。

唯一变化是**审计数据**：对照不再有 3 个被标记 `is_clarification_target=True` 却从未收到任何消息的 Agent。这正是要修掉的伪信息。

---

## 4. clarification_tick 映射

```python
IMMEDIATE_OFFSET_TICKS = 1
DELAYED_OFFSET_TICKS   = 5
```

```
clarification_tick =
    scandal_tick + IMMEDIATE_OFFSET_TICKS   if timing_factor == "immediate"        → 5 + 1 = 6
    scandal_tick + DELAYED_OFFSET_TICKS     if timing_factor == "delayed"          → 5 + 5 = 10
    None                                    if timing_factor == "no-clarification"
```

**固定表述（全文与论文、图例、结果文档必须一致）**

> **即时澄清 = 丑闻发生后 1 个 Tick，即当前配置下 Tick 6。**
> **延迟澄清 = 丑闻发生后 5 个 Tick，即当前配置下 Tick 10。**

`delayed` 是**理论实验因子名称**，它只承诺「晚于 immediate」；**具体延迟长度由 `clarification_tick` 提供**，而不是由标签提供。`delay-3` 与 `delay-5` 均不得作为采用值。

不变量（由模块级断言与验收项 S5 强制）：

1. `STRATEGY_TIMING_LEVELS` 中**任何标签都不得包含数字字符**：
   `assert all(not any(ch.isdigit() for ch in lv) for lv in STRATEGY_TIMING_LEVELS)`。
   这条断言把「名称内嵌数字」这一缺陷类型永久拒之门外。
2. 数字 5 只出现在 `DELAYED_OFFSET_TICKS` 这一处；`clarification_tick` 是唯一权威取值渠道。
3. 默认参数下 `immediate → 6`、`delayed → 10`，由验收项 S4 **精确数值**断言（不是断言 `scandal+5`，那是同义反复）。

写出位置（全部为既有列，**不新增任何字段**）：

| 产物 | 列 | 策略条件 | 共同对照 |
|---|---|---|---|
| `agent_records.csv`（60 列不变） | `clarification_tick_config` | 6 / 10 | `""`（既有代码 `simulation_core.py` L384–L386 已实现 None→`""`） |
| `experiment_metadata.jsonl`（18 字段不变） | `clarification_tick` | 6 / 10 | `""`（既有代码 `run_experiments.py` L428 已实现） |
| `run_metadata.json` | `experiments[].config.clarification_tick` | 6 / 10 | `null`（JSON 中 None → null，属 config 原样序列化） |

**`clarification_tick` 继续真实落盘**，不做任何推断式重建。

---

## 5. exp_id 生成规则

**规则（唯一、稳定、可读，全部使用完整词元）**

```pascal
IF is_control THEN
    exp_id ← CONTROL_EXP_ID           // 字面常量 "NoClarification-Control"
ELSE
    exp_id ← "{Content}-{Channel}-{Timing}"
      Content ∈ {"Rational", "Empathy"}
      Channel ∈ {"Hub", "Random"}
      Timing  ∈ {"Immediate", "Delayed"}
END IF
```

映射表（实现时的三个字面字典）：

```python
CONTENT_ID_TOKEN = {"rational-evidence": "Rational", "emotional-empathy": "Empathy"}
CHANNEL_ID_TOKEN = {"hub": "Hub", "random": "Random"}
TIMING_ID_TOKEN  = {"immediate": "Immediate", "delayed": "Delayed"}
CONTROL_EXP_ID   = "NoClarification-Control"
```

生成的 9 个 `exp_id`（与 §2 表逐字一致）：

```
Rational-Hub-Immediate      Rational-Hub-Delayed
Rational-Random-Immediate   Rational-Random-Delayed
Empathy-Hub-Immediate       Empathy-Hub-Delayed
Empathy-Random-Immediate    Empathy-Random-Delayed
NoClarification-Control
```

**四条性质**

- **唯一性**：8 个策略 id 由三个二值维度的笛卡尔积构成，天然互异；`NoClarification-Control` 与全部 8 个都不同（首词元 `NoClarification` 不在 `{Rational, Empathy}` 内）。矩阵生成函数用 `assert len({c.exp_id for c in configs}) == 9` 强制。
- **稳定性**：`exp_id` 只由三个因子水平决定，不含 Tick 数字、不含时间戳、不含 seed。`DELAYED_OFFSET_TICKS` 从 5 改成 4 也不会改变任何 `exp_id`——这正是拒绝 `delay-5` 命名的核心理由（附录 A）。
- **可读性**：完整词 `Immediate` / `Delayed` 不携带天数。天数在图表中通过 `clarification_tick` 在**渲染期**拼接（例如图例写 `Delayed (T10)`），数字来自数据而非标识符。
- **不可混淆（保留第 1 版论证，据裁定四更新断言）**：`NoClarification-Control` 中**不含** `Rational` / `Empathy` / `Hub` / `Random` 任一子串，因此任何**按词元过滤 `exp_id`** 的脚本都不会把共同对照归入某个因子水平。共同对照的 `exp_id` 也**不携带** content 或 channel 标签。验收项 S3 以子串检查强制：

```python
for token in ("Rational", "Empathy", "Hub", "Random"):
    assert token not in CONTROL_EXP_ID
```

  额外一条（新增，第 1 版没有）：`"Immediate"` 与 `"Delayed"` 同样不出现在 `CONTROL_EXP_ID` 中，因此按时机词元过滤也不会误收对照。注意 `NoClarification` 与 `no-clarification` 是同一事实的两种书写（id 词元 vs 因子值），二者的对应关系只在 `CONTROL_EXP_ID` / `CONTROL_TIMING` 这一对常量处定义。

**与历史标签的关系（相对第 1 版的实质改善）**

| 历史 12 标签（已废弃） | 新 9 标签 | 关系 |
|---|---|---|
| `*-Imm`（4 个） | `*-Immediate`（4 个） | 重命名，**字符串不同** |
| `*-D3`（4 个） | `*-Delayed`（4 个） | 重命名（且修正名实不符），**字符串不同** |
| `*-NoClr`（4 个） | 合并为 1 个 `NoClarification-Control` | 4 → 1，**字符串不同** |

第 1 版因保留 `Imm` 缩写，导致 4 个即时组的历史与新标签**同名**，行级无法区分新旧数据。裁定四改用完整词后，**新旧 9 / 12 个 `exp_id` 集合的交集为空**，因此除了 run 级版本闸门（§11）之外，还额外获得了一条**行级**可判定信号。run 级闸门仍是主判据（更早、更明确），行级信号作为兜底。

---

## 6. common control 编码及统计语义

### 6.1 编码方案（唯一共同对照，全部取连字符形式）

唯一合法编码：

```python
content_factor = "not-applicable"
channel_factor = "not-applicable"
timing_factor  = "no-clarification"
budget_k       = 0
```

| 载体 | content_factor | channel_factor | timing_factor | 其他 |
|---|---|---|---|---|
| `ExperimentConfig` | `"not-applicable"` | `"not-applicable"` | `"no-clarification"` | `budget_k=0`，`is_control=True`，`clarification_tick=None` |
| `agent_records.csv`（**60 列不变**） | `not-applicable` | `not-applicable` | `no-clarification` | `clarification_tick_config=""`；`is_clarification_target` 全 False；`clarification_injected` / `clarification_received` / `clarification_detected_by_plan` 全 False |
| `target_nodes.csv` | — | — | — | **0 行**（对照无目标节点）→ `not-applicable` 永不出现在该文件 |
| `experiment_metadata.jsonl`（**18 字段不变**） | `not-applicable` | `not-applicable` | `no-clarification` | `clarification_tick=""`，`budget_k=0`，`target_nodes=[]` |
| `summary.csv` / `trajectories.csv` | `not-applicable` | `not-applicable` | `no-clarification` | **新增 `is_control` 列 = True** |
| `run_metadata.json` | 同 config | 同 config | 同 config | 新增 run 级 `experiment_matrix` 块（§11） |

被禁止的替代编码（重申，验收项 S6 逐项反证）：空字符串；`None`；用 `rational-evidence` / `emotional-empathy` / `hub` / `random` 占位；生成多个 `no-clarification` 配置；以及**任何下划线写法** `not_applicable`。

### 6.2 下游「绝不把 not-applicable 当成因子水平」的三道防线

1. **词表分层**（§3.1）：所有按因子水平遍历的代码只引用 `CONTENT_LEVELS` / `CHANNEL_LEVELS` / `STRATEGY_TIMING_LEVELS`，`not-applicable` 不在其中。
2. **`is_control` 布尔列**：`summary.csv` / `trajectories.csv` 新增该列，`analysis/` 的主效应与交互一律先 `df = df[~df["is_control"]]`，而不是写 `df[df.timing_factor != "no-clarification"]`。
3. **值域断言**：`analysis` 的 loader 内加一条
   `assert "not-applicable" not in set(strategy_rows["content_factor"])`（channel 同理）；验收项 S13 对该断言做正反用例。

### 6.3 逐消费者影响核对（已核实）

| 消费者 | 是否读因子 | 影响 | 处置 |
|---|---|---|---|
| `metrics_calculator.compute_metrics` | **否**（签名只有 trajectory / scandal_tick / total_ticks / clarification_tick） | 无。`clarification_tick=None` 时 `clarification_effect` 已走 `if clarification_tick is not None` 分支 | **不修改**（指标口径属 TASK_004） |
| `node_selector.select_target_nodes` | 读 `channel`，`else: raise ValueError(f"Unknown channel strategy…")` | 若对照仍调用它并传 `not-applicable` → **抛异常** | 在 `simulation_core.py` L638 前加 `is_control` 守卫，跳过调用（§9 第 3 行 / §13.3） |
| `clarification_injector.ClarificationInjector` | `__init__` 读 `content_factor`；`get_message()` 查 `CONTENT_TEMPLATES[…]` | 运行期不可达（`should_inject()` 先返 False），**不会 KeyError**（已核实） | **本任务完全不修改**（R-11）。不加防御性 `raise`：「运行期不可达、不会 KeyError」这一已核实事实即是不需要护栏的依据；为一个不可达分支改动一个否则完全不动的文件，只会扩大 diff 面与回滚牵连范围 |
| `analysis/plot_experiments.py` | 是（L34–L39 三张色/标签字典，L110 groupby，L162 pivot） | `not-applicable` 会成为主效应图的第三根柱、交互热力图的第三行/列 | 必须改（§9 第 4 行 / §13.4） |
| `analysis/plot_trajectories.py` | 是（L32–L36 `TIMING_STYLE`，L134/136/190/214/273 字符串匹配，L73/230/287 时点字典） | 时机键失配 → `KeyError`（L276 直接下标）；12 面板结构失效 | 必须改（§9 第 5 行 / §13.4） |
| `analysis/analyze.py`、`analysis/plot.py`、`analysis/plot_trial.py` | **未匹配到任何 `timing_factor` / `no-clarification` / `delay-3`**（全库 grep 确认） | 无 | 不修改 |
| TASK_002 产物 `network_nodes.csv` / `network_edges.csv` | 不含因子列（5 列 / 3 列，已核实） | 无 | 不修改 |

### 6.4 统计语义（裁定六）

**共同对照只参与一个对比，不进入 2×2×2 的任何均值。**

> **共同对照不是第三个 timing 水平，也不是 content / channel 的缺失单元。**
> 它是「完全不澄清」这一独立的数据生成过程的唯一实现，`timing_factor="no-clarification"` 只是它在同一列里的书写方式，不代表它与 `immediate` / `delayed` 同属一个因子的三个水平。任何把它当作 timing 第三水平的分组（`groupby("timing_factor")` 直接出三根柱）都是错误口径。

#### 对比一：any clarification vs common control（唯一涉及对照的对比）

| 项 | 内容 |
|---|---|
| 处理组 | 8 个策略 exp_id 全体：`Rational-Hub-Immediate`、`Rational-Hub-Delayed`、`Rational-Random-Immediate`、`Rational-Random-Delayed`、`Empathy-Hub-Immediate`、`Empathy-Hub-Delayed`、`Empathy-Random-Immediate`、`Empathy-Random-Delayed` |
| 对照组 | `NoClarification-Control` |
| 对比 | $\bar Y_{\text{8 策略}} - Y_{\text{control}}$ |
| df | **1** |
| 用途 | 回答「澄清是否有用」，即澄清作为一个整体相对于不澄清的效应 |

#### 对比二至八：2×2×2 内部（**只用 8 个澄清条件**）

编码：content $C$（Rational = +1，Empathy = −1）、channel $H$（Hub = +1，Random = −1）、timing $T$（Immediate = +1，Delayed = −1）。每个对比都是 4 vs 4 的正交对照，df 均为 1。

| # | 对比 | (+) 组 | (−) 组 | df |
|---|---|---|---|---|
| 2 | **content 主效应** | `Rational-Hub-Immediate`、`Rational-Hub-Delayed`、`Rational-Random-Immediate`、`Rational-Random-Delayed` | `Empathy-Hub-Immediate`、`Empathy-Hub-Delayed`、`Empathy-Random-Immediate`、`Empathy-Random-Delayed` | 1 |
| 3 | **channel 主效应** | `Rational-Hub-Immediate`、`Rational-Hub-Delayed`、`Empathy-Hub-Immediate`、`Empathy-Hub-Delayed` | `Rational-Random-Immediate`、`Rational-Random-Delayed`、`Empathy-Random-Immediate`、`Empathy-Random-Delayed` | 1 |
| 4 | **timing 主效应** | `Rational-Hub-Immediate`、`Rational-Random-Immediate`、`Empathy-Hub-Immediate`、`Empathy-Random-Immediate` | `Rational-Hub-Delayed`、`Rational-Random-Delayed`、`Empathy-Hub-Delayed`、`Empathy-Random-Delayed` | 1 |
| 5 | **content × channel** | `Rational-Hub-Immediate`、`Rational-Hub-Delayed`、`Empathy-Random-Immediate`、`Empathy-Random-Delayed` | `Rational-Random-Immediate`、`Rational-Random-Delayed`、`Empathy-Hub-Immediate`、`Empathy-Hub-Delayed` | 1 |
| 6 | **content × timing** | `Rational-Hub-Immediate`、`Rational-Random-Immediate`、`Empathy-Hub-Delayed`、`Empathy-Random-Delayed` | `Rational-Hub-Delayed`、`Rational-Random-Delayed`、`Empathy-Hub-Immediate`、`Empathy-Random-Immediate` | 1 |
| 7 | **channel × timing** | `Rational-Hub-Immediate`、`Empathy-Hub-Immediate`、`Rational-Random-Delayed`、`Empathy-Random-Delayed` | `Rational-Hub-Delayed`、`Empathy-Hub-Delayed`、`Rational-Random-Immediate`、`Empathy-Random-Immediate` | 1 |
| 8 | **content × channel × timing** | `Rational-Hub-Immediate`、`Rational-Random-Delayed`、`Empathy-Hub-Delayed`、`Empathy-Random-Immediate` | `Rational-Hub-Delayed`、`Rational-Random-Immediate`、`Empathy-Hub-Immediate`、`Empathy-Random-Delayed` | 1 |

`NoClarification-Control` **不出现在对比 2–8 的任何一侧**。这是「共同对照不污染主效应」这一目标的可机器检查表述，验收项 S14 用集合断言强制：对比 2–8 的 (+) ∪ (−) 恒等于 8 个策略 exp_id 的集合，且不含 `CONTROL_EXP_ID`。

#### n=1 无重复下的可检验性（诚实标注）

- 8 个策略条件、每条件 1 次运行 ⇒ **8 个观测**。
- 饱和模型参数数 = 1（总均值）+ 3（主效应）+ 3（二阶交互）+ 1（三阶交互）= **8**。
- 观测数 8 = 参数数 8 ⇒ **残差自由度 = 0**。
- **结论：在 n=1 下，对比 2–8 全部是「精确复现数据的点估计」，没有任何一个可以做显著性检验。三阶交互与误差项无法同时估计**（8 条件 1 次运行时二者只能取其一）。
- 若坚持要一个误差项，唯一办法是把三阶交互**假定为 0** 并把它并入误差（得到 df=1 的误差项）。那样三阶交互就不再可检验。本设计要求论文明确标注采用了哪一种，且**不得同时报告三阶交互的估计值与基于该误差项的 p 值**。
- 对比一同样没有误差项（对照 n=1）。
- 另有一项**方差来源不对称**（不是偏差）：`immediate` 组从 Tick 6 起走真实 LLM（25 个 Tick 的采样噪声累积），`delayed` 组从 Tick 10 起（21 个 Tick）。因此 timing 主效应（对比 4）两侧的噪声累积长度不同，而 content / channel 主效应（对比 2、3）两侧各含 2 个 immediate + 2 个 delayed、噪声长度平衡。详见 §7.4。在 n=1 下这部分方差无法分离。

**所需重复数**（每个重复 = 一个新 `random_seed`，**一 seed 一 run 目录**，见 §7.6）

| n（每条件重复数） | 总运行数（9 条件） | 策略内残差 df | 可检验范围 |
|---|---|---|---|
| 1 | 9 | **0** | 无（仅描述性点估计） |
| 2 | 18 | 8 | 三阶 + 全部低阶可检验，功效极低 |
| 3 | 27 | 16 | 二阶交互与主效应可检验（**最低推荐**） |
| 5 | 45 | 32 | 主效应功效可接受 |

重复引入 seed 变化 ⇒ 网络拓扑随重复变化 ⇒ 网络效应（Hub vs Random）从「单一网络上的一次实现」变为「跨网络的平均效应」。这在因果解释上是**加强**（不再依赖某一张特定 BA 图），但要求分析层把 seed 作为**区组（block）因子**而非误差来源。本设计只作记录，具体分析模型属 TASK_004 范围。

---

## 7. Recording / Replay 详细时序

第 1 版「以 `Rational-Hub-NoClr` 作为录制组、其余 11 组回放」的逻辑**已整体废弃**（该组合在新矩阵中不存在，且它依赖被复制的对照）。本节给出裁定五要求的新方案。

### 7.1 八条原则的逐条落实

| # | 原则 | 本方案如何满足 | 证据/位置 |
|---|---|---|---|
| 1 | 唯一共同对照不能被复制 | 矩阵只生成 1 个 `is_control` 配置，`generate_experiment_matrix()` 断言 `len([c for c in configs if c.is_control]) == 1` | §3.2 段二 + §12 / S2 |
| 2 | 8 个策略组与共同对照的丑闻前路径可比较 | 9 条件共享 `random_seed=42`、`num_agents=20`、同一张网络、同一份被 patch 成「只保留 Tick 5」的事件时间线；Tick 1–5 无任何条件注入澄清 | §7.4(a) |
| 3 | 澄清前路径尽可能使用同一基线缓存 | 8 个策略组全部回放**同一份**共同对照缓存；immediate 组回放 Tick 1–5，delayed 组回放 Tick 1–9。**回放窗口内缓存 miss 一律 fail-closed**：立即抛 `ReplayAlignmentError`，**禁止降级调用真实 Router**（§8.5） | §7.2 时序表、§8.5 |
| 4 | immediate 组在 Tick 6 后开始分化 | `replay_until_tick = 6` ⇒ Tick 6 起走真实 LLM（澄清当天即分化） | §8.1 边界语义 |
| 5 | delayed 组在 Tick 10 后开始分化 | `replay_until_tick = 10` ⇒ Tick 10 起走真实 LLM | 同上 |
| 6 | no-clarification 全程不注入澄清 | `clarification_tick is None` ⇒ `should_inject()` 恒 False；`budget_k=0` 且跳过选点 | §3.4 |
| 7 | Recording/Replay 只用于控制共同随机与 LLM 路径，**不得把重复控制组伪装成独立样本** | 只有 1 个对照实验、1 条对照记录；不再存在「另外 3 个对照全程回放」这种把同一路径写成 4 行结果的做法 | §7.3 对比表 |
| 8 | 正式重复实验仍需多个独立 seed / LLM 路径，**Replay 不能替代重复实验** | 显式声明，见 §7.5；重复设计与 run 目录约束见 §7.6 | §7.5、§7.6 |

### 7.2 采纳方案：对照先录制，策略组回放至各自首次处理 Tick 之前

**评估结论：该方案无硬性技术障碍，采纳。** 现有 `ReplayRouter` 的边界语义正好等价于「回放到自己的处理 Tick 之前」，无需任何接口改动即可实现（逐行核实见 §8.1）。

执行顺序 = `[共同对照] + sorted(8 个策略组, key=exp_id)`（字典序，确定性、可复现）。

| 顺序 | exp_id | Router 角色 | `replay_until_tick` | 实际回放 Tick 区间 | 真实 LLM Tick 区间 | 澄清注入 Tick |
|---|---|---|---|---|---|---|
| 1 | `NoClarification-Control` | recording | —（不适用，无 ReplayRouter） | 无 | **1–30** | 无 |
| 2 | `Empathy-Hub-Delayed` | replay | **10** | 1–9 | 10–30 | 10 |
| 3 | `Empathy-Hub-Immediate` | replay | **6** | 1–5 | 6–30 | 6 |
| 4 | `Empathy-Random-Delayed` | replay | **10** | 1–9 | 10–30 | 10 |
| 5 | `Empathy-Random-Immediate` | replay | **6** | 1–5 | 6–30 | 6 |
| 6 | `Rational-Hub-Delayed` | replay | **10** | 1–9 | 10–30 | 10 |
| 7 | `Rational-Hub-Immediate` | replay | **6** | 1–5 | 6–30 | 6 |
| 8 | `Rational-Random-Delayed` | replay | **10** | 1–9 | 10–30 | 10 |
| 9 | `Rational-Random-Immediate` | replay | **6** | 1–5 | 6–30 | 6 |

第 2–9 行即 8 个策略 `exp_id` 的字典序（`Empathy-Hub-Delayed` < `Empathy-Hub-Immediate` < … < `Rational-Random-Immediate`）。

**回放边界总表（供实现直接对照）**

```
NoClarification-Control : router = RecordingRouter, replay_until = 不适用, 真实 LLM Tick 1–30
*-Immediate  (4 组)     : router = ReplayRouter,    replay_until = 6,      回放 1–5, 真实 6–30
*-Delayed    (4 组)     : router = ReplayRouter,    replay_until = 10,     回放 1–9, 真实 10–30
无任何组使用 replay_until = total_ticks + 1
```

`replay_until_tick` 恒等于该组的 `clarification_tick`，实现上直接写
`ReplayRouter(_real_router, llm_cache, replay_until_tick=config.clarification_tick)`，
并以 `assert config.clarification_tick is not None`（非对照必有澄清 Tick）替代 D4 的魔法值分支。

### 7.3 与旧方案的差异

| 项 | 旧（12 条件） | 新（9 条件） |
|---|---|---|
| 录制组 | `Rational-Hub-NoClr`（4 个重复对照之一，L732–L738） | `NoClarification-Control`（唯一对照） |
| 录制组选择依据 | 三个字符串同时匹配（content + channel + timing） | `cfg.is_control`（单一布尔属性） |
| 对照的回放 | 另外 3 个对照用 `replay_until_tick = total_ticks + 1`（L800）**全程回放**，产出 3 行与录制组只差噪声的「独立结果」 | **不存在**。只有 1 个对照，它就是录制组 |
| `total_ticks + 1` 魔法值 | 需要 | **彻底删除**（验收项 S9 断言无任何组使用它） |
| 「把重复控制组伪装成独立样本」的风险 | 存在（3 个全程回放的对照进入 `summary.csv`，并被 `groupby` 计入均值） | 结构上消除（原则 7） |

`total_ticks + 1` 的消失是本次重构的一个实质收益：它原本的唯一用途是「让没有 `clarification_tick` 的组也能全程回放」，而那些组之所以存在，正是因为对照被复制了 4 份。

### 7.4 「澄清前路径完全一致」这一对齐前提在新矩阵下成立到什么程度（诚实分析）

分三段，逐段给出成立范围与不成立之处。

**（a）Tick 1–5：全部 9 个条件逐 Agent 逐 Tick 完全一致。**
Tick 1–5 内没有任何条件注入澄清（最早的 `immediate` 在 Tick 6）。9 个条件共享 `random_seed=42`、`num_agents=20`、同一张网络（`network_hash` 由 `(num_agents, random_seed)` 决定，TASK_002 的 `verify_single_network()` 会验证而非假设）、同一份 patch 后的事件时间线。8 个策略组在这 5 个 Tick 全部命中共同对照缓存。
此外，`channel_factor` 的选点在澄清前不改变行为，且用局部 RNG（§3.4 已核实），因此 hub / random 两类策略组在 Tick 1–5 也完全一致。

**（b）Tick 6–9：4 个 `delayed` 组仍与共同对照完全一致，且这是正确的反事实。**
`delayed` 组在 Tick 6–9 尚未注入澄清，其「应然」轨迹恰好就是共同对照的轨迹（同一个数据生成过程）。回放共同对照在这 4 个 Tick 的响应**不是近似，而是正确的反事实**。因此 `delayed` 组的 Tick 1–9 = 共同对照的 Tick 1–9，逐值相等。

**（c）不成立之处：immediate 与 delayed 两组共享的缓存前缀只有 Tick 1–5。**
`immediate` 组自 Tick 6 起走真实 LLM，`delayed` 组自 Tick 10 起。因此：

| 对齐命题 | 是否成立 | 说明 |
|---|---|---|
| 「每个策略组自身的**澄清前**路径与共同对照逐值相同」 | **完全成立** | immediate 的澄清前 = Tick 1–5；delayed 的澄清前 = Tick 1–9。两者都是共同对照的前缀 |
| 「同一 timing 内不同 content/channel 的组，澄清前路径逐值相同」 | **完全成立** | 4 个 immediate 组共享 Tick 1–5；4 个 delayed 组共享 Tick 1–9 |
| 「immediate 组与 delayed 组在 Tick 6–9 共享同一条 LLM 路径」 | **不成立，且不应成立** | immediate 在 Tick 6 已受处理，其 Tick 6–9 必须是真实响应；强行复用缓存会把「有澄清」的输入配上「没有澄清」的响应 |
| 「immediate 与 delayed 的真实-LLM 噪声累积长度相同」 | **不成立** | 25 个 Tick vs 21 个 Tick |

**对 timing 主效应估计的影响（关键）**

- content 主效应（对比 2）与 channel 主效应（对比 3）：两侧各含 2 个 immediate + 2 个 delayed，**噪声累积长度平衡**，且两侧成对的组共享完全相同的缓存前缀。这两个主效应是「共同随机数」意义上的配对比较，采样噪声大部分被抵消。
- timing 主效应（对比 4）：(+) 侧全为 immediate（各 25 个真实-LLM Tick），(−) 侧全为 delayed（各 21 个）。两侧只共享 Tick 1–5 的缓存前缀，**Tick 6–9 一侧是真实响应、一侧是缓存响应**。因此 timing 主效应的点估计中混入了两部分不可分离的量：
  1. 真实的时机效应（澄清早晚导致的信任恢复差异）；
  2. 「真实-LLM 噪声累积长度差」带来的方差不对称。
- 结论：**timing 主效应的估计精度系统性低于 content / channel 主效应**，且在 n=1 下无法量化这部分差异。论文报告 timing 主效应时必须附带这一限制说明；要把它分离出来，唯一办法是重复实验（§7.5、§7.6），使每个条件都有多条独立 LLM 路径。
- 一个**不可采纳的伪解决方案**（记录以防日后重提）：让 immediate 组在 Tick 6–9 也回放缓存，以「对齐噪声长度」。这会用「无澄清」的响应冒充「有澄清后」的响应，直接销毁处理效应本身，是比方差不对称严重得多的偏差。

### 7.5 Replay 不能替代重复实验（显式声明）

> **Recording / Replay 的唯一作用是控制共同随机数与 LLM 路径，使不同条件在处理发生之前处于同一条实现路径上。它不产生任何新的独立样本。**
> **8 个策略组回放同一份共同对照缓存，不等于这 8 组各有一次独立重复；`n` 仍然是 1。**
> **正式的重复实验必须使用多个独立 `random_seed` / 独立 LLM 路径。Replay 在任何情况下都不能替代重复实验。**

据此，两条禁止项：

1. 禁止把「9 个条件各 1 次运行」称为 9 个样本并据此做任何显著性检验（§6.4 已给出 df=0 的算术依据）。
2. 禁止把「同一 run 内的多个回放组」当作重复：它们共享同一段缓存前缀，误差项相关，不满足独立性。

### 7.6 重复实验的硬约束：一 seed 一 run 目录

若要做重复（n ≥ 2），`random_seed` 必须变化；而 `random_seed` 同时决定网络拓扑，TASK_002 的 `verify_single_network()` 要求**同一个 run 目录内所有实验拓扑相同**，否则拒写 `network_nodes.csv` / `network_edges.csv`、写出 `network_inconsistency_report.json`，并以**退出码 3** 结束（`run_experiments.py` L977–L981，已核实）。

**因此重复设计必须是「一 seed 一 run 目录」**：每个 seed 跑完整 9 条件、产出独立 run 目录（含独立的共同对照录制），分析阶段跨目录聚合。
**不得在单个 run 内混入多个 seed**——那会直接触发 TASK_002 的 fail-closed 分支。这是硬约束，写入 §11 与 §14。

推论：每个 seed 的 run 内部都要重新录制一次共同对照（因为缓存键与该 seed 的路径绑定，见 §8.6），跨 run 复用缓存**不被支持也不应尝试**。

---

## 8. Replay 分叉与 cache miss 处理

### 8.1 现有 `ReplayRouter` 的逐行核实：**当前不支持分叉后录制**

`run_experiments.py` L81–L109 原文（逐行核对结果如下）：

```python
class ReplayRouter:
    """在 replay_until_tick 之前回放缓存，之后走真实 LLM"""

    def __init__(self, inner_router, cache: dict, replay_until_tick: int):   # L85
        self._inner = inner_router                                            # L86
        self._cache = cache                                                   # L87
        self._replay_until = replay_until_tick                                # L88
        self._current_tick: int = 0                                           # L89
        self._call_counts: dict = {}                                          # L90
        self.miss_count: int = 0                                              # L91

    def set_tick(self, tick: int):                                            # L93
        self._current_tick = tick                                             # L94
        self._call_counts = {}                                                # L95

    async def chat(self, prompt: str) -> str:                                 # L96
        pk = RecordingRouter._pk(prompt)                                      # L98
        count = self._call_counts.get(pk, 0)                                  # L99
        self._call_counts[pk] = count + 1                                     # L100

        if self._current_tick < self._replay_until:                           # L101
            key = (pk, self._current_tick, count)                             # L102
            if key in self._cache:                                            # L103
                return self._cache[key]                                       # L104
            self.miss_count += 1                                              # L105
            if self.miss_count <= 3:                                          # L106
                print(f"  ⚠️  [ReplayRouter] cache miss tick={self._current_tick}")  # L108
        return await self._inner.chat(prompt)                                 # L109
```

逐行结论：

| 行 | 事实 | 推论 |
|---|---|---|
| L87 | `self._cache = cache` —— 持有**外部传入的 dict 引用**（`main()` 里的 `llm_cache`） | 若写入该 dict 会污染其它组的回放基线；当前没有写入 |
| L101 | 回放窗口判定是 `_current_tick < _replay_until`（严格小于） | `replay_until_tick = clarification_tick` 精确表示「澄清当天及之后走真实 LLM」，符合原则 4 / 5 |
| L103–L104 | 命中缓存则 `return`，**只读，不写** | 回放路径不改变缓存 |
| L105–L108 | 未命中：`miss_count += 1`，仅前 3 次打印 | 之后**静默**落到 L109 |
| L109 | 回放窗口外（`_current_tick >= _replay_until`）与窗口内 miss 两种情形，**都**直接 `return await self._inner.chat(prompt)` | 真实响应**不写入任何 dict** |
| 全类 | 除 `miss_count` / `_call_counts` / `_current_tick` 外，无任何赋值语句写入缓存结构；无 `divergent_cache` 之类属性 | **`ReplayRouter` 不具备任何录制能力** |

对照 `RecordingRouter`（L51–L78）：只有它在 L73 执行 `self._cache[(pk, self._current_tick, count)] = response`，且它**没有**回放能力（无论 tick 为何都调真实 router）。

> **明确结论：现有实现中「处理前回放、处理后重新录制」不被支持。两个 Router 的能力是互斥的——`RecordingRouter` 只录不放，`ReplayRouter` 只放不录。分叉后（Tick ≥ `replay_until`）产生的真实响应不进入任何缓存，运行结束即丢失。本设计不假设该能力已存在。**

> **上表 L105–L109 描述的是当前工作树的既有行为（窗口内 miss 计数后落穿到真实 Router）。TASK_003 明确改掉这一条：窗口内 miss 改为 fail-closed，见 §8.5 与 §13.2。上表保留原样，因为它是「改之前是什么」的核实记录。**

### 8.2 采纳方案是否需要分叉后录制？

**不需要（对本矩阵的正确性而言）。** 理由：§7.2 的时序中，8 个策略组只回放**共同对照**的缓存，没有任何策略组需要回放另一个策略组的分叉后路径。回放的数据源只有一份，而它由 `RecordingRouter` 在共同对照上完整录制（Tick 1–30）。因此裁定五要求的时序**在不改动任何 Router 接口的前提下即可实现**——这就是 §7.2 所称「无硬性技术障碍」的具体含义。

分叉后录制只在以下两个**非必需**用途下有价值：

1. **跨进程复现**：把某个策略组分叉后的真实响应留档，使该组可在不调用 LLM 的情况下逐 Tick 重放（调试、审计复算、图表重绘）。
2. **未来的嵌套设计**：例如「先跑 immediate，再让某组回放 immediate 至 Tick 9」。本矩阵不需要，但若 TASK_004 之后引入新时机水平则可能需要。

因此本设计的**默认策略是：不录制分叉后响应**（等价于当前行为，零风险），同时给出最小接口调整规格，作为**默认关闭**的可选能力。

### 8.3 所需最小接口调整（两方案对比，推荐方案 B）

**方案 A：新增 `RecordingReplayRouter` 类**

```python
class RecordingReplayRouter:
    """回放窗口内读缓存；窗口外（分叉后）调真实 LLM 并录入独立的 divergent_cache。"""
    def __init__(self, inner_router, cache: dict, replay_until_tick: int): ...
```

- 优点：`ReplayRouter` 一字不改，行为零风险；新旧路径在类型层面即可区分。
- 缺点：`chat()` / `set_tick()` / `_pk` 逻辑与 `ReplayRouter` 重复 ~20 行，两份实现日后可能漂移；`main()` 里要多一个分支。

**方案 B（推荐）：给 `ReplayRouter` 增加一个默认关闭的开关 + 一个独立缓存属性**

```python
class ReplayRouter:
    def __init__(self, inner_router, cache: dict, replay_until_tick: int,
                 record_after_divergence: bool = False):     # 新增，默认 False
        ...
        self.record_after_divergence = bool(record_after_divergence)
        self.divergent_cache: dict = {}                       # 新增，永不写回 self._cache

    async def chat(self, prompt: str) -> str:
        pk = RecordingRouter._pk(prompt)
        count = self._call_counts.get(pk, 0)
        self._call_counts[pk] = count + 1

        if self._current_tick < self._replay_until:
            key = (pk, self._current_tick, count)
            if key in self._cache:
                return self._cache[key]
            # 窗口内 miss = 对齐前提已被打破 ⇒ fail-closed，见 §8.5
            self.miss_count += 1
            raise ReplayAlignmentError(exp_id=self._exp_id, tick=self._current_tick,
                                       replay_until=self._replay_until,
                                       miss_count=self.miss_count)

        response = await self._inner.chat(prompt)
        if self.record_after_divergence:
            self.divergent_cache[(pk, self._current_tick, count)] = response
        return response
```

三条不可协商的规则：

1. **`record_after_divergence=False` 时，控制流与 §8.5 规定的 fail-closed 语义逐语句等价**（本开关只影响**窗口外**是否留档，与窗口内的 fail-closed 分支完全无关）。默认值即 False ⇒ 采纳本方案不改变窗口外的任何可观测行为。
2. **`divergent_cache` 与 `self._cache` 严格分离，永不写回**。写回会把某个策略组的分叉后响应注入其它组的回放基线，直接摧毁 §7.4 的对齐前提。
3. **窗口内 miss 直接抛 `ReplayAlignmentError`，因此「窗口内 miss 是否录入 `divergent_cache`」这个问题不再存在**——控制流在计数后立即离开 `chat()`，既不会调用真实 Router，也不会产生任何可录制的响应。第 2 版此处写的是「窗口内 miss 不录」，第 3 版更强：**根本不存在窗口内 miss 的响应**。

**推荐方案 B 的理由**：改动面 = 1 个默认参数 + 1 个属性 + 1 个 `if`，无重复实现，且默认行为不变；方案 A 的收益（类型区分）可由 `router_role` 字段在审计层达成（§8.4）。

**本任务是否实施该调整**：**不实施**（§9 中标为「可选，默认不启用」）。理由是 §8.2——本矩阵不需要它，而 TASK_003 的原则是只做实验设计所必需的改动。规格写在此处，以便日后需要时不必重新推导。

### 8.4 对 TASK_002 三个审计字段的语义影响（取值规则不得被破坏）

三个字段位于 `EXPERIMENT_METADATA_FIELDS`（`run_experiments.py` L389），**字段数仍为 18，字段名与取值规则均不改变**：

| 字段 | TASK_002 既定取值规则 | 新矩阵下（不启用分叉录制） | 若启用分叉录制（方案 B） |
|---|---|---|---|
| `router_role` | 说明 `recording_cache_size` 的语义归属；共同对照 = `"recording"`，回放组 = `"replay"` | **规则不变**：唯一对照 → `"recording"`，8 个策略组 → `"replay"` | 策略组记 `"replay+record"`。这是**词表新增一个取值**，不改变「本字段说明 `recording_cache_size` 语义归属」这条规则；TASK_002 验收测试未对该字段做值域断言（已核实 L1547–L1571、L1803–L1808 只透传 `"replay"`） |
| `recording_cache_size` | 录制组 = `len(RecordingRouter.cache)`（产出规模）；回放组 = `len(llm_cache)` | **表达式不变**。诚实澄清一处既有语义张力：回放组写的是 `len(llm_cache)`，即该组**可用**的缓存规模（Tick 1–30 全量）；新矩阵下策略组只实际消费其中 Tick 1–5 / 1–9 的子集。**取值规则一字不改**，但文档中应把它读作「可用缓存规模」而非「已消费条数」 | 仍为 `len(llm_cache)`。`len(divergent_cache)` **不得**写入本字段，也**不得**新增字段（18 字段契约）——它只写入 `run_metadata.json` 的 `experiment_matrix` 同级块（该文件无字段数契约） |
| `replay_miss_count` | `ReplayRouter.miss_count`；录制组不适用 → `""`（与 `0` = 回放零 miss 严格区分） | **规则不变**：对照 → `""`，8 个策略组 → 整数。**fail-closed 后取值域收缩为 `{0, 1}`**：成功的策略组恒为 `0`；一旦出现窗口内 miss，`miss_count` 自增到 `1` 后立即抛 `ReplayAlignmentError`，该组进入失败分支，其元数据行记 `1` 且 `success=False`。**不可能出现 ≥ 2**——第 2 次 miss 永远不会被执行到 | 不变。分叉后调用**不计入** miss（它们不在回放窗口内），因此启用录制不会改变本字段取值 |

同时保持不变的既有约定：`""` 表示「不适用」，`0` 表示「真实的零」；两者在任何字段上都不得混用。

### 8.5 Replay 窗口内 miss 的处理：fail-closed（无「静默降级」一级）

miss 只可能发生在回放窗口内（`_current_tick < _replay_until`）。按 §7.4，新矩阵下**期望 miss 恒为 0**：immediate 组回放 Tick 1–5、delayed 组回放 Tick 1–9，这两段都是共同对照的正确反事实前缀，逐 Agent 逐调用都应命中。因此任何窗口内 miss 都是「澄清前路径对齐前提被打破」的信号，而不是可以容忍的性能事件。

**第 2 版的「L1 记录 + 仍降级调用真实 Router 继续跑」已整体废弃。** 降级的后果是：该组 Tick 1–5（或 1–9）里出现一个**不来自共同对照**的真实响应，此后其状态与对照分叉，但运行照常完成、结果照常写入 `summary.csv` 并进入 2×2×2 均值——一个已知失效的观测被当作有效样本使用。这比中断运行严重得多。

#### 8.5.1 语义规格（三条，均为强制）

**Replay 窗口内（`_current_tick < _replay_until`）缓存键不存在时：**

1. `miss_count += 1`；
2. **立即 `raise ReplayAlignmentError`**；
3. **禁止调用真实 Router 作为 fallback**（`self._inner.chat()` 在该分支内不出现）。

**Replay 窗口外（`_current_tick >= _replay_until`）**：正常调用真实 Router，且该调用**不计入** `miss_count`——它本来就应该走真实 LLM。这一点必须在实现注释中写明，避免把「正常分叉」误报为「对齐违约」。

#### 8.5.2 `ReplayAlignmentError` 的定义位置与最小定义

**定义位置**：`run_experiments.py` 模块级，紧接在「Recording / Replay Router」分节标题之后、`RecordingRouter` 之前。理由：它是 Router 契约的一部分，与两个 Router 同生命周期；放在此处使 `ReplayRouter.chat()` 与 `main()` 的 `except` 分支都能直接引用，无需新增模块，也不触碰 §15 列出的任何不修改文件。

**最小定义**：

```python
class ReplayAlignmentError(RuntimeError):
    """Replay 窗口内缓存未命中：澄清前路径与共同对照的对齐前提已被打破。

    fail-closed：绝不降级调用真实 Router。窗口内一旦 miss，该组 Tick 1..replay_until-1
    的轨迹就不再是共同对照的正确反事实前缀，其结果不可用于任何对比（§8.5、§8.6）。
    """

    def __init__(self, exp_id: str, tick: int, replay_until: int, miss_count: int):
        self.exp_id = exp_id
        self.tick = tick
        self.replay_until = replay_until
        self.miss_count = miss_count
        super().__init__(
            f"REPLAY ALIGNMENT VIOLATED: exp_id={exp_id} tick={tick} "
            f"replay_until={replay_until} miss_count={miss_count} — "
            f"refusing to fall back to the real router"
        )
```

配套的**唯一** `ReplayRouter` 构造签名变更：新增 `exp_id: str = ""` 参数并存为 `self._exp_id`，使异常自带归属信息。这不改变 `miss_count` / `divergent_cache` 之外的任何属性，也不影响 §8.4 的三个审计字段取值规则。

#### 8.5.3 分级表（fail-closed 语义，不存在「静默降级」这一级）

| 级别 | 触发条件 | 处置 |
|---|---|---|
| L0 正常 | 全部 8 个策略组均无窗口内 miss | 无动作；`experiment_metadata.jsonl` 逐策略行记 `replay_miss_count = 0`（不是 `""`），对照行记 `""` |
| L1 **实验级 fail-closed**（强制） | 某组在窗口内 miss | ①`miss_count` 自增至 `1`；②`raise ReplayAlignmentError`，**不调用真实 Router**；③`main()` 的 `except` 捕获后该实验进入**失败分支**：结果记 `error`、`error_type="ReplayAlignmentError"`、并**必须保留 `config`（`config.to_dict()`）与 `run_audit`**（与 TASK_002 / R12「失败实验最需要知道它是哪一组因子/什么 seed」的约定一致，见 §10.1 与 `run_experiments.py` 既有 `entry["config"] = r.get("config", {})` 分支）；④消息追加到 `errors.log`；⑤`run_metadata.json` 的 `experiment_matrix` 块记 `replay_alignment_violated: true` 与 `replay_miss_by_exp_id`。**该组轨迹不进入 `summary.csv` 的有效行**（只写 ERROR 占位行）、**不进入 `trajectories.csv` / `agent_records.csv`**（既有代码对 `"error" in r` 的行直接 `continue`）、**不参与对比 1–8 的任何一侧** |
| L2 **批次级非零退出**（强制；退出码值 4 为建议值） | 本批次存在任一 L1 | 批次以**非零退出码**结束，**建议退出码 4**（与 TASK_002 的退出码 3 = 网络一致性违约、0 = 正常相区分）。沿用 TASK_002 的次序原则：**在所有产物与图表安全落盘之后**再抛 `SystemExit(4)`，绝不因审计契约问题销毁已获得的实验证据 |

**明确禁止项（第 2 版残留的两种写法，本轮一律作废）**：

- 禁止「窗口内 miss 后 `return await self._inner.chat(prompt)`」——任何形式的 fallback。
- 禁止「只 `errors.append(msg)` 后继续把该组轨迹当作有效结果」——记录不等于隔离；该组必须走失败分支。

#### 8.5.4 与「不可判定」的区别

fail-closed 的对象是**已判定的违约**（键确实不存在），不是「不确定」。这与 §8.6 的键碰撞情形正好相反：碰撞时 `miss_count` 仍为 0、`chat()` 不抛错，只能由 S15 的逐 Agent 比较捕获。两者互补，缺一不可——**`miss_count == 0` 与 S15 通过必须同时成立，才算对齐前提被证实**。

### 8.6 缓存键的脆弱性：`miss == 0` 是对齐的必要但不充分条件

`RecordingRouter._pk`（L65–L67，已核实）：

```python
    @staticmethod
    def _pk(prompt: str) -> str:
        return str(hash(prompt[:200]) & 0xFFFFFFFF)
```

缓存键 = `(prompt 前 200 字符的哈希, tick, 该键在本 Tick 内的第几次调用)`。

- **进程内一致**：录制与回放在同一次 `main()` 调用内完成，`PYTHONHASHSEED` 相同，键稳定。**跨进程不可复用缓存**——本设计也不跨进程复用（§7.6）。
- **前 200 字符截断 + 调用序号**：多个 Agent 的 prompt 前缀可能相同，靠 `call_index`（本 Tick 内的调用次序）区分。只要状态相同，Agent 遍历顺序与调用顺序就相同，键一一对应。
- **脆弱点**：若状态一旦分叉，回放**不会 miss**，而会返回**另一个 Agent 的**响应（键仍然命中）。因此 `replay_miss_count == 0` 只是必要条件，不能证明对齐。

**据此设立一条运行期验收项（S15，需真实实验运行后核对，不属离线单测）。主要证据是 `agent_records` 的逐 Agent 逐 Tick 精确比较，`trajectories.csv` 的 `avg_trust` 只作汇总检查。**

**为什么 `avg_trust` 不足以作为唯一证据**：`avg_trust` 是 20 个 Agent 的均值。上述键碰撞的典型后果恰恰是**两个 Agent 的响应互换**——A 拿到了 B 的响应、B 拿到了 A 的响应。此时个体轨迹已经错位，而均值可能**逐值不变**（互换是对称的），甚至在数值上完全相等。也就是说 `avg_trust` 相等与「个体互换」是**相容的**，它无法排除本节所述的失效模式。把它当作唯一证据，等于用一个对目标失效模式不敏感的统计量去证明该失效模式不存在。

**比较键与比较范围**

| 项 | 规定 |
|---|---|
| 比较键 | `tick`、`agent_id`（二元组，逐行对齐；缺行/多行本身即为失败） |
| immediate 组 | Tick **1–5** 与共同对照的同键行比较 |
| delayed 组 | Tick **1–9** 与共同对照的同键行比较 |
| 容差 | **0**（精确相等；数值字段按落盘的十进制文本逐字比较） |

**精确比较字段（5 个）**

`trust_score_raw`、`shock_anchor_after_raw`、`quiet_ticks`、`is_buying`、`is_posting`

选这 5 个的理由：它们是**运行期状态的直接落盘**（前两个来自 `plan_result` 的未舍入 float，经 `_audit_float(…, 12)` 落到 12 位小数；后三个是整数/布尔，无精度问题），且与 TASK_002 行为不变性所比较的量**同源**——TASK_002 的 `COMPARED_FIELDS` 是 `trust_score` / `shock_anchor` / `quiet_ticks` / `is_buying` / `is_posting`（`tests/test_task002_observability.py` 已核实）。本项用 `_raw` 变体替换前两个，是因为 `trust_score` / `shock_anchor` 只保留 4 位小数，一个 1e-6 量级的分叉会被舍入掩盖；`_raw` 版本保留 12 位，远细于本模型任何有意义的数值差异。这样 S15 与 TASK_002 T10 在「比较什么」上保持一致，只在精度上更严。

**不得比较的字段（4 个）**

`is_clarification_target`、`content_factor`、`channel_factor`、`timing_factor`

理由：这 4 个按设计**本就应当不同**。共同对照的 content/channel 是 `not-applicable`、`timing_factor` 是 `no-clarification`、`is_clarification_target` 全为 False；策略组则携带真实水平且有 3 个目标节点被标记 True（`budget_k=3`，标记在 Tick 1 起即存在，与澄清是否已注入无关）。把它们纳入比较会产生**必然失败**，使 S15 变成一个永远红灯、因此毫无判别力的断言。

**汇总检查（降级项，保留但不作为唯一证据）**：对 `trajectories.csv` 断言
`avg_trust[tick 1..5]` 在全部 9 个 `exp_id` 上逐值相等；`avg_trust[tick 1..9]` 在共同对照与 4 个 `*-Delayed` 上逐值相等。它便宜、可先跑，用于快速发现粗粒度分叉；**通过它不构成对齐证明**。

若逐 Agent 比较失败而 `replay_miss_count == 0`，则几乎可以确定命中了上述「键碰撞返回他人响应」的情形。

---

## 9. 需要修改的文件清单

**生产文件只有 5 个（R-11 收窄）**：`experiment_config.py`、`run_experiments.py`、`simulation_core.py`、`analysis/plot_experiments.py`、`analysis/plot_trajectories.py`。
`clarification_injector.py` **已从实施清单中删除**，本任务对它不作任何改动（理由见 §6.3 该行与 §15 第 4 项）。

| # | 文件 | 类别 | 变更性质 | 风险 | 说明 |
|---|---|---|---|---|---|
| 1 | `experiment_config.py` | 生产 | **结构性重写**：三层词表（`NOT_APPLICABLE = "not-applicable"`）、组合级校验、`is_control`、完整词 `exp_id`、`clarification_tick` 常量化、9 条件矩阵生成、`EXPERIMENT_MATRIX_VERSION` | **中** | 实验设计的单一事实来源；改动面最大，但纯配置层，不含任何机制逻辑 |
| 2 | `run_experiments.py` | 生产 | ①新增 `ReplayAlignmentError`（§8.5.2）+ `ReplayRouter` 窗口内 miss 改 **fail-closed**（`raise`，无 fallback）+ 构造签名增 `exp_id`；②录制/回放配对重写（对照录制 + 8 组回放至各自 `clarification_tick`，删除 `total_ticks + 1`）；③`main()` 增 `except ReplayAlignmentError` 失败分支（保留 `config` / `error_type` / `run_audit`）+ 末尾 `SystemExit(4)`；④`ctrl_baseline` 单基线化；⑤`summary.csv` / `trajectories.csv` 增 `is_control` 列；⑥`run_metadata.json` 增 `experiment_matrix` 块；⑦修 D1 列数；⑧修 D2 函数名 | **中** | 涉及运行编排，但不触碰仿真内部 |
| 3 | `simulation_core.py` | 生产 | 仅在 L638 前加 `is_control` 守卫，跳过 `select_target_nodes`（约 3 行） | **低** | 已论证 RNG 中性、行为等价（§3.4） |
| 4 | `analysis/plot_experiments.py` | 生产 | 词表更新（`delayed` / 移除 `delay-3`）；主效应与交互一律 `df[~df["is_control"]]`；对照改为水平参考线；值域断言 | **低** | 仅出图，不影响数据 |
| 5 | `analysis/plot_trajectories.py` | 生产 | 词表更新；时点字典改为从 `clarification_tick` 推导（修正 L73 / L230 / L287）；`plot_all_12_strategies` → `plot_all_9_conditions`（4×2 策略面板 + 对照参考线） | **低** | 仅出图 |
| 6 | `tests/test_task003_experiment_matrix.py` | 测试（**新增**） | S1–S18 验收测试。**必须在应用任何生产 diff 之前创建完成**（§12.1 第 2 步） | **低** | 见 §12 |
| 7 | `tests/fixtures/task003/pre_task003_behavior_trace.json` | fixture（**新增**） | pre-TASK_003 行为基线。**必须在生产代码无未提交修改时生成**（§12.1 第 3 步），随后与测试**一起冻结** | **低** | 见 §12.1；与 TASK_002 fixture 各自独立、互不覆盖 |
| 8 | `tests/test_task002_observability.py` + `tests/fixtures/task002/pre_task002_behavior_trace.json` | 历史验收证据 | **永久冻结，一字不改**；不再纳入常规回归执行集 | — | 详见 §10.2（历史验收工具冻结与覆盖迁移） |
| 9 | `docs/kiro_tasks/TASK_003_result.md`、`docs/decisions/model_change_log.md` | 文档 | 实施阶段新增 / 追加 | 低 | **本设计阶段不得触碰**（`TASK_002_result.md` 与 `model_change_log.md` 已提交并推送，禁止修改） |

**可选但本任务不实施**：§8.3 方案 B 的 `record_after_divergence` / `divergent_cache`（默认关闭，本矩阵不需要）。注意 fail-closed（§8.5）**不是**可选项，它属于第 2 行的必做变更。

**明确不修改**：`clarification_injector.py`、`node_selector.py`、`metrics_calculator.py`、`generate_data.py`、`plugins/**`、`configs/**`、`analysis/analyze.py`、`analysis/plot.py`、`analysis/plot_trial.py`、`tests/test_task002_observability.py`、`tests/fixtures/task002/**`、`docs/kiro_tasks/TASK_002_result.md`、`docs/decisions/model_change_log.md`。完整清单见 §15。

---

## 10. 对 TASK_002 产物的兼容性

### 10.1 逐项核对（结论：字段数全部不变）

| TASK_002 断言 / 契约 | 位置 | 新矩阵下是否触发 | 结论 |
|---|---|---|---|
| `len(AGENT_RECORDS_FIELDS) == 60` | `simulation_core.py` L216 + `run_experiments.py` L192 | 不触发 | **`agent_records` 仍为 schema v2.0 / 共 60 字段，一个不增一个不减** |
| 字段唯一性 `len == len(set)` | 同上 | 不触发 | 不变 |
| `set(record.keys()) == set(AGENT_RECORDS_FIELDS)` | `simulation_core.py` L448 | 不触发（只改值，不改键） | 不变 |
| v1.0 21 字段相对顺序严格递增 | `tests` T3 | 不触发 | 不变 |
| `clarification_tick_config` 为 None 时写 `""` | `simulation_core.py` L384–L386 | 不触发（对照走 `""` 分支，正是既有实现） | 不变，`clarification_tick` **继续真实落盘** |
| `len(EXPERIMENT_METADATA_FIELDS) == 18` | `run_experiments.py` L380–L399 + `tests` | **不触发（前提：不新增字段）** | **本设计刻意不给 `experiment_metadata.jsonl` 加字段**；矩阵版本与 Replay 审计只写 `run_metadata.json` |
| `set(row.keys()) == set(EXPERIMENT_METADATA_FIELDS)` | `run_experiments.py` L455 | 不触发 | 不变 |
| `router_role` / `recording_cache_size` / `replay_miss_count` 取值规则 | `run_experiments.py` L389、L783–L807 | 不触发 | 取值规则不变，见 §8.4 |
| `NETWORK_NODES_FIELDS` 5 列 / `NETWORK_EDGES_FIELDS` 3 列、均不含 `exp_id` | `run_experiments.py` L288–L290 | 不触发 | 不变 |
| `verify_single_network()` → `consistent` | `run_experiments.py` L856 | 不触发（9 条件同为 `(20, 42)`） | 不变 |
| 行为不变性（信任公式 / Prompt / Persona / 网络生成 / 节点选择） | TASK_002 T10 | 不触发 | 本任务不改任何机制（§15） |

**`agent_records` 的 4 个因子列在共同对照下的取值（明确声明）**

| 列 | 策略条件 | 共同对照 |
|---|---|---|
| `content_factor` | `rational-evidence` / `emotional-empathy` | `not-applicable` |
| `channel_factor` | `hub` / `random` | `not-applicable` |
| `timing_factor` | `immediate` / `delayed` | `no-clarification` |
| `clarification_tick_config` | `6` / `10` | `""`（空串，**不是 0**，不是 `None` 字面量） |

**字段数是否改变：不改变。`agent_records` 仍为 60 字段，`experiment_metadata.jsonl` 仍为 18 字段。**

### 10.2 历史验收工具冻结与当前回归覆盖迁移

本节规定 TASK_002 验收工具的生命周期处置，以及 TASK_003 如何在**不重新生成任何 TASK_002 产物**的前提下承接长期契约。

#### 10.2.1 六条规定（全部为强制）

| # | 规定 |
|---|---|
| 1 | `tests/test_task002_observability.py` **保持永久不变（冻结）**。本任务与后续任务均不修改其一个字节 |
| 2 | `tests/fixtures/task002/pre_task002_behavior_trace.json` **保持永久不变（冻结）** |
| 3 | 二者作为 **TASK_002 提交状态的历史验收证据**而存在。证据目录 `results/task002_validation/20260801_101156/`：**270 断言 / 268 PASS / 0 FAIL / 2 WARN / 退出码 0** |
| 4 | TASK_003 **必须在应用生产 diff 之前**新增：`tests/test_task003_experiment_matrix.py` 与 `tests/fixtures/task003/pre_task003_behavior_trace.json`（严格顺序见 §12.1） |
| 5 | 新的 TASK_003 测试**承接**那些仍需长期保证的 TASK_002 核心契约（清单见 §10.2.3，归入验收项 **S18**） |
| 6 | **不重新生成 TASK_002 fixture，不修改其 `test_harness_sha256`** |

#### 10.2.2 为什么那个测试文件不能改（技术论证，第 2 版原文保留）

已核实的两处硬编码：

- L1521：`BAD_FACTORS = ("emotional-empathy", "random", "delay-3")      # → "Empathy-Random-D3"`
- L1851：`noclr = _fake_result(("rational-evidence", "hub", "no-clarification"), SC)`

新词表下：`delay-3` 不再是合法 `timing_factor`（字段级拒绝）；`("rational-evidence","hub","no-clarification")` 违反组合级规则（对照必须两项 `not-applicable` 且 `budget_k == 0`）。两者都会抛 `ValueError`。
调用点 `check_new_artifacts(v, RX, SC)` 与 `check_effective_timeline(v, RX, SC)`（L2154–L2155）**没有 try 包裹**（已核实）。

**两条路都被锁住**：T17 断言 `fixture["test_harness_sha256"] == harness_sha256()`（L2001–L2011），即测试文件自身哈希必须与 fixture 记录完全一致；而重新生成 fixture 需要回到 **pre-TASK_002** 代码状态（`assert_clean_production_tree` + `generated_from_commit` 的双重前置），TASK_002 的 diff 已应用并提交，该状态在当前分支上已不可复现。
即：**harness 哈希锁定 + fixture 无法在当前代码状态重新生成**，两者合起来使这份工具在词表变更后不可能被「修好」。

#### 10.2.3 结论：冻结 + 覆盖迁移

**结论不是「破坏」，而是「冻结 + 覆盖迁移」。**

`tests/test_task002_observability.py` 与其 fixture 是一次性验收工具，其设计目的是证明「TASK_002 的 diff 未改变既有行为」。该证明已在提交时完成并留档（§10.2.1 第 3 项）。工具的价值已经兑现，它此后作为**证据**而非**可执行回归**存在。

**冻结后该文件不再被纳入常规回归执行集**——它的 fixture 绑定 pre-TASK_002 代码状态，任何在当前代码状态下的执行结果都没有可解释的含义。**这是设计决定，不是缺陷。** 一份绑定历史代码状态的行为基线本来就不可能是持续回归基线；把它排除出执行集，是承认这个事实，而不是掩盖失败。

**长期契约的承接（不允许覆盖率净损失）**。以下 7 项由 `tests/test_task003_experiment_matrix.py` 接管，归入验收项 **S18**：

1. `AGENT_RECORDS_FIELDS` 长度 **60** 且无重复；
2. v1.0 21 字段相对顺序严格递增；
3. `EXPERIMENT_METADATA_FIELDS` 仍为 **18** 且键集合不变；
4. `build_agent_record()` 输出键集合 == 60 字段（对**共同对照**与**策略条件**各构造一次）；
5. 共同对照 `clarification_tick_config == ""`，且不是 `0`、不是 `int`；
6. `NETWORK_NODES_FIELDS` / `NETWORK_EDGES_FIELDS` 列契约不变、均不含 `exp_id`；
7. `router_role` / `recording_cache_size` / `replay_miss_count` 的 `""` 与 `0` 可区分性。

其中第 1–7 项的纯 schema 断言部分沿用既有编号 **S7**（语义不变），**S18** 在其之上补齐归属登记与 **pre-TASK_003 行为不变性比对**（新 fixture，见 §12.1）。两者引用同一份清单，不重复计数。

**两份 fixture 的关系**：`tests/fixtures/task002/pre_task002_behavior_trace.json` 与 `tests/fixtures/task003/pre_task003_behavior_trace.json **各自独立、互不覆盖**，位于不同目录、由不同测试文件读取、记录不同代码状态（前者 pre-TASK_002，后者 pre-TASK_003）。**TASK_002 的那份不被重新生成，其 `test_harness_sha256` 不被修改。**

**被否方案**（保留 `delay-3` 作为 deprecated 别名 + 放宽组合级规则，以让历史测试继续可执行）的代价：把本任务要消灭的两个缺陷（误导性名称、伪因子组合合法）永久保留在生产代码里，换取一份已完成使命的工具能继续跑。**不接受。**

---

## 11. legacy 数据迁移规则

### 11.1 run 级机器可判定判据（主判据）

在 `run_metadata.json` 顶层新增：

```json
"experiment_matrix": {
  "matrix_version": "3.0",
  "condition_count": 9,
  "strategy_condition_count": 8,
  "control_condition_count": 1,
  "control_exp_id": "NoClarification-Control",
  "content_levels": ["rational-evidence", "emotional-empathy"],
  "channel_levels": ["hub", "random"],
  "timing_levels": ["immediate", "delayed"],
  "control_timing": "no-clarification",
  "not_applicable_value": "not-applicable",
  "immediate_offset_ticks": 1,
  "delayed_offset_ticks": 5,
  "recording_exp_id": "NoClarification-Control",
  "replay_until_by_exp_id": {
    "Rational-Hub-Immediate": 6,
    "Rational-Hub-Delayed": 10,
    "Rational-Random-Immediate": 6,
    "Rational-Random-Delayed": 10,
    "Empathy-Hub-Immediate": 6,
    "Empathy-Hub-Delayed": 10,
    "Empathy-Random-Immediate": 6,
    "Empathy-Random-Delayed": 10
  },
  "replay_alignment_violated": false,
  "replay_miss_by_exp_id": {},
  "divergent_recording_enabled": false
}
```

注意 `"not_applicable_value": "not-applicable"` —— **键名**用下划线（JSON 习惯与常量名一致），**取值**是连字符字面量。这一条同时充当自我描述的版本证据。

判定规则（三条，任一命中即 legacy）：

```
legacy  ⟺  run_metadata.json 缺少 "experiment_matrix" 键
        ∨  experiment_matrix.matrix_version != "3.0"
        ∨  experiment_matrix.condition_count != 9
```

这与 TASK_002 用「缺少 `schema_version` 列」判定 v1.0 数据是同一手法：**用新增键的缺失作为版本证据**，无需回改任何历史文件。

### 11.2 行级辅助信号（用于已丢失 `run_metadata.json` 的目录）

| 信号 | 判定 |
|---|---|
| `summary.csv` 缺少 `is_control` 列 | legacy |
| `summary.csv` 出现 `timing_factor == "delay-3"` | legacy（`delay-3` 为已废弃历史标签） |
| `exp_id` 以 `-Imm` / `-D3` / `-NoClr` 结尾（历史缩写词元，已废弃） | legacy |
| `content_factor` 或 `channel_factor` 出现 `not_applicable`（**下划线**写法） | 非法/中间态数据，按 legacy 处置并报错——本设计从未产出过该写法 |
| 存在多于 1 行 `timing_factor == "no-clarification"` | legacy（对照被复制，v3.0 唯一对照只可能 1 行） |

裁定四改用完整词后，新旧 `exp_id` 集合**交集为空**（§5），因此行级信号不再存在第 1 版那种「4 个即时组新旧同名、行级无法区分」的盲区。run 级闸门仍是主判据（更早触发、更明确）。

### 11.3 处置：保留但隔离，绝不删除，绝不合并分析

1. 历史 `results/experiments/run_*` 目录**原样保留，不改一个字节**。
2. `analysis/` 的 loader 增加版本闸门：读入前检查 `experiment_matrix`；判为 legacy 时**拒绝**与 v3.0 数据同框，打印明确原因（而不是静默拼接）。多目录聚合时若 `matrix_version` 不唯一 → 报错退出。
   **新旧数据不得合并分析**，这是硬规则，不是建议。
3. 历史 12 标签结果统一标记为 **legacy**（矩阵 v1，12 条件）。
4. `results/experiments/latest/` 是快照目录，会被新 run 覆盖——这是既有行为，legacy 证据仍在带时间戳的 `run_*` 目录里。
5. **可选的物理隔离**（不含在本次 diff 内）：把历史目录移动到 `results/experiments/legacy/matrix_v1_12cond/`。这是**移动数据**，属需用户确认的操作，且完全可逆；本设计**不主动执行**，只作为建议记录。
6. 跨 seed 重复（§7.6）在 legacy 判定上是同一套规则：每个 seed 一个 run 目录，各自带 `experiment_matrix` 块；聚合时要求全部为 `matrix_version == "3.0"` 且 `condition_count == 9`。
7. 论文层面：第 5–6 章必须整体由 v3.0 run 重新生成；12 条件结果只能作为「设计缺陷诊断」的附录材料引用，**不得与 9 条件结果并列比较**。

---

## 12. 验收测试设计

新增 `tests/test_task003_experiment_matrix.py`。离线项无网络、不调用真实 LLM；运行期项需一次真实 run 的产物。

### 12.0 S 编号总表（S1–S18，连续无缺）

| # | 主题 | 类型 |
|---|---|---|
| S1 | 矩阵版本与基数（9） | 离线 |
| S2 | 对照唯一 + 策略 8 条完全交叉 | 离线 |
| S3 | 9 个 `exp_id` 精确集合与词元隔离 | 离线 |
| S4 | `clarification_tick` 精确数值 6 / 10 / None | 离线 |
| S5 | 时机标签无数字 + 全库无 `delay-3` / `delay-5` 采用值 | 离线 |
| S6 | 组合级校验反证（7 个非法编码） | 离线 |
| S7 | TASK_002 schema 契约断言（60 / 18 等，S18 的离线子集） | 离线 |
| S8 | 哨兵取值 `not-applicable` 与全库无下划线写法 | 离线 |
| S9 | 录制/回放配对 + `total_ticks + 1` 已删除 | 离线 |
| S10 | `ReplayRouter` 能力核实 **+ 子项 S10.1：窗口内 miss fail-closed 用例（R-8）** | 离线 |
| S11 | `summary.csv` 列契约与错误行格数（D1） | 离线 |
| S12 | `analysis/` 被调用函数名存在（D2） | 离线 |
| S13 | 分析层值域断言正反用例 | 离线 |
| S14 | 统计口径：对比 2–8 不含对照 | 离线 |
| S15 | **逐 Agent 处理前路径对齐**（主证据 `agent_records`；`avg_trust` 仅汇总） | **运行期** |
| S16 | 运行期产物（`run_metadata.json` / `experiment_metadata.jsonl` / `target_nodes.csv`） | **运行期** |
| S17 | legacy 闸门 | 离线 |
| S18 | **TASK_002 核心契约承接（§10.2.3 七项）+ pre-TASK_003 行为不变性** | 离线 |

### 12.1 pre-TASK_003 基线流程（不可调换的 7 步顺序）

本流程复用 TASK_002 已验证有效的机制，**顺序不可调换**：任何一步提前或推后都会使基线失去证据资格。

| 步 | 动作 | 不可调换的理由 |
|---|---|---|
| 1 | **提交 `design.md`** | 设计先于实现落定；fixture 的 `generated_from_commit` 才有一个可解释的设计快照与之对应 |
| 2 | **创建完整的 `tests/test_task003_experiment_matrix.py`** | 测试文件定义了 fixture 的全部输入（确定性 Router 返回值、场景字面常量、Tick 序列、比较字段），它本身就是输入的一部分。测试未定稿 ⇒ 输入未定稿 ⇒ fixture 无意义 |
| 3 | **在 pre-TASK_003 代码状态已被锚定时生成 fixture** | 基线必须是某个**已提交代码状态**的可复现快照。脏树或不可判定 ⇒ 快照来源不明 ⇒ 证据作废。**（R-29）仅工作树 clean 不够**：还必须由 `assert_pre_task003_generation_state()` 验证 fixture 尚不存在、`design.md` 已提交无改动、且 **HEAD 与 `PRE_TASK003_BASE_COMMIT` 在 `PRODUCTION_PATHS` 上的树内容完全一致、不存在净文件差异**（§12.6.1.2）。落盘本身采用排他创建（§12.6.1.3） |
| 4 | **fixture 记录**：`generated_from_commit`、`git_branch`、`git_is_dirty`、`test_harness_sha256`、`production_baseline_commit`、`fixture_generation_guard_version`、行为轨迹、关键生产文件哈希 | 缺任一项则无法在验证时判定「同输入、同代码史 + TASK_003 diff」这一前提。后两个字段（R-29）用于锚定「生产 diff 尚未应用」与「守卫强度」 |
| 5 | **单独提交**测试与 fixture | 与生产 diff 混提 ⇒ `generated_from_commit` 指向的提交里已含被测改动 ⇒ 基线自证循环 |
| 6 | 此后测试与 fixture **冻结** | `test_harness_sha256` 一旦写入即锁定输入定义；改测试 ⇒ 哈希不符 ⇒ 验证必失败（这正是 §10.2.2 中 TASK_002 遇到的锁） |
| 7 | **才允许**应用生产 diff | 顺序的全部意义所在：基线必须早于被测变更存在 |

**复用的 TASK_002 机制（逐项引用，全部已在 `tests/test_task002_observability.py` 中验证有效）**

| 机制 | TASK_002 实现 | TASK_003 复用要点 |
|---|---|---|
| 生产树洁净前置检查 | `assert_clean_production_tree()` + `collect_dirty_production_entries()`；**脏或不可判定 → 退出码 2**（fail-closed：「不知道代码状态」与「代码状态错误」对基线可信度而言后果相同） | 原样复用，`PRODUCTION_PATHS` 需覆盖本任务的 5 个生产文件；**故意排除 `tests/`**，否则第 3 步永远无法执行（测试此时尚未提交，会形成死锁）。**TASK_003 新增一道 TASK_002 没有的检查**：`assert_pre_task003_generation_state()` 的树内容锚定（§12.6.1.2 第 6 项），因为 TASK_002 的 fixture 生成时不存在「生产改动已被提交」这一风险面 |
| `git_is_dirty` 必须为 bool | `assert_provenance_determined()`：`"unknown"` **拒绝生成**（退出码 2）；**`True` 属预期且允许** | 原样复用。`True` 允许的理由：**测试文件按流程尚未提交**（第 2 步产出、第 5 步才提交），因此仓库级 `git_is_dirty` 可以为 `True`；而 **`design.md` 必须已经在第 1 步提交**。仓库级 dirty 与生产路径洁净是两件事 |
| `test_harness_sha256` | `harness_sha256()` + 验证期断言与 fixture 记录值**完全相同** | 原样复用；这是第 6 步「冻结」的技术实现 |
| commit 祖先关系 | `check_fixture_commit_ancestry()` 用 `git merge-base --is-ancestor <fixture_commit> HEAD`（退出码 0 = 是祖先或等于 HEAD；1 = 不是；其他 = 不可判定，同样 FAIL） | 原样复用；用于排除分支切换 / rebase / reset 导致的「基线与当前代码不在同一历史线上」 |

**pre-TASK_003 fixture 的行为轨迹应记录的字段**（与 §8.6 / S15 的 5 个精确比较字段对齐）：
`trust_score_raw`、`shock_anchor_after_raw`、`quiet_ticks`、`is_buying`、`is_posting`，逐 `(scenario, cluster_type, tick)` 记录，容差 **0**，比较对象为**运行期未舍入内存状态**（不经 CSV，沿用 TASK_002 的 `compare_source: "runtime_state_unrounded"` 约定）。
这样 S15（跨实验、逐 Agent）与 S18（跨代码状态、逐场景）比较的是**同一组量**，两项证据可以互相印证。

**与 TASK_002 fixture 的关系**：两份 fixture **各自独立、互不覆盖**——不同目录（`tests/fixtures/task002/` vs `tests/fixtures/task003/`）、不同读取者、不同代码状态。**TASK_002 的那份不被重新生成，其 `test_harness_sha256` 不被修改**（§10.2.1 第 6 项）。

### 12.2 验收项明细（S1–S18）

| # | 断言 | 期望 | 类型 |
|---|---|---|---|
| S1 | `EXPERIMENT_MATRIX_VERSION == "3.0"`；`generate_experiment_matrix()` 长度 == 9 | 9 | 离线 |
| S2 | 矩阵中 `is_control` 恰 1 条；策略条件恰 8 条；8 个策略条件 == `product(CONTENT_LEVELS, CHANNEL_LEVELS, STRATEGY_TIMING_LEVELS)` 的完整交叉 | 1 / 8 / 完全交叉 | 离线 |
| S3 | 9 个 `exp_id` 集合逐字等于 §2 表；无重复；`CONTROL_EXP_ID == "NoClarification-Control"` 且不含 `Rational` / `Empathy` / `Hub` / `Random` / `Immediate` / `Delayed` 任一子串 | 精确集合相等 | 离线 |
| S4 | `clarification_tick`：`immediate → 6`、`delayed → 10`、对照 `→ None`（**精确数值**，不写成 `scandal+5`） | 6 / 10 / None | 离线 |
| S5 | **旧标签作用域**（R-13，5 个面，AST + 符号白名单，**不做全库 grep**）：①`generate_experiment_matrix()` 生成的当前配置 `timing_factor` 不含旧标签；②`STRATEGY_TIMING_LEVELS` 无数字字符且取值为 `(immediate, delayed)`；③当前 `exp_id` 不含 `D3` / `Delay-3` / `Delay-5`；④`experiment_config.py` 的活跃因子常量（`CONTENT_LEVELS` / `CHANNEL_LEVELS` / `STRATEGY_TIMING_LEVELS` / `CONTROL_TIMING` / `CONTROL_EXP_ID` / `VALID_*` / `*_ID_TOKEN`）不采用旧标签；⑤`analysis` 的当前图例（`TIMING_COLORS` / `TIMING_LABELS` / `TIMING_STYLE` 等）、当前分组与当前时点映射 dict 不采用旧标签。**豁免清单见 §12.3** | 5 个面全通过 | 离线 |
| S6 | 组合级校验反证：对照带真实 content/channel → `ValueError`；策略条件带 `not-applicable` → `ValueError`；`content_factor=""` → `ValueError`；`content_factor=None` → `ValueError`；对照 `budget_k=3` → `ValueError`；策略条件 `budget_k=0` → `ValueError`；`clarification_tick > total_ticks` → `ValueError` | 全部抛错 | 离线 |
| S7 | TASK_002 契约接管清单 7 项（§10.2.3）的**纯 schema 断言**全部通过，其中字段数断言为 **60** 与 **18**（语义与第 2 版一致；归属登记与行为不变性见 S18） | 全通过 | 离线 |
| S8 | 哨兵取值：`NOT_APPLICABLE == "not-applicable"`；`"_" not in NOT_APPLICABLE`；三层词表分离（`CONTENT_LEVELS` vs `VALID_CONTENT_FACTORS` 等）。**并且**（R-14）：只在生产 Python 的 **AST 精确字符串字面量**中检查 `"not_applicable"` 是否被用作当前字段值，**不做子串匹配**。合法且不得误判的四类见 §12.3 | 断言通过 | 离线 |
| S9 | 录制/回放配对：录制组 == `CONTROL_EXP_ID`；8 个策略组 `replay_until_tick == clarification_tick`（4 个 6、4 个 10）；**无任何组使用 `total_ticks + 1`**（源码级 grep 断言该表达式已删除） | 断言通过 | 离线 |
| S10 | **`ReplayRouter` 行为契约**（R-15，不绑定任何实现细节属性）：①窗口内命中缓存时真实 Router 调用数为 **0**；②窗口内 miss 时 `miss_count` 增加 1、抛 `ReplayAlignmentError`、真实 Router 调用数为 **0**；③窗口外真实 Router 正常调用；④窗口外调用不增加 `miss_count`；⑤**所有路径均不得修改共同对照基线 cache**（逐路径与快照做整字典相等比较）。已删除对 `divergent_cache` / `record_after_divergence` 存在性的断言 | 5 条全通过 | 离线（mock inner router） |
| **S10.1**（S10 的子项，不占新编号） | **窗口内 miss fail-closed（本轮新增，5 项子断言）**：构造回放缓存后**删除一个 Replay 窗口内的缓存键** ⇒ ①`chat()` 抛 `ReplayAlignmentError`；②**真实 Router 没有被调用**（mock inner router 的调用计数断言 `== 0`）；③`miss_count == 1`；④窗口外（`tick >= replay_until`）调用仍正常返回且 `miss_count` 不变；⑤模拟 `main()` 的失败分支后，失败元数据仍保留**完整 `config`**（`config.to_dict()` 的全部键，含 `content_factor` / `channel_factor` / `timing_factor` / `random_seed` / `budget_k`）、`error_type == "ReplayAlignmentError"`、`run_audit` 非空 | 5 项全通过 | 离线（mock inner router，无网络） |
| S11 | `summary.csv` 列契约：表头含 `is_control`；错误行格数 == 表头格数（D1 修复，用 `len(SUMMARY_FIELDS)` 派生而非字面 16） | 相等 | 离线 |
| S12 | `analysis/plot_trajectories.py` 与 `plot_experiments.py` 中被 `run_experiments.py` 调用的函数名全部存在（D2 修复，用 `hasattr` 断言） | 全部存在 | 离线 |
| S13 | **分析层功能闸门**（R-16，**不限定 helper 函数名称或内部组织方式**）：①输入 8 个策略行 + 1 个共同对照；②分析入口实际只返回 / 使用 8 个策略行；③共同对照不进入主效应与交互计算；④若 `is_control=False` 但 content/channel 为 `not-applicable`，必须抛错。已删除「生产代码必须存在名为 `_strategy_rows` 的函数」这一断言。**探测范围六条约束与按模式分档的判定见 §12.3.4**：`--offline-only` 下依赖不可用可 WARN；`--runtime-dir` 正式验收下依赖不可用、无可验证闸门、或无法完成策略行过滤验证一律 **FAIL**。**候选判定为六项同时满足（R-26）**：`len(out) == 8`、`exp_id` 列长度 == 8、`exp_id` 无重复、集合恰为 8 个策略 id、不含对照、反例必须抛错——**不得只用 `set(out["exp_id"])` 判断**，集合会折叠重复行。**⑤集成验证（R-30，见 §12.3.5）**：对 `run_experiments.py` 实际调用的**全部** `plot_experiments` 入口做运行期探测（**不按源码字面量筛选**）。探测按**生产调用序列与数据流重放**（§12.3.5.1）。**每个被实际调用的入口必须获得终局判定（R-31）**，合格状态只有两个：`factorial-entry-pass`（观测到因子聚合 + candidate 被调用 + 所有聚合输入均为 8 个唯一策略行且不含对照）与 `not-factorial-entry`（有静态可达性**机器证据**证明其调用链不做因子聚合、且无 `getattr` 动态派发）。`factorial-entry-fail` / `entry-error` / `unknown-not-proven` **一律 FAIL**，不得中性放过。另需至少一个入口为 `factorial-entry-pass`——但该条**不得代替**「所有入口均达合格终局」 | 全部入口达合格终局 | 离线 |
| S14 | 统计口径：对比 2–8 的 (+)∪(−) 恒等于 8 个策略 `exp_id` 集合，且**不含** `CONTROL_EXP_ID`；对比 1 的对照侧恰为 `{CONTROL_EXP_ID}` | 集合相等 | 离线 |
| S15 | **逐 Agent 处理前路径对齐（主要证据），三层递进（任一层不成立即停止下一层）**：**第一层（R-23，fail-closed）**统计每个 `(exp_id, tick, agent_id)` 的出现次数，必须恰好为 1，绝不用字典赋值静默覆盖重复行；**第二层（R-27）**构造**绝对预期键空间** `9 exp_id × Tick 1..total_ticks × network_nodes.csv 的 agent_id`，断言 `actual_keys == expected_keys`、`missing_keys` / `extra_keys` 为空、每键 `count == 1`（`count == 0` 只能靠这一层发现，见 §12.5.3）；**第三层**在处理前窗口内按键 `(tick, agent_id)` 逐行对齐并**精确比较 5 个字段**——`trust_score_raw`、`shock_anchor_after_raw`、`quiet_ticks`、`is_buying`、`is_posting`（容差 0）。范围：4 个 `*-Immediate` 组的 **Tick 1–5**、4 个 `*-Delayed` 组的 **Tick 1–9**，各自与共同对照 `NoClarification-Control` 的同键行比较；缺行 / 多行本身即为失败。**明确不比较** `is_clarification_target`、`content_factor`、`channel_factor`、`timing_factor`（按设计本就应当不同，比较即必然失败）。**汇总检查（降级项，不得作为唯一证据）**：`trajectories.csv` 中 `avg_trust[tick 1..5]` 在 9 个 `exp_id` 上逐值相等、`avg_trust[tick 1..9]` 在对照与 4 个 `*-Delayed` 上逐值相等 | 逐 Agent 逐 Tick 精确相等 | **运行期** |
| S16 | 运行期产物：`run_metadata.json` 含 `experiment_matrix` 块且 `matrix_version=="3.0"` / `condition_count==9`；**`batch_exit_code == 0` 且 `run_completed is True`（R-24，机器可读，取代原先「人工观察进程退出码」的 WARN）**；`experiment_metadata.jsonl` 恰 9 行、18 键；对照行 `clarification_tick == ""` 且 `replay_miss_count == ""`；8 个策略行 `replay_miss_count == 0`；`target_nodes.csv` 中不含对照 `exp_id`；`experiment_matrix.replay_alignment_violated == false`；进程退出码 **0**（若为 4 则本批次存在 Replay 对齐违约，S15/S16 一并判 FAIL） | 全部满足 | **运行期** |
| S17 | legacy 闸门：构造一个缺 `experiment_matrix` 的假 `run_metadata.json` → loader 判 legacy 并拒绝聚合；构造 `matrix_version="3.0"` 但 `condition_count=12` → 同样判 legacy | 双向通过 | 离线 |
| S18 | **TASK_002 核心契约承接与 pre-TASK_003 行为不变性**：①§10.2.3 的 7 项契约全部由本测试覆盖（归属登记 + 断言执行，其纯 schema 部分与 S7 共用同一份清单）；②读取 `tests/fixtures/task003/pre_task003_behavior_trace.json`，断言 `test_harness_sha256` 与当前测试文件哈希**完全相同**、`git_is_dirty` 为 **bool**、`generated_from_commit` 为 40 位 hex 且为 HEAD 的祖先（或等于 HEAD）；③逐 `(scenario, cluster_type, tick)` 精确比较 5 个字段（与 S15 同一组量，容差 0，比较对象为运行期未舍入内存状态）；④断言 `tests/fixtures/task002/**` 与 `tests/test_task002_observability.py` **未被本任务改动**（哈希与 TASK_002 记录一致），即冻结生效；⑤**`baseline_file_sha256` 逐项校验（R-28）**：字段存在且为 dict、键集合恰为三个 Agent 插件（`ConsumerPlanPlugin.py` / `GreenCognitionPlugin.py` / `GreenInvokePlugin.py`）、每个记录值是 64 位 SHA-256、且**等于当前文件的 SHA-256**。fixture 存在而哈希不符时两种模式**同样 FAIL**；⑥**生产基线锚点（R-29）**：`production_baseline_commit` 为 40 位 SHA、与测试常量 `PRE_TASK003_BASE_COMMIT` 完全相等、且为当前 HEAD 的祖先；`fixture_generation_guard_version == "2.0"`（版本不符 = 该 fixture 由更弱的前置检查生成） | 全通过 | 离线 |

S15 是 §8.6 所述「miss 计数不充分」的补强：`miss_count == 0` 只排除「键不存在」，逐 Agent 比较才能排除「键碰撞返回他人响应」。**两者必须同时成立**（§8.5.4）。

### 12.3 判据作用域：为什么不做全库字符串扫描（R-13 / R-14 / R-15 / R-16）

四项判据在第 3 版都写成了「全库不存在某字符串」或「必须存在某名字的实现」。这两类断言有同一个毛病：**它们检查的是文本，而要保证的是行为**。后果分别是假阳性与实现锁定。

#### 12.3.1 旧标签的合法栖息地（S5 的豁免清单）

`delay-3` / `delay-5` / `-Imm` / `-D3` / `-NoClr` 在以下语境中**必须允许存在**，否则 §11 的 legacy 迁移规则根本无法实现——**legacy 检测逻辑必须认识旧标签，才可能识别历史数据**：

| # | 允许出现的位置 | 理由 |
|---|---|---|
| 1 | `LEGACY_*` 前缀的常量 | 旧标签的清单本身就是迁移判据的一部分 |
| 2 | `is_legacy_run()` 及任何 legacy 检测逻辑（判定依据：所在符号名含 `legacy`） | §11.1 / §11.2 的行级信号需要匹配旧标签 |
| 3 | 验收测试中的反例输入 | S6 需要用 `delay-3` 反证「已废弃标签必须被拒绝」 |
| 4 | 设计文档与历史文档 | 本文档 §1.1 / §1.2 / §5 / §11.2 大量引用旧标签作为诊断材料 |

因此 S5 改为检查**5 个「当前生效」的面**，实现手段为 AST 定向读取 + 符号白名单：

| 面 | 检查对象 | 手段 |
|---|---|---|
| 1 | `generate_experiment_matrix()` 返回的 9 个配置的 `timing_factor` | 运行期取值，取值集合必须 ⊆ `{immediate, delayed, no-clarification}` |
| 2 | `STRATEGY_TIMING_LEVELS` | 无数字字符；取值 == `(immediate, delayed)` |
| 3 | 当前 9 个 `exp_id` | 不含子串 `D3` / `Delay-3` / `Delay-5` |
| 4 | `experiment_config.py` 的活跃因子常量 | AST 读模块级赋值，收集其中的字符串字面量；名称含 `legacy` 的常量跳过 |
| 5 | `analysis` 的当前图例 / 分组 / 时点映射 | AST 读上述常量 + 收集**以时机为键的 dict 字面量**（含函数体内），所在函数名含 `legacy` 者豁免 |

面 5 的「以时机为键的 dict 字面量」正是 §1.1 表中四处缺陷的机器可判定形态：`{"immediate": …, "delay-3": …}` 会被捕获，而 legacy 语境下的同形字典不会。

#### 12.3.2 下划线哨兵的精确判据（S8）

只检查一件事：**生产 Python 的 AST 中，精确字符串字面量 `"not_applicable"` 不得作为当前字段值**。扫描范围为 8 个生产 Python 文件（`experiment_config.py`、`run_experiments.py`、`simulation_core.py`、`clarification_injector.py`、`node_selector.py`、`metrics_calculator.py`、`analysis/plot_experiments.py`、`analysis/plot_trajectories.py`）。

以下四类**合法，不得误判**——注意前两类在精确字面量比较下天然不会命中，这正是改用 AST 的收益：

| 合法项 | 为什么不会被误判 |
|---|---|
| `NOT_APPLICABLE` | 它是**标识符**，不是字符串常量，AST 里根本不是 `Constant` |
| `"not_applicable_value"`（§11.1 的 JSON 键名） | 与 `"not_applicable"` 是**两个不同的字面量**，精确比较不相等 |
| 历史文档中的说明文字 | 非 Python，不在扫描范围内 |
| 测试中的非法输入反例 | 测试文件不在扫描范围内（S6 需要用它反证拒绝行为） |

legacy 检测逻辑（所在符号名含 `legacy`）中出现该字面量属预期，豁免并在报告中列出。

#### 12.3.3 为什么 S10 不再断言实现细节属性

第 3 版断言「实例无 `divergent_cache` 属性」「`record_after_divergence` 缺省不存在」。这把测试焊死在一种特定实现上：任何等价重构（例如把开关放进构造参数、或改用组合而非属性）都会让测试失败，而**行为并未改变**。

要保证的后果只有一个：**分叉后不写共同对照基线缓存**。它是可观测的——基线 cache 是 8 个策略组共享的唯一数据源，任何写入都会污染其余组。因此 S10 改为 5 条行为契约（见 §12.2 / S10），其中第 ⑤ 条对**每一条路径**（窗口内命中、窗口内 miss、窗口外命中、窗口外未缓存 prompt）都与快照做整字典相等比较，而不只比长度——长度相等但值被改写同样是污染。

#### 12.3.4 为什么 S13 不再要求特定函数名

`_strategy_rows` 是本设计在 §13.4 diff 草案里给出的一个**建议实现**，不是契约。契约是「对照不进入 2×2×2 的任何均值」（§6.4）。要求特定函数名会带来两个坏处：实施者被迫采用某种内部组织方式；以及更糟的——**改名即失败，但泄漏未必失败**，判据与目标错位。

改为功能探测：把 9 行输入交给分析模块的候选可调用对象，只要**存在**一个满足「合法输入 → 恰好返回 8 个策略行且不含对照」且「`is_control=False` 但因子为 `not-applicable` 的输入 → 抛错」，即认定闸门已实现。

**探测范围（六条硬约束，全部必须满足才作为候选）**

| # | 约束 | 理由 |
|---|---|---|
| 1 | 定义于 `analysis.plot_experiments` 模块**自身**的函数 | 闸门是该模块的责任，不能由别处的同名函数顶替 |
| 2 | `obj.__module__ == module.__name__` | 排除 `from pandas import …` 之类**导入进来的**可调用对象被误认作闸门 |
| 3 | 非类、非导入 callable（`inspect.isfunction` 为真，`isinstance(obj, type)` 为假） | 类构造器碰巧返回 8 行不构成闸门证据 |
| 4 | 可接受**一个** DataFrame 位置参数（签名可判定） | 避免用错误参数数量去调用无关函数，产生无意义的异常噪声 |
| 5 | 名称不属于 `plot_*` / `load_*` / `main*` | 绘图与加载函数有 I/O 副作用，不应被探测调用 |
| 6 | 在临时目录执行（`OUTPUT_DIR` / `RESULTS_DIR` 重定向） | 探测绝不向仓库写入任何文件 |

约束 2 是关键：没有它，探测可能命中一个被 `import` 引入的第三方函数，从而给出「闸门已实现」的假阳性。

**判定结论按运行模式分档（R-17 的一致应用）**

| 情形 | `--offline-only` | `--runtime-dir`（正式验收） |
|---|---|---|
| `pandas` / `matplotlib` 不可用 | **WARN**（不可判定 ≠ 违约） | **FAIL** |
| `analysis.plot_experiments` 导入失败 | **WARN** | **FAIL** |
| 无任何候选可调用对象通过闸门判据 | **FAIL** | **FAIL** |
| 无法完成「9 行 → 8 条策略行」过滤验证 | **FAIL** | **FAIL** |
| 合法 9 行未得到 8 条策略行、或结果含对照 | **FAIL** | **FAIL** |
| 错标 `not-applicable` 的策略行未抛错 | **FAIL** | **FAIL** |

正式验收不接受「因依赖缺失而无法判定」：一次不能判定分析口径是否正确的验收，不构成验收。离线模式允许 WARN，是因为它已经自我声明 `NOT A FULL ACCEPTANCE`。

#### 12.3.5 集成验证：闸门必须被实际的分析入口调用（R-30）

§12.3.4 的探测只能证明**存在**一个行为正确的过滤函数。这不够。

「函数存在」与「函数被用上」是两件独立的事。一个写得完全正确、但没有任何入口调用的 `_strategy_rows()`，对 §1.2 的缺陷毫无帮助：`plot_main_effects` 照旧 `groupby("content_factor")`，共同对照照旧被算进边际均值，而 S13 会报告「闸门已实现」。这是本轮识别出的第二个阻断项。

**入口的发现方式：只按「是否真的会被调用」筛选，不按源码字面量筛选。**

第一版曾要求入口的源码里直接出现 `content_factor` / `channel_factor` / `timing_factor` 字面量。这个条件会**漏检两类入口**，而它们恰恰是闸门最容易被绕过的地方：

| 漏检类型 | 形态 | 为什么源码筛选看不见 |
|---|---|---|
| 通用包装入口 | `def plot_effect(df, factor_col): df.groupby(factor_col)…` | 因子列名由**参数**传入，函数体里没有任何字面量 |
| 间接委托入口 | `def plot_main_effects(df): _bar_grid(df)` | 自己不聚合，转调另一个函数完成聚合 |

因此发现条件只剩一条：出现在 `run_experiments.py` 的 `_pe.<name>` 调用点（AST 提取，与 S12 同源），且是定义于 `plot_experiments` 自身的模块级函数。**是否涉及因子聚合改由运行期观测判定**——判据是「该入口对一张含任一因子列的 DataFrame 执行了 `groupby` / `pivot` / `pivot_table`」，与源码写法完全无关。

所有由 `run_experiments.py` 实际调用的 `plot_experiments` 入口，均按生产调用序列和数据流重放。无法重放、调用报错或无法证明其为非因子入口的，分别归入 `entry-error` 或 `unknown-not-proven`，并判定 **FAIL**；**不得以 `not-probeable-signature` 作为中性状态放过**。

**两组断言**，对每个**产生因子聚合**的入口执行：

- **A. 入口实际调用了闸门**。把 candidate 临时替换为计数包装器（`setattr(module, name, wrapper)`，Python 在调用时解析全局名，因此模块内的直接调用也会被计入），调用入口后要求计数 > 0。**「存在但从未被调用」必须 FAIL。**
- **B. 聚合看到的数据恰为 8 个策略行**。临时替换 `pandas.DataFrame.groupby` / `pivot` / `pivot_table`，用**重入深度守卫**只记录分析代码自己发起的最外层调用（pandas 内部的再次调用不计入），因此记录到的就是「分析入口交给聚合的那张表」。对其中每一张含 `exp_id` 列的表断言五项：`len == 8`、`exp_id` 列长度 == 8、唯一数 == 8、集合恰为 `EXPECTED_STRATEGY_EXP_IDS`、不含 `NoClarification-Control`。

若某个因子聚合输入含因子列却**没有** `exp_id` 列，记为 problem 并注明「身份无法验证」——不可判定不得记为通过。

##### 12.3.5.1 探测方式：按生产调用序列与数据流重放（R-31）

孤立地逐个调用入口会造出两类**假象**，而它们恰好给「绕过闸门」提供了藏身处：

| 假象 | 成因 | 后果 |
|---|---|---|
| 参数形状不对 → `TypeError` | 生产里 `_pe.load_data()` 无参、`_pe.plot_main_effects(df)` 单参，孤立探测猜错 | 被记为 `entry-error`，中性放过 |
| 上游派生列缺失 → `KeyError` | `composite` 由 `plot_pareto_frontier` 写入并回填给下游入口 | 同上 |

因此改为**重放生产路径**：

1. `_pe_call_sequence()` 用 AST 从 `run_experiments.py` 提取 `_pe.<name>(…)` 的**有序调用序列**，同时记录每处的**实参个数**与**返回值是否被回填到变量**（对应 `df_exp = _pe.plot_pareto_frontier(df_exp)` 这类数据流）。
2. 把标准 9 行写成临时目录里的 `summary.csv`，`RESULTS_DIR` / `OUTPUT_DIR` 指向临时目录——于是 `_pe.load_data()` 也走**真实读取路径**，不再因「无参签名」被排除。
3. 按序列依次调用，把被回填的返回值作为下一个入口的输入。参数形状、调用顺序、上游派生列因此与生产一致。
4. 在这条完整路径上包装 candidate 并拦截 `groupby` / `pivot` / `pivot_table`。

**完整性闸门**：`run_experiments.py` 引用的每个 `_pe` 函数都必须出现在调用序列中。未出现者说明它以本方法捕获不到的形式被调用 → 判定为 `unknown-not-proven` → **FAIL**。不允许「没抓到就不算」。

##### 12.3.5.2 终局判定：不允许中性状态（R-31）

每个被实际调用的入口必须落在**两个合格终局状态**之一：

| 终局状态 | 条件 | 判定 |
|---|---|---|
| `factorial-entry-pass` | 运行期观测到因子聚合；candidate 调用次数 > 0；**所有**聚合输入均为 8 个唯一策略行且不含共同对照 | PASS |
| `not-factorial-entry` | 运行期未观测到因子聚合，**且有机器证据**：静态可达性分析证明该入口的调用链内不存在 `groupby` / `pivot` / `pivot_table`，也不存在 `getattr` 动态派发 | PASS |

以下状态**一律 FAIL**，不得在正式验收中保持中性：

| 状态 | 含义 |
|---|---|
| `factorial-entry-fail` | 聚合了，但没调闸门，或聚合输入不是 8 个唯一策略行 |
| `entry-error` | 已按生产顺序与生产参数形状重放，仍然抛异常。这正是缺陷 D2 的形态（异常被 `except` 吞掉 ⇒ 图表静默缺失） |
| `unknown-not-proven` | 未观测到聚合，但静态可达性**无法证明**它不会聚合（可达到聚合调用，或存在 `getattr` 动态派发，或调用图不可用，或该函数未出现在调用序列中） |

**机器证据的具体形态**（`not-factorial-entry` 的依据）：在 `analysis/plot_experiments.py` 内建模块级函数调用图，标记每个函数是否直接含 `.groupby(` / `.pivot(` / `.pivot_table(`，从入口做 DFS。可达集内无聚合调用且无 `getattr` ⇒ 已证明。

诚实标注该证据的局限：静态调用图**不能**跟踪动态派发（`getattr(obj, name)()`、`eval`）与跨模块间接调用。因此可达范围内一旦出现 `getattr`，结论就降级为 `unknown-not-proven` 而**不是**「已证明」——把不确定当成证明是这一整节要避免的错误。

**两条规则都是必要条件，互不替代**：

| # | 规则 | 它排除什么 |
|---|---|---|
| 1 | 至少一个入口必须是 `factorial-entry-pass` | 全都不聚合 ⇒ 主效应 / 交互根本没实现，或其实现不被 `run_experiments.py` 调用（D2 类缺陷） |
| 2 | **每个**入口都必须处于两个合格终局状态之一 | 「有入口绕过闸门」以及「无法判定的入口被中性放过」 |

**不得以规则 1 代替规则 2。** 「至少一个入口正确聚合」与「所有实际因子入口均正确」是两个不同的命题——前者成立而后者不成立，恰恰就是「一个入口用了闸门、另一个入口直接 `groupby` 全部 9 行」这一情形。

**若动态探测不可靠**（例如分析层用了闭包、局部导入或其它使 `setattr` 失效的组织方式，或静态可达性无法给出证据），本设计要求的补救**不是**放宽断言，而是：把过滤函数升级为**明确的公共接口**（模块级、可被 `setattr` 替换的名字），并让每个因子聚合入口都调用它。测试的失败信息里直接写明这条补救路径。**不得保留「存在任一候选即通过」的逻辑，也不得让任何入口以中性状态通过。**

所有替换都在 `try / finally` 中恢复，`OUTPUT_DIR` / `RESULTS_DIR` 重定向到临时目录，因此集成验证不向仓库写入任何文件。

### 12.4 三种运行模式（R-17）

测试入口必须显式选择模式；**无参数调用一律拒绝执行并以退出码 2 结束**。理由是排除「以为在做正式验收、实际只跑了离线项」这一类误判。

| 模式 | 行为 | 退出码 |
|---|---|---|
| `--generate-fixture` | **只**生成 pre-TASK_003 fixture。不运行 S1–S18；**不要求新矩阵已经实施**（fixture 的语义与矩阵是否重构无关，见 §12.6） | 0 = 成功；2 = 生产树不洁净或溯源不可判定 |
| `--offline-only` | 运行离线项（S1–S14、S17、S18）。S15 / S16 无运行目录、S13 依赖不可用、S18 缺 fixture 时均记 **WARN**。报告头尾均明确输出 `NOT A FULL ACCEPTANCE` | 0 = 无 FAIL；1 = 存在 FAIL |
| `--runtime-dir PATH` | 正式验收。`PATH` 必须是 `matrix_version == "3.0"` 且 `condition_count == 9` 的运行目录。S15 / S16 遇到**缺文件、缺行、版本不符**一律 **FAIL**；S13 依赖不可用或无可验证闸门 **FAIL**（R-22）；S18 缺 fixture 或 fixture 不可读 **FAIL**（R-25）。**绝不自动回退读取 `results/experiments/latest`** | 0 **仅在** `Failed == 0` 时给出；1 = 存在 FAIL |

`--offline-only` 与 `--runtime-dir` 对「不可判定」给出不同结论，是刻意的：**「尚未产出证据」与「证据表明违约」是两件不同的事**，用运行模式区分，而不是用同一档结论掩盖。反过来说，**正式模式不接受任何「不可判定」**——一次不能判定的验收不构成验收。

**报告字段口径（R-25 附带修正）**：验收报告的 `is_full_acceptance` 必须取 `formal and Failed == 0`，**不得**直接取 `formal`——否则「正式模式但验收失败」会被错标为完整验收通过。模式信息另由 `is_formal_mode` 保留。

**正式模式下 S18 的七项硬要求**（任一不成立即 FAIL）：①fixture 存在且可读；②`test_harness_sha256` 与当前测试文件哈希完全相同；③`generated_from_commit` 为 40 位 hex 且为 HEAD 的祖先（或等于 HEAD）；④`git_is_dirty` 为 bool；⑤`compared_fields` 与 S15 的 5 字段一致；⑥TASK_002 的测试与 fixture 冻结哈希匹配；⑦行为轨迹零差异。理由：行为不变性是 fixture 存在的唯一目的，正式验收若允许「没有基线」通过，这一项就完全没有被验证过。

### 12.5 正式验收运行目录的来源要求（R-18）

正式验收所依据的运行目录必须满足以下四条，缺一不可：

| # | 要求 | 机器可判定的检查 |
|---|---|---|
| 1 | 由**确定性 Mock Router** 产生 | `run_metadata.json` 存在 `llm` 块；批次全程不联网（由运行方式保证） |
| 2 | **不使用真实 LLM** | 同上；本任务全程禁止真实 LLM 实验（§15 第 16 项） |
| 3 | **不得使用历史 12 条件目录** | `is_legacy_run()` 必须判 `False`；`condition_count == 9`；`experiments` 恰 9 条且全部 `status == "ok"` |
| 4 | **不得用手工拼接的 CSV 伪造端到端证据** | 8 个产物齐备（`summary.csv` / `trajectories.csv` / `agent_records.csv` / `target_nodes.csv` / `experiment_metadata.jsonl` / `run_metadata.json` / `network_nodes.csv` / `network_edges.csv`）；`run_metadata` 含 `source_file_hashes` / `prompt_sources` / `persona_sources` / `clarification_templates` / `network_consistency`；`network_consistency.status == "consistent"`；`effective_event_ticks_union == [5]`；每个实验 `agent_record_count == num_agents × total_ticks` |

第 4 行的最后一项是关键：**行数完整性**是「真的跑完了 30 个 Tick × 20 个 Agent × 9 个条件」的必要条件，手工拼接的 CSV 极难同时满足它与 `run_metadata` 中由生产写入函数产出的哈希块。

诚实标注一处局限：上述检查能证明「产物由生产写入函数在一次完整批次中产出」，**不能**从产物本身证明「Router 是 Mock 而非真实 LLM」——`run_metadata` 的 `llm` 块记录的是配置，不是实际调用路径。这一条依赖运行方式的纪律，不是可自动验证的断言，因此在此显式登记而非伪装成已验证。

#### 12.5.1 批次退出码必须机器可读（R-24）

第 3 版把「进程退出码为 0」写成 S16 的一条 WARN。这等于没有验收：产物齐备但批次以退出码 4 结束时，报告仍会显示通过——而退出码 4 恰恰意味着**至少一组实验的澄清前路径对齐前提已被打破**，那批数据不能用于任何对比。

因此新增 `run_metadata.json` 的两个顶层字段契约：

| 字段 | 类型 | 语义 |
|---|---|---|
| `batch_exit_code` | `int` | 批次结束时的退出码。**0** = 正常完成；**3** = 网络一致性契约失败（§7.6 / TASK_002 R10）；**4** = Replay 对齐失败（§8.5） |
| `run_completed` | `bool` | 批次是否走完全部编排与产物落盘。区分「跑完了」与「中途异常退出但产物已部分落盘」 |

**正式验收要求**：`batch_exit_code == 0` **且** `run_completed is True`。正式模式下缺字段或值不符**必须 FAIL**。

写入时序与既有的退出码原则一致：这两个字段必须在**所有产物与图表落盘之后、抛出 `SystemExit` 之前**写入，否则退出码 3 / 4 的批次将不带这两个字段，反而失去可判定性。

**本轮只登记契约与测试预期，不修改 `run_experiments.py`**；生产实现属 TASK_003 实施阶段（§9 第 2 行第 ③ 项一并完成）。在实施之前，S16 的这两条断言在正式模式下 FAIL 属预期。

#### 12.5.2 agent_records 键唯一性是逐值比较的前置条件（R-23）

S15 的比较必须建立在「键唯一」之上，否则结论无意义。

第 3 版的实现用 `table[key] = {...}` 逐行填表。这在键重复时会**静默覆盖**：后写入的行胜出，逐值比较照样通过，而「同一 `(exp_id, tick, agent_id)` 出现两行」这一产物缺陷完全隐形。它的实际含义是主循环或写盘路径重复结算了某个 Agent——属于必须暴露的严重缺陷。

改为 fail-closed 的两段式：

**第一段（前置闸门）**：构造 `key_counts` 与 `key_to_rows`，对 `agent_records.csv` 的**所有**行验证 `(exp_id, tick, agent_id)` 的出现次数**恰好为 1**。任意 `count != 1` 立即 FAIL，并**停止后续逐值比较**——拒绝在键不唯一的数据上给出「对齐通过」的结论。报告中列出重复键及其行号，便于直接定位。

**第二段（逐区间验证）**：对每个策略条件的处理前区间（`*-Immediate` → Tick 1–5，`*-Delayed` → Tick 1–9）分别验证五项：

| 判据 | 内容 |
|---|---|
| 1 | 策略键集合与共同对照的同 Tick 键集合**完全相等** |
| 2 | 无缺失 Agent（对照有、策略无） |
| 3 | 无额外 Agent（策略有、对照无） |
| 4 | 区间内每键恰好一行 |
| 5 | 5 个字段（`trust_score_raw`、`shock_anchor_after_raw`、`quiet_ticks`、`is_buying`、`is_posting`）逐字相等，容差 0 |

判据 1 的集合相等同时覆盖 2 与 3，但三者分别登记，以便报告能直接指出是哪一类偏差。

**明确禁止**：不得用 S16 的总行数断言（`agent_record_count == num_agents × total_ticks`）替代键唯一性检查。**行数正确而键重复是完全可能的**——一个键出现两次、另一个键缺失，总数不变。两项检查覆盖不同的失效模式，缺一不可。

#### 12.5.3 绝对预期键空间：`count == 0` 需要外部期望才能发现（R-27）

§12.5.2 的键唯一性检查有一个结构性盲区：**它的期望值来自实际数据自身**。`key_counts` 是从 `agent_records.csv` 的行构造的，因此它只能发现 `count > 1`（重复），发现不了 `count == 0`（缺失）——一个从未出现的键不会出现在 `key_counts` 里，也就不会被任何断言碰到。

这个盲区对应的真实失效形态是：某组实验少跑了一个 Agent，或某个 Tick 的记录整体没写出。此时数据完全自洽（无重复、无冲突），逐值比较也会通过，因为参与比较的键在两侧都不存在。

因此必须建立一个**独立于实际数据**的绝对期望集合，由三个外部来源的笛卡尔积构造：

| 维度 | 来源 | 为什么它是外部的 |
|---|---|---|
| `exp_id`（9 个） | 测试自带的 `EXPECTED_EXP_IDS` | §12.3 的原则：测试的期望不从被测代码导入，否则退化为同义反复 |
| `tick`（`1..total_ticks`） | `run_metadata.json` 的 `experiments[0].config.total_ticks` | 来自 run 级元数据，不是从 `agent_records` 的 tick 列推断 |
| `agent_id` | `network_nodes.csv` 的 `agent_id` 集合 | run 级静态文件，9 个条件共用同一张网络（由 `verify_single_network()` 保证）。它是「本次 run 到底有哪些 Agent」的权威来源 |

```
expected_keys = {(exp_id, str(tick), agent_id)
                 for exp_id in EXPECTED_EXP_IDS
                 for tick in range(1, total_ticks + 1)
                 for agent_id in network_agent_ids}
```

**逐值比较之前**必须断言六项，任一失败立即停止：

| # | 断言 |
|---|---|
| 1 | `len(network_agent_ids) == num_agents` |
| 2 | `actual_keys == expected_keys` |
| 3 | `missing_keys` 为空 |
| 4 | `extra_keys` 为空 |
| 5 | 每个 `expected_key` 的 `count` 恰为 1（显式覆盖 `count == 0`） |
| 6 | `duplicate_keys` 为空 |

第 2 项与第 3、4 项在逻辑上等价，但分别登记：集合不等只给出「不相等」，而 missing / extra 分列能直接指出是缺了还是多了，定位成本差别很大。

**排序必须用安全 key 函数**：畸形 CSV（缺列 → `None`）在 `sorted()` 中混入 `None` 会抛 `TypeError: '<' not supported between 'NoneType' and 'str'`，那会让整份验收报告在写盘之前崩掉——判据本身反而成了新的失效点。因此对键元组排序时统一把 `None` 与非字符串转成字符串。这是 fail-closed 原则的一个具体应用：**判据遇到畸形输入时应当给出 FAIL，而不是崩溃**。

**分层关系**：原有的「策略组与共同对照处理前窗口比较」保留为**第二层**比较，**不能代替**绝对键空间检查。理由是它的期望值取自对照侧的实际数据：若对照与策略组**同时**缺同一个 Agent，第二层完全看不出来，而第一层（绝对键空间）会立刻报 missing。

### 12.6 洁净检查与 fixture 语义（R-19 / R-20）

#### 12.6.1 生产树洁净检查：三项独立执行

`--generate-fixture` 之前必须**同时**检查三项，任一非空即拒绝生成（退出码 2）：

| # | 检查 | 命令形态 |
|---|---|---|
| 1 | unstaged production diff | `git diff --name-only -- <production paths>` |
| 2 | staged production diff | `git diff --cached --name-only -- <production paths>` |
| 3 | production 路径下未跟踪文件 | `git ls-files --others --exclude-standard -- <production paths>` |

生产路径沿用 §12.1 规定的范围。**`tests` / `docs` / `.kiro` / `results` 仍排除**，以避免流程死锁：生成 fixture 时**本测试文件尚未提交**（它在第 5 步才与 fixture 一起提交），把 `tests/` 纳入检查会使第 3 步永远无法执行；**`design.md` 已经提交**（第 1 步），排除 `.kiro/` 与它的提交状态无关，只是因为该目录不属于生产路径。

#### 12.6.1.1 执行 `--generate-fixture` 时的仓库状态（五条同时成立）

这是第 3 步的完整前置状态，五条必须同时成立，缺一即拒绝生成：

| # | 对象 | 要求状态 |
|---|---|---|
| 1 | `.kiro/specs/task003-experiment-matrix/design.md` | **已提交**（§12.1 第 1 步） |
| 2 | `tests/test_task003_experiment_matrix.py` | **尚未提交**（第 2 步已产出，第 5 步才提交） |
| 3 | `tests/fixtures/task003/pre_task003_behavior_trace.json` | **尚未提交**，且此刻尚不存在（本步才生成） |
| 4 | 5 个生产文件（`experiment_config.py`、`run_experiments.py`、`simulation_core.py`、`analysis/plot_experiments.py`、`analysis/plot_trajectories.py`） | **无 staged、无 unstaged、无 untracked 变更**（三项独立检查，见上表） |
| 5 | `HEAD` 与 `PRE_TASK003_BASE_COMMIT` | 在 `PRODUCTION_PATHS` 上的**树内容完全一致，不存在净文件差异**（§12.6.1.2 第 6 项） |

第 2、3 条正是仓库级 `git_is_dirty == True` 的来源，因此 `True` 是**预期值**而非异常。第 4、5 条合起来才是 fixture 可作为证据的硬前提：**第 4 条管工作树，第 5 条管已提交状态的树内容**，缺任一条都能让 post 状态伪装成 pre 状态。

无法判定（无 git / 非仓库 / 命令失败）同样拒绝生成——「不知道代码状态」与「代码状态错误」对基线的可信度而言后果相同。

#### 12.6.1.2 代码状态锚定：`assert_pre_task003_generation_state()`（R-29）

三路工作树检查有一个致命盲区：**它只看工作树，不看已提交状态的树内容**。

设想有人把 TASK_003 的生产改动提交掉（无论是有意还是误操作），此时 `git diff`、`git diff --cached`、`git ls-files --others` 三项全部为空，工作树完全干净。fixture 会被生成并标注为「pre-TASK_003 行为基线」——而它记录的其实是 **post**-TASK_003 的行为。此后 S18 的行为不变性比较变成 post/post 自比，**永远通过**，而「TASK_003 未改变既有机制」这一结论从此毫无证据支撑。

因此在 `collect_behavior_trace()` **之前**必须执行 `assert_pre_task003_generation_state(root)`，七项全部成立才允许生成：

| # | 检查 | 手段 | 不成立的后果 |
|---|---|---|---|
| 1 | fixture 尚不存在 | `os.path.exists(FIXTURE_PATH)` | 覆盖一份已冻结的基线是不可逆的证据破坏。**退出码 2，禁止覆盖** |
| 2 | `design.md` 已被 Git 跟踪 | `git ls-files --error-unmatch -- <design.md>` | §12.1 第 1 步未完成，fixture 没有对应的设计快照 |
| 3 | `design.md` 无 unstaged 变更 | `git diff --quiet -- <design.md>` | 设计尚未定稿 |
| 4 | `design.md` 无 staged 变更 | `git diff --cached --quiet -- <design.md>` | 同上 |
| 5 | `PRE_TASK003_BASE_COMMIT` 存在且为 HEAD 祖先 | `git cat-file -e` + `git merge-base --is-ancestor` | 当前分支与基线不在同一历史线上（分支切换 / rebase / reset） |
| 6 | **HEAD 与 `PRE_TASK003_BASE_COMMIT` 在 `PRODUCTION_PATHS` 上的树内容完全一致，不存在净文件差异** | `git diff --quiet PRE_TASK003_BASE_COMMIT..HEAD -- <PRODUCTION_PATHS>` | **本节要封堵的漏洞本身。** 失败时列出具体差异文件 |
| 7 | 现有三路工作树洁净检查 | 见上表（unstaged / staged / untracked） | 基线来源不明 |

**第 6 项的证据强度（精确表述，不夸大）**：`git diff A..B -- <paths>` 比较的是**两个提交的树内容**，因此它证明的是「HEAD 与基线在这些路径上最终内容相同、无净文件差异」，**不是**「期间从未出现过修改提交」——改了又改回来同样通过。

这正是所需的语义。pre-TASK_003 代码状态的要求是**最终树内容相同**：只要 HEAD 上的生产代码逐字节等于基线，用它采集的行为轨迹就是合格的 pre 基线，中间经历过什么与结论无关。因此本设计**不附加任何 `git log` 历史禁令**——那会把一个与结论无关的过程约束伪装成正确性要求。

`PRE_TASK003_BASE_COMMIT` 是一个**写死的 40 位常量**，不是运行期推断值：

```
PRE_TASK003_BASE_COMMIT = "c8558d57f501dd32d483a2b2d939a06129554365"
  = git rev-parse c8558d5
  = "docs(observability): finalize TASK_002 records"
  即 TASK_003 生产改动之前的最后一个提交
```

写死是刻意的：任何「从当前状态推断基线」的做法都会随当前状态漂移，失去锚定意义。

fixture 相应新增两个字段：

| 字段 | 值 | S18 的校验 |
|---|---|---|
| `production_baseline_commit` | `PRE_TASK003_BASE_COMMIT` | 为 40 位 SHA；与测试常量**完全相等**；是当前 HEAD 的祖先 |
| `fixture_generation_guard_version` | `"2.0"` | 与测试常量相等——版本不符说明该 fixture 是用一套**更弱的**前置检查生成的 |

守卫版本号的作用：守卫规则本身升级时（例如本轮从「三路工作树」升级为「三路 + 树内容锚定」），旧 fixture 必须被识别出来，而不是被当作等效证据继续使用。

#### 12.6.1.3 最终落盘：排他创建 + 失败清理（R-29 第二半 / R-32）

生成前的 `os.path.exists()` 检查（§12.6.1.2 第 1 项）是**先验假设**，而 `open(path, "w")` 会**截断**已存在的文件。两者之间存在时间窗，被覆盖的是一份已冻结的基线——不可逆的证据破坏。

因此落盘规定为两阶段：

| 阶段 | 动作 | 目的 |
|---|---|---|
| 1 | 在 **fixture 同目录**创建临时文件（`tempfile.mkstemp(dir=FIXTURE_DIR, …)`），写入完整 JSON，并**回读 `json.load()` 校验** | 同目录保证同一文件系统；完整性在临时文件上确认，异常不会留下半写的 fixture |
| 2 | `open(FIXTURE_PATH, "x", encoding="utf-8")` **排他创建**并一次性写入 | `"x"` 把「文件不存在」从先验假设变成写入操作**自身的原子前提** |

**排他创建只保证「创建时刻文件不存在」，不保证写入成功（R-32）。** 创建成功之后的 `write` 若因磁盘写满、编码错误或 `KeyboardInterrupt` 中断，磁盘上就会留下一个**半写的 JSON**。它的危害是双重的：下一次生成会因 `FileExistsError` 被拒（fixture 被永久卡死），而这份残片还可能被误当作有效基线。

因此完整落盘契约为五条：

| # | 规定 |
|---|---|
| 1 | 最终文件创建后执行 `write` → `flush` → `os.fsync`（确保内容真正落到磁盘，而非停留在缓冲区） |
| 2 | 写入后**重新 `json.load` 最终文件**，确认它是可解析的完整 JSON |
| 3 | `FileExistsError` → 退出码 2；**原 fixture 一字不变**；同时删除临时文件 |
| 4 | **其它任何异常**（捕获 `BaseException`，含 `KeyboardInterrupt`）→ 若本次**已经创建**最终文件则**立即删除该文件**，再删除临时文件，退出码 2 |
| 5 | 只有全部成功后才删除临时文件并报告 fixture 生成完成 |

第 4 条的关键细节：用一个 `created_final` 标志区分「本次新建的文件」与「早已存在的 fixture」，**只删前者**。否则异常处理本身会变成新的证据破坏路径。

**绝不让写入异常留下部分 JSON 文件。**

#### 12.6.2 pre-TASK_003 fixture 的语义边界

该 fixture 证明的**只有**一件事：

> **TASK_003 的实施未改变既有的信任更新、`shock_anchor`、`quiet_ticks` 与行为决策机制。**

它明确**不是**以下两者：

1. **不是**旧 12 条件矩阵正确性的证明。旧矩阵的缺陷（伪因子、名实不符）已在 §1 诊断，fixture 不为它背书。
2. **不要求**旧 `ExperimentConfig` 接受 `delayed` 或 `not-applicable`。fixture 的采集路径只驱动三个 Agent 插件（`GreenCognitionPlugin` / `ConsumerPlanPlugin` / `GreenInvokePlugin`），**完全不构造 `ExperimentConfig`**，因此与因子词表的新旧无关。

这也是 `--generate-fixture` 模式「不要求新矩阵已经实施」的根据：fixture 的输入定义（确定性 Router 返回值、场景字面常量、Tick 序列、5 个比较字段）与矩阵重构正交。

---

## 13. unified diff 草案

> 本节中的 unified diff 仅用于说明预期变更结构与关键代码位置，
> 最终实施以经过验收测试的实际代码变更为准，不保证本节文本可直接通过
> `git apply` 执行。

> 以下为**草案**，用于评审改动边界与规模，**本阶段不应用**。行号以当前工作树为基准；实施时以实际上下文匹配为准。
>
> 草案覆盖 §9 的 5 个生产文件：§13.1 `experiment_config.py`、§13.2 `run_experiments.py`、§13.3 `simulation_core.py`、§13.4 `analysis/plot_experiments.py` + `analysis/plot_trajectories.py`。
> **`clarification_injector.py` 无 diff 片段**（R-11：本任务完全不修改该文件）。

### 13.1 `experiment_config.py`（结构性重写）

```diff
--- a/experiment_config.py
+++ b/experiment_config.py
@@ -1,14 +1,58 @@
 """
 experiment_config.py — 实验配置定义模块

-定义三因子实验空间（内容×渠道×时机），生成 2×2×3=12 个实验配置。
+定义 2×2×2 策略矩阵（内容×渠道×时机）+ 1 个唯一共同对照 = 9 个实验条件。
+
+矩阵 v3.0 的三条设计约束（详见 .kiro/specs/task003-experiment-matrix/design.md）：
+  1. 共同对照唯一，且不携带 content / channel 标签（消除伪因子）；
+  2. 时机标签不含任何数字，延迟长度只由 clarification_tick 提供
+     （延迟澄清 = 丑闻后 5 个 Tick，当前配置下 Tick 10）；
+  3. "不适用" 哨兵的**值**为连字符形式 "not-applicable"，与 content / channel
+     的真实水平（rational-evidence / emotional-empathy）风格一致。
+     常量**名** NOT_APPLICABLE 用下划线，因为 Python 标识符不允许连字符。
 """
 from dataclasses import dataclass, field, asdict
 from typing import List, Optional
 from itertools import product

-# 合法因子水平
-VALID_CONTENT_FACTORS = {"rational-evidence", "emotional-empathy"}
-VALID_CHANNEL_FACTORS = {"hub", "random"}
-VALID_TIMING_FACTORS  = {"immediate", "delay-3", "no-clarification"}
+EXPERIMENT_MATRIX_VERSION = "3.0"
+
+# ── "不适用" 哨兵：名用下划线（标识符限制），值用连字符（落盘字面量）──
+NOT_APPLICABLE = "not-applicable"
+
+# ── 真实因子水平（唯一可用于分组 / pivot / 图例 / 模板查表的集合）──
+CONTENT_LEVELS         = ("rational-evidence", "emotional-empathy")
+CHANNEL_LEVELS         = ("hub", "random")
+STRATEGY_TIMING_LEVELS = ("immediate", "delayed")
+
+# ── 共同对照专用常量（唯一，不可复制）──
+CONTROL_TIMING = "no-clarification"
+CONTROL_EXP_ID = "NoClarification-Control"
+
+# ── 字段级合法值 = 真实水平 ∪ {NOT_APPLICABLE}；与上面的"水平"严格区分用途 ──
+VALID_CONTENT_FACTORS = set(CONTENT_LEVELS) | {NOT_APPLICABLE}
+VALID_CHANNEL_FACTORS = set(CHANNEL_LEVELS) | {NOT_APPLICABLE}
+VALID_TIMING_FACTORS  = set(STRATEGY_TIMING_LEVELS) | {CONTROL_TIMING}
+
+# ── 澄清时机偏移量：数字只住在这里，绝不进入任何标签字符串 ──
+IMMEDIATE_OFFSET_TICKS = 1
+DELAYED_OFFSET_TICKS   = 5      # 延迟澄清 = 丑闻后 5 个 Tick → 默认 scandal_tick=5 时为 Tick 10
+
+# ── exp_id 词元（完整词，禁止缩写）──
+CONTENT_ID_TOKEN = {"rational-evidence": "Rational", "emotional-empathy": "Empathy"}
+CHANNEL_ID_TOKEN = {"hub": "Hub", "random": "Random"}
+TIMING_ID_TOKEN  = {"immediate": "Immediate", "delayed": "Delayed"}
+
+# ── 导入期不变量：把整类缺陷挡在门外 ──
+assert all(not any(ch.isdigit() for ch in lv) for lv in STRATEGY_TIMING_LEVELS), \
+    "时机标签不得内嵌数字：延迟长度只能由 clarification_tick 提供"
+assert NOT_APPLICABLE == "not-applicable" and "_" not in NOT_APPLICABLE, \
+    "哨兵值必须是连字符形式 'not-applicable'"
+assert NOT_APPLICABLE not in (set(CONTENT_LEVELS) | set(CHANNEL_LEVELS)
+                              | set(STRATEGY_TIMING_LEVELS) | {CONTROL_TIMING}), \
+    "'not-applicable' 不是因子水平"
+assert not any(tok in CONTROL_EXP_ID
+               for tok in ("Rational", "Empathy", "Hub", "Random",
+                           "Immediate", "Delayed")), \
+    "共同对照的 exp_id 不得携带任何因子词元"
@@ -18,32 +62,63 @@ class ExperimentConfig:
     """单次实验运行的完整配置（不可变）"""

     # ── 因子水平 ─────────────────────────────────────────────────────
-    content_factor: str      # "rational-evidence" | "emotional-empathy"
-    channel_factor: str      # "hub" | "random"
-    timing_factor: str       # "immediate" | "delay-3" | "no-clarification"
+    content_factor: str      # "rational-evidence" | "emotional-empathy" | "not-applicable"
+    channel_factor: str      # "hub" | "random" | "not-applicable"
+    timing_factor: str       # "immediate" | "delayed" | "no-clarification"

     # ── 固定参数 ─────────────────────────────────────────────────────
-    budget_k: int = 3        # 澄清直接投放节点数（20人网络中约15%渗透率）
+    budget_k: int = 3        # 策略条件 3；共同对照必须 0（真实的零，不是"不适用"）
     random_seed: int = 42
     num_agents: int = 20
     total_ticks: int = 30
     scandal_tick: int = 5

     def __post_init__(self):
-        """字段验证"""
+        """三段验证：字段级 → 组合级 → 自洽性"""
+        # ── 段一：字段级 ──
         if self.content_factor not in VALID_CONTENT_FACTORS:
             raise ValueError(
                 f"content_factor must be one of {VALID_CONTENT_FACTORS}, got '{self.content_factor}'"
             )
-        if self.channel_factor not in VALID_CHANNEL_FACTORS:
-            raise ValueError(...)
-        if self.timing_factor not in VALID_TIMING_FACTORS:
-            raise ValueError(...)
+        # channel / timing 同构，略
         if self.num_agents <= 0:
             raise ValueError(f"num_agents must be > 0, got {self.num_agents}")
         if self.total_ticks <= 0:
             raise ValueError(f"total_ticks must be > 0, got {self.total_ticks}")
+        if self.budget_k < 0:
+            raise ValueError(f"budget_k must be >= 0, got {self.budget_k}")
+
+        # ── 段二：组合级（字段级枚举无法表达的互斥规则）──
+        if self.is_control:
+            if self.content_factor != NOT_APPLICABLE or self.channel_factor != NOT_APPLICABLE:
+                raise ValueError(
+                    f"common control must encode content/channel as '{NOT_APPLICABLE}', "
+                    f"got content='{self.content_factor}', channel='{self.channel_factor}'"
+                )
+            if self.budget_k != 0:
+                raise ValueError(
+                    f"common control must have budget_k == 0 (it delivers nothing), "
+                    f"got {self.budget_k}"
+                )
+        else:
+            if self.content_factor not in CONTENT_LEVELS:
+                raise ValueError(
+                    f"strategy condition requires a real content level {CONTENT_LEVELS}, "
+                    f"got '{self.content_factor}'"
+                )
+            if self.channel_factor not in CHANNEL_LEVELS:
+                raise ValueError(
+                    f"strategy condition requires a real channel level {CHANNEL_LEVELS}, "
+                    f"got '{self.channel_factor}'"
+                )
+            if self.budget_k <= 0:
+                raise ValueError(
+                    f"strategy condition requires budget_k > 0, got {self.budget_k}"
+                )
+
+        # ── 段三：自洽性（澄清必须落在丑闻之后、仿真窗口之内）──
+        clr = self.clarification_tick
+        if clr is not None and not (self.scandal_tick < clr <= self.total_ticks):
+            raise ValueError(
+                f"clarification_tick={clr} must satisfy "
+                f"scandal_tick({self.scandal_tick}) < tick <= total_ticks({self.total_ticks})"
+            )
+
+    @property
+    def is_control(self) -> bool:
+        """是否为唯一共同对照。下游一律用它判断，禁止字符串比较。"""
+        return self.timing_factor == CONTROL_TIMING

     @property
     def exp_id(self) -> str:
-        """唯一实验标识符，如 'Rational-Hub-Imm'"""
-        content_short = "Rational" if self.content_factor == "rational-evidence" else "Empathy"
-        channel_short = "Hub" if self.channel_factor == "hub" else "Random"
-        timing_map = {"immediate": "Imm", "delay-3": "D3", "no-clarification": "NoClr"}
-        timing_short = timing_map[self.timing_factor]
-        return f"{content_short}-{channel_short}-{timing_short}"
+        """唯一实验标识符（完整词元），如 'Rational-Hub-Immediate'。
+        共同对照固定为 'NoClarification-Control'，不携带 content / channel 标签。"""
+        if self.is_control:
+            return CONTROL_EXP_ID
+        return "-".join((CONTENT_ID_TOKEN[self.content_factor],
+                         CHANNEL_ID_TOKEN[self.channel_factor],
+                         TIMING_ID_TOKEN[self.timing_factor]))

     @property
     def clarification_tick(self) -> Optional[int]:
-        """澄清注入的 Tick，None 表示不澄清
-          - immediate:        丑闻次日（scandal_tick + 1）
-          - delay-3:          丑闻后第 5 天（scandal_tick + 5）
-          - no-clarification: 不澄清
-        """
+        """澄清注入的 Tick，None 表示不澄清。
+          - immediate       : 丑闻后 1 个 Tick（scandal_tick + IMMEDIATE_OFFSET_TICKS）→ 默认 Tick 6
+          - delayed         : 丑闻后 5 个 Tick（scandal_tick + DELAYED_OFFSET_TICKS）  → 默认 Tick 10
+          - no-clarification: 不澄清 → None
+        标签本身不含数字；具体 Tick 只由本属性提供，是唯一权威取值渠道。
+        """
         if self.timing_factor == "immediate":
-            return self.scandal_tick + 1
-        elif self.timing_factor == "delay-3":
-            return self.scandal_tick + 5
+            return self.scandal_tick + IMMEDIATE_OFFSET_TICKS
+        if self.timing_factor == "delayed":
+            return self.scandal_tick + DELAYED_OFFSET_TICKS
         return None

     def to_dict(self) -> dict:
         d = asdict(self)
         d["exp_id"] = self.exp_id
         d["clarification_tick"] = self.clarification_tick
+        d["is_control"] = self.is_control
+        d["matrix_version"] = EXPERIMENT_MATRIX_VERSION
         return d
@@ -83,24 +190,40 @@ def generate_experiment_matrix() -> List[ExperimentConfig]:
-    """
-    生成完整的因子实验矩阵。
-
-    2（内容）× 2（渠道）× 3（时机）= 12 个配置。
-    """
-    content_levels = ["rational-evidence", "emotional-empathy"]
-    channel_levels = ["hub", "random"]
-    timing_levels  = ["immediate", "delay-3", "no-clarification"]
-
-    configs = []
-    for content, channel, timing in product(content_levels, channel_levels, timing_levels):
-        configs.append(ExperimentConfig(
-            content_factor=content,
-            channel_factor=channel,
-            timing_factor=timing,
-        ))
-    return configs
+    """生成矩阵 v3.0：8 个策略条件（2×2×2 完全交叉）+ 1 个唯一共同对照 = 9 个配置。
+
+    返回顺序：共同对照在首位（它是 Recording 基线），其后是 8 个策略条件的字典序。
+    """
+    control = ExperimentConfig(
+        content_factor=NOT_APPLICABLE,
+        channel_factor=NOT_APPLICABLE,
+        timing_factor=CONTROL_TIMING,
+        budget_k=0,
+    )
+    strategies = [
+        ExperimentConfig(content_factor=c, channel_factor=h, timing_factor=t)
+        for c, h, t in product(CONTENT_LEVELS, CHANNEL_LEVELS, STRATEGY_TIMING_LEVELS)
+    ]
+    strategies.sort(key=lambda cfg: cfg.exp_id)
+    configs = [control] + strategies
+
+    # ── 矩阵级不变量（构造期强制，不留给下游发现）──
+    assert len(configs) == 9, f"矩阵必须为 9 条，实际 {len(configs)}"
+    assert len(strategies) == 8, f"策略条件必须为 8 条，实际 {len(strategies)}"
+    ids = [c.exp_id for c in configs]
+    assert len(set(ids)) == 9, f"exp_id 必须唯一，实际 {ids}"
+    controls = [c for c in configs if c.is_control]
+    assert len(controls) == 1, f"共同对照必须唯一，实际 {len(controls)} 条"
+    assert controls[0].exp_id == CONTROL_EXP_ID
+    for cfg in strategies:
+        assert cfg.content_factor in CONTENT_LEVELS and cfg.channel_factor in CHANNEL_LEVELS
+        assert cfg.clarification_tick in (6, 10) or cfg.scandal_tick != 5
+    return configs
```

### 13.2 `run_experiments.py`（编排与产物）

```diff
@@ "Recording / Replay Router" 分节标题之后、class RecordingRouter 之前：新增异常类型
+class ReplayAlignmentError(RuntimeError):
+    """Replay 窗口内缓存未命中：澄清前路径与共同对照的对齐前提已被打破。
+
+    fail-closed：绝不降级调用真实 Router。窗口内一旦 miss，该组
+    Tick 1..replay_until-1 的轨迹就不再是共同对照的正确反事实前缀，
+    其结果不可用于任何对比（设计 §8.5）。
+    """
+
+    def __init__(self, exp_id: str, tick: int, replay_until: int, miss_count: int):
+        self.exp_id = exp_id
+        self.tick = tick
+        self.replay_until = replay_until
+        self.miss_count = miss_count
+        super().__init__(
+            f"REPLAY ALIGNMENT VIOLATED: exp_id={exp_id} tick={tick} "
+            f"replay_until={replay_until} miss_count={miss_count} — "
+            f"refusing to fall back to the real router"
+        )
@@ class ReplayRouter.__init__ — 增 exp_id（仅供异常归属）
 class ReplayRouter:
-    """在 replay_until_tick 之前回放缓存，之后走真实 LLM"""
+    """在 replay_until_tick 之前回放缓存，之后走真实 LLM。
+    窗口内缓存 miss 一律 fail-closed：抛 ReplayAlignmentError，绝不 fallback。"""

-    def __init__(self, inner_router, cache: dict, replay_until_tick: int):
+    def __init__(self, inner_router, cache: dict, replay_until_tick: int,
+                 exp_id: str = ""):
         self._inner = inner_router
         self._cache = cache
         self._replay_until = replay_until_tick
+        self._exp_id = exp_id
         self._current_tick: int = 0
         self._call_counts: dict = {}
         self.miss_count: int = 0
@@ class ReplayRouter.chat — 窗口内 miss 改 fail-closed（删除 fallback）
     async def chat(self, prompt: str) -> str:
         pk = RecordingRouter._pk(prompt)
         count = self._call_counts.get(pk, 0)
         self._call_counts[pk] = count + 1

         if self._current_tick < self._replay_until:
             key = (pk, self._current_tick, count)
             if key in self._cache:
                 return self._cache[key]
-            self.miss_count += 1
-            if self.miss_count <= 3:
-                print(f"  ⚠️  [ReplayRouter] cache miss tick={self._current_tick}")
-        return await self._inner.chat(prompt)
+            # 窗口内 miss = 对齐前提已被打破 ⇒ fail-closed。
+            # 这里**没有** self._inner.chat() ——禁止任何 fallback（设计 §8.5.1）。
+            self.miss_count += 1
+            raise ReplayAlignmentError(exp_id=self._exp_id,
+                                       tick=self._current_tick,
+                                       replay_until=self._replay_until,
+                                       miss_count=self.miss_count)
+
+        # 窗口外（tick >= replay_until）：正常调真实 LLM，且**不计入** miss_count。
+        # 这是正常分叉，不是对齐违约。
+        return await self._inner.chat(prompt)
@@ 单事件 patch 区块之后，新增 summary 列契约常量（修 D1）
+SUMMARY_FIELDS = [
+    "exp_id", "content_factor", "channel_factor", "timing_factor", "is_control",
+    "delta_recovery", "auc_post_scandal", "recovery_speed",
+    "steady_state_score", "recovery_rate", "t50", "t80",
+    "trust_min", "trust_min_tick", "baseline_trust", "clarification_effect",
+    "trust_gain_vs_control",
+]
@@ def write_summary_csv — 单基线化 + 列数自洽
-    ctrl_baseline: dict = {}   # channel → final_trust
-    for r in results:
-        if "error" in r:
-            continue
-        if r["config"].get("timing_factor") == "no-clarification":
-            channel = r["config"].get("channel_factor", "hub")
-            final_trust = r["trust_trajectory"][-1] if r.get("trust_trajectory") else 0.0
-            ctrl_baseline[channel] = round(final_trust, 4)
+    # 唯一共同对照 → 唯一基线。不再按 channel 分组（对照的 channel 无因果意义，
+    # 分组会让 Hub / Random 策略组被两条只差噪声的基线归一化，见设计 §1.2）。
+    ctrl_final: float = None
+    for r in results:
+        if "error" in r:
+            continue
+        if r["config"].get("is_control"):
+            ctrl_final = round(r["trust_trajectory"][-1], 4) if r.get("trust_trajectory") else 0.0
+    # 对照缺失（失败）时不伪造基线：trust_gain_vs_control 写 ""，与真实的 0.0 区分
@@
-        writer.writerow([... 16 列字面量 ...])
+        writer.writerow(SUMMARY_FIELDS)
@@
-            if "error" in r:
-                writer.writerow([r["exp_id"]] + ["ERROR"] * 16)
+            if "error" in r:
+                # D1 修复：格数由表头派生，永不与表头脱节
+                writer.writerow([r["exp_id"]] + ["ERROR"] * (len(SUMMARY_FIELDS) - 1))
@@ def write_trajectories_csv — 增 is_control 列
-            "exp_id", "content_factor", "channel_factor", "timing_factor",
+            "exp_id", "content_factor", "channel_factor", "timing_factor", "is_control",
             "tick", "avg_trust", "conversion_rate",
@@ async def main — 打印与编排
-    print("🧪 GABM 批量实验 — 单一漂绿事件 × 12 种澄清策略")
-    print("   矩阵    : 2(内容) × 2(渠道) × 3(时机) = 12 组")
+    print("🧪 GABM 批量实验 — 单一漂绿事件 × 8 澄清策略 + 1 共同对照")
+    print("   矩阵    : 2(内容) × 2(渠道) × 2(时机) = 8 组 + 唯一共同对照 = 9 组")
+    print("   对齐    : 共同对照 Recording；策略组 Replay 至各自澄清 Tick 之前")
@@
-    baseline_config = next(
-        c for c in configs
-        if c.timing_factor == "no-clarification"
-        and c.channel_factor == "hub"
-        and c.content_factor == "rational-evidence"
-    )
-    other_configs = [c for c in configs if c != baseline_config]
-    ordered_configs = [baseline_config] + other_configs
+    # 录制组 = 唯一共同对照（布尔属性判定，不做字符串匹配）
+    control_config = next(c for c in configs if c.is_control)
+    strategy_configs = sorted((c for c in configs if not c.is_control),
+                              key=lambda c: c.exp_id)
+    assert len(strategy_configs) == 8
+    ordered_configs = [control_config] + strategy_configs
@@ 循环内
-        is_baseline = (config == baseline_config)
+        is_recording = config.is_control
@@
-            "router_role": "recording" if is_baseline else "replay",
+            "router_role": "recording" if is_recording else "replay",
@@
-                # ── 其余 11 组（含另外 3 个 NoClr）：全程 Replay 到 clr_tick 前 ──
-                clr_tick = config.clarification_tick if config.clarification_tick else config.total_ticks + 1
-                rp_router = ReplayRouter(_real_router, llm_cache, replay_until_tick=clr_tick)
+                # ── 8 个策略组：Replay 至各自澄清 Tick 之前（immediate→1..5, delayed→1..9）──
+                #    魔法值 total_ticks + 1 已删除：唯一对照就是录制组，不存在"全程回放"的组。
+                assert config.clarification_tick is not None, \
+                    "策略条件必须有 clarification_tick（组合级校验已保证）"
+                rp_router = ReplayRouter(_real_router, llm_cache,
+                                         replay_until_tick=config.clarification_tick,
+                                         exp_id=config.exp_id)
@@ 实验级 except 分支：窗口内 miss 走失败路径，绝不当作有效结果
-                if rp_router.miss_count > 0:
-                    print(f"  ⚠️  ReplayRouter cache miss: {rp_router.miss_count} 次")
+            except ReplayAlignmentError as e:
+                # fail-closed（设计 §8.5.3 / L1）：该实验作废，轨迹不进入任何有效产物。
+                # 绝不"errors.append 之后继续把这组轨迹当有效结果"。
+                print(f"  ❌ {e}")
+                errors.append(str(e))
+                replay_miss_by_exp_id[config.exp_id] = e.miss_count
+                results.append({
+                    "exp_id": config.exp_id,
+                    # R12：失败实验必须保留完整 config —— 最需要知道"哪一组因子 / 什么 seed"
+                    "config": config.to_dict(),
+                    "error_type": "ReplayAlignmentError",
+                    "error": str(e),
+                    "run_audit": run_audit,   # started_at / finished_at / router_role / miss
+                })
+                continue      # 无 trust_trajectory / agent_records ⇒ 下游一律 skip
@@ main() 末尾：所有产物与图表落盘之后才非零退出（次序原则同 TASK_002 退出码 3）
+    # 退出码约定：0 = 正常；3 = 网络一致性违约（TASK_002）；4 = Replay 对齐违约（本任务）
+    if replay_miss_by_exp_id:
+        print("=" * 65)
+        print("❌ REPLAY ALIGNMENT VIOLATED — 以下实验已作废，不参与任何对比：")
+        for exp_id, n in sorted(replay_miss_by_exp_id.items()):
+            print(f"   {exp_id}: window-internal cache miss × {n}")
+        print("   全部产物与图表已安全落盘；以退出码 4 结束。")
+        print("=" * 65)
+        raise SystemExit(4)
@@ write_run_metadata_json — 新增 run 级矩阵块
+        "experiment_matrix": {
+            "matrix_version": EXPERIMENT_MATRIX_VERSION,
+            "condition_count": 9,
+            "strategy_condition_count": 8,
+            "control_condition_count": 1,
+            "control_exp_id": CONTROL_EXP_ID,
+            "content_levels": list(CONTENT_LEVELS),
+            "channel_levels": list(CHANNEL_LEVELS),
+            "timing_levels": list(STRATEGY_TIMING_LEVELS),
+            "control_timing": CONTROL_TIMING,
+            "not_applicable_value": NOT_APPLICABLE,          # 值为 "not-applicable"
+            "immediate_offset_ticks": IMMEDIATE_OFFSET_TICKS,
+            "delayed_offset_ticks": DELAYED_OFFSET_TICKS,
+            "recording_exp_id": CONTROL_EXP_ID,
+            "replay_until_by_exp_id": replay_until_by_exp_id,
+            "replay_alignment_violated": bool(replay_miss_by_exp_id),
+            "replay_miss_by_exp_id": replay_miss_by_exp_id,
+            "divergent_recording_enabled": False,
+        },
@@ 图表段（修 D2）
-            _pt_traj.plot_timing_effect(df_traj)
-            _pt_traj.plot_content_channel(df_traj)
-            _pt_traj.plot_all_12_strategies(df_traj)
+            _pt_traj.plot_timing_comparison(df_traj)
+            _pt_traj.plot_content_channel_comparison(df_traj)
+            _pt_traj.plot_all_9_conditions(df_traj)
```

### 13.3 `simulation_core.py`（唯一改动：3 行守卫）

```diff
@@ -636,9 +636,14 @@
     # ── 8. 初始化澄清注入器 ─────────────────────────────────────────
     injector = ClarificationInjector(config)
-    target_nodes = select_target_nodes(net_plugin.graph, config.channel_factor, config.budget_k, config.random_seed)
-    injector.set_target_nodes(target_nodes)
+    # 共同对照不投放任何澄清：跳过选点。
+    # 行为等价性已核实（设计 §3.4）：random 分支用局部 random.Random(seed+7777)，
+    # 不触碰全局 RNG；hub 分支纯确定性；因此跳过不改变任何随机序列。
+    if config.is_control:
+        target_nodes = []
+    else:
+        target_nodes = select_target_nodes(net_plugin.graph, config.channel_factor,
+                                          config.budget_k, config.random_seed)
+    injector.set_target_nodes(target_nodes)
```

### 13.4 `analysis/plot_experiments.py` / `plot_trajectories.py`（词表与口径，节选）

```diff
--- a/analysis/plot_experiments.py
+++ b/analysis/plot_experiments.py
-TIMING_COLORS  = {"immediate": "#fc8d59", "delay-3": "#fdcc8a", "no-clarification": "#91bfdb"}
-TIMING_LABELS  = {"immediate": "Immediate", "delay-3": "Delay-3d", "no-clarification": "No-Clr"}
+TIMING_COLORS  = {"immediate": "#fc8d59", "delayed": "#fdcc8a"}
+TIMING_LABELS  = {"immediate": "Immediate", "delayed": "Delayed"}   # 天数在渲染期由 clarification_tick 拼接
+CONTROL_LABEL  = "No clarification (common control)"
@@ loader 值域闸门
+def _strategy_rows(df):
+    """主效应 / 交互一律只用策略行。共同对照单独作参考线，绝不进入均值。"""
+    rows = df[~df["is_control"].astype(bool)]
+    for col in ("content_factor", "channel_factor"):
+        assert "not-applicable" not in set(rows[col]), \
+            f"'not-applicable' 泄漏进策略行的 {col}：is_control 过滤失效"
+    return rows

--- a/analysis/plot_trajectories.py
+++ b/analysis/plot_trajectories.py
-TIMING_STYLE = {
-    "immediate":        {...},
-    "delay-3":          {..., "label": "延迟3天"},
-    "no-clarification": {..., "label": "不澄清（对照）"},
-}
+TIMING_STYLE = {
+    "immediate": {"color": "#d62728", "ls": "-",  "lw": 2.5, "label": "即时澄清"},
+    "delayed":   {"color": "#ff7f0e", "ls": "--", "lw": 2.2, "label": "延迟澄清"},
+}
+CONTROL_STYLE = {"color": "#1f77b4", "ls": ":", "lw": 2.0, "label": "不澄清（共同对照）"}
@@ 时点标注：不再从标签数字重建，改为读数据
-    clr_tick = {"immediate": scandal_tick, "delay-3": scandal_tick + 3}.get(timing)
+    # 澄清时点唯一权威来源是数据里的 clarification_tick（trajectories.csv join 或元数据）
+    clr_tick = clarification_tick_by_timing.get(timing)   # immediate→6, delayed→10
@@
-def plot_all_12_strategies(df):
-    timing_levels  = ["immediate", "delay-3", "no-clarification"]
+def plot_all_9_conditions(df):
+    """4×2 策略面板（内容×渠道 4 行 × 时机 2 列）+ 每格叠加唯一共同对照参考线。"""
+    timing_levels = ["immediate", "delayed"]
```

（`analysis/` 两个文件的其余改动为同类替换，实施时逐处核对；`analyze.py` / `plot.py` / `plot_trial.py` 全库 grep 无匹配，不修改。）

---

## 14. 风险与回滚方案

### 14.1 风险登记

| # | 风险 | 概率 | 影响 | 缓解 | 检出手段 |
|---|---|---|---|---|---|
| R1 | 冻结的 `tests/test_task002_observability.py` 若被误纳入常规回归执行集，会在 T15 / T16 处抛 `ValueError` 终止 | 中（取决于是否误执行） | 误判为「回归失败」，实际是执行了一份绑定历史代码状态的历史证据 | §10.2 冻结 + 覆盖迁移：该文件与其 fixture 永久不变、不入执行集；长期契约由 S7 / S18 承接 | S18 第 ④ 项（断言二者未被改动）+ S7 覆盖率核对 |
| R2 | 下游残留 `delay-3` 字符串匹配（`analysis/` 三处时点字典 + 一处标签） | 高 | `KeyError` 或时点错标 | §9 第 4 / 5 行 + §13.4；S5 全库 grep 断言 | S5、S12 |
| R3 | 实施时把哨兵值误写成下划线 `not_applicable` | 中 | 数据列出现两种风格；下游值域断言失败 | 导入期断言 `"_" not in NOT_APPLICABLE`；S8 全库字面量 grep | S8 |
| R4 | 实施时把 `exp_id` 词元误写回缩写 | 中 | 与历史 legacy 标签混淆，行级判据失效 | S3 精确集合断言 | S3 |
| R5 | Replay 命中他人响应（键碰撞，§8.6）导致「miss=0 但已分叉」 | 低 | 澄清前路径悄然不一致，主效应被污染。**注意 fail-closed（R-8）对本风险无效**：碰撞时 `chat()` 不抛错 | S15 的**逐 Agent 逐 Tick 精确比较**（`agent_records`，5 字段，容差 0）。`avg_trust` 相等可以掩盖个体互换，因此不得作为唯一证据（§8.6） | S15 |
| R6 | 有人为了「对齐噪声长度」让 immediate 组在 Tick 6–9 也回放 | 低 | 用无澄清响应冒充有澄清响应，销毁处理效应 | §7.4 明确列为不可采纳伪方案；`replay_until == clarification_tick` 由 S9 断言 | S9 |
| R7 | 重复实验时在单个 run 内混入多个 seed | 中 | 触发 TASK_002 网络一致性 fail-closed（退出码 3），无网络产物 | §7.6 硬约束：一 seed 一 run 目录 | 退出码 3 + `network_inconsistency_report.json` |
| R8 | 新旧数据被合并分析 | 中 | 结论不可解释（12 伪条件与 9 实质条件混算） | §11 loader 版本闸门；`matrix_version` 唯一性检查 | S17 |
| R9 | fail-closed 引入新的失败路径：单组窗口内 miss 会使该组作废，并使批次以非零码结束 | 中 | 该组无有效轨迹；批次末尾退出码 4 | **fail-closed 本身为强制**（不再是建议项）；只有**退出码取值 4** 是建议值（与 3 / 0 区分）。风险由次序原则控制：**所有产物与图表安全落盘之后**才抛 `SystemExit(4)`，证据不因审计契约问题被销毁；失败组保留 `config` / `error_type` / `run_audit`（R12），可直接定位是哪一组因子 | 退出码 4 + `errors.log` + `experiment_matrix.replay_alignment_violated` + S10.1 |
| R10 | `to_dict()` 新增 `is_control` / `matrix_version` 键影响下游 | 低 | `experiment_metadata.jsonl` 显式构行，不受影响；`run_metadata.json` 的 `config` 块无字段契约 | S16 断言 18 键不变 | S16 |
| R11 | `budget_k=0` 被误解为「不适用」而写成 `""` | 低 | 破坏 TASK_002 的 `""` / `0` 区分约定 | §3.4 明确 0 是真实值 | S16 |

### 14.2 回滚方案

本任务的全部生产改动集中在 **5 个文件**（§9 第 1–5 项；`clarification_injector.py` 已移出清单），且**不涉及任何数据迁移、不删除任何历史文件**，因此回滚是纯代码回滚：

| 层级 | 回滚动作 | 代价 |
|---|---|---|
| L0 单文件 | `git checkout -- <file>` 撤销单个文件 | 无（工作树级） |
| L1 整任务 | `git revert` TASK_003 的实现提交 | 无。矩阵回到 12 条件，`analysis/` 回到旧词表 |
| L2 数据 | 无需动作 | 历史 `run_*` 目录从未被改写；v3.0 run 目录带自己的 `experiment_matrix` 块，回滚后仍可被识别为 v3.0 数据（只是当前代码不再产出） |
| L3 文档 | `docs/kiro_tasks/TASK_003_result.md` 为新增文件，删除即可 | 无。`TASK_002_result.md` 与 `model_change_log.md` 本任务全程不改 |

**回滚的前置条件（必须在实施前满足）**：TASK_003 的实现必须是**独立提交**（不与其它改动混提），否则 L1 revert 会牵连无关变更。提交粒度必须与 §12.1 的 7 步顺序一致：

| 提交 | 内容 | 对应 §12.1 步骤 |
|---|---|---|
| C0 | `.kiro/specs/task003-experiment-matrix/design.md` | 第 1 步 |
| C1 | `tests/test_task003_experiment_matrix.py` + `tests/fixtures/task003/pre_task003_behavior_trace.json` | 第 2–5 步（**单独提交，不含任何生产改动**） |
| C2 | `experiment_config.py` | 第 7 步起 |
| C3 | `run_experiments.py` + `simulation_core.py` | 第 7 步起 |
| C4 | `analysis/plot_experiments.py` + `analysis/plot_trajectories.py` | 第 7 步起 |

C2 / C3 / C4 各自可独立 revert；C1 **不应被 revert**（它是基线证据，回滚生产代码后它仍然有效——这正是把它单独提交的目的）。`clarification_injector.py` 不出现在任何提交中。

**不可回滚项（必须事先接受）**：`tests/test_task002_observability.py` 的可执行性依赖 12 标签词表，回滚 TASK_003 也不会使它重新进入回归执行集——按 §10.2 它已被**永久冻结**为历史验收证据。这不是回滚缺陷，而是该工具生命周期的正常终点：它证明的事情（TASK_002 diff 未改变既有行为）已在提交时完成并留档。

---

## 15. 明确不修改的机制

以下内容本任务**一律不改**，逐项对应 TASK_003 的兼容性要求：

| # | 不修改项 | 位置 | 理由 |
|---|---|---|---|
| 1 | 信任更新公式、`shock_anchor` 分支、`quiet_ticks` 逻辑、遗忘曲线 | `plugins/agent/plan/ConsumerPlanPlugin.py`、`plugins/agent/reflect/GreenCognitionPlugin.py` | 属模型机制，非实验设计 |
| 2 | Prompt 文本（reflect / plan） | 同上 | TASK_002 已登记哈希；改动会作废行为基线 |
| 3 | Persona 模板与人群配额 | `generate_data.py`、`plugins/agent/profile/GreenProfilePlugin.py` | 同上 |
| 4 | **`clarification_injector.py` 整个文件**（含 `CONTENT_TEMPLATES` 文本、`should_inject()`、`inject()`、`get_message()`） | `clarification_injector.py` | **本任务完全不修改**（R-11）。第 2 版曾预留「只可能新增一处防御性 `raise`」，本轮取消：`get_message()` 在对照下运行期不可达（`should_inject()` 先返 `False`，已核实），**不会 KeyError**，因此不需要护栏；为一个不可达分支改动一个否则完全不动的文件，只会扩大 diff 面与 revert 牵连范围。该文件不出现在 §9 清单、§13 diff 草案与 §14.2 的任何提交中 |
| 5 | 网络生成（有向 BA + 有向化规则）与 `register_agents` 路径 | `plugins/environment/network/SocialNetworkPlugin.py` | 拓扑必须与 `(num_agents, random_seed)` 的既有映射一致 |
| 6 | 节点选择算法（hub 按出度 / random 局部 RNG） | `node_selector.py` | 只在调用侧加 `is_control` 守卫，函数本体不改 |
| 7 | 指标公式（`delta_recovery`、`auc_post_scandal`、`recovery_speed`、`t50` / `t80`、`recovery_rate`、`clarification_effect`） | `metrics_calculator.py` | **指标重构属 TASK_004**，本任务不越界 |
| 8 | `agent_records` schema v2.0 的字段清单与顺序（**60 字段**） | `simulation_core.py` L136–L219 | TASK_002 契约；本任务只改字段的**值** |
| 9 | `experiment_metadata.jsonl` 的 18 字段清单 | `run_experiments.py` L380–L399 | 同上；矩阵版本信息只进 `run_metadata.json` |
| 10 | `network_nodes.csv`（5 列）/ `network_edges.csv`（3 列）契约与 run 级语义 | `run_experiments.py` L288–L290 | 不含因子列，与矩阵无关 |
| 11 | `verify_single_network()` 的 fail-closed 行为与退出码 3 | `run_experiments.py` L856、L977–L981 | 审计契约；重复实验设计反而依赖它（§7.6） |
| 12 | 全局事件脚本 `ENTERPRISE_STRATEGY` 文本与单事件 patch 机制 | `simulation_core.py`、`run_experiments.py` `_run_with_patch` | 丑闻仍在 Tick 5，其余事件仍屏蔽 |
| 13 | `Agent` 执行顺序与 Perceive → Reflect → Plan → Invoke 管线 | 框架侧 | 行为不变性前提 |
| 14 | 已提交的任务记录 | `docs/kiro_tasks/TASK_002_result.md`、`docs/decisions/model_change_log.md` | **已提交并推送，禁止修改** |
| 15 | 既有测试文件、既有 fixture、配置 | `tests/test_task001_state_reset.py`、`tests/test_task002_observability.py`、`tests/fixtures/task002/**`、`configs/**` | **永久冻结 / 不改**。唯一允许新增的是 `tests/test_task003_experiment_matrix.py` 与 `tests/fixtures/task003/pre_task003_behavior_trace.json`，且必须按 §12.1 的 7 步顺序在应用生产 diff **之前**完成并单独提交 |
| 16 | 真实 LLM 实验 | — | **本设计阶段不运行任何真实 LLM 实验** |

---

## 附录 A：决策二原文保留 —— `delay-5` vs `delayed`

（本节与裁定一一致，第 1 版原文保留，仅将示例 `exp_id` 更新为完整词形式。）

**采用 `timing_factor = "delayed"`**，并显式记录 `clarification_tick = 10`（= 丑闻后 5 个 Tick）。理由按四个评估维度逐条给出：

1. **可读性**：`delayed` 在图表与 CSV 里读作「延迟澄清」，语义完整。天数并未丢失——它在同一行的 `clarification_tick` / `clarification_tick_config` 列里，且图例在渲染期拼成 `Delayed (T10)`。**数字显示出来，但不住在标识符里。**
2. **与 `scandal_tick` 解耦**：`delayed` 不对偏移量作任何承诺，偏移量是 `DELAYED_OFFSET_TICKS` 这一个常量。`delay-5` 则在字符串里复制了一份偏移量，形成两个必须手工同步的事实来源——这正是当前缺陷的成因（历史上偏移从 +3 调到 +5，代码改了、标签没改）。
3. **未来若改 `scandal_tick` 是否仍自洽**：`delayed` 恒自洽——它只说「晚于 immediate」，而 `scandal_tick < immediate_tick < delayed_tick ≤ total_ticks` 由 `__post_init__` 段三强制。`delay-5` 的语义是「丑闻后第 5 天」，改 `scandal_tick` 时仍成立（偏移不变），但**改偏移时立即失效**；而偏移正是最可能被调的旋钮（本项目已经调过一次）。
4. **下游字符串匹配风险**：已核实存在 4 处按标签数字重建时点的匹配（§1.1 表）。`delay-5` 会诱使这些匹配继续存在（因为标签「看起来」提供了数字）；`delayed` 使标签不含任何可推导信息，迫使下游去读 `clarification_tick`——这是我们要的方向。再加一条模块级断言禁止时机标签含数字（§4 不变量 1），把这类缺陷永久挡在门外。

**被否方案 `delay-5` 的代价（诚实列出其真实优点与放弃它的损失）**：
优点是「自解释」——看一眼就知道第 5 天，无需 join 元数据，对论文读者友好。
放弃它的损失就是这份便利，**补偿手段**是：图例/表头在渲染期由 `clarification_tick` 拼接出天数，`experiment_metadata.jsonl` 与 `agent_records.csv` 逐行携带该 Tick。
选择 `delay-5` 的代价则是：偏移量存在两个来源；任何偏移调整都要重命名标签，进而作废已归档的 `exp_id` 与图表；且它给下游一个「标签里有数字，可以直接解析」的错误示范。**便利换正确性，不划算。**

---

## 附录 B：修订自检

### B.1 第 3 版（本轮 6 项定向补正）自检

| # | 检查项 | 结果 |
|---|---|---|
| R-7 | §10.2 已整节重写为「历史验收工具冻结与当前回归覆盖迁移」；6 条规定齐备（冻结测试、冻结 fixture、历史证据 270/268/0/2/退出码 0、diff 前新增两文件、承接 7 项归 S18、不重新生成 TASK_002 fixture 与不改其 `test_harness_sha256`）；harness 哈希 + fixture 不可重生成的技术论证保留于 §10.2.2；结论措辞为「冻结 + 覆盖迁移」；已写明冻结后不入常规回归执行集属**设计决定**而非缺陷 | ✅ 全文再无「不可避免的破坏 / 将无法再执行」作为该节主框架（§14 R1 亦已重写为「误纳入执行集」风险） |
| R-8 | §8.5 已按 fail-closed 重写：三条强制语义（`miss_count += 1` → 立即 `raise ReplayAlignmentError` → 禁止 fallback）；`ReplayAlignmentError` 定义位置（`run_experiments.py` 模块级，Router 分节内）与最小定义已给出；分级表已无「静默降级」一级；失败实验保留 `config` / `error_type` / `run_audit`（引用 TASK_002 R12）；退出码 4（建议值）+ 产物落盘后再抛；明确禁止「只 `errors.append` 后继续当有效结果」。§8.3 规则 3、§8.4 `replay_miss_count` 值域（`{0,1}`）、§7.1 原则 3、§13.2 三处 diff（Router / `except` / 末尾退出码）、§14 R5+R9 已同步 | ✅ 全文再无「窗口内 miss 后降级调用真实 Router」 |
| R-9 | S15 主证据改为 `agent_records` 逐 Agent 逐 Tick 精确比较（键 `tick` + `agent_id`；immediate Tick 1–5 / delayed Tick 1–9；5 字段 `trust_score_raw` / `shock_anchor_after_raw` / `quiet_ticks` / `is_buying` / `is_posting`；容差 0）；明确排除 4 个必然不同字段；`avg_trust` 降级为汇总检查并给出「均值相等可掩盖个体互换」的理由（引用 §8.6 键碰撞分析）；选字段理由（运行期状态直接落盘 + 与 TASK_002 `COMPARED_FIELDS` 同源，仅精度更严）已写入 §8.6 | ✅ Property 7 措辞已更新，仍为导航性质、未新增规则 |
| R-10 | 新增 §12.1：7 步顺序表（提交 design → 建测试 → 洁净树生成 fixture → 记录 6 项 → 单独提交 → 冻结 → 才应用生产 diff）+ 每步不可调换理由；复用机制表逐项引用 TASK_002（洁净前置检查退出码 2、`git_is_dirty` 必须 bool 且 `True` 允许、`test_harness_sha256` 完全相同、`git merge-base --is-ancestor`）；已说明轨迹字段与补正三 5 字段对齐、与 TASK_002 fixture 各自独立互不覆盖；§14.2 提交粒度表引用 7 步 | ✅ |
| R-11 | 生产文件收窄为 5 个；`clarification_injector.py` 已从 §9 清单删除、§13 无其 diff 片段（并加显式声明）、§15 第 4 项改为「本任务完全不修改」并保留「运行期不可达、不会 KeyError」作为不需要护栏的依据、§6.3 处置列同步、§14.2 提交粒度表不含该文件；新增 TASK_003 fixture 已加入 §9 清单第 7 行 | ✅ 全文再无 `clarification_injector.py` 出现在实施清单中 |
| R-12 | §12 重排为 §12.0 S 编号总表（S1–S18，逐项标注离线 / 运行期）+ §12.1 基线流程 + §12.2 明细；S1–S14 语义未变，仅 S10 按补正二增补子项 S10.1（不占新编号）；S15 / S16 / S17 / S18 按裁定定义；§10.2.3 的 7 项归入 S18，S7 保留为其离线 schema 子集并显式声明不重复计数 | ✅ S 编号 S1–S18 连续无缺 |
| — | Kiro spec 兼容层完好：7 个模板小节（Overview / Architecture / Components and Interfaces / Data Models / Correctness Properties / Error Handling / Testing Strategy）与 7 个 `Property N:` 标题（各含 `**Validates: Requirements X.Y**` 行）均未删除、未改标题 | ✅ 仅更新 Property 7 的说明文字与两处 §12 引用（S1–S17 → S1–S18） |
| — | 未修改生产代码 / 测试 / fixture / 配置；未应用任何 diff；未创建任何测试或 fixture 文件；未触碰 TASK_002 的两份已提交文档；未运行真实 LLM | ✅ 本轮唯一写入 `.kiro/specs/task003-experiment-matrix/design.md` |

### B.2 第 2 版自检（原文保留）

| 检查项 | 结果 |
|---|---|
| 全文无 `not_applicable`（下划线）作为**取值** | ✅ 取值一律 `not-applicable`。下划线仅出现在 Python 常量名 `NOT_APPLICABLE` 与 JSON 键名 `not_applicable_value`，二者均在 §3.1 / §11.1 显式说明 |
| 无 `Imm` / `Del` 缩写作为**采用的** exp_id 词元 | ✅ 采用值全为 `Immediate` / `Delayed`。缩写仅出现在 §1.2（引用当前代码 L56 的 `timing_map`）、§5 历史对照表、§11.2 legacy 判定规则，均显式标注「已废弃历史标签」 |
| 无第 1 版的 `Control-` 前缀式对照 id | ✅ 已全部替换；共同对照的唯一写法为 `NoClarification-Control`（§2 / §5 / §6.4 / §7.2 / §11.1 逐处一致） |
| 无 `delay-3` / `delay-5` 作为**建议采用值** | ✅ `delay-3` 仅作为已废弃历史标签（§1.1、§1.3、§10.2、§11.2）；`delay-5` 仅作为被否方案（附录 A） |
| 9 个 exp_id 与裁定四完全一致 | ✅ §2 表、§5 清单、§6.4 对比表、§11.1 `replay_until_by_exp_id` 四处逐字一致 |
| 明确写出「延迟澄清 = 丑闻后 5 个 Tick，当前配置 Tick 10」 | ✅ §4 固定表述块；另见 §2 表注与 §13.1 代码注释 |
| 明确写出「Replay 不能替代重复实验」 | ✅ §7.5 独立小节（含两条禁止项） |
| 明确写出 `ReplayRouter` 当前不支持分叉后录制 + 最小接口调整 | ✅ §8.1 逐行核实表 + 明确结论；§8.3 方案 A/B 与推荐；§8.4 三个审计字段语义影响 |
| 明确写出 `agent_records` 仍为 60 字段 | ✅ §10.1 首行 + §15 第 8 项 + §12 / S7 |
| 15 个章节齐备且编号符合规定顺序 | ✅ §1–§15 + 附录 A/B |
| 未创建或修改其它文件、未应用任何 diff、未运行真实 LLM | ✅ 唯一写入 `.kiro/specs/task003-experiment-matrix/design.md` |

> 第 2 版自检中「§10.2 裁定」「Replay miss 分级 L1/L2」「S1–S17」三处已被第 3 版的 R-7 / R-8 / R-12 取代，以 B.1 为准。
