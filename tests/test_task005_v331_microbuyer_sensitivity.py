from __future__ import annotations

import ast
import inspect

import pandas as pd

from greenconsumer_v33 import microbuyer_sensitivity as ms


def test_microbuyer_profile_grid_is_pre_specified():
    df = ms.profile_table()
    assert len(df) == 15
    assert set(df["network_seed"]) == set(ms.NETWORK_SEEDS)
    assert set(df["micro_buyers_per_cognitive_agent"]) == {10, 25, 50}
    counts = df.groupby("network_seed").size().to_dict()
    assert set(counts.values()) == {3}
    assert ms.BASELINE_MICROBUYERS == 25


def test_buyer_count_integrity_for_all_resolutions():
    for m in ms.MICROBUYER_COUNTS:
        ok, detail = ms._buyer_count_integrity(m, 2026081701)
        assert ok, detail
        assert str(20 * m) in detail


def test_stability_table_preserves_sign_and_baseline():
    rows = []
    for seed in ms.NETWORK_SEEDS:
        for eid, vals in (
            (ms.DOWNSTREAM_ESTIMANDS[0], {10: 0.010, 25: 0.011, 50: 0.012}),
            (ms.DOWNSTREAM_ESTIMANDS[1], {10: 0.030, 25: 0.029, 50: 0.028}),
        ):
            for m, value in vals.items():
                rows.append(
                    {
                        "network_seed": seed,
                        "micro_buyers_per_cognitive_agent": m,
                        "estimand_id": eid,
                        "value": value,
                    }
                )
    out = ms._stability_table(pd.DataFrame(rows))
    assert len(out) == 10
    assert out["sign_stable_across_m"].all()
    assert (out[out["estimand_id"] == ms.DOWNSTREAM_ESTIMANDS[0]]["m25_baseline"] == 0.011).all()


def _imported_modules(module) -> set[str]:
    """Return actual Python import targets, ignoring comments/docstrings/text."""

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
    return imported


def test_microbuyer_suite_is_demand_only_no_heavy_runtime_imports():
    imported = _imported_modules(ms)
    forbidden_roots = {
        "simulation_core",
        "agentkernel_standalone",
        "AgentKernel",
        "greenconsumer_v33.runner",
        "greenconsumer_v32.routers",
    }
    assert forbidden_roots.isdisjoint(imported), sorted(imported & forbidden_roots)

    # Also guard against importing nested heavy modules under those roots.
    forbidden_prefixes = (
        "simulation_core.",
        "agentkernel_standalone.",
        "AgentKernel.",
        "greenconsumer_v33.runner.",
        "greenconsumer_v32.routers.",
    )
    assert not any(
        name.startswith(forbidden_prefixes)
        for name in imported
    ), sorted(imported)
