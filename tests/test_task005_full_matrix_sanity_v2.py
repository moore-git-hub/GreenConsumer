from __future__ import annotations

import contextlib
import inspect
import io
import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mechanism_v2 as mechanism
from experiment_config import (
    CHANNEL_LEVELS,
    CONTENT_LEVELS,
    CONTROL_EXP_ID,
    EXPERIMENT_MATRIX_VERSION,
    STRATEGY_TIMING_LEVELS,
    generate_experiment_matrix,
)
from node_selector import select_target_nodes


DESIGN_PATH = (
    ROOT
    / ".kiro/specs/task005-replication-inference/"
    / "deterministic_full_matrix_sanity_v2_design1.0.json"
)
RESULT_PATH = (
    ROOT
    / ".kiro/specs/task005-replication-inference/"
    / "deterministic_full_matrix_sanity_v2_result1.0.json"
)

DIAGNOSTIC_SEEDS = tuple(range(4201, 4213))
BASELINE_TRUST = 6.0
CONTENT_CONTRAST_TOLERANCE = 1e-9

SCANDAL_ORACLE = {
    "valence": -0.85,
    "arousal": 0.80,
    "credibility": 0.80,
    "evidence_strength": 0.65,
    "topic_relevance": 0.95,
}

CLARIFICATION_ORACLE = {
    "rational-evidence": {
        "valence": 0.50,
        "arousal": 0.45,
        "credibility": 0.90,
        "evidence_strength": 0.95,
        "topic_relevance": 0.90,
    },
    "emotional-empathy": {
        "valence": 0.75,
        "arousal": 0.75,
        "credibility": 0.72,
        "evidence_strength": 0.35,
        "topic_relevance": 0.90,
    },
}


class Reporter:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.warned = 0

    def check(self, name: str, condition: bool, actual: Any = None) -> None:
        if condition:
            self.passed += 1
            print("PASS", name)
        else:
            self.failed += 1
            print("FAIL", name, actual)

    def warn(self, name: str, actual: Any = None) -> None:
        self.warned += 1
        print("WARNING", name, actual)


def _build_production_like_graph(seed: int, n: int = 20) -> nx.DiGraph:
    agent_ids = [f"Agent_{i:02d}" for i in range(n)]
    undirected = nx.barabasi_albert_graph(n, m=2, seed=seed)
    undirected = nx.relabel_nodes(undirected, {i: agent_ids[i] for i in range(n)})
    degrees = dict(undirected.degree())
    directed = nx.DiGraph()
    directed.add_nodes_from(undirected.nodes())
    for u, v in undirected.edges():
        if degrees[u] >= degrees[v]:
            directed.add_edge(u, v)
        else:
            directed.add_edge(v, u)
    return directed


def _select_targets_silent(graph: nx.Graph, channel: str, k: int, seed: int) -> list[str]:
    with contextlib.redirect_stdout(io.StringIO()):
        return list(select_target_nodes(graph, channel, k, seed))


def _sum_window(values: list[float], start_tick: int, end_tick: int) -> float:
    return float(sum(values[start_tick - 1 : end_tick]))


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values))


