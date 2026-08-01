"""
run_experiments.py — 实验批量调度入口

观测目标：单一漂绿事件（Blackstone 丑闻，Tick 5）后，
         12 种企业澄清策略（2×内容 × 2×渠道 × 3×时机）的信任恢复差异。

设计原则：
  1. 单事件控制  — 临时 patch ENTERPRISE_STRATEGY 为仅含 Tick 5 的漂绿事件，
                   屏蔽 Tick 10/15 的后续事件，确保策略效果归因干净。
  2. 路径对齐   — 先跑 no-clarification 对照组并缓存 LLM 响应（RecordingRouter），
                   其余 11 组在澄清 Tick 之前 Replay 同一份缓存，
                   保证 Tick 1~(clarification_tick-1) 的信任轨迹完全一致。
  3. 真实 LLM   — 澄清 Tick 当天及之后走真实 LLM，差异完全由策略内容决定。

用法：
    python run_experiments.py
"""
import sys
import os
import asyncio
import csv
import datetime
import hashlib
import json
import platform
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from experiment_config import generate_experiment_matrix, ExperimentConfig
from simulation_core import (
    run_simulation_core,
    ENTERPRISE_STRATEGY,
    AGENT_RECORDS_FIELDS,
    AGENT_RECORDS_SCHEMA_VERSION,
)


# ══════════════════════════════════════════════════════════════════════
# 单事件 patch：只保留 Tick 5 的 Blackstone 漂绿丑闻
# ══════════════════════════════════════════════════════════════════════
_SINGLE_SCANDAL = {5: ENTERPRISE_STRATEGY[5]}


# ══════════════════════════════════════════════════════════════════════
# Recording / Replay Router（复用 run_clarification_trial 的设计）
# ══════════════════════════════════════════════════════════════════════

class RecordingRouter:
    """记录所有 LLM 调用：(prompt_hash, tick, call_index) → response"""

    def __init__(self, inner_router):
        self._inner = inner_router
        self._cache: dict = {}
        self._current_tick: int = 0
        self._call_counts: dict = {}

    def set_tick(self, tick: int):
        self._current_tick = tick
        self._call_counts = {}

    @staticmethod
    def _pk(prompt: str) -> str:
        return str(hash(prompt[:200]) & 0xFFFFFFFF)

    async def chat(self, prompt: str) -> str:
        pk = self._pk(prompt)
        count = self._call_counts.get(pk, 0)
        self._call_counts[pk] = count + 1
        response = await self._inner.chat(prompt)
        self._cache[(pk, self._current_tick, count)] = response
        return response

    @property
    def cache(self) -> dict:
        return self._cache


class ReplayRouter:
    """在 replay_until_tick 之前回放缓存，之后走真实 LLM"""

    def __init__(self, inner_router, cache: dict, replay_until_tick: int):
        self._inner = inner_router
        self._cache = cache
        self._replay_until = replay_until_tick
        self._current_tick: int = 0
        self._call_counts: dict = {}
        self.miss_count: int = 0

    def set_tick(self, tick: int):
        self._current_tick = tick
        self._call_counts = {}

    async def chat(self, prompt: str) -> str:
        pk = RecordingRouter._pk(prompt)
        count = self._call_counts.get(pk, 0)
        self._call_counts[pk] = count + 1

        if self._current_tick < self._replay_until:
            key = (pk, self._current_tick, count)
            if key in self._cache:
                return self._cache[key]
            self.miss_count += 1
            if self.miss_count <= 3:
                print(f"  ⚠️  [ReplayRouter] cache miss tick={self._current_tick}")
        return await self._inner.chat(prompt)


# ══════════════════════════════════════════════════════════════════════
# CSV 写入函数
# ══════════════════════════════════════════════════════════════════════

def write_summary_csv(results: list, output_path: str):
    """将所有实验结果写入汇总 CSV（含高区分度指标 + 相对对照组的增益）"""

    # 预计算对照组（no-clarification）的基线信任，用于计算相对增益
    # 按渠道分组取对应的 no-clr 基线（hub vs random 的基线不同）
    ctrl_baseline: dict = {}   # channel → final_trust
    for r in results:
        if "error" in r:
            continue
        if r["config"].get("timing_factor") == "no-clarification":
            channel = r["config"].get("channel_factor", "hub")
            final_trust = r["trust_trajectory"][-1] if r.get("trust_trajectory") else 0.0
            ctrl_baseline[channel] = round(final_trust, 4)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "exp_id", "content_factor", "channel_factor", "timing_factor",
            "delta_recovery", "auc_post_scandal", "recovery_speed",
            "steady_state_score", "recovery_rate", "t50", "t80",
            "trust_min", "trust_min_tick", "baseline_trust", "clarification_effect",
            # 新增：相对对照组的净信任增益（同渠道 no-clr 为基线）
            "trust_gain_vs_control",
        ])
        for r in results:
            if "error" in r:
                writer.writerow([r["exp_id"]] + ["ERROR"] * 16)
                continue
            cfg = r["config"]
            m   = r["metrics"]

            # 计算相对对照组的净增益
            channel = cfg["channel_factor"]
            final_trust = r["trust_trajectory"][-1] if r.get("trust_trajectory") else 0.0
            ctrl_final  = ctrl_baseline.get(channel, final_trust)
            trust_gain  = round(final_trust - ctrl_final, 4)

            writer.writerow([
                r["exp_id"], cfg["content_factor"], cfg["channel_factor"], cfg["timing_factor"],
                m.delta_recovery, m.auc_post_scandal, m.recovery_speed,
                m.steady_state_score, m.recovery_rate, m.t50, m.t80,
                m.trust_min, m.trust_min_tick, m.baseline_trust, m.clarification_effect,
                trust_gain,
            ])


