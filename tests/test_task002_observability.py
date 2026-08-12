"""
TASK_002-V: agent_records 可审计性（schema v2.0）验收测试

两种运行模式：
    python tests/test_task002_observability.py --generate-fixture
        在**应用 TASK_002 diff 之前**运行，生成行为基线 fixture。

    python tests/test_task002_observability.py
        在**应用 TASK_002 diff 之后**运行，执行全部验收检查。

覆盖检查项：
    T1  Python 语法检查（5 个修改文件 + 本测试文件）
    T2  fieldnames 无重复
    T3  60 个唯一字段 + v1.0 21 字段相对顺序保持
    T4  build_agent_record() 输出字段集合 == schema v2.0
    T5  审计字段精度：12 位小数用于复算（禁止塌陷到 4 位）；不变性不依赖 CSV
    T6  run_metadata.json 哈希不为 unknown / top_p 未配置时为 "unknown" /
        不泄漏 api_key / git_is_dirty 显式存在 / 不含 global_event_ticks
    T7  network_type 与实际建图分支一致（complete / BA / ER fallback / empty）
    T8  network_hash 同时覆盖 nodes 与 edges，且确定性
    T9  target_nodes 审计：Random 渠道 metric_value 为空串而非 0
    T10 pre-TASK_002 fixture 行为完全一致（无容差精确比对，500 个比对点）
    T11 clarification_content_type 来自实际 observation，而非配置反推
    T12 导入卫生：未引入 time；TASK_002 新增导入均被使用
    T13 澄清四阶段 + 事件两阶段字段来源独立（互不替代，禁止 tick 比较推断 received）
    T14 ClarificationInjector.inject() 签名/返回类型不变 + last_injected_ids 回执语义
    T15 run 级 network_nodes.csv / network_edges.csv 契约（无 exp_id、无目标标记、
        network_hash 一致才写出、不一致则拒绝写出 + 报告）+ experiment_metadata.jsonl
        18 字段（含因子/seed/预算/目标节点/网络指纹/生效时间线；异常结果也带 config）
    T16 effective_event_timeline 取自实验结果，run_metadata 不从常量重建
    T17 fixture 溯源（commit/branch/is_dirty 为 bool/baseline_sha256/test_harness_sha256）
        + 生产树洁净前置检查 + fixture commit 与 HEAD 的祖先关系检查

本测试不修改任何生产代码，不访问网络，不加载 SBERT 模型。
"""
import sys
import os
import ast
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

# 关键：在导入任何插件之前禁用 sentence-transformers。
# sys.modules[name] = None 会让 `from sentence_transformers import ...` 抛 ImportError，
# 从而命中 MemoryManager 中**已存在**的回退分支（不改动 MemoryManager 任何代码）。
if "sentence_transformers" not in sys.modules:
    sys.modules["sentence_transformers"] = None

import random as random_module
import numpy as np
import networkx as nx

from plugins.agent.reflect.GreenCognitionPlugin import GreenCognitionPlugin
from plugins.agent.plan.ConsumerPlanPlugin import ConsumerPlanPlugin
from plugins.agent.invoke.GreenInvokePlugin import GreenInvokePlugin
from plugins.environment.network.SocialNetworkPlugin import SocialNetworkPlugin

FIXTURE_DIR = os.path.join(current_dir, "fixtures", "task002")
FIXTURE_PATH = os.path.join(FIXTURE_DIR, "pre_task002_behavior_trace.json")
FIXTURE_SEED = 42

MODIFIED_FILES = [
    "clarification_injector.py",
    "simulation_core.py",
    "run_experiments.py",
    os.path.join("plugins", "agent", "plan", "ConsumerPlanPlugin.py"),
    os.path.join("plugins", "environment", "network", "SocialNetworkPlugin.py"),
]

# TASK_002 由本设计引入的导入，必须确实被使用
TASK002_NEW_IMPORTS = {
    "simulation_core.py": ["hashlib"],
    "run_experiments.py": ["hashlib", "json", "platform", "subprocess"],
}

# schema v2.0 的字段总数（唯一口径；56 已废弃）
EXPECTED_FIELD_COUNT = 60

# 澄清四阶段字段（顺序即阶段顺序），四者必须同时存在且语义互不替代
CLARIFICATION_STAGE_FIELDS = [
    "is_clarification_target",         # ① 选中
    "clarification_injected",          # ② 写入
    "clarification_received",          # ③ 收到
    "clarification_detected_by_plan",  # ④ Plan 识别
]

# 全局事件两阶段字段
GLOBAL_EVENT_STAGE_FIELDS = ["global_event_scheduled", "global_event_received"]

# 本轮改名后**不得**再出现的旧字段名
REMOVED_FIELD_NAMES = ["has_clarification_observed", "is_target_node"]

# schema v1.0 的 21 个字段（相对顺序必须在 v2.0 中保持）
V1_FIELDS = [
    "exp_id", "tick", "agent_id", "cluster_type", "social_role",
    "trust_score", "baseline_trust", "trust_after_decay",
    "affective_change", "shock_anchor", "quiet_ticks", "decay_lambda",
    "is_buying", "is_posting", "post_content",
    "hypocrisy_perceived", "importance", "reasoning",
    "has_global_event", "has_clarification", "cumulative_buyers",
]

CLUSTER_TYPES = ["Active_Greens", "Convenient_Greens", "Dormant_Greens", "Non_Greens"]
INITIAL_TRUST_MAP = {
    "Active_Greens": 8.0, "Convenient_Greens": 6.5,
    "Dormant_Greens": 5.5, "Non_Greens": 5.0,
}


# ══════════════════════════════════════════════════════════════════════
# 判定记录器
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
# Fake 基础设施（与 tests/test_task001_state_reset.py 同构）
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
    """按 Prompt 中的稳定标记返回固定 JSON。无随机、无网络。"""

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


def _wire_plugin(plugin, agent):
    comp = FakeComponent(plugin)
    comp.agent = agent
    comp._agent = agent
    plugin.component = comp
    plugin.agent = agent


# ══════════════════════════════════════════════════════════════════════
# 场景定义（字面常量；不引用 CONTENT_TEMPLATES，保证 pre/post 同输入）
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
    return [
        {"tick": 5,  "observations": [{"source": "Global News", "content": SCANDAL_NEWS}],
         "current_news": SCANDAL_NEWS},
        {"tick": 6,  "observations": [copy.deepcopy(CLARIFICATION_MSG)],
         "current_news": CLARIFICATION_HEADLINE},
        {"tick": 7,  "observations": [], "current_news": ""},
        {"tick": 8,  "observations": [], "current_news": ""},
        {"tick": 9,  "observations": [], "current_news": ""},
        {"tick": 10, "observations": [copy.deepcopy(POSITIVE_SOCIAL_MSG)], "current_news": ""},
        {"tick": 11, "observations": [], "current_news": ""},
        {"tick": 12, "observations": [], "current_news": ""},
    ]


def _scenario_delayed():
    return [
        {"tick": 5,  "observations": [{"source": "Global News", "content": SCANDAL_NEWS}],
         "current_news": SCANDAL_NEWS},
        {"tick": 6,  "observations": [], "current_news": ""},
        {"tick": 7,  "observations": [], "current_news": ""},
        {"tick": 8,  "observations": [], "current_news": ""},
        {"tick": 9,  "observations": [], "current_news": ""},
        {"tick": 10, "observations": [copy.deepcopy(CLARIFICATION_MSG)],
         "current_news": CLARIFICATION_HEADLINE},
        {"tick": 11, "observations": [], "current_news": ""},
        {"tick": 12, "observations": [], "current_news": ""},
        {"tick": 13, "observations": [], "current_news": ""},
    ]


def _scenario_no_clarification():
    ticks = [{"tick": 5, "observations": [{"source": "Global News", "content": SCANDAL_NEWS}],
              "current_news": SCANDAL_NEWS}]
    ticks += [{"tick": t, "observations": [], "current_news": ""} for t in range(6, 13)]
    return ticks


SCENARIOS = {
    "immediate": _scenario_immediate,
    "delayed": _scenario_delayed,
    "no_clarification": _scenario_no_clarification,
}

COMPARED_FIELDS = ["trust_score", "shock_anchor", "quiet_ticks", "is_buying", "is_posting"]


# ══════════════════════════════════════════════════════════════════════
# 行为轨迹采集（pre/post 共用同一函数，保证同输入）
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
        ticks_out.append({
            "tick": tc["tick"],
            "trust_score": sd.get("trust_score"),
            "shock_anchor": sd.get("shock_anchor"),
            "quiet_ticks": plan.get("quiet_ticks"),
            "is_buying": bool(plan.get("is_buying", False)),
            "is_posting": bool(plan.get("is_posting", False)),
        })

    return {"scenario": scenario_name, "cluster_type": cluster_type,
            "initial_trust": init_trust, "ticks": ticks_out}


async def collect_behavior_trace():
    scenarios = []
    for scenario_name in ("immediate", "delayed", "no_clarification"):
        for cluster_type in CLUSTER_TYPES:
            scenarios.append(await run_behavior_scenario(scenario_name, cluster_type))
    return scenarios


def _sha256_file(path):
    if not os.path.isfile(path):
        return "missing:" + os.path.basename(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


BASELINE_HASHED_FILES = (
    "plugins/agent/plan/ConsumerPlanPlugin.py",
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "plugins/agent/invoke/GreenInvokePlugin.py",
)


# ══════════════════════════════════════════════════════════════════════
# fixture 生成前置检查：生产文件必须无未提交修改（TASK_002 / R5）
# ══════════════════════════════════════════════════════════════════════

# 只检查生产路径。故意排除 tests/ —— 生成 fixture 时测试文件本身尚未提交，
# 若纳入检查会导致永远无法生成（死锁）。
PRODUCTION_PATHS = [
    "run_experiments.py",
    "simulation_core.py",
    "experiment_config.py",
    "node_selector.py",
    "clarification_injector.py",
    "metrics_calculator.py",
    "generate_data.py",
    "custom_controller.py",
    "plugins",
    "configs",
]


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
    """返回生产路径下的未提交改动条目列表（含未跟踪文件）。

    返回值：
        (status, entries)
        status = "clean"        → entries == []
        status = "dirty"        → entries 为 porcelain 行列表
        status = "undetermined" → 无法判定（无 git / 非仓库 / 命令失败），entries 为原因
    """
    code, out, err = _git(["rev-parse", "--is-inside-work-tree"], root)
    if code != 0 or out != "true":
        return "undetermined", ["cannot verify git work tree: %s" % (err or out or code)]

    code, out, err = _git(
        ["status", "--porcelain", "--untracked-files=all", "--"] + PRODUCTION_PATHS, root)
    if code != 0:
        return "undetermined", ["git status failed: %s" % (err or code)]

    entries = [ln for ln in out.splitlines() if ln.strip()]
    return ("dirty" if entries else "clean"), entries


def assert_clean_production_tree(root):
    """生产树不洁净或不可判定时打印明确错误并以非零码退出。

    fail-closed：无法判定也拒绝生成——"不知道代码状态"与"代码状态错误"
    对 fixture 的可信度而言后果相同。
    """
    status, entries = collect_dirty_production_entries(root)
    if status == "clean":
        return
    print("=" * 66)
    print("ERROR: refusing to generate fixture.")
    if status == "dirty":
        print("Production files have uncommitted changes (%d entr%s):"
              % (len(entries), "y" if len(entries) == 1 else "ies"))
        for line in entries:
            print("  " + line)
        print("")
        print("The fixture must be a reproducible snapshot of a committed code state.")
        print("Commit or stash the changes above, then re-run:")
        print("  python tests/test_task002_observability.py --generate-fixture")
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


def read_git_provenance(root):
    """fixture 溯源信息：commit / branch / 仓库范围 is_dirty。

    注意 git_is_dirty 的范围是**整个仓库**（含 tests/、.kiro/ 等非生产路径），仅作记录；
    生产路径的洁净性由 assert_clean_production_tree() 强制，二者不是同一件事。

    本函数仍可能返回 "unknown"（表示无法判定）；R13 要求写入 fixture 的值必须是
    bool，因此 generate_fixture() 会在此之后调用 assert_provenance_determined()
    把 "unknown" 变成退出码 2，而不是让它进入 fixture。
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
    """R13：溯源信息不可判定时拒绝生成（退出码 2）。

    要求：
      · generated_from_commit 为 40 位 hex（祖先关系检查需要它）
      · git_branch 非空且非 "unknown"
      · git_is_dirty 为 bool —— "unknown" 不得进入 fixture
        （注意：True 是允许的，.kiro/ 下的设计文档未提交属正常状态）
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
    print("Note: git_is_dirty == True is FINE and expected (uncommitted docs under")
    print(".kiro/ are normal). Only 'unknown' is rejected. Production-path")
    print("cleanliness is enforced separately by assert_clean_production_tree().")
    print("=" * 66)
    sys.exit(2)


def check_fixture_commit_ancestry(root, fixture_commit):
    """fixture 的 commit 是否为当前 HEAD 的祖先（或就是 HEAD）。

    git merge-base --is-ancestor <A> <B> 的退出码约定：
        0 → A 是 B 的祖先（A == B 时也返回 0，符合"或等于 HEAD"的要求）
        1 → A 不是 B 的祖先
        其他 → 命令本身失败（如 commit 不存在于本地仓库）

    Returns:
        (status, detail)
        status = "ancestor"     → 通过
        status = "not_ancestor" → 明确不成立（FAIL）
        status = "undetermined" → 无法判定（同样 FAIL，fail-closed）
    """
    if not (isinstance(fixture_commit, str) and len(fixture_commit) == 40):
        return "undetermined", "fixture commit is not a 40-hex sha: %r" % (fixture_commit,)

    code_h, head, err_h = _git(["rev-parse", "HEAD"], root)
    if code_h != 0 or not head:
        return "undetermined", "cannot resolve HEAD: %s" % (err_h or code_h)

    # commit 是否存在于本地仓库（不存在时 merge-base 会以非 0/1 退出码失败）
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
            "history + TASK_002 diff'; regenerate the fixture on this line."
            % (fixture_commit[:12], head[:12]))
    return "undetermined", "git merge-base failed: %s" % (err or code)


