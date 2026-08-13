"""Pure network builders for TASK_005 v3.3.1 robustness checks.

The production baseline remains the existing directed BA graph. This module is
used only by explicitly labelled sensitivity suites. Fixed-N topology checks use
N=20 for BA/WS/community; network-size checks may use BA at N=20/40/80 while
preserving m=2.  Equal-degree edge orientation is now explicit so the legacy
first-endpoint branch can be falsification-tested without changing the frozen
baseline default.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

import networkx as nx


TOPOLOGIES = ("ba", "ws", "community")
SIZE_ROBUSTNESS_N = (20, 40, 80)
TIE_RULES = ("legacy_first_endpoint", "reverse_first_endpoint", "hash_balanced")
BASELINE_NETWORK_HASH = "886be697894ff8f79c4e72be4b778978f9c40390ee5a15dcb1e09b73040281ac"


@dataclass(frozen=True)
class NetworkVariantV331Spec:
    topology: str
    network_seed: int
    ba_m: int = 2
    ws_k: int = 4
    ws_beta: float = 0.10
    community_blocks: int = 4
    community_block_size: int = 5
    community_p_in: float = 0.65
    community_p_out: float = 0.08
    tie_rule: str = "legacy_first_endpoint"

    def validate(self, n: int) -> None:
        n = int(n)
        if self.topology not in TOPOLOGIES:
            raise ValueError(f"unknown topology: {self.topology}")
        if self.tie_rule not in TIE_RULES:
            raise ValueError(f"tie_rule must be one of {TIE_RULES}; got {self.tie_rule!r}")
        if self.topology == "ba":
            if n not in SIZE_ROBUSTNESS_N:
                raise ValueError(
                    f"v3.3.1 BA robustness supports N in {SIZE_ROBUSTNESS_N}; got {n}"
                )
            if not 1 <= int(self.ba_m) < n:
                raise ValueError("ba_m must satisfy 1 <= m < n")
            return

        # WS/community are currently fixed-N topology robustness only. Keeping
        # this guard prevents accidental topology×size expansion before it is
        # separately pre-registered.
        if n != 20:
            raise ValueError("v3.3.1 WS/community topology robustness currently requires N=20")
        if self.topology == "ws":
            if int(self.ws_k) <= 0 or int(self.ws_k) >= n or int(self.ws_k) % 2:
                raise ValueError("ws_k must be positive, even, and < n")
            if not 0.0 <= float(self.ws_beta) <= 1.0:
                raise ValueError("ws_beta must be in [0,1]")
        if self.topology == "community":
            if int(self.community_blocks) * int(self.community_block_size) != n:
                raise ValueError("community blocks × block size must equal n")
            for value in (self.community_p_in, self.community_p_out):
                if not 0.0 <= float(value) <= 1.0:
                    raise ValueError("community probabilities must be in [0,1]")
            if float(self.community_p_in) <= float(self.community_p_out):
                raise ValueError("community_p_in must exceed community_p_out")

    def audit_payload(self) -> dict:
        return {
            "topology": self.topology,
            "network_seed": int(self.network_seed),
            "ba_m": int(self.ba_m),
            "ws_k": int(self.ws_k),
            "ws_beta": float(self.ws_beta),
            "community_blocks": int(self.community_blocks),
            "community_block_size": int(self.community_block_size),
            "community_p_in": float(self.community_p_in),
            "community_p_out": float(self.community_p_out),
            "tie_rule": self.tie_rule,
            "empirically_calibrated": False,
            "role": "pre-specified network robustness",
        }


def _undirected_graph(n: int, spec: NetworkVariantV331Spec) -> nx.Graph:
    spec.validate(n)
    seed = int(spec.network_seed)
    if spec.topology == "ba":
        return nx.barabasi_albert_graph(n, m=int(spec.ba_m), seed=seed)
    if spec.topology == "ws":
        return nx.watts_strogatz_graph(
            n,
            k=int(spec.ws_k),
            p=float(spec.ws_beta),
            seed=seed,
        )

    sizes = [int(spec.community_block_size)] * int(spec.community_blocks)
    probs = [
        [
            float(spec.community_p_in) if i == j else float(spec.community_p_out)
            for j in range(int(spec.community_blocks))
        ]
        for i in range(int(spec.community_blocks))
    ]
    return nx.stochastic_block_model(
        sizes,
        probs,
        seed=seed,
        selfloops=False,
        sparse=True,
    )


def _hash_tie_direction(u: str, v: str, seed: int) -> tuple[str, str]:
    """Choose one deterministic tie direction independent of edge iteration order."""

    left, right = sorted((str(u), str(v)))
    payload = f"{int(seed)}|{left}|{right}|equal-degree-tie".encode("utf-8")
    choose_left = hashlib.sha256(payload).digest()[0] % 2 == 0
    return (left, right) if choose_left else (right, left)


def _orient_like_v331(
    undirected: nx.Graph,
    *,
    tie_rule: str = "legacy_first_endpoint",
    network_seed: int = 0,
) -> tuple[nx.DiGraph, dict]:
    if tie_rule not in TIE_RULES:
        raise ValueError(f"unknown tie_rule: {tie_rule}")

    degrees = dict(undirected.degree())
    directed = nx.DiGraph()
    directed.add_nodes_from(undirected.nodes())
    ties = 0
    for u, v in undirected.edges():
        if degrees[u] > degrees[v]:
            directed.add_edge(u, v)
        elif degrees[v] > degrees[u]:
            directed.add_edge(v, u)
        else:
            ties += 1
            if tie_rule == "legacy_first_endpoint":
                directed.add_edge(u, v)
            elif tie_rule == "reverse_first_endpoint":
                directed.add_edge(v, u)
            else:
                source, target = _hash_tie_direction(u, v, int(network_seed))
                directed.add_edge(source, target)

    edge_count = int(undirected.number_of_edges())
    return directed, {
        "undirected_edge_count": edge_count,
        "equal_degree_tie_edges": int(ties),
        "equal_degree_tie_edge_share": float(ties / edge_count) if edge_count else 0.0,
        "tie_rule": tie_rule,
        "direction_rule": (
            "higher-undirected-degree-to-lower; equal-degree rule=" + tie_rule
        ),
    }


def build_directed_network_variant(
    agent_ids: list[str],
    spec: NetworkVariantV331Spec,
) -> tuple[nx.DiGraph, dict]:
    """Build one directed robustness topology and return audit metadata."""

    ids = [str(x) for x in agent_ids]
    n = len(ids)
    spec.validate(n)
    undirected = _undirected_graph(n, spec)
    mapping = {i: ids[i] for i in range(n)}
    undirected = nx.relabel_nodes(undirected, mapping)
    directed, orientation = _orient_like_v331(
        undirected,
        tie_rule=spec.tie_rule,
        network_seed=int(spec.network_seed),
    )

    audit = {
        **spec.audit_payload(),
        **orientation,
        "n": n,
        "network_type": {
            "ba": "barabasi_albert_v331_variant",
            "ws": "watts_strogatz_v331_variant",
            "community": "stochastic_block_v331_variant",
        }[spec.topology],
        "undirected_connected": bool(nx.is_connected(undirected)) if n else True,
        "undirected_density": float(nx.density(undirected)) if n > 1 else 0.0,
        "undirected_average_clustering": float(nx.average_clustering(undirected)) if n else 0.0,
    }
    if n and nx.is_connected(undirected):
        audit["undirected_average_shortest_path_length"] = float(
            nx.average_shortest_path_length(undirected)
        )
    else:
        audit["undirected_average_shortest_path_length"] = None
    return directed, audit
