"""Zero-API tests for horizon-aware v3.3.1 thesis outputs."""
from __future__ import annotations

import pandas as pd
import pytest

from greenconsumer_v33.thesis_outputs_finite_horizon import (
    _resolve_end_tick,
    _time_checkpoint_table,
)


def test_resolve_end_tick_matches_run_provenance():
    agent = pd.DataFrame(
        [
            {"exp_id": "NoClarification-Control", "agent_id": "A", "tick": tick}
            for tick in range(1, 36)
        ]
    )
    data = {"summary": {"total_ticks": 35}, "agent": agent}
    assert _resolve_end_tick(data) == 35


def test_resolve_end_tick_rejects_silent_horizon_mismatch():
    agent = pd.DataFrame(
        [
            {"exp_id": "NoClarification-Control", "agent_id": "A", "tick": tick}
            for tick in range(1, 36)
        ]
    )
    data = {"summary": {"total_ticks": 30}, "agent": agent}
    with pytest.raises(ValueError):
        _resolve_end_tick(data)


def test_checkpoint_table_uses_only_pre_specified_available_horizons():
    rows = []
    for exp_id, offset in [
        ("NoClarification-Control", 0.0),
        ("Rational-Hub-Immediate", 0.2),
    ]:
        for tick in range(1, 36):
            rows.append(
                {
                    "exp_id": exp_id,
                    "tick": tick,
                    "trust_final": 5.0 + offset,
                    "purchase_intention": 0.5,
                }
            )
    out = _time_checkpoint_table(pd.DataFrame(rows), 35)
    assert set(out["checkpoint_tick"]) == {30, 35}
    treated = out[out["exp_id"] == "Rational-Hub-Immediate"]
    assert (treated["trust_delta_vs_control"].round(10) == 0.2).all()