def harness_sha256():
    """R13：本测试文件自身的 SHA-256。

    测试文件定义了 fixture 的全部输入（DeterministicRouter 返回值、场景字面常量、
    Tick 序列、COMPARED_FIELDS），因此它本身就是输入的一部分，必须与 fixture 一起锁定。
    """
    return _sha256_file(os.path.abspath(__file__))


async def generate_fixture():
    # ── R5 前置检查：生产文件必须无未提交修改；脏或不可判定 → sys.exit(2) ──
    # 必须在任何场景执行之前调用，避免产出一个来源不明的 fixture。
    assert_clean_production_tree(project_root)
    provenance = read_git_provenance(project_root)
    # ── R13 前置检查：commit / branch / git_is_dirty 必须可判定；
    #    git_is_dirty 必须是 bool（True 是允许的），"unknown" → sys.exit(2) ──
    assert_provenance_determined(provenance)

    os.makedirs(FIXTURE_DIR, exist_ok=True)
    scenarios = await collect_behavior_trace()
    fixture = {
        "fixture_version": "1.2",
        "purpose": "pre-TASK_002 behavior baseline (trust/anchor/quiet/buy/post per tick)",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "code_state": "pre-TASK_002 (TASK_001 applied)",
        "router": "DeterministicRouter/v1",
        "seed": FIXTURE_SEED,
        "compare_tolerance": 0.0,
        # R7：比对对象是运行期未舍入内存状态，不经 CSV，不依赖任何小数位约定
        "compare_source": "runtime_state_unrounded",
        "compared_fields": list(COMPARED_FIELDS),
        # ── R13：测试文件自身哈希（输入定义指纹；验证时必须完全相同）──
        "test_harness_sha256": harness_sha256(),
        # ── R5 + R13：溯源四项（git_is_dirty 此处必为 bool，已由前置检查保证）──
        "generated_from_commit": provenance["generated_from_commit"],
        "git_branch": provenance["git_branch"],
        "git_is_dirty": provenance["git_is_dirty"],
        "production_paths_checked": list(PRODUCTION_PATHS),
        "baseline_file_sha256": {
            rel: _sha256_file(os.path.join(project_root, *rel.split("/")))
            for rel in BASELINE_HASHED_FILES
        },
        "scenarios": scenarios,
    }
    with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)
    total_ticks = sum(len(s["ticks"]) for s in scenarios)
    print("Fixture written : " + FIXTURE_PATH)
    print("From commit     : %s (%s)" % (provenance["generated_from_commit"],
                                         provenance["git_branch"]))
    print("Repo is_dirty   : %s   (bool; production tree verified clean)"
          % provenance["git_is_dirty"])
    print("Harness sha256  : %s   (do NOT modify this test file from now on)"
          % fixture["test_harness_sha256"][:16])
    print("Scenarios       : %d" % len(scenarios))
    print("Tick snapshots  : %d" % total_ticks)
    print("Compare points  : %d" % (total_ticks * len(COMPARED_FIELDS)))
    return fixture


def compare_traces(fixture, current_scenarios):
    """返回差异列表；空列表 = 行为完全一致。"""
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
# 通用工具
# ══════════════════════════════════════════════════════════════════════

