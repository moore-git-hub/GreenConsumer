"""Zero-API tests for Stage-B Morris Trust sensitivity."""
from __future__ import annotations

import numpy as np
import pandas as pd

from greenconsumer_v33.trust_sensitivity_morris import (
    DELTA,
    ESTIMANDS,
    LEVELS,
    PARAMETERS,
    TRAJECTORIES,
    elementary_effects,
    generate_morris_design,
    morris_statistics,
    validate_morris_design,
)


def test_morris_design_has_pre_specified_dimensions_and_valid_steps():
    design = generate_morris_design()
    assert len(PARAMETERS) == 7
    assert LEVELS == 6
    assert abs(DELTA - 0.6) < 1e-12
    assert TRAJECTORIES == 10
    assert len(design) == TRAJECTORIES * (len(PARAMETERS) + 1)

    checks = validate_morris_design(design)
    assert not (checks["status"] == "FAIL").any()

    for _trajectory, group in design.groupby("trajectory_id"):
        g = group.sort_values("step_index")
        assert len(g) == len(PARAMETERS) + 1
        changed = list(g.loc[g["step_index"] > 0, "changed_parameter"])
        assert sorted(changed) == sorted(PARAMETERS)


def test_morris_design_is_deterministic_for_fixed_design_seed():
    a = generate_morris_design()
    b = generate_morris_design()
    pd.testing.assert_frame_equal(a, b, check_dtype=False, check_exact=True)


def test_elementary_effects_recover_linear_normalized_model():
    design = generate_morris_design(trajectories=3, seed=123)
    unique = design.drop_duplicates("evaluation_id").copy()
    coefficients = {name: float(i + 1) for i, name in enumerate(PARAMETERS)}

    rows = []
    for row in unique.itertuples(index=False):
        y = sum(
            coefficients[name] * float(getattr(row, f"x_{name}"))
            for name in PARAMETERS
        )
        payload = {"evaluation_id": row.evaluation_id}
        for estimand in ESTIMANDS:
            payload[estimand] = y
        rows.append(payload)

    effects = elementary_effects(design, pd.DataFrame(rows))
    for name in PARAMETERS:
        observed = effects[
            (effects["parameter"] == name)
            & (effects["estimand_id"] == ESTIMANDS[0])
        ]["elementary_effect"].to_numpy(dtype=float)
        assert len(observed) == 3
        assert np.allclose(observed, coefficients[name], atol=1e-12)

    stats = morris_statistics(effects)
    for name in PARAMETERS:
        row = stats[
            (stats["parameter"] == name)
            & (stats["estimand_id"] == ESTIMANDS[0])
        ].iloc[0]
        assert abs(float(row["mu"]) - coefficients[name]) < 1e-12
        assert abs(float(row["mu_star"]) - coefficients[name]) < 1e-12
        assert abs(float(row["sigma"])) < 1e-12


def test_every_parameter_gets_one_effect_per_trajectory_per_estimand():
    design = generate_morris_design(trajectories=4, seed=321)
    unique = design.drop_duplicates("evaluation_id").copy()
    rows = []
    for row in unique.itertuples(index=False):
        payload = {"evaluation_id": row.evaluation_id}
        base = sum(float(getattr(row, f"x_{name}")) ** 2 for name in PARAMETERS)
        for estimand in ESTIMANDS:
            payload[estimand] = base
        rows.append(payload)
    effects = elementary_effects(design, pd.DataFrame(rows))
    counts = effects.groupby(["parameter", "estimand_id"]).size()
    assert set(counts) == {4}
