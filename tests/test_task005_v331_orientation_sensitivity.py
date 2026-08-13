"""Zero-API tests for v3.3.1 equal-degree edge-orientation robustness."""
from __future__ import annotations

import networkx as nx

from greenconsumer_v33.network_variants import (
    BASELINE_NETWORK_HASH,
    NetworkVariantV331Spec,
    TIE_RULES,
    _orient_like_v331,
    build_directed_network_variant,
)
from greenconsumer_v33.orientation_sensitivity import profile_table
from simulation_core import compute_network_hash


def test_orientation_profile_grid_is_pre_specified():
    df = profile_table()
    assert len(df) == 45
    assert set(df["tie_rule"]) == set(TIE_RULES)
    assert set(df["topology"]) == {"ba", "ws", "community"}
    assert df.groupby(["topology", "network_seed"]).size().eq(3).all()


def test_legacy_baseline_hash_is_unchanged():
    ids = [f"Consumer_{i:03d}" for i in range(20)]
    graph, _ = build_directed_network_variant(
        ids,
        NetworkVariantV331Spec(
            topology="ba",
            network_seed=2026081501,
            tie_rule="legacy_first_endpoint",
        ),
    )
    assert compute_network_hash(graph) == BASELINE_NETWORK_HASH


def test_only_equal_degree_edges_change_between_tie_rules():
    # Deliberately include both equal-degree and unequal-degree edges.
    g = nx.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 3), (1, 4), (2, 4)])
    degrees = dict(g.degree())
    oriented = {
        rule: _orient_like_v331(g, tie_rule=rule, network_seed=123)[0]
        for rule in TIE_RULES
    }
    legacy = {tuple(sorted((u, v))): (u, v) for u, v in oriented["legacy_first_endpoint"].edges()}
    for rule, graph in oriented.items():
        current = {tuple(sorted((u, v))): (u, v) for u, v in graph.edges()}
        assert set(current) == set(legacy)
        for pair, direction in legacy.items():
            if degrees[pair[0]] != degrees[pair[1]]:
                assert current[pair] == direction


def test_hash_balanced_is_independent_of_undirected_edge_insertion_order():
    edges = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")]
    g1 = nx.Graph()
    g1.add_edges_from(edges)
    g2 = nx.Graph()
    g2.add_edges_from(reversed(edges))
    d1, _ = _orient_like_v331(g1, tie_rule="hash_balanced", network_seed=77)
    d2, _ = _orient_like_v331(g2, tie_rule="hash_balanced", network_seed=77)
    assert set(d1.edges()) == set(d2.edges())