def _is_hex64(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _try_import(module_name, v):
    try:
        return __import__(module_name)
    except Exception as e:
        v.error("T0-import", "import " + module_name,
                "%s: %s" % (type(e).__name__, e))
        return None


class _NetAgent:
    """只提供 agent_id 的最小 Agent 壳，供 register_agents 使用。"""

    def __init__(self, agent_id):
        self.agent_id = agent_id


def _expected_directed(undirected, agent_ids, n):
    """按生产代码的相同规则复现有向化结果（relabel → degree → 高度数指向低度数）。"""
    und = nx.relabel_nodes(undirected, {i: agent_ids[i] for i in range(n)})
    deg = dict(und.degree())
    d = nx.DiGraph()
    d.add_nodes_from(und.nodes())
    for u, w in und.edges():
        if deg[u] >= deg[w]:
            d.add_edge(u, w)
        else:
            d.add_edge(w, u)
    return d


def _net_ids(n):
    return ["Consumer_%03d" % i for i in range(n)]


# ══════════════════════════════════════════════════════════════════════
# T1  语法检查
# ══════════════════════════════════════════════════════════════════════

def check_syntax(v):
    targets = [os.path.join(project_root, rel) for rel in MODIFIED_FILES]
    targets.append(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        for path in targets:
            rel = os.path.relpath(path, project_root).replace(os.sep, "/")
            cfile = os.path.join(tmp, rel.replace("/", "_") + "c")
            try:
                py_compile.compile(path, cfile=cfile, doraise=True)
                v.check("T1-syntax", "py_compile " + rel, True, "compiles", "compiles")
            except Exception as e:
                v.check("T1-syntax", "py_compile " + rel, False, "compiles",
                        "%s: %s" % (type(e).__name__, e))


# ══════════════════════════════════════════════════════════════════════
# T2 / T3  schema 字段契约
# ══════════════════════════════════════════════════════════════════════

def check_schema(v, SC):
    if SC is None:
        v.error("T2-schema", "schema 可读", "simulation_core 未能导入")
        return None
    fields = list(SC.AGENT_RECORDS_FIELDS)
    dups = sorted({n for n in fields if fields.count(n) > 1})

    v.check("T2-schema", "fieldnames 无重复", not dups, "[]", dups)
    v.check("T2-schema", "trust_after_decay 只出现一次",
            fields.count("trust_after_decay") == 1, 1, fields.count("trust_after_decay"))
    v.check("T2-schema", "trust_after_decay_raw 只出现一次",
            fields.count("trust_after_decay_raw") == 1, 1, fields.count("trust_after_decay_raw"))
    v.check("T3-schema", "字段数 == %d" % EXPECTED_FIELD_COUNT,
            len(fields) == EXPECTED_FIELD_COUNT, EXPECTED_FIELD_COUNT, len(fields))
    v.check("T3-schema", "唯一字段数 == %d" % EXPECTED_FIELD_COUNT,
            len(set(fields)) == EXPECTED_FIELD_COUNT, EXPECTED_FIELD_COUNT, len(set(fields)))
    v.check("T3-schema", "schema_version == 2.0",
            SC.AGENT_RECORDS_SCHEMA_VERSION == "2.0", "2.0", SC.AGENT_RECORDS_SCHEMA_VERSION)

    # ── 澄清四阶段 / 事件两阶段字段必须同时存在（R1 / R2）──
    for name in CLARIFICATION_STAGE_FIELDS + GLOBAL_EVENT_STAGE_FIELDS:
        v.check("T3-schema", "阶段字段存在: " + name, name in fields, "present",
                "present" if name in fields else "MISSING")
    # ── 改名后的旧字段名不得残留（R9 语义去重）──
    for name in REMOVED_FIELD_NAMES:
        v.check("T3-schema", "旧字段名已移除: " + name, name not in fields, "absent",
                "STILL PRESENT" if name in fields else "absent")
    # ── has_clarification（配置声称）必须与四阶段并存，不得被替换掉 ──
    v.check("T3-schema", "has_clarification（配置声称）保留",
            "has_clarification" in fields, "present",
            "present" if "has_clarification" in fields else "MISSING")

    missing = [f for f in V1_FIELDS if f not in fields]
    v.check("T3-schema", "v1.0 的 21 字段全部保留", not missing, "[]", missing)
    if not missing:
        idx = [fields.index(f) for f in V1_FIELDS]
        v.check("T3-schema", "v1.0 字段相对顺序保持", idx == sorted(idx), "ascending", idx)
    return fields


def check_csv_header(v, RX, SC):
    """真实调用 write_agent_records_csv，验证落盘表头恰为 60 列且无重复。"""
    if RX is None or SC is None:
        v.error("T3-schema", "CSV 表头可验证", "run_experiments / simulation_core 未能导入")
        return
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "agent_records.csv")
        try:
            RX.write_agent_records_csv([], out)
        except AssertionError as e:
            v.check("T3-schema", "write_agent_records_csv 断言通过", False,
                    "no AssertionError", str(e))
            return
        with open(out, "r", encoding="utf-8", newline="") as f:
            header = next(csv.reader(f))
    v.check("T3-schema", "CSV 表头列数 == %d" % EXPECTED_FIELD_COUNT,
            len(header) == EXPECTED_FIELD_COUNT, EXPECTED_FIELD_COUNT, len(header))
    v.check("T3-schema", "CSV 表头无重复列", len(header) == len(set(header)),
            len(set(header)), len(header))
    v.check("T3-schema", "CSV 表头 == AGENT_RECORDS_FIELDS",
            header == list(SC.AGENT_RECORDS_FIELDS), "identical",
            "mismatch" if header != list(SC.AGENT_RECORDS_FIELDS) else "identical")
    v.check("T3-schema", "CSV 表头不含已废弃字段名",
            not [n for n in REMOVED_FIELD_NAMES if n in header], "[]",
            [n for n in REMOVED_FIELD_NAMES if n in header])


# ══════════════════════════════════════════════════════════════════════
# T4 / T5  记录构造与精度
# ══════════════════════════════════════════════════════════════════════

def _synthetic_inputs(trust_after_decay_raw=6.123456789012345):
    from experiment_config import ExperimentConfig
    config = ExperimentConfig(content_factor="rational-evidence",
                             channel_factor="hub", timing_factor="immediate")
    clr_msg = dict(CLARIFICATION_MSG)
    clr_msg["content_factor"] = "emotional-empathy"
    s_data = {
        "baseline_trust": 6.5,
        # 观察流内同时含澄清与全局事件 → 阶段③ / global_event_received 均应为 True
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
        "trust_after_decay_raw": trust_after_decay_raw,
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
    return config, s_data, plan, thought


def _build(SC, plan_override=None, raw=6.123456789012345,
           s_data_override=None, tick=6,
           is_clarification_target=True, clarification_injected=True):
    config, s_data, plan, thought = _synthetic_inputs(raw)
    if plan_override:
        plan.update(plan_override)
    if s_data_override is not None:
        s_data = dict(s_data)
        s_data.update(s_data_override)
    return SC.build_agent_record(
        config=config, tick=tick, agent_id="Consumer_001",
        cluster_type="Convenient_Greens", social_role="Regular User",
        trust=5.3456789, s_data=s_data, plan=plan, thought=thought,
        out_degree=4, in_degree=2,
        is_clarification_target=is_clarification_target,
        clarification_injected=clarification_injected,
        cumulative_buyers_count=7,
    )


def check_record_builder(v, SC):
    if SC is None:
        v.error("T4-record", "build_agent_record 可用", "simulation_core 未能导入")
        return
    fields = list(SC.AGENT_RECORDS_FIELDS)
    rec = _build(SC)

    v.check("T4-record", "记录字段集合 == schema v2.0",
            set(rec.keys()) == set(fields), "equal",
            "missing=%s extra=%s" % (sorted(set(fields) - set(rec.keys())),
                                     sorted(set(rec.keys()) - set(fields))))
    v.check("T4-record", "记录字段数 == %d" % EXPECTED_FIELD_COUNT,
            len(rec) == EXPECTED_FIELD_COUNT, EXPECTED_FIELD_COUNT, len(rec))
    if list(rec.keys()) != fields:
        v.warn("T4-record", "记录键顺序与 schema 顺序不同（不影响 DictWriter）",
               "order differs")

    # ── 精度：审计字段保留 12 位小数 ──
    raw_value = 6.123456789012345
    v.check("T5-precision", "审计字段保留 12 位小数",
            rec["trust_after_decay_raw"] == round(raw_value, 12),
            round(raw_value, 12), rec["trust_after_decay_raw"])
    v.check("T5-precision", "审计字段未塌陷到 4 位小数",
            rec["trust_after_decay_raw"] != round(raw_value, 4),
            "!= " + str(round(raw_value, 4)), rec["trust_after_decay_raw"])

    # ── 精度：仅第 6 位小数不同的两个输入必须产生不同的审计值 ──
    a = _build(SC, raw=3.1415926535)
    b = _build(SC, raw=3.1415936535)
    v.check("T5-precision", "第 6 位小数差异在审计字段中可分辨",
            a["trust_after_decay_raw"] != b["trust_after_decay_raw"],
            "different", "%s vs %s" % (a["trust_after_decay_raw"], b["trust_after_decay_raw"]))
    v.check("T5-precision", "同一差异在 4 位兼容字段中不可分辨（说明审计字段确有必要）",
            round(3.1415926535, 4) == round(3.1415936535, 4), True, True)

    # ── 旧兼容字段精度保持 round(…,4) ──
    v.check("T5-precision", "旧字段 trust_after_decay 仍为 round(…,4)",
            rec["trust_after_decay"] == round(6.123, 4), round(6.123, 4),
            rec["trust_after_decay"])
    v.check("T5-precision", "旧字段 trust_score 仍为 round(…,4)",
            rec["trust_score"] == round(5.3456789, 4), round(5.3456789, 4), rec["trust_score"])

    # ── 不适用值写空串，禁止写 0 ──
    rec_none = _build(SC, plan_override={"clr_anchor_lift_ratio": "", "clr_lift_raw": ""})
    v.check("T5-precision", "不适用的 clr_anchor_lift_ratio 写空串而非 0",
            rec_none["clr_anchor_lift_ratio"] == "", "''", repr(rec_none["clr_anchor_lift_ratio"]))

    # ── Reflect 审计字段落库 ──
    v.check("T4-record", "raw_affective_output 取自 state（12 位）",
            rec["raw_affective_output"] == round(-2.345678901234, 12),
            round(-2.345678901234, 12), rec["raw_affective_output"])
    v.check("T4-record", "observation_count 取自 last_observations",
            rec["observation_count"] == 2, 2, rec["observation_count"])
    v.check("T4-record", "observation_sources 排序拼接",
            rec["observation_sources"] == "Enterprise_Clarification;Global News",
            "Enterprise_Clarification;Global News", rec["observation_sources"])

    # ── R11 单一快照一致性：四个字段必须同源于同一份 last_observations ──
    # 参照记录 rec：last_observations = [澄清, Global News]
    v.check("T4-record", "R11 快照一致: count>0 且两个 received 均为 True",
            rec["observation_count"] == 2
            and rec["clarification_received"] is True
            and rec["global_event_received"] is True,
            "2 / True / True",
            "%s / %s / %s" % (rec["observation_count"], rec["clarification_received"],
                              rec["global_event_received"]))
    v.check("T4-record", "R11 快照一致: observation_sources 覆盖两个 received 的来源",
            ("Enterprise_Clarification" in rec["observation_sources"].split(";")) ==
            rec["clarification_received"]
            and ("Global News" in rec["observation_sources"].split(";")) ==
            rec["global_event_received"],
            "sources ⟺ received", rec["observation_sources"])

    # 关键用例：last_observations 为空，但 observations 里有内容 →
    # 四个字段必须全部反映"空快照"，证明**没有**回退读取 observations
    clr_only = dict(CLARIFICATION_MSG)
    clr_only["content_factor"] = "emotional-empathy"
    rec_empty = _build(SC, s_data_override={
        "last_observations": [],
        "observations": [clr_only, {"source": "Global News", "content": "x"}],
    })
    v.check("T4-record", "R11 last_observations 为空 → observation_count == 0",
            rec_empty["observation_count"] == 0, 0, rec_empty["observation_count"])
    v.check("T4-record", "R11 last_observations 为空 → observation_sources == ''",
            rec_empty["observation_sources"] == "", "''",
            repr(rec_empty["observation_sources"]))
    v.check("T4-record", "R11 不回退 observations → clarification_received False",
            rec_empty["clarification_received"] is False, False,
            rec_empty["clarification_received"])
    v.check("T4-record", "R11 不回退 observations → global_event_received False",
            rec_empty["global_event_received"] is False, False,
            rec_empty["global_event_received"])

    # _observed_source_present 的签名必须是"接收观察列表"，而不是 s_data
    import inspect as _inspect
    _osp_params = list(_inspect.signature(SC._observed_source_present).parameters.keys())
    v.check("T4-record", "R11 _observed_source_present 首参为观察列表（非 s_data）",
            _osp_params[:1] == ["observations"], "['observations', ...]", _osp_params)
    v.check("T4-record", "R11 _observed_source_present 直接接受列表输入",
            SC._observed_source_present([clr_only], "Enterprise_Clarification",
                                        "clarification") is True
            and SC._observed_source_present([], "Enterprise_Clarification",
                                            "clarification") is False,
            "True / False",
            "%s / %s" % (SC._observed_source_present([clr_only],
                                                     "Enterprise_Clarification",
                                                     "clarification"),
                         SC._observed_source_present([], "Enterprise_Clarification",
                                                     "clarification")))


# ══════════════════════════════════════════════════════════════════════
# T6  run_metadata.json
# ══════════════════════════════════════════════════════════════════════

def check_metadata(v, RX, SC):
    if RX is None:
        v.error("T6-metadata", "write_run_metadata_json 可用", "run_experiments 未能导入")
        return
    import yaml
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "run_metadata.json")
        meta = RX.write_run_metadata_json([], out, project_root=project_root, run_id="TASK002V")
        with open(out, "r", encoding="utf-8") as f:
            raw_text = f.read()

    all_hashes = []
    for rel, h in sorted(meta["source_file_hashes"].items()):
        all_hashes.append(h)
        v.check("T6-metadata", "源文件哈希有效: " + rel, _is_hex64(h), "64-hex", h)
    for group in ("prompt_sources", "persona_sources"):
        for key, item in sorted(meta[group].items()):
            all_hashes.append(item["sha256"])
            v.check("T6-metadata", "%s 哈希有效: %s" % (group, key),
                    _is_hex64(item["sha256"]), "64-hex", item["sha256"])
            abs_path = os.path.join(project_root, *item["path"].split("/"))
            v.check("T6-metadata", "%s 路径由 project_root 解析且存在: %s" % (group, key),
                    os.path.isfile(abs_path), "file exists", item["path"])
    bad = [h for h in all_hashes if not _is_hex64(h)]
    v.check("T6-metadata", "不存在 unknown / missing 哈希", not bad, "[]", bad)

    v.check("T6-metadata", "project_root 来自显式入参",
            meta["project_root"] == project_root, project_root, meta["project_root"])
    if SC is not None:
        v.check("T6-metadata", "元数据内字段清单与 schema 一致",
                meta["agent_records_fields"] == list(SC.AGENT_RECORDS_FIELDS)
                and meta["agent_records_field_count"] == EXPECTED_FIELD_COUNT,
                "%d fields identical" % EXPECTED_FIELD_COUNT,
                meta["agent_records_field_count"])

    # ── R8：git_is_dirty 必须显式存在，且为 bool 或 "unknown"（不得缺省为 False）──
    v.check("T6-metadata", "顶层 git_is_dirty 存在",
            "git_is_dirty" in meta, "present",
            "present" if "git_is_dirty" in meta else "MISSING")
    v.check("T6-metadata", "git_is_dirty 取值合法（bool 或 'unknown'）",
            isinstance(meta.get("git_is_dirty"), bool) or meta.get("git_is_dirty") == "unknown",
            "bool | 'unknown'", repr(meta.get("git_is_dirty")))
    v.check("T6-metadata", "git.is_dirty 与顶层镜像一致",
            meta.get("git", {}).get("is_dirty") == meta.get("git_is_dirty"),
            meta.get("git_is_dirty"), meta.get("git", {}).get("is_dirty"))

    # ── R4：不得再从常量重建全局事件时间线 ──
    v.check("T6-metadata", "已删除 global_event_ticks（不从常量重建）",
            "global_event_ticks" not in meta, "absent",
            "STILL PRESENT" if "global_event_ticks" in meta else "absent")
    v.check("T6-metadata", "effective_event_ticks_union 由结果聚合得出",
            meta.get("effective_event_ticks_union") == [], "[] (results 为空)",
            meta.get("effective_event_ticks_union"))

    # top_p：配置里没有就必须是 "unknown"，禁止填 1.0
    cfg_path = os.path.join(project_root, "configs", "models_config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f)
    entries = [e for e in (conf if isinstance(conf, list) else [conf]) if isinstance(e, dict)]
    entry = next((e for e in entries if "chat" in (e.get("capabilities") or [])),
                 entries[0] if entries else {})
    expected_top_p = entry.get("top_p", "unknown")
    v.check("T6-metadata", "top_p 未配置时记为 unknown（禁止默认 1.0）",
            meta["llm"]["top_p"] == expected_top_p, expected_top_p, meta["llm"]["top_p"])
    v.check("T6-metadata", "temperature 取自真实配置",
            meta["llm"]["temperature"] == entry.get("temperature", "unknown"),
            entry.get("temperature", "unknown"), meta["llm"]["temperature"])

    # 安全：api_key 不得写入产物
    api_key = str(entry.get("api_key", "") or "")
    leaked = bool(api_key) and (api_key in raw_text)
    v.check("T6-metadata", "api_key 未写入元数据", not leaked, "absent",
            "LEAKED" if leaked else "absent")
    v.check("T6-metadata", "api_key_present 标记存在",
            isinstance(meta["llm"].get("api_key_present"), bool), "bool",
            type(meta["llm"].get("api_key_present")).__name__)

    # 网络元数据在无实验时也应结构完整
    v.check("T6-metadata", "experiments 为列表",
            isinstance(meta["experiments"], list), "list",
            type(meta["experiments"]).__name__)


# ══════════════════════════════════════════════════════════════════════
# T7  network_type 与真实建图分支一致
# ══════════════════════════════════════════════════════════════════════

def check_network(v):
    ids20 = _net_ids(20)
    p = SocialNetworkPlugin()
    p.register_agents([_NetAgent(i) for i in ids20], seed=42)
    v.check("T7-network", "n=20 → network_type=barabasi_albert",
            p.network_type == "barabasi_albert", "barabasi_albert", p.network_type)
    v.check("T7-network", "n=20 → network_params 记录 n/m/seed",
            p.network_params == {"n": 20, "m": 2, "seed": 42},
            {"n": 20, "m": 2, "seed": 42}, p.network_params)
    v.check("T7-network", "n=20 → fallback_reason 为空",
            p.network_fallback_reason == "", "''", repr(p.network_fallback_reason))
    exp = _expected_directed(nx.barabasi_albert_graph(20, m=2, seed=42), ids20, 20)
    v.check("T7-network", "声明的 BA 分支与实际图结构一致",
            set(p.graph.nodes()) == set(exp.nodes()) and set(p.graph.edges()) == set(exp.edges()),
            "identical",
            "nodes_eq=%s edges_eq=%s" % (set(p.graph.nodes()) == set(exp.nodes()),
                                         set(p.graph.edges()) == set(exp.edges())))

    ids3 = _net_ids(3)
    p3 = SocialNetworkPlugin()
    p3.register_agents([_NetAgent(i) for i in ids3], seed=42)
    v.check("T7-network", "n=3 → network_type=complete",
            p3.network_type == "complete", "complete", p3.network_type)
    v.check("T7-network", "n=3 → network_params={'n':3}",
            p3.network_params == {"n": 3}, {"n": 3}, p3.network_params)
    exp3 = _expected_directed(nx.complete_graph(3), ids3, 3)
    v.check("T7-network", "声明的 complete 分支与实际图结构一致",
            set(p3.graph.edges()) == set(exp3.edges()), "identical",
            sorted(p3.graph.edges()))

    p0 = SocialNetworkPlugin()
    p0.register_agents([], seed=42)
    v.check("T7-network", "n=0 → network_type=empty",
            p0.network_type == "empty", "empty", p0.network_type)

    # 强制 BA 失败 → 必须真实记录 ER fallback
    original_ba = nx.barabasi_albert_graph

    def _boom(*args, **kwargs):
        raise RuntimeError("forced BA failure for audit test")

    nx.barabasi_albert_graph = _boom
    try:
        pf = SocialNetworkPlugin()
        pf.register_agents([_NetAgent(i) for i in ids20], seed=42)
    finally:
        nx.barabasi_albert_graph = original_ba

    v.check("T7-network", "BA 失败 → network_type=erdos_renyi",
            pf.network_type == "erdos_renyi", "erdos_renyi", pf.network_type)
    v.check("T7-network", "BA 失败 → network_params 记录 n/p/seed",
            pf.network_params == {"n": 20, "p": 0.3, "seed": 42},
            {"n": 20, "p": 0.3, "seed": 42}, pf.network_params)
    v.check("T7-network", "BA 失败 → fallback_reason 记录真实原因",
            pf.network_fallback_reason.startswith("barabasi_albert_failed")
            and "forced BA failure" in pf.network_fallback_reason,
            "barabasi_albert_failed: …", pf.network_fallback_reason)
    exp_er = _expected_directed(nx.erdos_renyi_graph(20, p=0.3, seed=42), ids20, 20)
    v.check("T7-network", "声明的 ER fallback 分支与实际图结构一致",
            set(pf.graph.edges()) == set(exp_er.edges()), "identical",
            "edges_eq=%s" % (set(pf.graph.edges()) == set(exp_er.edges())))


# ══════════════════════════════════════════════════════════════════════
# T8  network_hash：覆盖 nodes + edges，且确定性
# ══════════════════════════════════════════════════════════════════════

def check_network_hash(v, SC):
    if SC is None:
        v.error("T8-hash", "compute_network_hash 可用", "simulation_core 未能导入")
        return
    ids = _net_ids(20)
    p1 = SocialNetworkPlugin()
    p1.register_agents([_NetAgent(i) for i in ids], seed=42)
    p2 = SocialNetworkPlugin()
    p2.register_agents([_NetAgent(i) for i in ids], seed=42)

    h1 = SC.compute_network_hash(p1.graph)
    h2 = SC.compute_network_hash(p2.graph)
    v.check("T8-hash", "hash 为 64 位 hex", _is_hex64(h1), "64-hex", h1)
    v.check("T8-hash", "同 seed 同结构 → hash 相同", h1 == h2, h1, h2)

    g_node = p1.graph.copy()
    g_node.add_node("Consumer_999")
    h_node = SC.compute_network_hash(g_node)
    v.check("T8-hash", "仅新增孤立节点 → hash 改变（证明覆盖 nodes）",
            h_node != h1, "different", "same" if h_node == h1 else "different")

    g_edge = p1.graph.copy()
    g_edge.remove_edge(*next(iter(p1.graph.edges())))
    h_edge = SC.compute_network_hash(g_edge)
    v.check("T8-hash", "仅删除一条边 → hash 改变（证明覆盖 edges）",
            h_edge != h1, "different", "same" if h_edge == h1 else "different")

    # 顺序无关性：节点插入顺序不同但结构相同 → hash 相同
    g_perm = nx.DiGraph()
    g_perm.add_nodes_from(reversed(list(p1.graph.nodes())))
    g_perm.add_edges_from(reversed(list(p1.graph.edges())))
    v.check("T8-hash", "节点/边插入顺序不影响 hash（已排序）",
            SC.compute_network_hash(g_perm) == h1, h1, SC.compute_network_hash(g_perm))


# ══════════════════════════════════════════════════════════════════════
# T9  target_nodes 审计明细
# ══════════════════════════════════════════════════════════════════════

def check_target_nodes(v, SC):
    if SC is None:
        v.error("T9-target", "build_target_nodes_meta 可用", "simulation_core 未能导入")
        return
    from experiment_config import ExperimentConfig
    from node_selector import select_target_nodes

    ids = _net_ids(20)
    p = SocialNetworkPlugin()
    p.register_agents([_NetAgent(i) for i in ids], seed=42)
    out_deg = dict(p.graph.out_degree())

    cfg_hub = ExperimentConfig(content_factor="rational-evidence",
                              channel_factor="hub", timing_factor="immediate")
    hub_nodes = select_target_nodes(p.graph, "hub", cfg_hub.budget_k, cfg_hub.random_seed)
    hub_rows = SC.build_target_nodes_meta(p.graph, cfg_hub, hub_nodes)

    v.check("T9-target", "hub 行数 == budget_k",
            len(hub_rows) == len(hub_nodes), len(hub_nodes), len(hub_rows))
    v.check("T9-target", "hub selection_metric == out_degree",
            all(r["selection_metric"] == "out_degree" for r in hub_rows), "out_degree",
            sorted({r["selection_metric"] for r in hub_rows}))
    v.check("T9-target", "hub metric_value == 真实出度",
            all(r["metric_value"] == out_deg.get(r["agent_id"], 0) for r in hub_rows),
            "matches graph.out_degree()",
            [(r["agent_id"], r["metric_value"], out_deg.get(r["agent_id"])) for r in hub_rows])
    v.check("T9-target", "hub rank 为 1..k",
            [r["rank"] for r in hub_rows] == list(range(1, len(hub_rows) + 1)),
            list(range(1, len(hub_rows) + 1)), [r["rank"] for r in hub_rows])

    cfg_rnd = ExperimentConfig(content_factor="rational-evidence",
                               channel_factor="random", timing_factor="immediate")
    rnd_nodes = select_target_nodes(p.graph, "random", cfg_rnd.budget_k, cfg_rnd.random_seed)
    rnd_rows = SC.build_target_nodes_meta(p.graph, cfg_rnd, rnd_nodes)

    v.check("T9-target", "random selection_metric == random_sample",
            all(r["selection_metric"] == "random_sample" for r in rnd_rows), "random_sample",
            sorted({r["selection_metric"] for r in rnd_rows}))
    v.check("T9-target", "random metric_value 为空串",
            all(r["metric_value"] == "" for r in rnd_rows), "''",
            [repr(r["metric_value"]) for r in rnd_rows])
    v.check("T9-target", "random metric_value 不是 0（不适用不得用 0 表示）",
            all(not isinstance(r["metric_value"], (int, float)) for r in rnd_rows),
            "not numeric", [type(r["metric_value"]).__name__ for r in rnd_rows])
    v.check("T9-target", "random rank 为空串",
            all(r["rank"] == "" for r in rnd_rows), "''",
            [repr(r["rank"]) for r in rnd_rows])


# ══════════════════════════════════════════════════════════════════════
# T11  clarification_content_type 来自实际 observation
# ══════════════════════════════════════════════════════════════════════

async def _run_plan_only(last_observations, current_news, cluster_type="Convenient_Greens"):
    router = DeterministicRouter()
    state_plugin = FakeStatePlugin()
    profile_plugin = FakeProfilePlugin(cluster_type)
    plan_plugin = ConsumerPlanPlugin()
    agent = FakeAgent("Test_Agent_001", router, state_plugin, profile_plugin)
    _wire_plugin(plan_plugin, agent)

    init_trust = INITIAL_TRUST_MAP[cluster_type]
    for key, value in (("trust_score", init_trust), ("baseline_trust", init_trust),
                       ("shock_anchor", init_trust), ("quiet_ticks", 0),
                       ("trust_change_affective", 0.0), ("current_news", current_news),
                       ("last_observations", list(last_observations)),
                       ("latest_thought", None)):
        await state_plugin.set_state(key, value)

    await plan_plugin.execute(6)
    return state_plugin._state_data.get("plan_result", {}) or {}


async def check_clarification_type(v):
    clr_with_factor = dict(CLARIFICATION_MSG)
    clr_with_factor["content_factor"] = "emotional-empathy"

    plan = await _run_plan_only([clr_with_factor], CLARIFICATION_HEADLINE)
    v.check("T11-clarification", "content_type 取自 observation 的 content_factor",
            plan.get("clarification_content_type") == "emotional-empathy",
            "emotional-empathy", plan.get("clarification_content_type"))
    v.check("T11-clarification", "clarification_detected_by_plan 为 True（阶段④）",
            plan.get("clarification_detected_by_plan") is True, True,
            plan.get("clarification_detected_by_plan"))
    v.check("T11-clarification", "旧键 has_clarification_observed 已不再写入",
            "has_clarification_observed" not in plan, "absent",
            "STILL PRESENT" if "has_clarification_observed" in plan else "absent")

    plan2 = await _run_plan_only([dict(CLARIFICATION_MSG)], CLARIFICATION_HEADLINE)
    v.check("T11-clarification", "observation 缺 content_factor → unknown（不猜配置）",
            plan2.get("clarification_content_type") == "unknown", "unknown",
            plan2.get("clarification_content_type"))

    plan3 = await _run_plan_only([{"source": "Global News", "content": SCANDAL_NEWS}], SCANDAL_NEWS)
    v.check("T11-clarification", "无澄清观察 → content_type 为空串",
            plan3.get("clarification_content_type") == "", "''",
            repr(plan3.get("clarification_content_type")))
    v.check("T11-clarification", "无澄清观察 → clarification_detected_by_plan 为 False",
            plan3.get("clarification_detected_by_plan") is False, False,
            plan3.get("clarification_detected_by_plan"))
    v.check("T11-clarification", "全局事件当天 anchor 分支为 global_event",
            plan3.get("anchor_update_branch") == "global_event", "global_event",
            plan3.get("anchor_update_branch"))
    v.check("T11-clarification", "澄清当天 anchor 分支为 clarification",
            plan.get("anchor_update_branch") == "clarification", "clarification",
            plan.get("anchor_update_branch"))

# ══════════════════════════════════════════════════════════════════════
# T13  澄清四阶段 + 事件两阶段：来源独立，互不替代
# ══════════════════════════════════════════════════════════════════════

def check_stage_fields(v, SC):
    """四阶段/两阶段字段必须各自反映**自己那一路输入**。

    做法：构造若干"阶段之间刻意不一致"的输入，断言每个字段等于其指定来源，
    而不是从别的阶段推导。任何一个字段被"顺手用另一个字段填充"都会在此暴露。
    """
    if SC is None:
        v.error("T13-stages", "build_agent_record 可用", "simulation_core 未能导入")
        return

    clr_obs = dict(CLARIFICATION_MSG)
    clr_obs["content_factor"] = "emotional-empathy"
    news_obs = {"source": "Global News", "content": SCANDAL_NEWS}

    # 组合 A：全链路贯通（target ✓ injected ✓ received ✓ detected ✓）
    a = _build(SC, s_data_override={"last_observations": [clr_obs, news_obs]},
               is_clarification_target=True, clarification_injected=True,
               plan_override={"clarification_detected_by_plan": True})
    for name in CLARIFICATION_STAGE_FIELDS:
        v.check("T13-stages", "A 全链路贯通: %s == True" % name,
                a[name] is True, True, a[name])

    # 组合 B：选中但本 Tick 未注入（时机未到）→ ①True ②False ③False ④False
    b = _build(SC, s_data_override={"last_observations": [news_obs]},
               is_clarification_target=True, clarification_injected=False,
               plan_override={"clarification_detected_by_plan": False})
    v.check("T13-stages", "B ①target=True", b["is_clarification_target"] is True, True,
            b["is_clarification_target"])
    v.check("T13-stages", "B ②injected=False（未由 target 推断）",
            b["clarification_injected"] is False, False, b["clarification_injected"])
    v.check("T13-stages", "B ③received=False（观察流中无澄清）",
            b["clarification_received"] is False, False, b["clarification_received"])

    # 组合 C：已注入但被信箱限流挤掉 → ②True ③False（关键断裂用例）
    c = _build(SC, s_data_override={"last_observations": [news_obs, news_obs, news_obs]},
               is_clarification_target=True, clarification_injected=True,
               plan_override={"clarification_detected_by_plan": False})
    v.check("T13-stages", "C ②injected=True", c["clarification_injected"] is True, True,
            c["clarification_injected"])
    v.check("T13-stages", "C ③received=False（未由 injected 推断）",
            c["clarification_received"] is False, False, c["clarification_received"])
    v.check("T13-stages", "C ④detected=False（取自 plan_result）",
            c["clarification_detected_by_plan"] is False, False,
            c["clarification_detected_by_plan"])

    # 组合 D：收到了但 Plan 没识别 → ③True ④False（received 不得由 detected 顶替）
    d = _build(SC, s_data_override={"last_observations": [clr_obs]},
               is_clarification_target=True, clarification_injected=True,
               plan_override={"clarification_detected_by_plan": False})
    v.check("T13-stages", "D ③received=True（记录器独立判定）",
            d["clarification_received"] is True, True, d["clarification_received"])
    v.check("T13-stages", "D ④detected=False（与 ③ 分离）",
            d["clarification_detected_by_plan"] is False, False,
            d["clarification_detected_by_plan"])

    # 组合 E：非目标节点却收到澄清（社交转述等异常路径）→ ①False ③True
    e = _build(SC, s_data_override={"last_observations": [clr_obs]},
               is_clarification_target=False, clarification_injected=False,
               plan_override={"clarification_detected_by_plan": True})
    v.check("T13-stages", "E ①target=False 而 ③received=True 可同时记录",
            e["is_clarification_target"] is False and e["clarification_received"] is True,
            "False/True",
            "%s/%s" % (e["is_clarification_target"], e["clarification_received"]))

    # 四个字段在同一条记录内确实是 4 个独立键，且四种"断裂组合"全部可达
    v.check("T13-stages", "四阶段为 4 个独立键",
            len({k for k in CLARIFICATION_STAGE_FIELDS if k in a}) == 4, 4,
            [k for k in CLARIFICATION_STAGE_FIELDS if k not in a])
    combos = {tuple(rec[k] for k in CLARIFICATION_STAGE_FIELDS)
              for rec in (a, b, c, d, e)}
    expected_combos = {(True, True, True, True), (True, False, False, False),
                       (True, True, False, False), (True, True, True, False),
                       (False, False, True, True)}
    v.check("T13-stages", "五种阶段组合全部可达（证明互不推导）",
            combos == expected_combos, sorted(expected_combos), sorted(combos))

    # ── 全局事件两阶段：received 只能来自观察流 ──
    scandal_tick = sorted(SC.ENTERPRISE_STRATEGY.keys())[0]
    quiet_tick = max(SC.ENTERPRISE_STRATEGY.keys()) + 7

    # F：事件 Tick 但该 Agent 没观察到 Global News → scheduled=True, received=False
    f = _build(SC, tick=scandal_tick,
               s_data_override={"last_observations": [clr_obs]})
    v.check("T13-stages", "F 事件 Tick → global_event_scheduled=True",
            f["global_event_scheduled"] is True, True, f["global_event_scheduled"])
    v.check("T13-stages", "F 未观察到 → global_event_received=False（禁止 tick 推断）",
            f["global_event_received"] is False, False, f["global_event_received"])

    # G：非事件 Tick 但观察流里确有 Global News → scheduled=False, received=True
    g = _build(SC, tick=quiet_tick,
               s_data_override={"last_observations": [news_obs]})
    v.check("T13-stages", "G 非事件 Tick → global_event_scheduled=False",
            g["global_event_scheduled"] is False, False, g["global_event_scheduled"])
    v.check("T13-stages", "G 观察到 → global_event_received=True（只看观察流）",
            g["global_event_received"] is True, True, g["global_event_received"])

    # has_global_event 作为 v1.0 兼容别名，值恒等于 global_event_scheduled
    for rec, label in ((f, "F"), (g, "G")):
        v.check("T13-stages", "%s has_global_event == global_event_scheduled" % label,
                rec["has_global_event"] == rec["global_event_scheduled"],
                rec["global_event_scheduled"], rec["has_global_event"])

    # ── R11 组合 H：last_observations 为空，observations 里却有澄清与 Global News ──
    # 第四轮的实现会回退读 observations 并把两个 received 判成 True（假阳性）。
    # 本轮删除回退后，H 的四个断言全部要求"空快照 → False"。
    h = _build(SC, tick=scandal_tick,
               s_data_override={"last_observations": [],
                                "observations": [clr_obs, news_obs]},
               is_clarification_target=True, clarification_injected=True,
               plan_override={"clarification_detected_by_plan": False})
    v.check("T13-stages", "H ③received=False（不回退 observations）",
            h["clarification_received"] is False, False, h["clarification_received"])
    v.check("T13-stages", "H global_event_received=False（不回退 observations）",
            h["global_event_received"] is False, False, h["global_event_received"])
    v.check("T13-stages", "H observation_count=0 与两个 received 一致（单一快照）",
            h["observation_count"] == 0
            and h["clarification_received"] is False
            and h["global_event_received"] is False,
            "0 / False / False",
            "%s / %s / %s" % (h["observation_count"], h["clarification_received"],
                              h["global_event_received"]))
    v.check("T13-stages", "H ②injected=True 仍照实记录（阶段②不受快照影响）",
            h["clarification_injected"] is True, True, h["clarification_injected"])
    v.check("T13-stages", "H 暴露的正是「已注入但未进入观察流」的断裂（②T ③F）",
            h["clarification_injected"] is True and h["clarification_received"] is False,
            "True/False",
            "%s/%s" % (h["clarification_injected"], h["clarification_received"]))


# ══════════════════════════════════════════════════════════════════════
# T14  ClarificationInjector 回执语义（签名与返回类型不变）
# ══════════════════════════════════════════════════════════════════════

class _InjAgent:
    """带 state 组件的最小 Agent 壳，供 injector.inject() 使用。"""

    def __init__(self, agent_id):
        self.agent_id = agent_id
        self._state = FakeStatePlugin()
        self._components = {"state": FakeComponent(self._state)}

    def get_component(self, name):
        return self._components.get(name)


async def check_injector_receipt(v):
    import inspect
    from clarification_injector import ClarificationInjector
    from experiment_config import ExperimentConfig

    sig = inspect.signature(ClarificationInjector.inject)
    v.check("T14-injector", "inject 签名保持 (self, agents, current_tick)",
            list(sig.parameters.keys()) == ["self", "agents", "current_tick"],
            "['self','agents','current_tick']", list(sig.parameters.keys()))
    v.check("T14-injector", "inject 返回标注仍为 int",
            sig.return_annotation is int, "int", sig.return_annotation)

    cfg = ExperimentConfig(content_factor="rational-evidence",
                           channel_factor="hub", timing_factor="immediate")
    inj = ClarificationInjector(cfg)
    agents = [_InjAgent("Consumer_%03d" % i) for i in range(5)]
    targets = ["Consumer_001", "Consumer_003"]
    inj.set_target_nodes(targets)

    v.check("T14-injector", "初始 last_injected_ids 为空列表",
            getattr(inj, "last_injected_ids", None) == [], [],
            getattr(inj, "last_injected_ids", None))

    # 非注入 Tick：返回 0 且回执为空
    n0 = await inj.inject(agents, cfg.clarification_tick + 1)
    v.check("T14-injector", "非注入 Tick 返回 0", n0 == 0, 0, n0)
    v.check("T14-injector", "非注入 Tick 回执为空",
            getattr(inj, "last_injected_ids", None) == [], [],
            getattr(inj, "last_injected_ids", None))

    # 注入 Tick：返回值 == len(回执)，回执 ⊆ target_nodes，且真的写进了 inbox
    n1 = await inj.inject(agents, cfg.clarification_tick)
    receipt = getattr(inj, "last_injected_ids", None) or []
    v.check("T14-injector", "返回值 == len(last_injected_ids)",
            n1 == len(receipt), n1, len(receipt))
    v.check("T14-injector", "返回值类型为 int", isinstance(n1, int), "int",
            type(n1).__name__)
    v.check("T14-injector", "回执 ⊆ target_nodes",
            set(receipt) <= set(targets), sorted(targets), sorted(receipt))
    v.check("T14-injector", "回执 == 实际收到消息的 Agent",
            sorted(receipt) == sorted(
                a.agent_id for a in agents
                if any(m.get("source") == "Enterprise_Clarification"
                       for m in (a._state.get_state_sync("incoming_messages") or []))),
            sorted(targets), sorted(receipt))
    v.check("T14-injector", "消息包携带 content_factor",
            inj.get_message().get("content_factor") == cfg.content_factor,
            cfg.content_factor, inj.get_message().get("content_factor"))

    # 后续非注入 Tick 必须清空回执（防止阶段②跨 Tick 泄漏）
    await inj.inject(agents, cfg.clarification_tick + 2)
    v.check("T14-injector", "后续 Tick 回执被重置（无跨 Tick 泄漏）",
            getattr(inj, "last_injected_ids", None) == [], [],
            getattr(inj, "last_injected_ids", None))


# ══════════════════════════════════════════════════════════════════════
# T15  network_nodes.csv / network_edges.csv / experiment_metadata.jsonl
# ══════════════════════════════════════════════════════════════════════

# ExperimentConfig 是 frozen dataclass 且 exp_id 是只读 property，
# 因此测试用不同的因子组合来获得不同 exp_id，绝不试图赋值 exp_id。
OK_FACTORS = ("rational-evidence", "hub", "immediate")        # → "Rational-Hub-Imm"
BAD_FACTORS = ("emotional-empathy", "random", "delay-3")      # → "Empathy-Random-D3"
# 第三组：用于"两个成功实验"的一致性用例。exp_id 必须与 OK / BAD 都不同——
# 否则 run 级写入函数按 source_exp_id 回查结果时可能命中失败组（无 network_nodes）。
THIRD_FACTORS = ("rational-evidence", "random", "immediate")   # → "Rational-Random-Imm"


def _cfg(factors):
    from experiment_config import ExperimentConfig
    return ExperimentConfig(content_factor=factors[0],
                            channel_factor=factors[1],
                            timing_factor=factors[2])


def _fake_result(factors, SC, ok=True, n_agents=8, seed=42):
    """构造一个逼真的实验结果。

    n_agents / seed 可变，用于制造"拓扑不同"的结果，验证 R10 的一致性拒绝分支。
    失败结果按 R12 同样携带 config.to_dict()。
    """
    cfg = _cfg(factors)
    if not ok:
        return {"exp_id": cfg.exp_id,
                # R12：异常结果也必须带 config
                "config": cfg.to_dict(),
                "error": "boom", "error_type": "RuntimeError",
                "run_audit": {"started_at": "2026-07-31T10:00:00",
                              "finished_at": "2026-07-31T10:00:05",
                              "recording_cache_size": "", "replay_miss_count": "",
                              "router_role": "replay"}}
    ids = _net_ids(n_agents)
    p = SocialNetworkPlugin()
    p.register_agents([_NetAgent(i) for i in ids], seed=seed)
    agents = [_InjAgent(i) for i in ids]
    for ag in agents:                       # 给 profile 组件补上真实结构
        ag._components["profile"] = FakeComponent(FakeProfilePlugin("Convenient_Greens"))
    targets = ids[:2]
    return {
        "exp_id": cfg.exp_id,
        "config": cfg.to_dict(),
        # R10：run 级构造函数，不接收 config / target_nodes
        "network_nodes": SC.build_network_nodes_meta(p, agents),
        "network_edges": SC.build_network_edges_meta(p),
        "network_meta": SC.build_network_meta(p, cfg),
        "target_nodes_meta": SC.build_target_nodes_meta(p.graph, cfg, targets),
        "agent_records": [],
        "effective_event_timeline": [
            {"tick": 5, "content_sha256": "0" * 64, "char_count": 123}],
        "run_audit": {"started_at": "2026-07-31T09:00:00",
                      "finished_at": "2026-07-31T09:04:00",
                      "recording_cache_size": 240, "replay_miss_count": 0,
                      "router_role": "replay"},
        "_plugin": p, "_targets": targets,
    }


def check_new_artifacts(v, RX, SC):
    """R10：run 级网络文件契约 + 一致性拒绝写出；R12：experiment_metadata 18 字段。"""
    if RX is None or SC is None:
        v.error("T15-artifacts", "新产物写入函数可用", "模块未能导入")
        return
    ok = _fake_result(OK_FACTORS, SC)
    bad = _fake_result(BAD_FACTORS, SC, ok=False)
    ok_id, bad_id = ok["exp_id"], bad["exp_id"]
    results = [ok, bad]

    # ── 列契约常量：两个 run 级文件都不得含 exp_id ──
    v.check("T15-artifacts", "NETWORK_NODES_FIELDS 为 5 列且无 exp_id",
            list(RX.NETWORK_NODES_FIELDS) == ["agent_id", "cluster_type", "social_role",
                                              "out_degree", "in_degree"],
            "5 cols w/o exp_id", list(RX.NETWORK_NODES_FIELDS))
    v.check("T15-artifacts", "NETWORK_NODES_FIELDS 不含 is_clarification_target",
            "is_clarification_target" not in RX.NETWORK_NODES_FIELDS, "absent",
            list(RX.NETWORK_NODES_FIELDS))
    v.check("T15-artifacts", "NETWORK_EDGES_FIELDS 为 3 列且无 exp_id",
            list(RX.NETWORK_EDGES_FIELDS) == ["source_agent_id", "target_agent_id",
                                              "is_directed"],
            "3 cols w/o exp_id", list(RX.NETWORK_EDGES_FIELDS))

    # ── 构造函数签名：R10 已去掉 config / target_nodes ──
    import inspect as _inspect
    _np = list(_inspect.signature(SC.build_network_nodes_meta).parameters.keys())
    _ep = list(_inspect.signature(SC.build_network_edges_meta).parameters.keys())
    v.check("T15-artifacts", "build_network_nodes_meta(net_plugin, agents)",
            _np == ["net_plugin", "agents"], "['net_plugin','agents']", _np)
    v.check("T15-artifacts", "build_network_edges_meta(net_plugin)",
            _ep == ["net_plugin"], "['net_plugin']", _ep)
    v.check("T15-artifacts", "节点行内无 exp_id / 无 is_clarification_target",
            all(("exp_id" not in row) and ("is_clarification_target" not in row)
                for row in ok["network_nodes"]), "absent",
            sorted(ok["network_nodes"][0].keys()))
    v.check("T15-artifacts", "边行内无 exp_id",
            all("exp_id" not in row for row in ok["network_edges"]), "absent",
            sorted(ok["network_edges"][0].keys()))
    # 目标身份的唯一落点仍是 target_nodes.csv 的行数据
    v.check("T15-artifacts", "目标身份仍完整保留在 target_nodes_meta 中",
            sorted(r["agent_id"] for r in ok["target_nodes_meta"]) == sorted(ok["_targets"])
            and all({"selection_metric", "metric_value", "rank",
                     "content_factor", "channel_factor", "timing_factor"} <= set(r)
                    for r in ok["target_nodes_meta"]),
            "targets + metric + factors",
            sorted(ok["target_nodes_meta"][0].keys()))

    # ── 一致性验证：同一 (n, seed) 的两组实验必须判 consistent ──
    ok3 = _fake_result(THIRD_FACTORS, SC)        # 不同因子、同拓扑（n=8, seed=42）
    ver_multi = RX.verify_single_network([ok, ok3])
    v.check("T15-artifacts", "同拓扑多实验 → status=consistent",
            ver_multi["status"] == "consistent", "consistent", ver_multi["status"])
    v.check("T15-artifacts", "consistent 时 hash_groups 只有一组",
            len(ver_multi["hash_groups"]) == 1, 1, len(ver_multi["hash_groups"]))
    v.check("T15-artifacts", "source_exp_id 为字典序最小的成功 exp_id（确定性）",
            ver_multi["source_exp_id"] == min(ok_id, ok3["exp_id"]),
            min(ok_id, ok3["exp_id"]), ver_multi["source_exp_id"])
    v.check("T15-artifacts", "network_hash 等于真实图指纹",
            ver_multi["network_hash"] == SC.compute_network_hash(ok["_plugin"].graph),
            "compute_network_hash(graph)", ver_multi["network_hash"][:12])

    # 写出用的验证结果取自 results 本身（1 成功 + 1 失败 → source_exp_id == ok_id）
    ver_ok = RX.verify_single_network(results)
    v.check("T15-artifacts", "失败实验被排除后仍判 consistent（source == 成功组）",
            ver_ok["status"] == "consistent" and ver_ok["source_exp_id"] == ok_id,
            "consistent / " + ok_id,
            "%s / %s" % (ver_ok["status"], ver_ok["source_exp_id"]))
    v.check("T15-artifacts", "checked_experiments 只计成功实验",
            ver_ok["checked_experiments"] == 1, 1, ver_ok["checked_experiments"])

    with tempfile.TemporaryDirectory() as tmp:
        nodes_path = os.path.join(tmp, "network_nodes.csv")
        edges_path = os.path.join(tmp, "network_edges.csv")
        meta_path = os.path.join(tmp, "experiment_metadata.jsonl")
        wrote_n = RX.write_network_nodes_csv(results, nodes_path, ver_ok)
        wrote_e = RX.write_network_edges_csv(results, edges_path, ver_ok)
        RX.write_experiment_metadata_jsonl(results, meta_path)

        with open(nodes_path, "r", encoding="utf-8", newline="") as f:
            node_rows = list(csv.DictReader(f))
        with open(edges_path, "r", encoding="utf-8", newline="") as f:
            edge_rows = list(csv.DictReader(f))
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_rows = [json.loads(ln) for ln in f if ln.strip()]

    plugin = ok["_plugin"]
    degrees = plugin.export_node_degrees()
    v.check("T15-artifacts", "consistent 时两个写入函数均返回 True",
            wrote_n is True and wrote_e is True, "True / True",
            "%s / %s" % (wrote_n, wrote_e))

    # ── network_nodes.csv（run 级，一份）──
    v.check("T15-artifacts", "nodes 行数 == 图节点数（run 级，不乘实验数）",
            len(node_rows) == plugin.graph.number_of_nodes(),
            plugin.graph.number_of_nodes(), len(node_rows))
    v.check("T15-artifacts", "nodes 表头恰为 5 列（无 exp_id / 无目标标记）",
            list(node_rows[0].keys()) == list(RX.NETWORK_NODES_FIELDS),
            list(RX.NETWORK_NODES_FIELDS), list(node_rows[0].keys()))
    v.check("T15-artifacts", "nodes 无重复 agent_id（每节点恰一行）",
            len({r["agent_id"] for r in node_rows}) == len(node_rows),
            len(node_rows), len({r["agent_id"] for r in node_rows}))
    v.check("T15-artifacts", "nodes 度数 == 真实图度数",
            all(int(r["out_degree"]) == degrees[r["agent_id"]]["out_degree"]
                and int(r["in_degree"]) == degrees[r["agent_id"]]["in_degree"]
                for r in node_rows), "matches graph",
            [(r["agent_id"], r["out_degree"], r["in_degree"]) for r in node_rows[:3]])

    # ── network_edges.csv（run 级，一份）──
    v.check("T15-artifacts", "edges 行数 == 图边数（run 级，不乘实验数）",
            len(edge_rows) == plugin.graph.number_of_edges(),
            plugin.graph.number_of_edges(), len(edge_rows))
    v.check("T15-artifacts", "edges 表头恰为 3 列（无 exp_id）",
            list(edge_rows[0].keys()) == list(RX.NETWORK_EDGES_FIELDS),
            list(RX.NETWORK_EDGES_FIELDS), list(edge_rows[0].keys()))
    v.check("T15-artifacts", "edges 集合 == 图边集合",
            {(r["source_agent_id"], r["target_agent_id"]) for r in edge_rows}
            == {(str(u), str(v_)) for u, v_ in plugin.graph.edges()},
            "identical", "mismatch")
    v.check("T15-artifacts", "edges 按字典序（可复现）",
            [(r["source_agent_id"], r["target_agent_id"]) for r in edge_rows]
            == sorted((r["source_agent_id"], r["target_agent_id"]) for r in edge_rows),
            "sorted", "unsorted")

    # ── R10 关键用例：拓扑不一致 → 拒绝写出 + 报告 ──
    # exp_id 与 ok 不同（THIRD_FACTORS），拓扑刻意不同（n=9, seed=7）
    diff_net = _fake_result(THIRD_FACTORS, SC, n_agents=9, seed=7)
    ver_bad = RX.verify_single_network([ok, diff_net])
    v.check("T15-artifacts", "拓扑不一致 → status=inconsistent",
            ver_bad["status"] == "inconsistent", "inconsistent", ver_bad["status"])
    v.check("T15-artifacts", "不一致报告含 2 个哈希分组",
            len(ver_bad["hash_groups"]) == 2, 2, len(ver_bad["hash_groups"]))
    v.check("T15-artifacts", "不一致时不给出 source_exp_id / network_hash",
            ver_bad["source_exp_id"] == "" and ver_bad["network_hash"] == "",
            "'' / ''", "%r / %r" % (ver_bad["source_exp_id"], ver_bad["network_hash"]))
    v.check("T15-artifacts", "不一致时 refused_outputs 列出两个网络文件",
            sorted(ver_bad["refused_outputs"]) == ["network_edges.csv",
                                                   "network_nodes.csv"],
            ["network_edges.csv", "network_nodes.csv"], ver_bad["refused_outputs"])
    v.check("T15-artifacts", "per_experiment 含 random_seed / num_agents 诊断项",
            all({"random_seed", "num_agents", "network_type", "network_params"} <= set(e)
                for e in ver_bad["per_experiment"]), "diagnostic keys present",
            sorted(ver_bad["per_experiment"][0].keys()))

    with tempfile.TemporaryDirectory() as tmp:
        n2 = os.path.join(tmp, "network_nodes.csv")
        e2 = os.path.join(tmp, "network_edges.csv")
        rep = os.path.join(tmp, "network_inconsistency_report.json")
        r_n = RX.write_network_nodes_csv([ok, diff_net], n2, ver_bad)
        r_e = RX.write_network_edges_csv([ok, diff_net], e2, ver_bad)
        RX.write_network_inconsistency_report(ver_bad, rep)
        exists_n, exists_e = os.path.exists(n2), os.path.exists(e2)
        with open(rep, "r", encoding="utf-8") as f:
            report = json.load(f)

    v.check("T15-artifacts", "不一致时写入函数返回 False",
            r_n is False and r_e is False, "False / False", "%s / %s" % (r_n, r_e))
    v.check("T15-artifacts", "不一致时**连表头都不写**（文件不存在）",
            (not exists_n) and (not exists_e), "both absent",
            "nodes=%s edges=%s" % (exists_n, exists_e))
    v.check("T15-artifacts", "不一致报告落盘且含 reason / hash_groups / remedy",
            all(k in report for k in ("status", "reason", "hash_groups",
                                      "per_experiment", "refused_outputs", "remedy")),
            "all keys", sorted(report.keys()))

    # ── 12 组全失败 → unavailable，同样拒绝写出（fail-closed）──
    ver_none = RX.verify_single_network([bad])
    v.check("T15-artifacts", "无成功实验 → status=unavailable",
            ver_none["status"] == "unavailable", "unavailable", ver_none["status"])
    with tempfile.TemporaryDirectory() as tmp:
        n3 = os.path.join(tmp, "network_nodes.csv")
        v.check("T15-artifacts", "unavailable 时同样不写出",
                RX.write_network_nodes_csv([bad], n3, ver_none) is False
                and not os.path.exists(n3), "False / absent",
                "exists=%s" % os.path.exists(n3))

    # ── run_metadata 记录一致性结论 ──
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "run_metadata.json")
        meta_ok = RX.write_run_metadata_json([ok, ok3], out, project_root=project_root,
                                            run_id="T15", network_verification=ver_multi)
        out2 = os.path.join(tmp, "run_metadata_bad.json")
        meta_bad = RX.write_run_metadata_json([ok, diff_net], out2,
                                             project_root=project_root, run_id="T15b",
                                             network_verification=ver_bad)
        out3 = os.path.join(tmp, "run_metadata_nv.json")
        meta_nv = RX.write_run_metadata_json([ok], out3, project_root=project_root,
                                            run_id="T15c")
    v.check("T15-artifacts", "run_metadata.network_consistency 记录 consistent",
            meta_ok["network_consistency"]["status"] == "consistent", "consistent",
            meta_ok["network_consistency"]["status"])
    v.check("T15-artifacts", "run_metadata.network_consistency 记录 inconsistent",
            meta_bad["network_consistency"]["status"] == "inconsistent", "inconsistent",
            meta_bad["network_consistency"]["status"])
    v.check("T15-artifacts", "未传验证结果时记 not_verified（不冒充 consistent）",
            meta_nv["network_consistency"]["status"] == "not_verified", "not_verified",
            meta_nv["network_consistency"]["status"])

    # ── experiment_metadata.jsonl（R12：18 字段）──
    v.check("T15-artifacts", "EXPERIMENT_METADATA_FIELDS 恰为 18 个且无重复",
            len(RX.EXPERIMENT_METADATA_FIELDS) == 18
            and len(set(RX.EXPERIMENT_METADATA_FIELDS)) == 18,
            18, len(RX.EXPERIMENT_METADATA_FIELDS))
    for name in ("content_factor", "channel_factor", "timing_factor",
                 "clarification_tick", "random_seed", "budget_k",
                 "target_nodes", "network_hash", "effective_event_timeline"):
        v.check("T15-artifacts", "R12 新增字段在契约内: " + name,
                name in RX.EXPERIMENT_METADATA_FIELDS, "present",
                name in RX.EXPERIMENT_METADATA_FIELDS)
    v.check("T15-artifacts", "jsonl 每个 exp_id 一行（含失败组）",
            [r["exp_id"] for r in meta_rows] == [ok_id, bad_id],
            [ok_id, bad_id], [r["exp_id"] for r in meta_rows])
    for row in meta_rows:
        v.check("T15-artifacts", "jsonl 字段集合固定: " + row["exp_id"],
                set(row.keys()) == set(RX.EXPERIMENT_METADATA_FIELDS),
                sorted(RX.EXPERIMENT_METADATA_FIELDS), sorted(row.keys()))
    r_ok = meta_rows[0]
    r_bad = meta_rows[1]
    cfg_ok = _cfg(OK_FACTORS)
    cfg_bad = _cfg(BAD_FACTORS)
    v.check("T15-artifacts", "成功组 success=True", r_ok["success"] is True, True,
            r_ok["success"])
    v.check("T15-artifacts", "成功组 error/error_type 为空串",
            r_ok["error"] == "" and r_ok["error_type"] == "", "'' / ''",
            "%r / %r" % (r_ok["error"], r_ok["error_type"]))
    v.check("T15-artifacts", "started_at / finished_at 取自 run_audit",
            r_ok["started_at"] == "2026-07-31T09:00:00"
            and r_ok["finished_at"] == "2026-07-31T09:04:00",
            "run_audit values", "%s..%s" % (r_ok["started_at"], r_ok["finished_at"]))
    v.check("T15-artifacts", "recording_cache_size 取自真实缓存规模",
            r_ok["recording_cache_size"] == 240, 240, r_ok["recording_cache_size"])
    v.check("T15-artifacts", "replay_miss_count=0 与 ''（不适用）可区分",
            r_ok["replay_miss_count"] == 0 and r_bad["replay_miss_count"] == "",
            "0 / ''", "%r / %r" % (r_ok["replay_miss_count"], r_bad["replay_miss_count"]))
    v.check("T15-artifacts", "失败组 success=False 且 error_type 有值",
            r_bad["success"] is False and r_bad["error_type"] == "RuntimeError",
            "False / RuntimeError",
            "%s / %s" % (r_bad["success"], r_bad["error_type"]))

    # R12：因子/seed/预算取自 config，成功与失败组都有
    v.check("T15-artifacts", "R12 成功组三因子取自 config",
            (r_ok["content_factor"], r_ok["channel_factor"], r_ok["timing_factor"])
            == (cfg_ok.content_factor, cfg_ok.channel_factor, cfg_ok.timing_factor),
            (cfg_ok.content_factor, cfg_ok.channel_factor, cfg_ok.timing_factor),
            (r_ok["content_factor"], r_ok["channel_factor"], r_ok["timing_factor"]))
    v.check("T15-artifacts", "R12 失败组同样有三因子（config 已保存）",
            (r_bad["content_factor"], r_bad["channel_factor"], r_bad["timing_factor"])
            == (cfg_bad.content_factor, cfg_bad.channel_factor, cfg_bad.timing_factor),
            (cfg_bad.content_factor, cfg_bad.channel_factor, cfg_bad.timing_factor),
            (r_bad["content_factor"], r_bad["channel_factor"], r_bad["timing_factor"]))
    v.check("T15-artifacts", "R12 random_seed 用真实属性名取值",
            r_ok["random_seed"] == cfg_ok.random_seed
            and r_bad["random_seed"] == cfg_bad.random_seed,
            cfg_ok.random_seed, "%s / %s" % (r_ok["random_seed"], r_bad["random_seed"]))
    v.check("T15-artifacts", "R12 budget_k 取自 config",
            r_ok["budget_k"] == cfg_ok.budget_k, cfg_ok.budget_k, r_ok["budget_k"])
    v.check("T15-artifacts", "R12 clarification_tick 取自 property（immediate = scandal+1）",
            r_ok["clarification_tick"] == cfg_ok.clarification_tick,
            cfg_ok.clarification_tick, r_ok["clarification_tick"])
    v.check("T15-artifacts", "R12 target_nodes == 真实选点",
            r_ok["target_nodes"] == [row_["agent_id"] for row_ in ok["target_nodes_meta"]],
            [row_["agent_id"] for row_ in ok["target_nodes_meta"]], r_ok["target_nodes"])
    v.check("T15-artifacts", "R12 network_hash == 真实图指纹",
            r_ok["network_hash"] == SC.compute_network_hash(plugin.graph),
            "compute_network_hash(graph)", r_ok["network_hash"][:12])
    v.check("T15-artifacts", "R12 effective_event_timeline 原样透传（只有 Tick 5）",
            [e["tick"] for e in r_ok["effective_event_timeline"]] == [5], [5],
            [e["tick"] for e in r_ok["effective_event_timeline"]])
    v.check("T15-artifacts", "R12 失败组的三个结果类字段记空（不猜测）",
            r_bad["target_nodes"] == [] and r_bad["network_hash"] == ""
            and r_bad["effective_event_timeline"] == [],
            "[] / '' / []",
            "%r / %r / %r" % (r_bad["target_nodes"], r_bad["network_hash"],
                              r_bad["effective_event_timeline"]))

    # no-clarification 的 clarification_tick 必须是 ""，不是 0
    noclr = _fake_result(("rational-evidence", "hub", "no-clarification"), SC)
    with tempfile.TemporaryDirectory() as tmp:
        p_noclr = os.path.join(tmp, "experiment_metadata.jsonl")
        RX.write_experiment_metadata_jsonl([noclr], p_noclr)
        with open(p_noclr, "r", encoding="utf-8") as f:
            row_noclr = json.loads(f.readline())
    v.check("T15-artifacts", "R12 no-clarification 的 clarification_tick 为 ''（非 0）",
            row_noclr["clarification_tick"] == ""
            and not isinstance(row_noclr["clarification_tick"], int),
            "''", repr(row_noclr["clarification_tick"]))


# ══════════════════════════════════════════════════════════════════════
# T16  effective_event_timeline 取自实验结果，不从常量重建
# ══════════════════════════════════════════════════════════════════════

def check_effective_timeline(v, RX, SC):
    if RX is None or SC is None:
        v.error("T16-timeline", "时间线相关函数可用", "模块未能导入")
        return

    # 运行期快照函数本身：对"被 patch 成只剩 Tick 5"的字典取值
    single = {5: SC.ENTERPRISE_STRATEGY[5]}
    tl = SC.build_effective_event_timeline(single)
    v.check("T16-timeline", "快照只含实际生效的 Tick",
            [e["tick"] for e in tl] == [5], [5], [e["tick"] for e in tl])
    v.check("T16-timeline", "快照记录内容哈希（64-hex）",
            _is_hex64(tl[0]["content_sha256"]), "64-hex", tl[0]["content_sha256"])
    v.check("T16-timeline", "快照记录字符数",
            tl[0]["char_count"] == len(str(single[5])), len(str(single[5])),
            tl[0]["char_count"])
    v.check("T16-timeline", "完整常量的快照含全部 4 个 Tick（对照）",
            [e["tick"] for e in SC.build_effective_event_timeline(SC.ENTERPRISE_STRATEGY)]
            == sorted(SC.ENTERPRISE_STRATEGY.keys()),
            sorted(SC.ENTERPRISE_STRATEGY.keys()),
            [e["tick"] for e in
             SC.build_effective_event_timeline(SC.ENTERPRISE_STRATEGY)])

    # run_metadata 必须原样透传结果里的时间线，且不引用常量
    ok = _fake_result(OK_FACTORS, SC)        # 其 effective_event_timeline 只有 Tick 5
    bad = _fake_result(BAD_FACTORS, SC, ok=False)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "run_metadata.json")
        meta = RX.write_run_metadata_json([ok, bad], out, project_root=project_root,
                                          run_id="T16")
    entry_ok = next(e for e in meta["experiments"] if e["exp_id"] == ok["exp_id"])
    entry_bad = next(e for e in meta["experiments"] if e["exp_id"] == bad["exp_id"])

    v.check("T16-timeline", "run_metadata 无 global_event_ticks 键",
            "global_event_ticks" not in meta, "absent",
            "STILL PRESENT" if "global_event_ticks" in meta else "absent")
    v.check("T16-timeline", "entry 时间线原样来自结果（只有 Tick 5）",
            [e["tick"] for e in entry_ok["effective_event_timeline"]] == [5], [5],
            [e["tick"] for e in entry_ok["effective_event_timeline"]])
    v.check("T16-timeline", "未从 ENTERPRISE_STRATEGY 重建（不等于常量的 4 个 Tick）",
            [e["tick"] for e in entry_ok["effective_event_timeline"]]
            != sorted(SC.ENTERPRISE_STRATEGY.keys()), "!= constant ticks",
            [e["tick"] for e in entry_ok["effective_event_timeline"]])
    v.check("T16-timeline", "时间线来源标注正确",
            entry_ok["effective_event_timeline_source"].startswith("run_simulation_core"),
            "run_simulation_core (runtime snapshot)",
            entry_ok["effective_event_timeline_source"])
    v.check("T16-timeline", "失败实验时间线为空且标注 unavailable",
            entry_bad["effective_event_timeline"] == []
            and "unavailable" in entry_bad["effective_event_timeline_source"],
            "[] / unavailable",
            "%s / %s" % (entry_bad["effective_event_timeline"],
                         entry_bad["effective_event_timeline_source"]))
    v.check("T16-timeline", "union 由结果聚合（== [5]）",
            meta["effective_event_ticks_union"] == [5], [5],
            meta["effective_event_ticks_union"])
    v.check("T16-timeline", "失败实验保留 error_type",
            entry_bad.get("error_type") == "RuntimeError", "RuntimeError",
            entry_bad.get("error_type"))


