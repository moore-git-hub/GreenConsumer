"""Finite-horizon thesis outputs for TASK_005 v3.3.1.

This module supersedes the legacy T30-specific post-processing path for new
v3.3.1 runs while reusing validated helper functions that are horizon-neutral.
It is strictly post-processing: no simulation state, treatment, prompt, seed,
network, Trust parameter, or demand parameter is modified.

The realized endpoint is read from run provenance and cross-checked against the
maximum observed Tick.  This prevents a 35- or 40-Tick run from being silently
summarized with legacy T30 filters.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from .config import DEFAULT_CRISIS_TICK, DEFAULT_TOTAL_TICKS, HORIZON_ROBUSTNESS_TICKS, horizon_role
from .network_animation import animate_network_state
from .thesis_outputs import (
    CONTROL,
    _as_bool,
    _condition_order,
    _design_table,
    _llm_audit,
    _load,
    _mechanism_tick,
    _network_metrics,
    _numeric,
    _semantic_tables,
    _sha256,
    _social_broadcasts,
    _targeting,
    _validation,
    _write_csv,
    _write_json,
)

OUTPUT_SCHEMA = "task005_fmcg_v331_thesis_outputs1.1"


def _resolve_end_tick(data: dict[str, object]) -> int:
    summary = data["summary"]
    agent = data["agent"]
    observed = int(pd.to_numeric(agent["tick"], errors="coerce").max())
    declared = summary.get("total_ticks")
    if declared not in (None, ""):
        declared = int(declared)
        if declared != observed:
            raise ValueError(
                f"run_summary total_ticks={declared} but Agent records end at T{observed}"
            )
        return declared
    return observed


def _design_table_horizon(summary: dict, agent: pd.DataFrame, end_tick: int) -> pd.DataFrame:
    base = _design_table(summary, agent)
    td = summary.get("time_design") or {}
    base.insert(len(base.columns), "endpoint_tick", end_tick)
    base.insert(
        len(base.columns),
        "post_crisis_observation_days",
        int(td.get("post_crisis_observation_days", end_tick - DEFAULT_CRISIS_TICK)),
    )
    base.insert(len(base.columns), "tick_unit", td.get("tick_unit", "day"))
    base.insert(len(base.columns), "horizon_role", td.get("horizon_role", horizon_role(end_tick)))
    base.insert(
        len(base.columns),
        "pre_specified_horizon_grid",
        ";".join(str(x) for x in HORIZON_ROBUSTNESS_TICKS),
    )
    return base


def _condition_outcomes_horizon(data: dict[str, object], end_tick: int) -> pd.DataFrame:
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
        post = c[c["tick"].between(6, end_tick)]
        endpoint = c[c["tick"] == end_tick]
        t30 = c[c["tick"] == 30]
        row = {
            "exp_id": exp_id,
            "content_factor": str(c["content_factor"].iloc[0]) if len(c) else "",
            "channel_factor": str(c["channel_factor"].iloc[0]) if len(c) else "",
            "timing_factor": str(c["timing_factor"].iloc[0]) if len(c) else "",
            "endpoint_tick": end_tick,
            "mean_trust_endpoint": endpoint["trust_final"].mean(),
            "mean_trust_t6_endpoint": post["trust_final"].mean(),
            "mean_purchase_intention_endpoint": endpoint["purchase_intention"].mean(),
            "mean_crisis_memory_endpoint": endpoint["crisis_memory"].mean(),
            "mean_repair_memory_endpoint": endpoint["repair_memory"].mean(),
            "mean_trust_t30_secondary": t30["trust_final"].mean() if len(t30) else np.nan,
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
            d = d[d["tick"].between(6, end_tick)]
            for support in ("absent", "present"):
                ds = d[d["conversion_support"].astype(str) == support]
                if len(ds):
                    row[f"expected_repeat_choice_{support}"] = ds["choice_probability"].mean()
                    row[f"mean_loyalty_{support}"] = ds["loyalty_after"].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def _heterogeneity_tables_horizon(
    cog: pd.DataFrame,
    agent: pd.DataFrame,
    end_tick: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    identity = agent[["exp_id", "agent_id", "cluster_type", "social_role"]].drop_duplicates()
    c = cog.merge(identity, on=["exp_id", "agent_id"], how="left")
    _numeric(c, ["tick", "trust_final", "purchase_intention", "subjective_norm_after"])
    post = c[c["tick"].between(6, end_tick)]
    segment = post.groupby(["exp_id", "cluster_type"], dropna=False).agg(
        mean_trust_t6_endpoint=("trust_final", "mean"),
        mean_purchase_intention_t6_endpoint=("purchase_intention", "mean"),
        mean_sn_t6_endpoint=("subjective_norm_after", "mean"),
        agent_tick_rows=("agent_id", "size"),
    ).reset_index()
    segment["endpoint_tick"] = end_tick

    t1 = c[c["tick"] == 1][["exp_id", "agent_id", "trust_final"]].rename(columns={"trust_final": "trust_t1"})
    t5 = c[c["tick"] == 5][["exp_id", "agent_id", "trust_final"]].rename(columns={"trust_final": "trust_t5"})
    te = c[c["tick"] == end_tick][["exp_id", "agent_id", "cluster_type", "social_role", "trust_final"]].rename(columns={"trust_final": "trust_endpoint"})
    individual = te.merge(t1, on=["exp_id", "agent_id"], how="left").merge(
        t5, on=["exp_id", "agent_id"], how="left"
    )
    individual["endpoint_tick"] = end_tick
    individual["delta_endpoint_vs_t5"] = individual["trust_endpoint"] - individual["trust_t5"]
    return segment, individual


def _support_effects_horizon(demand: pd.DataFrame, end_tick: int) -> pd.DataFrame:
    if demand.empty:
        return pd.DataFrame()
    d = demand.copy()
    _numeric(d, ["tick", "choice_probability", "loyalty_after"])
    d = d[d["tick"].between(6, end_tick)]
    agg = d.groupby(["exp_id", "conversion_support"]).agg(
        expected_choice_share=("choice_probability", "mean"),
        mean_loyalty=("loyalty_after", "mean"),
        opportunities=("buyer_id", "size"),
    ).reset_index()
    rows = []
    for exp_id, group in agg.groupby("exp_id"):
        row = {"exp_id": exp_id, "analysis_end_tick": end_tick}
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


def _demand_segment_horizon(demand: pd.DataFrame, agent: pd.DataFrame, end_tick: int) -> pd.DataFrame:
    if demand.empty:
        return pd.DataFrame()
    clusters = agent[["agent_id", "cluster_type"]].drop_duplicates("agent_id")
    d = demand.merge(clusters, on="agent_id", how="left")
    _numeric(d, ["tick", "choice_probability", "loyalty_after"])
    d["focal_brand_chosen"] = _as_bool(d["focal_brand_chosen"])
    d = d[d["tick"].between(6, end_tick)]
    out = d.groupby(["exp_id", "conversion_support", "cluster_type"], dropna=False).agg(
        opportunities=("buyer_id", "size"),
        expected_choice_share=("choice_probability", "mean"),
        realized_choice_share=("focal_brand_chosen", "mean"),
        mean_loyalty_after=("loyalty_after", "mean"),
    ).reset_index()
    out["analysis_end_tick"] = end_tick
    return out


def _time_checkpoint_table(cog: pd.DataFrame, end_tick: int) -> pd.DataFrame:
    c = cog.copy()
    _numeric(c, ["tick", "trust_final", "purchase_intention"])
    checkpoints = [x for x in HORIZON_ROBUSTNESS_TICKS if x <= end_tick]
    rows = []
    for checkpoint in checkpoints:
        cc = c[c["tick"] == checkpoint]
        control = cc[cc["exp_id"].astype(str) == CONTROL]
        control_trust = control["trust_final"].mean()
        for exp_id in _condition_order(cc["exp_id"].astype(str).unique()):
            e = cc[cc["exp_id"].astype(str) == exp_id]
            rows.append({
                "checkpoint_tick": checkpoint,
                "checkpoint_role": horizon_role(checkpoint),
                "exp_id": exp_id,
                "mean_trust": e["trust_final"].mean(),
                "trust_delta_vs_control": (
                    e["trust_final"].mean() - control_trust if exp_id != CONTROL else 0.0
                ),
                "mean_purchase_intention": e["purchase_intention"].mean(),
            })
    return pd.DataFrame(rows)


def _figures_horizon(data: dict[str, object], out_dir: Path, end_tick: int) -> list[str]:
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
    ax.set(xlabel="Tick", ylabel="Mean memory stock", title=f"Mean crisis and repair memory across eight strategies through T{end_tick}")
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
    te = cc[cc["tick"] == end_tick].groupby(["exp_id", "cluster_type"])["trust_final"].mean().unstack("cluster_type")
    if CONTROL in te.index:
        delta = te.drop(index=CONTROL).subtract(te.loc[CONTROL], axis=1)
        fig, ax = plt.subplots(figsize=(11, 5)); vmax = max(abs(np.nanmin(delta.values)), abs(np.nanmax(delta.values)), 1e-9)
        im = ax.imshow(delta.values, aspect="auto", cmap="coolwarm", vmin=-vmax, vmax=vmax)
        ax.set_yticks(range(len(delta.index))); ax.set_yticklabels(delta.index, fontsize=8)
        ax.set_xticks(range(len(delta.columns))); ax.set_xticklabels(delta.columns, rotation=25, ha="right")
        ax.set_title(f"Segment-level T{end_tick} Trust Δ vs contemporaneous control"); fig.colorbar(im, ax=ax, label="Δ Trust")
        path = fig_dir / f"03_segment_trust_delta_t{end_tick}.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    a = agent.copy(); _numeric(a, ["tick"]); a["is_posting"] = _as_bool(a["is_posting"])
    posts = a.groupby(["exp_id", "tick"])["is_posting"].sum().reset_index()
    fig, ax = plt.subplots(figsize=(11, 5))
    for exp_id in _condition_order(posts["exp_id"].astype(str).unique()):
        p = posts[posts["exp_id"].astype(str) == exp_id]; ax.plot(p["tick"], p["is_posting"], linewidth=1, label=exp_id)
    ax.set(xlabel="Tick", ylabel="Posting Agents", title=f"UGC posting activity by condition through T{end_tick}"); ax.legend(fontsize=6, ncol=2)
    path = fig_dir / "04_ugc_activity.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    _numeric(cog, ["tick", "semantic_social_observation_count"])
    social = cog.assign(has_social=cog["semantic_social_observation_count"] > 0).groupby(["exp_id", "tick"])["has_social"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(11, 5))
    for exp_id in _condition_order(social["exp_id"].astype(str).unique()):
        p = social[social["exp_id"].astype(str) == exp_id]; ax.plot(p["tick"], p["has_social"], linewidth=1, label=exp_id)
    ax.set(xlabel="Tick", ylabel="Fraction of Agents observing peer content", title=f"Peer-social exposure over time through T{end_tick}"); ax.legend(fontsize=6, ncol=2)
    path = fig_dir / "05_peer_social_exposure.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    if not nodes.empty and not edges.empty:
        graph = nx.DiGraph(); graph.add_nodes_from(nodes["agent_id"].astype(str)); graph.add_edges_from(zip(edges["source_agent_id"].astype(str), edges["target_agent_id"].astype(str)))
        pos = nx.spring_layout(graph.to_undirected(), seed=20260815, k=0.7); degree = dict(graph.out_degree())
        fig, ax = plt.subplots(figsize=(9, 8)); nx.draw_networkx_edges(graph, pos, ax=ax, alpha=0.3, arrows=True, arrowsize=10, edge_color="#999999")
        nx.draw_networkx_nodes(graph, pos, ax=ax, node_size=[350 + 100 * degree[n] for n in graph.nodes()], node_color=[degree[n] for n in graph.nodes()], cmap="viridis", edgecolors="#333333")
        nx.draw_networkx_labels(graph, pos, labels={n: n.replace("Consumer_", "C") for n in graph.nodes()}, font_size=7, ax=ax)
        ax.set_title("Audited directed BA baseline topology\nNode size/color = out-degree; topology is static during a run"); ax.axis("off")
        path = fig_dir / "06_network_topology.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    support = _support_effects_horizon(demand, end_tick)
    if len(support):
        fig, ax = plt.subplots(figsize=(11, 5)); ax.scatter(support["support_lift_expected_choice"], np.arange(len(support))); ax.axvline(0, linewidth=0.8)
        ax.set_yticks(np.arange(len(support))); ax.set_yticklabels(support["exp_id"], fontsize=8); ax.set_xlabel("Expected repeat-choice lift: support present − absent"); ax.set_title(f"Conversion-support effect by communication condition through T{end_tick}")
        path = fig_dir / "07_conversion_support_lift.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))

    checkpoints = _time_checkpoint_table(cog, end_tick)
    if len(checkpoints):
        strategies = checkpoints[checkpoints["exp_id"] != CONTROL].groupby(["checkpoint_tick", "exp_id"])["trust_delta_vs_control"].mean().reset_index()
        fig, ax = plt.subplots(figsize=(11, 5))
        for exp_id in _condition_order(strategies["exp_id"].astype(str).unique()):
            p = strategies[strategies["exp_id"].astype(str) == exp_id]
            ax.plot(p["checkpoint_tick"], p["trust_delta_vs_control"], marker="o", linewidth=1, label=exp_id)
        ax.axhline(0.0, linewidth=0.8); ax.set_xticks(sorted(strategies["checkpoint_tick"].unique()))
        ax.set(xlabel="Pre-specified horizon checkpoint", ylabel="Trust Δ vs control", title="Endpoint-sensitivity checkpoints available within this run")
        ax.legend(fontsize=6, ncol=2)
        path = fig_dir / "08_horizon_checkpoint_trust.png"; fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig); outputs.append(str(path))
    return outputs


def _append_time_validation(checks: pd.DataFrame, validation: dict, data: dict[str, object], end_tick: int) -> tuple[pd.DataFrame, dict]:
    summary = data["summary"]
    observed = int(pd.to_numeric(data["agent"]["tick"], errors="coerce").max())
    declared = int(summary.get("total_ticks", observed))
    row = {
        "check_id": "V16_TIME_HORIZON_PROVENANCE",
        "domain": "experiment design",
        "status": "PASS" if declared == observed == end_tick else "FAIL",
        "observed": f"declared={declared}; observed={observed}; resolved={end_tick}",
        "criterion": "run summary and realized max Tick must agree",
        "interpretation": "Prevents silent T30 analysis of T35/T40 runs.",
    }
    checks = pd.concat([checks, pd.DataFrame([row])], ignore_index=True)
    failures = int((checks["status"] == "FAIL").sum())
    warnings = int((checks["status"] == "WARN").sum())
    validation = dict(validation)
    validation.update({
        "schema_version": "task005_fmcg_v331_validation1.1",
        "overall_status": "PASS" if failures == 0 else "FAIL",
        "hard_failures": failures,
        "warnings": warnings,
        "resolved_end_tick": end_tick,
        "horizon_role": horizon_role(end_tick),
    })
    return checks, validation


def build_thesis_outputs(
    run_dir: Path,
    *,
    animate_condition: str | None = None,
    animation_fps: int = 3,
) -> dict:
    """Generate horizon-aware thesis tables, validity evidence, figures and optional GIF."""

    run_dir = Path(run_dir).resolve()
    data = _load(run_dir)
    end_tick = _resolve_end_tick(data)
    out_dir = run_dir / "thesis_outputs"
    table_dir = out_dir / "tables"
    validation_dir = out_dir / "validation"
    table_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)

    summary = data["summary"]
    generated = []
    generated.append(_write_csv(_design_table_horizon(summary, data["agent"], end_tick), table_dir / "01_run_design.csv"))
    generated.append(_write_csv(_condition_outcomes_horizon(data, end_tick), table_dir / "02_condition_outcomes.csv"))
    if not data["estimands"].empty:
        generated.append(_write_csv(data["estimands"], table_dir / "03_single_block_estimands_descriptive.csv"))
    sem_mean, sem_pair = _semantic_tables(data["thoughts"])
    generated.append(_write_csv(sem_mean, table_dir / "04_semantic_manipulation_means.csv"))
    generated.append(_write_csv(sem_pair, table_dir / "05_semantic_manipulation_paired.csv"))
    segment, individual = _heterogeneity_tables_horizon(data["cognitive"], data["agent"], end_tick)
    generated.append(_write_csv(segment, table_dir / "06_segment_heterogeneity.csv"))
    generated.append(_write_csv(individual, table_dir / "07_agent_heterogeneity.csv"))
    generated.append(_write_csv(_mechanism_tick(data["cognitive"]), table_dir / "08_mechanism_tick_summary.csv"))
    support = _support_effects_horizon(data["demand"], end_tick)
    if len(support): generated.append(_write_csv(support, table_dir / "09_conversion_support_effects.csv"))
    dseg = _demand_segment_horizon(data["demand"], data["agent"], end_tick)
    if len(dseg): generated.append(_write_csv(dseg, table_dir / "10_repeat_choice_by_segment.csv"))
    network = _network_metrics(data["network_nodes"], data["network_edges"])
    if len(network): generated.append(_write_csv(network, table_dir / "11_network_metrics.csv"))
    targeting = _targeting(data["network_nodes"], data["targets"], data["exposure"])
    if len(targeting): generated.append(_write_csv(targeting, table_dir / "12_targeting_audit.csv"))
    broadcasts = _social_broadcasts(data["agent"], data["network_edges"])
    if len(broadcasts): generated.append(_write_csv(broadcasts, table_dir / "13_social_broadcast_deliveries.csv"))
    llm = _llm_audit(run_dir, summary)
    generated.append(_write_csv(llm, table_dir / "14_llm_audit_summary.csv"))
    checkpoints = _time_checkpoint_table(data["cognitive"], end_tick)
    generated.append(_write_csv(checkpoints, table_dir / "15_time_horizon_checkpoints.csv"))

    checks, validation = _validation(data, run_dir)
    checks, validation = _append_time_validation(checks, validation, data, end_tick)
    generated.append(_write_csv(checks, validation_dir / "validation_evidence.csv"))
    generated.append(_write_json(validation, validation_dir / "validation_summary.json"))
    report = [
        "# TASK_005 v3.3.1 Internal Validation Evidence", "",
        f"Run: `{summary.get('run_id', '')}`", "",
        f"Resolved finite horizon: **T{end_tick}** ({horizon_role(end_tick)})", "",
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

    figures = _figures_horizon(data, out_dir, end_tick); generated.extend(figures)
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
        "resolved_end_tick": end_tick,
        "horizon_role": horizon_role(end_tick),
        "baseline_end_tick": DEFAULT_TOTAL_TICKS,
        "pre_specified_horizon_grid": list(HORIZON_ROBUSTNESS_TICKS),
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
        "resolved_end_tick": end_tick,
        "horizon_role": horizon_role(end_tick),
        "output_dir": str(out_dir),
        "validation": validation,
        "tables": [x for x in generated if "/tables/" in x.replace("\\", "/")],
        "figures": figures,
        "animation": animation,
        "manifest": str(manifest_path),
    }
