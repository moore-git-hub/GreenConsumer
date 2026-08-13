"""Zero-API tests for thesis-safe sensitivity figure post-processing."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from greenconsumer_v33.sensitivity_figures import replot_sensitivity_suite


PRIMARY = [
    "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
    "P2_CONTENT_POST_TRUST_V33",
    "P3_TIMING_PRE_DELAY_TRUST_V33",
    "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
]


def test_stage_a_replot_is_postprocessing_only(tmp_path: Path):
    rows = []
    for estimand in PRIMARY:
        for parameter, low, high in [
            ("event_adjustment", -0.1, 0.2),
            ("repair_retention", -0.05, 0.07),
        ]:
            rows.append(
                {
                    "parameter": parameter,
                    "estimand_id": estimand,
                    "low_delta_from_baseline": low,
                    "high_delta_from_baseline": high,
                }
            )
    pd.DataFrame(rows).to_csv(
        tmp_path / "trust_sensitivity_local_effects.csv", index=False
    )
    payload = replot_sensitivity_suite(tmp_path)
    assert payload["status"] == "PASS"
    assert payload["mode"] == "stage-a-oat"
    assert payload["post_processing_only"] is True
    assert payload["model_rerun_performed"] is False
    assert len(payload["figures"]) == 4
    assert all(Path(path).exists() for path in payload["figures"])


def test_morris_replot_is_postprocessing_only(tmp_path: Path):
    rows = []
    for estimand in PRIMARY:
        for rank, parameter in enumerate(
            ["event_adjustment", "repair_retention"], start=1
        ):
            rows.append(
                {
                    "parameter": parameter,
                    "estimand_id": estimand,
                    "mu_star": 0.2 / rank,
                    "sigma": 0.1 / rank,
                    "rank_mu_star": rank,
                }
            )
    pd.DataFrame(rows).to_csv(tmp_path / "morris_statistics.csv", index=False)
    payload = replot_sensitivity_suite(tmp_path)
    assert payload["status"] == "PASS"
    assert payload["mode"] == "stage-b-morris"
    assert len(payload["figures"]) == 4
    assert all(Path(path).exists() for path in payload["figures"])