# ══════════════════════════════════════════════════════════════════════
# T17  fixture 溯源元数据 + 生产树洁净前置检查
# ══════════════════════════════════════════════════════════════════════

def check_fixture_provenance(v):
    # ── 前置检查函数本身的行为 ──
    status, entries = collect_dirty_production_entries(project_root)
    v.check("T17-fixture", "洁净检查返回合法状态",
            status in ("clean", "dirty", "undetermined"),
            "clean|dirty|undetermined", status)
    v.check("T17-fixture", "PRODUCTION_PATHS 覆盖 5 个被修改文件所在路径",
            all(any(rel.replace(os.sep, "/").startswith(p.rstrip("/"))
                    for p in PRODUCTION_PATHS) for rel in MODIFIED_FILES),
            "all covered",
            [rel for rel in MODIFIED_FILES
             if not any(rel.replace(os.sep, "/").startswith(p.rstrip("/"))
                        for p in PRODUCTION_PATHS)])
    v.check("T17-fixture", "PRODUCTION_PATHS 不含 tests/（否则生成流程死锁）",
            not any(p.rstrip("/").startswith("tests") for p in PRODUCTION_PATHS),
            "tests excluded", PRODUCTION_PATHS)

    # ── R13：assert_provenance_determined 的裁定行为（不实际生成 fixture）──
    good_prov = {"generated_from_commit": "0" * 40, "git_branch": "main",
                 "git_is_dirty": True}          # True 必须被接受
    try:
        assert_provenance_determined(good_prov)
        accepted_true = True
    except SystemExit:
        accepted_true = False
    v.check("T17-fixture", "git_is_dirty=True 被接受（不得要求必须为 False）",
            accepted_true, "accepted", "rejected")

    for bad_prov, label in (
        ({"generated_from_commit": "0" * 40, "git_branch": "main",
          "git_is_dirty": "unknown"}, "git_is_dirty='unknown'"),
        ({"generated_from_commit": "unknown", "git_branch": "main",
          "git_is_dirty": False}, "commit='unknown'"),
        ({"generated_from_commit": "0" * 40, "git_branch": "unknown",
          "git_is_dirty": False}, "branch='unknown'"),
    ):
        try:
            assert_provenance_determined(bad_prov)
            code = None
        except SystemExit as se:
            code = se.code
        v.check("T17-fixture", "不可判定溯源被拒绝（退出码 2）: " + label,
                code == 2, 2, code)

    # ── fixture 溯源四项 ──
    if not os.path.isfile(FIXTURE_PATH):
        v.error("T17-fixture", "fixture 存在", "缺少 " + FIXTURE_PATH)
        return
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        fx = json.load(f)

    commit = fx.get("generated_from_commit", "")
    v.check("T17-fixture", "generated_from_commit 为 40 位 hex",
            isinstance(commit, str) and len(commit) == 40
            and all(c in "0123456789abcdef" for c in commit),
            "40-hex", commit)
    v.check("T17-fixture", "git_branch 非空且非 unknown",
            isinstance(fx.get("git_branch"), str)
            and fx.get("git_branch") not in ("", "unknown"),
            "branch name", fx.get("git_branch"))
    # R13：git_is_dirty 必须是 bool。True 属预期（.kiro/ 下设计文档未提交），
    #      "unknown" 不合法——生成阶段已以退出码 2 拒绝，出现即说明 fixture 来源不明。
    v.check("T17-fixture", "git_is_dirty 为 bool（'unknown' 不合法；True 属预期）",
            isinstance(fx.get("git_is_dirty"), bool),
            "bool (True or False)", repr(fx.get("git_is_dirty")))
    v.check("T17-fixture", "production_paths_checked 与当前 PRODUCTION_PATHS 一致",
            fx.get("production_paths_checked") == list(PRODUCTION_PATHS),
            list(PRODUCTION_PATHS), fx.get("production_paths_checked"))

    # ── R13：测试文件自身哈希必须完全相同（输入定义未被偷换）──
    fx_harness = fx.get("test_harness_sha256", "")
    cur_harness = harness_sha256()
    v.check("T17-fixture", "fixture 记录了 test_harness_sha256（64-hex）",
            _is_hex64(fx_harness), "64-hex", fx_harness)
    v.check("T17-fixture", "测试文件哈希与 fixture 记录完全相同（输入定义未变）",
            fx_harness == cur_harness, fx_harness, cur_harness,
            note=("测试文件定义了 fixture 的全部输入（Router 返回值 / 场景常量 / "
                  "比对字段）；一旦改动，P14 的零容差比对就不再是同输入同输出。"
                  "若确需修改测试文件，必须回到 pre-TASK_002 commit 重新生成 fixture。"))

    # ── R13：fixture 的 commit 必须是当前 HEAD 的祖先（或等于 HEAD）──
    anc_status, anc_detail = check_fixture_commit_ancestry(project_root, commit)
    v.check("T17-fixture", "fixture commit 是 HEAD 的祖先（或等于 HEAD）",
            anc_status == "ancestor", "ancestor", anc_status, note=anc_detail)
    if anc_status == "not_ancestor":
        v.warn("T17-fixture", "基线与当前代码不在同一条历史线上（需重新生成 fixture）",
               anc_detail)

    sha = fx.get("baseline_file_sha256", {})
    v.check("T17-fixture", "baseline_file_sha256 覆盖 3 个基线文件",
            sorted(sha.keys()) == sorted(BASELINE_HASHED_FILES),
            sorted(BASELINE_HASHED_FILES), sorted(sha.keys()))
    v.check("T17-fixture", "baseline_file_sha256 全为 64 位 hex",
            all(_is_hex64(h) for h in sha.values()), "64-hex",
            {k: h for k, h in sha.items() if not _is_hex64(h)})
    # 仅记录当前哈希以供人工溯源；ConsumerPlanPlugin.py 的变化属预期，不作为判据
    v.warn("T17-fixture", "当前生产文件哈希（供溯源，非判据）",
           json.dumps({rel: _sha256_file(os.path.join(project_root, *rel.split("/")))[:12]
                       for rel in BASELINE_HASHED_FILES}, ensure_ascii=False))


