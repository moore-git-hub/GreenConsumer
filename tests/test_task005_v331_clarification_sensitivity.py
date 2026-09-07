"""Zero-API tests for v3.3.1 paid-reach sensitivity design."""
from __future__ import annotations

import networkx as nx
import pytest

from clarification_diffusion_v33 import (
    DEFAULT_CLARIFICATION_PARAMETERS,
    ClarificationDiffusionV33Parameters,
    clarification_parameters_audit_payload,
    select_paid_amplification_nodes_v33,
)
from greenconsumer_v33.clarification_sensitivity import (
    BASELINE_LAG,
    BASELINE_PROBABILITY,
    DELIVERY_LAGS,
    EDGE_PROBABILITIES,
    profile_table,
)


def test_frozen_clarification_baseline_is_055_lag1():
    assert DEFAULT_CLARIFICATION_PARAMETERS.paid_edge_probability == pytest.approx(0.55)
    assert DEFAULT_CLARIFICATION_PARAMETERS.paid_delivery_lag == 1
    assert BASELINE_PROBABILITY == pytest.approx(0.55)
    assert BASELINE_LAG == 1


def test_parameter_validation_and_audit_payload():
    p = ClarificationDiffusionV33Parameters(0.30, 2)
    audit = clarification_parameters_audit_payload(p)
    assert audit["paid_edge_probability"] == pytest.approx(0.30)
    assert audit["paid_delivery_lag"] == 2
    assert audit["empirically_calibrated"] is False

    with pytest.raises(ValueError):
        ClarificationDiffusionV33Parameters(-0.01, 1)
    with pytest.raises(ValueError):
        ClarificationDiffusionV33Parameters(1.01, 1)
    with pytest.raises(ValueError):
        ClarificationDiffusionV33Parameters(0.55, -1)
    with pytest.raises(ValueError):
        ClarificationDiffusionV33Parameters(0.55, 1.5)


def test_pre_specified_grid_is_complete_3x3():
    table = profile_table()
    assert tuple(EDGE_PROBABILITIES) == (0.30, 0.55, 0.80)
    assert tuple(DELIVERY_LAGS) == (0, 1, 2)
    assert len(table) == 9
    assert table["profile_id"].nunique() == 9
    baseline = table[table["profile_role"] == "frozen-baseline"]
    assert len(baseline) == 1
    assert baseline.iloc[0]["paid_edge_probability"] == pytest.approx(0.55)
    assert int(baseline.iloc[0]["paid_delivery_lag"]) == 1


def test_paid_recipient_set_is_monotone_in_probability():
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("A", "B"),
            ("A", "C"),
            ("A", "D"),
            ("E", "B"),
            ("E", "F"),
        ]
    )
    seed_nodes = ["A", "E"]
    reached = []
    for probability in EDGE_PROBABILITIES:
        reached.append(
            set(
                select_paid_amplification_nodes_v33(
                    graph,
                    seed_nodes,
                    base_seed=2026081501,
                    edge_probability=probability,
                )
            )
        )
    assert reached[0].issubset(reached[1])
    assert reached[1].issubset(reached[2])