def _diagnostic_run(config: Any, seed: int) -> dict[str, Any]:
    cfg = replace(config, random_seed=seed)
    graph = _build_production_like_graph(seed, cfg.num_agents)

    if cfg.is_control:
        target_nodes: list[str] = []
        public_nodes: list[str] = []
        amplified_nodes: list[str] = []
    else:
        target_nodes = _select_targets_silent(
            graph, cfg.channel_factor, cfg.budget_k, cfg.random_seed
        )
        public_nodes = mechanism.select_public_exposure_nodes(
            graph.nodes(), cfg.random_seed, mechanism.PUBLIC_EXPOSURE_RATE
        )
        amplified_nodes = mechanism.one_hop_amplification_nodes(graph, target_nodes)

    reached_nodes = sorted(set(public_nodes) | set(target_nodes) | set(amplified_nodes))
    states = {
        node: {
            "baseline_trust": BASELINE_TRUST,
            "previous_trust": BASELINE_TRUST,
            "attitude_att": 0.60,
            "subjective_norm_sn": 0.50,
            "pbc": 0.50,
            "crisis_memory": 0.0,
            "repair_memory": 0.0,
        }
        for node in graph.nodes()
    }

    trajectory: list[float] = []
    clipping_count = 0
    pbc_invariant = True

    for tick in range(1, cfg.total_ticks + 1):
        for node, state in states.items():
            signal = {
                "valence": 0.0,
                "arousal": 0.0,
                "credibility": 0.50,
                "evidence_strength": 0.0,
                "topic_relevance": 0.0,
                "had_observation": False,
                "social_observation_count": 0,
            }

            if tick == cfg.scandal_tick:
                signal.update(SCANDAL_ORACLE)
                signal["had_observation"] = True

            if (
                not cfg.is_control
                and tick == cfg.clarification_tick
                and node in reached_nodes
            ):
                signal.update(CLARIFICATION_ORACLE[cfg.content_factor])
                signal["had_observation"] = True
                signal["social_observation_count"] = int(node in target_nodes) + int(
                    node in amplified_nodes
                )

            updated = mechanism.update_psychological_state(**state, **signal)
            if updated["trust_final"] <= 1e-12 or updated["trust_final"] >= 10.0 - 1e-12:
                clipping_count += 1
            if updated["pbc"] != state["pbc"]:
                pbc_invariant = False

            state.update(
                previous_trust=updated["trust_final"],
                attitude_att=updated["attitude_att"],
                subjective_norm_sn=updated["subjective_norm_sn"],
                pbc=updated["pbc"],
                crisis_memory=updated["crisis_memory"],
                repair_memory=updated["repair_memory"],
            )

        trajectory.append(_mean([s["previous_trust"] for s in states.values()]))

    union_reach = sorted(set(public_nodes) | set(target_nodes) | set(amplified_nodes))
    return {
        "seed": seed,
        "exp_id": cfg.exp_id,
        "content_factor": cfg.content_factor,
        "channel_factor": cfg.channel_factor,
        "timing_factor": cfg.timing_factor,
        "is_control": cfg.is_control,
        "clarification_tick": cfg.clarification_tick,
        "target_nodes": sorted(str(n) for n in target_nodes),
        "public_nodes": sorted(str(n) for n in public_nodes),
        "amplified_nodes": sorted(str(n) for n in amplified_nodes),
        "reached_nodes": union_reach,
        "clarification_reach": len(union_reach),
        "trajectory": trajectory,
        "final_trust": trajectory[-1],
        "post_crisis_auc": _sum_window(trajectory, cfg.scandal_tick, cfg.total_ticks),
        "early_auc": _sum_window(trajectory, 6, 10),
        "clipping_count": clipping_count,
        "pbc_invariant": pbc_invariant,
    }


def _result_record(metrics: dict[str, Any], passed: bool, failed: int) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "stage": "TASK_005 deterministic-full-matrix-sanity-v2",
        "status": "diagnostic-only",
        "matrix_conditions": metrics["matrix_conditions"],
        "diagnostic_seeds": list(DIAGNOSTIC_SEEDS),
        "simulation_rows": metrics["simulation_rows"],
        "hub_mean_reach": metrics["hub_mean_reach"],
        "random_mean_reach": metrics["random_mean_reach"],
        "hub_advantage_seed_count": metrics["hub_advantage_seed_count"],
        "min_treatment_final_trust_gain": metrics["min_treatment_final_trust_gain"],
        "min_treatment_post_crisis_auc_gain": metrics[
            "min_treatment_post_crisis_auc_gain"
        ],
        "min_immediate_minus_delayed_early_auc": metrics[
            "min_immediate_minus_delayed_early_auc"
        ],
        "mean_immediate_minus_delayed_final_trust": metrics[
            "mean_immediate_minus_delayed_final_trust"
        ],
        "min_abs_content_final_trust_contrast": metrics[
            "min_abs_content_final_trust_contrast"
        ],
        "trust_clipping_count": metrics["trust_clipping_count"],
        "pbc_invariant": metrics["pbc_invariant"],
        "passed": passed,
        "failed": failed,
        "formal_inference": False,
        "formal_effect_evidence": False,
        "statistical_significance_evidence": False,
        "synthetic_oracle_is_empirical_calibration": False,
        "literature_derived": False,
        "real_llm_calls": False,
        "formal_execution": False,
        "p_values_computed": False,
        "parameter_tuned_to_significance": False,
    }


