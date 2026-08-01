"""
TASK_003-V: 实验矩阵重构（12 伪条件 → 9 实质条件，matrix v3.0）验收测试

权威依据: .kiro/specs/task003-experiment-matrix/design.md（第 4 版）
          验收项定义见该文档 §12.0 / §12.2；基线流程见 §12.1。

三种运行模式（必须显式选择其一；无参数调用会拒绝执行并退出码 2）
────────────────────────────────────────────────────────────────────────
    python tests/test_task003_experiment_matrix.py --generate-fixture
        **只**生成 pre-TASK_003 行为基线 fixture（§12.1 第 3 步）。
        不运行 S1–S18；不要求新矩阵已经实施。
        前置（三项同时检查）：生产路径无 unstaged diff、无 staged diff、
        无未跟踪文件；溯源可判定。任一不满足 → 退出码 2。

    python tests/test_task003_experiment_matrix.py --offline-only
        运行离线验收（S1–S14、S17、S18）。S15 / S16 无运行目录时记 WARN。
        报告头尾均明确输出 "NOT A FULL ACCEPTANCE"。
        退出码 0 = 无 FAIL，1 = 存在 FAIL。**这不是正式验收。**

    python tests/test_task003_experiment_matrix.py --runtime-dir PATH
        正式验收。PATH 必须是 matrix_version == "3.0" 且 condition_count == 9
        的运行目录；S15 / S16 遇到缺文件、缺行、版本不符一律 FAIL。
        **绝不自动回退读取 results/experiments/latest。**
        退出码 0 仅在 Failed == 0 时给出。

pre-TASK_003 fixture 的语义（不得扩大解释）
────────────────────────────────────────────────────────────────────────
    该 fixture 证明的是：
        「TASK_003 的实施未改变既有的信任更新、shock_anchor、quiet_ticks
          与行为决策机制。」
    它**不是**旧 12 条件矩阵正确性的证明；
    它**不要求**旧 ExperimentConfig 接受 "delayed" 或 "not-applicable"。
    因此 fixture 的采集路径只驱动三个 Agent 插件，完全不构造 ExperimentConfig。

验收项映射（S 编号与 design.md §12.0 逐项对应）
────────────────────────────────────────────────────────────────────────
    S1   EXPERIMENT_MATRIX_VERSION == "3.0" 且矩阵长度 == 9          [离线]
    S2   is_control 恰 1 条 / 策略恰 8 条 / 完整 2×2×2 交叉           [离线]
    S3   9 个 exp_id 逐字相等；对照 id 不含任何因子词元               [离线]
    S4   clarification_tick: immediate→6 / delayed→10 / 对照→None     [离线]
    S5   旧标签只在 legacy 语境中允许出现（AST + 符号白名单，非全库 grep）：
         当前矩阵配置 / STRATEGY_TIMING_LEVELS / 当前 exp_id /
         experiment_config 活跃因子常量 / analysis 当前图例·分组·时点映射  [离线]
    S6   组合级校验反证（13 类非法组合必须抛 ValueError）             [离线]
    S7   TASK_002 契约 7 项的纯 schema 断言（60 / 18 字段等）         [离线]
    S8   哨兵值为连字符 "not-applicable"；生产 Python 的 AST 中
         精确字面量 "not_applicable" 不得作为当前字段值               [离线]
    S9   录制组 == 共同对照；策略组 replay_until == clarification_tick
         且 total_ticks + 1 魔法值已从源码删除                        [离线]
    S10  ReplayRouter **行为契约**（不绑定任何实现细节属性）：
         窗口内命中 → 真实 Router 调用数 0；窗口内 miss → miss_count+1
         且抛 ReplayAlignmentError 且真实 Router 调用数 0；窗口外正常调用；
         窗口外不增加 miss_count；**所有路径都不得修改共同对照基线 cache** [离线]
    S10.1 fail-closed 的失败面：异常类型、禁止 fallback、
         失败元数据保留完整 config / error_type / run_audit、退出码 4  [离线]
    S11  summary.csv 列契约：含 is_control；错误行格数 == 表头格数    [离线]
    S12  run_experiments 调用的绘图函数名在 analysis 模块中全部存在   [离线]
    S13  分析层**功能**闸门（不限定 helper 名称与内部组织）：
         输入 8 策略 + 1 对照 → 实际只使用 8 策略行；对照不进入主效应与
         交互；is_control=False 却带 not-applicable 必须抛错。
         **并且（R-30 / R-31）集成验证**：按生产调用序列与数据流重放全部
         plot_experiments 入口，每个入口必须获得**终局判定** ——
         factorial-entry-pass（聚合正确且调用了闸门）或 not-factorial-entry
         （静态可达性证明其调用链不做因子聚合）；entry-error 与
         unknown-not-proven 一律 FAIL，不得停留在中性状态          [离线]
    S14  统计口径：对比 2–8 只用 8 个策略条件，对照不出现在任一侧     [离线]
    S15  逐 Agent 处理前路径对齐，三层递进：
         ①键唯一性（count 必须恰为 1）；
         ②**绝对预期键空间**：9 exp_id × Tick 1..total_ticks × network_nodes 的
           agent_id，逐一核对 missing / extra / count==0（count==0 只能靠
           独立于实际数据的期望集合发现）；
         ③处理前窗口内策略组与对照 5 字段逐字相等。任一层不成立即停止下一层 [运行期]
    S16  运行期产物：experiment_matrix 块 / 9 行元数据 /
         **batch_exit_code == 0 且 run_completed is True**（机器可读）  [运行期]
    S17  legacy 闸门双向用例                                          [离线]
    S18  TASK_002 契约承接登记 + TASK_002 冻结校验
         + pre-TASK_003 行为不变性（fixture）
         + **baseline_file_sha256 逐项比对三个 Agent 插件的当前哈希**。
         **正式模式下缺 fixture 或任一溯源项不成立均 FAIL**             [离线]

设计边界（本测试自身的约束）
────────────────────────────────────────────────────────────────────────
  · 不修改任何生产代码、不修改 TASK_002 测试与 fixture、不访问网络、
    不调用真实 LLM、不加载 SBERT 模型。
  · 「不可判定」只在 --offline-only 模式下记 WARN：
    "尚未产出证据" 与 "证据表明违约" 是两件事，不得混为一谈。
    在 --runtime-dir 模式下，S13（依赖不可用 / 无可验证闸门）、
    S15 / S16（缺运行目录、缺文件、缺行、版本不符）、
    S18（缺 fixture / fixture 不可读）**一律 FAIL**。
    理由：一次不能判定的验收不构成验收。
  · 旧标签（delay-3 / delay-5 / -Imm / -D3 / -NoClr）在 legacy 检测逻辑、
    LEGACY_* 常量、本测试的反例、以及设计与历史文档中**允许存在**；
    S5 只禁止它们出现在"当前生效"的因子词表、exp_id 与分析口径中。
  · 本文件在 pre-TASK_003 代码状态下即可导入并运行。实施后才成立的断言
    此时会 FAIL，这是预期的（§12.1 第 2 步：测试先于实现定稿）。
"""
import sys
import os
import re
import ast
import inspect
import csv
import json
import copy
import asyncio
import hashlib
import logging
import argparse
import datetime
import tempfile
import subprocess
import py_compile

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)          # GreenConsumer/
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 在导入任何插件之前禁用 sentence-transformers：
# sys.modules[name] = None 会让 `from sentence_transformers import ...` 抛 ImportError，
# 从而命中 MemoryManager 中**已存在**的回退分支（不改动 MemoryManager 任何代码）。
if "sentence_transformers" not in sys.modules:
    sys.modules["sentence_transformers"] = None

import random as random_module
import numpy as np

from plugins.agent.reflect.GreenCognitionPlugin import GreenCognitionPlugin
from plugins.agent.plan.ConsumerPlanPlugin import ConsumerPlanPlugin
from plugins.agent.invoke.GreenInvokePlugin import GreenInvokePlugin

# ══════════════════════════════════════════════════════════════════════
# fixture 位置（与 TASK_002 的 fixture 各自独立、互不覆盖：不同目录、
# 不同读取者、不同代码状态。design §10.2.1 第 6 项 / §12.1）
# ══════════════════════════════════════════════════════════════════════

FIXTURE_DIR = os.path.join(current_dir, "fixtures", "task003")
FIXTURE_PATH = os.path.join(FIXTURE_DIR, "pre_task003_behavior_trace.json")
FIXTURE_SEED = 42
FIXTURE_VERSION = "1.0"

# 永久冻结的 TASK_002 验收工具（design §10.2）。本任务一字不改。
TASK002_TEST_REL = "tests/test_task002_observability.py"
TASK002_FIXTURE_REL = "tests/fixtures/task002/pre_task002_behavior_trace.json"

# 本设计文档（§12.1 第 1 步要求它在生成 fixture 之前**已经提交**）
DESIGN_DOC_REL = ".kiro/specs/task003-experiment-matrix/design.md"

# ── pre-TASK_003 生产代码基线（R-29）────────────────────────────────
#
# 这是「TASK_003 生产 diff 尚未应用」这一状态的**锚点**，不是一个可推断的量：
# 仅检查工作树 clean 完全不够——只要有人把 TASK_003 的生产改动**提交**掉，
# 工作树就是干净的，而 fixture 会被当作 pre 状态的基线记录下来，
# 从此 pre/post 比较变成 post/post 自比，永远通过。
#
# 因此除三路工作树检查之外，还必须验证
#     git diff --quiet PRE_TASK003_BASE_COMMIT..HEAD -- <PRODUCTION_PATHS>
# 它证明的是：**HEAD 与 PRE_TASK003_BASE_COMMIT 在 PRODUCTION_PATHS 上的树内容
# 完全一致，不存在净文件差异**。注意这不等于「期间从未出现过修改提交」——
# 改了又改回来同样通过。这正是我们需要的语义：pre-TASK_003 代码状态的要求是
# **最终树内容相同**，中间过程无关。因此本设计不附加任何 git log 历史禁令。
#
# 取值 = `git rev-parse c8558d5`（TASK_002 记录收尾提交，TASK_003 生产改动前的最后一个提交）
PRE_TASK003_BASE_COMMIT = "c8558d57f501dd32d483a2b2d939a06129554365"

# fixture 生成守卫的版本号。守卫规则变更时必须递增，
# 以便 S18 能区分「用旧守卫生成的 fixture」与「用当前守卫生成的 fixture」。
#
# 保持 "2.0"：本轮修的是 S13 的一处格式化缺陷，**守卫规则本身未变**。
FIXTURE_GENERATION_GUARD_VERSION = "2.0"

# ── fixture 作废与重新生成记录 ──────────────────────────────────────
# 第一份 fixture（harness sha256 0634b315…，generated_from_commit 0ae00a3）已作废。
# 作废原因：
#   Regenerated because S13 unavailable-path formatting used tuple indexing
#   on dict records and could raise KeyError before mode-aware verdict handling.
# 该缺陷使「依赖不可用」分支在 formal / offline 分档之前崩溃，从未真正执行。
# 修复改变了本测试文件的哈希，因此旧 fixture 的 test_harness_sha256 必然不再匹配，
# 不得继续使用；已删除并按 §12.1 第 3 步重新生成。

# ══════════════════════════════════════════════════════════════════════
# 目标矩阵 v3.0 的期望值（design §2 / §4 / §5 / §6.1 / §11.1）
#
# 这些常量是测试自带的**独立期望**，刻意不从 experiment_config 导入：
# 若两侧都读同一个来源，断言就会退化成同义反复。
# ══════════════════════════════════════════════════════════════════════

EXPECTED_MATRIX_VERSION = "3.0"
EXPECTED_CONDITION_COUNT = 9
EXPECTED_STRATEGY_COUNT = 8
EXPECTED_CONTROL_COUNT = 1

EXPECTED_CONTENT_LEVELS = ("rational-evidence", "emotional-empathy")
EXPECTED_CHANNEL_LEVELS = ("hub", "random")
EXPECTED_STRATEGY_TIMING_LEVELS = ("immediate", "delayed")
EXPECTED_CONTROL_TIMING = "no-clarification"
EXPECTED_CONTROL_EXP_ID = "NoClarification-Control"

# 哨兵值：**连字符**形式（落盘字面量）。常量名用下划线仅因 Python 标识符限制。
EXPECTED_NOT_APPLICABLE = "not-applicable"
# 被禁止的下划线写法。刻意拼接构造，避免本文件出现该字面量而污染 S8 的全库扫描。
FORBIDDEN_SENTINEL = "not" + chr(95) + "applicable"

EXPECTED_SCANDAL_TICK = 5
EXPECTED_IMMEDIATE_OFFSET = 1
EXPECTED_DELAYED_OFFSET = 5
EXPECTED_IMMEDIATE_TICK = EXPECTED_SCANDAL_TICK + EXPECTED_IMMEDIATE_OFFSET      # 6
EXPECTED_DELAYED_TICK = EXPECTED_SCANDAL_TICK + EXPECTED_DELAYED_OFFSET          # 10
EXPECTED_STRATEGY_BUDGET_K = 3
EXPECTED_CONTROL_BUDGET_K = 0

# design §2 表：8 个策略 exp_id（完整词元，禁止缩写）
EXPECTED_STRATEGY_EXP_IDS = frozenset({
    "Rational-Hub-Immediate", "Rational-Hub-Delayed",
    "Rational-Random-Immediate", "Rational-Random-Delayed",
    "Empathy-Hub-Immediate", "Empathy-Hub-Delayed",
    "Empathy-Random-Immediate", "Empathy-Random-Delayed",
})
EXPECTED_EXP_IDS = frozenset(EXPECTED_STRATEGY_EXP_IDS | {EXPECTED_CONTROL_EXP_ID})

# design §11.1：策略组的回放边界 == 各自的 clarification_tick
EXPECTED_REPLAY_UNTIL = {
    "Rational-Hub-Immediate": EXPECTED_IMMEDIATE_TICK,
    "Rational-Random-Immediate": EXPECTED_IMMEDIATE_TICK,
    "Empathy-Hub-Immediate": EXPECTED_IMMEDIATE_TICK,
    "Empathy-Random-Immediate": EXPECTED_IMMEDIATE_TICK,
    "Rational-Hub-Delayed": EXPECTED_DELAYED_TICK,
    "Rational-Random-Delayed": EXPECTED_DELAYED_TICK,
    "Empathy-Hub-Delayed": EXPECTED_DELAYED_TICK,
    "Empathy-Random-Delayed": EXPECTED_DELAYED_TICK,
}

# ── 已废弃的历史标签与词元 ──────────────────────────────────────────
# 重要：这些字面量在以下语境中**合法**，S5 绝不因其存在而报错：
#   · LEGACY_* 前缀的常量；
#   · is_legacy_run() 及任何 legacy 检测逻辑；
#   · 本测试文件中的反例输入；
#   · 设计文档与历史文档（非 Python，不在扫描范围内）。
# S5 只禁止它们出现在"当前生效"的因子词表、exp_id 与分析口径中。
LEGACY_TIMING_LABELS = ("delay-3", "delay-5")
LEGACY_ID_TOKEN_SUFFIXES = ("-Imm", "-D3", "-NoClr")
# exp_id 中不得出现的旧标签子串（裁定一第 3 项）
LEGACY_ID_SUBSTRINGS = ("D3", "Delay-3", "Delay-5")

# 判定"legacy 语境"的符号名标记：名称含此标记的常量/函数允许携带旧标签
LEGACY_CONTEXT_MARKER = "legacy"

# ── S5 的活跃符号白名单（AST 定向检查，不做全库 grep）──────────────
# 键 = 文件；值 = 该文件中"当前生效"的因子常量名。只检查这些符号的字面量。
ACTIVE_FACTOR_CONSTANTS = {
    "experiment_config.py": (
        "NOT_APPLICABLE", "CONTENT_LEVELS", "CHANNEL_LEVELS",
        "STRATEGY_TIMING_LEVELS", "CONTROL_TIMING", "CONTROL_EXP_ID",
        "VALID_CONTENT_FACTORS", "VALID_CHANNEL_FACTORS", "VALID_TIMING_FACTORS",
        "CONTENT_ID_TOKEN", "CHANNEL_ID_TOKEN", "TIMING_ID_TOKEN",
    ),
    # analysis 的"当前图例"与"当前分组"常量
    "analysis/plot_experiments.py": (
        "CONTENT_COLORS", "CHANNEL_COLORS", "TIMING_COLORS",
        "CONTENT_LABELS", "CHANNEL_LABELS", "TIMING_LABELS",
    ),
    "analysis/plot_trajectories.py": (
        "TIMING_STYLE", "CONTENT_STYLE", "CHANNEL_STYLE",
    ),
}

# S5 第 5 项"当前时点映射"：analysis 中以时机为键的 dict 字面量（含函数体内）
TIMING_MAPPING_SCAN_FILES = (
    "analysis/plot_trajectories.py",
    "analysis/plot_experiments.py",
)

# S8 的扫描范围：只查生产 Python 文件的 AST 精确字面量
S8_SCAN_FILES = (
    "experiment_config.py",
    "run_experiments.py",
    "simulation_core.py",
    "clarification_injector.py",
    "node_selector.py",
    "metrics_calculator.py",
    "analysis/plot_experiments.py",
    "analysis/plot_trajectories.py",
)
# 共同对照 exp_id 中不得出现的任何因子词元（design §5 第四条性质）
FORBIDDEN_CONTROL_ID_TOKENS = ("Rational", "Empathy", "Hub", "Random",
                               "Immediate", "Delayed")

# ══════════════════════════════════════════════════════════════════════
# TASK_002 契约（design §10.2.3 的 7 项；S7 执行 schema 断言，S18 登记归属）
# ══════════════════════════════════════════════════════════════════════

EXPECTED_AGENT_RECORDS_FIELD_COUNT = 60
EXPECTED_EXPERIMENT_METADATA_FIELD_COUNT = 18
EXPECTED_AGENT_RECORDS_SCHEMA_VERSION = "2.0"

TASK002_CONTRACT_ITEMS = {
    "C1": "AGENT_RECORDS_FIELDS 长度 60 且无重复",
    "C2": "schema v1.0 的 21 字段相对顺序严格递增",
    "C3": "EXPERIMENT_METADATA_FIELDS 仍为 18 且键集合不变",
    "C4": "build_agent_record() 输出键集合 == 60 字段（对照与策略各一次）",
    "C5": "共同对照 clarification_tick_config == \"\"，不是 0、不是 int",
    "C6": "NETWORK_NODES_FIELDS / NETWORK_EDGES_FIELDS 列契约不变且不含 exp_id",
    "C7": "router_role / recording_cache_size / replay_miss_count 的 \"\" 与 0 可区分",
}

# schema v1.0 的 21 个字段（相对顺序必须在 v2.0 中保持递增）
V1_FIELDS = [
    "exp_id", "tick", "agent_id", "cluster_type", "social_role",
    "trust_score", "baseline_trust", "trust_after_decay",
    "affective_change", "shock_anchor", "quiet_ticks", "decay_lambda",
    "is_buying", "is_posting", "post_content",
    "hypocrisy_perceived", "importance", "reasoning",
    "has_global_event", "has_clarification", "cumulative_buyers",
]

EXPECTED_NETWORK_NODES_FIELDS = ["agent_id", "cluster_type", "social_role",
                                 "out_degree", "in_degree"]
EXPECTED_NETWORK_EDGES_FIELDS = ["source_agent_id", "target_agent_id", "is_directed"]

# ══════════════════════════════════════════════════════════════════════
# 统计口径：design §6.4 的 8 个 planned contrast
#   对比 1 = any clarification vs common control（唯一涉及对照的对比）
#   对比 2–8 = 2×2×2 内部，**只用 8 个策略条件**，对照不出现在任一侧
# ══════════════════════════════════════════════════════════════════════

def _ids(*specs):
    """把 (content, channel, timing) 三元词元拼成 exp_id 集合。"""
    return frozenset("-".join(s) for s in specs)


CONTRAST_TABLE = {
    "C-main-content": {
        "plus": _ids(("Rational", "Hub", "Immediate"), ("Rational", "Hub", "Delayed"),
                     ("Rational", "Random", "Immediate"), ("Rational", "Random", "Delayed")),
        "minus": _ids(("Empathy", "Hub", "Immediate"), ("Empathy", "Hub", "Delayed"),
                      ("Empathy", "Random", "Immediate"), ("Empathy", "Random", "Delayed")),
    },
    "C-main-channel": {
        "plus": _ids(("Rational", "Hub", "Immediate"), ("Rational", "Hub", "Delayed"),
                     ("Empathy", "Hub", "Immediate"), ("Empathy", "Hub", "Delayed")),
        "minus": _ids(("Rational", "Random", "Immediate"), ("Rational", "Random", "Delayed"),
                      ("Empathy", "Random", "Immediate"), ("Empathy", "Random", "Delayed")),
    },
    "C-main-timing": {
        "plus": _ids(("Rational", "Hub", "Immediate"), ("Rational", "Random", "Immediate"),
                     ("Empathy", "Hub", "Immediate"), ("Empathy", "Random", "Immediate")),
        "minus": _ids(("Rational", "Hub", "Delayed"), ("Rational", "Random", "Delayed"),
                      ("Empathy", "Hub", "Delayed"), ("Empathy", "Random", "Delayed")),
    },
    "C-int-content-channel": {
        "plus": _ids(("Rational", "Hub", "Immediate"), ("Rational", "Hub", "Delayed"),
                     ("Empathy", "Random", "Immediate"), ("Empathy", "Random", "Delayed")),
        "minus": _ids(("Rational", "Random", "Immediate"), ("Rational", "Random", "Delayed"),
                      ("Empathy", "Hub", "Immediate"), ("Empathy", "Hub", "Delayed")),
    },
    "C-int-content-timing": {
        "plus": _ids(("Rational", "Hub", "Immediate"), ("Rational", "Random", "Immediate"),
                     ("Empathy", "Hub", "Delayed"), ("Empathy", "Random", "Delayed")),
        "minus": _ids(("Rational", "Hub", "Delayed"), ("Rational", "Random", "Delayed"),
                      ("Empathy", "Hub", "Immediate"), ("Empathy", "Random", "Immediate")),
    },
    "C-int-channel-timing": {
        "plus": _ids(("Rational", "Hub", "Immediate"), ("Empathy", "Hub", "Immediate"),
                     ("Rational", "Random", "Delayed"), ("Empathy", "Random", "Delayed")),
        "minus": _ids(("Rational", "Hub", "Delayed"), ("Empathy", "Hub", "Delayed"),
                      ("Rational", "Random", "Immediate"), ("Empathy", "Random", "Immediate")),
    },
    "C-int-three-way": {
        "plus": _ids(("Rational", "Hub", "Immediate"), ("Rational", "Random", "Delayed"),
                     ("Empathy", "Hub", "Delayed"), ("Empathy", "Random", "Immediate")),
        "minus": _ids(("Rational", "Hub", "Delayed"), ("Rational", "Random", "Immediate"),
                      ("Empathy", "Hub", "Immediate"), ("Empathy", "Random", "Delayed")),
    },
}

# 对比一单列：它是唯一允许出现对照的对比
CONTRAST_ANY_VS_CONTROL = {
    "plus": EXPECTED_STRATEGY_EXP_IDS,
    "minus": frozenset({EXPECTED_CONTROL_EXP_ID}),
}

# ══════════════════════════════════════════════════════════════════════
# 源码扫描范围
# ══════════════════════════════════════════════════════════════════════

# TASK_003 允许修改的 5 个生产文件（design §9）
PRODUCTION_FILES_TASK003 = [
    "experiment_config.py",
    "run_experiments.py",
    "simulation_core.py",
    os.path.join("analysis", "plot_experiments.py"),
    os.path.join("analysis", "plot_trajectories.py"),
]

# 本任务**明确不修改**的文件（design §15）；S18 只对 TASK_002 两个产物做哈希冻结校验
UNTOUCHED_FILES_TASK003 = [
    "clarification_injector.py",
    "node_selector.py",
    "metrics_calculator.py",
    "generate_data.py",
]

# 生产树洁净前置检查的范围（design §12.1 / §12.6.1）。
# 故意排除 tests/ —— 生成 fixture 时本测试文件尚未提交（第 5 步才提交），
# 纳入检查会形成死锁。design.md 此时**已经提交**（第 1 步），排除 .kiro/
# 与它的提交状态无关，只是因为该目录不属于生产路径。
PRODUCTION_PATHS = [
    "run_experiments.py",
    "simulation_core.py",
    "experiment_config.py",
    "node_selector.py",
    "clarification_injector.py",
    "metrics_calculator.py",
    "generate_data.py",
    "custom_controller.py",
    "analysis",
    "plugins",
    "configs",
]

# fixture 溯源用：直接决定行为轨迹的三个插件
BASELINE_HASHED_FILES = (
    "plugins/agent/plan/ConsumerPlanPlugin.py",
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "plugins/agent/invoke/GreenInvokePlugin.py",
)

# fixture 溯源用：TASK_003 将要修改的 5 个生产文件（记录改动前哈希）
PRETASK003_HASHED_FILES = tuple(p.replace(os.sep, "/") for p in PRODUCTION_FILES_TASK003)

CLUSTER_TYPES = ["Active_Greens", "Convenient_Greens", "Dormant_Greens", "Non_Greens"]
INITIAL_TRUST_MAP = {
    "Active_Greens": 8.0, "Convenient_Greens": 6.5,
    "Dormant_Greens": 5.5, "Non_Greens": 5.0,
}

# S15 / S18 共用的 5 个精确比较字段（design §12.1 / §12.2 S15）。
# 选 *_raw 而非 round(…,4) 版本：比较对象是运行期未舍入内存状态，容差 0。
COMPARED_FIELDS = ["trust_score_raw", "shock_anchor_after_raw",
                   "quiet_ticks", "is_buying", "is_posting"]

# S15 明确**不比较**的字段（按设计本就应当不同，比较即必然失败）
S15_EXCLUDED_FIELDS = ("is_clarification_target", "content_factor",
                       "channel_factor", "timing_factor")


# ══════════════════════════════════════════════════════════════════════
# 判定记录器（与 TASK_002 同构，便于两份报告并列阅读）
# ══════════════════════════════════════════════════════════════════════

