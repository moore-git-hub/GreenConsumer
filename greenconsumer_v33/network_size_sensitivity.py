"""Network-size × targeting-budget robustness for TASK_005 v3.3.1.

Pre-specified design:
- N = 20 / 40 / 80 cognitive Agents;
- BA m=2 only, five network-only seeds;
- fixed K=3 versus proportional K/N=15% (K=3/6/12);
- nested balanced non-cloned persona panels;
- Fake LLM, T35, frozen Trust/clarification mechanisms.

This is engineering robustness, not calibration or formal inference.
"""
from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

import task005_fmcg_runtime_v33 as runtime_module
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
from .network_variants import BASELINE_NETWORK_HASH, NetworkVariantV331Spec
from .persona_panels import (
    PANEL_SCHEMA,
    SUPPORTED_SIZES,
    build_nested_persona_panel,
    panel_audit_rows,
    panel_marginal_rows,
    persona_tuple,
)
from . import runner as runner_module

SCHEMA = "task005_fmcg_v331_network_size_sensitivity1.0"
NETWORK_SEEDS = tuple(range(2026081501, 2026081506))
BASELINE_N = 20
BASELINE_K = 3
PROPORTIONAL_SHARE = BASELINE_K / BASELINE_N
CONTROL = "NoClarification-Control"


def proportional_k(n: int) -> int:
    return int(round(float(n) * PROPORTIONAL_SHARE))


def _profile_specs() -> list[dict]:
    specs = []
    for seed in NETWORK_SEEDS:
        specs.append(
            {
                "profile_id": f"n20_k3_nseed{seed}",
                "num_agents": 20,
                "budget_k": 3,
                "budget_regime": "shared-baseline",
                "network_seed": seed,
                "profile_role": (
                    "frozen-baseline-network-size"
                    if seed == NETWORK_SEEDS[0]
                    else "pre-specified-size-robustness"
                ),
            }
        )
        for n in (40, 80):
            specs.append(
                {
                    "profile_id": f"n{n}_k3_fixed_nseed{seed}",
                    "num_agents": n,
                    "budget_k": 3,
                    "budget_regime": "fixed-k3",
                    "network_seed": seed,
                    "profile_role": "pre-specified-size-robustness",
                }
            )
            k_prop = proportional_k(n)
            specs.append(
                {
                    "profile_id": f"n{n}_k{k_prop}_proportional_nseed{seed}",
                    "num_agents": n,
                    "budget_k": k_prop,
                    "budget_regime": "proportional-15pct",
                    "network_seed": seed,
                    "profile_role": "pre-specified-size-robustness",
                }
            )
    return specs


def profile_table() -> pd.DataFrame:
    df = pd.DataFrame(_profile_specs())
    df["paid_seed_share"] = df["budget_k"] / df["num_agents"]
    return df


async def _execute_size_profile(
    settings: RunSettings,
    *,
    panel,
    budget_k: int,
    network_seed: int,
) -> dict:
    """Run one labelled size profile while restoring all normal runner globals."""

    n = len(panel)
    spec = NetworkVariantV331Spec(topology="ba", network_seed=int(network_seed), ba_m=2)
    spec.validate(n)

    original_num_agents = runner_module.DEFAULT_NUM_AGENTS
    original_configs = runner_module._configs
    original_run_scenario = runner_module.run_scenario_v33
    original_simulate_demand = runner_module.simulate_demand
    original_runtime_personas = runtime_module.ENGINEERING_PERSONAS
    original_runtime_profiles = runtime_module.engineering_profiles

    def scoped_configs(run_settings):
        configs = original_configs(run_settings)
        return [
            dataclasses.replace(
                cfg,
                num_agents=n,
                budget_k=0 if cfg.is_control else int(budget_k),
            )
            for cfg in configs
        ]

    async def scoped_run_scenario(
        config,
        *,
        override_router,
        trust_parameters=DEFAULT_TRUST_PARAMETERS,
    ):
        return await original_run_scenario(
            config,
            override_router=override_router,
            trust_parameters=trust_parameters,
            clarification_parameters=DEFAULT_CLARIFICATION_PARAMETERS,
            network_spec=spec,
        )

    def scoped_demand(
        cognitive_rows,
        *,
        support_present,
        demand_seed,
        micro_buyers=25,
    ):
        return original_simulate_demand(
            cognitive_rows,
            support_present=support_present,
            demand_seed=demand_seed,
            micro_buyers=micro_buyers,
            personas=tuple(panel),
        )

    runner_module.DEFAULT_NUM_AGENTS = n
    runner_module._configs = scoped_configs
    runner_module.run_scenario_v33 = scoped_run_scenario
    runner_module.simulate_demand = scoped_demand
    runtime_module.ENGINEERING_PERSONAS = tuple(panel)
    runtime_module.engineering_profiles = lambda: tuple(p.to_profile() for p in panel)
    try:
        return await runner_module.execute(
            settings,
            trust_parameters=DEFAULT_TRUST_PARAMETERS,
        )
    finally:
        runner_module.DEFAULT_NUM_AGENTS = original_num_agents
        runner_module._configs = original_configs
        runner_module.run_scenario_v33 = original_run_scenario
        runner_module.simulate_demand = original_simulate_demand
        runtime_module.ENGINEERING_PERSONAS = original_runtime_personas
        runtime_module.engineering_profiles = original_runtime_profiles


