"""Zero-API unit tests for the finite-horizon robustness helpers."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from greenconsumer_v33.horizon_sensitivity import (
    _prefix_compare,
    _stability_table,
)


def _write_cognitive(path: Path, end_tick: int, offset: float = 0.0) -> None:
    rows = []
    for tick in range(1, end_tick + 1):
        rows.append(
            {
                "exp_id": "NoClarification-Control",
                "tick": tick,
                "agent_id": "A",
                "trust_final": 5.0 + offset + tick / 1000.0,
            }
        )
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path / "cognitive_records.csv", index=False)


def test_prefix_compare_passes_when_longer_run_preserves_history(tmp_path):
    a = tmp_path / "T30"
    b = tmp_path / "T35"
    _write_cognitive(a, 30)
    _write_cognitive(b, 35)
    out = _prefix_compare(a, b, 30)
    assert out["status"] == "PASS"


def test_prefix_compare_fails_when_future_horizon_changes_the_past(tmp_path):
    a = tmp_path / "T30"
    b = tmp_path / "T35"
    _write_cognitive(a, 30)
    _write_cognitive(b, 35, offset=0.1)
    out = _prefix_compare(a, b, 30)
    assert out["status"] == "FAIL"


def test_stability_table_reports_sign_change_without_selecting_endpoint():
    df = pd.DataFrame(
        [
            {"estimand_id": "P2", "horizon_tick": 30, "value": -0.01},
            {"estimand_id": "P2", "horizon_tick": 35, "value": 0.00},
            {"estimand_id": "P2", "horizon_tick": 40, "value": 0.02},
        ]
    )
    out = _stability_table(df)
    assert bool(out.loc[0, "sign_stable"]) is False
    assert "boundary evidence" in out.loc[0, "interpretation"]
