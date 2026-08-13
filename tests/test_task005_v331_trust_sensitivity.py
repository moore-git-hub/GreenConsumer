"""Zero-API tests for Stage-A Trust parameter sensitivity design."""
from __future__ import annotations

import pandas as pd

from mechanism_v33 import DEFAULT_TRUST_PARAMETERS, TrustDynamicsV33Parameters
from greenconsumer_v33.trust_sensitivity import (
    PARAMETER_RANGES,
    _local_effects,
    _profile_rows,
    profile_table,
)


def test_profile_matrix_is_pre_specified_and_baseline_exact():
    rows = _profile_rows()
    assert len(rows) == 18  # baseline + 14 OAT + 3 structured boundaries
    assert rows[0]["profile_id"] == "baseline"
    assert rows[0]["parameters"] == DEFAULT_TRUST_PARAMETERS
    assert len(PARAMETER_RANGES) == 7

    table = profile_table()
    baseline = table[table["profile_id"] == "baseline"].iloc[0]
    for name in PARAMETER_RANGES:
        assert float(baseline[name]) == float(getattr(DEFAULT_TRUST_PARAMETERS, name))
    assert set(table["empirically_calibrated"]) == {False}


def test_structured_profiles_include_retention_direction_reversal_and_legacy_boundary():
    specs = {row["profile_id"]: row["parameters"] for row in _profile_rows()}
    symmetric = specs["retention_symmetric_097"]
    assert symmetric.crisis_retention == symmetric.repair_retention == 0.97

    reversed_profile = specs["retention_reversed_096_098"]
    assert reversed_profile.crisis_retention < reversed_profile.repair_retention

    assert specs["legacy_v32_transition"] == TrustDynamicsV33Parameters.legacy_v32()


def test_local_effects_use_absolute_deltas_and_flag_sign_instability():
    df = pd.DataFrame(
        [
            {"profile_id": "baseline", "estimand_id": "P2", "value": 0.01},
            {"profile_id": "crisis_retention_low", "estimand_id": "P2", "value": -0.02},
            {"profile_id": "crisis_retention_high", "estimand_id": "P2", "value": 0.03},
        ]
    )
    out = _local_effects(df)
    row = out[(out["parameter"] == "crisis_retention") & (out["estimand_id"] == "P2")].iloc[0]
    assert abs(float(row["low_delta_from_baseline"]) - (-0.03)) < 1e-12
    assert abs(float(row["high_delta_from_baseline"]) - 0.02) < 1e-12
    assert bool(row["sign_stable"]) is False
