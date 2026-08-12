#!/usr/bin/env python3
"""诊断 GreenConsumer 旧实验中 Reflect 状态残留问题。"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import networkx as nx
import pandas as pd


def build_directed_ba(n: int, m: int, seed: int) -> nx.DiGraph:
    undirected = nx.barabasi_albert_graph(n, m=m, seed=seed)
    mapping = {i: f"Consumer_{i:03d}" for i in range(n)}
    undirected = nx.relabel_nodes(undirected, mapping)
    degrees = dict(undirected.degree())
    graph = nx.DiGraph()
    graph.add_nodes_from(undirected.nodes())
    for u, v in undirected.edges():
        if degrees[u] >= degrees[v]:
            graph.add_edge(u, v)
        else:
            graph.add_edge(v, u)
    return graph


def select_targets(graph: nx.DiGraph, channel: str, k: int, seed: int) -> list[str]:
    if channel == "hub":
        return [
            node
            for node, _ in sorted(
                graph.out_degree(),
                key=lambda item: item[1],
                reverse=True,
            )[:k]
        ]
    rng = random.Random(seed + 7777)
    return rng.sample(list(graph.nodes()), k)


def longest_zero_run(values: list[int]) -> int:
    best = current = 0
    for value in values:
        if value == 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-records", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--num-agents", type=int, default=20)
    parser.add_argument("--ba-m", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--budget-k", type=int, default=3)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    agents = pd.read_csv(args.agent_records)
    summary = pd.read_csv(args.summary)
    graph = build_directed_ba(args.num_agents, args.ba_m, args.seed)

    target_map = {
        channel: select_targets(graph, channel, args.budget_k, args.seed)
        for channel in ("hub", "random")
    }

    records = []
    treatment_rows = summary[summary["timing_factor"] != "no-clarification"]
    for _, row in treatment_rows.iterrows():
        timing = row["timing_factor"]
        clarification_tick = 6 if timing == "immediate" else 10
        targets = target_map[row["channel_factor"]]

        for agent_id in targets:
            series = agents[
                (agents["exp_id"] == row["exp_id"])
                & (agents["agent_id"] == agent_id)
                & (agents["tick"] >= clarification_tick)
            ].sort_values("tick")
            after = series[series["tick"] > clarification_tick]
            clarification_row = series[series["tick"] == clarification_tick]
            clarification_reason = (
                str(clarification_row.iloc[0]["reasoning"])
                if not clarification_row.empty
                else ""
            )
            repeated_reason_days = int(
                (
                    after["reasoning"].fillna("").astype(str)
                    == clarification_reason
                ).sum()
            )

            records.append(
                {
                    "exp_id": row["exp_id"],
                    "content_factor": row["content_factor"],
                    "channel_factor": row["channel_factor"],
                    "timing_factor": timing,
                    "clarification_tick": clarification_tick,
                    "agent_id": agent_id,
                    "out_degree": int(graph.out_degree(agent_id)),
                    "ticks_after_clarification": int(len(after)),
                    "longest_zero_quiet_run_after": longest_zero_run(
                        after["quiet_ticks"].astype(int).tolist()
                    ),
                    "all_post_clarification_quiet_ticks_zero": bool(
                        not after.empty and (after["quiet_ticks"] == 0).all()
                    ),
                    "repeated_clarification_reason_days": repeated_reason_days,
                    "max_quiet_ticks_after": int(after["quiet_ticks"].max())
                    if not after.empty
                    else 0,
                }
            )

    diagnosis = pd.DataFrame(records)
    diagnosis_path = output_dir / "state_residue_diagnosis.csv"
    diagnosis.to_csv(diagnosis_path, index=False, encoding="utf-8-sig")

    summary_data = {
        "treatment_conditions": int(treatment_rows.shape[0]),
        "target_condition_units": int(diagnosis.shape[0]),
        "targets_stuck_at_zero_for_all_remaining_ticks": int(
            diagnosis["all_post_clarification_quiet_ticks_zero"].sum()
        ),
        "total_repeated_clarification_reason_days": int(
            diagnosis["repeated_clarification_reason_days"].sum()
        ),
        "median_longest_zero_quiet_run": float(
            diagnosis["longest_zero_quiet_run_after"].median()
        ),
        "max_longest_zero_quiet_run": int(
            diagnosis["longest_zero_quiet_run_after"].max()
        ),
        "hub_targets": target_map["hub"],
        "random_targets": target_map["random"],
    }
    with (output_dir / "state_residue_summary.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(summary_data, file, ensure_ascii=False, indent=2)

    print(json.dumps(summary_data, ensure_ascii=False, indent=2))
    print(f"CSV: {diagnosis_path}")


if __name__ == "__main__":
    main()