def _read_summary(run_dir: Path) -> dict:
    return json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))


def _read_estimands(run_dir: Path, spec) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "single_block_estimands.csv")
    insert = [
        ("profile_id", spec.profile_id),
        ("num_agents", int(spec.num_agents)),
        ("budget_k", int(spec.budget_k)),
        ("budget_regime", str(spec.budget_regime)),
        ("network_seed", int(spec.network_seed)),
        ("paid_seed_share", float(spec.budget_k / spec.num_agents)),
    ]
    for index, (name, value) in enumerate(insert):
        df.insert(index, name, value)
    return df


def _network_metrics(run_dir: Path, spec) -> dict:
    nodes = pd.read_csv(run_dir / "network_nodes.csv")
    edges = pd.read_csv(run_dir / "network_edges.csv")
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes["agent_id"].astype(str))
    graph.add_edges_from(zip(edges["source_agent_id"].astype(str), edges["target_agent_id"].astype(str)))
    undirected = graph.to_undirected()
    degrees = np.array([d for _, d in undirected.degree()], dtype=float)
    mean_degree = float(degrees.mean()) if len(degrees) else 0.0
    connected = bool(nx.is_connected(undirected)) if len(undirected) else True
    return {
        "profile_id": spec.profile_id,
        "num_agents": int(spec.num_agents),
        "budget_k": int(spec.budget_k),
        "budget_regime": str(spec.budget_regime),
        "paid_seed_share": float(spec.budget_k / spec.num_agents),
        "network_seed": int(spec.network_seed),
        "network_hash": str((_read_summary(run_dir).get("network") or {}).get("network_hash", "")),
        "num_directed_edges": int(graph.number_of_edges()),
        "undirected_density": float(nx.density(undirected)) if len(undirected) > 1 else 0.0,
        "mean_undirected_degree": mean_degree,
        "degree_cv": float(degrees.std(ddof=0) / mean_degree) if mean_degree else 0.0,
        "max_out_degree": int(max(dict(graph.out_degree()).values(), default=0)),
        "max_out_degree_share": float(max(dict(graph.out_degree()).values(), default=0) / len(graph)) if len(graph) else 0.0,
        "reach_granularity": float(1.0 / len(graph)) if len(graph) else np.nan,
        "average_clustering": float(nx.average_clustering(undirected)) if len(undirected) else 0.0,
        "connected": connected,
        "average_shortest_path_length": (
            float(nx.average_shortest_path_length(undirected)) if connected and len(undirected) > 1 else np.nan
        ),
    }


def _reach_summary(run_dir: Path, spec) -> list[dict]:
    df = pd.read_csv(run_dir / "clarification_reach_v33.csv")
    rows = []
    for channel in ("hub", "random"):
        part = df[df["exp_id"].astype(str).str.contains(f"-{channel.title()}-")]
        vals = pd.to_numeric(part["eventual_enterprise_reach"], errors="raise")
        rows.append(
            {
                "profile_id": spec.profile_id,
                "num_agents": int(spec.num_agents),
                "budget_k": int(spec.budget_k),
                "budget_regime": str(spec.budget_regime),
                "paid_seed_share": float(spec.budget_k / spec.num_agents),
                "network_seed": int(spec.network_seed),
                "channel": channel,
                "eventual_enterprise_reach": float(vals.mean()),
                "reach_granularity": 1.0 / int(spec.num_agents),
            }
        )
    return rows


