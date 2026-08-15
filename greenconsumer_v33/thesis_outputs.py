"""Thesis-oriented outputs and internal-validity evidence for TASK_005 v3.3.1.

This module is post-processing only. It does not change simulation state,
scientific parameters, seeds, prompts, topology, treatment allocation, or LLM
configuration. The generated checks can support implementation validity,
construct manipulation, process consistency, and reproducibility; they do not
prove external validity or real-world population effect sizes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from .network_animation import animate_network_state

CONTROL = "NoClarification-Control"
OUTPUT_SCHEMA = "task005_fmcg_v331_thesis_outputs1.0"


def _as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})


def _numeric(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _write_csv(df: pd.DataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _write_json(payload: dict, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _condition_order(values: Iterable[str]) -> list[str]:
    canonical = [
        CONTROL,
        "Rational-Hub-Immediate",
        "Rational-Hub-Delayed",
        "Rational-Random-Immediate",
        "Rational-Random-Delayed",
        "Empathy-Hub-Immediate",
        "Empathy-Hub-Delayed",
        "Empathy-Random-Immediate",
        "Empathy-Random-Delayed",
    ]
    available = set(str(v) for v in values)
    return [x for x in canonical if x in available] + sorted(available - set(canonical))


def _load(run_dir: Path) -> dict[str, object]:
    required = [
        "run_summary.json",
        "agent_records.csv",
        "agent_thoughts.csv",
        "cognitive_records.csv",
    ]
    for name in required:
        if not (run_dir / name).exists():
            raise FileNotFoundError(run_dir / name)
    return {
        "summary": json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8")),
        "agent": pd.read_csv(run_dir / "agent_records.csv"),
        "thoughts": pd.read_csv(run_dir / "agent_thoughts.csv"),
        "cognitive": pd.read_csv(run_dir / "cognitive_records.csv"),
        "demand": _read_csv(run_dir / "demand_opportunities.csv"),
        "curves": _read_csv(run_dir / "choice_curves.csv"),
        "estimands": _read_csv(run_dir / "single_block_estimands.csv"),
        "reach": _read_csv(run_dir / "clarification_reach_v33.csv"),
        "network_nodes": _read_csv(run_dir / "network_nodes.csv"),
        "network_edges": _read_csv(run_dir / "network_edges.csv"),
        "targets": _read_csv(run_dir / "target_nodes.csv"),
        "exposure": _read_csv(run_dir / "clarification_exposure_plan.csv"),
    }


def _design_table(summary: dict, agent: pd.DataFrame) -> pd.DataFrame:
    trust = (summary.get("trust_v33_parameters") or {}).get("parameters", {})
    clarification = summary.get("clarification_v33_parameters") or {}
    demand = summary.get("demand_v33") or {}
    git = summary.get("git_provenance") or {}
    conditions = summary.get("conditions_run") or agent["exp_id"].astype(str).unique()
    return pd.DataFrame([{
        "run_id": summary.get("run_id", ""),
        "code_release": summary.get("code_release", ""),
        "schema_version": summary.get("schema_version", ""),
        "scope": summary.get("scope", ""),
        "llm_mode": summary.get("llm_mode", ""),
        "llm_model": summary.get("llm_model", ""),
        "llm_temperature": summary.get("llm_temperature", ""),
        "simulation_seed": summary.get("simulation_seed", ""),
        "requested_llm_seed": summary.get("requested_llm_seed", ""),
        "demand_seed": summary.get("demand_seed", ""),
        "conditions": len(conditions),
        "cognitive_agents": agent["agent_id"].astype(str).nunique(),
        "ticks": pd.to_numeric(agent["tick"], errors="coerce").max(),
        "crisis_retention": trust.get("crisis_retention", ""),
        "repair_retention": trust.get("repair_retention", ""),
        "event_adjustment": trust.get("event_adjustment", ""),
        "quiet_adjustment": trust.get("quiet_adjustment", ""),
        "repair_saturation": trust.get("repair_saturation", ""),
        "hypocrisy_weight": trust.get("hypocrisy_weight", ""),
        "paid_edge_probability": clarification.get("paid_edge_probability", ""),
        "paid_delivery_lag": clarification.get("paid_delivery_lag", ""),
        "renewal_purchase_opportunities": demand.get("renewal_purchase_opportunities", ""),
        "loyalty_update": demand.get("loyalty_update", ""),
        "git_head": git.get("git_head", ""),
        "git_branch": git.get("git_branch", ""),
        "git_dirty": git.get("git_dirty", ""),
        "formal_inference_performed": False,
        "external_validity_claimed": False,
    }])


def _condition_outcomes(data: dict[str, object]) -> pd.DataFrame:
    cog = data["cognitive"].copy()
    agent = data["agent"].copy()
    demand = data["demand"].copy()
    reach = data["reach"].copy()
    _numeric(cog, ["tick", "trust_final", "purchase_intention", "crisis_memory", "repair_memory"])
    _numeric(agent, ["tick", "tick_posts_total"])
    rows = []
    for exp_id in _condition_order(cog["exp_id"].astype(str).unique()):
        c = cog[cog["exp_id"].astype(str) == exp_id]
        a = agent[agent["exp_id"].astype(str) == exp_id]
        post = c[c["tick"].between(6, 30)]
        t30 = c[c["tick"] == 30]
        row = {
            "exp_id": exp_id,
            "content_factor": str(c["content_factor"].iloc[0]) if len(c) else "",
            "channel_factor": str(c["channel_factor"].iloc[0]) if len(c) else "",
            "timing_factor": str(c["timing_factor"].iloc[0]) if len(c) else "",
            "mean_trust_t30": t30["trust_final"].mean(),
            "mean_trust_t6_t30": post["trust_final"].mean(),
            "mean_purchase_intention_t30": t30["purchase_intention"].mean(),
            "mean_crisis_memory_t30": t30["crisis_memory"].mean(),
            "mean_repair_memory_t30": t30["repair_memory"].mean(),
            "total_ugc_posts": int(a.groupby("tick")["tick_posts_total"].max().fillna(0).sum()) if len(a) else 0,
        }
        if not reach.empty and exp_id != CONTROL:
            rr = reach[reach["exp_id"].astype(str) == exp_id]
            if len(rr):
                row["enterprise_reach"] = pd.to_numeric(
                    rr["eventual_enterprise_reach"], errors="coerce"
                ).iloc[0]
        if not demand.empty:
            d = demand[demand["exp_id"].astype(str) == exp_id].copy()
            _numeric(d, ["tick", "choice_probability", "loyalty_after"])
            d = d[d["tick"].between(6, 30)]
            for support in ("absent", "present"):
                ds = d[d["conversion_support"].astype(str) == support]
                if len(ds):
                    row[f"expected_repeat_choice_{support}"] = ds["choice_probability"].mean()
                    row[f"mean_loyalty_{support}"] = ds["loyalty_after"].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def _semantic_tables(thoughts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = thoughts.copy()
    t["clarification_received"] = _as_bool(t["clarification_received"])
    clar = t[t["clarification_received"]].copy()
    metrics = [
        "semantic_valence",
        "semantic_arousal",
        "semantic_credibility",
        "semantic_evidence_strength",
        "semantic_topic_relevance",
        "semantic_perceived_empathy",
    ]
    _numeric(clar, ["tick", *metrics])
    means = clar.groupby("content_factor", dropna=False)[metrics].agg(["mean", "std", "count"])
    means.columns = [f"{a}_{b}" for a, b in means.columns]
    means = means.reset_index()

    r = clar[clar["content_factor"].astype(str) == "rational-evidence"]
    e = clar[clar["content_factor"].astype(str) == "emotional-empathy"]
    keys = ["channel_factor", "timing_factor", "tick", "agent_id"]
    pair = r.merge(e, on=keys, suffixes=("_r", "_e"))
    rows = []
    for metric in metrics:
        d = pair[f"{metric}_r"] - pair[f"{metric}_e"]
        rows.append({
            "metric": metric,
            "paired_n": int(d.notna().sum()),
            "mean_rational_minus_empathy": d.mean(),
            "median_rational_minus_empathy": d.median(),
            "rational_gt_empathy": int((d > 0).sum()),
            "empathy_gt_rational": int((d < 0).sum()),
            "equal": int((d == 0).sum()),
        })
    return means, pd.DataFrame(rows)


def _heterogeneity_tables(cog: pd.DataFrame, agent: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    identity = agent[["exp_id", "agent_id", "cluster_type", "social_role"]].drop_duplicates()
    c = cog.merge(identity, on=["exp_id", "agent_id"], how="left")
    _numeric(c, ["tick", "trust_final", "purchase_intention", "subjective_norm_after"])
    post = c[c["tick"].between(6, 30)]
    segment = post.groupby(["exp_id", "cluster_type"], dropna=False).agg(
        mean_trust_t6_t30=("trust_final", "mean"),
        mean_purchase_intention_t6_t30=("purchase_intention", "mean"),
        mean_sn_t6_t30=("subjective_norm_after", "mean"),
        agent_tick_rows=("agent_id", "size"),
    ).reset_index()

    t1 = c[c["tick"] == 1][["exp_id", "agent_id", "trust_final"]].rename(columns={"trust_final": "trust_t1"})
    t5 = c[c["tick"] == 5][["exp_id", "agent_id", "trust_final"]].rename(columns={"trust_final": "trust_t5"})
    t30 = c[c["tick"] == 30][["exp_id", "agent_id", "cluster_type", "social_role", "trust_final"]].rename(columns={"trust_final": "trust_t30"})
    individual = t30.merge(t1, on=["exp_id", "agent_id"], how="left").merge(
        t5, on=["exp_id", "agent_id"], how="left"
    )
    individual["delta_t30_vs_t5"] = individual["trust_t30"] - individual["trust_t5"]
    return segment, individual


def _mechanism_tick(cog: pd.DataFrame) -> pd.DataFrame:
    c = cog.copy()
    fields = [
        "trust_final", "attitude_att", "subjective_norm_after", "pbc",
        "purchase_intention", "posting_intention", "crisis_memory", "repair_memory",
        "crisis_increment", "repair_increment", "semantic_valence",
        "semantic_credibility", "semantic_evidence_strength",
        "semantic_perceived_empathy",
    ]
    fields = [f for f in fields if f in c.columns]
    _numeric(c, ["tick", *fields])
    return c.groupby(["exp_id", "tick"], dropna=False)[fields].mean().reset_index()


def _support_effects(demand: pd.DataFrame) -> pd.DataFrame:
    if demand.empty:
        return pd.DataFrame()
    d = demand.copy()
    _numeric(d, ["tick", "choice_probability", "loyalty_after"])
    d = d[d["tick"].between(6, 30)]
    agg = d.groupby(["exp_id", "conversion_support"]).agg(
        expected_choice_share=("choice_probability", "mean"),
        mean_loyalty=("loyalty_after", "mean"),
        opportunities=("buyer_id", "size"),
    ).reset_index()
    rows = []
    for exp_id, group in agg.groupby("exp_id"):
        row = {"exp_id": exp_id}
        for support in ("absent", "present"):
            s = group[group["conversion_support"].astype(str) == support]
            if len(s):
                row[f"expected_choice_share_{support}"] = s["expected_choice_share"].iloc[0]
                row[f"mean_loyalty_{support}"] = s["mean_loyalty"].iloc[0]
                row[f"opportunities_{support}"] = s["opportunities"].iloc[0]
        row["support_lift_expected_choice"] = (
            row.get("expected_choice_share_present", np.nan)
            - row.get("expected_choice_share_absent", np.nan)
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _demand_segment(demand: pd.DataFrame, agent: pd.DataFrame) -> pd.DataFrame:
    if demand.empty:
        return pd.DataFrame()
    clusters = agent[["agent_id", "cluster_type"]].drop_duplicates("agent_id")
    d = demand.merge(clusters, on="agent_id", how="left")
    _numeric(d, ["tick", "choice_probability", "loyalty_after"])
    d["focal_brand_chosen"] = _as_bool(d["focal_brand_chosen"])
    d = d[d["tick"].between(6, 30)]
    return d.groupby(["exp_id", "conversion_support", "cluster_type"], dropna=False).agg(
        opportunities=("buyer_id", "size"),
        expected_choice_share=("choice_probability", "mean"),
        realized_choice_share=("focal_brand_chosen", "mean"),
        mean_loyalty_after=("loyalty_after", "mean"),
    ).reset_index()


def _network_metrics(nodes: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    if nodes.empty or edges.empty:
        return pd.DataFrame()
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes["agent_id"].astype(str))
    graph.add_edges_from(zip(edges["source_agent_id"].astype(str), edges["target_agent_id"].astype(str)))
    und = graph.to_undirected()
    weak = list(nx.weakly_connected_components(graph))
    largest = graph.subgraph(max(weak, key=len)).to_undirected() if weak else und
    avg_path = (
        nx.average_shortest_path_length(largest)
        if len(largest) > 1 and nx.is_connected(largest)
        else np.nan
    )
    return pd.DataFrame([{
        "nodes": graph.number_of_nodes(),
        "directed_edges": graph.number_of_edges(),
        "density": nx.density(graph),
        "reciprocity": nx.reciprocity(graph) if graph.number_of_edges() else 0.0,
        "mean_out_degree": np.mean([d for _, d in graph.out_degree()]),
        "max_out_degree": max((d for _, d in graph.out_degree()), default=0),
        "mean_in_degree": np.mean([d for _, d in graph.in_degree()]),
        "weak_components": nx.number_weakly_connected_components(graph),
        "strong_components": nx.number_strongly_connected_components(graph),
        "undirected_average_clustering": nx.average_clustering(und),
        "largest_weak_component_average_path_length": avg_path,
    }])


def _targeting(nodes: pd.DataFrame, targets: pd.DataFrame, exposure: pd.DataFrame) -> pd.DataFrame:
    if nodes.empty or targets.empty:
        return pd.DataFrame()
    out = targets.merge(nodes, on="agent_id", how="left")
    if not exposure.empty:
        cols = [
            c for c in [
                "exp_id", "agent_id", "public_organic", "paid_seed",
                "paid_one_hop", "reached", "exposure_modes"
            ] if c in exposure.columns
        ]
        out = out.merge(exposure[cols], on=["exp_id", "agent_id"], how="left")
    return out


def _social_broadcasts(agent: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct broadcast deliveries implied by actual posting and graph edges.

    This records inbox deliveries, not guaranteed downstream appraisal: the
    recipient inbox may subsequently be capped to its last three messages.
    """
    if edges.empty:
        return pd.DataFrame()
    a = agent.copy()
    a["is_posting"] = _as_bool(a["is_posting"])
    _numeric(a, ["tick"])
    posts = a[
        a["is_posting"]
        & a["post_content"].fillna("").astype(str).str.strip().ne("")
    ][["exp_id", "tick", "agent_id", "post_content"]].copy()
    e = edges.rename(
        columns={"source_agent_id": "agent_id", "target_agent_id": "recipient_agent_id"}
    ).copy()
    posts["agent_id"] = posts["agent_id"].astype(str)
    e["agent_id"] = e["agent_id"].astype(str)
    out = posts.merge(e[["agent_id", "recipient_agent_id"]], on="agent_id", how="inner")
    out = out.rename(columns={"agent_id": "sender_agent_id"})
    out["delivery_semantics"] = (
        "post-decision broadcast; recipient appraises next Tick only if retained by inbox cap"
    )
    return out