class Verdicts:
    def __init__(self):
        self.items = []

    def check(self, group, name, passed, expected="", actual="", note=""):
        self.items.append({
            "group": group, "assertion": name,
            "result": "PASS" if passed else "FAIL",
            "expected": str(expected), "actual": str(actual), "note": note,
        })
        return bool(passed)

    def warn(self, group, name, note):
        self.items.append({
            "group": group, "assertion": name, "result": "WARN",
            "expected": "", "actual": "", "note": note,
        })

    def error(self, group, name, note):
        return self.check(group, name, False, "no exception", "exception", note)

    @property
    def n_pass(self):
        return sum(1 for v in self.items if v["result"] == "PASS")

    @property
    def n_fail(self):
        return sum(1 for v in self.items if v["result"] == "FAIL")

    @property
    def n_warn(self):
        return sum(1 for v in self.items if v["result"] == "WARN")


# ══════════════════════════════════════════════════════════════════════
# Fake 基础设施（与 tests/test_task002_observability.py 同构）
# 只用于驱动**冻结不改**的三个 Agent 插件采集行为轨迹。
# ══════════════════════════════════════════════════════════════════════

class FakeStatePlugin:
    def __init__(self):
        self._state_data = {}
        self.state_data = self._state_data
        self._memories = []

    async def set_state(self, key, value):
        self._state_data[key] = value
        self.state_data = self._state_data

    def get_state_sync(self, key):
        return self._state_data.get(key)

    def add_to_memory(self, tick, content, importance=5.0):
        self._memories.append({"tick": tick, "content": content, "importance": importance})

    def retrieve_memory(self, current_tick, query, top_k=3):
        return [m["content"] for m in self._memories[-top_k:]]


class FakeProfilePlugin:
    def __init__(self, cluster_type="Convenient_Greens"):
        self._profile_data = {
            "psychology": {"cluster_type": cluster_type, "social_role": "Regular User"},
            "persona": ("You are a 32-year-old urban professional who buys oat milk occasionally. "
                        "You care about sustainability but price matters too."),
        }
        self.profile_data = self._profile_data

    def get_prompt(self):
        return self._profile_data.get("persona", "You are a consumer.")


class FakeComponent:
    def __init__(self, plugin):
        self._plugin = plugin
        self.plugin = plugin
        plugin.component = self


class FakeAgent:
    def __init__(self, agent_id, model, state_plugin, profile_plugin, invoke_plugin=None):
        self.agent_id = agent_id
        self._model = model
        self.model = model
        self._components = {
            "state": FakeComponent(state_plugin),
            "profile": FakeComponent(profile_plugin),
        }
        if invoke_plugin:
            self._components["invoke"] = FakeComponent(invoke_plugin)

    def get_component(self, name):
        return self._components.get(name)


class DeterministicRouter:
    """按 Prompt 中的稳定标记返回固定 JSON。无随机、无网络、不调用真实 LLM。"""

    def __init__(self):
        self.call_count = 0

    async def chat(self, prompt):
        self.call_count += 1
        is_reflect = ("Immediate Gut Reaction" in prompt) and ("trust_change_affective" in prompt)
        if is_reflect:
            if "[Brand Statement]" in prompt:
                return json.dumps({"hypocrisy_perceived": False,
                                   "trust_change_affective": 0.8,
                                   "importance": 6.0,
                                   "reasoning": "The statement gives me some reassurance."})
            if "POSITIVE_SIGNAL" in prompt:
                return json.dumps({"hypocrisy_perceived": False,
                                   "trust_change_affective": 1.0,
                                   "importance": 4.0,
                                   "reasoning": "A friend says the brand is improving."})
            return json.dumps({"hypocrisy_perceived": True,
                               "trust_change_affective": -1.2,
                               "importance": 7.5,
                               "reasoning": "I feel disappointed by this corporate hypocrisy."})
        return json.dumps({"is_buying": False, "is_posting": False,
                           "post_content": "",
                           "reason": "Trust too low, staying quiet today."})


