"""
simulation_core.py — 可复用仿真核心函数

从 run_simulation.py 提取的核心逻辑，接受 ExperimentConfig 参数，
返回结构化结果（含逐 Tick 轨迹和三目标指标）。

调用方式：
    from simulation_core import run_simulation_core
    result = await run_simulation_core(config)
"""
import sys
import os
import asyncio
import yaml
import json
import hashlib
import random as random_module
import numpy as np
import networkx as nx
import logging

# 屏蔽底层日志
logging.getLogger("agentkernel_standalone").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
standalone_path = os.path.join(project_root, "packages", "agentkernel-standalone")
if os.path.exists(standalone_path) and standalone_path not in sys.path:
    sys.path.insert(0, standalone_path)
if current_dir not in sys.path:
    sys.path.append(current_dir)

from agentkernel_standalone.mas.builder import Builder
from agentkernel_standalone.mas.agent.agent import Agent
from agentkernel_standalone.mas.environment.environment import Environment
from agentkernel_standalone.mas.environment.base.component_base import EnvironmentComponent
from agentkernel_standalone.toolkit.models.router import ModelRouter, AsyncModelRouter
from agentkernel_standalone.mas.agent.components.profile import ProfileComponent
from agentkernel_standalone.mas.agent.components.state import StateComponent
from agentkernel_standalone.mas.agent.components.perceive import PerceiveComponent
from agentkernel_standalone.mas.agent.components.plan import PlanComponent
from agentkernel_standalone.mas.agent.components.invoke import InvokeComponent
from agentkernel_standalone.mas.agent.components.reflect import ReflectComponent
from agentkernel_standalone.mas.system.components.timer import Timer
from agentkernel_standalone.mas.system.components.messager import Messager

from plugins.agent.profile.GreenProfilePlugin import GreenProfilePlugin
from plugins.agent.state.GreenStatePlugin import GreenStatePlugin
from plugins.agent.perceive.GreenPerceivePlugin import GreenPerceivePlugin
from plugins.agent.reflect.GreenCognitionPlugin import GreenCognitionPlugin
from plugins.agent.plan.ConsumerPlanPlugin import ConsumerPlanPlugin
from plugins.agent.invoke.GreenInvokePlugin import GreenInvokePlugin
from plugins.environment.network.SocialNetworkPlugin import SocialNetworkPlugin

from experiment_config import ExperimentConfig
from node_selector import select_target_nodes
from clarification_injector import ClarificationInjector
from mechanism_v2 import (
    PUBLIC_EXPOSURE_RATE,
    build_exposure_audit,
    one_hop_amplification_nodes,
    select_public_exposure_nodes,
)
from metrics_calculator import compute_metrics, SimulationMetrics
from generate_data import FORRESTER_2026_CLUSTERS, SOCIAL_MEDIA_ROLES, ROLE_PROBS, SOCIAL_ROLES  # kept for reference

resource_maps = {
    "agent_components": {
        "profile": ProfileComponent, "state": StateComponent,
        "perceive": PerceiveComponent, "reflect": ReflectComponent,
        "plan": PlanComponent, "invoke": InvokeComponent
    },
    "agent_plugins": {
        "GreenProfilePlugin": GreenProfilePlugin, "GreenStatePlugin": GreenStatePlugin,
        "GreenPerceivePlugin": GreenPerceivePlugin, "GreenCognitionPlugin": GreenCognitionPlugin,
        "ConsumerPlanPlugin": ConsumerPlanPlugin, "GreenInvokePlugin": GreenInvokePlugin
    },
    "system_components": {"timer": Timer, "messager": Messager},
    "environment_components": {}, "action_components": {}, "controller": None
}

# Oatly 真实事件时间轴（基于公开报道）
ENTERPRISE_STRATEGY = {
    1: (
        "Oatly's Barista Edition oat milk is expanding rapidly across the US. "
        "The brand now supplies over 10,000 coffee shops in North America, up from 2,000 two years ago. "
        "Oatly holds B Corp certification (score: 93.4/200, above the 80-point qualifying threshold) "
        "and publishes an annual sustainability report disclosing its carbon footprint at 0.44 kg CO₂e "
        "per liter — roughly 80% lower than conventional dairy milk. "
        "The brand's signature ad 'It's like milk, but made for humans' goes viral with 4.2 million "
        "organic shares. Independent barista forums rate Oatly Barista as the #1 plant-based milk "
        "for latte art, citing its consistent micro-foam texture. Oatly is widely regarded as the "
        "most credible and transparent brand in the sustainable food sector."
    ),
    5: (
        "BREAKING: Oatly sold a 10% stake ($200 million) to an investment group led by "
        "Blackstone Group in July 2020. Blackstone is the world's largest private equity "
        "firm, directly linked to Amazon deforestation in Brazil, and its CEO Stephen "
        "Schwarzman is a major donor to Trump's political campaigns opposing climate policy. "
        "Activists on Twitter are trending #BoycottOatly, calling this a 'sell-out' and "
        "'enabling Blackstone to greenwash its climate-damaging portfolio.' "
        "Critics say Oatly has 'sold its soul for growth capital.' "
        "Oatly defended the deal, saying the investment would help them scale sustainably — "
        "but many long-time fans feel profoundly betrayed."
    ),
    10: (
        "HEALTH BACKLASH: A popular nutrition blogger's post exposing Oatly's ingredient "
        "list goes viral. Critics highlight that Oatly Barista contains rapeseed (canola) "
        "oil and high levels of rapidly digestible starch from enzymatic processing, "
        "which can cause significant blood sugar spikes — one analysis showed a glycemic "
        "response comparable to Coca-Cola. The post has been shared over 100,000 times. "
        "Many consumers feel misled: they bought Oatly thinking it was a health food, "
        "but are now questioning whether it is 'just glorified sugar water.' "
        "Note: mainstream nutrition scientists largely dispute these claims, but the "
        "viral perception damage is already spreading across social media."
    ),
    15: (
        "INVESTOR LAWSUIT & SHORT SELLER ATTACK: Just weeks after Oatly's May 2021 "
        "Nasdaq IPO (OTLY), activist short-seller Spruce Point Capital publishes a "
        "devastating 68-page report accusing Oatly of: overstating revenue and margins, "
        "exaggerating its sustainability impact in official filings, misleading investors "
        "about growth in China, and producing abnormally high wastewater at its New "
        "Jersey plant. Oatly's stock crashes 30% in a single day. "
        "A class-action securities lawsuit is filed. "
        "Oatly later settles a greenwashing lawsuit for $9.25 million in 2024. "
        "Consumer trust in the brand hits a new low as the IPO scandal reinforces "
        "earlier fears that Oatly was always more about marketing than sustainability."
    ),
}