def _llm_audit(run_dir: Path, summary: dict) -> pd.DataFrame:
    rows = []
    for meta in summary.get("condition_meta") or []:
        exp_id = str(meta.get("exp_id", ""))
        path = run_dir / "conditions" / exp_id / "llm_audit.jsonl"
        audited = parse_fail = schema_fail = errors = 0
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                audited += 1
                row = json.loads(line)
                if row.get("response_parse_ok") is False:
                    parse_fail += 1
                if row.get("semantic_schema_ok") is False:
                    schema_fail += 1
                if str(row.get("error_type", "") or "").strip():
                    errors += 1
        rows.append({
            "exp_id": exp_id,
            "logical_llm_calls": meta.get("logical_llm_calls", 0),
            "provider_calls": meta.get("provider_calls", 0),
            "replay_hits": meta.get("replay_hits", 0),
            "replay_misses": meta.get("replay_misses", 0),
            "audit_rows": audited,
            "parse_failures": parse_fail,
            "schema_failures": schema_fail,
            "provider_errors": errors,
        })
    return pd.DataFrame(rows)


def _validation(data: dict[str, object], run_dir: Path) -> tuple[pd.DataFrame, dict]:
    summary = data["summary"]
    agent = data["agent"].copy()
    thoughts = data["thoughts"].copy()
    cog = data["cognitive"].copy()
    demand = data["demand"].copy()
    nodes = data["network_nodes"].copy()
    edges = data["network_edges"].copy()
    _numeric(agent, ["tick"])
    _numeric(cog, ["tick"])

    checks = []
    def add(cid, domain, status, observed, criterion, interpretation):
        checks.append({
            "check_id": cid,
            "domain": domain,
            "status": status,
            "observed": observed,
            "criterion": criterion,
            "interpretation": interpretation,
        })

    conditions = sorted(agent["exp_id"].astype(str).unique())
    n_agents = agent["agent_id"].astype(str).nunique()
    ticks = int(agent["tick"].max())
    expected = len(conditions) * n_agents * ticks
    add("V01_AGENT_TICK_COMPLETENESS", "implementation", "PASS" if len(agent) == expected else "FAIL", f"{len(agent)}/{expected}", "exact condition×Agent×Tick grid", "Checks missing Agent-Tick records.")
    dup = int(agent.duplicated(["exp_id", "tick", "agent_id"]).sum())
    add("V02_AGENT_TICK_UNIQUENESS", "implementation", "PASS" if dup == 0 else "FAIL", dup, "0 duplicates", "One state row per Agent and Tick.")

    fallback = int(_as_bool(thoughts["semantic_fallback_used"]).sum())
    add("V03_SEMANTIC_FALLBACK", "LLM pipeline", "PASS" if fallback == 0 else "WARN", fallback, "0 preferred", "Fallbacks weaken semantic evidence and require inspection.")
    llm = _llm_audit(run_dir, summary)
    replay_miss = int(pd.to_numeric(llm["replay_misses"], errors="coerce").fillna(0).sum()) if len(llm) else 0
    errors = int(pd.to_numeric(llm["provider_errors"], errors="coerce").fillna(0).sum()) if len(llm) else 0
    parse_schema = int((pd.to_numeric(llm["parse_failures"], errors="coerce").fillna(0) + pd.to_numeric(llm["schema_failures"], errors="coerce").fillna(0)).sum()) if len(llm) else 0
    add("V04_COMMON_HISTORY_REPLAY", "experimental control", "PASS" if replay_miss == 0 else "FAIL", replay_miss, "0 replay misses", "Common-history replay must remain complete.")
    add("V05_LLM_AUDIT_ERRORS", "LLM pipeline", "PASS" if errors + parse_schema == 0 else "WARN", f"provider={errors}; parse/schema={parse_schema}", "0 preferred", "Checks realized LLM execution integrity.")

    ranges = {
        "semantic_valence": (-1.0, 1.0),
        "semantic_arousal": (0.0, 1.0),
        "semantic_credibility": (0.0, 1.0),
        "semantic_evidence_strength": (0.0, 1.0),
        "semantic_topic_relevance": (0.0, 1.0),
        "semantic_perceived_empathy": (0.0, 1.0),
    }
    violations = 0
    for field, (lo, hi) in ranges.items():
        values = pd.to_numeric(cog[field], errors="coerce").dropna()
        violations += int(((values < lo) | (values > hi)).sum())
    add("V06_SEMANTIC_RANGES", "construct implementation", "PASS" if violations == 0 else "FAIL", violations, "0 out-of-range values", "Semantic schema bounds.")

    social_count = pd.to_numeric(cog["semantic_social_observation_count"], errors="coerce").fillna(0)
    peer = pd.to_numeric(cog["semantic_perceived_peer_approval"], errors="coerce")
    sn_applied = _as_bool(cog["subjective_norm_peer_update_applied"])
    sn_bad = int(((social_count == 0) & peer.notna()).sum())
    sn_bad += int(((social_count > 0) & peer.isna()).sum())
    sn_bad += int(((social_count == 0) & sn_applied).sum())
    sn_bad += int(((social_count > 0) & ~sn_applied).sum())
    add("V07_SN_PEER_ONLY_BOUNDARY", "construct validity", "PASS" if sn_bad == 0 else "FAIL", sn_bad, "0 boundary violations", "Enterprise/news information must not directly update peer-only SN.")

    _, paired = _semantic_tables(thoughts)
    pmap = paired.set_index("metric") if len(paired) else pd.DataFrame()
    evidence = float(pmap.loc["semantic_evidence_strength", "mean_rational_minus_empathy"]) if len(paired) else np.nan
    empathy = float(pmap.loc["semantic_perceived_empathy", "mean_rational_minus_empathy"]) if len(paired) else np.nan
    add("V08_RATIONAL_EVIDENCE_MANIPULATION", "construct manipulation", "SUPPORTED" if evidence > 0 else "NOT_SUPPORTED", evidence, "Rational−Empathy > 0", "Descriptive manipulation direction, not population inference.")
    add("V09_EMPATHY_MANIPULATION", "construct manipulation", "SUPPORTED" if empathy < 0 else "NOT_SUPPORTED", empathy, "Rational−Empathy < 0", "Descriptive manipulation direction, not population inference.")

    control = agent[agent["exp_id"].astype(str) == CONTROL]
    contaminated = int(_as_bool(control["clarification_received"]).sum()) if len(control) else -1
    add("V10_CONTROL_CONTAMINATION", "experimental control", "PASS" if contaminated == 0 else "FAIL", contaminated, "0 control clarification observations", "Control must remain treatment-free.")

    pre_fields = [f for f in ["trust_final", "attitude_att", "subjective_norm_after", "pbc", "crisis_memory", "repair_memory"] if f in cog.columns]
    _numeric(cog, pre_fields + ["clarification_tick_config"])
    control_cog = cog[cog["exp_id"].astype(str) == CONTROL].set_index(["tick", "agent_id"])
    pre_bad = 0
    max_diff = 0.0
    for exp_id in [x for x in conditions if x != CONTROL]:
        tr = cog[cog["exp_id"].astype(str) == exp_id].copy()
        clr = tr["clarification_tick_config"].dropna()
        if clr.empty:
            continue
        t0 = int(clr.iloc[0])
        tr = tr[tr["tick"] < t0].set_index(["tick", "agent_id"])
        idx = tr.index.intersection(control_cog.index)
        for field in pre_fields:
            d = (tr.loc[idx, field] - control_cog.loc[idx, field]).abs().dropna()
            if len(d):
                pre_bad += int((d > 1e-12).sum())
                max_diff = max(max_diff, float(d.max()))
    add("V11_PRETREATMENT_COMMON_HISTORY", "experimental control", "PASS" if pre_bad == 0 else "FAIL", f"mismatches={pre_bad}; max_abs_diff={max_diff:.3g}", "exact equality before treatment onset", "Realized state-level check of blocked common history.")

    if not demand.empty:
        d = demand.copy()
        _numeric(d, ["tick", "choice_probability", "loyalty_after", "next_opportunity_tick"])
        choice_bad = int(((d["choice_probability"] < 0) | (d["choice_probability"] > 1)).sum())
        loyalty_bad = int(((d["loyalty_after"] < -1) | (d["loyalty_after"] > 1)).sum())
        time_bad = int((d["next_opportunity_tick"] <= d["tick"]).sum())
        add("V12_DEMAND_PROBABILITY_BOUNDS", "demand mechanism", "PASS" if choice_bad == 0 else "FAIL", choice_bad, "choice probability in [0,1]", "Hard probability invariant.")
        add("V13_LOYALTY_BOUNDS", "demand mechanism", "PASS" if loyalty_bad == 0 else "FAIL", loyalty_bad, "loyalty in [-1,1]", "Bounded EWMA invariant.")
        add("V14_RENEWAL_FORWARD_TIME", "demand mechanism", "PASS" if time_bad == 0 else "FAIL", time_bad, "next opportunity > current Tick", "Renewal process moves forward.")

    if not nodes.empty and not edges.empty:
        graph = nx.DiGraph()
        graph.add_nodes_from(nodes["agent_id"].astype(str))
        graph.add_edges_from(zip(edges["source_agent_id"].astype(str), edges["target_agent_id"].astype(str)))
        observed = dict(zip(nodes["agent_id"].astype(str), pd.to_numeric(nodes["out_degree"], errors="coerce").fillna(-1).astype(int)))
        mismatch = sum(graph.out_degree(n) != observed.get(n, -1) for n in graph.nodes())
        add("V15_NETWORK_EXPORT_CONSISTENCY", "network implementation", "PASS" if mismatch == 0 else "FAIL", mismatch, "exported edges reproduce node degrees", "Topology evidence is internally consistent.")
    else:
        add("V15_NETWORK_EXPORT_CONSISTENCY", "network implementation", "WARN", "network files absent", "v3.3.1 topology files present", "Older runs need re-run for network evidence/animation.")

    checks = pd.DataFrame(checks)
    failures = int((checks["status"] == "FAIL").sum())
    warnings = int((checks["status"] == "WARN").sum())
    payload = {
        "schema_version": "task005_fmcg_v331_validation1.0",
        "overall_status": "PASS" if failures == 0 else "FAIL",
        "hard_failures": failures,
        "warnings": warnings,
        "supported_manipulation_checks": int((checks["status"] == "SUPPORTED").sum()),
        "scope": "internal implementation/construct/process evidence only",
        "external_validity_proven": False,
        "formal_inference_performed": False,
        "note": "Passing checks supports internal model evidence, not real-world population validity.",
    }
    return checks, payload