# ══════════════════════════════════════════════════════════════════════
# T10  pre-TASK_002 行为不变性
# ══════════════════════════════════════════════════════════════════════

async def check_behavior_invariance(v):
    if not os.path.isfile(FIXTURE_PATH):
        v.error("T10-behavior", "fixture 存在",
                "缺少 " + FIXTURE_PATH + "；必须在应用 diff 之前用 --generate-fixture 生成")
        return []
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixture = json.load(f)

    v.check("T10-behavior", "fixture 比对字段声明正确",
            fixture.get("compared_fields") == COMPARED_FIELDS, COMPARED_FIELDS,
            fixture.get("compared_fields"))
    v.check("T10-behavior", "fixture 声明零容差",
            fixture.get("compare_tolerance") == 0.0, 0.0, fixture.get("compare_tolerance"))
    # R7：不变性证据必须来自运行期未舍入状态，而不是 CSV 的 12 位小数
    v.check("T10-behavior", "fixture 声明比对源为运行期未舍入状态",
            fixture.get("compare_source") == "runtime_state_unrounded",
            "runtime_state_unrounded", fixture.get("compare_source"))
    v.check("T10-behavior", "fixture 场景数 == 12",
            len(fixture.get("scenarios", [])) == 12, 12, len(fixture.get("scenarios", [])))
    n_fixture_ticks = sum(len(s["ticks"]) for s in fixture.get("scenarios", []))
    v.check("T10-behavior", "fixture Tick 快照数 == 100",
            n_fixture_ticks == 100, 100, n_fixture_ticks)

    current = await collect_behavior_trace()
    diffs = compare_traces(fixture, current)
    n_ticks = sum(len(s["ticks"]) for s in current)
    n_points = n_ticks * len(COMPARED_FIELDS)

    v.check("T10-behavior", "当前运行 Tick 快照数 == 100", n_ticks == 100, 100, n_ticks)
    v.check("T10-behavior", "比对点数 == 500", n_points == 500, 500, n_points)
    v.check("T10-behavior",
            "行为逐 Tick 完全一致（%d 个比对点，零容差，比较运行期未舍入状态）" % n_points,
            not diffs, "0 diff", "%d diff" % len(diffs))
    for d in diffs[:20]:
        v.check("T10-behavior",
                "diff %s/%s T%s %s" % (d["scenario"], d["cluster_type"], d["tick"], d["field"]),
                False, d["baseline"], d["current"])
    return diffs


