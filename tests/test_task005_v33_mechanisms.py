"""Zero-API regression tests for the parallel TASK_005 v3.3 mechanisms."""
from __future__ import annotations

import networkx as nx

from clarification_diffusion_v33 import (
    select_paid_amplification_nodes_v33,
    select_public_exposure_nodes_v33,
)
from mechanism_v2 import update_psychological_state
from mechanism_v33 import (
    TrustDynamicsV33Parameters,
    update_psychological_state_v33,
)
from purchase_mechanism_v31 import DemandParameters, MicroBuyerProfile
from purchase_mechanism_v33 import (
    initial_renewal_state,
    next_renewal_interval,
    update_loyalty_v33,
)


def _shared_transition_kwargs():
    return dict(
        baseline_trust=6.5,
        previous_trust=5.8,
        attitude_att=0.62,
        subjective_norm_sn=0.50,
        pbc=0.50,
        crisis_memory=1.10,
        repair_memory=0.35,
        valence=0.40,
        arousal=0.55,
        credibility=0.80,
        evidence_strength=0.75,
        topic_relevance=0.90,
        had_observation=True,
        social_observation_count=0,
        perceived_empathy=0.45,
        enterprise_clarification_observed=True,
    )


def test_v33_legacy_profile_recovers_v32_trust_transition():
    kwargs = _shared_transition_kwargs()
    legacy = update_psychological_state(**kwargs)
    v33 = update_psychological_state_v33(
        **kwargs,
        hypocrisy_perceived=False,
        parameters=TrustDynamicsV33Parameters.legacy_v32(),
    )
    assert abs(v33["trust_final"] - legacy["trust_final"]) < 1e-12
    assert abs(v33["crisis_memory"] - legacy["crisis_memory"]) < 1e-12
    assert abs(v33["repair_memory"] - legacy["repair_memory"]) < 1e-12


def test_v33_quiet_adjustment_is_gradual_not_instantaneous():
    params = TrustDynamicsV33Parameters(
        crisis_retention=0.98,
        repair_retention=0.96,
        event_adjustment=0.80,
        quiet_adjustment=0.18,
        repair_saturation=0.30,
        hypocrisy_weight=0.25,
    )
    row = update_psychological_state_v33(
        baseline_trust=6.5,
        previous_trust=5.0,
        attitude_att=0.5,
        subjective_norm_sn=0.5,
        pbc=0.5,
        crisis_memory=1.0,
        repair_memory=0.0,
        valence=0.0,
        arousal=0.0,
        credibility=0.5,
        evidence_strength=0.0,
        topic_relevance=0.0,
        had_observation=False,
        social_observation_count=0,
        parameters=params,
    )
    target = row["trust_target_after_signal"]
    assert row["trust_final"] != target
    assert min(5.0, target) <= row["trust_final"] <= max(5.0, target)


def test_hypocrisy_amplifies_negative_crisis_increment():
    common = dict(
        baseline_trust=6.5,
        previous_trust=6.0,
        attitude_att=0.6,
        subjective_norm_sn=0.5,
        pbc=0.5,
        crisis_memory=0.0,
        repair_memory=0.0,
        valence=-0.7,
        arousal=0.8,
        credibility=0.8,
        evidence_strength=0.2,
        topic_relevance=0.9,
        had_observation=True,
        social_observation_count=0,
    )
    no_h = update_psychological_state_v33(
        **common, hypocrisy_perceived=False
    )
    yes_h = update_psychological_state_v33(
        **common, hypocrisy_perceived=True
    )
    assert yes_h["crisis_increment"] > no_h["crisis_increment"]


def test_public_exposure_is_reproducible_bernoulli_selection():
    nodes = [f"A{i}" for i in range(20)]
    a = select_public_exposure_nodes_v33(nodes, 12345, rate=0.25)
    b = select_public_exposure_nodes_v33(nodes, 12345, rate=0.25)
    assert a == b
    assert set(a).issubset(set(nodes))


def test_paid_amplification_is_reproducible_subset_of_actual_successors():
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("H1", "A"),
            ("H1", "B"),
            ("H2", "B"),
            ("H2", "C"),
            ("X", "Y"),
        ]
    )
    a = select_paid_amplification_nodes_v33(
        graph, ["H1", "H2"], base_seed=77, edge_probability=0.55
    )
    b = select_paid_amplification_nodes_v33(
        graph, ["H1", "H2"], base_seed=77, edge_probability=0.55
    )
    assert a == b
    assert set(a).issubset({"A", "B", "C"})


def test_renewal_intervals_are_reproducible_and_within_persona_range():
    allowed = (7, 8, 9, 10)
    seq1 = [
        next_renewal_interval(
            seed=100,
            buyer_id="Consumer_001::M000",
            purchase_index=i,
            allowed_intervals=allowed,
        )
        for i in range(1, 8)
    ]
    seq2 = [
        next_renewal_interval(
            seed=100,
            buyer_id="Consumer_001::M000",
            purchase_index=i,
            allowed_intervals=allowed,
        )
        for i in range(1, 8)
    ]
    assert seq1 == seq2
    assert set(seq1).issubset(set(allowed))


def test_loyalty_ewma_remains_bounded_without_clipping_pressure():
    loyalty = 0.0
    for _ in range(20):
        loyalty = update_loyalty_v33(
            previous_loyalty=loyalty,
            focal_brand_chosen=True,
            retention=0.85,
        )
        assert 0.0 <= loyalty <= 1.0
    assert loyalty < 1.0


def test_initial_renewal_state_preserves_existing_phase():
    profile = MicroBuyerProfile(
        buyer_id="B",
        archetype_id="A",
        micro_index=0,
        opportunity_interval=8,
        opportunity_phase=3,
        preference_offset=0.0,
        baseline_pbc=0.5,
        initial_loyalty=0.2,
    )
    state = initial_renewal_state(profile)
    assert state.next_opportunity_tick == 4
    assert state.purchase_index == 0
    assert state.loyalty == 0.2
