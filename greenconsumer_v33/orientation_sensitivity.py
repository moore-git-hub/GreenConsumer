"""Equal-degree edge-orientation robustness for TASK_005 v3.3.1.

The undirected BA/WS/community substrates and their five pre-specified network
seeds are held fixed. Only the direction assigned to equal-degree edges changes:
legacy first endpoint, reversed legacy, or deterministic hash-balanced.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from clarification_diffusion_v33 import DEFAULT_CLARIFICATION_PARAMETERS
from greenconsumer_v32.config import (
    DEFAULT_DEMAND_SEED,
    DEFAULT_LLM_SEED,
    DEFAULT_SIMULATION_SEED,
    PROJECT_ROOT,
)
from mechanism_v33 import DEFAULT_TRUST_PARAMETERS

from .analysis import analyze_run
from .config import RunSettings
from .network_variants import (
    BASELINE_NETWORK_HASH,
    NetworkVariantV331Spec,
    TIE_RULES,
    TOPOLOGIES,
)
from .topology_sensitivity import NETWORK_SEEDS
from . import runner as runner_module

SCHEMA = "task005_fmcg_v331_orientation_sensitivity1.0"
CONTROL = "NoClarification-Control"
LEGACY = "legacy_first_endpoint"


def profile_id(topology: str, network_seed: int, tie_rule: str) -> str:
    token = {
        "legacy_first_endpoint": "legacy",
        "reverse_first_endpoint": "reverse",
        "hash_balanced": "hash",
    }[tie_rule]
    return f"{topology}_nseed{int(network_seed)}_{token}"


def profile_table() -> pd.DataFrame:
    rows = []
    for topology in TOPOLOGIES:
        for seed in NETWORK_SEEDS:
            for tie_rule in TIE_RULES:
                rows.append({
                    "profile_id": profile_id(topology, seed, tie_rule),
                    "topology": topology,
                    "network_seed": int(seed),
                    "tie_rule": tie_rule,
                    "profile_role": (
                        "frozen-baseline-orientation"
                        if topology == "ba" and seed == NETWORK_SEEDS[0] and tie_rule == LEGACY
                        else "pre-specified-orientation-robustness"
                    ),
                })
    return pd.DataFrame(rows)


async def _execute_with_spec(settings: RunSettings, spec: NetworkVariantV331Spec) -> dict:
    original = runner_module.run_scenario_v33

    async def scoped_run_scenario(config, *, override_router, trust_parameters=DEFAULT_TRUST_PARAMETERS):
        return await original(
            config,
            override_router=override_router,
            trust_parameters=trust_parameters,
            clarification_parameters=DEFAULT_CLARIFICATION_PARAMETERS,
            network_spec=spec,
        )

    runner_module.run_scenario_v33 = scoped_run_scenario
    try:
        return await runner_module.execute(settings, trust_parameters=DEFAULT_TRUST_PARAMETERS)
    finally:
        runner_module.run_scenario_v33 = original


def _read_summary(run_dir: Path) -> dict:
    return json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))


def _graph(run_dir: Path) -> nx.DiGraph:
    nodes = pd.read_csv(run_dir / "network_nodes.csv")
    edges = pd.read_csv(run_dir / "network_edges.csv")
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes["agent_id"].astype(str))
    graph.add_edges_from(zip(edges["source_agent_id"].astype(str), edges["target_agent_id"].astype(str)))
    return graph


def _pair(u: str, v: str) -> tuple[str, str]:
    return tuple(sorted((str(u), str(v))))


def _undirected_signature(graph: nx.DiGraph) -> tuple:
    nodes = tuple(sorted(str(n) for n in graph.nodes()))
    edges = tuple(sorted(_pair(u, v) for u, v in graph.edges()))
    return nodes, edges


def _undirected_hash(graph: nx.DiGraph) -> str:
    nodes, edges = _undirected_signature(graph)
    payload = json.dumps({"nodes": nodes, "edges": edges}, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _orientation_map(graph: nx.DiGraph) -> dict[tuple[str, str], tuple[str, str]]:
    return {_pair(u, v): (str(u), str(v)) for u, v in graph.edges()}


def _read_estimands(run_dir: Path, spec) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "single_block_estimands.csv")
    df.insert(0, "profile_id", spec.profile_id)
    df.insert(1, "topology", spec.topology)
    df.insert(2, "network_seed", int(spec.network_seed))
    df.insert(3, "tie_rule", spec.tie_rule)
    return df


def _read_reach(run_dir: Path, spec) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "clarification_reach_v33.csv")
    df.insert(0, "profile_id", spec.profile_id)
    df.insert(1, "topology", spec.topology)
    df.insert(2, "network_seed", int(spec.network_seed))
    df.insert(3, "tie_rule", spec.tie_rule)
    return df


def _orientation_metrics(run_dir: Path, spec) -> dict:
    graph = _graph(run_dir)
    undirected = graph.to_undirected()
    degree = dict(undirected.degree())
    out = np.array([graph.out_degree(n) for n in graph.nodes()], dtype=float)
    tie_edges = sum(1 for u, v in undirected.edges() if degree[u] == degree[v])
    return {
        "profile_id": spec.profile_id,
        "topology": spec.topology,
        "network_seed": int(spec.network_seed),
        "tie_rule": spec.tie_rule,
        "directed_network_hash": str((_read_summary(run_dir).get("network") or {}).get("network_hash", "")),
        "undirected_network_hash": _undirected_hash(graph),
        "num_nodes": graph.number_of_nodes(),
        "num_edges": graph.number_of_edges(),
        "equal_degree_tie_edges": tie_edges,
        "equal_degree_tie_edge_share": tie_edges / graph.number_of_edges() if graph.number_of_edges() else 0.0,
        "max_out_degree": int(out.max()) if len(out) else 0,
        "mean_out_degree": float(out.mean()) if len(out) else 0.0,
        "out_degree_cv": float(out.std(ddof=0) / out.mean()) if len(out) and out.mean() else 0.0,
    }


def _sorted_random_targets(run_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "target_nodes.csv")
    df = df[df["channel_factor"].astype(str) == "random"].copy()
    keep = [c for c in ("exp_id", "content_factor", "timing_factor", "agent_id") if c in df.columns]
    return df[keep].sort_values(keep).reset_index(drop=True)


def _public_nodes(run_dir: Path) -> tuple[str, ...]:
    df = pd.read_csv(run_dir / "clarification_exposure_plan.csv")
    mask = df["public_organic"].astype(str).str.lower().isin({"true", "1", "yes"})
    return tuple(sorted(df.loc[mask, "agent_id"].astype(str).unique()))


def _invariants(run_dirs: dict[str, Path], profiles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    baseline_id = profile_id("ba", NETWORK_SEEDS[0], LEGACY)
    baseline_hash = str((_read_summary(run_dirs[baseline_id]).get("network") or {}).get("network_hash", ""))
    rows.append({
        "check_id": "BASELINE_LEGACY_HASH_REPRODUCTION",
        "profile_id": baseline_id,
        "status": "PASS" if baseline_hash == BASELINE_NETWORK_HASH else "FAIL",
        "observed": baseline_hash,
        "criterion": BASELINE_NETWORK_HASH,
    })
    baseline_random = _sorted_random_targets(run_dirs[baseline_id])
    baseline_public = _public_nodes(run_dirs[baseline_id])

    for (topology, seed), group in profiles.groupby(["topology", "network_seed"]):
        group_ids = list(group["profile_id"].astype(str))
        graphs = {pid: _graph(run_dirs[pid]) for pid in group_ids}
        signatures = {_undirected_signature(graph) for graph in graphs.values()}
        rows.append({
            "check_id": "UNDIRECTED_SUBSTRATE_INVARIANCE",
            "profile_id": f"{topology}:nseed{int(seed)}",
            "status": "PASS" if len(signatures) == 1 else "FAIL",
            "observed": f"unique_signatures={len(signatures)}",
            "criterion": "same node set and unordered edge set across all tie rules",
        })

        legacy_pid = profile_id(str(topology), int(seed), LEGACY)
        legacy_graph = graphs[legacy_pid]
        degrees = dict(legacy_graph.to_undirected().degree())
        legacy_map = _orientation_map(legacy_graph)
        for pid, graph in graphs.items():
            amap = _orientation_map(graph)
            unequal_ok = all(
                amap[pair] == direction
                for pair, direction in legacy_map.items()
                if degrees[pair[0]] != degrees[pair[1]]
            )
            changed = [pair for pair in legacy_map if amap[pair] != legacy_map[pair]]
            changed_only_ties = all(degrees[a] == degrees[b] for a, b in changed)
            rows.extend([
                {
                    "check_id": "UNEQUAL_DEGREE_DIRECTION_INVARIANCE",
                    "profile_id": pid,
                    "status": "PASS" if unequal_ok else "FAIL",
                    "observed": "unchanged" if unequal_ok else "direction mismatch",
                    "criterion": "only equal-degree edges may change direction",
                },
                {
                    "check_id": "CHANGED_EDGES_ARE_TIES",
                    "profile_id": pid,
                    "status": "PASS" if changed_only_ties else "FAIL",
                    "observed": f"changed_edges={len(changed)}",
                    "criterion": "every changed orientation must have equal undirected endpoint degree",
                },
            ])

    for spec in profiles.itertuples(index=False):
        pid = str(spec.profile_id)
        run_dir = run_dirs[pid]
        random_targets = _sorted_random_targets(run_dir)
        try:
            pd.testing.assert_frame_equal(baseline_random, random_targets, check_dtype=False, check_exact=True)
            r_status = "PASS"
        except AssertionError:
            r_status = "FAIL"
        rows.append({
            "check_id": "RANDOM_TARGET_ALLOCATION_INVARIANCE",
            "profile_id": pid,
            "status": r_status,
            "observed": "exact equality" if r_status == "PASS" else "mismatch",
            "criterion": "Random K=3 targets must not depend on tie rule/topology seed",
        })
        public = _public_nodes(run_dir)
        rows.append({
            "check_id": "PUBLIC_ORGANIC_ALLOCATION_INVARIANCE",
            "profile_id": pid,
            "status": "PASS" if public == baseline_public else "FAIL",
            "observed": ";".join(public),
            "criterion": "public organic exposure IDs remain fixed",
        })
        clarification = _read_summary(run_dir).get("clarification_v33_parameters") or {}
        ok = abs(float(clarification.get("paid_edge_probability", -1)) - .55) <= 1e-12 and int(clarification.get("paid_delivery_lag", -1)) == 1
        rows.append({
            "check_id": "CLARIFICATION_BASELINE_PARAMETERS_FROZEN",
            "profile_id": pid,
            "status": "PASS" if ok else "FAIL",
            "observed": json.dumps(clarification, ensure_ascii=False, sort_keys=True),
            "criterion": "p=.55 and lag=1",
        })
    return pd.DataFrame(rows)


def _p4_stability(estimands: pd.DataFrame) -> pd.DataFrame:
    p4 = estimands[estimands["estimand_id"] == "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33"].copy()
    rows = []
    for (topology, seed), group in p4.groupby(["topology", "network_seed"]):
        values = pd.to_numeric(group["value"], errors="raise")
        signs = ["positive" if x > 0 else "negative" if x < 0 else "zero" for x in values]
        legacy = float(group[group["tie_rule"] == LEGACY]["value"].iloc[0])
        rows.append({
            "topology": topology,
            "network_seed": int(seed),
            "legacy_p4": legacy,
            "min_p4": values.min(),
            "max_p4": values.max(),
            "range_p4": values.max() - values.min(),
            "signs": ";".join(signs),
            "sign_stable_across_tie_rules": len(set(signs)) == 1,
        })
    return pd.DataFrame(rows)


def _plot_p4(estimands: pd.DataFrame, path: Path) -> str:
    df = estimands[estimands["estimand_id"] == "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33"].copy()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for topology in TOPOLOGIES:
        part = df[df["topology"] == topology]
        means = part.groupby("tie_rule")["value"].mean()
        xs = np.arange(len(TIE_RULES))
        ax.plot(xs, [means[r] for r in TIE_RULES], marker="o", label=topology)
    ax.axhline(0.0, linewidth=.8)
    ax.set_xticks(np.arange(len(TIE_RULES)))
    ax.set_xticklabels(["Legacy", "Reverse ties", "Hash-balanced ties"])
    ax.set_ylabel("Hub − Random eventual enterprise reach")
    ax.set_title("Equal-degree orientation robustness of channel reach\n5 pre-specified undirected realizations per topology; Fake LLM, T35")
    ax.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


async def run_orientation_sensitivity_suite(
    *,
    output_root: Path = PROJECT_ROOT / "results" / "v33_orientation_sensitivity",
    simulation_seed: int = DEFAULT_SIMULATION_SEED,
    llm_seed: int = DEFAULT_LLM_SEED,
    demand_seed: int = DEFAULT_DEMAND_SEED,
) -> dict:
    suite_id = dt.datetime.now().strftime("orientation_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)
    profiles = profile_table()
    profiles.to_csv(suite_dir / "orientation_profiles.csv", index=False, encoding="utf-8-sig")

    run_dirs = {}
    estimand_frames = []
    reach_frames = []
    metric_rows = []
    analysis_payloads = {}

    for spec_row in profiles.itertuples(index=False):
        spec = NetworkVariantV331Spec(
            topology=str(spec_row.topology),
            network_seed=int(spec_row.network_seed),
            tie_rule=str(spec_row.tie_rule),
        )
        settings = RunSettings(
            llm_mode="fake",
            condition="all",
            simulation_seed=simulation_seed,
            requested_llm_seed=llm_seed,
            demand_seed=demand_seed,
            output_dir=suite_dir / "profiles" / str(spec_row.profile_id),
            run_demand=True,
            support_mode="both",
            allow_real_llm=False,
            total_ticks=35,
        )
        payload = await _execute_with_spec(settings, spec)
        run_dir = Path(payload["output_dir"])
        run_dirs[str(spec_row.profile_id)] = run_dir
        analysis_payloads[str(spec_row.profile_id)] = analyze_run(run_dir)
        estimand_frames.append(_read_estimands(run_dir, spec_row))
        reach_frames.append(_read_reach(run_dir, spec_row))
        metric_rows.append(_orientation_metrics(run_dir, spec_row))

    estimands = pd.concat(estimand_frames, ignore_index=True)
    estimands.to_csv(suite_dir / "orientation_estimands.csv", index=False, encoding="utf-8-sig")
    reach = pd.concat(reach_frames, ignore_index=True)
    reach.to_csv(suite_dir / "orientation_reach.csv", index=False, encoding="utf-8-sig")
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(suite_dir / "orientation_network_metrics.csv", index=False, encoding="utf-8-sig")
    invariants = _invariants(run_dirs, profiles)
    invariants.to_csv(suite_dir / "orientation_invariants.csv", index=False, encoding="utf-8-sig")
    p4 = _p4_stability(estimands)
    p4.to_csv(suite_dir / "orientation_p4_stability.csv", index=False, encoding="utf-8-sig")

    figures = [_plot_p4(estimands, suite_dir / "figures" / "P4_ORIENTATION_ROBUSTNESS.png")]
    failures = int((invariants["status"] == "FAIL").sum())
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS" if failures == 0 else "FAIL",
        "scope": "Fake-LLM equal-degree edge-orientation engineering robustness; not formal inference",
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "orientation_selection_permitted": False,
        "topologies": list(TOPOLOGIES),
        "network_seeds": list(NETWORK_SEEDS),
        "tie_rules": list(TIE_RULES),
        "profiles_run": len(profiles),
        "baseline_horizon": 35,
        "baseline_paid_edge_probability": .55,
        "baseline_paid_delivery_lag": 1,
        "invariant_failures": failures,
        "p4_sign_unstable_undirected_networks": int((~p4["sign_stable_across_tie_rules"]).sum()),
        "simulation_seed": simulation_seed,
        "llm_seed": llm_seed,
        "demand_seed": demand_seed,
        "analysis": analysis_payloads,
        "run_dirs": {k: str(v) for k, v in run_dirs.items()},
        "figures": figures,
        "interpretation_rule": (
            "Treat tie-rule sensitivity as a boundary on directed-network claims; never select the rule producing the preferred Hub advantage"
        ),
    }
    (suite_dir / "orientation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary["output_dir"] = str(suite_dir)
    return summary


def run_sync(**kwargs) -> dict:
    return asyncio.run(run_orientation_sensitivity_suite(**kwargs))