# ══════════════════════════════════════════════════════════════════════
# T12  导入卫生
# ══════════════════════════════════════════════════════════════════════

def check_imports(v):
    task002_added = sorted({n for names in TASK002_NEW_IMPORTS.values() for n in names})
    for rel in MODIFIED_FILES:
        path = os.path.join(project_root, rel)
        key = rel.replace(os.sep, "/")
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            v.check("T12-imports", "可解析: " + key, False, "parses", str(e))
            continue

        bound = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound[alias.asname or alias.name.split(".")[0]] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        bound[alias.asname or alias.name] = node.lineno
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        unused = sorted(n for n in bound if n not in used)

        v.check("T12-imports", "未引入 time: " + key, "time" not in bound,
                "no 'time' import", "time imported" if "time" in bound else "absent")

        for name in TASK002_NEW_IMPORTS.get(os.path.basename(rel), []):
            v.check("T12-imports", "%s: %s 已导入且被使用" % (key, name),
                    (name in bound) and (name not in unused), "imported & used",
                    "imported=%s used=%s" % (name in bound, name not in unused))

        preexisting_unused = [n for n in unused if n not in task002_added]
        if preexisting_unused:
            v.warn("T12-imports", "既有未使用导入（TASK_002 范围外，本轮不删除）: " + key,
                   ", ".join(preexisting_unused))


