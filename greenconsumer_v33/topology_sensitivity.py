"""Fixed-N network-topology robustness for TASK_005 v3.3.1.

Pre-specified design:
- N=20 and the same Engineering Personas in every run;
- topology = BA / Watts-Strogatz / community stochastic block;
- five network-only seeds;
- behavior, LLM, demand, Trust and clarification parameters remain frozen.

This is deterministic Fake-LLM engineering robustness, not formal inference.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
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
    TOPOLOGIES,
)
from . import runner as runner_module

SCHEMA = "task005_fmcg_v331_topology_sensitivity1.0"
NETWORK_SEEDS = tuple(range(2026081501, 2026081506))
CONTROL = "NoClarification-Control"


def profile_id(topology: str, network_seed: int) -> str:
    return f"{topology}_nseed{int(network_seed)}"


def profile_table() -> pd.DataFrame:
    rows = []
    for topology in TOPOLOGIES:
        for network_seed in NETWORK_SEEDS:
            rows.append(
                {
                    "profile_id": profile_id(topology, network_seed),
                    "topology": topology,
                    "network_seed": int(network_seed),
                    "profile_role": (
                        "frozen-baseline-network"
                        if topology == "ba" and int(network_seed) == NETWORK_SEEDS[0]
                        else "pre-specified-topology-robustness"
                    ),
                }
            )
    return pd.DataFrame(rows)


async def _execute_with_network_spec(settings: RunSettings, spec: NetworkVariantV331Spec) -> dict:
    """Inject one version-scoped network variant without changing normal runner defaults."""

    original = runner_module.run_scenario_v33

    async def scoped_run_scenario(
        config,
        *,
        override_router,
        trust_parameters=DEFAULT_TRUST_PARAMETERS,
    ):
        return await original(
            config,
            override_router=override_router,
            trust_parameters=trust_parameters,
            clarification_parameters=DEFAULT_CLARIFICATION_PARAMETERS,
            network_spec=spec,
        )

    runner_module.run_scenario_v33 = scoped_run_scenario
    try:
        return await runner_module.execute(
            settings,
            trust_parameters=DEFAULT_TRUST_PARAMETERS,
        )
    finally:
        runner_module.run_scenario_v33 = original


def _read_summary(run_dir: Path) -> dict:
    return json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))


def _read_estimands(run_dir: Path, pid: str, topology: str, network_seed: int) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "single_block_estimands.csv")
    df.insert(0, "profile_id", pid)
    df.insert(1, "topology", topology)
    df.insert(2, "network_seed", int(network_seed))
    return df


def _network_metrics(run_dir: Path, pid: str, topology: str, network_seed: int) -> dict:
    nodes = pd.read_csv(run_dir / "network_nodes.csv")
    edges = pd.read_csv(run_dir / "network_edges.csv")
    meta = json.loads((run_dir / "network_meta.json").read_text(encoding="utf-8"))

    graph = nx.DiGraph()
    graph.add_nodes_from(nodes["agent_id"].astype(str))
    graph.add_edges_from(
        zip(edges["source_agent_id"].astype(str), edges["target_agent_id"].astype(str))
    )
    undirected = graph.to_undirected()
    degrees = np.array([degree for _, degree in undirected.degree()], dtype=float)
    mean_degree = float(degrees.mean()) if len(degrees) else 0.0
    degree_cv = float(degrees.std(ddof=0) / mean_degree) if mean_degree else 0.0
    connected = bool(nx.is_connected(undirected)) if undirected.number_of_nodes() else True
    communities = list(nx.algorithms.community.greedy_modularity_communities(undirected)) if undirected.number_of_edges() else []
    modularity = (
        float(nx.algorithms.community.modularity(undirected, communities))
        if communities and undirected.number_of_edges()
        else 0.0
    )
    params = meta.get("network_params") or {}

    return {
        "profile_id": pid,
        "topology": topology,
        "network_seed": int(network_seed),
        "network_type": meta.get("network_type", ""),
        "network_hash": meta.get("network_hash", ""),
        "num_nodes": int(graph.number_of_nodes()),
        "num_directed_edges": int(graph.number_of_edges()),
        "undirected_density": float(nx.density(undirected)) if undirected.number_of_nodes() > 1 else 0.0,
        "mean_undirected_degree": mean_degree,
        "degree_cv": degree_cv,
        "max_out_degree": int(max(dict(graph.out_degree()).values(), default=0)),
        "average_clustering": float(nx.average_clustering(undirected)) if undirected.number_of_nodes() else 0.0,
        "connected": connected,
        "average_shortest_path_length": (
            float(nx.average_shortest_path_length(undirected)) if connected and undirected.number_of_nodes() > 1 else np.nan
        ),
        "greedy_modularity": modularity,
        "equal_degree_tie_edges": params.get("equal_degree_tie_edges", ""),
        "equal_degree_tie_edge_share": params.get("equal_degree_tie_edge_share", ""),
    }


def _sorted_targets(run_dir: Path, channel: str) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "target_nodes.csv")
    df = df[df["channel_factor"].astype(str) == channel].copy()
    keep = [c for c in ("exp_id", "content_factor", "channel_factor", "timing_factor", "agent_id") if c in df.columns]
    return df[keep].sort_values(keep).reset_index(drop=True)


def _public_nodes(run_dir: Path) -> tuple[str, ...]:
    df = pd.read_csv(run_dir / "clarification_exposure_plan.csv")
    mask = df["public_organic"].astype(str).str.lower().isin({"true", "1", "yes"})
    return tuple(sorted(df.loc[mask, "agent_id"].astype(str).unique()))


def _node_set(run_dir: Path) -> tuple[str, ...]:
    df = pd.read_csv(run_dir / "network_nodes.csv")
    return tuple(sorted(df["agent_id"].astype(str)))


def _invariants(run_dirs: dict[str, Path], profiles: pd.DataFrame) -> pd.DataFrame:
    baseline_id = profile_id("ba", NETWORK_SEEDS[0])
    baseline_dir = run_dirs[baseline_id]
    baseline_random_targets = _sorted_targets(baseline_dir, "random")
    baseline_public = _public_nodes(baseline_dir)
    baseline_nodes = _node_set(baseline_dir)
    rows = []

    baseline_hash = str((_read_summary(baseline_dir).get("network") or {}).get("network_hash", ""))
    rows.append(
        {
            "check_id": "BASELINE_BA_HASH_REPRODUCTION",
            "profile_id": baseline_id,
            "status": "PASS" if baseline_hash == BASELINE_NETWORK_HASH else "FAIL",
            "observed": baseline_hash,
            "criterion": BASELINE_NETWORK_HASH,
        }
    )

    for spec in profiles.itertuples(index=False):
        pid = str(spec.profile_id)
        run_dir = run_dirs[pid]
        summary = _read_summary(run_dir)
        condition_hashes = {
            str(row.get("network_hash", "")) for row in summary.get("condition_meta", [])
        }
        rows.append(
            {
                "check_id": "WITHIN_RUN_NETWORK_HASH_INVARIANCE",
                "profile_id": pid,
                "status": "PASS" if len(condition_hashes) == 1 else "FAIL",
                "observed": ";".join(sorted(condition_hashes)),
                "criterion": "all 9 conditions must share one topology",
            }
        )

        nodes = _node_set(run_dir)
        rows.append(
            {
                "check_id": "AGENT_NODE_SET_INVARIANCE",
                "profile_id": pid,
                "status": "PASS" if nodes == baseline_nodes else "FAIL",
                "observed": f"n={len(nodes)}",
                "criterion": "same 20 Engineering Persona IDs",
            }
        )

        random_targets = _sorted_targets(run_dir, "random")
        try:
            pd.testing.assert_frame_equal(
                baseline_random_targets,
                random_targets,
                check_dtype=False,
                check_exact=True,
            )
            status, observed = "PASS", "exact equality"
        except AssertionError as exc:
            status, observed = "FAIL", str(exc).splitlines()[0][:500]
        rows.append(
            {
                "check_id": "RANDOM_TARGET_ALLOCATION_INVARIANCE",
                "profile_id": pid,
                "status": status,
                "observed": observed,
                "criterion": "Random K=3 target IDs must not depend on topology/network seed",
            }
        )

        public = _public_nodes(run_dir)
        rows.append(
            {
                "check_id": "PUBLIC_ORGANIC_ALLOCATION_INVARIANCE",
                "profile_id": pid,
                "status": "PASS" if public == baseline_public else "FAIL",
                "observed": ";".join(public),
                "criterion": "public organic exposure IDs must remain fixed",
            }
        )

        clarification = summary.get("clarification_v33_parameters") or {}
        c_ok = (
            abs(float(clarification.get("paid_edge_probability", -1)) - 0.55) <= 1e-12
            and int(clarification.get("paid_delivery_lag", -1)) == 1
        )
        rows.append(
            {
                "check_id": "CLARIFICATION_BASELINE_PARAMETERS_FROZEN",
                "profile_id": pid,
                "status": "PASS" if c_ok else "FAIL",
                "observed": json.dumps(clarification, ensure_ascii=False, sort_keys=True),
                "criterion": "paid_edge_probability=.55 and paid_delivery_lag=1",
            }
        )
    return pd.DataFrame(rows)


def _family_summary(estimands: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (topology, estimand_id), group in estimands.groupby(["topology", "estimand_id"]):
        values = pd.to_numeric(group["value"], errors="raise")
        signs = ["positive" if x > 0 else "negative" if x < 0 else "zero" for x in values]
        rows.append(
            {
                "topology": topology,
                "estimand_id": estimand_id,
                "network_realizations": len(values),
                "mean": values.mean(),
                "min": values.min(),
                "max": values.max(),
                "range": values.max() - values.min(),
                "signs": ";".join(signs),
                "sign_stable_within_topology": len(set(signs)) == 1,
                "analysis_role": "engineering descriptive across pre-specified network realizations; not formal inference",
            }
        )
    return pd.DataFrame(rows)


def _plot_estimand(estimands: pd.DataFrame, estimand_id: str, path: Path) -> str | None:
    df = estimands[estimands["estimand_id"].astype(str) == estimand_id].copy()
    if df.empty:
        return None
    df["value"] = pd.to_numeric(df["value"], errors="raise")
    fig, ax = plt.subplots(figsize=(8, 5))
    for x, topology in enumerate(TOPOLOGIES):
        part = df[df["topology"] == topology].sort_values("network_seed")
        offsets = np.linspace(-0.12, 0.12, len(part)) if len(part) > 1 else np.array([0.0])
        ax.scatter(np.full(len(part), x) + offsets, part["value"], s=45)
        if len(part):
            ax.plot([x - 0.18, x + 0.18], [part["value"].mean()] * 2, linewidth=2)
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xticks(range(len(TOPOLOGIES)))
    ax.set_xticklabels(["BA", "Watts-Strogatz", "Community SBM"])
    ax.set_ylabel(str(df["unit"].iloc[0]))
    ax.set_title(f"Network-topology robustness: {estimand_id}\n5 pre-specified network realizations per topology; Fake LLM, T35")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


async def run_topology_sensitivity_suite(
    *,
    output_root: Path = PROJECT_ROOT / "results" / "v33_topology_sensitivity",
    simulation_seed: int = DEFAULT_SIMULATION_SEED,
    llm_seed: int = DEFAULT_LLM_SEED,
    demand_seed: int = DEFAULT_DEMAND_SEED,
) -> dict:
    suite_id = dt.datetime.now().strftime("topology_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)

    profiles = profile_table()
    profiles.to_csv(suite_dir / "topology_profiles.csv", index=False, encoding="utf-8-sig")
    run_dirs: dict[str, Path] = {}
    estimand_frames = []
    network_rows = []
    analysis_payloads = {}

    for row in profiles.itertuples(index=False):
        pid = str(row.profile_id)
        spec = NetworkVariantV331Spec(
            topology=str(row.topology),
            network_seed=int(row.network_seed),
        )
        settings = RunSettings(
            llm_mode="fake",
            condition="all",
            simulation_seed=simulation_seed,
            requested_llm_seed=llm_seed,
            demand_seed=demand_seed,
            output_dir=suite_dir / "profiles" / pid,
            run_demand=True,
            support_mode="both",
            allow_real_llm=False,
            total_ticks=35,
        )
        payload = await _execute_with_network_spec(settings, spec)
        run_dir = Path(payload["output_dir"])
        run_dirs[pid] = run_dir
        analysis_payloads[pid] = analyze_run(run_dir)
        estimand_frames.append(_read_estimands(run_dir, pid, str(row.topology), int(row.network_seed)))
        network_rows.append(_network_metrics(run_dir, pid, str(row.topology), int(row.network_seed)))

    estimands = pd.concat(estimand_frames, ignore_index=True)
    estimands.to_csv(suite_dir / "topology_estimands.csv", index=False, encoding="utf-8-sig")
    metrics = pd.DataFrame(network_rows)
    metrics.to_csv(suite_dir / "topology_network_metrics.csv", index=False, encoding="utf-8-sig")
    invariants = _invariants(run_dirs, profiles)
    invariants.to_csv(suite_dir / "topology_invariants.csv", index=False, encoding="utf-8-sig")
    family = _family_summary(estimands)
    family.to_csv(suite_dir / "topology_family_summary.csv", index=False, encoding="utf-8-sig")

    figures = []
    for estimand_id in (
        "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
        "P3_TIMING_PRE_DELAY_TRUST_V33",
        "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33",
        "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    ):
        output = _plot_estimand(estimands, estimand_id, suite_dir / "figures" / f"{estimand_id}.png")
        if output:
            figures.append(output)

    failures = int((invariants["status"] == "FAIL").sum())
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS" if failures == 0 else "FAIL",
        "scope": "Fake-LLM fixed-N network-topology engineering robustness; not calibration or formal inference",
        "topologies": list(TOPOLOGIES),
        "network_seeds": list(NETWORK_SEEDS),
        "profiles_run": len(profiles),
        "cognitive_agents": 20,
        "baseline_horizon": 35,
        "simulation_seed": simulation_seed,
        "llm_seed": llm_seed,
        "demand_seed": demand_seed,
        "baseline_paid_edge_probability": 0.55,
        "baseline_paid_delivery_lag": 1,
        "invariant_failures": failures,
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "topology_selection_permitted": False,
        "interpretation_rule": (
            "Report topology/realization dependence as structural boundary evidence; "
            "do not select the topology that produces the preferred effect."
        ),
        "analysis": analysis_payloads,
        "run_dirs": {key: str(value) for key, value in run_dirs.items()},
        "figures": figures,
        "output_dir": str(suite_dir),
    }
    (suite_dir / "topology_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def run_sync(**kwargs) -> dict:
    return asyncio.run(run_topology_sensitivity_suite(**kwargs))