AGENT_RECORDS_SCHEMA_VERSION = "2.0"

# ══════════════════════════════════════════════════════════════════════
# agent_records schema v2.0 — 60 个唯一字段（单一事实来源）
#   v1.0 的 21 个字段全部保留，且相对顺序与 v1.0 一致（新增字段插入其间）
#   其余 39 个为新增审计字段
#   注意：trust_after_decay 只出现一次；高精度版本使用不同名的 trust_after_decay_raw
#   澄清四阶段（target/injected/received/detected_by_plan）语义互不替代，禁止合并
# ══════════════════════════════════════════════════════════════════════
AGENT_RECORDS_FIELDS = [
    # ── 标识与 schema（6）──
    "schema_version", "exp_id", "tick", "agent_id", "cluster_type", "social_role",
    # ── 实验因子（4）──
    "content_factor", "channel_factor", "timing_factor", "clarification_tick_config",
    # ── v1.0 兼容信任链（7，round(…,4) 精度不变）──
    "trust_score", "baseline_trust", "trust_after_decay",
    "affective_change", "shock_anchor", "quiet_ticks", "decay_lambda",
    # ── 高精度信任链审计（13，round(…,12)）──
    "previous_trust_raw", "baseline_trust_raw", "trust_after_decay_raw",
    "affective_change_raw", "trust_score_raw",
    "shock_anchor_before_raw", "shock_anchor_after_raw",
    "decay_rate_raw", "sensitivity_multiplier",
    "trust_clipped_at_bound", "anchor_update_branch",
    "clr_anchor_lift_ratio", "clr_lift_raw",
    # ── System 1 / Reflect 审计（7）──
    "raw_affective_output", "trust_change_affective_used", "affective_was_clipped",
    "reflect_primary_source", "reflect_message_sources",
    "observation_count", "observation_sources",
    # ── 行为决策（5）──
    "is_buying", "is_posting", "post_content", "plan_reason", "plan_fallback_used",
    # ── 认知输出（3，v1.0）──
    "hypocrisy_perceived", "importance", "reasoning",
    # ── 全局事件两阶段 + 澄清四阶段审计（10）──
    #   has_global_event : v1.0 兼容别名（值 == global_event_scheduled），deprecated
    #   has_clarification: v1.0 兼容列，语义为"配置声称本 Tick 注入"（实验级）
    "has_global_event", "global_event_scheduled", "global_event_received",
    "has_clarification",
    "is_clarification_target",        # 阶段① 是否在 target_nodes 内
    "clarification_injected",         # 阶段② 注入器本 Tick 是否实际写入其 inbox
    "clarification_received",         # 阶段③ 是否实际出现在其 observations 中
    "clarification_detected_by_plan",  # 阶段④ Plan 层是否实际识别到澄清
    "clarification_content_type", "is_quiet_day",
    # ── 网络与 Tick 汇总（5）──
    "out_degree", "in_degree",
    "tick_posts_total", "tick_buys_total", "cumulative_buyers",
]

assert len(AGENT_RECORDS_FIELDS) == 60, \
    f"agent_records schema v2.0 必须为 60 字段，实际 {len(AGENT_RECORDS_FIELDS)}"
assert len(AGENT_RECORDS_FIELDS) == len(set(AGENT_RECORDS_FIELDS)), \
    "agent_records schema v2.0 存在重复字段"


MECHANISM_RECORDS_SCHEMA_VERSION = "1.0"
MECHANISM_RECORDS_FIELDS = [
    "schema_version",
    "exp_id", "tick", "agent_id",
    "content_factor", "channel_factor", "timing_factor", "clarification_tick_config",
    "semantic_observation_present", "semantic_social_observation_count",
    "semantic_valence", "semantic_arousal", "semantic_credibility",
    "semantic_evidence_strength", "semantic_topic_relevance",
    "semantic_hypocrisy_perceived",
    "semantic_fallback_used", "reflect_primary_source",
    "previous_trust", "baseline_trust", "trust_before_signal",
    "affective_change", "trust_final",
    "attitude_att", "subjective_norm_sn", "pbc",
    "emotion_valence", "emotion_arousal",
    "crisis_memory_before", "repair_memory_before",
    "crisis_memory", "repair_memory",
    "purchase_intention", "posting_intention",
    "buy_probability", "post_probability",
    "buy_draw", "post_draw",
    "is_buying", "is_posting",
    "plan_fallback_used",
    "clarification_detected_by_plan", "clarification_content_type",
]

assert len(MECHANISM_RECORDS_FIELDS) == len(set(MECHANISM_RECORDS_FIELDS)), \
    "mechanism_records schema v1.0 存在重复字段"


def _audit_float(value, digits: int = 12):
    """审计浮点：保留 12 位小数，用于事后高精度复算。

    12 位小数远细于本模型任何有意义的数值差异（>1e-9 的差异必然可分辨），
    但**不是** float64 的无损表示——十进制文本 CSV 一般无法无损往返 float64。
    行为不变性因此不依赖本函数：它直接比较运行期未舍入的内存状态（见 tests/…）。
    不可转换（含 None / 空字符串）时返回 ""，禁止用 0 冒充"不适用"。
    """
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return ""