class CountingInnerRouter:
    """S10 / S10.1 专用：统计"真实 Router 是否被调用过"。

    fail-closed 的核心断言是"窗口内 miss 时**没有**落穿到真实 Router"，
    因此必须有一个能证明调用次数为 0 的替身，而不是仅看返回值。
    """

    def __init__(self, response="REAL_ROUTER_RESPONSE"):
        self.calls = 0
        self.prompts = []
        self._response = response

    async def chat(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        return self._response


def _wire_plugin(plugin, agent):
    comp = FakeComponent(plugin)
    comp.agent = agent
    comp._agent = agent
    plugin.component = comp
    plugin.agent = agent


# ══════════════════════════════════════════════════════════════════════
# 行为场景（字面常量；不引用 CONTENT_TEMPLATES，保证 pre/post 同输入）
#
# 三个场景的时点与矩阵 v3.0 一致：
#   immediate      → 澄清在 Tick 6  （scandal_tick 5 + 1）
#   delayed        → 澄清在 Tick 10 （scandal_tick 5 + 5）
#   common_control → 全程无澄清
# 场景名 "common_control" 用下划线：它是**测试内部的场景键**，不是任何因子取值，
# 与 §6.1 禁止的下划线哨兵写法无关。
# ══════════════════════════════════════════════════════════════════════

SCANDAL_NEWS = ("BREAKING: Oatly sold a 10% stake to Blackstone Group. "
                "Activists trending #BoycottOatly.")

CLARIFICATION_MSG = {
    "source": "Enterprise_Clarification",
    "content": ("Official Statement: We acknowledge concerns about our Blackstone partnership. "
                "We have established an independent sustainability board with veto power over "
                "all future investments. Full audit results will be published quarterly."),
    "type": "clarification",
}

POSITIVE_SOCIAL_MSG = {
    "source": "Social",
    "content": "[Social Media Feed] Connection Consumer_002 posted: POSITIVE_SIGNAL the audit looks real.",
    "type": "social_review",
}

CLARIFICATION_HEADLINE = ("[Enterprise Clarification] The brand has issued an official statement "
                          "addressing the controversy.")


def _scenario_immediate():
    """澄清在 Tick 6 = EXPECTED_IMMEDIATE_TICK。"""
    return [
        {"tick": 5, "observations": [{"source": "Global News", "content": SCANDAL_NEWS}],
         "current_news": SCANDAL_NEWS},
        {"tick": EXPECTED_IMMEDIATE_TICK, "observations": [copy.deepcopy(CLARIFICATION_MSG)],
         "current_news": CLARIFICATION_HEADLINE},
        {"tick": 7, "observations": [], "current_news": ""},
        {"tick": 8, "observations": [], "current_news": ""},
        {"tick": 9, "observations": [], "current_news": ""},
        {"tick": EXPECTED_DELAYED_TICK, "observations": [copy.deepcopy(POSITIVE_SOCIAL_MSG)],
         "current_news": ""},
        {"tick": 11, "observations": [], "current_news": ""},
        {"tick": 12, "observations": [], "current_news": ""},
    ]


def _scenario_delayed():
    """澄清在 Tick 10 = EXPECTED_DELAYED_TICK（丑闻后 5 个 Tick）。"""
    return [
        {"tick": 5, "observations": [{"source": "Global News", "content": SCANDAL_NEWS}],
         "current_news": SCANDAL_NEWS},
        {"tick": 6, "observations": [], "current_news": ""},
        {"tick": 7, "observations": [], "current_news": ""},
        {"tick": 8, "observations": [], "current_news": ""},
        {"tick": 9, "observations": [], "current_news": ""},
        {"tick": EXPECTED_DELAYED_TICK, "observations": [copy.deepcopy(CLARIFICATION_MSG)],
         "current_news": CLARIFICATION_HEADLINE},
        {"tick": 11, "observations": [], "current_news": ""},
        {"tick": 12, "observations": [], "current_news": ""},
        {"tick": 13, "observations": [], "current_news": ""},
    ]


def _scenario_common_control():
    """全程无澄清（唯一共同对照对应的行为场景）。"""
    ticks = [{"tick": 5, "observations": [{"source": "Global News", "content": SCANDAL_NEWS}],
              "current_news": SCANDAL_NEWS}]
    ticks += [{"tick": t, "observations": [], "current_news": ""} for t in range(6, 14)]
    return ticks


SCENARIOS = {
    "immediate": _scenario_immediate,
    "delayed": _scenario_delayed,
    "common_control": _scenario_common_control,
}


# ══════════════════════════════════════════════════════════════════════
# 行为轨迹采集（pre / post 共用同一函数，保证同输入）
# ══════════════════════════════════════════════════════════════════════

async def run_behavior_scenario(scenario_name, cluster_type):
    random_module.seed(FIXTURE_SEED)
    np.random.seed(FIXTURE_SEED)

    router = DeterministicRouter()
    state_plugin = FakeStatePlugin()
    profile_plugin = FakeProfilePlugin(cluster_type)
    reflect_plugin = GreenCognitionPlugin()
    plan_plugin = ConsumerPlanPlugin()
    invoke_plugin = GreenInvokePlugin()

    agent = FakeAgent("Test_Agent_001", router, state_plugin, profile_plugin, invoke_plugin)
    for p in (reflect_plugin, plan_plugin, invoke_plugin):
        _wire_plugin(p, agent)

    init_trust = INITIAL_TRUST_MAP[cluster_type]
    await state_plugin.set_state("trust_score", init_trust)
    await state_plugin.set_state("baseline_trust", init_trust)
    await state_plugin.set_state("shock_anchor", init_trust)
    await state_plugin.set_state("quiet_ticks", 0)
    await state_plugin.set_state("incoming_messages", [])
    await state_plugin.set_state("observations", [])
    await state_plugin.set_state("last_observations", [])
    await state_plugin.set_state("latest_thought", None)
    await state_plugin.set_state("trust_change_affective", 0.0)
    await state_plugin.set_state("raw_affective_output", 0.0)
    await state_plugin.set_state("affective_was_clipped", False)
    await state_plugin.set_state("current_news", "")

    ticks_out = []
    for tc in SCENARIOS[scenario_name]():
        await state_plugin.set_state("observations", list(tc["observations"]))
        await state_plugin.set_state("current_news", tc["current_news"])
        await state_plugin.set_state("current_tick", tc["tick"])

        await reflect_plugin.execute(tc["tick"])
        await plan_plugin.execute(tc["tick"])
        try:
            await invoke_plugin.execute(tc["tick"])
        except Exception:
            pass

        sd = state_plugin._state_data
        plan = sd.get("plan_result", {}) or {}
        # 与 S15 同一组量：运行期未舍入内存状态，不经 CSV、不依赖任何小数位约定。
        ticks_out.append({
            "tick": tc["tick"],
            "trust_score_raw": plan.get("trust_score_raw"),
            "shock_anchor_after_raw": plan.get("shock_anchor_after_raw"),
            "quiet_ticks": plan.get("quiet_ticks"),
            "is_buying": bool(plan.get("is_buying", False)),
            "is_posting": bool(plan.get("is_posting", False)),
        })

    return {"scenario": scenario_name, "cluster_type": cluster_type,
            "initial_trust": init_trust, "ticks": ticks_out}


async def collect_behavior_trace():
    scenarios = []
    for scenario_name in ("immediate", "delayed", "common_control"):
        for cluster_type in CLUSTER_TYPES:
            scenarios.append(await run_behavior_scenario(scenario_name, cluster_type))
    return scenarios


def compare_traces(fixture, current_scenarios):
    """返回差异列表；空列表 = 行为完全一致（精确相等，无容差）。"""
    diffs = []
    fmap = {(s["scenario"], s["cluster_type"]): s for s in fixture.get("scenarios", [])}
    cmap = {(s["scenario"], s["cluster_type"]): s for s in current_scenarios}

    for key in sorted(set(fmap) - set(cmap)):
        diffs.append({"scenario": key[0], "cluster_type": key[1], "tick": "",
                      "field": "<scenario>", "baseline": "present", "current": "missing"})
    for key in sorted(set(cmap) - set(fmap)):
        diffs.append({"scenario": key[0], "cluster_type": key[1], "tick": "",
                      "field": "<scenario>", "baseline": "missing", "current": "present"})

    for key in sorted(set(fmap) & set(cmap)):
        fticks = {t["tick"]: t for t in fmap[key]["ticks"]}
        cticks = {t["tick"]: t for t in cmap[key]["ticks"]}
        for tick in sorted(set(fticks) | set(cticks)):
            if tick not in fticks or tick not in cticks:
                diffs.append({"scenario": key[0], "cluster_type": key[1], "tick": tick,
                              "field": "<tick>",
                              "baseline": "present" if tick in fticks else "missing",
                              "current": "present" if tick in cticks else "missing"})
                continue
            for field in COMPARED_FIELDS:
                b = fticks[tick].get(field)
                c = cticks[tick].get(field)
                if b != c:                      # 精确相等，无容差
                    diffs.append({"scenario": key[0], "cluster_type": key[1], "tick": tick,
                                  "field": field, "baseline": repr(b), "current": repr(c)})
    return diffs


# ══════════════════════════════════════════════════════════════════════
# 哈希 / git / 溯源（复用 TASK_002 已验证有效的四道机制，design §12.1）
# ══════════════════════════════════════════════════════════════════════

def _sha256_file(path):
    if not os.path.isfile(path):
        return "missing:" + os.path.basename(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(args, cwd):
    """执行 git 子命令。返回 (returncode, stdout, stderr)；无法执行时 returncode = -1。

    使用 argv 列表（不经过 shell），路径以独立参数传入，避免任何命令注入。
    """
    try:
        proc = subprocess.run(["git"] + list(args), cwd=cwd,
                              capture_output=True, text=True, timeout=30)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return -1, "", "git executable not found"
    except Exception as e:
        return -1, "", "%s: %s" % (type(e).__name__, e)


def collect_dirty_production_entries(root):
    """生产路径洁净性检查，**三项分别独立执行**（裁定七）：

        1. unstaged production diff   → git diff --name-only -- <paths>
        2. staged production diff     → git diff --cached --name-only -- <paths>
        3. production 未跟踪文件       → git ls-files --others --exclude-standard -- <paths>

    只覆盖生产路径。tests / docs / .kiro / results 仍排除：生成 fixture 时
    **本测试文件尚未提交**（第 5 步才与 fixture 一起提交），纳入检查会形成
    流程死锁；**design.md 已经提交**（第 1 步），排除 .kiro/ 与其提交状态无关。

    返回值：
        (status, entries)
        status = "clean"        → entries == []
        status = "dirty"        → entries 为带类别前缀的条目列表
        status = "undetermined" → 无法判定（无 git / 非仓库 / 命令失败），entries 为原因
    """
    code, out, err = _git(["rev-parse", "--is-inside-work-tree"], root)
    if code != 0 or out != "true":
        return "undetermined", ["cannot verify git work tree: %s" % (err or out or code)]

    probes = (
        ("unstaged", ["diff", "--name-only", "--"] + PRODUCTION_PATHS),
        ("staged", ["diff", "--cached", "--name-only", "--"] + PRODUCTION_PATHS),
        ("untracked", ["ls-files", "--others", "--exclude-standard", "--"]
         + PRODUCTION_PATHS),
    )
    entries = []
    for label, args in probes:
        code, out, err = _git(args, root)
        if code != 0:
            return "undetermined", ["git %s failed: %s" % (args[0], err or code)]
        for line in out.splitlines():
            if line.strip():
                entries.append("%-9s %s" % (label + ":", line.strip()))
    return ("dirty" if entries else "clean"), entries


def assert_clean_production_tree(root):
    """生产树不洁净或不可判定时打印明确错误并以非零码退出（design §12.1 第 3 步）。

    fail-closed：无法判定也拒绝生成——"不知道代码状态"与"代码状态错误"
    对 fixture 的可信度而言后果相同。
    """
    status, entries = collect_dirty_production_entries(root)
    if status == "clean":
        return
    print("=" * 66)
    print("ERROR: refusing to generate fixture.")
    if status == "dirty":
        print("Production paths are not clean (%d entr%s across "
              "unstaged / staged / untracked):"
              % (len(entries), "y" if len(entries) == 1 else "ies"))
        for line in entries:
            print("  " + line)
        print("")
        print("The pre-TASK_003 baseline must be a reproducible snapshot of a committed")
        print("code state. Commit or stash the changes above, then re-run:")
        print("  python tests/test_task003_experiment_matrix.py --generate-fixture")
    else:
        print("Cannot determine whether production files are clean:")
        for line in entries:
            print("  " + line)
        print("")
        print("Refusing to proceed (fail-closed): an unverifiable code state makes the")
        print("behavior baseline unusable as evidence.")
    print("Checked paths: " + ", ".join(PRODUCTION_PATHS))
    print("=" * 66)
    sys.exit(2)


def _quiet_diff(args, root):
    """`git diff --quiet …` 的三态封装。

    git 的退出码约定：0 = 无差异，1 = 有差异，其他 = 命令本身失败。
    返回 "clean" / "dirty" / "undetermined"（后者同样按失败处理，fail-closed）。
    """
    code, out, err = _git(args, root)
    if code == 0:
        return "clean", ""
    if code == 1:
        return "dirty", "differences present"
    return "undetermined", (err or out or ("exit code %s" % code))


def assert_pre_task003_generation_state(root):
    """生成 fixture 之前的**代码状态**锚定检查（R-29），七项全部必须成立。

    与 assert_clean_production_tree() 的分工：
        后者只看**工作树**（unstaged / staged / untracked）；
        本函数额外比较 HEAD 与基线 commit 的**树内容**——这是前者无法覆盖的
        漏洞：把 TASK_003 的生产改动提交掉之后，工作树是干净的，
        fixture 会被当成 pre 状态记录下来，pre/post 比较从此永远通过。

    任一项不成立即打印明确原因并 sys.exit(2)。
    """
    problems = []

    # ── 1. fixture 尚不存在：禁止覆盖 ──
    # 覆盖一份已冻结的基线是不可逆的证据破坏，因此这一条排在最前面。
    if os.path.exists(FIXTURE_PATH):
        problems.append(
            "fixture already exists: %s\n"
            "      Refusing to overwrite a frozen baseline. Overwriting it would\n"
            "      silently rebase the behavior baseline onto the current code state.\n"
            "      Delete it deliberately (and record why) if regeneration is truly intended."
            % os.path.relpath(FIXTURE_PATH, root))

    # ── 2. design.md 已被 Git 跟踪（§12.1 第 1 步已完成）──
    code, _, err = _git(["ls-files", "--error-unmatch", "--", DESIGN_DOC_REL], root)
    if code != 0:
        problems.append("design.md is not tracked by Git: %s (%s)"
                        % (DESIGN_DOC_REL, err or code))
    else:
        # ── 3. design.md 无 unstaged 变更 ──
        status, detail = _quiet_diff(["diff", "--quiet", "--", DESIGN_DOC_REL], root)
        if status != "clean":
            problems.append("design.md has unstaged changes (%s); commit them first "
                            "so the fixture corresponds to a settled design" % detail)
        # ── 4. design.md 无 staged 变更 ──
        status, detail = _quiet_diff(
            ["diff", "--cached", "--quiet", "--", DESIGN_DOC_REL], root)
        if status != "clean":
            problems.append("design.md has staged (but uncommitted) changes (%s)" % detail)

    # ── 5. 基线 commit 存在，且是当前 HEAD 的祖先 ──
    status, detail = check_fixture_commit_ancestry(root, PRE_TASK003_BASE_COMMIT)
    if status != "ancestor":
        problems.append("PRE_TASK003_BASE_COMMIT is not an ancestor of HEAD (%s): %s"
                        % (status, detail))
    else:
        # ── 6. HEAD 与基线在 PRODUCTION_PATHS 上的树内容完全一致 ──
        #    语义：无净文件差异。改了又改回来同样通过——这正是所需语义，
        #    pre-TASK_003 的要求是最终树内容相同，中间过程无关。
        status, detail = _quiet_diff(
            ["diff", "--quiet", "%s..HEAD" % PRE_TASK003_BASE_COMMIT, "--"]
            + PRODUCTION_PATHS, root)
        if status != "clean":
            code, changed, _ = _git(
                ["diff", "--name-only", "%s..HEAD" % PRE_TASK003_BASE_COMMIT, "--"]
                + PRODUCTION_PATHS, root)
            listed = ", ".join(changed.split()) if code == 0 and changed else detail
            problems.append(
                "HEAD and PRE_TASK003_BASE_COMMIT do NOT have identical tree content\n"
                "      on PRODUCTION_PATHS — net file differences exist in: %s\n"
                "      (compared %s..HEAD)\n"
                "      A clean work tree is NOT sufficient: committing the TASK_003\n"
                "      production diff would leave the tree clean while the code is\n"
                "      already post-TASK_003. The baseline would then be worthless."
                % (listed, PRE_TASK003_BASE_COMMIT[:12]))

    if not problems:
        return
    print("=" * 66)
    print("ERROR: refusing to generate fixture — pre-TASK_003 state not established.")
    for p in problems:
        print("  · " + p)
    print("")
    print("Expected state at this point in the flow (design §12.6.1.1):")
    print("  1. design.md                     committed        (step 1)")
    print("  2. this test file                NOT yet committed (step 5)")
    print("  3. the fixture                   does NOT exist yet")
    print("  4. the 5 production files        no staged / unstaged / untracked change")
    print("  5. HEAD vs PRE_TASK003_BASE_COMMIT")
    print("                                   identical tree content on PRODUCTION_PATHS")
    print("                                   (no net file differences)")
    print("=" * 66)
    sys.exit(2)


def read_git_provenance(root):
    """fixture 溯源信息：commit / branch / 仓库范围 is_dirty。

    git_is_dirty 的范围是**整个仓库**（含 tests/、.kiro/ 等非生产路径），仅作记录；
    生产路径的洁净性由 assert_clean_production_tree() 强制，二者不是同一件事。
    """
    code_c, commit, _ = _git(["rev-parse", "HEAD"], root)
    code_b, branch, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    code_s, status_out, _ = _git(["status", "--porcelain", "--untracked-files=all"], root)
    return {
        "generated_from_commit": commit if code_c == 0 and commit else "unknown",
        "git_branch": branch if code_b == 0 and branch else "unknown",
        # True / False = 已判定；"unknown" = 无法判定（绝不静默记为 False）
        "git_is_dirty": (bool([ln for ln in status_out.splitlines() if ln.strip()])
                         if code_s == 0 else "unknown"),
    }


def assert_provenance_determined(provenance):
    """溯源信息不可判定时拒绝生成（退出码 2）。

    要求：
      · generated_from_commit 为 40 位 hex（祖先关系检查需要它）
      · git_branch 非空且非 "unknown"
      · git_is_dirty 为 bool —— "unknown" 不得进入 fixture
        （True 是允许的：**本测试文件按流程尚未提交**，fixture 也尚不存在，
          因此仓库级 dirty 是预期状态。design.md 此时已经提交。）
    """
    problems = []
    commit = provenance.get("generated_from_commit", "")
    if not (isinstance(commit, str) and len(commit) == 40
            and all(c in "0123456789abcdef" for c in commit.lower())):
        problems.append("generated_from_commit is not a 40-hex sha: %r" % (commit,))
    branch = provenance.get("git_branch", "")
    if not isinstance(branch, str) or branch in ("", "unknown"):
        problems.append("git_branch undetermined: %r" % (branch,))
    dirty = provenance.get("git_is_dirty", "unknown")
    if not isinstance(dirty, bool):
        problems.append("git_is_dirty is not a bool (got %r); a fixture whose git "
                        "state cannot be determined is not usable as evidence" % (dirty,))
    if not problems:
        return
    print("=" * 66)
    print("ERROR: refusing to generate fixture — provenance is undetermined.")
    for p in problems:
        print("  " + p)
    print("")
    print("Note: git_is_dirty == True is FINE and expected. At this point in the")
    print("flow design.md is already committed (step 1), while this test file is")
    print("not yet committed (step 5) and the fixture does not exist yet, so the")
    print("repository is legitimately dirty. Only 'unknown' is rejected.")
    print("Production-path cleanliness is enforced separately by")
    print("assert_clean_production_tree().")
    print("=" * 66)
    sys.exit(2)


def check_fixture_commit_ancestry(root, fixture_commit):
    """fixture 的 commit 是否为当前 HEAD 的祖先（或就是 HEAD）。

    git merge-base --is-ancestor <A> <B> 的退出码约定：
        0 → A 是 B 的祖先（A == B 时也返回 0，符合"或等于 HEAD"的要求）
        1 → A 不是 B 的祖先
        其他 → 命令本身失败（如 commit 不存在于本地仓库）

    Returns:
        (status, detail)；status ∈ {"ancestor", "not_ancestor", "undetermined"}
        undetermined 同样判 FAIL（fail-closed）。
    """
    if not (isinstance(fixture_commit, str) and len(fixture_commit) == 40):
        return "undetermined", "fixture commit is not a 40-hex sha: %r" % (fixture_commit,)

    code_h, head, err_h = _git(["rev-parse", "HEAD"], root)
    if code_h != 0 or not head:
        return "undetermined", "cannot resolve HEAD: %s" % (err_h or code_h)

    code_e, _, err_e = _git(["cat-file", "-e", fixture_commit + "^{commit}"], root)
    if code_e != 0:
        return "undetermined", ("fixture commit not found in this repository: %s "
                                "(%s)" % (fixture_commit, err_e or code_e))

    code, _, err = _git(["merge-base", "--is-ancestor", fixture_commit, "HEAD"], root)
    if code == 0:
        return "ancestor", ("fixture commit %s is an ancestor of (or equal to) HEAD %s"
                            % (fixture_commit[:12], head[:12]))
    if code == 1:
        return "not_ancestor", (
            "fixture commit %s is NOT an ancestor of HEAD %s — the baseline and the "
            "current code are on different history lines (branch switch / rebase / "
            "reset). The pre/post comparison is therefore not 'same input, same code "
            "history + TASK_003 diff'; the baseline is unusable."
            % (fixture_commit[:12], head[:12]))
    return "undetermined", "git merge-base failed: %s" % (err or code)


def harness_sha256():
    """本测试文件自身的 SHA-256（design §12.1 第 6 步"冻结"的技术实现）。

    测试文件定义了 fixture 的全部输入（DeterministicRouter 返回值、场景字面常量、
    Tick 序列、COMPARED_FIELDS），因此它本身就是输入的一部分，必须与 fixture 一起锁定。
    """
    return _sha256_file(os.path.abspath(__file__))


def _write_fixture_exclusively(fixture):
    """两阶段落盘：同目录临时文件写完整 JSON → 以**排他方式**建立最终文件。

    为什么不用 open(path, "w")：`"w"` 会截断已存在的文件。生成前的 exists 检查
    （assert_pre_task003_generation_state 第 1 项）与最终落盘之间存在时间窗，
    而被覆盖的是一份**已冻结的基线**——不可逆的证据破坏。`"x"` 把「不存在」
    从一个先验假设变成写入操作本身的原子前提。

    临时文件的作用：完整 JSON 先在同目录（保证同一文件系统）落成并回读校验，
    最终文件只做一次一次性写入。异常不会留下半写的 fixture。
    """
    payload = json.dumps(fixture, indent=2, ensure_ascii=False)

    tmp_path = None
    created_final = False          # 本次是否真的创建了最终文件（决定异常时要不要删）

    def _drop_tmp():
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def _drop_partial_final():
        """只删除**本次新建**的最终文件。绝不碰早已存在的 fixture。

        返回 True  = 无需删除，或删除成功（磁盘上确定没有半成品）
        返回 False = 删除失败（半成品**可能仍然存在**）
        调用方必须据此给出真实的结论，不得无条件宣布「没有残留」。
        """
        if not (created_final and os.path.exists(FIXTURE_PATH)):
            return True
        try:
            os.remove(FIXTURE_PATH)
            print("Removed the partially written fixture: "
                  + os.path.relpath(FIXTURE_PATH, project_root))
            return True
        except OSError as e:
            print("WARNING: could not remove partially written fixture %s: %s"
                  % (FIXTURE_PATH, e))
            return False

    try:
        # ── 阶段 1：同目录临时文件写完整 JSON 并回读校验 ──
        fd, tmp_path = tempfile.mkstemp(dir=FIXTURE_DIR, prefix=".pre_task003_",
                                        suffix=".json.tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as tf:
            tf.write(payload)
            tf.flush()
            os.fsync(tf.fileno())
        with open(tmp_path, encoding="utf-8") as tf:
            json.load(tf)

        # ── 阶段 2：排他创建最终文件 ──
        try:
            f = open(FIXTURE_PATH, "x", encoding="utf-8")
        except FileExistsError:
            print("=" * 66)
            print("ERROR: refusing to overwrite an existing fixture.")
            print("  " + os.path.relpath(FIXTURE_PATH, project_root))
            print("")
            print("The fixture is a FROZEN baseline. Overwriting it would silently")
            print("rebase the behavior baseline onto the current code state and")
            print("destroy the only evidence that TASK_003 preserved behavior.")
            print("The existing file has NOT been modified.")
            print("")
            print("If regeneration is genuinely intended, delete it deliberately")
            print("and record why in docs/decisions/model_change_log.md first.")
            print("=" * 66)
            _drop_tmp()
            sys.exit(2)

        # 创建成功：从这一刻起，任何异常都必须删除这个新建的文件，
        # 否则会留下一个半写的 JSON 冒充基线。
        created_final = True
        with f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        # ── 阶段 3：回读校验最终文件 ──
        with open(FIXTURE_PATH, encoding="utf-8") as rf:
            json.load(rf)

    except SystemExit:
        raise
    except BaseException as e:
        # 任何其它异常（含 KeyboardInterrupt / 磁盘写满 / JSON 校验失败）：
        # 删除本次新建的最终文件与临时文件，再以退出码 2 结束。
        print("=" * 66)
        print("ERROR: fixture write failed — %s: %s" % (type(e).__name__, e))
        cleaned = _drop_partial_final()
        _drop_tmp()
        if cleaned:
            print("No partial fixture has been left behind.")
        else:
            print("CRITICAL: the partially written fixture may still exist at:")
            print("  " + FIXTURE_PATH)
            print("Remove it manually before any later fixture-generation attempt.")
        print("=" * 66)
        sys.exit(2)

    # ── 成功：只在这里删除临时文件 ──
    _drop_tmp()


async def generate_fixture():
    """生成 pre-TASK_003 行为基线 fixture（design §12.1 第 3–4 步）。

    必须在应用任何 TASK_003 生产 diff **之前**运行。此刻的正确仓库状态
    （design §12.6.1.1，四条同时成立）：
        1. design.md                            已提交（第 1 步）
        2. tests/test_task003_experiment_matrix.py  尚未提交（第 5 步才提交）
        3. tests/fixtures/task003/pre_task003_behavior_trace.json  尚不存在
        4. 5 个生产文件  无 staged / unstaged / untracked 变更
    第 2、3 条正是仓库级 git_is_dirty == True 的来源，属预期而非异常。
    """
    # ── 前置检查一：生产路径三项独立检查（unstaged / staged / untracked）──
    #    任一非空或不可判定 → sys.exit(2)
    assert_clean_production_tree(project_root)
    # ── 前置检查二（R-29）：代码状态锚定 —— fixture 不存在、design.md 已提交、
    #    且 HEAD 与 PRE_TASK003_BASE_COMMIT 在生产路径上的树内容完全一致、
    #    不存在净文件差异 ──
    #    必须在 collect_behavior_trace() 之前执行：一旦开始采集就已经太晚了。
    assert_pre_task003_generation_state(project_root)
    provenance = read_git_provenance(project_root)
    # ── 前置检查三：commit / branch / git_is_dirty 必须可判定，后者必须是 bool ──
    assert_provenance_determined(provenance)

    os.makedirs(FIXTURE_DIR, exist_ok=True)
    scenarios = await collect_behavior_trace()
    fixture = {
        "fixture_version": FIXTURE_VERSION,
        "purpose": ("pre-TASK_003 behavior baseline "
                    "(trust_score_raw / shock_anchor_after_raw / quiet_ticks / "
                    "is_buying / is_posting per tick)"),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "code_state": "pre-TASK_003 (TASK_001 + TASK_002 applied; matrix still v1/12-condition)",
        "router": "DeterministicRouter/v1",
        "seed": FIXTURE_SEED,
        "compare_tolerance": 0.0,
        # 比对对象是运行期未舍入内存状态，不经 CSV，不依赖任何小数位约定
        "compare_source": "runtime_state_unrounded",
        "compared_fields": list(COMPARED_FIELDS),
        # 输入定义指纹：验证时必须完全相同，否则 fixture 无意义
        "test_harness_sha256": harness_sha256(),
        # 溯源四项（git_is_dirty 此处必为 bool，已由前置检查保证）
        "generated_from_commit": provenance["generated_from_commit"],
        "git_branch": provenance["git_branch"],
        "git_is_dirty": provenance["git_is_dirty"],
        "production_paths_checked": list(PRODUCTION_PATHS),
        # R-29：生产代码基线锚点 + 守卫版本。S18 会逐项校验这两个字段。
        "production_baseline_commit": PRE_TASK003_BASE_COMMIT,
        "fixture_generation_guard_version": FIXTURE_GENERATION_GUARD_VERSION,
        # 直接决定行为轨迹的三个插件（TASK_003 一律不改）
        "baseline_file_sha256": {
            rel: _sha256_file(os.path.join(project_root, *rel.split("/")))
            for rel in BASELINE_HASHED_FILES
        },
        # TASK_003 将要修改的 5 个生产文件的改动前哈希（仅供溯源，不作行为断言）
        "pretask003_file_sha256": {
            rel: _sha256_file(os.path.join(project_root, *rel.split("/")))
            for rel in PRETASK003_HASHED_FILES
        },
        # 永久冻结的 TASK_002 验收工具哈希：S18 第 ④ 项据此证明"冻结生效"
        "frozen_task002_sha256": {
            rel: _sha256_file(os.path.join(project_root, *rel.split("/")))
            for rel in (TASK002_TEST_REL, TASK002_FIXTURE_REL)
        },
        "scenarios": scenarios,
    }
    _write_fixture_exclusively(fixture)
    total_ticks = sum(len(s["ticks"]) for s in scenarios)
    print("Fixture written : " + FIXTURE_PATH)
    print("From commit     : %s (%s)" % (provenance["generated_from_commit"],
                                         provenance["git_branch"]))
    print("Prod baseline   : %s   (identical tree content on PRODUCTION_PATHS at HEAD)"
          % PRE_TASK003_BASE_COMMIT[:12])
    print("Guard version   : %s" % FIXTURE_GENERATION_GUARD_VERSION)
    print("Repo is_dirty   : %s   (bool; production tree verified clean)"
          % provenance["git_is_dirty"])
    print("Harness sha256  : %s   (do NOT modify this test file from now on)"
          % fixture["test_harness_sha256"][:16])
    print("Scenarios       : %d" % len(scenarios))
    print("Tick snapshots  : %d" % total_ticks)
    print("Compare points  : %d" % (total_ticks * len(COMPARED_FIELDS)))
    return fixture


# ══════════════════════════════════════════════════════════════════════
# 通用工具：导入、源码读取、AST 分析
# ══════════════════════════════════════════════════════════════════════

def _is_hex64(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _is_hex40(value):
    return (isinstance(value, str) and len(value) == 40
            and all(c in "0123456789abcdef" for c in value.lower()))


def _try_import(module_name, v):
    try:
        return __import__(module_name)
    except Exception as e:
        v.error("T0-import", "导入 " + module_name,
                "%s: %s" % (type(e).__name__, e))
        return None


def _abs(rel):
    return os.path.join(project_root, *rel.replace("\\", "/").split("/"))


def _read_source(rel):
    """读取源文件文本；不存在时返回 None。"""
    path = _abs(rel)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse(rel):
    """解析源文件为 AST；不可读或语法错误时返回 None。"""
    src = _read_source(rel)
    if src is None:
        return None
    try:
        return ast.parse(src)
    except SyntaxError:
        return None


def _str_literals_in(node):
    """节点子树中的全部字符串字面量（精确值，不做子串匹配）。"""
    return {n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _module_constant_literals(rel, names):
    """返回 {常量名: 该常量表达式中出现的全部字符串字面量集合}。

    只取模块顶层赋值。名称含 LEGACY_CONTEXT_MARKER 的常量一律跳过——
    旧标签住在 LEGACY_* 常量里是**预期**，不是缺陷。
    """
    tree = _parse(rel)
    if tree is None:
        return None
    out = {}
    wanted = set(names)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in wanted:
                continue
            if LEGACY_CONTEXT_MARKER in target.id.lower():
                continue
            out.setdefault(target.id, set()).update(_str_literals_in(node.value))
    return out


def _enclosing_def_names(tree):
    """返回 {AST 节点 id: 所在最内层 def 名称}，用于判定 legacy 语境。"""
    owner = {}

    def _walk(node, current):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _walk(child, child.name)
            else:
                owner[id(child)] = current
                _walk(child, current)

    _walk(tree, "<module>")
    return owner


def _timing_keyed_dicts(rel):
    """收集以时机水平为键的 dict 字面量（含函数体内的时点映射）。

    返回 [(所在 def 名称, 行号, 键集合)]。这就是裁定一第 5 项所指的
    "当前图例 / 当前分组 / 当前时点映射"的可机器判定形态。
    """
    tree = _parse(rel)
    if tree is None:
        return None
    owner = _enclosing_def_names(tree)
    probe = set(EXPECTED_STRATEGY_TIMING_LEVELS) | {EXPECTED_CONTROL_TIMING} \
        | set(LEGACY_TIMING_LABELS)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if not (keys & probe):
            continue
        found.append((owner.get(id(node), "<module>"), getattr(node, "lineno", 0), keys))
    return found


def _exact_literal_sites(rel, literal):
    """返回出现精确字符串字面量 literal 的 (所在 def 名称, 行号) 列表。

    精确相等匹配：`"not_applicable_value"` 与 `"not_applicable"` 是两个不同的
    字面量，前者不会被匹配；标识符 `NOT_APPLICABLE` 不是字面量，同样不会被匹配。
    """
    tree = _parse(rel)
    if tree is None:
        return None
    owner = _enclosing_def_names(tree)
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == literal:
            sites.append((owner.get(id(node), "<module>"), getattr(node, "lineno", 0)))
    return sites


def _normalized(src):
    """去掉所有空白，用于匹配 `total_ticks + 1` 这类可能被重排空格的表达式。"""
    return re.sub(r"\s+", "", src or "")


# ══════════════════════════════════════════════════════════════════════
# 矩阵构造辅助（全部 fail-soft：pre-TASK_003 状态下不得让测试崩溃退出）
# ══════════════════════════════════════════════════════════════════════

def _matrix(EC):
    """调用 generate_experiment_matrix()；失败时返回 (None, 原因)。"""
    if EC is None:
        return None, "experiment_config 未能导入"
    try:
        return list(EC.generate_experiment_matrix()), ""
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def _cfg(EC, content, channel, timing, **kw):
    """构造 ExperimentConfig；失败时返回 (None, 异常)。"""
    try:
        return EC.ExperimentConfig(content_factor=content, channel_factor=channel,
                                   timing_factor=timing, **kw), None
    except Exception as e:
        return None, e


def _control_cfg(EC):
    return _cfg(EC, EXPECTED_NOT_APPLICABLE, EXPECTED_NOT_APPLICABLE,
                EXPECTED_CONTROL_TIMING, budget_k=EXPECTED_CONTROL_BUDGET_K)


def _strategy_cfg(EC, content="rational-evidence", channel="hub", timing="immediate"):
    return _cfg(EC, content, channel, timing)


def _is_control(cfg):
    """优先用派生属性；属性不存在时退回字符串比较（仅为让测试能给出判定）。"""
    if hasattr(cfg, "is_control"):
        return bool(cfg.is_control)
    return cfg.timing_factor == EXPECTED_CONTROL_TIMING


# ══════════════════════════════════════════════════════════════════════
# S1 矩阵版本与基数
# ══════════════════════════════════════════════════════════════════════

def check_s1_matrix_size(v, EC):
    group = "S1-matrix-size"
    if EC is None:
        v.error(group, "experiment_config 可用", "模块未能导入")
        return None

    version = getattr(EC, "EXPERIMENT_MATRIX_VERSION", None)
    v.check(group, 'EXPERIMENT_MATRIX_VERSION == "3.0"',
            version == EXPECTED_MATRIX_VERSION,
            EXPECTED_MATRIX_VERSION, repr(version),
            "矩阵版本是 legacy 判定的主判据（design §11.1），必须由生产代码提供")

    matrix, why = _matrix(EC)
    if matrix is None:
        v.error(group, "generate_experiment_matrix() 可调用", why)
        return None

    v.check(group, "generate_experiment_matrix() 长度 == 9",
            len(matrix) == EXPECTED_CONDITION_COUNT,
            EXPECTED_CONDITION_COUNT, len(matrix),
            "8 个策略条件 + 1 个唯一共同对照")
    return matrix


# ══════════════════════════════════════════════════════════════════════
# S2 矩阵结构：唯一对照 + 完整 2×2×2 交叉
# ══════════════════════════════════════════════════════════════════════

def check_s2_matrix_structure(v, EC, matrix):
    group = "S2-matrix-structure"
    if not matrix:
        v.error(group, "矩阵可用", "S1 未能取得矩阵")
        return

    controls = [c for c in matrix if _is_control(c)]
    strategies = [c for c in matrix if not _is_control(c)]

    v.check(group, "is_control 恰 1 条", len(controls) == EXPECTED_CONTROL_COUNT,
            EXPECTED_CONTROL_COUNT, len(controls),
            "唯一共同对照不可被复制（这正是 12 条件矩阵的核心缺陷）")
    v.check(group, "策略条件恰 8 条", len(strategies) == EXPECTED_STRATEGY_COUNT,
            EXPECTED_STRATEGY_COUNT, len(strategies))

    v.check(group, "ExperimentConfig 具备 is_control 派生属性",
            all(hasattr(c, "is_control") for c in matrix),
            "所有配置均有 is_control", "缺失",
            "下游一律用它判断对照，禁止 == \"no-clarification\" 字符串比较（design §3.3）")

    expected_cross = {(c, h, t) for c in EXPECTED_CONTENT_LEVELS
                      for h in EXPECTED_CHANNEL_LEVELS
                      for t in EXPECTED_STRATEGY_TIMING_LEVELS}
    actual_cross = {(c.content_factor, c.channel_factor, c.timing_factor)
                    for c in strategies}
    v.check(group, "8 个策略条件构成完整 2×2×2 交叉",
            actual_cross == expected_cross, sorted(expected_cross), sorted(actual_cross))

    if controls:
        ctl = controls[0]
        v.check(group, "对照 content_factor == \"not-applicable\"",
                ctl.content_factor == EXPECTED_NOT_APPLICABLE,
                EXPECTED_NOT_APPLICABLE, repr(ctl.content_factor))
        v.check(group, "对照 channel_factor == \"not-applicable\"",
                ctl.channel_factor == EXPECTED_NOT_APPLICABLE,
                EXPECTED_NOT_APPLICABLE, repr(ctl.channel_factor))
        v.check(group, "对照 timing_factor == \"no-clarification\"",
                ctl.timing_factor == EXPECTED_CONTROL_TIMING,
                EXPECTED_CONTROL_TIMING, repr(ctl.timing_factor))
        v.check(group, "对照 budget_k == 0（真实的零，不是\"不适用\"）",
                ctl.budget_k == EXPECTED_CONTROL_BUDGET_K,
                EXPECTED_CONTROL_BUDGET_K, ctl.budget_k,
                "design §3.4：对照真的投放了 0 个节点，因此写 0 而非 \"\"")

    for c in strategies:
        v.check(group, "策略条件 budget_k > 0: " + getattr(c, "exp_id", "?"),
                c.budget_k > 0, "> 0", c.budget_k)

    # 全部 9 条件共享同一 seed / 规模 / 丑闻时点：这是澄清前路径可比较的前提（design §7.4a）
    seeds = {c.random_seed for c in matrix}
    sizes = {c.num_agents for c in matrix}
    scandals = {c.scandal_tick for c in matrix}
    v.check(group, "9 条件共享同一 random_seed", len(seeds) == 1, 1, sorted(seeds),
            "seed 决定网络拓扑；一 seed 一 run 目录（design §7.6）")
    v.check(group, "9 条件共享同一 num_agents", len(sizes) == 1, 1, sorted(sizes))
    v.check(group, "9 条件共享同一 scandal_tick", len(scandals) == 1, 1, sorted(scandals))


# ══════════════════════════════════════════════════════════════════════
# S3 exp_id 精确集合 + 对照 id 不携带任何因子词元
# ══════════════════════════════════════════════════════════════════════

def check_s3_exp_ids(v, EC, matrix):
    group = "S3-exp-id"
    if not matrix:
        v.error(group, "矩阵可用", "S1 未能取得矩阵")
        return

    ids = [c.exp_id for c in matrix]
    v.check(group, "9 个 exp_id 集合逐字等于设计 §2 表",
            set(ids) == set(EXPECTED_EXP_IDS),
            sorted(EXPECTED_EXP_IDS), sorted(set(ids)))
    v.check(group, "exp_id 无重复", len(ids) == len(set(ids)), len(ids), len(set(ids)))

    control_id = getattr(EC, "CONTROL_EXP_ID", None)
    v.check(group, 'CONTROL_EXP_ID == "NoClarification-Control"',
            control_id == EXPECTED_CONTROL_EXP_ID,
            EXPECTED_CONTROL_EXP_ID, repr(control_id))

    target = control_id if isinstance(control_id, str) else EXPECTED_CONTROL_EXP_ID
    for token in FORBIDDEN_CONTROL_ID_TOKENS:
        v.check(group, "对照 exp_id 不含词元 %r" % token, token not in target,
                "absent", "present" if token in target else "absent",
                "按词元过滤 exp_id 的脚本不得把共同对照归入某个因子水平（design §5）")

    for suffix in LEGACY_ID_TOKEN_SUFFIXES:
        offenders = sorted(i for i in ids if i.endswith(suffix))
        v.check(group, "无 exp_id 使用已废弃缩写后缀 %r" % suffix, not offenders,
                "none", offenders,
                "新旧 exp_id 集合交集必须为空，否则行级无法区分 legacy 数据")

    v.check(group, "exp_id 不含任何数字字符",
            all(not any(ch.isdigit() for ch in i) for i in ids),
            "no digits", sorted(i for i in ids if any(ch.isdigit() for ch in i)),
            "Tick 数字只住在 clarification_tick 里，绝不进入标识符")


# ══════════════════════════════════════════════════════════════════════
# S4 clarification_tick 精确数值
# ══════════════════════════════════════════════════════════════════════

def check_s4_clarification_tick(v, EC, matrix):
    group = "S4-clarification-tick"
    if not matrix:
        v.error(group, "矩阵可用", "S1 未能取得矩阵")
        return

    by_timing = {}
    for c in matrix:
        by_timing.setdefault(c.timing_factor, set()).add(c.clarification_tick)

    v.check(group, "immediate → clarification_tick == 6（精确数值）",
            by_timing.get("immediate") == {EXPECTED_IMMEDIATE_TICK},
            {EXPECTED_IMMEDIATE_TICK}, by_timing.get("immediate"),
            "即时澄清 = 丑闻后 1 个 Tick")
    v.check(group, "delayed → clarification_tick == 10（精确数值）",
            by_timing.get("delayed") == {EXPECTED_DELAYED_TICK},
            {EXPECTED_DELAYED_TICK}, by_timing.get("delayed"),
            "延迟澄清 = 丑闻后 5 个 Tick，当前配置下 Tick 10")
    v.check(group, "no-clarification → clarification_tick is None",
            by_timing.get(EXPECTED_CONTROL_TIMING) == {None},
            {None}, by_timing.get(EXPECTED_CONTROL_TIMING))

    for name, expected in (("IMMEDIATE_OFFSET_TICKS", EXPECTED_IMMEDIATE_OFFSET),
                           ("DELAYED_OFFSET_TICKS", EXPECTED_DELAYED_OFFSET)):
        actual = getattr(EC, name, None)
        v.check(group, "%s == %d（偏移量常量化）" % (name, expected),
                actual == expected, expected, repr(actual),
                "数字只住在这一个常量里，不出现在任何标签字符串中（design §4）")

    # 自洽性：澄清必须落在丑闻之后、仿真窗口之内
    for c in matrix:
        if c.clarification_tick is None:
            continue
        ok = c.scandal_tick < c.clarification_tick <= c.total_ticks
        v.check(group, "自洽性 scandal < clr <= total: " + c.exp_id, ok,
                "%d < clr <= %d" % (c.scandal_tick, c.total_ticks), c.clarification_tick)


# ══════════════════════════════════════════════════════════════════════
# S5 旧标签只允许存在于 legacy 语境（AST + 符号白名单）
#
# 本项刻意**不做**"全库不存在 delay-3 / delay-5"的断言：legacy 判定逻辑
# 必须认识旧标签才能识别历史数据，把它们一律禁掉会让 §11 的迁移规则无法实现。
# 检查的是"当前生效的口径里没有旧标签"，共 5 个面。
# ══════════════════════════════════════════════════════════════════════

def _legacy_labels_in(literals):
    return sorted(l for l in LEGACY_TIMING_LABELS if l in literals)


def check_s5_label_scope(v, EC, matrix):
    group = "S5-label-scope"

    # ── 面 1：generate_experiment_matrix() 生成的当前配置不含旧标签 ──
    if matrix:
        offenders = sorted({c.timing_factor for c in matrix
                            if c.timing_factor in LEGACY_TIMING_LABELS})
        v.check(group, "面1 当前矩阵配置的 timing_factor 不含旧标签", not offenders,
                "none", offenders,
                "旧标签允许被 legacy 检测认识，但不得再被生成")
        allowed = set(EXPECTED_STRATEGY_TIMING_LEVELS) | {EXPECTED_CONTROL_TIMING}
        actual = {c.timing_factor for c in matrix}
        v.check(group, "面1 当前矩阵 timing_factor 取值 ⊆ {immediate, delayed, no-clarification}",
                actual <= allowed, sorted(allowed), sorted(actual))
    else:
        v.error(group, "面1 当前矩阵可校验", "S1 未能取得矩阵")

    # ── 面 2：STRATEGY_TIMING_LEVELS 不含数字 ──
    levels = getattr(EC, "STRATEGY_TIMING_LEVELS", None) if EC else None
    v.check(group, "面2 STRATEGY_TIMING_LEVELS 存在",
            isinstance(levels, (tuple, list, set, frozenset)),
            "tuple/list", type(levels).__name__ if levels is not None else "None",
            "真实因子水平与字段合法值必须是两个不同常量（design §3.1）")
    if isinstance(levels, (tuple, list, set, frozenset)):
        v.check(group, "面2 STRATEGY_TIMING_LEVELS 取值 == (immediate, delayed)",
                set(levels) == set(EXPECTED_STRATEGY_TIMING_LEVELS),
                set(EXPECTED_STRATEGY_TIMING_LEVELS), set(levels))
        offenders = sorted(l for l in levels if any(ch.isdigit() for ch in str(l)))
        v.check(group, "面2 STRATEGY_TIMING_LEVELS 无数字字符", not offenders,
                "no digits", offenders,
                "延迟长度只能由 clarification_tick 提供，绝不由标签提供")

    # ── 面 3：当前 exp_id 不含 D3 / Delay-3 / Delay-5 ──
    if matrix:
        ids = [c.exp_id for c in matrix]
        for sub in LEGACY_ID_SUBSTRINGS:
            hits = sorted(i for i in ids if sub in i)
            v.check(group, "面3 当前 exp_id 不含子串 %r" % sub, not hits, "none", hits)
    else:
        v.error(group, "面3 当前 exp_id 可校验", "S1 未能取得矩阵")

    # ── 面 4：experiment_config.py 的活跃因子常量不采用旧标签 ──
    consts = _module_constant_literals("experiment_config.py",
                                       ACTIVE_FACTOR_CONSTANTS["experiment_config.py"])
    if consts is None:
        v.error(group, "面4 experiment_config.py 可解析", "文件不可读或语法错误")
    else:
        expected_names = set(ACTIVE_FACTOR_CONSTANTS["experiment_config.py"])
        v.check(group, "面4 活跃因子常量齐备", set(consts) == expected_names,
                sorted(expected_names), sorted(consts),
                "三层词表 + 词元映射必须都以模块级常量存在（design §3.1 / §5）")
        for name in sorted(consts):
            bad = _legacy_labels_in(consts[name])
            v.check(group, "面4 %s 不含旧标签" % name, not bad, "none", bad)

    # ── 面 5：analysis 的当前图例 / 分组 / 时点映射不采用旧标签 ──
    for rel in ("analysis/plot_experiments.py", "analysis/plot_trajectories.py"):
        consts = _module_constant_literals(rel, ACTIVE_FACTOR_CONSTANTS[rel])
        if consts is None:
            v.error(group, "面5 %s 可解析" % rel, "文件不可读或语法错误")
            continue
        v.check(group, "面5 %s 的当前图例常量齐备" % rel,
                set(consts) == set(ACTIVE_FACTOR_CONSTANTS[rel]),
                sorted(ACTIVE_FACTOR_CONSTANTS[rel]), sorted(consts))
        for name in sorted(consts):
            bad = _legacy_labels_in(consts[name])
            v.check(group, "面5 %s.%s 不含旧标签" % (rel, name), not bad, "none", bad,
                    "图例文字错误会直接写进论文（旧代码把 delay-5 标成 Delay-3d）")

    # 当前时点映射：以时机为键的 dict 字面量（含函数体内），legacy 语境豁免
    for rel in TIMING_MAPPING_SCAN_FILES:
        dicts = _timing_keyed_dicts(rel)
        if dicts is None:
            v.error(group, "面5 %s 的时点映射可解析" % rel, "文件不可读或语法错误")
            continue
        offenders = []
        exempt = []
        for owner, lineno, keys in dicts:
            bad = _legacy_labels_in(keys)
            if not bad:
                continue
            if LEGACY_CONTEXT_MARKER in owner.lower():
                exempt.append("%s:%d in %s" % (rel, lineno, owner))
            else:
                offenders.append("%s:%d in %s → %s" % (rel, lineno, owner, bad))
        v.check(group, "面5 %s 的当前时点映射不含旧标签" % rel, not offenders,
                "none", offenders,
                "时点必须从 clarification_tick 推导，不得从标签数字重建"
                + ("；legacy 语境豁免: %s" % exempt if exempt else ""))


# ══════════════════════════════════════════════════════════════════════
# S6 组合级校验反证
# ══════════════════════════════════════════════════════════════════════

def check_s6_invalid_combinations(v, EC):
    group = "S6-validation"
    if EC is None:
        v.error(group, "experiment_config 可用", "模块未能导入")
        return

    # ── 正例：两个合法配置必须能构造成功 ──
    ctl, err = _control_cfg(EC)
    v.check(group, "合法共同对照可构造（not-applicable ×2 + budget_k=0）",
            ctl is not None, "constructed",
            "%s: %s" % (type(err).__name__, err) if err else "ok")
    stg, err = _strategy_cfg(EC)
    v.check(group, "合法策略条件可构造（真实水平 + budget_k>0）",
            stg is not None, "constructed",
            "%s: %s" % (type(err).__name__, err) if err else "ok")

    # ── 反例：每一条都必须抛 ValueError ──
    NA = EXPECTED_NOT_APPLICABLE
    cases = [
        ("对照携带真实 content/channel → 拒绝",
         dict(content="rational-evidence", channel="hub", timing=EXPECTED_CONTROL_TIMING,
              budget_k=EXPECTED_CONTROL_BUDGET_K),
         "正是 §1.2 要消灭的伪因子：对照的 content/channel 无因果意义"),
        ("对照只有一项 not-applicable → 拒绝",
         dict(content=NA, channel="hub", timing=EXPECTED_CONTROL_TIMING,
              budget_k=EXPECTED_CONTROL_BUDGET_K), ""),
        ("策略条件携带 not-applicable content → 拒绝",
         dict(content=NA, channel="hub", timing="immediate"),
         "澄清必须有真实内容与真实渠道"),
        ("策略条件携带 not-applicable channel → 拒绝",
         dict(content="rational-evidence", channel=NA, timing="immediate"), ""),
        ("content_factor 为空串 → 拒绝",
         dict(content="", channel="hub", timing="immediate"),
         "空串与\"字段缺失 / 读取失败\"不可区分"),
        ("content_factor 为 None → 拒绝",
         dict(content=None, channel="hub", timing="immediate"),
         "None 在 CSV 里写成空串，且破坏 str 字段类型"),
        ("channel_factor 为空串 → 拒绝",
         dict(content="rational-evidence", channel="", timing="immediate"), ""),
        ("对照 budget_k=3 → 拒绝",
         dict(content=NA, channel=NA, timing=EXPECTED_CONTROL_TIMING, budget_k=3),
         "不投放却声称预算 3 个节点，是第四个伪参数"),
        ("策略条件 budget_k=0 → 拒绝",
         dict(content="rational-evidence", channel="hub", timing="immediate", budget_k=0), ""),
        ("budget_k 为负 → 拒绝",
         dict(content="rational-evidence", channel="hub", timing="immediate", budget_k=-1), ""),
        ("已废弃 timing 标签 delay-3 → 拒绝",
         dict(content="rational-evidence", channel="hub", timing="delay-3"), ""),
        ("clarification_tick 超出 total_ticks → 拒绝",
         dict(content="rational-evidence", channel="hub", timing="delayed", total_ticks=8),
         "改 scandal_tick 或偏移量导致澄清落在窗口外，必须在构造时报错"),
        ("下划线哨兵写法 → 拒绝",
         dict(content=FORBIDDEN_SENTINEL, channel=FORBIDDEN_SENTINEL,
              timing=EXPECTED_CONTROL_TIMING, budget_k=EXPECTED_CONTROL_BUDGET_K),
         "本设计从未产出下划线写法；它是非法/中间态数据"),
    ]
    for label, kw, note in cases:
        cfg, err = _cfg(EC, kw.pop("content"), kw.pop("channel"), kw.pop("timing"), **kw)
        v.check(group, label, isinstance(err, ValueError),
                "ValueError",
                "no exception" if cfg is not None else type(err).__name__, note)


# ══════════════════════════════════════════════════════════════════════
# S8 哨兵取值（连字符）
# ══════════════════════════════════════════════════════════════════════

def check_s8_sentinel(v, EC):
    group = "S8-sentinel"

    na = getattr(EC, "NOT_APPLICABLE", None) if EC else None
    v.check(group, 'NOT_APPLICABLE == "not-applicable"（连字符）',
            na == EXPECTED_NOT_APPLICABLE, EXPECTED_NOT_APPLICABLE, repr(na),
            "常量名用下划线仅因 Python 标识符限制；**值**必须是连字符")
    if isinstance(na, str):
        v.check(group, 'NOT_APPLICABLE 值中不含下划线', "_" not in na,
                "no underscore", repr(na))

    # 哨兵不得是因子水平
    for name, expected in (("CONTENT_LEVELS", EXPECTED_CONTENT_LEVELS),
                           ("CHANNEL_LEVELS", EXPECTED_CHANNEL_LEVELS),
                           ("STRATEGY_TIMING_LEVELS", EXPECTED_STRATEGY_TIMING_LEVELS)):
        levels = getattr(EC, name, None) if EC else None
        v.check(group, "%s == %s（真实水平，不含哨兵）" % (name, tuple(expected)),
                levels is not None and set(levels) == set(expected),
                set(expected), set(levels) if levels is not None else None)

    # 字段合法值 = 真实水平 ∪ {哨兵}：两层必须是不同常量
    for valid_name, level_expected in (("VALID_CONTENT_FACTORS", EXPECTED_CONTENT_LEVELS),
                                       ("VALID_CHANNEL_FACTORS", EXPECTED_CHANNEL_LEVELS)):
        valid = getattr(EC, valid_name, None) if EC else None
        v.check(group, "%s == 真实水平 ∪ {not-applicable}" % valid_name,
                valid is not None
                and set(valid) == set(level_expected) | {EXPECTED_NOT_APPLICABLE},
                set(level_expected) | {EXPECTED_NOT_APPLICABLE},
                set(valid) if valid is not None else None,
                "字段级合法性与因子水平是两件事，混用会让哨兵进入分组均值")
    valid_timing = getattr(EC, "VALID_TIMING_FACTORS", None) if EC else None
    v.check(group, "VALID_TIMING_FACTORS == 策略水平 ∪ {no-clarification}",
            valid_timing is not None
            and set(valid_timing) == set(EXPECTED_STRATEGY_TIMING_LEVELS)
            | {EXPECTED_CONTROL_TIMING},
            set(EXPECTED_STRATEGY_TIMING_LEVELS) | {EXPECTED_CONTROL_TIMING},
            set(valid_timing) if valid_timing is not None else None)

    # ── 生产 Python 的 AST 精确字面量检查（不做子串匹配）──
    #
    # 只判定一件事：精确字面量 "not_applicable" 是否被用作**当前字段值**。
    # 以下一律不会被误判，因为它们根本不是这个字面量：
    #   · NOT_APPLICABLE        —— 标识符，不是字符串常量
    #   · "not_applicable_value" —— 不同的字面量（§11.1 的合法 JSON 键名）
    #   · 历史文档中的说明文字   —— 非 Python，不在扫描范围内
    #   · 本测试中的非法输入反例 —— 测试文件不在扫描范围内
    # legacy 检测逻辑（函数名含 legacy）中出现该字面量属预期，豁免。
    all_offenders = []
    all_exempt = []
    unreadable = []
    for rel in S8_SCAN_FILES:
        sites = _exact_literal_sites(rel, FORBIDDEN_SENTINEL)
        if sites is None:
            if _read_source(rel) is None:
                continue                     # 文件不存在：不属于本项判定范围
            unreadable.append(rel)
            continue
        for owner, lineno in sites:
            tag = "%s:%d in %s" % (rel, lineno, owner)
            if LEGACY_CONTEXT_MARKER in owner.lower():
                all_exempt.append(tag)
            else:
                all_offenders.append(tag)
    v.check(group, "生产 Python 的 AST 中无下划线哨兵作为当前字段值",
            not all_offenders, "no occurrence", all_offenders,
            "扫描范围: %d 个生产文件；legacy 语境豁免: %s"
            % (len(S8_SCAN_FILES), all_exempt or "none"))
    v.check(group, "S8 扫描范围内所有文件均可解析", not unreadable,
            "all parseable", unreadable)


# ══════════════════════════════════════════════════════════════════════
# S7 TASK_002 契约的纯 schema 断言（承接清单见 design §10.2.3）
#
# 每条断言的 note 携带 "contract=Cn" 标记，S18 据此核对 7 项契约的归属登记，
# 避免"声称承接但没有任何断言真的执行"这种覆盖率净损失。
# ══════════════════════════════════════════════════════════════════════

def _synthetic_record_inputs():
    """build_agent_record 的合成输入（与 TASK_002 的 _synthetic_inputs 同构）。"""
    clr_msg = dict(CLARIFICATION_MSG)
    clr_msg["content_factor"] = "emotional-empathy"
    s_data = {
        "baseline_trust": 6.5,
        "last_observations": [clr_msg, {"source": "Global News", "content": "x"}],
        "reflect_message_sources": ["Enterprise_Clarification", "Global News"],
        "reflect_primary_source": "Global News",
        "raw_affective_output": -2.345678901234,
        "trust_change_affective": -2.0,
        "affective_was_clipped": True,
    }
    plan = {
        "trust_after_decay": 6.123, "affective_change": -1.2, "shock_anchor": 5.5,
        "quiet_ticks": 3, "decay_lambda": 0.07,
        "is_buying": True, "is_posting": True, "post_content": "p", "reason": "r",
        "previous_trust_raw": 6.5,
        "baseline_trust_raw": 6.5,
        "trust_after_decay_raw": 6.123456789012345,
        "affective_change_raw": -1.234567890123,
        "trust_score_raw": 4.888888888888,
        "shock_anchor_before_raw": 5.5,
        "shock_anchor_after_raw": 5.65,
        "decay_rate_raw": 0.190111111111,
        "sensitivity_multiplier": 0.6,
        "trust_clipped_at_bound": False,
        "anchor_update_branch": "clarification",
        "clr_anchor_lift_ratio": 0.35,
        "clr_lift_raw": 0.35,
        "is_quiet_day": False,
        "clarification_detected_by_plan": True,
        "clarification_content_type": "emotional-empathy",
        "plan_fallback_used": False,
    }
    thought = {"hypocrisy_perceived": True, "importance": 7.5, "reasoning": "x"}
    return s_data, plan, thought


def _build_record(SC, config, tick=6):
    s_data, plan, thought = _synthetic_record_inputs()
    return SC.build_agent_record(
        config=config, tick=tick, agent_id="Consumer_001",
        cluster_type="Convenient_Greens", social_role="Regular User",
        trust=5.3456789, s_data=s_data, plan=plan, thought=thought,
        out_degree=4, in_degree=2,
        is_clarification_target=False, clarification_injected=False,
        cumulative_buyers_count=7,
    )


def _fake_metadata_result(exp_id, cfg_dict, router_role, cache_size, miss_count):
    return {
        "exp_id": exp_id,
        "config": cfg_dict,
        "run_audit": {
            "started_at": "2026-01-01T00:00:00",
            "finished_at": "2026-01-01T00:01:00",
            "recording_cache_size": cache_size,
            "replay_miss_count": miss_count,
            "router_role": router_role,
        },
        "target_nodes_meta": [],
        "network_meta": {"network_hash": "0" * 64},
        "effective_event_timeline": [5],
    }


def check_s7_task002_schema(v, EC, RX, SC):
    group = "S7-task002-schema"

    # ── C1：AGENT_RECORDS_FIELDS 长度 60 且无重复 ──
    fields = list(getattr(SC, "AGENT_RECORDS_FIELDS", []) or []) if SC else []
    v.check(group, "AGENT_RECORDS_FIELDS 长度 == 60",
            len(fields) == EXPECTED_AGENT_RECORDS_FIELD_COUNT,
            EXPECTED_AGENT_RECORDS_FIELD_COUNT, len(fields), "contract=C1")
    dups = sorted({n for n in fields if fields.count(n) > 1})
    v.check(group, "AGENT_RECORDS_FIELDS 无重复字段", not dups, "no duplicates", dups,
            "contract=C1")
    v.check(group, 'AGENT_RECORDS_SCHEMA_VERSION == "2.0"',
            getattr(SC, "AGENT_RECORDS_SCHEMA_VERSION", None)
            == EXPECTED_AGENT_RECORDS_SCHEMA_VERSION,
            EXPECTED_AGENT_RECORDS_SCHEMA_VERSION,
            repr(getattr(SC, "AGENT_RECORDS_SCHEMA_VERSION", None)),
            "contract=C1 TASK_003 只改字段的值，不改 schema 版本")

    # ── C2：v1.0 的 21 字段相对顺序严格递增 ──
    if fields:
        missing = [f for f in V1_FIELDS if f not in fields]
        v.check(group, "v1.0 的 21 字段全部仍在 schema 中", not missing,
                "all present", missing, "contract=C2")
        if not missing:
            idx = [fields.index(f) for f in V1_FIELDS]
            v.check(group, "v1.0 21 字段相对顺序严格递增",
                    all(a < b for a, b in zip(idx, idx[1:])), "strictly increasing",
                    idx, "contract=C2")
    else:
        v.error(group, "v1.0 字段顺序可校验", "AGENT_RECORDS_FIELDS 不可用 (contract=C2)")

    # ── C3：EXPERIMENT_METADATA_FIELDS 仍为 18 且键集合不变 ──
    meta_fields = list(getattr(RX, "EXPERIMENT_METADATA_FIELDS", []) or []) if RX else []
    v.check(group, "EXPERIMENT_METADATA_FIELDS 长度 == 18",
            len(meta_fields) == EXPECTED_EXPERIMENT_METADATA_FIELD_COUNT,
            EXPECTED_EXPERIMENT_METADATA_FIELD_COUNT, len(meta_fields),
            "contract=C3 矩阵版本信息只进 run_metadata.json，绝不给这里加字段")
    v.check(group, "EXPERIMENT_METADATA_FIELDS 无重复", len(meta_fields) == len(set(meta_fields)),
            len(meta_fields), len(set(meta_fields)), "contract=C3")

    # ── C4 / C5：build_agent_record 对**对照**与**策略**各构造一次 ──
    if SC is None or EC is None:
        v.error(group, "build_agent_record 可校验", "模块未能导入 (contract=C4,C5)")
    else:
        stg, err = _strategy_cfg(EC)
        if stg is None:
            v.error(group, "策略条件记录可构造",
                    "配置构造失败: %s (contract=C4)" % err)
        else:
            try:
                rec = _build_record(SC, stg)
                v.check(group, "策略条件记录键集合 == 60 字段",
                        set(rec.keys()) == set(fields), "equal",
                        "diff=%s" % sorted(set(rec.keys()) ^ set(fields)), "contract=C4")
                v.check(group, "策略条件 clarification_tick_config 为 int",
                        isinstance(rec.get("clarification_tick_config"), int),
                        "int", type(rec.get("clarification_tick_config")).__name__,
                        "contract=C5")
            except Exception as e:
                v.error(group, "策略条件记录可构造",
                        "%s: %s (contract=C4)" % (type(e).__name__, e))

        ctl, err = _control_cfg(EC)
        if ctl is None:
            v.error(group, "共同对照记录可构造",
                    "对照配置构造失败: %s (contract=C4,C5)" % err)
        else:
            try:
                rec = _build_record(SC, ctl)
                v.check(group, "共同对照记录键集合 == 60 字段",
                        set(rec.keys()) == set(fields), "equal",
                        "diff=%s" % sorted(set(rec.keys()) ^ set(fields)), "contract=C4")
                ctc = rec.get("clarification_tick_config")
                v.check(group, '共同对照 clarification_tick_config == ""', ctc == "",
                        '""', repr(ctc), "contract=C5")
                v.check(group, "共同对照 clarification_tick_config 不是 0 / 不是 int",
                        not isinstance(ctc, int), "not int", type(ctc).__name__,
                        'contract=C5 "" = 不适用，0 = 真实的零，两者不得混用')
                v.check(group, "共同对照记录 content_factor == not-applicable",
                        rec.get("content_factor") == EXPECTED_NOT_APPLICABLE,
                        EXPECTED_NOT_APPLICABLE, repr(rec.get("content_factor")),
                        "contract=C5")
                v.check(group, "共同对照记录 has_clarification 为 False",
                        rec.get("has_clarification") is False, False,
                        repr(rec.get("has_clarification")),
                        "contract=C5 对照的 clarification_tick 为 None，永不等于任何 tick")
            except Exception as e:
                v.error(group, "共同对照记录可构造",
                        "%s: %s (contract=C4)" % (type(e).__name__, e))

    # ── C6：run 级网络文件列契约 ──
    nodes = list(getattr(RX, "NETWORK_NODES_FIELDS", []) or []) if RX else []
    edges = list(getattr(RX, "NETWORK_EDGES_FIELDS", []) or []) if RX else []
    v.check(group, "NETWORK_NODES_FIELDS 列契约不变", nodes == EXPECTED_NETWORK_NODES_FIELDS,
            EXPECTED_NETWORK_NODES_FIELDS, nodes, "contract=C6")
    v.check(group, "NETWORK_EDGES_FIELDS 列契约不变", edges == EXPECTED_NETWORK_EDGES_FIELDS,
            EXPECTED_NETWORK_EDGES_FIELDS, edges, "contract=C6")
    v.check(group, "两个 run 级网络文件均不含 exp_id",
            "exp_id" not in nodes and "exp_id" not in edges,
            "absent", "present", "contract=C6 它们是 run 级静态文件，与矩阵无关")

    # ── C7：router_role / recording_cache_size / replay_miss_count 的 "" 与 0 可区分 ──
    for name in ("router_role", "recording_cache_size", "replay_miss_count"):
        v.check(group, "experiment_metadata 保留字段 " + name, name in meta_fields,
                "present", "absent" if name not in meta_fields else "present",
                "contract=C7")
    if RX is None or not hasattr(RX, "write_experiment_metadata_jsonl"):
        v.error(group, '"" 与 0 可区分性可校验', "write_experiment_metadata_jsonl 不可用 "
                                              "(contract=C7)")
    else:
        try:
            ctl_dict = {"exp_id": EXPECTED_CONTROL_EXP_ID,
                        "content_factor": EXPECTED_NOT_APPLICABLE,
                        "channel_factor": EXPECTED_NOT_APPLICABLE,
                        "timing_factor": EXPECTED_CONTROL_TIMING,
                        "clarification_tick": None, "random_seed": 42,
                        "budget_k": EXPECTED_CONTROL_BUDGET_K}
            stg_dict = {"exp_id": "Rational-Hub-Immediate",
                        "content_factor": "rational-evidence", "channel_factor": "hub",
                        "timing_factor": "immediate",
                        "clarification_tick": EXPECTED_IMMEDIATE_TICK,
                        "random_seed": 42, "budget_k": EXPECTED_STRATEGY_BUDGET_K}
            results = [
                # 录制组：无 ReplayRouter → replay_miss_count 必须是 ""，不是 0
                _fake_metadata_result(EXPECTED_CONTROL_EXP_ID, ctl_dict,
                                      "recording", 120, ""),
                # 回放组：零 miss 是真实的 0，不是 ""
                _fake_metadata_result("Rational-Hub-Immediate", stg_dict,
                                      "replay", 120, 0),
            ]
            with tempfile.TemporaryDirectory() as td:
                path = os.path.join(td, "experiment_metadata.jsonl")
                RX.write_experiment_metadata_jsonl(results, path)
                rows = [json.loads(ln) for ln in open(path, encoding="utf-8")
                        if ln.strip()]
            v.check(group, "experiment_metadata.jsonl 每实验一行", len(rows) == 2, 2, len(rows),
                    "contract=C3")
            for row in rows:
                v.check(group, "行键集合 == 18 字段: " + row.get("exp_id", "?"),
                        set(row.keys()) == set(meta_fields), "equal",
                        "diff=%s" % sorted(set(row.keys()) ^ set(meta_fields)),
                        "contract=C3")
            rec_row = next((r for r in rows if r["router_role"] == "recording"), {})
            rep_row = next((r for r in rows if r["router_role"] == "replay"), {})
            v.check(group, '录制组 replay_miss_count == ""（不适用）',
                    rec_row.get("replay_miss_count") == ""
                    and not isinstance(rec_row.get("replay_miss_count"), int),
                    '""', repr(rec_row.get("replay_miss_count")), "contract=C7")
            v.check(group, "回放组 replay_miss_count == 0（真实的零）",
                    rep_row.get("replay_miss_count") == 0
                    and isinstance(rep_row.get("replay_miss_count"), int),
                    0, repr(rep_row.get("replay_miss_count")), "contract=C7")
            v.check(group, '共同对照 clarification_tick 落盘为 ""',
                    rec_row.get("clarification_tick") == "",
                    '""', repr(rec_row.get("clarification_tick")),
                    "contract=C5 clarification_tick 继续真实落盘，None → \"\"")
            v.check(group, "策略条件 clarification_tick 落盘为 6",
                    rep_row.get("clarification_tick") == EXPECTED_IMMEDIATE_TICK,
                    EXPECTED_IMMEDIATE_TICK, repr(rep_row.get("clarification_tick")),
                    "contract=C5")
        except Exception as e:
            v.error(group, '"" 与 0 可区分性', "%s: %s (contract=C7)" % (type(e).__name__, e))


# ══════════════════════════════════════════════════════════════════════
# S9 录制 / 回放配对
# ══════════════════════════════════════════════════════════════════════

def check_s9_recording_replay_pairing(v, EC, RX, matrix):
    group = "S9-record-replay"

    # ── 功能面：策略组的回放边界必须等于各自的 clarification_tick ──
    if matrix:
        strategies = [c for c in matrix if not _is_control(c)]
        controls = [c for c in matrix if _is_control(c)]
        actual = {c.exp_id: c.clarification_tick for c in strategies}
        v.check(group, "8 个策略组 replay_until == clarification_tick（4 个 6 / 4 个 10）",
                actual == EXPECTED_REPLAY_UNTIL, EXPECTED_REPLAY_UNTIL, actual,
                "immediate 回放 Tick 1–5，delayed 回放 Tick 1–9")
        v.check(group, "录制组 == 唯一共同对照",
                len(controls) == 1
                and controls[0].exp_id == EXPECTED_CONTROL_EXP_ID,
                EXPECTED_CONTROL_EXP_ID,
                [c.exp_id for c in controls],
                "对照先录制全 30 Tick，8 个策略组回放同一份缓存")
        v.check(group, "所有策略条件 clarification_tick 非 None",
                all(c.clarification_tick is not None for c in strategies),
                "all not None",
                [c.exp_id for c in strategies if c.clarification_tick is None],
                "组合级校验已保证；这是删除 total_ticks+1 分支的前提")
    else:
        v.error(group, "回放边界可校验", "S1 未能取得矩阵")

    # ── 源码面：total_ticks + 1 魔法值必须已从 run_experiments.py 删除 ──
    src = _read_source("run_experiments.py")
    if src is None:
        v.error(group, "run_experiments.py 可读", "文件不存在")
        return
    norm = _normalized(src)
    v.check(group, "run_experiments.py 已删除 total_ticks + 1 魔法值",
            "total_ticks+1" not in norm, "absent",
            "present" if "total_ticks+1" in norm else "absent",
            "该魔法值唯一用途是让无 clarification_tick 的组全程回放，"
            "而那些组之所以存在正是因为对照被复制了 4 份（design §7.3）")
    v.check(group, "录制组选择改用 is_control 布尔属性（不做字符串匹配）",
            "is_control" in norm,
            "uses is_control", "absent",
            'if timing_factor == "no-clarification" 式的字符串匹配必须消失')
    v.check(group, "录制组选择不再依赖 content/channel 组合",
            not ('c.channel_factor=="hub"' in norm
                 and 'c.content_factor=="rational-evidence"' in norm),
            "no content/channel condition", "still present",
            "旧代码用 no-clarification + hub + rational 挑录制组（D3）")


# ══════════════════════════════════════════════════════════════════════
# S10 ReplayRouter 能力核实 + S10.1 窗口内 miss fail-closed
# ══════════════════════════════════════════════════════════════════════

def _make_replay_router(RX, cache, until, exp_id="Rational-Hub-Immediate"):
    """构造 ReplayRouter，兼容尚未新增 exp_id 参数的 pre-TASK_003 签名。"""
    inner = CountingInnerRouter()
    try:
        return RX.ReplayRouter(inner, cache, replay_until_tick=until, exp_id=exp_id), inner
    except TypeError:
        return RX.ReplayRouter(inner, cache, replay_until_tick=until), inner


async def check_s10_replay_router(v, RX):
    """S10 = ReplayRouter 的**行为契约**。

    本项刻意不断言任何实现细节属性（例如 divergent_cache / record_after_divergence
    是否存在）：那会把测试焊死在一种特定实现上，而设计要求的是行为。
    要保证的是"分叉后不写基线缓存"这一**可观测后果**，见第 5 条。
    """
    group = "S10-replay-behavior"
    if RX is None or not hasattr(RX, "ReplayRouter"):
        v.error(group, "ReplayRouter 可用", "run_experiments 未能导入或缺少 ReplayRouter")
        return

    prompt_hit = "PROMPT-HIT"
    prompt_miss = "PROMPT-MISS"
    pk_hit = RX.RecordingRouter._pk(prompt_hit)
    until = EXPECTED_IMMEDIATE_TICK          # 回放窗口 = Tick < 6
    exc_cls = getattr(RX, "ReplayAlignmentError", None)

    # 共同对照基线缓存：全程只读，任何路径都不得修改它
    cache = {(pk_hit, 3, 0): "CACHED-T3"}
    baseline_snapshot = dict(cache)
    router, inner = _make_replay_router(RX, cache, until)

    def _cache_unchanged(label):
        v.check(group, "5 %s 后基线 cache 未被修改" % label,
                cache == baseline_snapshot,
                "%d entries unchanged" % len(baseline_snapshot),
                "%d entries, equal=%s" % (len(cache), cache == baseline_snapshot),
                "基线缓存是 8 个策略组共享的唯一数据源；任何写入都会污染其余组")

    # ── 1：窗口内命中 → 真实 Router 调用数为 0 ──
    try:
        router.set_tick(3)
        got = await router.chat(prompt_hit)
        v.check(group, "1 窗口内命中返回缓存值", got == "CACHED-T3", "CACHED-T3", repr(got))
        v.check(group, "1 窗口内命中时真实 Router 调用数为 0", inner.calls == 0, 0,
                inner.calls)
        v.check(group, "1 窗口内命中不增加 miss_count", router.miss_count == 0, 0,
                router.miss_count)
        _cache_unchanged("窗口内命中")
    except Exception as e:
        v.error(group, "1 窗口内命中", "%s: %s" % (type(e).__name__, e))

    # ── 2：窗口内 miss → miss_count+1、抛 ReplayAlignmentError、真实 Router 调用数为 0 ──
    calls_before = inner.calls
    miss_before = router.miss_count
    raised = None
    try:
        router.set_tick(3)
        await router.chat(prompt_miss)
    except Exception as e:
        raised = e
    v.check(group, "2 窗口内 miss 使 miss_count 增加 1",
            router.miss_count == miss_before + 1, miss_before + 1, router.miss_count)
    if isinstance(exc_cls, type):
        v.check(group, "2 窗口内 miss 抛 ReplayAlignmentError",
                isinstance(raised, exc_cls), "ReplayAlignmentError",
                type(raised).__name__ if raised else "no exception")
    else:
        v.check(group, "2 窗口内 miss 抛 ReplayAlignmentError", False,
                "ReplayAlignmentError",
                type(raised).__name__ if raised else "no exception",
                "ReplayAlignmentError 尚未定义")
    v.check(group, "2 窗口内 miss 时真实 Router 调用数为 0",
            inner.calls == calls_before, calls_before, inner.calls,
            "fail-closed：禁止落穿到真实 Router")
    _cache_unchanged("窗口内 miss")

    # ── 3 / 4：窗口外正常调用，且不增加 miss_count ──
    calls_before = inner.calls
    miss_before = router.miss_count
    try:
        router.set_tick(until + 2)
        got = await router.chat(prompt_hit)
        v.check(group, "3 窗口外正常调用真实 Router 并返回其响应",
                got == "REAL_ROUTER_RESPONSE" and inner.calls == calls_before + 1,
                "real response, calls+1", "%r, calls=%d" % (got, inner.calls))
        v.check(group, "4 窗口外调用不增加 miss_count",
                router.miss_count == miss_before, miss_before, router.miss_count,
                "窗口外是正常分叉，不是对齐违约")
        _cache_unchanged("窗口外调用")
    except Exception as e:
        v.error(group, "3 窗口外调用", "%s: %s" % (type(e).__name__, e))

    # 窗口外的"未缓存 prompt"同样不得写入基线缓存
    try:
        router.set_tick(until + 3)
        await router.chat(prompt_miss)
        _cache_unchanged("窗口外未缓存 prompt")
    except Exception as e:
        v.error(group, "3 窗口外未缓存 prompt", "%s: %s" % (type(e).__name__, e))


async def check_s10_1_fail_closed(v, RX):
    group = "S10.1-fail-closed"
    if RX is None or not hasattr(RX, "ReplayRouter"):
        v.error(group, "ReplayRouter 可用", "run_experiments 未能导入或缺少 ReplayRouter")
        return

    exc_cls = getattr(RX, "ReplayAlignmentError", None)
    v.check(group, "ReplayAlignmentError 已定义",
            isinstance(exc_cls, type) and issubclass(exc_cls, Exception),
            "exception class", repr(exc_cls),
            "窗口内 miss 是对齐前提被打破的信号，必须有专用异常类型（design §8.5.2）")

    prompt_hit = "PROMPT-HIT"
    prompt_miss = "PROMPT-MISS"
    pk_hit = RX.RecordingRouter._pk(prompt_hit)
    until = EXPECTED_DELAYED_TICK             # 回放窗口 = Tick < 10

    # 缓存中**故意缺少** prompt_miss 在窗口内的键
    cache = {(pk_hit, 3, 0): "CACHED-T3"}
    router, inner = _make_replay_router(RX, cache, until)

    # ① 抛 ReplayAlignmentError；② 真实 Router 未被调用；③ miss_count == 1
    raised = None
    try:
        router.set_tick(3)
        await router.chat(prompt_miss)
    except Exception as e:
        raised = e

    if exc_cls is not None and isinstance(exc_cls, type):
        v.check(group, "① 窗口内 miss 抛 ReplayAlignmentError",
                isinstance(raised, exc_cls), "ReplayAlignmentError",
                type(raised).__name__ if raised else "no exception")
    else:
        v.check(group, "① 窗口内 miss 抛 ReplayAlignmentError", False,
                "ReplayAlignmentError",
                type(raised).__name__ if raised else "no exception",
                "异常类型尚未定义")
    v.check(group, "② 窗口内 miss 时真实 Router 未被调用", inner.calls == 0, 0, inner.calls,
            "禁止 fallback：一旦落穿，该组轨迹就不再是共同对照的正确反事实前缀")
    v.check(group, "③ 窗口内 miss 后 miss_count == 1", router.miss_count == 1, 1,
            router.miss_count)

    # ④ 窗口外（tick >= replay_until）仍正常返回，且 miss_count 不变
    try:
        miss_before = router.miss_count
        router.set_tick(until + 1)
        got = await router.chat(prompt_miss)
        v.check(group, "④ 窗口外调用仍正常返回", got == "REAL_ROUTER_RESPONSE",
                "REAL_ROUTER_RESPONSE", repr(got))
        v.check(group, "④ 窗口外调用不改变 miss_count", router.miss_count == miss_before,
                miss_before, router.miss_count)
    except Exception as e:
        v.error(group, "④ 窗口外调用", "%s: %s" % (type(e).__name__, e))

    # ⑤ 失败元数据必须保留完整 config / error_type / run_audit
    failure = _simulated_failure_record(RX, raised)
    required_cfg_keys = ("exp_id", "content_factor", "channel_factor", "timing_factor",
                         "random_seed", "budget_k", "clarification_tick")
    cfg = failure.get("config", {}) or {}
    v.check(group, "⑤ 失败实验保留完整 config",
            all(k in cfg for k in required_cfg_keys),
            sorted(required_cfg_keys), sorted(cfg.keys()),
            "失败实验恰恰最需要知道哪一组因子 / 什么 seed（TASK_002 R12）")
    v.check(group, '⑤ 失败实验 error_type == "ReplayAlignmentError"',
            failure.get("error_type") == "ReplayAlignmentError",
            "ReplayAlignmentError", repr(failure.get("error_type")))
    v.check(group, "⑤ 失败实验保留非空 run_audit",
            bool(failure.get("run_audit")), "non-empty", failure.get("run_audit"))
    v.check(group, "⑤ 失败实验无 trust_trajectory（不进入任何有效对比）",
            "trust_trajectory" not in failure, "absent",
            "present" if "trust_trajectory" in failure else "absent",
            "轨迹不得进入 summary.csv 有效行")

    # 源码面：窗口内 miss 分支不得再落穿到真实 Router
    src = _read_source("run_experiments.py")
    if src is not None:
        norm = _normalized(src)
        v.check(group, "run_experiments.py 定义 ReplayAlignmentError",
                "classReplayAlignmentError" in norm, "defined",
                "absent" if "classReplayAlignmentError" not in norm else "defined")
        v.check(group, "main() 具备 except ReplayAlignmentError 失败分支",
                "exceptReplayAlignmentError" in norm, "present",
                "absent" if "exceptReplayAlignmentError" not in norm else "present")
        v.check(group, "批次末尾以退出码 4 结束（产物落盘之后）",
                "SystemExit(4)" in norm, "SystemExit(4)",
                "absent" if "SystemExit(4)" not in norm else "present",
                "0 = 正常，3 = 网络一致性违约，4 = Replay 对齐违约")


def _simulated_failure_record(RX, raised):
    """按 design §13.2 的失败分支语义构造一条失败结果，用于 ⑤ 的元数据断言。

    这里刻意**不**调用 main()（会触发真实运行），只复现其失败分支的记录结构。
    config 取自真实 ExperimentConfig.to_dict()（若可构造），否则退回等价字典。
    """
    cfg_dict = None
    try:
        import experiment_config as EC_mod
        cfg, _ = _cfg(EC_mod, "rational-evidence", "hub", "immediate")
        if cfg is not None:
            cfg_dict = cfg.to_dict()
    except Exception:
        cfg_dict = None
    if cfg_dict is None:
        cfg_dict = {"exp_id": "Rational-Hub-Immediate",
                    "content_factor": "rational-evidence", "channel_factor": "hub",
                    "timing_factor": "immediate", "random_seed": 42,
                    "budget_k": EXPECTED_STRATEGY_BUDGET_K,
                    "clarification_tick": EXPECTED_IMMEDIATE_TICK}
    return {
        "exp_id": cfg_dict.get("exp_id", "Rational-Hub-Immediate"),
        "config": cfg_dict,
        "error_type": type(raised).__name__ if raised is not None else "",
        "error": str(raised) if raised is not None else "",
        "run_audit": {"started_at": "2026-01-01T00:00:00",
                      "finished_at": "2026-01-01T00:00:10",
                      "recording_cache_size": 120,
                      "replay_miss_count": 1,
                      "router_role": "replay"},
    }


# ══════════════════════════════════════════════════════════════════════
# S11 summary.csv 列契约（含 D1 修复：错误行格数必须等于表头格数）
# ══════════════════════════════════════════════════════════════════════

def check_s11_summary_columns(v, RX):
    group = "S11-summary-columns"
    if RX is None:
        v.error(group, "run_experiments 可用", "模块未能导入")
        return

    summary_fields = getattr(RX, "SUMMARY_FIELDS", None)
    v.check(group, "SUMMARY_FIELDS 常量存在（列数不再由字面量 16 决定）",
            isinstance(summary_fields, (list, tuple)) and len(summary_fields) > 0,
            "list/tuple", type(summary_fields).__name__,
            "D1 修复：错误行格数必须由表头派生，永不与表头脱节")
    if isinstance(summary_fields, (list, tuple)):
        v.check(group, "SUMMARY_FIELDS 含 is_control 列",
                "is_control" in summary_fields, "present",
                "absent" if "is_control" not in summary_fields else "present",
                "分析层一律 df[~df.is_control]，而不是字符串比较 timing_factor")
        v.check(group, "SUMMARY_FIELDS 无重复",
                len(summary_fields) == len(set(summary_fields)),
                len(summary_fields), len(set(summary_fields)))

    if not hasattr(RX, "write_summary_csv"):
        v.error(group, "write_summary_csv 可用", "函数不存在")
        return

    # ── 功能面（D1 的直接反证）：一条失败实验就足以暴露列数脱节 ──
    err_result = {
        "exp_id": "Rational-Hub-Immediate",
        "config": {"exp_id": "Rational-Hub-Immediate",
                   "content_factor": "rational-evidence", "channel_factor": "hub",
                   "timing_factor": "immediate", "is_control": False,
                   "clarification_tick": EXPECTED_IMMEDIATE_TICK,
                   "random_seed": 42, "budget_k": EXPECTED_STRATEGY_BUDGET_K},
        "error": "ReplayAlignmentError: window-internal cache miss",
        "error_type": "ReplayAlignmentError",
    }
    try:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "summary.csv")
            RX.write_summary_csv([err_result], path)
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        header = rows[0] if rows else []
        err_row = rows[1] if len(rows) > 1 else []
        v.check(group, "summary.csv 表头含 is_control 列", "is_control" in header,
                "present", "absent" if "is_control" not in header else "present")
        v.check(group, "错误行格数 == 表头格数（D1）",
                len(err_row) == len(header),
                "%d == %d" % (len(header), len(header)),
                "%d vs %d" % (len(err_row), len(header)),
                "列数不齐会让 pandas 读取时整表错位")
    except Exception as e:
        v.error(group, "write_summary_csv 可写出", "%s: %s" % (type(e).__name__, e))

    # ── trajectories.csv 也必须带 is_control ──
    if hasattr(RX, "write_trajectories_csv"):
        src = _read_source("run_experiments.py") or ""
        try:
            tree = ast.parse(src)
            traj_fn = next((n for n in tree.body
                            if isinstance(n, ast.FunctionDef)
                            and n.name == "write_trajectories_csv"), None)
            literals = {n.value for n in ast.walk(traj_fn) if isinstance(n, ast.Constant)
                        and isinstance(n.value, str)} if traj_fn else set()
            v.check(group, "trajectories.csv 表头含 is_control",
                    "is_control" in literals, "present",
                    "absent" if "is_control" not in literals else "present")
        except Exception as e:
            v.error(group, "trajectories.csv 表头可校验", "%s: %s" % (type(e).__name__, e))


# ══════════════════════════════════════════════════════════════════════
# S12 绘图函数名核对（D2 修复）
# ══════════════════════════════════════════════════════════════════════

def _module_level_names(rel):
    """模块顶层可访问名称：def / async def / 赋值目标 / class。"""
    src = _read_source(rel)
    if src is None:
        return None
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _attr_names_by_var(rel, var_names):
    """返回 {变量名: {属性名, ...}}，用于核对跨模块调用点。"""
    src = _read_source(rel)
    if src is None:
        return None
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    out = {name: set() for name in var_names}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id in out):
            out[node.value.id].add(node.attr)
    return out


def check_s12_plot_function_names(v):
    group = "S12-plot-names"

    used = _attr_names_by_var("run_experiments.py", {"_pe", "_pt_traj"})
    if used is None:
        v.error(group, "run_experiments.py 可解析", "文件不可读或语法错误")
        return

    modules = {
        "_pe": ("analysis/plot_experiments.py", _module_level_names("analysis/plot_experiments.py")),
        "_pt_traj": ("analysis/plot_trajectories.py",
                     _module_level_names("analysis/plot_trajectories.py")),
    }
    for var, (rel, available) in modules.items():
        if available is None:
            v.error(group, "%s 可解析" % rel, "文件不可读或语法错误")
            continue
        called = sorted(used.get(var, set()))
        v.check(group, "%s 的调用点非空（确实有图表被调用）" % rel, bool(called),
                "non-empty", called)
        for attr in called:
            v.check(group, "%s 中存在 %s" % (rel, attr), attr in available,
                    "defined", "MISSING" if attr not in available else "defined",
                    "D2：run_experiments 调用不存在的函数名，异常被 except 吞掉后"
                    "全部轨迹图静默缺失")

    traj_names = modules["_pt_traj"][1] or set()
    v.check(group, "plot_trajectories 提供 plot_all_9_conditions",
            "plot_all_9_conditions" in traj_names, "defined",
            "absent" if "plot_all_9_conditions" not in traj_names else "defined",
            "4×2 策略面板 + 每格叠加唯一共同对照参考线")
    v.check(group, "plot_trajectories 不再提供 plot_all_12_strategies",
            "plot_all_12_strategies" not in traj_names, "absent",
            "present" if "plot_all_12_strategies" in traj_names else "absent",
            "12 面板结构对应的是被废弃的伪条件矩阵")


# ══════════════════════════════════════════════════════════════════════
# S13 分析层值域闸门（正反用例）
# ══════════════════════════════════════════════════════════════════════

def _reference_strategy_rows(rows):
    """参考实现：闸门先按 is_control 过滤，再对策略行做值域断言。

    与生产实现保持同一语义。它的作用是让 S13 的反例有一个确定的判据：
    "注入一行 not-applicable 到策略集合后必须被捕获"。
    """
    kept = [r for r in rows if not bool(r.get("is_control"))]
    for col in ("content_factor", "channel_factor"):
        bad = [r for r in kept if r.get(col) == EXPECTED_NOT_APPLICABLE]
        if bad:
            raise AssertionError(
                "'%s' leaked into strategy rows via %s: is_control filter failed"
                % (EXPECTED_NOT_APPLICABLE, col))
    return kept


def _metric_columns(i):
    """一组完整的指标列，取值互不相同以避免退化。

    刻意覆盖 summary.csv 的**全部**指标列（而不只是三个核心指标）：集成验证
    要把这张表交给真实的分析入口，缺列会让入口抛 KeyError，那种失败与
    「闸门未被调用」毫无关系，只会污染判定。
    """
    return {
        "delta_recovery": round(0.10 + i * 0.01, 4),
        "auc_post_scandal": round(1.00 + i * 0.10, 4),
        "recovery_speed": round(0.10 + i * 0.01, 4),
        "steady_state_score": round(6.00 + i * 0.05, 4),
        "recovery_rate": round(0.20 + i * 0.02, 4),
        "t50": 8 + i,
        "t80": 12 + i,
        "trust_min": round(4.00 + i * 0.03, 4),
        "trust_min_tick": 6,
        "baseline_trust": 6.5,
        "clarification_effect": round(0.30 + i * 0.01, 4),
        "trust_gain_vs_control": round(0.05 + i * 0.01, 4),
    }


def _nine_condition_rows():
    """8 个策略行 + 1 个共同对照行（S13 的标准输入，列集合对齐 summary.csv）。"""
    control = {"exp_id": EXPECTED_CONTROL_EXP_ID,
               "content_factor": EXPECTED_NOT_APPLICABLE,
               "channel_factor": EXPECTED_NOT_APPLICABLE,
               "timing_factor": EXPECTED_CONTROL_TIMING,
               "is_control": True}
    control.update(_metric_columns(0))
    control["trust_gain_vs_control"] = 0.0      # 对照相对自身的增益恒为 0
    rows = [control]
    for i, eid in enumerate(sorted(EXPECTED_STRATEGY_EXP_IDS), start=1):
        row = {
            "exp_id": eid,
            "content_factor": ("rational-evidence" if eid.startswith("Rational")
                               else "emotional-empathy"),
            "channel_factor": "hub" if "-Hub-" in eid else "random",
            "timing_factor": "immediate" if eid.endswith("Immediate") else "delayed",
            "is_control": False,
        }
        row.update(_metric_columns(i))
        rows.append(row)
    return rows


SKIP_PROBE_PREFIXES = ("plot_", "load_", "main")


def _accepts_one_dataframe_arg(fn):
    """签名是否可以接受**一个** DataFrame 位置参数。

    只接受"恰好能用一个位置实参调用"的函数：至少一个可位置传入的形参，
    且其余形参都有默认值或是 *args / **kwargs。签名不可判定时返回 False——
    宁可漏掉一个候选，也不要用错误的参数数量去调用无关函数、制造异常噪声。
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    positional = 0
    required_extra = 0
    has_var_positional = False
    for i, p in enumerate(sig.parameters.values()):
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                      inspect.Parameter.POSITIONAL_OR_KEYWORD):
            if i == 0:
                positional += 1
            elif p.default is inspect.Parameter.empty:
                required_extra += 1
        elif p.kind == inspect.Parameter.VAR_POSITIONAL:
            has_var_positional = True
        elif (p.kind == inspect.Parameter.KEYWORD_ONLY
              and p.default is inspect.Parameter.empty):
            required_extra += 1
    if required_extra:
        return False
    return positional == 1 or (positional == 0 and has_var_positional)


def _probe_analysis_gate(rows_good, rows_bad):
    """在不限定 helper 名称的前提下，功能性地探测分析层的值域闸门。

    候选函数必须**同时**满足六条硬约束（design §12.3.4）：
        1. inspect.isfunction(fn)
        2. fn.__module__ == _pe.__name__      —— 排除导入进来的第三方 callable
        3. 非 class、非导入 callable
        4. 签名可接受一个 DataFrame 位置参数
        5. 名称不以 plot_ / load_ / main 开头（这些有 I/O 副作用）
        6. 在临时目录内执行（OUTPUT_DIR / RESULTS_DIR 重定向）

    候选判定必须**同时**满足六项才算通过（R-26）：
        1. len(out) == 8                       —— 行数精确为 8
        2. len(out["exp_id"]) == 8             —— exp_id 列长度精确为 8
        3. exp_id 无重复                        —— 排除"4 行各出现两次"之类
        4. exp_id 集合恰为 EXPECTED_STRATEGY_EXP_IDS
        5. 结果不含 NoClarification-Control
        6. 错标 not-applicable 的策略行输入 → 必须抛错

    为什么不能只用 set(out["exp_id"]) 判断：集合会把重复行折叠掉。一个返回
    16 行（每个策略 exp_id 各两行）的函数，其 exp_id 集合与期望完全相等，
    但它显然不是闸门——而下游的主效应均值会因重复行被算错。因此行数与
    去重前的列长度必须单独断言。

    两类"未通过"的候选都不得提前返回，必须继续检查后续候选：
        · invalid  —— 集合相等但行数不等于 8 或存在重复行；
        · filter_only —— 过滤通过但反例不抛错（只会过滤、不会报错的半成品）。
    否则任何一个半成品都会掩盖真正的缺失。

    返回 (status, detail, good_ids, raised_on_bad, candidate_name)
        status ∈ {"ok", "no_gate", "unavailable"}
        status == "no_gate" 时 detail 会分别列出 invalid 与 filter_only 候选。
        candidate_name 供 R-30 的集成验证使用：**找到一个正确的候选还不够，
        还必须证明分析入口真的调用了它**。
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import pandas as pd
    except Exception as e:
        return ("unavailable",
                "pandas/matplotlib 不可用: %s: %s" % (type(e).__name__, e),
                None, None, None)

    analysis_dir = os.path.join(project_root, "analysis")
    if analysis_dir not in sys.path:
        sys.path.insert(0, analysis_dir)
    try:
        import plot_experiments as _pe
    except Exception as e:
        return ("unavailable",
                "plot_experiments 导入失败: %s: %s" % (type(e).__name__, e),
                None, None, None)

    df_good = pd.DataFrame(rows_good)
    df_bad = pd.DataFrame(rows_bad)
    considered = []
    filter_only = []            # 过滤通过但反例不抛错的半成品候选
    invalid = []                # 集合相等但行数 / 重复性不合格的候选

    with tempfile.TemporaryDirectory() as td:
        # 约束 6：重定向输出目录，确保探测不向仓库写入任何文件
        for attr in ("OUTPUT_DIR", "RESULTS_DIR"):
            if hasattr(_pe, attr):
                setattr(_pe, attr, td)

        for name in sorted(vars(_pe)):
            if name.startswith("__") or name.startswith(SKIP_PROBE_PREFIXES):
                continue          # 约束 5
            fn = vars(_pe)[name]
            if isinstance(fn, type):
                continue          # 约束 3：类不是候选
            if not inspect.isfunction(fn):
                continue          # 约束 1：只要真正的 Python 函数
            if getattr(fn, "__module__", None) != _pe.__name__:
                continue          # 约束 2：必须定义于该模块自身
            if not _accepts_one_dataframe_arg(fn):
                continue          # 约束 4
            considered.append(name)

            try:
                out = fn(df_good.copy())
            except Exception:
                continue
            try:
                id_list = list(out["exp_id"])
            except Exception:
                continue

            ids = set(id_list)
            # 判据 4：集合必须先相等，否则这个函数与闸门无关，不计入 invalid
            if ids != set(EXPECTED_STRATEGY_EXP_IDS):
                continue

            # 判据 1 / 2 / 3 / 5：行数、列长度、去重前唯一性、不含对照。
            # 集合相等但这几项不成立 → invalid candidate，记录后继续下一个候选。
            problems = []
            try:
                n_rows = len(out)
            except Exception:
                n_rows = None
            if n_rows != EXPECTED_STRATEGY_COUNT:
                problems.append("len(out)=%r != %d" % (n_rows, EXPECTED_STRATEGY_COUNT))
            if len(id_list) != EXPECTED_STRATEGY_COUNT:
                problems.append("len(exp_id column)=%d != %d"
                                % (len(id_list), EXPECTED_STRATEGY_COUNT))
            if len(id_list) != len(ids):
                dups = sorted({e for e in id_list if id_list.count(e) > 1})
                problems.append("duplicated exp_id rows: %s" % dups)
            if EXPECTED_CONTROL_EXP_ID in ids:
                problems.append("control row present")
            if problems:
                invalid.append("%s(%s)" % (name, "; ".join(problems)))
                continue

            # 判据 6：反例必须抛错。不通过则**不返回 ok**，继续下一个候选。
            raised = None
            try:
                fn(df_bad.copy())
            except Exception as e:
                raised = e
            if raised is None:
                filter_only.append(name)
                continue
            return ("ok",
                    "闸门由 %s() 实现（名称不构成契约）；已筛选候选: %s"
                    % (name, considered), ids, raised, name)

    detail = ("plot_experiments 中没有任何候选函数同时满足"
              "「9 行 → 恰好 8 个不重复策略行」与「错标 not-applicable 必须抛错」。"
              "已筛选候选: %s" % (considered or "none"))
    if invalid:
        detail += ("；其中 %s 的 exp_id 集合相等但**行数或唯一性不合格**"
                   "（集合会折叠重复行，因此不计为实现）" % invalid)
    if filter_only:
        detail += ("；其中 %s 能过滤但**反例不抛错**（半成品闸门：泄漏时会静默"
                   "通过，因此不计为实现）" % filter_only)
    return "no_gate", detail, None, None, None


# ══════════════════════════════════════════════════════════════════════
# S13 集成验证（R-30）：闸门必须被实际的分析入口调用
#
# 「模块里存在一个正确的过滤函数」与「分析入口真的用了它」是两件事。
# 前者成立而后者不成立时，主效应与交互仍会把共同对照算进均值——
# 而这正是 TASK_003 要消灭的核心缺陷。因此必须做集成验证。
# ══════════════════════════════════════════════════════════════════════

FACTOR_COLUMNS = ("content_factor", "channel_factor", "timing_factor")


AGGREGATION_OPS = ("groupby", "pivot", "pivot_table")


def _pe_call_sequence():
    """从 run_experiments.py 提取 `_pe.<name>(…)` 的**真实调用序列**（R-31）。

    孤立地逐个调用入口会产生两类假象：
      · 参数形状不对 → TypeError，被误记为 entry-error；
      · 上游派生列缺失（例如 `composite` 由前一个入口写入）→ KeyError。
    因此按生产代码的**顺序与数据流**重放：把返回值回填到被赋值的变量上，
    正如 `df_exp = _pe.plot_pareto_frontier(df_exp)` 那样。

    返回 [(name, n_args, assigns_back), ...]，按源码出现顺序（lineno, col）。
    """
    tree = _parse("run_experiments.py")
    if tree is None:
        return None
    assigned_calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            assigned_calls.add(id(node.value))
    seq = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                and fn.value.id == "_pe"):
            continue
        seq.append((getattr(node, "lineno", 0), getattr(node, "col_offset", 0),
                    fn.attr, len(node.args), id(node) in assigned_calls))
    seq.sort()
    return [(name, n_args, assigns) for _, _, name, n_args, assigns in seq]


def _static_aggregation_reachability(rel):
    """静态可达性：从每个模块级函数出发，是否可能到达因子聚合调用（R-31）。

    这是「该入口**不是**因子入口」这一断言的机器证据来源。仅凭「孤立运行时
    没观察到聚合」不足以下这个结论——那只是没触发到，不是不可能触发。

    做法：在模块内建调用图（只跟踪模块级函数间的直接名字调用），
    标记每个函数是否直接含 `.groupby(` / `.pivot(` / `.pivot_table(`，
    然后从入口做 DFS。

    诚实标注其局限：动态派发（`getattr(obj, name)()`、`eval`）无法静态跟踪。
    因此额外记录可达范围内是否出现 `getattr(` —— 出现则该入口的结论标为
    **不可判定**，而不是「已证明非因子入口」。

    返回 {func_name: (reachable_aggregators, has_dynamic_dispatch)} 或 None。
    """
    tree = _parse(rel)
    if tree is None:
        return None
    funcs = {n.name: n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    direct_aggr, callees, dynamic = {}, {}, {}
    for name, node in funcs.items():
        aggr, called, dyn = False, set(), False
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                f = sub.func
                if isinstance(f, ast.Attribute) and f.attr in AGGREGATION_OPS:
                    aggr = True
                if isinstance(f, ast.Name):
                    if f.id in funcs:
                        called.add(f.id)
                    elif f.id == "getattr":
                        dyn = True
        direct_aggr[name] = aggr
        callees[name] = called
        dynamic[name] = dyn

    out = {}
    for entry in funcs:
        seen, stack = set(), [entry]
        aggregators, dyn = [], False
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            if direct_aggr.get(cur):
                aggregators.append(cur)
            if dynamic.get(cur):
                dyn = True
            stack.extend(callees.get(cur, ()))
        out[entry] = (sorted(aggregators), dyn)
    return out


def _verify_gate_integration(candidate_name, rows_good):
    """按**生产调用路径**重放分析编排，给每个入口一个终局判定（R-30 / R-31）。

    重放方式（优先方案）：
      · 把标准 9 行写成临时目录里的 summary.csv，`RESULTS_DIR` / `OUTPUT_DIR`
        指向临时目录，因此 `_pe.load_data()` 也走真实读取路径；
      · 按 `_pe_call_sequence()` 得到的顺序与参数个数依次调用，
        并把返回值回填到被赋值的变量上——与生产的数据流一致，
        上游派生列（如 `composite`）因此存在。
    这消除了「孤立调用导致的 TypeError / KeyError」这类假 entry-error。

    终局判定（正式验收中不允许任何入口停留在中性状态）：
      · factorial-entry-pass —— 观测到因子聚合、candidate 被调用、
        所有聚合输入均为 8 个唯一策略行且不含共同对照；
      · not-factorial-entry —— 运行期未观测到因子聚合，**且**静态可达性证明
        该入口的调用链内不存在 groupby / pivot / pivot_table，
        也不存在 getattr 动态派发；
      · factorial-entry-fail / entry-error / unknown-not-proven —— 全部 FAIL。

    「至少一个入口正确聚合」**不能**代替「所有实际因子入口均正确」：
    两条都是必要条件，前者排除「闸门根本没被用上」，后者排除「有入口绕过闸门」。

    观测手段：临时替换 pandas 的 DataFrame.groupby / pivot / pivot_table，
    用**重入深度守卫**只记录分析代码自己发起的最外层调用（pandas 内部再次
    调用 groupby 不计入），因此记录到的就是「分析入口交给聚合的那张表」。

    返回 (status, per_entry)
        status ∈ {"ok", "unavailable", "no_entries", "problems"}
        per_entry = [dict(name, kind, calls, frames, problems, error, evidence), ...]
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import pandas as pd
    except Exception as e:
        return "unavailable", [{"name": "<import>", "kind": "unavailable", "calls": 0,
                                "frames": 0, "problems": [],
                                "error": "%s: %s" % (type(e).__name__, e)}]
    analysis_dir = os.path.join(project_root, "analysis")
    if analysis_dir not in sys.path:
        sys.path.insert(0, analysis_dir)
    try:
        import plot_experiments as _pe
    except Exception as e:
        return "unavailable", [{"name": "<import>", "kind": "unavailable", "calls": 0,
                                "frames": 0, "problems": [],
                                "error": "%s: %s" % (type(e).__name__, e)}]

    sequence = _pe_call_sequence()
    if not sequence:
        return "no_entries", [{"name": "<none>", "kind": "unknown-not-proven",
                               "calls": 0, "frames": 0, "problems": [], "evidence": "",
                               "error": "无法从 run_experiments.py 提取 _pe.<name>(…) "
                                        "调用序列——分析编排不存在，或调用形式无法"
                                        "静态识别"}]

    reach = _static_aggregation_reachability("analysis/plot_experiments.py") or {}

    # 完整性闸门：run_experiments 引用的每个 _pe 函数都必须出现在调用序列里，
    # 否则说明它以某种本方法捕获不到的形式被调用 → 无法判定，必须暴露。
    attrs = (_attr_names_by_var("run_experiments.py", {"_pe"}) or {}).get("_pe", set())
    referenced_funcs = {a for a in attrs
                        if inspect.isfunction(getattr(_pe, a, None))
                        and getattr(getattr(_pe, a), "__module__", None) == _pe.__name__}
    in_sequence = {name for name, _, _ in sequence}
    uncaptured = sorted(referenced_funcs - in_sequence)

    original = getattr(_pe, candidate_name)
    state = {"calls": 0, "depth": 0, "entry": ""}
    observed = []          # [(entry, op, DataFrame)]

    def counting_gate(*a, **k):
        state["calls"] += 1
        return original(*a, **k)

    orig_groupby = pd.DataFrame.groupby
    orig_pivot = pd.DataFrame.pivot
    orig_pivot_table = pd.DataFrame.pivot_table

    def _record(op, frame):
        # 重入守卫：只记录分析代码自己发起的最外层调用
        if state["depth"] == 0:
            observed.append((state["entry"], op, frame))

    def rec_groupby(self, *a, **k):
        _record("groupby", self)
        state["depth"] += 1
        try:
            return orig_groupby(self, *a, **k)
        finally:
            state["depth"] -= 1

    def rec_pivot(self, *a, **k):
        _record("pivot", self)
        state["depth"] += 1
        try:
            return orig_pivot(self, *a, **k)
        finally:
            state["depth"] -= 1

    def rec_pivot_table(self, *a, **k):
        _record("pivot_table", self)
        state["depth"] += 1
        try:
            return orig_pivot_table(self, *a, **k)
        finally:
            state["depth"] -= 1

    per_entry = [{"name": n, "kind": "unknown-not-proven", "calls": 0, "frames": 0,
                  "problems": [], "evidence": "",
                  "error": "run_experiments.py 引用了该函数，但其调用形式未被调用序列"
                           "捕获，因此既不能证明它做因子聚合、也不能证明它不做"}
                 for n in uncaptured]

    orig_results_dir = getattr(_pe, "RESULTS_DIR", None)
    orig_output_dir = getattr(_pe, "OUTPUT_DIR", None)
    try:
        setattr(_pe, candidate_name, counting_gate)
        pd.DataFrame.groupby = rec_groupby
        pd.DataFrame.pivot = rec_pivot
        pd.DataFrame.pivot_table = rec_pivot_table

        with tempfile.TemporaryDirectory() as td:
            # 让 load_data() 走真实读取路径：把标准 9 行写成 summary.csv
            fig_dir = os.path.join(td, "figures")
            os.makedirs(fig_dir, exist_ok=True)
            standard = pd.DataFrame(rows_good)
            standard.to_csv(os.path.join(td, "summary.csv"), index=False)
            if hasattr(_pe, "RESULTS_DIR"):
                setattr(_pe, "RESULTS_DIR", td)
            if hasattr(_pe, "OUTPUT_DIR"):
                setattr(_pe, "OUTPUT_DIR", fig_dir)

            # 按生产顺序与数据流重放
            threaded = None
            for name, n_args, assigns in sequence:
                fn = getattr(_pe, name, None)
                if not callable(fn):
                    per_entry.append({"name": name, "kind": "unknown-not-proven",
                                      "calls": 0, "frames": 0, "problems": [],
                                      "evidence": "",
                                      "error": "_pe.%s 不是可调用对象" % name})
                    continue

                state["calls"] = 0
                state["entry"] = name
                observed.clear()
                error = ""
                out = None
                base = threaded if threaded is not None else standard
                try:
                    args = () if n_args == 0 else (base.copy(),)
                    out = fn(*args)
                except Exception as e:
                    error = "%s: %s" % (type(e).__name__, e)
                if assigns and isinstance(out, pd.DataFrame):
                    threaded = out

                problems = []
                factor_frames = 0
                for entry_name, op, frame in list(observed):
                    try:
                        cols = list(frame.columns)
                    except Exception:
                        continue
                    # 「因子聚合」的判据：聚合输入含任一因子列。
                    # 完全基于运行期观测，与源码字面量无关。
                    if not any(col in cols for col in FACTOR_COLUMNS):
                        continue
                    factor_frames += 1

                    if len(frame) != EXPECTED_STRATEGY_COUNT:
                        problems.append("%s: len=%d != %d"
                                        % (op, len(frame), EXPECTED_STRATEGY_COUNT))
                    if "exp_id" not in cols:
                        problems.append("%s: aggregation input has factor columns but "
                                        "no exp_id — identity cannot be verified" % op)
                        continue
                    id_list = list(frame["exp_id"])
                    ids = set(id_list)
                    if len(id_list) != EXPECTED_STRATEGY_COUNT:
                        problems.append("%s: exp_id column len=%d != %d"
                                        % (op, len(id_list), EXPECTED_STRATEGY_COUNT))
                    if len(ids) != EXPECTED_STRATEGY_COUNT:
                        problems.append("%s: unique exp_id=%d != %d"
                                        % (op, len(ids), EXPECTED_STRATEGY_COUNT))
                    if ids != set(EXPECTED_STRATEGY_EXP_IDS):
                        problems.append("%s: exp_id set mismatch (%s)"
                                        % (op, sorted(ids, key=_safe_key)[:4]))
                    if EXPECTED_CONTROL_EXP_ID in ids:
                        problems.append("%s: CONTROL ROW LEAKED into aggregation" % op)

                # ── 终局判定 ──
                aggregators, dyn = reach.get(name, (None, True))
                if factor_frames:
                    if state["calls"] == 0:
                        problems.append("performed factor aggregation WITHOUT calling "
                                        "the gate %s()" % candidate_name)
                    kind = ("factorial-entry-pass" if not problems
                            else "factorial-entry-fail")
                    evidence = "runtime: %d factor aggregation(s) observed" % factor_frames
                elif error:
                    kind = "entry-error"
                    evidence = ("replayed in production order with production-shaped "
                                "arguments, yet still raised — this mirrors defect D2 "
                                "(exception swallowed by except ⇒ figure silently missing)")
                elif aggregators is None:
                    kind = "unknown-not-proven"
                    evidence = "static call graph unavailable for this entry"
                elif dyn:
                    kind = "unknown-not-proven"
                    evidence = ("no aggregation observed, but getattr() dynamic dispatch "
                                "is reachable from this entry — cannot statically prove "
                                "it never aggregates")
                elif aggregators:
                    kind = "unknown-not-proven"
                    evidence = ("no aggregation observed at runtime, but %s reachable "
                                "from this entry do call %s — not proven non-factorial"
                                % (aggregators, "/".join(AGGREGATION_OPS)))
                else:
                    kind = "not-factorial-entry"
                    evidence = ("proven: no %s call reachable from this entry in the "
                                "module call graph, and no getattr dynamic dispatch"
                                % "/".join(AGGREGATION_OPS))

                per_entry.append({"name": name, "kind": kind, "calls": state["calls"],
                                  "frames": factor_frames, "problems": problems,
                                  "error": error, "evidence": evidence})
    finally:
        setattr(_pe, candidate_name, original)
        pd.DataFrame.groupby = orig_groupby
        pd.DataFrame.pivot = orig_pivot
        pd.DataFrame.pivot_table = orig_pivot_table
        if orig_results_dir is not None:
            setattr(_pe, "RESULTS_DIR", orig_results_dir)
        if orig_output_dir is not None:
            setattr(_pe, "OUTPUT_DIR", orig_output_dir)

    terminal_ok = {"factorial-entry-pass", "not-factorial-entry"}
    factorial_pass = [e for e in per_entry if e["kind"] == "factorial-entry-pass"]
    all_ok = (bool(factorial_pass)
              and all(e["kind"] in terminal_ok for e in per_entry))
    return ("ok" if all_ok else "problems"), per_entry


def _format_integration_unavailable(per_entry):
    """把 `unavailable` 的 per_entry 记录格式化成一行可读原因（纯函数）。

    `_verify_gate_integration()` 返回的 per_entry 元素是 **dict**，不是 tuple。
    早先这里写成 `e[3]` —— 对 dict 取整数下标会抛 `KeyError: 3`，
    于是在 formal / offline 分档**之前**验收程序就崩掉，
    「依赖不可用」这一分支从来没有真正执行过。

    本函数无副作用，对以下输入一律给出确定字符串，绝不抛异常：
      · 空列表；
      · 缺 error / evidence / name 键的 dict；
      · 非 dict 元素（防御性兜底）。
    """
    if not per_entry:
        return "<no reason reported>"
    reasons = []
    for e in per_entry:
        if isinstance(e, dict):
            reason = (e.get("error")
                      or e.get("evidence")
                      or e.get("name")
                      or "<unknown unavailable reason>")
        else:
            reason = e
        reasons.append(str(reason))
    return "; ".join(reasons)


def check_s13_domain_gate(v, formal):
    """formal=False（--offline-only）：依赖不可用记 WARN。
       formal=True（--runtime-dir）：依赖不可用一律 FAIL——一次不能判定分析口径
       是否正确的验收，不构成验收（design §12.3.4）。"""
    group = "S13-domain-gate"

    good_rows = _nine_condition_rows()
    # 反例：把共同对照错标为策略行（is_control=False 但因子仍是 not-applicable）
    bad_rows = copy.deepcopy(good_rows)
    bad_rows[0]["is_control"] = False

    # ── 判据自证：参考闸门在正例通过、在反例报错 ──
    # 这一步只验证"本项的判据本身是有区分力的"，不对生产实现提任何命名要求。
    try:
        kept = _reference_strategy_rows(good_rows)
        v.check(group, "判据自证 · 正例：参考闸门保留 8 行策略",
                len(kept) == EXPECTED_STRATEGY_COUNT, EXPECTED_STRATEGY_COUNT, len(kept))
    except AssertionError as e:
        v.check(group, "判据自证 · 正例：参考闸门通过", False, "no assertion error", str(e))
    caught = None
    try:
        _reference_strategy_rows(bad_rows)
    except AssertionError as e:
        caught = e
    v.check(group, "判据自证 · 反例：参考闸门必须报错", caught is not None,
            "AssertionError", "no assertion error" if caught is None else "AssertionError",
            "均值污染是静默的，判据必须能捕获它")

    # 判据自证：unavailable 原因格式化必须能真的跑通。
    # 早先这里用 e[3] 对 dict 取下标，会在分档之前抛 KeyError:3 —— 也就是说
    # 「依赖不可用」这条分支从未被执行过。因此把它本身也纳入自证。
    fmt_probe = _format_integration_unavailable(
        [{"name": "<import>", "kind": "unavailable",
          "error": "ImportError: pandas unavailable"}])
    fmt_empty = _format_integration_unavailable([])
    fmt_sparse = _format_integration_unavailable([{"kind": "unavailable"}])
    v.check(group, "判据自证 · unavailable 原因格式化不抛异常且保留原因",
            ("ImportError: pandas unavailable" in fmt_probe
             and fmt_empty == "<no reason reported>"
             and fmt_sparse == "<unknown unavailable reason>"),
            "reason preserved / empty & sparse handled",
            "probe=%r empty=%r sparse=%r" % (fmt_probe, fmt_empty, fmt_sparse),
            "per_entry 元素是 dict，不能用整数下标取值")

    # ── 生产侧功能检查（不限定 helper 名称或内部组织方式）──
    status, detail, ids, raised, candidate = _probe_analysis_gate(good_rows, bad_rows)
    if status == "unavailable":
        if formal:
            v.check(group, "分析入口功能检查", False, "gate verified",
                    "unavailable: " + detail,
                    "正式验收不接受「因依赖缺失而无法判定」：一次不能判定分析口径"
                    "是否正确的验收，不构成验收")
        else:
            v.warn(group, "分析入口功能检查",
                   "跳过（无法判定，离线模式允许）：" + detail
                   + "。正式验收（--runtime-dir）下此情形一律 FAIL")
        return
    v.check(group, "1–2 分析入口把 9 行输入实际过滤为 8 个策略行", status == "ok",
            "gate found", status, detail)
    if status != "ok":
        return
    v.check(group, "3 共同对照不进入主效应与交互计算",
            EXPECTED_CONTROL_EXP_ID not in (ids or set()), "absent",
            "present" if EXPECTED_CONTROL_EXP_ID in (ids or set()) else "absent",
            "对照只参与 any clarification vs common control 这一个对比")
    v.check(group, "1 过滤结果恰为 8 个策略 exp_id", ids == set(EXPECTED_STRATEGY_EXP_IDS),
            sorted(EXPECTED_STRATEGY_EXP_IDS), sorted(ids or []))
    v.check(group, "4 is_control=False 但因子为 not-applicable 时必须抛错",
            raised is not None, "raises",
            "no exception" if raised is None else type(raised).__name__,
            "这是 is_control 过滤失效的唯一可观测信号：泄漏必须响，而不是静默进入均值")

    # ── 集成验证（R-30）：闸门必须被实际的分析入口调用 ──
    #
    # 到这里只证明了「模块里存在一个正确的过滤函数」。若没有任何入口调用它，
    # 主效应与交互照旧把共同对照算进均值——恰恰是本任务要消灭的缺陷。
    int_status, per_entry = _verify_gate_integration(candidate, good_rows)
    if int_status == "unavailable":
        note = _format_integration_unavailable(per_entry)
        if formal:
            v.check(group, "5 闸门集成验证", False, "verified",
                    "unavailable: " + note,
                    "正式验收不接受无法判定「闸门是否被真的调用」")
        else:
            v.warn(group, "5 闸门集成验证",
                   "跳过（无法判定，离线模式允许）：" + note)
        return
    if int_status == "no_entries":
        v.check(group, "5 可提取生产分析调用序列", False,
                "non-empty call sequence", "none", per_entry[0]["error"]
                + "。没有序列意味着主效应 / 交互根本没有实现，或它不被 "
                  "run_experiments.py 调用（D2 类缺陷）")
        return

    factorial_pass = [e for e in per_entry if e["kind"] == "factorial-entry-pass"]

    # ── 规则 1：至少一个入口必须真的做因子聚合并通过 ──
    # 这一条排除「闸门根本没被用上」，但它**不能**代替规则 2。
    v.check(group, "5 至少一个分析入口产生因子聚合且通过", bool(factorial_pass),
            "≥ 1 factorial-entry-pass", "0",
            "终局判定: %s。全都不做因子聚合 ⇒ 主效应 / 交互未实现，"
            "或其实现不被 run_experiments.py 调用"
            % [(e["name"], e["kind"]) for e in per_entry])

    # ── 规则 2：每个入口都必须落在两个合格终局状态之一 ──
    # not-probeable-signature / entry-error / unknown-not-proven 一律 FAIL：
    # 「无法证明它不是因子入口」不得作为中性结论放过（R-31）。
    for e in per_entry:
        kind = e["kind"]
        detail = e["evidence"] or ""
        if e["error"]:
            detail = (detail + "；error=" + e["error"]) if detail else e["error"]
        if e["problems"]:
            detail = (detail + "；" + "; ".join(e["problems"])) if detail else \
                "; ".join(e["problems"])

        if kind == "factorial-entry-pass":
            v.check(group, "5 入口 %s(): factorial-entry-pass" % e["name"], True,
                    "factorial-entry-pass", kind,
                    "调用闸门 %d 次；%d 张因子聚合表全部为 8 个唯一策略行、不含对照"
                    % (e["calls"], e["frames"]))
        elif kind == "not-factorial-entry":
            v.check(group, "5 入口 %s(): not-factorial-entry（已证明）" % e["name"],
                    True, "not-factorial-entry", kind, detail)
        else:
            v.check(group, "5 入口 %s(): 终局判定为 %s" % (e["name"], kind), False,
                    "factorial-entry-pass 或 not-factorial-entry", kind, detail
                    + "。正式验收不允许任何实际调用的入口停留在中性状态："
                      "要么证明它正确聚合，要么证明它不做因子聚合。"
                      "若动态探测无法给出证据，应把过滤函数升级为明确的公共接口"
                      "并让每个因子聚合入口都调用它")


# ══════════════════════════════════════════════════════════════════════
# S14 统计口径：对照不进入 2×2×2 的任何一侧
# ══════════════════════════════════════════════════════════════════════

def check_s14_contrasts(v):
    group = "S14-contrasts"

    v.check(group, "对比表恰 7 个内部对比（3 主效应 + 3 二阶 + 1 三阶）",
            len(CONTRAST_TABLE) == 7, 7, len(CONTRAST_TABLE))

    for name, sides in sorted(CONTRAST_TABLE.items()):
        plus, minus = sides["plus"], sides["minus"]
        v.check(group, "%s: (+) 侧 4 组" % name, len(plus) == 4, 4, sorted(plus))
        v.check(group, "%s: (−) 侧 4 组" % name, len(minus) == 4, 4, sorted(minus))
        v.check(group, "%s: 两侧不相交" % name, not (plus & minus), "disjoint",
                sorted(plus & minus))
        v.check(group, "%s: (+)∪(−) == 8 个策略 exp_id" % name,
                (plus | minus) == set(EXPECTED_STRATEGY_EXP_IDS),
                sorted(EXPECTED_STRATEGY_EXP_IDS), sorted(plus | minus))
        v.check(group, "%s: 不含共同对照" % name,
                EXPECTED_CONTROL_EXP_ID not in (plus | minus), "absent",
                "present" if EXPECTED_CONTROL_EXP_ID in (plus | minus) else "absent",
                "共同对照不是第三个 timing 水平，也不是 content/channel 的缺失单元")

    # 正交性：7 个对照向量两两正交（这是"平衡完全交叉"的可机器判定表述）
    ordered = sorted(EXPECTED_STRATEGY_EXP_IDS)
    vectors = {}
    for name, sides in CONTRAST_TABLE.items():
        vectors[name] = [1 if eid in sides["plus"] else -1 for eid in ordered]
    for name, vec in sorted(vectors.items()):
        v.check(group, "%s: 系数和为 0（对照向量合法）" % name, sum(vec) == 0, 0, sum(vec))
    names = sorted(vectors)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            dot = sum(x * y for x, y in zip(vectors[a], vectors[b]))
            v.check(group, "正交性 %s ⟂ %s" % (a, b), dot == 0, 0, dot,
                    "非正交意味着效应估计互相混淆")

    # 对比一：唯一涉及对照的对比
    v.check(group, "对比一处理侧 == 8 个策略 exp_id",
            CONTRAST_ANY_VS_CONTROL["plus"] == set(EXPECTED_STRATEGY_EXP_IDS),
            sorted(EXPECTED_STRATEGY_EXP_IDS),
            sorted(CONTRAST_ANY_VS_CONTROL["plus"]))
    v.check(group, "对比一对照侧恰为 {NoClarification-Control}",
            CONTRAST_ANY_VS_CONTROL["minus"] == {EXPECTED_CONTROL_EXP_ID},
            {EXPECTED_CONTROL_EXP_ID}, sorted(CONTRAST_ANY_VS_CONTROL["minus"]))

    # n=1 时残差自由度为 0：这不是缺陷，但必须被显式记录，避免论文误报 p 值
    n_obs = EXPECTED_STRATEGY_COUNT
    n_params = 1 + 3 + 3 + 1
    v.warn(group, "n=1 下残差自由度为 0（诚实标注）",
           "8 个策略观测 vs 饱和模型 8 个参数 ⇒ 残差 df = %d；对比 2–8 全部只是"
           "点估计，任何显著性检验都不成立。最低推荐 n=3（design §6.4）"
           % (n_obs - n_params))


# ══════════════════════════════════════════════════════════════════════
# 运行期产物（S15 / S16）
#
# 目录只来自显式的 --runtime-dir，**没有任何自动发现或回退逻辑**：
#   · --offline-only 缺目录        → WARN（尚未产出证据）
#   · --runtime-dir 缺目录/版本不符/产物不全 → FAIL（证据不成立）
# 两者是不同的事，用运行模式区分，而不是用同一档结论掩盖。
# ══════════════════════════════════════════════════════════════════════


def _load_run_metadata(run_dir):
    path = os.path.join(run_dir, "run_metadata.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


REQUIRED_RUN_ARTIFACTS = (
    "summary.csv", "trajectories.csv", "agent_records.csv", "target_nodes.csv",
    "experiment_metadata.jsonl", "run_metadata.json",
    "network_nodes.csv", "network_edges.csv",
)


def validate_runtime_dir(path):
    """校验 --runtime-dir 指向的目录是否可用作正式验收依据（裁定五 / 裁定六）。

    **绝不做任何自动发现或回退**：不扫描 results/experiments，不读 latest/。
    目录必须由调用者显式给出，且必须是 matrix_version == "3.0" 且
    condition_count == 9 的运行目录。

    返回 (found, problems)
        found = (目录名, 绝对路径, run_metadata dict) 或 None
        problems = 字符串列表，非空即表示该目录不可用于正式验收
    """
    problems = []
    if not path:
        return None, ["未提供运行目录"]
    run_dir = os.path.abspath(path)
    if not os.path.isdir(run_dir):
        return None, ["目录不存在: " + run_dir]

    meta = _load_run_metadata(run_dir)
    if not isinstance(meta, dict):
        return None, ["run_metadata.json 缺失或不可解析: " + run_dir]

    block = meta.get("experiment_matrix")
    if not isinstance(block, dict):
        problems.append("run_metadata 缺少 experiment_matrix 块 → 按 §11.1 判为 legacy，"
                        "不得用于 v3.0 正式验收")
    else:
        if block.get("matrix_version") != EXPECTED_MATRIX_VERSION:
            problems.append("matrix_version = %r，要求 %r"
                            % (block.get("matrix_version"), EXPECTED_MATRIX_VERSION))
        if block.get("condition_count") != EXPECTED_CONDITION_COUNT:
            problems.append("condition_count = %r，要求 %d"
                            % (block.get("condition_count"), EXPECTED_CONDITION_COUNT))

    missing = [n for n in REQUIRED_RUN_ARTIFACTS
               if not os.path.isfile(os.path.join(run_dir, n))]
    if missing:
        problems.append("缺少端到端产物: " + ", ".join(missing))

    if problems:
        return None, problems
    return (os.path.basename(run_dir.rstrip(os.sep)), run_dir, meta), []


def _read_agent_records(run_dir):
    path = os.path.join(run_dir, "agent_records.csv")
    if not os.path.isfile(path):
        return None
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_network_agent_ids(run_dir):
    """run 级 network_nodes.csv 的 agent_id 集合。

    它是「本次 run 到底有哪些 Agent」的权威来源（run 级静态文件，9 个条件共用
    同一张网络，由 verify_single_network() 保证）。用它构造预期键空间，
    而不是从 agent_records 自身推断——否则「整个 Agent 的记录全部缺失」
    这种情形会因为期望值也跟着缺失而永远无法被发现。
    """
    path = os.path.join(run_dir, "network_nodes.csv")
    if not os.path.isfile(path):
        return None
    with open(path, newline="", encoding="utf-8") as f:
        return {row.get("agent_id") for row in csv.DictReader(f)}


def _safe_key(item):
    """排序用的安全 key：把 None 与非字符串统一转成字符串。

    畸形 CSV（缺列 → None）在 sorted() 里混入 None 会抛
    TypeError: '<' not supported between 'NoneType' and 'str'，
    那会让整份验收报告在写盘之前崩掉——判据反而变成了新的失效点。
    """
    if isinstance(item, tuple):
        return tuple("" if x is None else str(x) for x in item)
    return "" if item is None else str(item)


# ══════════════════════════════════════════════════════════════════════
# S15 逐 Agent 处理前路径对齐（主要证据）
# ══════════════════════════════════════════════════════════════════════

def check_s15_pre_treatment_alignment(v, found, strict, skip_reason=""):
    group = "S15-pre-treatment-alignment"
    if found is None:
        note = ("无可用的 v3.0 运行目录：%s。miss_count == 0 与本项通过必须同时成立，"
                "才算对齐前提被证实" % (skip_reason or "未提供 --runtime-dir"))
        if strict:
            v.check(group, "逐 Agent 处理前路径对齐（运行期）", False,
                    "valid v3.0 run dir", "unavailable", note)
        else:
            v.warn(group, "逐 Agent 处理前路径对齐（运行期）", "跳过（离线模式）：" + note)
        return
    run_name, run_dir, meta = found

    records = _read_agent_records(run_dir)
    if records is None:
        v.error(group, "agent_records.csv 可读", "文件不存在于 " + run_name)
        return

    # ── 键唯一性（fail-closed）：绝不用 table[key] = value 静默覆盖重复行 ──
    #
    # 直接赋值会让"同一 (exp_id, tick, agent_id) 出现两行"这种产物缺陷完全隐形：
    # 后写入者胜出，比较照样通过。而重复行恰恰是最危险的情形之一——它意味着
    # 主循环或写盘路径重复结算了某个 Agent。因此先统计每个键的出现次数，
    # 任何 count != 1 立即 FAIL。这一项**不可**用 S16 的总行数断言替代：
    # 行数正确而键重复（配套某个键缺失）是完全可能的。
    key_counts = {}
    key_to_rows = {}
    for idx, row in enumerate(records):
        key = (row.get("exp_id"), row.get("tick"), row.get("agent_id"))
        key_counts[key] = key_counts.get(key, 0) + 1
        key_to_rows.setdefault(key, []).append(idx)

    dup_keys = sorted((k for k, n in key_counts.items() if n > 1), key=_safe_key)
    v.check(group, "agent_records 每个 (exp_id, tick, agent_id) 恰好出现 1 次",
            not dup_keys, "all counts == 1",
            "duplicated=%d | %s" % (len(dup_keys),
                                    "; ".join("%s×%d@rows%s"
                                              % (k, key_counts[k], key_to_rows[k][:4])
                                              for k in dup_keys[:3])),
            "重复键意味着某个 Agent 被重复结算；静默覆盖会让该缺陷完全隐形")

    # ── 绝对预期键空间（R-27）──
    #
    # 上面的重复检查只能发现 count > 1。**count == 0 需要一个独立于实际数据的
    # 期望集合才能发现**：如果某个 Agent 或某个 Tick 的记录整体缺失，仅从
    # agent_records 自身推断期望，期望也会跟着缺失，缺失就永远不可见。
    # 因此期望键空间由三个外部来源的笛卡尔积构造：
    #   · 9 个 exp_id            ← EXPECTED_EXP_IDS（测试自带的独立期望）
    #   · Tick 1..total_ticks    ← run_metadata 的 config.total_ticks
    #   · agent_id               ← network_nodes.csv（run 级静态文件）
    exps = meta.get("experiments") or []
    cfg0 = (exps[0].get("config") or {}) if exps else {}
    total_ticks = cfg0.get("total_ticks")
    num_agents = cfg0.get("num_agents")
    network_agent_ids = _read_network_agent_ids(run_dir)

    space_ok = True
    if not isinstance(total_ticks, int) or not isinstance(num_agents, int):
        v.check(group, "run_metadata 提供 total_ticks / num_agents", False,
                "int, int", "%r, %r" % (total_ticks, num_agents),
                "无此二者无法构造绝对预期键空间")
        space_ok = False
    if network_agent_ids is None:
        v.check(group, "network_nodes.csv 可读（预期键空间的 agent_id 来源）", False,
                "readable", "MISSING")
        space_ok = False

    if space_ok:
        v.check(group, "network_nodes.csv 的 agent_id 数量 == num_agents",
                len(network_agent_ids) == num_agents, num_agents,
                len(network_agent_ids),
                "run 级网络是 9 个条件共用的唯一一张图")

        expected_keys = {
            (exp_id, str(tick), agent_id)
            for exp_id in EXPECTED_EXP_IDS
            for tick in range(1, total_ticks + 1)
            for agent_id in network_agent_ids
        }
        actual_keys = set(key_counts)
        missing_keys = sorted(expected_keys - actual_keys, key=_safe_key)
        extra_keys = sorted(actual_keys - expected_keys, key=_safe_key)
        zero_count = [k for k in expected_keys if key_counts.get(k, 0) == 0]

        v.check(group, "actual_keys == expected_keys（9 exp_id × %s Tick × %s Agent）"
                % (total_ticks, num_agents),
                actual_keys == expected_keys,
                "%d keys" % len(expected_keys),
                "actual=%d missing=%d extra=%d"
                % (len(actual_keys), len(missing_keys), len(extra_keys)))
        v.check(group, "无缺失键（missing_keys 为空）", not missing_keys, "none",
                "%d | %s" % (len(missing_keys), missing_keys[:5]),
                "count == 0 只能靠绝对期望集合发现，无法从实际数据自身推断")
        v.check(group, "无额外键（extra_keys 为空）", not extra_keys, "none",
                "%d | %s" % (len(extra_keys), extra_keys[:5]))
        v.check(group, "每个 expected_key 的出现次数恰为 1", not zero_count and not dup_keys,
                "all == 1",
                "zero=%d duplicated=%d" % (len(zero_count), len(dup_keys)))
        if not (actual_keys == expected_keys and not dup_keys):
            v.check(group, "键空间成立后才进行逐值比较", False,
                    "exact key space", "key space violated",
                    "拒绝在键空间不完整或不唯一的数据上给出\"对齐通过\"的结论")
            return

    if dup_keys or not space_ok:
        # 键不唯一或键空间不可判定时，后续逐值比较的结论没有意义（fail-closed）
        v.check(group, "键空间成立后才进行逐值比较", False,
                "exact key space", "duplicated keys or undetermined key space",
                "拒绝在键不唯一 / 键空间不可判定的数据上给出\"对齐通过\"的结论")
        return

    table = {k: {f: records[key_to_rows[k][0]].get(f) for f in COMPARED_FIELDS}
             for k in key_counts}

    exp_ids = {row.get("exp_id") for row in records}
    v.check(group, "agent_records 覆盖 9 个 exp_id", exp_ids == set(EXPECTED_EXP_IDS),
            sorted(EXPECTED_EXP_IDS), sorted(exp_ids, key=_safe_key))

    ctl_keys = {(t, a) for (e, t, a) in table if e == EXPECTED_CONTROL_EXP_ID}
    if not ctl_keys:
        v.error(group, "共同对照记录存在", "agent_records 中没有 " + EXPECTED_CONTROL_EXP_ID)
        return

    # ── 第二层比较：策略组与共同对照的处理前窗口 ──
    #
    # 保留原有判据，但它是**第二层**：绝对键空间检查（上方 R-27）已经确认
    # 「9 × total_ticks × num_agents 个键一个不多一个不少、每个恰好一行」。
    # 本层只回答「处理前区间内策略组与对照是否逐值相同」，
    # **不能代替**绝对键空间检查——它的期望值来自对照侧的实际数据，
    # 若对照与策略同时缺同一个 Agent，本层是看不出来的。
    for exp_id in sorted(EXPECTED_STRATEGY_EXP_IDS):
        until = EXPECTED_REPLAY_UNTIL[exp_id]        # 处理前范围 = Tick 1 .. until-1
        ticks = [str(t) for t in range(1, until)]
        window = "Tick 1–%d" % (until - 1)

        # 判据 1：键集合完全相等（同时覆盖判据 2「无缺失」与 3「无额外」）
        ctl_window = {(t, a) for (t, a) in ctl_keys if t in ticks}
        stg_window = {(t, a) for (e, t, a) in table if e == exp_id and t in ticks}
        missing_agents = sorted(ctl_window - stg_window, key=_safe_key)
        extra_agents = sorted(stg_window - ctl_window, key=_safe_key)
        v.check(group, "%s 处理前键集合与对照完全相等（%s）" % (exp_id, window),
                ctl_window == stg_window, "%d keys equal" % len(ctl_window),
                "missing=%d extra=%d | -%s +%s"
                % (len(missing_agents), len(extra_agents),
                   missing_agents[:3], extra_agents[:3]),
                "判据 1/2/3：集合相等即同时排除缺失 Agent 与额外 Agent")
        v.check(group, "%s 处理前每个 Tick 的 Agent 集合与对照一致（%s）"
                % (exp_id, window),
                all({a for (t, a) in ctl_window if t == tk}
                    == {a for (t, a) in stg_window if t == tk} for tk in ticks),
                "per-tick agent sets equal",
                sorted((tk for tk in ticks
                        if {a for (t, a) in ctl_window if t == tk}
                        != {a for (t, a) in stg_window if t == tk}), key=_safe_key))
        if not ctl_window:
            v.check(group, "%s 处理前区间对照侧非空（%s）" % (exp_id, window), False,
                    "non-empty", "0 control rows in window",
                    "对照缺少该区间的记录，无法作为反事实前缀")
            continue

        # 判据 4：区间内每键恰好一行（此处必然成立，作为显式登记保留）
        counts_ok = all(key_counts.get((exp_id, t, a)) == 1 for (t, a) in stg_window) \
            and all(key_counts.get((EXPECTED_CONTROL_EXP_ID, t, a)) == 1
                    for (t, a) in ctl_window)
        v.check(group, "%s 处理前区间内每键恰好一行（%s）" % (exp_id, window),
                counts_ok, "all == 1", "some != 1")

        # 判据 5：5 个字段逐字相等（容差 0）
        diffs = []
        for (tick, agent) in sorted(ctl_window & stg_window, key=_safe_key):
            ck = (EXPECTED_CONTROL_EXP_ID, tick, agent)
            sk = (exp_id, tick, agent)
            for field in COMPARED_FIELDS:
                if table[ck][field] != table[sk][field]:
                    diffs.append("tick=%s agent=%s %s: %r != %r"
                                 % (tick, agent, field,
                                    table[ck][field], table[sk][field]))
        v.check(group, "%s 处理前 5 个字段逐字相等（%s）" % (exp_id, window),
                not diffs, "0 diff",
                "diffs=%d | %s" % (len(diffs), "; ".join(diffs[:3])),
                "容差 0。键碰撞返回他人响应只能由本项捕获（miss_count 对它无效）")

    # 明确不比较的 4 个字段：它们按设计本就应当不同
    v.warn(group, "明确排除的字段",
           "不比较 %s —— 按设计本就应当不同，比较即必然失败"
           % ", ".join(S15_EXCLUDED_FIELDS))

    # ── 汇总检查（降级项，不得作为唯一证据）──
    traj_path = os.path.join(run_dir, "trajectories.csv")
    if not os.path.isfile(traj_path):
        v.warn(group, "trajectories.csv 汇总检查", "跳过：文件不存在")
        return
    with open(traj_path, newline="", encoding="utf-8") as f:
        traj = list(csv.DictReader(f))
    by_exp = {}
    for row in traj:
        by_exp.setdefault(row.get("exp_id"), {})[row.get("tick")] = row.get("avg_trust")

    def _avg_equal(exp_ids_subset, upto):
        series = []
        for eid in exp_ids_subset:
            series.append(tuple(by_exp.get(eid, {}).get(str(t)) for t in range(1, upto)))
        return len(set(series)) == 1 and all(x is not None for x in series[0])

    v.check(group, "汇总：9 个 exp_id 的 avg_trust[1..5] 逐值相等",
            _avg_equal(sorted(EXPECTED_EXP_IDS), EXPECTED_IMMEDIATE_TICK),
            "identical", "differs",
            "降级项：均值相等可以掩盖个体互换，不得作为唯一证据（design §8.6）")
    delayed_set = sorted([EXPECTED_CONTROL_EXP_ID]
                         + [e for e in EXPECTED_STRATEGY_EXP_IDS if e.endswith("Delayed")])
    v.check(group, "汇总：对照与 4 个 Delayed 组的 avg_trust[1..9] 逐值相等",
            _avg_equal(delayed_set, EXPECTED_DELAYED_TICK),
            "identical", "differs", "降级项")


# ══════════════════════════════════════════════════════════════════════
# S16 运行期产物契约
# ══════════════════════════════════════════════════════════════════════

def check_s16_runtime_artifacts(v, found, strict, skip_reason=""):
    group = "S16-runtime-artifacts"
    if found is None:
        note = ("无可用的 v3.0 运行目录：%s。须复核 experiment_matrix 块、"
                "experiment_metadata.jsonl 的 9 行 18 键、target_nodes.csv 不含对照"
                % (skip_reason or "未提供 --runtime-dir"))
        if strict:
            v.check(group, "运行期产物契约", False,
                    "valid v3.0 run dir", "unavailable", note)
        else:
            v.warn(group, "运行期产物契约", "跳过（离线模式）：" + note)
        return
    run_name, run_dir, meta = found
    block = meta.get("experiment_matrix", {}) or {}

    # ── 端到端来源校验（裁定六）：证明这是一次真实跑完的 run，而非手工拼接的 CSV ──
    for name in REQUIRED_RUN_ARTIFACTS:
        v.check(group, "端到端产物存在: " + name,
                os.path.isfile(os.path.join(run_dir, name)), "present", "MISSING")
    legacy, why = is_legacy_run(meta)
    v.check(group, "正式验收目录不得判为 legacy", legacy is False, False,
            "%s (%s)" % (legacy, why),
            "历史 12 条件目录一律不得用作 v3.0 验收依据")
    exps = meta.get("experiments") or []
    v.check(group, "run_metadata.experiments 恰 9 条", len(exps) == EXPECTED_CONDITION_COUNT,
            EXPECTED_CONDITION_COUNT, len(exps))
    v.check(group, "9 个实验全部 status == ok",
            bool(exps) and all(e.get("status") == "ok" for e in exps), "all ok",
            sorted({e.get("status") for e in exps}))
    for key in ("source_file_hashes", "prompt_sources", "persona_sources",
                "clarification_templates", "llm", "network_consistency"):
        v.check(group, "run_metadata 含 %s（由生产写入函数产出）" % key,
                key in meta, "present", "absent" if key not in meta else "present",
                "这些块只可能由 write_run_metadata_json 生成，手工拼接的产物不会有")
    v.check(group, "network_consistency.status == consistent",
            (meta.get("network_consistency", {}) or {}).get("status") == "consistent",
            "consistent", (meta.get("network_consistency", {}) or {}).get("status"))
    v.check(group, "effective_event_ticks_union == [5]（单一丑闻事件）",
            meta.get("effective_event_ticks_union") == [EXPECTED_SCANDAL_TICK],
            [EXPECTED_SCANDAL_TICK], meta.get("effective_event_ticks_union"),
            "从运行期快照聚合，绝不从 ENTERPRISE_STRATEGY 重建")
    if exps:
        cfg0 = (exps[0].get("config") or {})
        n_agents = cfg0.get("num_agents")
        n_ticks = cfg0.get("total_ticks")
        if isinstance(n_agents, int) and isinstance(n_ticks, int):
            expected_rows = n_agents * n_ticks
            bad = sorted(e.get("exp_id") for e in exps
                         if e.get("agent_record_count") != expected_rows)
            v.check(group, "每个实验的 agent_record_count == num_agents × total_ticks (%d)"
                    % expected_rows, not bad, "all equal", bad,
                    "行数完整是\"真的跑完\"的必要条件；手工拼接极难满足")

    v.check(group, 'run_metadata 含 experiment_matrix 块', bool(block), "present",
            "absent" if not block else "present")
    for key, expected in (("matrix_version", EXPECTED_MATRIX_VERSION),
                          ("condition_count", EXPECTED_CONDITION_COUNT),
                          ("strategy_condition_count", EXPECTED_STRATEGY_COUNT),
                          ("control_condition_count", EXPECTED_CONTROL_COUNT),
                          ("control_exp_id", EXPECTED_CONTROL_EXP_ID),
                          ("control_timing", EXPECTED_CONTROL_TIMING),
                          ("not_applicable_value", EXPECTED_NOT_APPLICABLE),
                          ("immediate_offset_ticks", EXPECTED_IMMEDIATE_OFFSET),
                          ("delayed_offset_ticks", EXPECTED_DELAYED_OFFSET),
                          ("recording_exp_id", EXPECTED_CONTROL_EXP_ID),
                          ("divergent_recording_enabled", False)):
        v.check(group, "experiment_matrix.%s" % key, block.get(key) == expected,
                expected, repr(block.get(key)))
    v.check(group, "experiment_matrix.replay_until_by_exp_id 与设计一致",
            block.get("replay_until_by_exp_id") == EXPECTED_REPLAY_UNTIL,
            EXPECTED_REPLAY_UNTIL, block.get("replay_until_by_exp_id"))
    v.check(group, "experiment_matrix.replay_alignment_violated is False",
            block.get("replay_alignment_violated") is False, False,
            repr(block.get("replay_alignment_violated")),
            "为 True 时该批次存在 Replay 对齐违约，S15 / S16 一并判 FAIL")
    v.check(group, "experiment_matrix.replay_miss_by_exp_id 为空",
            block.get("replay_miss_by_exp_id") in ({}, None) or not block.get(
                "replay_miss_by_exp_id"),
            "{}", block.get("replay_miss_by_exp_id"))

    # experiment_metadata.jsonl：恰 9 行、18 键
    meta_path = os.path.join(run_dir, "experiment_metadata.jsonl")
    if not os.path.isfile(meta_path):
        v.error(group, "experiment_metadata.jsonl 存在", "文件不存在于 " + run_name)
    else:
        rows = [json.loads(ln) for ln in open(meta_path, encoding="utf-8") if ln.strip()]
        v.check(group, "experiment_metadata.jsonl 恰 9 行",
                len(rows) == EXPECTED_CONDITION_COUNT, EXPECTED_CONDITION_COUNT, len(rows))
        for row in rows:
            v.check(group, "18 键: " + row.get("exp_id", "?"),
                    len(row) == EXPECTED_EXPERIMENT_METADATA_FIELD_COUNT,
                    EXPECTED_EXPERIMENT_METADATA_FIELD_COUNT, len(row))
        ctl = next((r for r in rows if r.get("exp_id") == EXPECTED_CONTROL_EXP_ID), None)
        if ctl is None:
            v.error(group, "对照行存在", "experiment_metadata.jsonl 中缺 "
                    + EXPECTED_CONTROL_EXP_ID)
        else:
            v.check(group, '对照行 clarification_tick == ""',
                    ctl.get("clarification_tick") == "", '""',
                    repr(ctl.get("clarification_tick")))
            v.check(group, '对照行 replay_miss_count == ""（录制组不适用）',
                    ctl.get("replay_miss_count") == "", '""',
                    repr(ctl.get("replay_miss_count")))
            v.check(group, '对照行 router_role == "recording"',
                    ctl.get("router_role") == "recording", "recording",
                    repr(ctl.get("router_role")))
            v.check(group, "对照行 budget_k == 0", ctl.get("budget_k") == 0, 0,
                    repr(ctl.get("budget_k")))
        for row in [r for r in rows if r.get("exp_id") in EXPECTED_STRATEGY_EXP_IDS]:
            v.check(group, "策略行 replay_miss_count == 0: " + row.get("exp_id", "?"),
                    row.get("replay_miss_count") == 0
                    and isinstance(row.get("replay_miss_count"), int),
                    0, repr(row.get("replay_miss_count")),
                    "fail-closed 之下非 0 意味着该实验已作废")

    # target_nodes.csv 不得含对照（对照不投放，无目标节点）
    tn_path = os.path.join(run_dir, "target_nodes.csv")
    if not os.path.isfile(tn_path):
        v.warn(group, "target_nodes.csv 检查", "跳过：文件不存在")
    else:
        with open(tn_path, newline="", encoding="utf-8") as f:
            tn_rows = list(csv.DictReader(f))
        offenders = sorted({r.get("exp_id") for r in tn_rows
                            if r.get("exp_id") == EXPECTED_CONTROL_EXP_ID})
        v.check(group, "target_nodes.csv 不含共同对照 exp_id", not offenders, "absent",
                offenders, "对照跳过选点，因此 not-applicable 永不出现在该文件")

    # summary.csv 的 is_control 列
    sm_path = os.path.join(run_dir, "summary.csv")
    if os.path.isfile(sm_path):
        with open(sm_path, newline="", encoding="utf-8") as f:
            sm_rows = list(csv.reader(f))
        header = sm_rows[0] if sm_rows else []
        v.check(group, "summary.csv 含 is_control 列", "is_control" in header, "present",
                "absent" if "is_control" not in header else "present")
        v.check(group, "summary.csv 各行格数等于表头",
                all(len(r) == len(header) for r in sm_rows[1:]),
                "all equal", sorted({len(r) for r in sm_rows[1:]}))

    # ── 批次退出码：机器可读，不再依赖"人工观察进程退出码"──
    #
    # 第 3 版把这一项写成 WARN，实际上等于没有验收：产物齐备但批次以退出码 4
    # 结束（存在 Replay 对齐违约）时，报告仍会显示"通过"。因此改为要求
    # run_metadata.json 自带两个字段，由本项直接断言。
    # 语义（design §12.5.1）：0 = 正常完成，3 = 网络一致性失败，4 = Replay 对齐失败。
    v.check(group, "run_metadata 含 batch_exit_code 字段",
            "batch_exit_code" in meta, "present",
            "absent" if "batch_exit_code" not in meta else "present",
            "退出码必须机器可读；靠人工观察进程退出码等于没有验收")
    v.check(group, "run_metadata 含 run_completed 字段",
            "run_completed" in meta, "present",
            "absent" if "run_completed" not in meta else "present")
    v.check(group, "batch_exit_code == 0（正常完成）",
            meta.get("batch_exit_code") == 0, 0, repr(meta.get("batch_exit_code")),
            "3 = 网络一致性违约；4 = Replay 对齐违约。非 0 时本项与 S15 一并 FAIL")
    v.check(group, "run_completed is True",
            meta.get("run_completed") is True, True, repr(meta.get("run_completed")),
            "区分\"跑完了\"与\"中途异常退出但产物已部分落盘\"")
    if meta.get("batch_exit_code") == 4:
        v.check(group, "batch_exit_code == 4 时存在 Replay 对齐违约", False,
                "no violation", "exit code 4",
                "该批次至少一组实验的澄清前路径对齐前提已被打破，全批次不可用")


# ══════════════════════════════════════════════════════════════════════
# S17 legacy 闸门（双向用例）
# ══════════════════════════════════════════════════════════════════════

def is_legacy_run(meta):
    """design §11.1 的三条判定规则，任一命中即 legacy。"""
    if not isinstance(meta, dict):
        return True, "run_metadata 不可读"
    block = meta.get("experiment_matrix")
    if not isinstance(block, dict):
        return True, "缺少 experiment_matrix 键"
    if block.get("matrix_version") != EXPECTED_MATRIX_VERSION:
        return True, "matrix_version != %r" % EXPECTED_MATRIX_VERSION
    if block.get("condition_count") != EXPECTED_CONDITION_COUNT:
        return True, "condition_count != %d" % EXPECTED_CONDITION_COUNT
    return False, "v3.0"


def check_s17_legacy_gate(v):
    group = "S17-legacy-gate"

    v3_block = {
        "matrix_version": EXPECTED_MATRIX_VERSION,
        "condition_count": EXPECTED_CONDITION_COUNT,
        "strategy_condition_count": EXPECTED_STRATEGY_COUNT,
        "control_condition_count": EXPECTED_CONTROL_COUNT,
        "control_exp_id": EXPECTED_CONTROL_EXP_ID,
        "not_applicable_value": EXPECTED_NOT_APPLICABLE,
    }
    legacy, why = is_legacy_run({"experiment_matrix": v3_block})
    v.check(group, "正例：v3.0 run 不判 legacy", legacy is False, False,
            "%s (%s)" % (legacy, why))

    legacy, why = is_legacy_run({"schema_version": "2.0"})
    v.check(group, "反例一：缺 experiment_matrix 键 → legacy", legacy is True, True,
            "%s (%s)" % (legacy, why),
            "与 TASK_002 用\"缺少 schema_version 列\"判定 v1.0 是同一手法")

    bad = dict(v3_block, condition_count=12)
    legacy, why = is_legacy_run({"experiment_matrix": bad})
    v.check(group, "反例二：matrix_version 3.0 但 condition_count 12 → legacy",
            legacy is True, True, "%s (%s)" % (legacy, why))

    bad = dict(v3_block, matrix_version="1.0")
    legacy, why = is_legacy_run({"experiment_matrix": bad})
    v.check(group, "反例三：matrix_version != 3.0 → legacy", legacy is True, True,
            "%s (%s)" % (legacy, why))

    # 行级辅助信号（用于已丢失 run_metadata.json 的目录，design §11.2）
    legacy_headers = ["exp_id", "content_factor", "channel_factor", "timing_factor"]
    v.check(group, "行级信号：summary.csv 缺 is_control 列 → legacy",
            "is_control" not in legacy_headers, True,
            "is_control" not in legacy_headers)
    legacy_rows = [{"exp_id": "Rational-Hub-D3", "timing_factor": "delay-3"},
                   {"exp_id": "Rational-Hub-NoClr", "timing_factor": "no-clarification"},
                   {"exp_id": "Empathy-Random-NoClr", "timing_factor": "no-clarification"}]
    v.check(group, "行级信号：出现 delay-3 → legacy",
            any(r["timing_factor"] in LEGACY_TIMING_LABELS for r in legacy_rows),
            True, True)
    v.check(group, "行级信号：多于 1 行 no-clarification → legacy",
            sum(1 for r in legacy_rows
                if r["timing_factor"] == EXPECTED_CONTROL_TIMING) > 1, True, True,
            "v3.0 的唯一对照只可能有 1 行")
    v.check(group, "行级信号：exp_id 使用废弃缩写词元 → legacy",
            any(r["exp_id"].endswith(s) for r in legacy_rows
                for s in LEGACY_ID_TOKEN_SUFFIXES), True, True)
    v.check(group, "新旧 exp_id 集合交集为空",
            not (EXPECTED_EXP_IDS & {r["exp_id"] for r in legacy_rows}), "empty",
            sorted(EXPECTED_EXP_IDS & {r["exp_id"] for r in legacy_rows}),
            "裁定四改用完整词后，行级信号不再有\"新旧同名\"盲区")

    # 生产侧：分析 loader 必须真的实现版本闸门
    src = _read_source("analysis/plot_experiments.py") or ""
    v.check(group, "analysis loader 引用 experiment_matrix 版本闸门",
            "experiment_matrix" in src and "matrix_version" in src, "present",
            "absent",
            "判为 legacy 时必须拒绝与 v3.0 数据同框，而不是静默拼接（design §11.3）")


# ══════════════════════════════════════════════════════════════════════
# S18 契约承接登记 + TASK_002 冻结校验 + pre-TASK_003 行为不变性
# ══════════════════════════════════════════════════════════════════════

async def check_s18_handover_and_invariance(v, formal):
    """formal=False（--offline-only）：fixture 不存在或不可读记 WARN。
       formal=True（--runtime-dir）：以下任一不成立均 FAIL——
         · fixture 存在且可读；
         · test_harness_sha256 匹配；
         · generated_from_commit 有效且为 HEAD 祖先；
         · git_is_dirty 为 bool；
         · compared_fields 匹配；
         · baseline_file_sha256 的三个 Agent 插件哈希与当前文件一致（R-28）；
         · TASK_002 冻结哈希匹配；
         · 行为轨迹零差异。
       理由：正式验收若允许"没有基线"通过，行为不变性就完全没有被验证过。"""
    group = "S18-handover-invariance"
    diffs = []

    # ── ① 7 项 TASK_002 契约的归属登记：每项必须真的有断言被执行过 ──
    executed = " || ".join("%s %s" % (i["assertion"], i["note"]) for i in v.items)
    for cid, desc in sorted(TASK002_CONTRACT_ITEMS.items()):
        v.check(group, "① 契约 %s 已由本测试承接: %s" % (cid, desc),
                ("contract=" + cid) in executed, "covered",
                "NOT COVERED" if ("contract=" + cid) not in executed else "covered",
                "design §10.2.3：不允许覆盖率净损失")

    # ── ④ TASK_002 工具冻结校验（先做：不依赖 TASK_003 fixture 是否已生成）──
    t002_test_path = _abs(TASK002_TEST_REL)
    t002_fixture_path = _abs(TASK002_FIXTURE_REL)
    t002_fixture = None
    if os.path.isfile(t002_fixture_path):
        try:
            with open(t002_fixture_path, encoding="utf-8") as f:
                t002_fixture = json.load(f)
        except Exception as e:
            v.error(group, "④ TASK_002 fixture 可读", "%s: %s" % (type(e).__name__, e))
    else:
        v.error(group, "④ TASK_002 fixture 存在", "文件不存在: " + TASK002_FIXTURE_REL)

    if isinstance(t002_fixture, dict):
        recorded = t002_fixture.get("test_harness_sha256")
        actual = _sha256_file(t002_test_path)
        v.check(group, "④ TASK_002 测试文件未被改动（哈希与其 fixture 记录一致）",
                _is_hex64(recorded) and actual == recorded,
                recorded, actual,
                "design §10.2.1：永久冻结，作为提交状态的历史验收证据保留")
        v.check(group, "④ TASK_002 fixture 的 git_is_dirty 仍是 bool",
                isinstance(t002_fixture.get("git_is_dirty"), bool), "bool",
                type(t002_fixture.get("git_is_dirty")).__name__)
        v.check(group, "④ 未重新生成 TASK_002 fixture（compare_source 未变）",
                t002_fixture.get("compare_source") == "runtime_state_unrounded",
                "runtime_state_unrounded", repr(t002_fixture.get("compare_source")))

    # ── ② / ③ pre-TASK_003 fixture 溯源与行为不变性 ──
    rel_fixture = os.path.relpath(FIXTURE_PATH, project_root)
    if not os.path.isfile(FIXTURE_PATH):
        note = ("%s 不存在。按 design §12.1 第 3 步，须在生产树洁净且尚未应用任何 "
                "TASK_003 生产 diff 时以 --generate-fixture 生成" % rel_fixture)
        if formal:
            v.check(group, "② pre-TASK_003 fixture 存在", False, "present",
                    "MISSING", note + "。正式验收缺基线即无法验证行为不变性")
            v.check(group, "③ pre-TASK_003 行为不变性", False, "0 diff",
                    "no baseline", "无 fixture 时行为不变性未经任何验证")
        else:
            v.warn(group, "② pre-TASK_003 fixture 溯源", "跳过（离线模式）：" + note)
            v.warn(group, "③ pre-TASK_003 行为不变性",
                   "跳过（离线模式）：fixture 尚不存在。正式验收下此情形 FAIL")
        return diffs

    try:
        with open(FIXTURE_PATH, encoding="utf-8") as f:
            fixture = json.load(f)
    except Exception as e:
        detail = "%s: %s" % (type(e).__name__, e)
        if formal:
            v.check(group, "② fixture 可读", False, "readable JSON", detail,
                    "正式验收下不可读的基线等同于没有基线")
            v.check(group, "③ pre-TASK_003 行为不变性", False, "0 diff",
                    "baseline unreadable", detail)
        else:
            v.warn(group, "② fixture 可读", "跳过（离线模式）：" + detail)
            v.warn(group, "③ pre-TASK_003 行为不变性",
                   "跳过（离线模式）：fixture 不可读。正式验收下此情形 FAIL")
        return diffs

    recorded_harness = fixture.get("test_harness_sha256")
    v.check(group, "② test_harness_sha256 与当前测试文件完全相同",
            _is_hex64(recorded_harness) and recorded_harness == harness_sha256(),
            recorded_harness, harness_sha256(),
            "测试文件定义了 fixture 的全部输入；改测试即作废基线（design §12.1 第 6 步）")
    v.check(group, "② git_is_dirty 为 bool（\"unknown\" 不得进入 fixture）",
            isinstance(fixture.get("git_is_dirty"), bool), "bool",
            type(fixture.get("git_is_dirty")).__name__,
            "True 属预期且允许：生成时本测试文件尚未提交、fixture 尚不存在；"
            "design.md 已提交")
    commit = fixture.get("generated_from_commit")
    v.check(group, "② generated_from_commit 为 40 位 hex", _is_hex40(commit),
            "40-hex sha", repr(commit))
    branch = fixture.get("git_branch")
    v.check(group, "② git_branch 已判定", isinstance(branch, str)
            and branch not in ("", "unknown"), "non-empty branch", repr(branch))
    status, detail = check_fixture_commit_ancestry(project_root, commit)
    v.check(group, "② fixture commit 是 HEAD 的祖先（或等于 HEAD）",
            status == "ancestor", "ancestor", status, detail)

    # ── ⑥ 生产代码基线锚点（R-29）──
    baseline_commit = fixture.get("production_baseline_commit")
    v.check(group, "⑥ production_baseline_commit 为 40 位 SHA",
            _is_hex40(baseline_commit), "40-hex sha", repr(baseline_commit),
            "它锚定「TASK_003 生产 diff 尚未应用」这一状态，不可缺省")
    v.check(group, "⑥ production_baseline_commit 与测试常量完全相等",
            baseline_commit == PRE_TASK003_BASE_COMMIT,
            PRE_TASK003_BASE_COMMIT, repr(baseline_commit),
            "不相等意味着 fixture 与当前测试对「pre 状态」的定义不一致")
    b_status, b_detail = check_fixture_commit_ancestry(project_root, baseline_commit)
    v.check(group, "⑥ production_baseline_commit 是当前 HEAD 的祖先",
            b_status == "ancestor", "ancestor", b_status, b_detail)
    v.check(group, '⑥ fixture_generation_guard_version == "%s"'
            % FIXTURE_GENERATION_GUARD_VERSION,
            fixture.get("fixture_generation_guard_version")
            == FIXTURE_GENERATION_GUARD_VERSION,
            FIXTURE_GENERATION_GUARD_VERSION,
            repr(fixture.get("fixture_generation_guard_version")),
            "守卫版本不符说明该 fixture 是用一套更弱的前置检查生成的")
    v.check(group, "② compared_fields 与 S15 同一组量",
            list(fixture.get("compared_fields") or []) == list(COMPARED_FIELDS),
            list(COMPARED_FIELDS), fixture.get("compared_fields"),
            "S15 跨实验、S18 跨代码状态，比较同一组量才能互相印证")
    v.check(group, "② compare_tolerance == 0", fixture.get("compare_tolerance") == 0.0,
            0.0, repr(fixture.get("compare_tolerance")))
    v.check(group, "② 记录了 TASK_003 五个生产文件的改动前哈希",
            set(fixture.get("pretask003_file_sha256", {}) or {})
            == set(PRETASK003_HASHED_FILES),
            sorted(PRETASK003_HASHED_FILES),
            sorted((fixture.get("pretask003_file_sha256") or {}).keys()),
            "仅供溯源，不作行为断言")

    # ── ⑤ baseline_file_sha256 必须真正参与验收（R-28）──
    #
    # 三个 Agent 插件直接决定行为轨迹，而 TASK_003 明确不修改它们（§15 第 1–3 项）。
    # 第 4 版之前只在生成时**记录**这三个哈希、验证期从不读取，等于没有约束：
    # 插件被改动后，fixture 比对会以「行为差异」的形式失败，但报告无法指出
    # 「输入本身变了」这一根因，甚至可能因为改动恰好不影响本组场景而完全通过。
    baseline_hashes = fixture.get("baseline_file_sha256")
    v.check(group, "⑤ fixture 含 baseline_file_sha256 字段",
            isinstance(baseline_hashes, dict), "dict",
            type(baseline_hashes).__name__)
    if isinstance(baseline_hashes, dict):
        v.check(group, "⑤ baseline_file_sha256 键集合恰为三个 Agent 插件",
                set(baseline_hashes) == set(BASELINE_HASHED_FILES),
                sorted(BASELINE_HASHED_FILES), sorted(baseline_hashes),
                "多一个或少一个都意味着输入定义与 fixture 记录不一致")
        for rel in BASELINE_HASHED_FILES:
            recorded = baseline_hashes.get(rel)
            v.check(group, "⑤ 记录值为 64 位 SHA-256: " + rel, _is_hex64(recorded),
                    "64-hex sha256", repr(recorded),
                    "\"missing:...\" 或空值不得冒充已知哈希")
            current = _sha256_file(_abs(rel))
            v.check(group, "⑤ 当前文件哈希与 fixture 记录一致: " + rel,
                    _is_hex64(recorded) and current == recorded,
                    recorded, current,
                    "TASK_003 不修改任何 Agent 插件（design §15 第 1–3 项）；"
                    "不一致说明行为轨迹的输入已变，fixture 比对失去意义")

    # 冻结的 TASK_002 两个产物：与 fixture 生成时记录的哈希逐一比对
    frozen = fixture.get("frozen_task002_sha256", {}) or {}
    for rel in (TASK002_TEST_REL, TASK002_FIXTURE_REL):
        expected = frozen.get(rel)
        actual = _sha256_file(_abs(rel))
        v.check(group, "④ 冻结未被打破: " + rel,
                _is_hex64(expected) and expected == actual, expected, actual,
                "TASK_003 全程不修改 TASK_002 的测试与 fixture")

    # ── ③ 行为不变性：逐 (scenario, cluster_type, tick) 精确比较 ──
    current = await collect_behavior_trace()
    diffs = compare_traces(fixture, current)
    total_points = sum(len(s["ticks"]) for s in current) * len(COMPARED_FIELDS)
    v.check(group, "③ pre-TASK_003 行为完全一致（容差 0，%d 个比对点）" % total_points,
            not diffs, "0 diff", "%d diff" % len(diffs),
            "; ".join("%s/%s t%s %s: %s→%s" % (d["scenario"], d["cluster_type"],
                                               d["tick"], d["field"],
                                               d["baseline"], d["current"])
                      for d in diffs[:3]))
    return diffs


# ══════════════════════════════════════════════════════════════════════
# 语法检查（本测试文件 + 5 个生产文件）
# ══════════════════════════════════════════════════════════════════════

def check_syntax(v):
    group = "T0-syntax"
    targets = [_abs(rel) for rel in PRODUCTION_FILES_TASK003]
    targets.append(os.path.abspath(__file__))
    for path in targets:
        rel = os.path.relpath(path, project_root)
        if not os.path.isfile(path):
            v.error(group, "文件存在: " + rel, "文件不存在")
            continue
        try:
            py_compile.compile(path, doraise=True, cfile=os.devnull)
            v.check(group, "语法正确: " + rel, True, "compiles", "compiles")
        except Exception as e:
            v.error(group, "语法正确: " + rel, "%s: %s" % (type(e).__name__, e))

    # 本任务明确不修改的文件：只做存在性确认，不做任何写入
    for rel in UNTOUCHED_FILES_TASK003:
        v.check(group, "不修改的文件仍存在: " + rel, os.path.isfile(_abs(rel)),
                "present", "MISSING",
                "design §15：TASK_003 对这些文件不作任何改动")


# ══════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════

async def main_verify(runtime_dir=None):
    """runtime_dir is None → --offline-only（S15/S16 记 WARN，非正式验收）
       runtime_dir 非空     → --runtime-dir 正式验收（S15/S16 缺失即 FAIL）"""
    formal = runtime_dir is not None
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(project_root, "results", "task003_validation", timestamp)
    os.makedirs(out_dir, exist_ok=True)

    logger = logging.getLogger("task003v")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(os.path.join(out_dir, "validation.log"), encoding="utf-8")
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.info("TASK_003-V validation started: %s (mode=%s)", timestamp,
                "runtime-dir (FORMAL)" if formal else "offline-only")
    if not formal:
        print("=" * 66)
        print("MODE: --offline-only   >>> NOT A FULL ACCEPTANCE <<<")
        print("S15 / S16 需要一个 matrix v3.0 的运行目录；本模式下它们记 WARN。")
        print("正式验收请使用: --runtime-dir <path>")
        print("=" * 66)

    v = Verdicts()
    EC = _try_import("experiment_config", v)
    SC = _try_import("simulation_core", v)
    RX = _try_import("run_experiments", v)

    check_syntax(v)

    matrix = check_s1_matrix_size(v, EC)
    check_s2_matrix_structure(v, EC, matrix)
    check_s3_exp_ids(v, EC, matrix)
    check_s4_clarification_tick(v, EC, matrix)
    check_s5_label_scope(v, EC, matrix)
    check_s6_invalid_combinations(v, EC)
    # S7 必须在 S18 之前执行：S18 的 ① 项核对 contract=Cn 标记是否真的被执行过
    check_s7_task002_schema(v, EC, RX, SC)
    check_s8_sentinel(v, EC)
    check_s9_recording_replay_pairing(v, EC, RX, matrix)
    await check_s10_replay_router(v, RX)
    await check_s10_1_fail_closed(v, RX)
    check_s11_summary_columns(v, RX)
    check_s12_plot_function_names(v)
    check_s13_domain_gate(v, formal)
    check_s14_contrasts(v)

    # 运行期目录只来自显式的 --runtime-dir，绝不自动发现或回退到 latest/
    if formal:
        found, problems = validate_runtime_dir(runtime_dir)
        why = "; ".join(problems)
        v.check("S16-runtime-artifacts", "--runtime-dir 是合格的 v3.0 运行目录",
                found is not None, "matrix_version=3.0 且 condition_count=9",
                why or "ok", "正式验收拒绝任何版本不符或产物不全的目录")
        if found is None:
            logger.error("正式验收目录不可用：%s", why)
        else:
            logger.info("正式验收使用产物目录：%s", found[1])
    else:
        found, why = None, "离线模式未提供 --runtime-dir"
    check_s15_pre_treatment_alignment(v, found, formal, why)
    check_s16_runtime_artifacts(v, found, formal, why)

    check_s17_legacy_gate(v)
    diffs = await check_s18_handover_and_invariance(v, formal)

    verdict_path = os.path.join(out_dir, "task003_verdicts.json")
    summary = {
        "timestamp": timestamp,
        "mode": "runtime-dir" if formal else "offline-only",
        # 只有"正式模式 **且** 零 FAIL"才算完整验收通过。
        # 单看 formal 会把"正式模式但验收失败"错标为 full acceptance。
        "is_full_acceptance": bool(formal and v.n_fail == 0),
        "is_formal_mode": formal,
        "matrix_version_expected": EXPECTED_MATRIX_VERSION,
        "runtime_dir": (found[1] if found else None),
        "runtime_skip_reason": (why if found is None else ""),
        "total": len(v.items),
        "passed": v.n_pass,
        "failed": v.n_fail,
        "warned": v.n_warn,
        "all_pass": v.n_fail == 0,
        "verdicts": v.items,
    }
    with open(verdict_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    diff_path = os.path.join(out_dir, "behavior_diff.csv")
    with open(diff_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "cluster_type", "tick",
                                          "field", "baseline", "current"])
        w.writeheader()
        for d in diffs:
            w.writerow(d)

    for item in v.items:
        if item["result"] == "FAIL":
            logger.error("FAIL %s | %s | expected=%s actual=%s %s",
                         item["group"], item["assertion"],
                         item["expected"], item["actual"], item["note"])
        elif item["result"] == "WARN":
            logger.warning("WARN %s | %s | %s", item["group"], item["assertion"],
                           item["note"])

    by_group = {}
    for item in v.items:
        g = by_group.setdefault(item["group"], {"PASS": 0, "FAIL": 0, "WARN": 0})
        g[item["result"]] += 1

    print("=" * 66)
    print("TASK_003-V ACCEPTANCE RESULTS (%s)"
          % ("FORMAL: --runtime-dir" if formal else "OFFLINE ONLY"))
    print("=" * 66)
    for group in sorted(by_group):
        g = by_group[group]
        print("  %-32s PASS=%-4d FAIL=%-4d WARN=%d"
              % (group, g["PASS"], g["FAIL"], g["WARN"]))
    print("-" * 66)
    print("Total : %d" % len(v.items))
    print("Passed: %d" % v.n_pass)
    print("Failed: %d" % v.n_fail)
    print("Warned: %d" % v.n_warn)
    print("Output: %s" % out_dir)
    print("=" * 66)
    if formal:
        print("ALL ACCEPTANCE CRITERIA PASSED" if v.n_fail == 0
              else "%d ASSERTION(S) FAILED" % v.n_fail)
    else:
        print(">>> NOT A FULL ACCEPTANCE (offline-only) <<<")
        print("离线项无 FAIL" if v.n_fail == 0 else "%d ASSERTION(S) FAILED" % v.n_fail)
        print("正式验收必须使用 --runtime-dir <matrix v3.0 运行目录>")
    return v.n_fail == 0


def main():
    parser = argparse.ArgumentParser(
        description="TASK_003 experiment matrix (v3.0) acceptance test",
        epilog="必须显式选择一种模式：--generate-fixture / --offline-only / --runtime-dir")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--generate-fixture", action="store_true",
                      help="只生成 pre-TASK_003 行为基线 fixture；不运行 S1–S18，"
                           "不要求新矩阵已实施")
    mode.add_argument("--offline-only", action="store_true",
                      help="运行离线验收；S15/S16 无运行目录时记 WARN；"
                           "明确输出 NOT A FULL ACCEPTANCE")
    mode.add_argument("--runtime-dir", metavar="PATH", default=None,
                      help="正式验收。PATH 必须是 matrix_version=3.0 且 "
                           "condition_count=9 的运行目录；绝不回退读取 results/latest")
    args = parser.parse_args()

    if args.generate_fixture:
        # 只做 fixture：生产树洁净检查（unstaged / staged / untracked 三项）与
        # 溯源可判定性检查在 generate_fixture() 内部执行，不满足时 sys.exit(2)。
        # 这里刻意不运行任何 S1–S18 断言——fixture 的语义与新矩阵是否实施无关。
        asyncio.run(generate_fixture())
        return 0

    if args.offline_only:
        return 0 if asyncio.run(main_verify(runtime_dir=None)) else 1

    if args.runtime_dir:
        return 0 if asyncio.run(main_verify(runtime_dir=args.runtime_dir)) else 1

    print("=" * 66)
    print("ERROR: 必须显式选择一种运行模式。")
    print("")
    print("  --generate-fixture      只生成 pre-TASK_003 行为基线 fixture")
    print("  --offline-only          离线验收（NOT A FULL ACCEPTANCE）")
    print("  --runtime-dir PATH      正式验收（PATH 必须是 v3.0 运行目录）")
    print("")
    print("拒绝无参数运行，是为了排除\"以为在做正式验收、实际只跑了离线项\"这种")
    print("误判；也为了确保运行期目录只来自显式路径，绝不自动回退到 latest/。")
    print("=" * 66)
    return 2


if __name__ == "__main__":
    sys.exit(main())