def write_trajectories_csv(results: list, output_path: str):
    """将所有实验的逐 Tick 轨迹写入 CSV（供折线图使用）"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "exp_id", "content_factor", "channel_factor", "timing_factor",
            "tick", "avg_trust", "conversion_rate",
        ])
        for r in results:
            if "error" in r:
                continue
            cfg        = r["config"]
            trust_traj = r.get("trust_trajectory", [])
            conv_traj  = r.get("conversion_trajectory", [])
            for tick_idx, (trust, conv) in enumerate(zip(trust_traj, conv_traj), start=1):
                writer.writerow([
                    r["exp_id"], cfg["content_factor"], cfg["channel_factor"], cfg["timing_factor"],
                    tick_idx, round(trust, 4), round(conv, 4),
                ])


def write_agent_records_csv(results: list, output_path: str):
    """逐 Agent 逐 Tick 详细记录 → CSV（schema v2.0，60 个唯一字段）

    字段清单来自 simulation_core.AGENT_RECORDS_FIELDS（单一事实来源），
    此处只做硬性契约校验，避免任何字段被重复列出（历史事故：trust_after_decay 出现两次）。
    """
    fieldnames = list(AGENT_RECORDS_FIELDS)
    duplicates = sorted({n for n in fieldnames if fieldnames.count(n) > 1})
    assert len(fieldnames) == 60, \
        f"agent_records schema 必须为 60 字段，实际 {len(fieldnames)}"
    assert len(fieldnames) == len(set(fieldnames)), \
        f"agent_records schema 存在重复字段: {duplicates}"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="", extrasaction="raise")
        writer.writeheader()
        for r in results:
            if "error" in r or "agent_records" not in r:
                continue
            for rec in r["agent_records"]:
                writer.writerow(rec)


def write_target_nodes_csv(results: list, output_path: str):
    """目标节点选择审计明细 → CSV

    Random 渠道的 metric_value 写空字符串（不适用），禁止写 0：
    0 会与"该节点出度确实为 0"混淆，破坏审计可判定性。
    """
    fieldnames = ["exp_id", "content_factor", "channel_factor", "timing_factor",
                  "agent_id", "selection_metric", "metric_value", "rank"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for r in results:
            if "error" in r:
                continue
            for row in r.get("target_nodes_meta", []):
                writer.writerow(row)


# ── R10：run 级网络文件的列契约（均**不含** exp_id）──
NETWORK_NODES_FIELDS = ["agent_id", "cluster_type", "social_role",
                        "out_degree", "in_degree"]
NETWORK_EDGES_FIELDS = ["source_agent_id", "target_agent_id", "is_directed"]


def verify_single_network(results: list) -> dict:
    """TASK_002 / R10：验证"整个 run 只有一张网络"这个前提，而不是假设它。

    network_nodes.csv / network_edges.csv 是 run 级静态文件（全 run 一份、无 exp_id），
    其成立条件是所有成功实验的拓扑完全相同。该条件由 (num_agents, random_seed) 决定，
    12 组配置当前都是 (20, 42)，但**必须验证**——一旦有人改了某组的 seed，
    静默写出"某一组"的拓扑会让全部网络分析结论失去归属。

    Returns:
        {"status": "consistent" | "inconsistent" | "unavailable",
         "network_hash": str, "source_exp_id": str,
         "hash_groups": {hash: [exp_id…]}, "per_experiment": [...],
         "node_row_mismatch": [...], "edge_row_mismatch": [...],
         "checked_experiments": int, "reason": str}
    """
    ok = [r for r in results if "error" not in r and r.get("network_meta")]
    ok.sort(key=lambda r: str(r.get("exp_id", "")))
    per_exp = []
    for r in ok:
        nm = r.get("network_meta", {}) or {}
        cfg = r.get("config", {}) or {}
        per_exp.append({
            "exp_id": r.get("exp_id", "unknown"),
            "network_hash": nm.get("network_hash", ""),
            "num_nodes": nm.get("num_nodes", ""),
            "num_edges": nm.get("num_edges", ""),
            "network_type": nm.get("network_type", ""),
            "network_params": nm.get("network_params", {}),
            "random_seed": cfg.get("random_seed", ""),
            "num_agents": cfg.get("num_agents", ""),
        })

    hash_groups: dict = {}
    for e in per_exp:
        hash_groups.setdefault(e["network_hash"], []).append(e["exp_id"])

    base = {
        "hash_groups": hash_groups,
        "per_experiment": per_exp,
        "checked_experiments": len(ok),
        "node_row_mismatch": [],
        "edge_row_mismatch": [],
        "refused_outputs": ["network_nodes.csv", "network_edges.csv"],
    }

    if not ok:
        base.update({"status": "unavailable", "network_hash": "", "source_exp_id": "",
                     "reason": "no successful experiment reported network_meta"})
        return base

    if len(hash_groups) > 1:
        base.update({"status": "inconsistent", "network_hash": "", "source_exp_id": "",
                     "reason": "network_hash differs across successful experiments"})
        return base

    # 哈希只覆盖拓扑；节点表还含 cluster_type / social_role，逐行再核一次
    ref = ok[0]
    ref_nodes = [tuple(row[k] for k in NETWORK_NODES_FIELDS)
                 for row in ref.get("network_nodes", [])]
    ref_edges = [tuple(row[k] for k in NETWORK_EDGES_FIELDS)
                 for row in ref.get("network_edges", [])]
    for r in ok[1:]:
        rn = [tuple(row[k] for k in NETWORK_NODES_FIELDS)
              for row in r.get("network_nodes", [])]
        re_ = [tuple(row[k] for k in NETWORK_EDGES_FIELDS)
               for row in r.get("network_edges", [])]
        if rn != ref_nodes:
            base["node_row_mismatch"].append(r.get("exp_id", "unknown"))
        if re_ != ref_edges:
            base["edge_row_mismatch"].append(r.get("exp_id", "unknown"))

    if base["node_row_mismatch"] or base["edge_row_mismatch"]:
        base.update({"status": "inconsistent", "network_hash": "", "source_exp_id": "",
                     "reason": "network_hash matches but node/edge rows differ "
                               "(cluster_type / social_role / degree mismatch)"})
        return base

    base.update({
        "status": "consistent",
        "network_hash": per_exp[0]["network_hash"],
        # 按 exp_id 字典序取最小者作为 run 级代表，使选择是确定性的
        "source_exp_id": per_exp[0]["exp_id"],
        "reason": "",
        "refused_outputs": [],
    })
    return base


def write_network_inconsistency_report(verification: dict, output_path: str):
    """R10 失败路径：把"为什么拒绝写出 run 级网络文件"完整落盘。

    刻意包含 random_seed / num_agents / network_type / network_params——
    一致性被打破时，原因几乎总在这四项里。
    """
    report = dict(verification)
    report["remedy"] = (
        "Topology must be identical across the run (same num_agents / random_seed "
        "and the same register_agents path). Inspect per_experiment: differing "
        "random_seed or num_agents, or a non-deterministic graph construction."
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def write_network_nodes_csv(results: list, output_path: str, verification: dict) -> bool:
    """run 级社交网络节点表 → CSV（整个 run 一份，每节点一行，**无 exp_id**）。

    TASK_002 / R10：
      · 只有 verification["status"] == "consistent" 时才写出；否则**连表头都不写**
        （空表头文件会被下游误读为"网络为空"），返回 False 由调用方判 FAIL。
      · 行数据取自 verification["source_exp_id"] 指定的那组实验——此时已验证
        所有成功实验的行完全相同，取哪组都一样，取最小 exp_id 只为确定性。
      · 不含 is_clarification_target：目标身份是实验级事实，唯一落点是 target_nodes.csv。
    """
    if verification.get("status") != "consistent":
        return False
    src = next((r for r in results
                if r.get("exp_id") == verification.get("source_exp_id")), None)
    if src is None:
        return False
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NETWORK_NODES_FIELDS,
                               restval="", extrasaction="raise")
        writer.writeheader()
        for row in src.get("network_nodes", []):
            writer.writerow(row)
    return True


def write_network_edges_csv(results: list, output_path: str, verification: dict) -> bool:
    """run 级社交网络边表 → CSV（整个 run 一份，字典序，**无 exp_id**）。

    与 write_network_nodes_csv 同样的前置条件：不一致 / 不可判定 → 不写出，返回 False。
    """
    if verification.get("status") != "consistent":
        return False
    src = next((r for r in results
                if r.get("exp_id") == verification.get("source_exp_id")), None)
    if src is None:
        return False
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NETWORK_EDGES_FIELDS,
                               restval="", extrasaction="raise")
        writer.writeheader()
        for row in src.get("network_edges", []):
            writer.writerow(row)
    return True


# R12：18 个字段。因子/seed/预算来自 config.to_dict()（异常分支也必须带 config），
#      target_nodes / network_hash / effective_event_timeline 来自实验结果。
EXPERIMENT_METADATA_FIELDS = [
    # 标识
    "exp_id",
    # 实验因子与参数（真实字段名已核对：random_seed 不是 seed；
    # clarification_tick 是 ExperimentConfig 的 @property，由 to_dict() 补入）
    "content_factor", "channel_factor", "timing_factor",
    "clarification_tick", "random_seed", "budget_k",
    # 运行时序
    "started_at", "finished_at",
    # Router 审计（router_role 说明 recording_cache_size 的语义归属）
    "recording_cache_size", "replay_miss_count", "router_role",
    # 实验输入指纹
    "target_nodes", "network_hash", "effective_event_timeline",
    # 状态
    "success", "error_type", "error",
]


def write_experiment_metadata_jsonl(results: list, output_path: str):
    """每个 exp_id 一行的实验级运行元数据（JSON Lines，18 字段）。

    取值来源（全部为真实运行期采集，见设计文档 §C6）：
      content/channel/timing/clarification_tick/random_seed/budget_k
                               : result["config"]（= ExperimentConfig.to_dict()）
                                 —— 成功与失败实验**都**带 config（R12）
      started_at / finished_at : main() 循环内在 _run_with_patch 调用前后取 datetime
      recording_cache_size     : 录制组 len(RecordingRouter.cache)；
                                 回放组 len(llm_cache)（该组实际消费的缓存规模）
      replay_miss_count        : ReplayRouter.miss_count；录制组不适用 → ""
      target_nodes             : result["target_nodes_meta"] 的 agent_id 列表（真实选点）
      network_hash             : result["network_meta"]["network_hash"]（真实图指纹）
      effective_event_timeline : result["effective_event_timeline"]（运行期快照，
                                 绝不从 ENTERPRISE_STRATEGY 重建）
      success / error_type / error : 实验结果状态
    "" 表示"不适用"，与数值 0 严格区分；缺失键一律补 "" / []，绝不猜测。
    clarification_tick 为 None（no-clarification）时写 ""，不写 0。
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            audit = r.get("run_audit", {}) or {}
            cfg = r.get("config", {}) or {}
            clr_tick = cfg.get("clarification_tick", None)
            row = {
                "exp_id": r.get("exp_id", cfg.get("exp_id", "unknown")),
                # ── R12：实验因子与参数（异常结果同样具备）──
                "content_factor": cfg.get("content_factor", ""),
                "channel_factor": cfg.get("channel_factor", ""),
                "timing_factor": cfg.get("timing_factor", ""),
                "clarification_tick": "" if clr_tick is None else clr_tick,
                "random_seed": cfg.get("random_seed", ""),
                "budget_k": cfg.get("budget_k", ""),
                # ── 运行时序与 Router ──
                "started_at": audit.get("started_at", ""),
                "finished_at": audit.get("finished_at", ""),
                "recording_cache_size": audit.get("recording_cache_size", ""),
                "replay_miss_count": audit.get("replay_miss_count", ""),
                "router_role": audit.get("router_role", ""),
                # ── R12：实验输入指纹（依赖运行结果，失败实验记空）──
                "target_nodes": [row_.get("agent_id")
                                 for row_ in (r.get("target_nodes_meta") or [])],
                "network_hash": (r.get("network_meta", {}) or {}).get("network_hash", ""),
                "effective_event_timeline": r.get("effective_event_timeline", []),
                # ── 状态 ──
                "success": "error" not in r,
                "error_type": r.get("error_type", "") if "error" in r else "",
                "error": str(r.get("error", "")) if "error" in r else "",
            }
            assert set(row.keys()) == set(EXPERIMENT_METADATA_FIELDS), \
                "experiment_metadata 行字段与契约不一致"
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _sha256_file(path: str) -> str:
    """文件 SHA-256。文件缺失时返回 'missing:<basename>'，绝不返回 'unknown'。"""
    if not os.path.isfile(path):
        return f"missing:{os.path.basename(path)}"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_porcelain(project_root: str, paths=None):
    """`git status --porcelain` 的非空行列表；无法执行/非零退出时返回 None（= 不可判定）。

    使用列表形式的 argv（不经过 shell），路径作为独立参数传入，避免任何注入风险。
    """
    cmd = ["git", "status", "--porcelain", "--untracked-files=all"]
    if paths:
        cmd = cmd + ["--"] + [str(p) for p in paths]
    try:
        proc = subprocess.run(cmd, cwd=project_root, capture_output=True,
                              text=True, timeout=30)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def _git_is_dirty(project_root: str):
    """仓库是否存在未提交修改（含未跟踪文件）。

    不可判定（无 git / 非仓库 / 命令失败）时返回字符串 "unknown"——
    绝不假设为 False，否则会把"不知道"记录成"干净"。
    """
    lines = _git_porcelain(project_root)
    if lines is None:
        return "unknown"
    return len(lines) > 0