def _shared_pre_treatment(run_dir: Path, n_shared: int = 20) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "cognitive_records.csv")
    keep_agents = {f"Consumer_{i:03d}" for i in range(int(n_shared))}
    df = df[
        (pd.to_numeric(df["tick"], errors="raise") <= 5)
        & df["agent_id"].astype(str).isin(keep_agents)
    ].copy()
    sort_cols = [c for c in ("exp_id", "tick", "agent_id") if c in df.columns]
    return df.sort_values(sort_cols).reset_index(drop=True)


def _exact_common(a: pd.DataFrame, b: pd.DataFrame) -> tuple[str, str]:
    common = [c for c in a.columns if c in b.columns]
    try:
        pd.testing.assert_frame_equal(a[common], b[common], check_dtype=False, check_exact=True)
        return "PASS", "exact equality"
    except AssertionError as exc:
        return "FAIL", str(exc).splitlines()[0][:500]


def _invariants(run_dirs: dict[str, Path], profiles: pd.DataFrame, panels: dict[int, tuple]) -> pd.DataFrame:
    rows = []
    baseline_id = f"n20_k3_nseed{NETWORK_SEEDS[0]}"
    baseline_dir = run_dirs[baseline_id]
    baseline_pre = _shared_pre_treatment(baseline_dir)
    baseline_hash = str((_read_summary(baseline_dir).get("network") or {}).get("network_hash", ""))
    rows.append({
        "check_id": "BASELINE_N20_HASH_REPRODUCTION",
        "profile_id": baseline_id,
        "status": "PASS" if baseline_hash == BASELINE_NETWORK_HASH else "FAIL",
        "observed": baseline_hash,
        "criterion": BASELINE_NETWORK_HASH,
    })

    p20 = [persona_tuple(p) for p in panels[20]]
    p40 = [persona_tuple(p) for p in panels[40]]
    p80 = [persona_tuple(p) for p in panels[80]]
    for check_id, ok, observed in (
        ("PERSONA_N20_IN_N40_PREFIX", p20 == p40[:20], "exact prefix" if p20 == p40[:20] else "mismatch"),
        ("PERSONA_N40_IN_N80_PREFIX", p40 == p80[:40], "exact prefix" if p40 == p80[:40] else "mismatch"),
        ("PERSONA_N80_NO_CLONES", len(set(p80)) == 80, f"unique={len(set(p80))}"),
    ):
        rows.append({"check_id": check_id, "profile_id": "suite", "status": "PASS" if ok else "FAIL", "observed": observed, "criterion": "must pass"})

    for spec in profiles.itertuples(index=False):
        pid = str(spec.profile_id)
        run_dir = run_dirs[pid]
        summary = _read_summary(run_dir)
        hashes = {str(row.get("network_hash", "")) for row in summary.get("condition_meta", [])}
        rows.append({
            "check_id": "WITHIN_RUN_NETWORK_HASH_INVARIANCE",
            "profile_id": pid,
            "status": "PASS" if len(hashes) == 1 else "FAIL",
            "observed": ";".join(sorted(hashes)),
            "criterion": "all 9 conditions share one topology",
        })

        nodes = pd.read_csv(run_dir / "network_nodes.csv")
        node_ids = tuple(sorted(nodes["agent_id"].astype(str)))
        expected_ids = tuple(f"Consumer_{i:03d}" for i in range(int(spec.num_agents)))
        rows.append({
            "check_id": "PERSONA_NODE_SET_MATCH",
            "profile_id": pid,
            "status": "PASS" if node_ids == expected_ids else "FAIL",
            "observed": f"n={len(node_ids)}",
            "criterion": f"exact Consumer_000..Consumer_{int(spec.num_agents)-1:03d}",
        })

        targets = pd.read_csv(run_dir / "target_nodes.csv")
        treatment_counts = targets.groupby("exp_id").size().to_dict() if not targets.empty else {}
        budget_ok = bool(treatment_counts) and all(int(v) == int(spec.budget_k) for v in treatment_counts.values())
        rows.append({
            "check_id": "BUDGET_K_INTEGRITY",
            "profile_id": pid,
            "status": "PASS" if budget_ok else "FAIL",
            "observed": json.dumps(treatment_counts, sort_keys=True),
            "criterion": f"every treatment condition has K={int(spec.budget_k)} paid seeds",
        })

        clarification = summary.get("clarification_v33_parameters") or {}
        c_ok = (
            abs(float(clarification.get("paid_edge_probability", -1)) - 0.55) <= 1e-12
            and int(clarification.get("paid_delivery_lag", -1)) == 1
        )
        rows.append({
            "check_id": "CLARIFICATION_BASELINE_PARAMETERS_FROZEN",
            "profile_id": pid,
            "status": "PASS" if c_ok else "FAIL",
            "observed": json.dumps(clarification, ensure_ascii=False, sort_keys=True),
            "criterion": "paid_edge_probability=.55 and paid_delivery_lag=1",
        })

        if int(spec.network_seed) == NETWORK_SEEDS[0]:
            pre = _shared_pre_treatment(run_dir)
            status, detail = _exact_common(baseline_pre, pre)
            rows.append({
                "check_id": "SHARED_N20_PRE_TREATMENT_PREFIX",
                "profile_id": pid,
                "status": status,
                "observed": detail,
                "criterion": "shared Consumer_000..019 T1-T5 cognitive history equals N20 baseline for seed 2026081501",
            })
    return pd.DataFrame(rows)