def _figures(data: dict[str, object], out_dir: Path) -> list[str]:
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    cog = data["cognitive"].copy()
    thoughts = data["thoughts"].copy()
    agent = data["agent"].copy()
    demand = data["demand"].copy()
    nodes = data["network_nodes"].copy()
    edges = data["network_edges"].copy()

    _numeric(cog, ["tick", "crisis_memory", "repair_memory"])
    strategy = cog[cog["exp_id"].astype(str) != CONTROL]
    memory = strategy.groupby("tick")[["crisis_memory", "repair_memory"]].mean()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(memory.index, memory["crisis_memory"], marker="o", markersize=3, label="Crisis memory")
    ax.plot(memory.index, memory["repair_memory"], marker="o", markersize=3, label="Repair memory")
    ax.axvline(5, linestyle="--", linewidth=1)
    ax.set(xlabel="Tick", ylabel="Mean memory stock", title="Mean crisis and repair memory across eight strategies")
    ax.legend(); path = fig_dir / "01_memory_stocks.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    thoughts["clarification_received"] = _as_bool(thoughts["clarification_received"])
    clar = thoughts[thoughts["clarification_received"]].copy()
    metrics = ["semantic_credibility", "semantic_evidence_strength", "semantic_perceived_empathy"]
    _numeric(clar, metrics)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    for ax, metric in zip(axes, metrics):
        vals = [
            clar.loc[clar["content_factor"].astype(str) == label, metric].dropna().to_numpy()
            for label in ("rational-evidence", "emotional-empathy")
        ]
        ax.boxplot(vals, tick_labels=["Rational", "Empathy"], showfliers=True)
        ax.set_ylim(0, 1.05); ax.set_title(metric.replace("semantic_", "").replace("_", " ").title())
    fig.suptitle("Realized LLM semantic manipulation at actual clarification exposure")
    path = fig_dir / "02_semantic_manipulation.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    identity = agent[["exp_id", "agent_id", "cluster_type"]].drop_duplicates()
    cc = cog.merge(identity, on=["exp_id", "agent_id"], how="left")
    _numeric(cc, ["tick", "trust_final"])
    t30 = cc[cc["tick"] == 30].groupby(["exp_id", "cluster_type"])["trust_final"].mean().unstack("cluster_type")
    if CONTROL in t30.index:
        delta = t30.drop(index=CONTROL).subtract(t30.loc[CONTROL], axis=1)
        fig, ax = plt.subplots(figsize=(11, 5)); vmax = max(abs(np.nanmin(delta.values)), abs(np.nanmax(delta.values)), 1e-9)
        im = ax.imshow(delta.values, aspect="auto", cmap="coolwarm", vmin=-vmax, vmax=vmax)
        ax.set_yticks(range(len(delta.index))); ax.set_yticklabels(delta.index, fontsize=8)
        ax.set_xticks(range(len(delta.columns))); ax.set_xticklabels(delta.columns, rotation=25, ha="right")
        ax.set_title("Segment-level T30 Trust Δ vs contemporaneous control"); fig.colorbar(im, ax=ax, label="Δ Trust")
        path = fig_dir / "03_segment_trust_delta_t30.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    a = agent.copy(); _numeric(a, ["tick"]); a["is_posting"] = _as_bool(a["is_posting"])
    posts = a.groupby(["exp_id", "tick"])["is_posting"].sum().reset_index()
    fig, ax = plt.subplots(figsize=(11, 5))
    for exp_id in _condition_order(posts["exp_id"].astype(str).unique()):
        p = posts[posts["exp_id"].astype(str) == exp_id]; ax.plot(p["tick"], p["is_posting"], linewidth=1, label=exp_id)
    ax.set(xlabel="Tick", ylabel="Posting Agents", title="UGC posting activity by condition"); ax.legend(fontsize=6, ncol=2)
    path = fig_dir / "04_ugc_activity.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    _numeric(cog, ["tick", "semantic_social_observation_count"])
    social = cog.assign(has_social=cog["semantic_social_observation_count"] > 0).groupby(["exp_id", "tick"])["has_social"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(11, 5))
    for exp_id in _condition_order(social["exp_id"].astype(str).unique()):
        p = social[social["exp_id"].astype(str) == exp_id]; ax.plot(p["tick"], p["has_social"], linewidth=1, label=exp_id)
    ax.set(xlabel="Tick", ylabel="Fraction of Agents observing peer content", title="Peer-social exposure over time"); ax.legend(fontsize=6, ncol=2)
    path = fig_dir / "05_peer_social_exposure.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    if not nodes.empty and not edges.empty:
        graph = nx.DiGraph(); graph.add_nodes_from(nodes["agent_id"].astype(str)); graph.add_edges_from(zip(edges["source_agent_id"].astype(str), edges["target_agent_id"].astype(str)))
        pos = nx.spring_layout(graph.to_undirected(), seed=20260815, k=0.7); degree = dict(graph.out_degree())
        fig, ax = plt.subplots(figsize=(9, 8)); nx.draw_networkx_edges(graph, pos, ax=ax, alpha=0.3, arrows=True, arrowsize=10, edge_color="#999999")
        nx.draw_networkx_nodes(graph, pos, ax=ax, node_size=[350 + 100 * degree[n] for n in graph.nodes()], node_color=[degree[n] for n in graph.nodes()], cmap="viridis", edgecolors="#333333")
        nx.draw_networkx_labels(graph, pos, labels={n: n.replace("Consumer_", "C") for n in graph.nodes()}, font_size=7, ax=ax)
        ax.set_title("Audited directed BA baseline topology\nNode size/color = out-degree; topology is static during a run"); ax.axis("off")
        path = fig_dir / "06_network_topology.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    support = _support_effects(demand)
    if len(support):
        fig, ax = plt.subplots(figsize=(11, 5)); ax.scatter(support["support_lift_expected_choice"], np.arange(len(support))); ax.axvline(0, linewidth=0.8)
        ax.set_yticks(np.arange(len(support))); ax.set_yticklabels(support["exp_id"], fontsize=8); ax.set_xlabel("Expected repeat-choice lift: support present − absent"); ax.set_title("Conversion-support effect by communication condition")
        path = fig_dir / "07_conversion_support_lift.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))
    return outputs


