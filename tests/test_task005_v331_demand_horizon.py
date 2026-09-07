"""Zero-API tests for v3.3.1 horizon-aware renewal demand."""
from __future__ import annotations

import pandas as pd
import pytest

from fmcg_scenario_v32 import ENGINEERING_PERSONAS
from greenconsumer_v33.demand import _realized_horizon, simulate_demand


def _cognitive_rows(end_tick: int) -> list[dict]:
    rows = []
    for tick in range(1, end_tick + 1):
        for persona in ENGINEERING_PERSONAS:
            rows.append(
                {
                    "exp_id": "NoClarification-Control",
                    "tick": tick,
                    "agent_id": persona.agent_id,
                    "attitude_att": 0.55,
                    "subjective_norm_after": 0.50,
                    "trust_final": 5.50,
                }
            )
    return rows


def test_realized_horizon_requires_contiguous_ticks():
    rows = _cognitive_rows(5)
    assert _realized_horizon(rows) == 5
    broken = [row for row in rows if int(row["tick"]) != 3]
    with pytest.raises(ValueError):
        _realized_horizon(broken)


def test_t35_cognitive_run_produces_35_demand_curve_ticks():
    _, curves = simulate_demand(
        _cognitive_rows(35),
        support_present=False,
        demand_seed=2026081701,
        micro_buyers=2,
    )
    assert len(curves) == 35
    assert [int(row["tick"]) for row in curves] == list(range(1, 36))
    assert {int(row["total_ticks"]) for row in curves} == {35}


def test_extending_horizon_does_not_change_demand_prefix():
    rows30, curves30 = simulate_demand(
        _cognitive_rows(30),
        support_present=False,
        demand_seed=2026081701,
        micro_buyers=2,
    )
    rows35, curves35 = simulate_demand(
        _cognitive_rows(35),
        support_present=False,
        demand_seed=2026081701,
        micro_buyers=2,
    )

    # ``total_ticks`` is provenance and is expected to differ.  The realized
    # purchase process through T30 must otherwise be exactly identical.
    a = pd.DataFrame(rows30).drop(columns=["total_ticks"], errors="ignore")
    b = pd.DataFrame([row for row in rows35 if int(row["tick"]) <= 30]).drop(
        columns=["total_ticks"], errors="ignore"
    )
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True), check_dtype=False)

    ca = pd.DataFrame(curves30).drop(columns=["total_ticks"], errors="ignore")
    cb = pd.DataFrame([row for row in curves35 if int(row["tick"]) <= 30]).drop(
        columns=["total_ticks"], errors="ignore"
    )
    pd.testing.assert_frame_equal(ca.reset_index(drop=True), cb.reset_index(drop=True), check_dtype=False)