def _family_summary(estimands: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (n, regime, k, estimand_id), group in estimands.groupby(["num_agents", "budget_regime", "budget_k", "estimand_id"]):
        values = pd.to_numeric(group["value"], errors="raise")
        signs = ["positive" if x > 0 else "negative" if x < 0 else "zero" for x in values]
        rows.append({
            "num_agents": int(n),
            "budget_regime": regime,
            "budget_k": int(k),
            "estimand_id": estimand_id,
            "network_realizations": len(values),
            "mean": values.mean(),
            "min": values.min(),
            "max": values.max(),
            "range": values.max() - values.min(),
            "signs": ";".join(signs),
            "sign_stable": len(set(signs)) == 1,
            "analysis_role": "engineering descriptive across pre-specified BA realizations; not formal inference",
        })
    return pd.DataFrame(rows)


def _plot_estimand(estimands: pd.DataFrame, estimand_id: str, path: Path) -> str | None:
    df = estimands[estimands["estimand_id"].astype(str) == estimand_id].copy()
    if df.empty:
        return None
    df["value"] = pd.to_numeric(df["value"], errors="raise")
    fig, ax = plt.subplots(figsize=(8, 5))
    base = df[df["num_agents"].astype(int) == 20]
    base_mean = float(base["value"].mean())
    for regime, label in (("fixed-k3", "fixed K=3"), ("proportional-15pct", "proportional K/N=15%")):
        xs, ys = [20], [base_mean]
        for n in (40, 80):
            part = df[(df["num_agents"].astype(int) == n) & (df["budget_regime"] == regime)]
            xs.append(n)
            ys.append(float(part["value"].mean()))
            ax.scatter(np.full(len(part), n), part["value"], alpha=0.35)
        ax.plot(xs, ys, marker="o", label=label)
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xticks([20, 40, 80])
    ax.set_xlabel("Cognitive Agent network size N")
    ax.set_ylabel(str(df["unit"].iloc[0]))
    ax.set_title(f"Network-size robustness: {estimand_id}\nBA m=2; 5 pre-specified network realizations; Fake LLM, T35")
    ax.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


def _plot_reach(reach: pd.DataFrame, path: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 5))
    for regime, label in (("fixed-k3", "fixed K=3"), ("proportional-15pct", "proportional K/N=15%")):
        for channel, linestyle in (("hub", "-"), ("random", "--")):
            base = reach[(reach["num_agents"] == 20) & (reach["channel"] == channel)]
            xs, ys = [20], [float(base["eventual_enterprise_reach"].mean())]
            for n in (40, 80):
                part = reach[(reach["num_agents"] == n) & (reach["budget_regime"] == regime) & (reach["channel"] == channel)]
                xs.append(n)
                ys.append(float(part["eventual_enterprise_reach"].mean()))
            ax.plot(xs, ys, marker="o", linestyle=linestyle, label=f"{label}; {channel}")
    ax.set_xticks([20, 40, 80])
    ax.set_xlabel("Cognitive Agent network size N")
    ax.set_ylabel("Eventual direct enterprise reach")
    ax.set_title("Hub and Random reach under network-size / budget scaling\nBA m=2; Fake LLM, T35")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


