"""Zero-API tests for v3.3.1 fixed-N topology robustness."""
from __future__ import annotations

import hashlib
import json

import networkx as nx

from greenconsumer_v33.network_variants import (
    BASELINE_NETWORK_HASH,
    NetworkVariantV331Spec,
    build_directed_network_variant,
)
from greenconsumer_v33.topology_sensitivity import NETWORK_SEEDS, profile_table


def _agent_ids():
    return [f"Consumer_{i:03d}" for i in range(20)]


def _hash(graph: nx.DiGraph) -> str:
    nodes = sorted(str(n) for n in graph.nodes())
    edges = sorted([str(u), str(v)] for u, v in graph.edges())
    payload = json.dumps(
        {"nodes": nodes, "edges": edges},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_profile_grid_is_three_topologies_times_five_network_seeds():
    profiles = profile_table()
    assert len(profiles) == 15
    assert set(profiles["topology"]) == {"ba", "ws", "community"}
    assert set(profiles["network_seed"]) == set(NETWORK_SEEDS)
    assert (profiles["profile_role"] == "frozen-baseline-network").sum() == 1


def test_ba_baseline_variant_exactly_reproduces_frozen_network_hash():
    graph, audit = build_directed_network_variant(
        _agent_ids(),
        NetworkVariantV331Spec(topology="ba", network_seed=2026081501),
    )
    assert graph.number_of_nodes() == 20
    assert graph.number_of_edges() == 36
    assert _hash(graph) == BASELINE_NETWORK_HASH
    assert audit["network_type"] == "barabasi_albert_v331_variant"


def test_all_pre_specified_network_variants_are_deterministic_and_keep_node_set():
    for topology in ("ba", "ws", "community"):
        for seed in NETWORK_SEEDS:
            spec = NetworkVariantV331Spec(topology=topology, network_seed=seed)
            left, left_audit = build_directed_network_variant(_agent_ids(), spec)
            right, right_audit = build_directed_network_variant(_agent_ids(), spec)
            assert _hash(left) == _hash(right)
            assert set(left.nodes()) == set(_agent_ids())
            assert left_audit == right_audit


def test_pre_specified_ws_and_community_realizations_are_connected():
    for topology in ("ws", "community"):
        for seed in NETWORK_SEEDS:
            graph, audit = build_directed_network_variant(
                _agent_ids(),
                NetworkVariantV331Spec(topology=topology, network_seed=seed),
            )
            assert audit["undirected_connected"] is True
            assert nx.is_connected(graph.to_undirected())


def test_topology_parameters_match_pre_registered_comparators():
    ws = NetworkVariantV331Spec(topology="ws", network_seed=1)
    assert ws.ws_k == 4
    assert ws.ws_beta == 0.10
    community = NetworkVariantV331Spec(topology="community", network_seed=1)
    assert community.community_blocks == 4
    assert community.community_block_size == 5
    assert community.community_p_in == 0.65
    assert community.community_p_out == 0.08