def _read_git_info(project_root: str) -> dict:
    """直接读取 .git 内的文本引用取 branch/commit（不依赖子进程），
    另用 git status 取 is_dirty（TASK_002 / R8：脏工作区必须显式记录）。"""
    git_dir = os.path.join(project_root, ".git")
    info = {"branch": "unknown", "commit": "unknown",
            "is_dirty": _git_is_dirty(project_root)}
    head_path = os.path.join(git_dir, "HEAD")
    if not os.path.isfile(head_path):
        return info
    with open(head_path, "r", encoding="utf-8") as f:
        head = f.read().strip()
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        info["branch"] = ref.split("/")[-1]
        ref_path = os.path.join(git_dir, *ref.split("/"))
        if os.path.isfile(ref_path):
            with open(ref_path, "r", encoding="utf-8") as f:
                info["commit"] = f.read().strip()
        else:
            packed = os.path.join(git_dir, "packed-refs")
            if os.path.isfile(packed):
                with open(packed, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.rstrip().endswith(" " + ref):
                            info["commit"] = line.split()[0]
                            break
    else:
        info["branch"] = "DETACHED"
        info["commit"] = head
    return info


def _read_llm_config(project_root: str) -> dict:
    """读取 models_config.yaml 的采样参数。

    未在配置中出现的参数一律记为 "unknown"——例如当前配置没有 top_p，
    就必须记 "unknown"，禁止填 1.0 之类的假设默认值冒充"已知配置"。
    api_key 只记录是否存在，绝不写入结果文件。
    """
    import yaml
    cfg_path = os.path.join(project_root, "configs", "models_config.yaml")
    meta = {"config_file": "configs/models_config.yaml",
            "config_sha256": _sha256_file(cfg_path)}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            conf = yaml.safe_load(f)
    except Exception as e:
        meta["read_error"] = f"{type(e).__name__}: {e}"
        return meta
    entries = conf if isinstance(conf, list) else [conf]
    entries = [e for e in entries if isinstance(e, dict)]
    entry = next((e for e in entries if "chat" in (e.get("capabilities") or [])),
                 entries[0] if entries else {})
    for key in ("name", "model", "base_url", "temperature", "top_p", "seed",
                "max_tokens", "frequency_penalty", "presence_penalty"):
        meta[key] = entry.get(key, "unknown")
    meta["api_key_present"] = bool(entry.get("api_key"))
    return meta


# 元数据中登记哈希的源文件（相对 project_root）
_HASHED_SOURCES = [
    "run_experiments.py",
    "simulation_core.py",
    "experiment_config.py",
    "node_selector.py",
    "clarification_injector.py",
    "metrics_calculator.py",
    "generate_data.py",
    "plugins/agent/plan/ConsumerPlanPlugin.py",
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "plugins/agent/reflect/MemoryManager.py",
    "plugins/agent/perceive/GreenPerceivePlugin.py",
    "plugins/agent/profile/GreenProfilePlugin.py",
    "plugins/agent/state/GreenStatePlugin.py",
    "plugins/agent/invoke/GreenInvokePlugin.py",
    "plugins/environment/network/SocialNetworkPlugin.py",
    "configs/models_config.yaml",
]

# Prompt / Persona 的权威来源文件。路径**必须**由 project_root 解析，
# 禁止从 output_path 推导（输出目录是 results/experiments/run_*，与源码目录无结构关系）。
_PROMPT_SOURCES = {
    "reflect_prompt":          "plugins/agent/reflect/GreenCognitionPlugin.py",
    "plan_prompt":             "plugins/agent/plan/ConsumerPlanPlugin.py",
    "clarification_templates": "clarification_injector.py",
    "global_event_script":     "simulation_core.py",
}
_PERSONA_SOURCES = {
    "persona_templates":       "generate_data.py",
    "persona_profile_plugin":  "plugins/agent/profile/GreenProfilePlugin.py",
}


def write_run_metadata_json(results: list, output_path: str, project_root: str,
                            run_id: str = "", network_verification: dict = None) -> dict:
    """写入运行级元数据（schema v2.0 的补充证据）。

    Args:
        results:      实验结果列表
        output_path:  run_metadata.json 目标路径
        project_root: 项目根目录绝对路径。Prompt / Persona / 配置文件路径**必须**
                      由该参数解析，禁止从 output_path 反推。
        run_id:       本次运行时间戳 ID
        network_verification: verify_single_network() 的返回值（R10）。
                      为 None 时表示调用方未做验证 → 记 status="not_verified"，
                      绝不记成 "consistent"（不知道 ≠ 一致）。
    """
    from clarification_injector import CONTENT_TEMPLATES

    git_info = _read_git_info(project_root)
    meta = {
        "agent_records_schema_version": AGENT_RECORDS_SCHEMA_VERSION,
        "agent_records_field_count": len(AGENT_RECORDS_FIELDS),
        "agent_records_fields": list(AGENT_RECORDS_FIELDS),
        "run_id": run_id,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "project_root": project_root,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "git": git_info,
        # R8：顶层显式镜像，便于审计脚本直接 grep；值恒等于 git["is_dirty"]
        #     True/False = 已判定，"unknown" = 无法判定（绝不静默当作干净）
        "git_is_dirty": git_info["is_dirty"],
        "llm": _read_llm_config(project_root),
        # R10：run 级网络文件的前提是否被验证通过。唯一的运行级元数据文件
        #      自身即可判定：status != "consistent" 时两个网络 CSV 必然不存在。
        "network_consistency": (dict(network_verification)
                                if network_verification is not None
                                else {"status": "not_verified",
                                      "reason": "verify_single_network() was not called",
                                      "refused_outputs": ["network_nodes.csv",
                                                          "network_edges.csv"]}),
        "source_file_hashes": {
            rel: _sha256_file(os.path.join(project_root, *rel.split("/")))
            for rel in _HASHED_SOURCES
        },
        "prompt_sources": {
            key: {"path": rel,
                  "sha256": _sha256_file(os.path.join(project_root, *rel.split("/")))}
            for key, rel in _PROMPT_SOURCES.items()
        },
        "persona_sources": {
            key: {"path": rel,
                  "sha256": _sha256_file(os.path.join(project_root, *rel.split("/")))}
            for key, rel in _PERSONA_SOURCES.items()
        },
        "clarification_templates": {
            name: {
                "word_count": len(text.split()),
                "char_count": len(text),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
            for name, text in CONTENT_TEMPLATES.items()
        },
        # R4：**删除** 旧的 "global_event_ticks": sorted(ENTERPRISE_STRATEGY.keys())。
        #     该写法在运行结束后从常量重建时间线，无法反映 _run_with_patch 的实际改写，
        #     且与 patch 的恢复顺序耦合。改为从实验结果读取真实生效的时间线（见下）。
        "experiments": [],
    }

    for r in results:
        entry = {"exp_id": r.get("exp_id", "unknown")}
        if "error" in r:
            entry["status"] = "error"
            entry["error_type"] = str(r.get("error_type", ""))
            entry["error"] = str(r["error"])
            # R12：异常结果同样保存 config —— 失败实验最需要"它是哪一组因子/什么 seed"
            entry["config"] = r.get("config", {})
            # 失败实验没有生效时间线；显式记空列表 + 原因，不回退到常量
            entry["effective_event_timeline"] = []
            entry["effective_event_timeline_source"] = "unavailable: experiment failed"
        else:
            entry["status"] = "ok"
            entry["config"] = r.get("config", {})
            entry["network"] = r.get("network_meta", {})
            entry["target_nodes"] = [row.get("agent_id") for row in r.get("target_nodes_meta", [])]
            entry["agent_record_count"] = len(r.get("agent_records", []))
            entry["network_node_count"] = len(r.get("network_nodes", []))
            entry["network_edge_count"] = len(r.get("network_edges", []))
            # R4：只从实验结果读取；结果里没有就记 unknown，绝不从 ENTERPRISE_STRATEGY 重建
            if "effective_event_timeline" in r:
                entry["effective_event_timeline"] = r["effective_event_timeline"]
                entry["effective_event_timeline_source"] = "run_simulation_core (runtime snapshot)"
            else:
                entry["effective_event_timeline"] = []
                entry["effective_event_timeline_source"] = "unknown: not reported by result"
        meta["experiments"].append(entry)

    # 全部成功实验实际生效的事件 Tick 并集（仅由结果聚合，不引用任何常量）
    meta["effective_event_ticks_union"] = sorted({
        int(e["tick"])
        for entry in meta["experiments"]
        for e in entry.get("effective_event_timeline", [])
    })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

async def _run_with_patch(config: ExperimentConfig, override_router=None) -> dict:
    """
    在单事件策略下运行一组实验。
    临时 patch ENTERPRISE_STRATEGY → 只保留 Tick 5 漂绿丑闻。
    """
    import simulation_core as _sc
    original = _sc.ENTERPRISE_STRATEGY.copy()
    _sc.ENTERPRISE_STRATEGY.clear()
    _sc.ENTERPRISE_STRATEGY.update(_SINGLE_SCANDAL)
    try:
        return await run_simulation_core(config, override_router=override_router)
    finally:
        _sc.ENTERPRISE_STRATEGY.clear()
        _sc.ENTERPRISE_STRATEGY.update(original)


async def main():
    print("=" * 65)
    print("🧪 GABM 批量实验 — 单一漂绿事件 × 12 种澄清策略")
    print("   Scandal : Tick 5 (Blackstone 丑闻，其余事件屏蔽)")
    print("   矩阵    : 2(内容) × 2(渠道) × 3(时机) = 12 组")
    print("   对齐    : 澄清前路径 Replay 对照组 LLM 响应，消除采样噪声")
    print("=" * 65)

    configs = generate_experiment_matrix()
    total   = len(configs)

    # ── 执行顺序设计 ─────────────────────────────────────────────────
    # 1. 先跑单一 no-clarification 基线（hub+rational），录制全局 LLM 缓存
    # 2. 其余 11 组（含另外 3 个 no-clr）全部 replay 该缓存到 clarification_tick 前，
    #    保证所有实验在澄清注入前路径完全一致，差异仅来自策略本身
    baseline_config = next(
        c for c in configs
        if c.timing_factor == "no-clarification"
        and c.channel_factor == "hub"
        and c.content_factor == "rational-evidence"
    )
    other_configs = [c for c in configs if c != baseline_config]
    ordered_configs = [baseline_config] + other_configs

    # ── 获取真实 Router ───────────────────────────────────────────────
    import yaml
    try:
        with open(os.path.join(current_dir, "configs/models_config.yaml"), "r") as f:
            _models_conf = yaml.safe_load(f)
        from agentkernel_standalone.toolkit.models.router import ModelRouter, AsyncModelRouter
        _real_router = ModelRouter(AsyncModelRouter(_models_conf))
        print("🧠 LLM 引擎已就绪")
    except Exception:
        import json as _json
        class _MockInner:
            async def chat(self, prompt: str) -> str:
                if "trust_change_affective" in prompt or "hypocrisy_perceived" in prompt:
                    return _json.dumps({"hypocrisy_perceived": True,
                                        "trust_change_affective": -1.5,
                                        "importance": 7.0,
                                        "reasoning": "Mock: betrayed."})
                return _json.dumps({"is_buying": False, "is_posting": True,
                                    "post_content": "Upset about this.", "reason": "Mock."})
        _real_router = _MockInner()
        print("⚠️  使用 Mock Router")

    results = []
    errors  = []
    llm_cache: dict = {}   # 对照组建立后填入

    for i, config in enumerate(ordered_configs, 1):
        is_baseline = (config == baseline_config)

        print(f"\n{'─'*65}")
        print(f"  [{i}/{total}] 🚀 {config.exp_id}")
        print(f"    Content={config.content_factor} | Channel={config.channel_factor} "
              f"| Timing={config.timing_factor}"
              + (" [RECORDING — baseline]" if is_baseline else
                 f" [REPLAY until T{config.clarification_tick}]" if config.clarification_tick
                 else f" [REPLAY full — no clarification]"))
        print(f"{'─'*65}")

        # ── TASK_002 审计插桩：计时点位于 _run_with_patch 之外，不进入仿真 ──
        run_audit = {
            "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "finished_at": "",
            "recording_cache_size": "",   # "" = 不适用；录制组=产出规模，回放组=消费规模
            "replay_miss_count": "",      # "" = 不适用（录制组无 ReplayRouter）；0 = 回放零 miss
            "router_role": "recording" if is_baseline else "replay",
        }
        try:
            if is_baseline:
                # ── 唯一的录制组：建立全局 LLM 缓存 ────────────────────
                rec_router = RecordingRouter(_real_router)
                result = await _run_with_patch(config, override_router=rec_router)
                llm_cache.update(rec_router.cache)
                print(f"  📼 全局缓存已建立: {len(llm_cache)} 条 LLM 响应")
                # 真实来源：RecordingRouter._cache（由 .cache 属性暴露）
                run_audit["recording_cache_size"] = len(rec_router.cache)
                # 录制组不存在 ReplayRouter → replay_miss_count 保持 ""，不写 0
            else:
                # ── 其余 11 组（含另外 3 个 NoClr）：全程 Replay 到 clr_tick 前 ──
                # no-clarification 组没有澄清，replay_until_tick=total_ticks+1 意味着全程回放
                clr_tick = config.clarification_tick if config.clarification_tick else config.total_ticks + 1
                rp_router = ReplayRouter(_real_router, llm_cache, replay_until_tick=clr_tick)
                result = await _run_with_patch(config, override_router=rp_router)
                if rp_router.miss_count > 0:
                    print(f"  ⚠️  ReplayRouter cache miss: {rp_router.miss_count} 次")
                # 真实来源：该组实际消费的缓存规模 + ReplayRouter.miss_count
                run_audit["recording_cache_size"] = len(llm_cache)
                run_audit["replay_miss_count"] = rp_router.miss_count

            run_audit["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            result["run_audit"] = run_audit
            results.append(result)

        except Exception as e:
            import traceback
            error_msg = f"{config.exp_id}: {type(e).__name__}: {e}"
            print(f"  ❌ FAILED: {error_msg}")
            traceback.print_exc()
            errors.append(error_msg)
            run_audit["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            # R12：异常分支必须一并写入 config —— 只保存 exp_id + error 会丢掉
            #      "哪一组因子 / 什么 seed / 预算多少"，而失败实验恰恰最需要复现。
            #      ExperimentConfig.to_dict() 已核实存在，返回 asdict + exp_id + clarification_tick。
            results.append({"exp_id": config.exp_id,
                            "config": config.to_dict(),
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "run_audit": run_audit})

    # ── 写入输出文件 ─────────────────────────────────────────────────
    # 每次运行创建独立的带时间戳子目录，避免覆盖历史结果
    # latest/ 目录始终指向最新一次运行，供可视化脚本直接读取
    timestamp  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir   = os.path.join(current_dir, "results", "experiments")
    run_dir    = os.path.join(base_dir, f"run_{timestamp}")
    latest_dir = os.path.join(base_dir, "latest")
    os.makedirs(run_dir,    exist_ok=True)
    os.makedirs(latest_dir, exist_ok=True)

    summary_path = os.path.join(run_dir, "summary.csv")
    write_summary_csv(results, summary_path)
    print(f"\n📄 汇总表: {summary_path}")

    trajectories_path = os.path.join(run_dir, "trajectories.csv")
    write_trajectories_csv(results, trajectories_path)
    print(f"📈 轨迹数据: {trajectories_path}")

    agent_records_path = os.path.join(run_dir, "agent_records.csv")
    write_agent_records_csv(results, agent_records_path)
    print(f"🧬 逐Agent记录: {agent_records_path}")

    target_nodes_path = os.path.join(run_dir, "target_nodes.csv")
    write_target_nodes_csv(results, target_nodes_path)
    print(f"🎯 目标节点审计: {target_nodes_path}")

    # ── R10：run 级网络文件。写出前先验证"整个 run 只有一张网络" ──
    net_verification = verify_single_network(results)
    network_nodes_path = os.path.join(run_dir, "network_nodes.csv")
    network_edges_path = os.path.join(run_dir, "network_edges.csv")
    if net_verification["status"] == "consistent":
        write_network_nodes_csv(results, network_nodes_path, net_verification)
        write_network_edges_csv(results, network_edges_path, net_verification)
        print(f"🕸️ 网络节点表 (run 级): {network_nodes_path}")
        print(f"🕸️ 网络边表   (run 级): {network_edges_path}")
        print(f"   网络指纹: {net_verification['network_hash'][:12]} "
              f"(代表实验: {net_verification['source_exp_id']}, "
              f"已核对 {net_verification['checked_experiments']} 组一致)")
    else:
        # 拒绝写出：缺失文件是"响亮且无法误读"的信号，远优于写出一份归属不明的网络
        report_path = os.path.join(run_dir, "network_inconsistency_report.json")
        write_network_inconsistency_report(net_verification, report_path)
        msg = (f"NETWORK CONSISTENCY {net_verification['status'].upper()}: "
               f"{net_verification['reason']}; refused to write "
               f"network_nodes.csv / network_edges.csv; see {report_path}")
        print("=" * 65)
        print(f"  ❌ {msg}")
        print(f"     指纹分组: {net_verification['hash_groups']}")
        print("=" * 65)
        errors.append(msg)

    exp_meta_path = os.path.join(run_dir, "experiment_metadata.jsonl")
    write_experiment_metadata_jsonl(results, exp_meta_path)
    print(f"🗂️ 实验级元数据: {exp_meta_path}")

    metadata_path = os.path.join(run_dir, "run_metadata.json")
    write_run_metadata_json(results, metadata_path,
                            project_root=current_dir, run_id=timestamp,
                            network_verification=net_verification)
    print(f"🧾 运行元数据: {metadata_path}")

    # ── 写入错误日志 ─────────────────────────────────────────────────
    if errors:
        error_path = os.path.join(run_dir, "errors.log")
        with open(error_path, "w", encoding="utf-8") as f:
            f.write(f"Experiment Errors — {datetime.datetime.now()}\n")
            f.write("=" * 50 + "\n")
            for err in errors:
                f.write(f"  {err}\n")
        print(f"⚠️ {len(errors)} 次运行失败，详见: {error_path}")

    # ── 更新 latest/ 目录 ────────────────────────────────────────────
    import shutil
    # network_nodes.csv / network_edges.csv 在 R10 拒绝写出时不存在，
    # network_inconsistency_report.json 只在拒绝时存在；下面的 os.path.exists 守卫
    # 使两种情况都能正确同步（缺失即缺失，不创建占位文件）。
    for fname in ("summary.csv", "trajectories.csv", "agent_records.csv",
                  "target_nodes.csv", "network_nodes.csv", "network_edges.csv",
                  "experiment_metadata.jsonl", "run_metadata.json",
                  "network_inconsistency_report.json"):
        src = os.path.join(run_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(latest_dir, fname))
    with open(os.path.join(latest_dir, "run_info.txt"), "w", encoding="utf-8") as f:
        f.write(f"run_id   : {timestamp}\n")
        f.write(f"run_dir  : {run_dir}\n")
        f.write(f"generated: {datetime.datetime.now()}\n")
        f.write(f"success  : {len([r for r in results if 'error' not in r])}/{total}\n")
    print(f"📁 本次结果目录 : {run_dir}")
    print(f"🔗 最新结果快照 : {latest_dir}  (可视化脚本读此目录)")

    # results_dir 供后续可视化使用（指向 latest）
    results_dir = latest_dir

    # ── 可视化 ────────────────────────────────────────────────────────
    successful = [r for r in results if "error" not in r]
    if successful:
        try:
            from plot_pareto import analyze_and_plot_pareto
            analyze_and_plot_pareto(successful, results_dir)
        except Exception as e:
            print(f"⚠️ 帕累托分析失败: {e}")

        analysis_dir = os.path.join(current_dir, "analysis")
        if analysis_dir not in sys.path:
            sys.path.insert(0, analysis_dir)
        try:
            import plot_experiments as _pe
            import plot_trajectories as _pt_traj
            import shutil as _shutil
            # 图像输出到本次 run_dir（带时间戳），历史图像永久保留
            run_figures_dir = os.path.join(run_dir, "figures")
            os.makedirs(run_figures_dir, exist_ok=True)
            _pe.OUTPUT_DIR     = run_figures_dir
            _pe.RESULTS_DIR    = run_dir
            _pt_traj.OUTPUT_DIR  = run_figures_dir
            _pt_traj.RESULTS_DIR = run_dir
            print("\n🎨 生成实验结果图表...")
            df_exp = _pe.load_data()
            _pe.plot_main_effects(df_exp)
            _pe.plot_heatmap_interactions(df_exp)
            df_exp = _pe.plot_pareto_frontier(df_exp)
            _pe.plot_strategy_ranking(df_exp)
            _pe.plot_clarification_diagnosis(df_exp)
            df_traj = _pt_traj.load_trajectories()
            _pt_traj.plot_timing_effect(df_traj)
            _pt_traj.plot_content_channel(df_traj)
            _pt_traj.plot_all_12_strategies(df_traj)
            _pt_traj.plot_trust_recovery_zoom(df_traj)
            # 同步到 latest/figures/（方便快速查看最新图像，但历史图在 run_dir 里永久保存）
            latest_figures = os.path.join(latest_dir, "figures")
            if os.path.exists(latest_figures):
                _shutil.rmtree(latest_figures)
            _shutil.copytree(run_figures_dir, latest_figures)
            print(f"  → 本次图表: {run_figures_dir}")
            print(f"  → 最新快照: {latest_figures}")
        except Exception as e:
            print(f"⚠️ 实验图表生成失败（{type(e).__name__}）: {e}")

    # ── 最终汇总 ─────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"✅ 实验完成: {len(successful)}/{total} 成功, {len(errors)}/{total} 失败")
    print(f"   结果目录: {results_dir}")
    print(f"{'='*65}")

    # ── R10 fail-closed：网络一致性契约被违反时以退出码 3 结束 ──
    #    刻意放在最后：所有其他产物与图表都已安全落盘，不因审计契约问题丢失实验证据。
    if net_verification["status"] != "consistent":
        print(f"❌ FAIL: run 级网络文件未写出（{net_verification['status']}: "
              f"{net_verification['reason']}）")
        print(f"   诊断报告: {os.path.join(run_dir, 'network_inconsistency_report.json')}")
        print(f"   退出码 3 = 网络一致性契约违反（与正常结束的 0 区分）")
        raise SystemExit(3)


if __name__ == "__main__":
    asyncio.run(main())