def build_thesis_outputs(
    run_dir: Path,
    *,
    animate_condition: str | None = None,
    animation_fps: int = 3,
) -> dict:
    """Generate thesis tables, internal-validity evidence, figures and optional GIF."""

    run_dir = Path(run_dir).resolve()
    data = _load(run_dir)
    out_dir = run_dir / "thesis_outputs"
    table_dir = out_dir / "tables"
    validation_dir = out_dir / "validation"
    table_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)

    summary = data["summary"]
    generated = []
    generated.append(_write_csv(_design_table(summary, data["agent"]), table_dir / "01_run_design.csv"))
    generated.append(_write_csv(_condition_outcomes(data), table_dir / "02_condition_outcomes.csv"))
    if not data["estimands"].empty:
        generated.append(_write_csv(data["estimands"], table_dir / "03_single_block_estimands_descriptive.csv"))
    sem_mean, sem_pair = _semantic_tables(data["thoughts"])
    generated.append(_write_csv(sem_mean, table_dir / "04_semantic_manipulation_means.csv"))
    generated.append(_write_csv(sem_pair, table_dir / "05_semantic_manipulation_paired.csv"))
    segment, individual = _heterogeneity_tables(data["cognitive"], data["agent"])
    generated.append(_write_csv(segment, table_dir / "06_segment_heterogeneity.csv"))
    generated.append(_write_csv(individual, table_dir / "07_agent_heterogeneity.csv"))
    generated.append(_write_csv(_mechanism_tick(data["cognitive"]), table_dir / "08_mechanism_tick_summary.csv"))
    support = _support_effects(data["demand"])
    if len(support): generated.append(_write_csv(support, table_dir / "09_conversion_support_effects.csv"))
    dseg = _demand_segment(data["demand"], data["agent"])
    if len(dseg): generated.append(_write_csv(dseg, table_dir / "10_repeat_choice_by_segment.csv"))
    network = _network_metrics(data["network_nodes"], data["network_edges"])
    if len(network): generated.append(_write_csv(network, table_dir / "11_network_metrics.csv"))
    targeting = _targeting(data["network_nodes"], data["targets"], data["exposure"])
    if len(targeting): generated.append(_write_csv(targeting, table_dir / "12_targeting_audit.csv"))
    broadcasts = _social_broadcasts(data["agent"], data["network_edges"])
    if len(broadcasts): generated.append(_write_csv(broadcasts, table_dir / "13_social_broadcast_deliveries.csv"))
    llm = _llm_audit(run_dir, summary)
    generated.append(_write_csv(llm, table_dir / "14_llm_audit_summary.csv"))

    checks, validation = _validation(data, run_dir)
    generated.append(_write_csv(checks, validation_dir / "validation_evidence.csv"))
    generated.append(_write_json(validation, validation_dir / "validation_summary.json"))
    report = [
        "# TASK_005 v3.3.1 Internal Validation Evidence", "",
        f"Run: `{summary.get('run_id', '')}`", "",
        f"Overall status: **{validation['overall_status']}**", "",
        "> These checks support implementation, construct manipulation and process consistency. They do not prove external validity or real-world population effect sizes.", "",
        "| Check | Domain | Status | Observed | Criterion |", "|---|---|---:|---|---|",
    ]
    for row in checks.itertuples(index=False):
        report.append(f"| {row.check_id} | {row.domain} | {row.status} | {str(row.observed).replace('|','/')} | {str(row.criterion).replace('|','/')} |")
    report += ["", "PASS denotes a hard implementation/process invariant. SUPPORTED denotes a descriptive manipulation direction in this engineering block; neither is a population-level statistical claim.", ""]
    report_path = validation_dir / "VALIDATION_REPORT.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    generated.append(str(report_path))

    figures = _figures(data, out_dir); generated.extend(figures)
    animation = None
    if animate_condition:
        animation = animate_network_state(run_dir, condition=animate_condition, fps=animation_fps)
        generated.append(animation)

    evidence_names = [
        "run_summary.json", "agent_records.csv", "agent_thoughts.csv",
        "cognitive_records.csv", "demand_opportunities.csv", "choice_curves.csv",
        "network_nodes.csv", "network_edges.csv", "target_nodes.csv",
    ]
    evidence_hashes = [
        {"path": name, "sha256": _sha256(run_dir / name), "bytes": (run_dir / name).stat().st_size}
        for name in evidence_names if (run_dir / name).exists()
    ]
    generated_hashes = []
    for raw in generated:
        path = Path(raw)
        if path.exists():
            generated_hashes.append({
                "path": str(path.relative_to(run_dir)).replace("\\", "/"),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            })
    manifest = {
        "schema_version": OUTPUT_SCHEMA,
        "run_id": summary.get("run_id", ""),
        "code_release": summary.get("code_release", ""),
        "scope": "thesis-oriented descriptive post-processing; no model-state mutation",
        "formal_inference_performed": False,
        "external_validity_claimed": False,
        "validation_overall_status": validation["overall_status"],
        "source_evidence_hashes": evidence_hashes,
        "generated_outputs": generated_hashes,
        "network_animation": animation,
        "network_animation_semantics": "fixed topology with evolving node states and information flow; not topology evolution" if animation else "not requested",
    }
    manifest_path = out_dir / "thesis_output_manifest.json"
    _write_json(manifest, manifest_path)
    return {
        "status": "PASS" if validation["overall_status"] == "PASS" else "FAIL",
        "run_id": summary.get("run_id", ""),
        "output_dir": str(out_dir),
        "validation": validation,
        "tables": [x for x in generated if "/tables/" in x.replace("\\", "/")],
        "figures": figures,
        "animation": animation,
        "manifest": str(manifest_path),
    }