async def run_network_size_sensitivity_suite(
    *,
    output_root: Path = PROJECT_ROOT / "results" / "v33_network_size_sensitivity",
    simulation_seed: int = DEFAULT_SIMULATION_SEED,
    llm_seed: int = DEFAULT_LLM_SEED,
    demand_seed: int = DEFAULT_DEMAND_SEED,
) -> dict:
    suite_id = dt.datetime.now().strftime("size_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)

    profiles = profile_table()
    profiles.to_csv(suite_dir / "size_profiles.csv", index=False, encoding="utf-8-sig")
    panels = {n: build_nested_persona_panel(n) for n in SUPPORTED_SIZES}
    pd.DataFrame([row for n in SUPPORTED_SIZES for row in panel_audit_rows(panels[n])]).to_csv(
        suite_dir / "persona_panels.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([row for n in SUPPORTED_SIZES for row in panel_marginal_rows(panels[n])]).to_csv(
        suite_dir / "persona_marginal_balance.csv", index=False, encoding="utf-8-sig"
    )

    run_dirs = {}
    estimand_frames = []
    metric_rows = []
    reach_rows = []
    analysis_payloads = {}

    for spec in profiles.itertuples(index=False):
        settings = RunSettings(
            llm_mode="fake",
            condition="all",
            simulation_seed=simulation_seed,
            requested_llm_seed=llm_seed,
            demand_seed=demand_seed,
            output_dir=suite_dir / "profiles" / str(spec.profile_id),
            run_demand=True,
            support_mode="both",
            allow_real_llm=False,
            total_ticks=35,
        )
        payload = await _execute_size_profile(
            settings,
            panel=panels[int(spec.num_agents)],
            budget_k=int(spec.budget_k),
            network_seed=int(spec.network_seed),
        )
        run_dir = Path(payload["output_dir"])
        run_dirs[str(spec.profile_id)] = run_dir
        analysis_payloads[str(spec.profile_id)] = analyze_run(run_dir)
        estimand_frames.append(_read_estimands(run_dir, spec))
        metric_rows.append(_network_metrics(run_dir, spec))
        reach_rows.extend(_reach_summary(run_dir, spec))

    estimands = pd.concat(estimand_frames, ignore_index=True)
    estimands.to_csv(suite_dir / "size_estimands.csv", index=False, encoding="utf-8-sig")
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(suite_dir / "size_network_metrics.csv", index=False, encoding="utf-8-sig")
    reach = pd.DataFrame(reach_rows)
    reach.to_csv(suite_dir / "size_reach.csv", index=False, encoding="utf-8-sig")
    family = _family_summary(estimands)
    family.to_csv(suite_dir / "size_family_summary.csv", index=False, encoding="utf-8-sig")
    invariants = _invariants(run_dirs, profiles, panels)
    invariants.to_csv(suite_dir / "size_invariants.csv", index=False, encoding="utf-8-sig")

    figures = []
    for eid in (
        "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
        "P3_TIMING_PRE_DELAY_TRUST_V33",
        "P4_CHANNEL_EVENTUAL_ENTERPRISE_REACH_V33",
        "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    ):
        path = _plot_estimand(estimands, eid, suite_dir / "figures" / f"{eid}.png")
        if path:
            figures.append(path)
    figures.append(_plot_reach(reach, suite_dir / "figures" / "HUB_RANDOM_REACH_BY_SIZE.png"))

    failures = int((invariants["status"] == "FAIL").sum())
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS" if failures == 0 else "FAIL",
        "scope": "Fake-LLM BA network-size × targeting-budget engineering robustness; not formal inference",
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "parameter_selection_permitted": False,
        "persona_panel_schema": PANEL_SCHEMA,
        "network_sizes": list(SUPPORTED_SIZES),
        "network_seeds": list(NETWORK_SEEDS),
        "profiles_run": len(profiles),
        "budget_regimes": {
            "fixed-k3": {"K": 3},
            "proportional-15pct": {"share": PROPORTIONAL_SHARE, "K_by_N": {"20": 3, "40": 6, "80": 12}},
        },
        "baseline_horizon": 35,
        "baseline_topology": "BA m=2",
        "baseline_paid_edge_probability": 0.55,
        "baseline_paid_delivery_lag": 1,
        "micro_buyers_per_cognitive_agent": 25,
        "simulation_seed": simulation_seed,
        "llm_seed": llm_seed,
        "demand_seed": demand_seed,
        "invariant_failures": failures,
        "analysis": analysis_payloads,
        "run_dirs": {k: str(v) for k, v in run_dirs.items()},
        "figures": figures,
        "interpretation_rule": (
            "Treat N and K/N effects as model-scale/budget boundary evidence; do not select the size or budget producing the preferred effect"
        ),
    }
    (suite_dir / "size_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary["output_dir"] = str(suite_dir)
    return summary


def run_sync(**kwargs) -> dict:
    return asyncio.run(run_network_size_sensitivity_suite(**kwargs))