def _observed_source_present(observations, source: str, msg_type: str = "") -> bool:
    """给定的观察快照中是否**实际存在**指定来源的消息。

    入参是**观察列表**（不是 state_data）：TASK_002 / R11 刻意用签名把"取哪份快照"
    的决定权收归调用方（build_agent_record 内唯一的一行），使本函数在类型层面
    无法再去读取 state，也就不可能出现第二份快照。

    唯一合法的快照是 state_data["last_observations"]（Reflect 为本 Tick 保存的只读快照）。
    **不得**回退到 state_data["observations"]：后者是 Perceive 侧的累积容器，
    可能含跨 Tick 残留，用它回退会把"本 Tick 没观察到"染成"观察到了"。
    同样**严禁**用 tick 与 ENTERPRISE_STRATEGY / config.clarification_tick 的比较来推断
    ——那只能证明"安排过"，不能证明"收到了"。
    """
    for o in (observations or []):
        if not isinstance(o, dict):
            continue
        if o.get("source") == source:
            return True
        if msg_type and o.get("type") == msg_type:
            return True
    return False


def compute_network_hash(graph) -> str:
    """网络结构指纹：**同时**覆盖排序后的节点集合与排序后的边集合。
    只哈希 edges 会漏掉孤立节点的增删，因此 nodes 必须一起进入 payload。"""
    nodes = sorted(str(n) for n in graph.nodes())
    edges = sorted([str(u), str(v)] for u, v in graph.edges())
    payload = json.dumps({"nodes": nodes, "edges": edges},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_network_meta(net_plugin, config) -> dict:
    """从 SocialNetworkPlugin 的纯审计属性读取**真实建图分支**，不做任何硬编码推断。"""
    graph = net_plugin.graph
    return {
        "exp_id": config.exp_id,
        "network_type": getattr(net_plugin, "network_type", "unknown"),
        "network_params": getattr(net_plugin, "network_params", {}),
        "network_fallback_reason": getattr(net_plugin, "network_fallback_reason", ""),
        "is_directed": graph.is_directed(),
        "num_nodes": graph.number_of_nodes(),
        "num_edges": graph.number_of_edges(),
        "network_hash": compute_network_hash(graph),
    }


def build_target_nodes_meta(graph, config, target_nodes) -> list:
    """目标节点选择审计明细。

    Hub 渠道   : selection_metric = out_degree / degree，metric_value = 真实度数，rank = 名次
    Random 渠道: selection_metric = "random_sample"，metric_value = ""（不适用），rank = ""
                 —— 禁止用 0 表示"不适用"，否则与"度数确为 0"无法区分。
    """
    rows = []
    if config.channel_factor == "hub":
        metric_name = "out_degree" if graph.is_directed() else "degree"
        degree_view = dict(graph.out_degree()) if graph.is_directed() else dict(graph.degree())
        for rank, node_id in enumerate(target_nodes, start=1):
            rows.append({
                "exp_id": config.exp_id,
                "content_factor": config.content_factor,
                "channel_factor": config.channel_factor,
                "timing_factor": config.timing_factor,
                "agent_id": node_id,
                "selection_metric": metric_name,
                "metric_value": degree_view.get(node_id, 0),
                "rank": rank,
            })
    else:
        for node_id in target_nodes:
            rows.append({
                "exp_id": config.exp_id,
                "content_factor": config.content_factor,
                "channel_factor": config.channel_factor,
                "timing_factor": config.timing_factor,
                "agent_id": node_id,
                "selection_metric": "random_sample",
                "metric_value": "",
                "rank": "",
            })
    return rows


def build_network_nodes_meta(net_plugin, agents) -> list:
    """network_nodes.csv 的行数据：每个节点一行（度数 + 人群 + 社交角色）。

    TASK_002 / R10：本表是 **run 级静态拓扑事实**，因此行内**不含** exp_id，
    也**不含** is_clarification_target ——
      · exp_id：拓扑由 (num_agents, random_seed) 唯一决定，全 run 相同，按实验重复即冗余；
      · is_clarification_target：随 channel_factor 变化，属实验级事实，
        唯一落点是 target_nodes.csv（以及 agent_records.csv 的同名列）。
        Keeping it in run-level files would mix the 8 strategy target sets by write order.

    度数取自 SocialNetworkPlugin.export_node_degrees()（真实图），
    人群与社交角色取自各 Agent 的 profile 插件真实数据，不做任何猜测。
    """
    degrees = net_plugin.export_node_degrees()
    profile_by_id = {}
    for ag in agents:
        comp = ag.get_component("profile")
        pl = getattr(comp, "_plugin", getattr(comp, "plugin", None)) if comp else None
        p_data = getattr(pl, "_profile_data", getattr(pl, "profile_data", {})) if pl else {}
        psy = (p_data or {}).get("psychology", {})
        profile_by_id[ag.agent_id] = (psy.get("cluster_type", "Unknown"),
                                      psy.get("social_role", "Unknown"))
    rows = []
    for node_id in sorted(degrees.keys()):
        cluster, role = profile_by_id.get(node_id, ("Unknown", "Unknown"))
        rows.append({
            "agent_id": node_id,
            "cluster_type": cluster,
            "social_role": role,
            "out_degree": degrees[node_id]["out_degree"],
            "in_degree": degrees[node_id]["in_degree"],
        })
    return rows


def build_network_edges_meta(net_plugin) -> list:
    """network_edges.csv 的行数据：每条有向边一行（按字典序，可复现）。

    TASK_002 / R10：run 级静态文件，行内**不含** exp_id。
    """
    is_dir = net_plugin.graph.is_directed()
    return [
        {"source_agent_id": u, "target_agent_id": v, "is_directed": is_dir}
        for u, v in net_plugin.export_edges()
    ]


def build_effective_event_timeline(strategy: dict) -> list:
    """本次实验**实际生效**的全局事件时间线快照。

    strategy 必须是运行期真正被主循环读取的那个字典对象（模块级 ENTERPRISE_STRATEGY，
    可能已被 run_experiments._run_with_patch 就地改写为"只保留 Tick 5"）。
    禁止调用方从常量或配置重建该时间线。
    """
    timeline = []
    for tick in sorted(int(t) for t in strategy.keys()):
        text = str(strategy[tick])
        timeline.append({
            "tick": tick,
            "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "char_count": len(text),
        })
    return timeline


def build_agent_record(*, config, tick, agent_id, cluster_type, social_role,
                       trust, s_data, plan, thought,
                       out_degree, in_degree,
                       is_clarification_target, clarification_injected,
                       cumulative_buyers_count) -> dict:
    """构造一条 agent_records v2.0 记录（60 字段）。

    tick_posts_total / tick_buys_total 先置 0，由主循环在本 Tick 全部 Agent 结算完成后回填。

    澄清四阶段的来源分工（禁止互相顶替）：
      ① is_clarification_target  ← 入参（injector.target_nodes 成员）
      ② clarification_injected   ← 入参（injector.last_injected_ids 回执）
      ③ clarification_received   ← 本函数内从**唯一的 last_observations 快照**判定
      ④ clarification_detected_by_plan ← plan_result（Plan 层自己的识别结果）
    global_event_received 同样只从该快照判定，不使用 tick 比较。

    TASK_002 / R11 单一快照契约：last_obs 在下面只取一次，
    observation_count / observation_sources / clarification_received /
    global_event_received 四者**全部复用同一个 last_obs 变量**。
    禁止在本函数内第二次读取 s_data 的观察容器，也禁止回退到 s_data["observations"]
    ——否则会产出 observation_count=0 却 clarification_received=True 之类自相矛盾的记录。
    """
    # ── 唯一观察快照（R11）：本函数内**只此一处**读取观察容器 ──
    last_obs = s_data.get("last_observations") or []
    obs_sources = ";".join(sorted({str(o.get("source", "Unknown")) for o in last_obs
                                   if isinstance(o, dict)}))
    refl_sources = s_data.get("reflect_message_sources") or []
    record = {
        # ── 标识与 schema ──
        "schema_version":            AGENT_RECORDS_SCHEMA_VERSION,
        "exp_id":                    config.exp_id,
        "tick":                      tick,
        "agent_id":                  agent_id,
        "cluster_type":              cluster_type,
        "social_role":               social_role,
        # ── 实验因子 ──
        "content_factor":            config.content_factor,
        "channel_factor":            config.channel_factor,
        "timing_factor":             config.timing_factor,
        "clarification_tick_config": (config.clarification_tick
                                      if config.clarification_tick is not None else ""),
        # ── v1.0 兼容字段（精度保持 round(…,4)，禁止改动）──
        "trust_score":               round(trust, 4),
        "baseline_trust":            round(float(s_data.get("baseline_trust", trust)), 4),
        "trust_after_decay":         round(float(plan.get("trust_after_decay", trust)), 4),
        "affective_change":          round(float(plan.get("affective_change", 0.0)), 4),
        "shock_anchor":              round(float(plan.get("shock_anchor", trust)), 4),
        "quiet_ticks":               int(plan.get("quiet_ticks", 0)),
        "decay_lambda":              float(plan.get("decay_lambda", 0.0)),
        # ── 高精度审计字段（round(…,12)，源头为未舍入 float）──
        "previous_trust_raw":        _audit_float(plan.get("previous_trust_raw", "")),
        "baseline_trust_raw":        _audit_float(plan.get("baseline_trust_raw", "")),
        "trust_after_decay_raw":     _audit_float(plan.get("trust_after_decay_raw", "")),
        "affective_change_raw":      _audit_float(plan.get("affective_change_raw", "")),
        "trust_score_raw":           _audit_float(plan.get("trust_score_raw", "")),
        "shock_anchor_before_raw":   _audit_float(plan.get("shock_anchor_before_raw", "")),
        "shock_anchor_after_raw":    _audit_float(plan.get("shock_anchor_after_raw", "")),
        "decay_rate_raw":            _audit_float(plan.get("decay_rate_raw", "")),
        "sensitivity_multiplier":    _audit_float(plan.get("sensitivity_multiplier", "")),
        "trust_clipped_at_bound":    bool(plan.get("trust_clipped_at_bound", False)),
        "anchor_update_branch":      str(plan.get("anchor_update_branch", "")),
        "clr_anchor_lift_ratio":     _audit_float(plan.get("clr_anchor_lift_ratio", "")),
        "clr_lift_raw":              _audit_float(plan.get("clr_lift_raw", "")),
        # ── System 1 / Reflect 审计 ──
        "raw_affective_output":        _audit_float(s_data.get("raw_affective_output", 0.0)),
        "trust_change_affective_used": _audit_float(s_data.get("trust_change_affective", 0.0)),
        "affective_was_clipped":       bool(s_data.get("affective_was_clipped", False)),
        "reflect_primary_source":      str(s_data.get("reflect_primary_source", "")),
        "reflect_message_sources":     ";".join(str(x) for x in refl_sources),
        # ↓ 与 clarification_received / global_event_received 同源于 last_obs（R11）
        "observation_count":           len(last_obs),
        "observation_sources":         obs_sources,
        # ── 行为决策 ──
        "is_buying":                 bool(plan.get("is_buying", False)),
        "is_posting":                bool(plan.get("is_posting", False)),
        "post_content":              str(plan.get("post_content", ""))[:200],
        "plan_reason":               str(plan.get("reason", ""))[:300],
        "plan_fallback_used":        bool(plan.get("plan_fallback_used", False)),
        # ── 认知输出 ──
        "hypocrisy_perceived":       bool(thought.get("hypocrisy_perceived", False)),
        "importance":                float(thought.get("importance", 0.0)),
        "reasoning":                 str(thought.get("reasoning", ""))[:300],
        # ── 全局事件两阶段 ──
        #   scheduled: 运行期实际生效的事件时间线是否在本 Tick 安排了事件（调度事实）
        #   received : 该 Agent 是否**实际观察到** Global News（禁止用 tick 比较推断）
        "has_global_event":       tick in ENTERPRISE_STRATEGY,   # v1.0 兼容别名
        "global_event_scheduled": tick in ENTERPRISE_STRATEGY,
        # R11：只查 last_obs 这一份快照，无 observations 回退
        "global_event_received":  _observed_source_present(last_obs, "Global News"),
        # ── 澄清四阶段（语义互不替代）──
        "has_clarification":              (config.clarification_tick == tick),  # 配置声称
        "is_clarification_target":        bool(is_clarification_target),        # ①
        "clarification_injected":         bool(clarification_injected),         # ②
        "clarification_received":         _observed_source_present(              # ③ R11
            last_obs, "Enterprise_Clarification", "clarification"),
        "clarification_detected_by_plan": bool(                                  # ④
            plan.get("clarification_detected_by_plan", False)),
        "clarification_content_type":     str(plan.get("clarification_content_type", "")),
        "is_quiet_day":                   bool(plan.get("is_quiet_day", False)),
        # ── 网络与 Tick 汇总 ──
        "out_degree":                int(out_degree),
        "in_degree":                 int(in_degree),
        "tick_posts_total":          0,
        "tick_buys_total":           0,
        "cumulative_buyers":         cumulative_buyers_count,
    }
    assert set(record.keys()) == set(AGENT_RECORDS_FIELDS), \
        "agent_records 记录字段与 schema v2.0 不一致"
    return record


def build_mechanism_record(*, config, tick, agent_id, s_data, plan, thought) -> dict:
    """Persist mechanism-v2 values actually present in this Agent/Tick snapshot.

    This is reporting-only audit data. Values come from Reflect state and the
    Plan-layer plan_result; this function must not recompute mechanism equations.
    """
    latest_thought = thought if isinstance(thought, dict) else {}
    clr_tick = config.clarification_tick if config.clarification_tick is not None else ""
    record = {
        "schema_version": MECHANISM_RECORDS_SCHEMA_VERSION,
        "exp_id": config.exp_id,
        "tick": tick,
        "agent_id": agent_id,
        "content_factor": config.content_factor,
        "channel_factor": config.channel_factor,
        "timing_factor": config.timing_factor,
        "clarification_tick_config": clr_tick,
        "semantic_observation_present": bool(s_data.get("semantic_observation_present", False)),
        "semantic_social_observation_count": int(
            s_data.get("semantic_social_observation_count", 0)
        ),
        "semantic_valence": _audit_float(s_data.get("semantic_valence", "")),
        "semantic_arousal": _audit_float(s_data.get("semantic_arousal", "")),
        "semantic_credibility": _audit_float(s_data.get("semantic_credibility", "")),
        "semantic_evidence_strength": _audit_float(
            s_data.get("semantic_evidence_strength", "")
        ),
        "semantic_topic_relevance": _audit_float(
            s_data.get("semantic_topic_relevance", "")
        ),
        "semantic_hypocrisy_perceived": bool(
            s_data.get("semantic_hypocrisy_perceived", False)
        ),
        "semantic_fallback_used": bool(latest_thought.get("semantic_fallback_used", False)),
        "reflect_primary_source": str(s_data.get("reflect_primary_source", "")),
        "previous_trust": _audit_float(plan.get("previous_trust_raw", "")),
        "baseline_trust": _audit_float(plan.get("baseline_trust_raw", "")),
        "trust_before_signal": _audit_float(plan.get("trust_after_decay_raw", "")),
        "affective_change": _audit_float(plan.get("affective_change_raw", "")),
        "trust_final": _audit_float(plan.get("trust_score_raw", "")),
        "attitude_att": _audit_float(plan.get("attitude_att", "")),
        "subjective_norm_sn": _audit_float(plan.get("subjective_norm_sn", "")),
        "pbc": _audit_float(plan.get("pbc", "")),
        "emotion_valence": _audit_float(plan.get("emotion_valence", "")),
        "emotion_arousal": _audit_float(plan.get("emotion_arousal", "")),
        "crisis_memory_before": _audit_float(plan.get("crisis_memory_before", "")),
        "repair_memory_before": _audit_float(plan.get("repair_memory_before", "")),
        "crisis_memory": _audit_float(plan.get("crisis_memory", "")),
        "repair_memory": _audit_float(plan.get("repair_memory", "")),
        "purchase_intention": _audit_float(plan.get("purchase_intention", "")),
        "posting_intention": _audit_float(plan.get("posting_intention", "")),
        "buy_probability": _audit_float(plan.get("buy_probability", "")),
        "post_probability": _audit_float(plan.get("post_probability", "")),
        "buy_draw": _audit_float(plan.get("buy_draw", "")),
        "post_draw": _audit_float(plan.get("post_draw", "")),
        "is_buying": bool(plan.get("is_buying", False)),
        "is_posting": bool(plan.get("is_posting", False)),
        "plan_fallback_used": bool(plan.get("plan_fallback_used", False)),
        "clarification_detected_by_plan": bool(
            plan.get("clarification_detected_by_plan", False)
        ),
        "clarification_content_type": str(plan.get("clarification_content_type", "")),
    }
    assert set(record.keys()) == set(MECHANISM_RECORDS_FIELDS), \
        "mechanism_records 记录字段与 schema v1.0 不一致"
    return record


def _generate_profiles_inline(num_agents: int, seed: int) -> list:
    """
    内联生成 Agent profiles（不写文件）。
    与 generate_data.py 的配额制逻辑保持一致：按 AGENT_QUOTA 比例分配群体，
    然后随机打乱顺序，保证同 seed 下结果可复现。
    """
    from generate_data import AGENT_QUOTA, FORRESTER_2026_CLUSTERS, SOCIAL_MEDIA_ROLES, ROLE_PROBS, SOCIAL_ROLES

    rng_random = random_module.Random(seed)
    rng_np     = np.random.RandomState(seed)

    # 按配额比例计算每个类型的 Agent 数量
    total_quota = sum(AGENT_QUOTA.values())
    quota = {k: max(1, round(v / total_quota * num_agents)) for k, v in AGENT_QUOTA.items()}
    # 误差修正：多余的补到 Dormant_Greens（占比最大，影响最小）
    quota["Dormant_Greens"] += num_agents - sum(quota.values())

    # 按配额展开为 cluster_id 列表并随机打乱
    cluster_order = []
    for cid, count in quota.items():
        cluster_order.extend([cid] * count)
    rng_random.shuffle(cluster_order)

    cluster_map = {c["cluster_id"]: c for c in FORRESTER_2026_CLUSTERS}
    profiles = []

    for i, cluster_id in enumerate(cluster_order):
        agent_id    = f"Consumer_{i:03d}"
        base_cluster = cluster_map[cluster_id]
        role         = rng_np.choice(SOCIAL_ROLES, p=ROLE_PROBS)

        persona_prompt = base_cluster["persona"] + SOCIAL_MEDIA_ROLES[role]

        profiles.append({
            "id":   agent_id,
            "name": agent_id,
            "psychology": {
                "cluster_type": base_cluster["cluster_id"],
                "social_role":  role,
            },
            "persona": persona_prompt,
        })

    return profiles


async def run_simulation_core(config: ExperimentConfig, override_router=None) -> dict:
    """
    可复用仿真核心函数。

    Args:
        config: ExperimentConfig 实例
        override_router: 可选。若提供，跳过内部 LLM Router 初始化，直接使用此对象。
                         用于对照实验中的 Recording/Replay Router 注入。

    Returns:
        {
            "exp_id": str,
            "config": dict,
            "metrics": SimulationMetrics,
            "trust_trajectory": List[float],
            "conversion_trajectory": List[float],
        }
    """
    # ── 1. 设置随机种子 ──────────────────────────────────────────────
    random_module.seed(config.random_seed)
    np.random.seed(config.random_seed)

    # ── 2. 生成 Agent profiles 并写入临时文件，让 Builder 正常解析 ──
    # 这样完全复用框架的 Pydantic 验证路径，避免手工构造 AgentComponentConfig 对象
    profiles = _generate_profiles_inline(config.num_agents, config.random_seed)

    tmp_profiles_path = os.path.join(current_dir, "data", "agents", "_tmp_profiles.jsonl")
    os.makedirs(os.path.dirname(tmp_profiles_path), exist_ok=True)

    # 备份原始 profiles.jsonl，写入临时数据
    original_profiles_path = os.path.join(current_dir, "data", "agents", "profiles.jsonl")
    original_backup_path   = os.path.join(current_dir, "data", "agents", "profiles.jsonl.bak")
    profiles_swapped = False
    try:
        if os.path.exists(original_profiles_path):
            os.rename(original_profiles_path, original_backup_path)
        with open(original_profiles_path, "w", encoding="utf-8") as f:
            for p in profiles:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        profiles_swapped = True

        # ── 3. Builder 正常解析（走 Pydantic 验证，生成真实 AgentConfig 对象）──
        builder = Builder(current_dir, resource_maps)
        builder._load_data_into_config()
        agent_configs = builder.config.agents

    finally:
        # 恢复原始 profiles.jsonl
        if profiles_swapped:
            if os.path.exists(original_profiles_path):
                os.remove(original_profiles_path)
            if os.path.exists(original_backup_path):
                os.rename(original_backup_path, original_profiles_path)

    # ── 4. 构建环境与网络插件（不在此处建图，延迟到 Agents 初始化后） ──
    env = Environment()
    net_plugin = SocialNetworkPlugin()
    net_comp = EnvironmentComponent()
    net_comp.plugin = net_plugin
    net_comp._plugin = net_plugin
    net_plugin.component = net_comp

    # ── 5. 初始化 Agents ─────────────────────────────────────────────
    agents = []
    for conf in agent_configs:
        agent = Agent(conf.id, conf.component_order)
        agent.env = env
        await agent.init(conf.components, resource_maps)
        for name, comp in agent._components.items():
            comp._agent = agent
            plugin = getattr(comp, "plugin", None)
            if plugin:
                comp._plugin = plugin
                plugin.component = comp
        agents.append(agent)

    # 网络构建：调用 register_agents() 统一走有向 BA 网络逻辑
    # 与 run_simulation.py 路径行为完全一致
    net_plugin.register_agents(agents, seed=config.random_seed)

    # ── 6. 初始化 LLM Router ────────────────────────────────────────
    if override_router is not None:
        router = override_router
    else:
        try:
            with open(os.path.join(current_dir, "configs/models_config.yaml"), "r") as f:
                models_conf = yaml.safe_load(f)
            router = ModelRouter(AsyncModelRouter(models_conf))
        except Exception:
            class Mock:
                async def chat(self, prompt):
                    if "trust_change_affective" in prompt or "hypocrisy_perceived" in prompt:
                        return json.dumps({
                            "hypocrisy_perceived": True,
                            "trust_change_affective": -1.5,
                            "importance": 7.0,
                            "reasoning": "Mock: I feel betrayed by this brand."
                        })
                    else:
                        return json.dumps({
                            "is_buying": False,
                            "is_posting": True,
                            "post_content": "I can't believe this brand betrayed us!",
                            "reason": "Mock: Trust is too low to buy."
                        })
            router = Mock()

    for ag in agents:
        ag._model = router

    # ── 7. 初始化 Agent 状态 ─────────────────────────────────────────
    # 各消费者类型的初始信任基线（差异化，而非统一 5.0）
    INITIAL_TRUST_MAP = {
        "Active_Greens":     8.0,
        "Convenient_Greens": 6.5,
        "Dormant_Greens":    5.5,
        "Non_Greens":        5.0,
    }
    for ag in agents:
        state_plugin = ag.get_component("state")._plugin
        await state_plugin.set_state("incoming_messages", [])
        await state_plugin.set_state("observations", [])
        await state_plugin.set_state("last_observations", [])   # Plan 层读取的只读快照
        await state_plugin.set_state("latest_thought", None)

        # 根据消费者类型设置差异化初始信任
        p_data = getattr(ag.get_component("profile")._plugin, "_profile_data",
                         getattr(ag.get_component("profile")._plugin, "profile_data", {}))
        cluster_type = p_data.get("psychology", {}).get("cluster_type", "")
        initial_trust = INITIAL_TRUST_MAP.get(cluster_type, 5.5)
        await state_plugin.set_state("trust_score", initial_trust)
        await state_plugin.set_state("baseline_trust", initial_trust)
        await state_plugin.set_state("trust_score_initialized", True)
        await state_plugin.set_state("shock_anchor", initial_trust)
        await state_plugin.set_state("quiet_ticks", 0)
        await state_plugin.set_state("attitude_Att", max(0.0, min(1.0, initial_trust / 10.0)))
        await state_plugin.set_state("subjective_norm_SN", 0.5)
        await state_plugin.set_state("perceived_behavioral_control_PBC", 0.5)
        await state_plugin.set_state("emotion_valence", 0.0)
        await state_plugin.set_state("emotion_arousal", 0.0)
        await state_plugin.set_state("crisis_memory", 0.0)
        await state_plugin.set_state("repair_memory", 0.0)
        await state_plugin.set_state("purchase_intention", 0.0)
        await state_plugin.set_state("posting_intention", 0.0)
        await state_plugin.set_state("behavior_seed_base", int(config.random_seed))
        await state_plugin.set_state("ever_purchased", False)
        await state_plugin.set_state("last_post_tick", None)

    # ── 8. 初始化澄清注入器 ─────────────────────────────────────────
    injector = ClarificationInjector(config)
    if config.is_control:
        target_nodes = []
    else:
        target_nodes = select_target_nodes(
            net_plugin.graph, config.channel_factor, config.budget_k, config.random_seed
        )
    injector.set_target_nodes(target_nodes)

    # Mechanism-v2: separate public statement availability from paid seed allocation.
    if config.is_control:
        public_exposure_nodes = []
        amplified_nodes = []
    else:
        public_exposure_nodes = select_public_exposure_nodes(
            net_plugin.graph.nodes(), config.random_seed, PUBLIC_EXPOSURE_RATE
        )
        amplified_nodes = one_hop_amplification_nodes(net_plugin.graph, target_nodes)

    injector.set_public_exposure_nodes(public_exposure_nodes)
    injector.set_amplified_nodes(amplified_nodes)
    clarification_exposure_meta = build_exposure_audit(
        net_plugin.graph, config.exp_id,
        public_exposure_nodes, target_nodes, amplified_nodes
    )

    # ── 8b. 网络 / 目标节点审计元数据（TASK_002，只读，不改变任何选点或建图逻辑）──
    network_meta      = build_network_meta(net_plugin, config)
    target_nodes_meta = build_target_nodes_meta(net_plugin.graph, config, target_nodes)
    # R10：run 级拓扑事实，构造时不带 config / target_nodes。
    #      Returned per experiment so the runner can verify the 8 strategies + 1 common control share one topology.
    network_nodes     = build_network_nodes_meta(net_plugin, agents)
    network_edges     = build_network_edges_meta(net_plugin)
    _is_dir           = net_plugin.graph.is_directed()
    out_degree_map    = dict(net_plugin.graph.out_degree()) if _is_dir else dict(net_plugin.graph.degree())
    in_degree_map     = dict(net_plugin.graph.in_degree())  if _is_dir else dict(net_plugin.graph.degree())
    target_node_set   = set(target_nodes or [])
    print(f"🧾 [Audit] network_type={network_meta['network_type']} "
          f"params={network_meta['network_params']} "
          f"hash={network_meta['network_hash'][:12]}")

    # ── 8c. 本次实验**实际生效**的全局事件时间线（TASK_002 / R4）──
    #   直接对运行期的 ENTERPRISE_STRATEGY 取快照：run_experiments._run_with_patch
    #   会就地把它改写为"只保留 Tick 5 丑闻"，因此此处采集到的才是真实生效的时间线。
    #   禁止任何下游从常量重建该时间线。
    effective_event_timeline = build_effective_event_timeline(ENTERPRISE_STRATEGY)
    print(f"🧾 [Audit] effective_event_ticks="
          f"{[e['tick'] for e in effective_event_timeline]}")

    # ── 9. 仿真主循环 ───────────────────────────────────────────────
    trust_trajectory = []
    conversion_trajectory = []
    cumulative_buyers = set()
    # 逐 Agent 逐 Tick 详细记录（供后续分析使用）
    agent_records = []    # List[dict]，每条一个 Agent 在一个 Tick 的完整快照
    mechanism_records = [] # List[dict]，每条一个 Agent 在一个 Tick 的 mechanism-v2 快照
    tick_post_counts = [] # 每 Tick 发帖总数（用于社交活跃度分析）
    tick_buy_counts  = [] # 每 Tick 新增购买数

    for tick in range(1, config.total_ticks + 1):
        # 通知 router 当前 Tick（用于 Recording/Replay Router 的缓存对齐）
        if hasattr(router, "set_tick"):
            router.set_tick(tick)

        # 9.1 全局事件注入
        if tick in ENTERPRISE_STRATEGY:
            event_text = ENTERPRISE_STRATEGY[tick]
            event_msg = {"source": "Global News", "content": event_text}
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                s_data = getattr(s_plugin, "state_data", getattr(s_plugin, "_state_data", {}))
                inbox = s_data.get("incoming_messages", [])
                await s_plugin.set_state("incoming_messages", list(inbox) + [event_msg])
                await s_plugin.set_state("current_news", event_text)
        else:
            for ag in agents:
                s_plugin = ag.get_component("state")._plugin
                await s_plugin.set_state("current_news", "")

        # 9.2 企业澄清注入（在 Perceive 之前）
        injected_count = await injector.inject(agents, tick)
        # TASK_002 阶段②：本 Tick 实际写入 inbox 的 Agent，来自注入器回执。
        # 禁止用 should_inject() / (agent_id in target_nodes) 推断——后者是阶段①。
        # 直接读属性而非 getattr 兜底：注入器缺少回执属性时必须**立刻报错**，
        # 而不是静默退化成"本 Tick 没有任何 Agent 被注入"（那会让阶段②全为 False）。
        clarification_injected_ids = set(injector.last_injected_ids or [])

        # ── 澄清注入当天：同步更新 current_news，让 Plan 层感知到澄清事件 ──
        # 否则 Plan 层会把澄清当成"平静日"，quiet_ticks 继续累加，
        # 遗忘曲线把信任往 baseline 拉，而澄清的正向冲击被抵消
        if injected_count > 0:
            clarification_headline = (
                "[Enterprise Clarification] The brand has issued an official statement "
                "addressing the controversy. The company responds to the greenwashing allegations."
            )
            for ag in agents:
                if ag.agent_id in clarification_injected_ids:
                    s_plugin = ag.get_component("state")._plugin
                    # current_news 更新 → Plan 层 is_quiet_day=False → quiet_ticks 不累加
                    await s_plugin.set_state("current_news", clarification_headline)

        # 9.3 认知管线
        for ag in agents:
            s_plugin = ag.get_component("state")._plugin
            await s_plugin.set_state("time_context", f"Day {tick} of the simulation.")
            await s_plugin.set_state("current_tick", tick)
            await ag.get_component("perceive").execute(tick)
            await ag.get_component("reflect").execute(tick)

        # 9.4 计划与执行
        for ag in agents:
            await ag.get_component("plan").execute(tick)
            await ag.get_component("invoke").execute(tick)

        # 9.5 数据结算
        trust_list = []
        tick_buys = 0
        tick_posts = 0
        for ag in agents:
            s_data = getattr(ag.get_component("state")._plugin, "state_data",
                             getattr(ag.get_component("state")._plugin, "_state_data", {}))
            p_data = getattr(ag.get_component("profile")._plugin, "_profile_data",
                             getattr(ag.get_component("profile")._plugin, "profile_data", {}))
            trust = float(s_data.get("trust_score", 5.0))
            trust_list.append(trust)

            plan    = s_data.get("plan_result", {}) or {}
            thought = s_data.get("latest_thought", {}) or {}
            cluster = p_data.get("psychology", {}).get("cluster_type", "Unknown")
            role    = p_data.get("psychology", {}).get("social_role", "Unknown")
            is_buying_flag  = bool(plan.get("is_buying", False))
            is_posting_flag = bool(plan.get("is_posting", False))

            if is_buying_flag:
                tick_buys += 1
                cumulative_buyers.add(ag.agent_id)
            if is_posting_flag:
                tick_posts += 1

            # 逐 Agent 详细记录（schema v2.0，60 字段；集中构造便于单测校验字段集合）
            agent_records.append(build_agent_record(
                config=config,
                tick=tick,
                agent_id=ag.agent_id,
                cluster_type=cluster,
                social_role=role,
                trust=trust,
                s_data=s_data,
                plan=plan,
                thought=thought,
                out_degree=out_degree_map.get(ag.agent_id, 0),
                in_degree=in_degree_map.get(ag.agent_id, 0),
                # 阶段①：是否被选为投放目标
                is_clarification_target=(ag.agent_id in target_node_set),
                # 阶段②：注入器本 Tick 是否确实写入了它的 inbox（回执，非推断）
                clarification_injected=(ag.agent_id in clarification_injected_ids),
                cumulative_buyers_count=len(cumulative_buyers),
            ))
            mechanism_records.append(build_mechanism_record(
                config=config,
                tick=tick,
                agent_id=ag.agent_id,
                s_data=s_data,
                plan=plan,
                thought=thought,
            ))

        # 回填本 Tick 汇总列（必须等本 Tick 所有 Agent 结算完毕才可知）
        if agents:
            for _rec in agent_records[-len(agents):]:
                _rec["tick_posts_total"] = tick_posts
                _rec["tick_buys_total"]  = tick_buys

        tick_post_counts.append(tick_posts)
        tick_buy_counts.append(tick_buys)

        avg_trust = np.mean(trust_list)
        conversion_rate = len(cumulative_buyers) / len(agents)
        trust_trajectory.append(round(avg_trust, 4))
        conversion_trajectory.append(round(conversion_rate, 4))

        # 9.6 社交路由
        tick_posts_dict = {}
        for ag in agents:
            s_data = getattr(ag.get_component("state")._plugin, "state_data",
                             getattr(ag.get_component("state")._plugin, "_state_data", {}))
            plan = s_data.get("plan_result", {})
            if plan.get("is_posting", False) and plan.get("post_content", "").strip():
                tick_posts_dict[ag.agent_id] = plan["post_content"].strip()

        for ag in agents:
            state_plugin = ag.get_component("state")._plugin
            await state_plugin.set_state("incoming_messages", [])

        for author_id, content in tick_posts_dict.items():
            social_content = f'[Social Media Feed] Connection {author_id} posted: "{content}"'
            await net_plugin.broadcast_message(author_id, social_content)

        # 信箱限流
        for ag in agents:
            state_plugin = ag.get_component("state")._plugin
            msgs = state_plugin.get_state_sync("incoming_messages") or []
            if len(msgs) > 3:
                await state_plugin.set_state("incoming_messages", msgs[-3:])

    # ── 10. 计算多维指标 ─────────────────────────────────────────────
    metrics = compute_metrics(
        trust_trajectory, conversion_trajectory,
        scandal_tick=config.scandal_tick,
        total_ticks=config.total_ticks,
        clarification_tick=config.clarification_tick,
    )

    print(f"📊 [{config.exp_id}] "
          f"ΔRecovery={metrics.delta_recovery:.3f} | "
          f"AUC={metrics.auc_post_scandal:.4f} | "
          f"Speed={metrics.recovery_speed:.4f} | "
          f"Steady={metrics.steady_state_score:.2f} | "
          f"ClarEffect={metrics.clarification_effect:+.3f}")

    return {
        "exp_id": config.exp_id,
        "config": config.to_dict(),
        "metrics": metrics,
        "trust_trajectory": trust_trajectory,
        "conversion_trajectory": conversion_trajectory,
        "agent_records": agent_records,       # 逐 Agent 逐 Tick 详细数据
        "mechanism_records": mechanism_records,
        "mechanism_records_schema_version": MECHANISM_RECORDS_SCHEMA_VERSION,
        "tick_post_counts": tick_post_counts, # 每 Tick 发帖数
        "tick_buy_counts":  tick_buy_counts,  # 每 Tick 新增购买数
        "agent_records_schema_version": AGENT_RECORDS_SCHEMA_VERSION,
        "network_meta": network_meta,             # 真实建图分支 + 结构指纹
        "target_nodes_meta": target_nodes_meta,   # 目标节点选择审计明细
        "clarification_exposure_meta": clarification_exposure_meta,
        "network_nodes": network_nodes,           # run 级 network_nodes.csv 行数据（无 exp_id）
        "network_edges": network_edges,           # run 级 network_edges.csv 行数据（无 exp_id）
        "effective_event_timeline": effective_event_timeline,  # 本次实际生效的事件时间线
    }
