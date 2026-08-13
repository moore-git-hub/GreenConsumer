"""Zero-API tests for v3.3.1 network-size × budget robustness."""
from __future__ import annotations

from collections import Counter

import pandas as pd

from fmcg_scenario_v32 import ENGINEERING_PERSONAS
from greenconsumer_v33.demand import simulate_demand
from greenconsumer_v33.network_size_sensitivity import (
    NETWORK_SEEDS,
    profile_table,
    proportional_k,
)
from greenconsumer_v33.network_variants import NetworkVariantV331Spec, build_directed_network_variant
from greenconsumer_v33.persona_panels import (
    build_nested_persona_panel,
    persona_tuple,
)


def test_nested_persona_panels_preserve_baseline_and_are_unique():
    p20 = build_nested_persona_panel(20)
    p40 = build_nested_persona_panel(40)
    p80 = build_nested_persona_panel(80)

    assert p20 == tuple(ENGINEERING_PERSONAS)
    assert p40[:20] == p20
    assert p80[:40] == p40
    assert len({persona_tuple(p) for p in p40}) == 40
    assert len({persona_tuple(p) for p in p80}) == 80


def test_persona_marginals_scale_as_integer_multiples_of_n20():
    base = build_nested_persona_panel(20)
    for size, multiplier in ((40, 2), (80, 4)):
        panel = build_nested_persona_panel(size)
        for index in range(6):
            baseline_counts = Counter(persona_tuple(p)[index] for p in base)
            observed_counts = Counter(persona_tuple(p)[index] for p in panel)
            assert observed_counts == Counter({k: v * multiplier for k, v in baseline_counts.items()})


def test_size_budget_profile_grid_is_pre_specified_and_deduplicated():
    df = profile_table()
    assert len(df) == 25
    assert set(df["network_seed"]) == set(NETWORK_SEEDS)
    assert proportional_k(20) == 3
    assert proportional_k(40) == 6
    assert proportional_k(80) == 12
    for seed in NETWORK_SEEDS:
        part = df[df["network_seed"] == seed]
        assert set(zip(part["num_agents"], part["budget_k"])) == {
            (20, 3), (40, 3), (40, 6), (80, 3), (80, 12)
        }


def test_ba_variant_supports_pre_registered_network_sizes():
    for n in (20, 40, 80):
        ids = [f"Consumer_{i:03d}" for i in range(n)]
        spec = NetworkVariantV331Spec(topology="ba", network_seed=2026081501, ba_m=2)
        graph, audit = build_directed_network_variant(ids, spec)
        assert graph.number_of_nodes() == n
        assert audit["n"] == n
        assert audit["topology"] == "ba"
        assert audit["ba_m"] == 2


def _cognitive_rows(panel, end_tick=3):
    rows = []
    for tick in range(1, end_tick + 1):
        for persona in panel:
            rows.append({
                "exp_id": "NoClarification-Control",
                "tick": tick,
                "agent_id": persona.agent_id,
                "attitude_att": 0.55,
                "subjective_norm_after": 0.50,
                "trust_final": 5.50,
            })
    return rows


def test_demand_accepts_expanded_persona_panel_without_falling_back_to_n20():
    panel = build_nested_persona_panel(40)
    rows, curves = simulate_demand(
        _cognitive_rows(panel),
        support_present=False,
        demand_seed=2026081701,
        micro_buyers=1,
        personas=panel,
    )
    assert len(curves) == 3
    assert {int(row["cognitive_agents"]) for row in curves} == {40}
    assert {int(row["micro_buyers_per_cognitive_agent"]) for row in curves} == {1}
    assert all(str(row["agent_id"]).startswith("Consumer_") for row in rows)
