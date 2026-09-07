"""Zero-API tests for v3.3.1 thesis-output helpers."""
from __future__ import annotations

import pandas as pd

from greenconsumer_v33.thesis_outputs import _network_metrics, _social_broadcasts


def test_network_metrics_reconstruct_simple_directed_graph():
    nodes = pd.DataFrame([
        {"agent_id": "A", "out_degree": 1, "in_degree": 0},
        {"agent_id": "B", "out_degree": 1, "in_degree": 1},
        {"agent_id": "C", "out_degree": 0, "in_degree": 1},
    ])
    edges = pd.DataFrame([
        {"source_agent_id": "A", "target_agent_id": "B", "is_directed": True},
        {"source_agent_id": "B", "target_agent_id": "C", "is_directed": True},
    ])
    out = _network_metrics(nodes, edges)
    assert int(out.loc[0, "nodes"]) == 3
    assert int(out.loc[0, "directed_edges"]) == 2
    assert int(out.loc[0, "max_out_degree"]) == 1


def test_social_broadcast_reconstruction_uses_actual_outgoing_edges_only():
    agent = pd.DataFrame([
        {
            "exp_id": "X",
            "tick": 5,
            "agent_id": "A",
            "is_posting": True,
            "post_content": "hello",
        },
        {
            "exp_id": "X",
            "tick": 5,
            "agent_id": "B",
            "is_posting": False,
            "post_content": "",
        },
    ])
    edges = pd.DataFrame([
        {"source_agent_id": "A", "target_agent_id": "B", "is_directed": True},
        {"source_agent_id": "A", "target_agent_id": "C", "is_directed": True},
        {"source_agent_id": "B", "target_agent_id": "C", "is_directed": True},
    ])
    out = _social_broadcasts(agent, edges)
    assert len(out) == 2
    assert set(out["recipient_agent_id"]) == {"B", "C"}
    assert set(out["sender_agent_id"]) == {"A"}