# ══════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════

async def main_verify():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(project_root, "results", "task002_validation", timestamp)
    os.makedirs(out_dir, exist_ok=True)

    logger = logging.getLogger("task002v")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(os.path.join(out_dir, "validation.log"), encoding="utf-8")
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.info("TASK_002-V validation started: %s", timestamp)

    v = Verdicts()
    SC = _try_import("simulation_core", v)
    RX = _try_import("run_experiments", v)

    check_syntax(v)
    check_schema(v, SC)
    check_csv_header(v, RX, SC)
    check_record_builder(v, SC)
    check_metadata(v, RX, SC)
    check_network(v)
    check_network_hash(v, SC)
    check_target_nodes(v, SC)
    await check_clarification_type(v)
    check_stage_fields(v, SC)                  # T13
    await check_injector_receipt(v)             # T14
    check_new_artifacts(v, RX, SC)              # T15
    check_effective_timeline(v, RX, SC)         # T16
    check_fixture_provenance(v)                 # T17
    diffs = await check_behavior_invariance(v)
    check_imports(v)

    verdict_path = os.path.join(out_dir, "task002_verdicts.json")
    summary = {
        "timestamp": timestamp,
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
            logger.warning("WARN %s | %s | %s", item["group"], item["assertion"], item["note"])

    print("=" * 66)
    print("TASK_002-V ACCEPTANCE RESULTS")
    print("=" * 66)
    print("Total : %d" % len(v.items))
    print("Passed: %d" % v.n_pass)
    print("Failed: %d" % v.n_fail)
    print("Warned: %d" % v.n_warn)
    print("Output: %s" % out_dir)
    print("=" * 66)
    print("ALL ACCEPTANCE CRITERIA PASSED" if v.n_fail == 0
          else "%d ASSERTION(S) FAILED" % v.n_fail)
    return v.n_fail == 0


def main():
    parser = argparse.ArgumentParser(description="TASK_002 observability acceptance test")
    parser.add_argument("--generate-fixture", action="store_true",
                        help="在应用 TASK_002 diff 之前运行，生成 pre-TASK_002 行为基线 fixture")
    args = parser.parse_args()

    if args.generate_fixture:
        # generate_fixture() 内部先做生产树洁净检查与溯源可判定性检查；
        # 脏或不可判定时直接 sys.exit(2)，不会走到这里。
        asyncio.run(generate_fixture())
        return 0
    return 0 if asyncio.run(main_verify()) else 1


if __name__ == "__main__":
    sys.exit(main())