def main() -> int:
    reporter = Reporter()
    matrix = generate_experiment_matrix()
    treatments = [cfg for cfg in matrix if not cfg.is_control]
    controls = [cfg for cfg in matrix if cfg.is_control]

    reporter.check("matrix has exactly 9 conditions", len(matrix) == 9, len(matrix))
    reporter.check("matrix version is 3.0", EXPERIMENT_MATRIX_VERSION == "3.0")
    reporter.check("one common control", len(controls) == 1, [c.exp_id for c in controls])
    reporter.check("control exp_id frozen", controls[0].exp_id == CONTROL_EXP_ID)
    reporter.check("8 treatment cells", len(treatments) == 8, len(treatments))

    rows = [_diagnostic_run(cfg, seed) for seed in DIAGNOSTIC_SEEDS for cfg in matrix]
    by_seed_exp = {(row["seed"], row["exp_id"]): row for row in rows}

    control_rows = [row for row in rows if row["is_control"]]
    treatment_rows = [row for row in rows if not row["is_control"]]
    reporter.check(
        "control clarification reach is zero",
        all(row["clarification_reach"] == 0 for row in control_rows),
        [row["clarification_reach"] for row in control_rows],
    )

    public_blocking_ok = True
    for seed in DIAGNOSTIC_SEEDS:
        sets = {
            tuple(row["public_nodes"])
            for row in treatment_rows
            if row["seed"] == seed
        }
        if len(sets) != 1:
            public_blocking_ok = False
            break
    reporter.check("public exposure condition-blocked within seed", public_blocking_ok)

    same_k_ok = all(len(row["target_nodes"]) == 3 for row in treatment_rows)
    reporter.check("paid seed budget K equal across treatments", same_k_ok)
    union_ok = all(
        sorted(set(row["public_nodes"]) | set(row["target_nodes"]) | set(row["amplified_nodes"]))
        == row["reached_nodes"]
        for row in treatment_rows
    )
    reporter.check("union reach equals public plus paid seed plus one-hop", union_ok)

    hub_seed_means: list[float] = []
    random_seed_means: list[float] = []
    hub_advantage_count = 0
    for seed in DIAGNOSTIC_SEEDS:
        hub_reach = [
            row["clarification_reach"]
            for row in treatment_rows
            if row["seed"] == seed and row["channel_factor"] == "hub"
        ]
        random_reach = [
            row["clarification_reach"]
            for row in treatment_rows
            if row["seed"] == seed and row["channel_factor"] == "random"
        ]
        hub_mean = _mean(hub_reach)
        random_mean = _mean(random_reach)
        hub_seed_means.append(hub_mean)
        random_seed_means.append(random_mean)
        if hub_mean > random_mean:
            hub_advantage_count += 1
    hub_mean_reach = _mean(hub_seed_means)
    random_mean_reach = _mean(random_seed_means)
    reporter.check(
        "hub mean reach exceeds random mean reach",
        hub_mean_reach > random_mean_reach,
        (hub_mean_reach, random_mean_reach),
    )
    reporter.check(
        "hub reach advantage appears in at least 9 of 12 seeds",
        hub_advantage_count >= 9,
        hub_advantage_count,
    )

    control_damage_ok = all(
        row["trajectory"][-1] < row["trajectory"][3] for row in control_rows
    )
    reporter.check("control retains post-scandal damage at tick 30", control_damage_ok)

    final_gains: list[float] = []
    auc_gains: list[float] = []
    for row in treatment_rows:
        control = by_seed_exp[(row["seed"], CONTROL_EXP_ID)]
        final_gains.append(row["final_trust"] - control["final_trust"])
        auc_gains.append(row["post_crisis_auc"] - control["post_crisis_auc"])
    min_final_gain = min(final_gains)
    min_auc_gain = min(auc_gains)
    reporter.check("all treatment final trust gains are positive", min_final_gain > 0.0, min_final_gain)
    reporter.check(
        "all treatment post-crisis AUC gains are positive",
        min_auc_gain > 0.0,
        min_auc_gain,
    )

    timing_early_diffs: list[float] = []
    timing_final_diffs: list[float] = []
    for content in CONTENT_LEVELS:
        for channel in CHANNEL_LEVELS:
            immediate = [
                row
                for row in treatment_rows
                if row["content_factor"] == content
                and row["channel_factor"] == channel
                and row["timing_factor"] == "immediate"
            ]
            delayed = [
                row
                for row in treatment_rows
                if row["content_factor"] == content
                and row["channel_factor"] == channel
                and row["timing_factor"] == "delayed"
            ]
            early_diff = _mean([row["early_auc"] for row in immediate]) - _mean(
                [row["early_auc"] for row in delayed]
            )
            final_diff = _mean([row["final_trust"] for row in immediate]) - _mean(
                [row["final_trust"] for row in delayed]
            )
            timing_early_diffs.append(early_diff)
            timing_final_diffs.append(final_diff)
    min_timing_early_diff = min(timing_early_diffs)
    mean_timing_final_diff = _mean(timing_final_diffs)
    reporter.check(
        "immediate early AUC exceeds delayed for every matched cell",
        min_timing_early_diff > 0.0,
        min_timing_early_diff,
    )
    if mean_timing_final_diff < 0.0:
        reporter.warn("final-horizon timing reversal", mean_timing_final_diff)

    content_contrasts: list[float] = []
    for channel in CHANNEL_LEVELS:
        for timing in STRATEGY_TIMING_LEVELS:
            rational = [
                row["final_trust"]
                for row in treatment_rows
                if row["content_factor"] == "rational-evidence"
                and row["channel_factor"] == channel
                and row["timing_factor"] == timing
            ]
            empathy = [
                row["final_trust"]
                for row in treatment_rows
                if row["content_factor"] == "emotional-empathy"
                and row["channel_factor"] == channel
                and row["timing_factor"] == timing
            ]
            content_contrasts.append(abs(_mean(empathy) - _mean(rational)))
    min_content_contrast = min(content_contrasts)
    reporter.check(
        "content pathway produces nonzero final-trust contrast",
        min_content_contrast > CONTENT_CONTRAST_TOLERANCE,
        min_content_contrast,
    )

    pbc_invariant = all(row["pbc_invariant"] for row in rows)
    reporter.check("PBC invariant under scandal and clarification signals", pbc_invariant)

    clipping_count = sum(row["clipping_count"] for row in rows)
    reporter.check("trust clipping count is zero", clipping_count == 0, clipping_count)

    first = _diagnostic_run(treatments[0], DIAGNOSTIC_SEEDS[0])
    second = _diagnostic_run(treatments[0], DIAGNOSTIC_SEEDS[0])
    reporter.check("same seed and condition are exactly reproducible", first == second)

    source = inspect.getsource(mechanism.update_psychological_state).lower()
    forbidden_labels = ("rational-evidence", "emotional-empathy", "hub", "random")
    reporter.check(
        "state transition source does not contain treatment labels",
        not any(label in source for label in forbidden_labels),
    )

    metrics = {
        "matrix_conditions": len(matrix),
        "simulation_rows": len(rows),
        "hub_mean_reach": hub_mean_reach,
        "random_mean_reach": random_mean_reach,
        "hub_advantage_seed_count": hub_advantage_count,
        "min_treatment_final_trust_gain": min_final_gain,
        "min_treatment_post_crisis_auc_gain": min_auc_gain,
        "min_immediate_minus_delayed_early_auc": min_timing_early_diff,
        "mean_immediate_minus_delayed_final_trust": mean_timing_final_diff,
        "min_abs_content_final_trust_contrast": min_content_contrast,
        "trust_clipping_count": clipping_count,
        "pbc_invariant": pbc_invariant,
    }

    print("\nTASK_005 DETERMINISTIC FULL-MATRIX SANITY V2")
    print("Passed:", reporter.passed)
    print("Failed:", reporter.failed)
    print("Warned:", reporter.warned)

    if reporter.failed == 0:
        RESULT_PATH.write_text(
            json.dumps(_result_record(metrics, True, 0), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    elif RESULT_PATH.exists():
        RESULT_PATH.unlink()

    return 1 if reporter.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
