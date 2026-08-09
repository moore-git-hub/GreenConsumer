from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_task005_real_variance_pilot_v1 as pilot


P = 0
F = 0


def check(name: str, condition: bool, actual=None) -> None:
    global P, F
    if condition:
        P += 1
        print("PASS", name)
    else:
        F += 1
        print("FAIL", name, actual)


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_contract_identity() -> None:
    contract = json.loads(
        (ROOT / ".kiro/specs/task005-replication-inference/real_llm_variance_pilot_contract1.0.json").read_text(
            encoding="utf-8"
        )
    )
    estimand = json.loads(
        (ROOT / ".kiro/specs/task005-replication-inference/task005_estimand_contract1.0.json").read_text(
            encoding="utf-8"
        )
    )
    preflight = pilot.preflight()
    check("pilot id", pilot.PILOT_ID == "task005-real-variance-pilot-v1", pilot.PILOT_ID)
    check("contract pilot id", contract["pilot_id"] == pilot.PILOT_ID, contract["pilot_id"])
    check("master seed", pilot.MASTER_SEED == 2026081001, pilot.MASTER_SEED)
    check("10 blocks", preflight["replication_blocks"] == 10, preflight)
    check("replicate ids exact", tuple(preflight["replicate_ids"]) == tuple(f"R{i:03d}" for i in range(1, 11)))
    check("conditions 9", preflight["conditions_per_block"] == 9, preflight)
    check("condition order exact", tuple(preflight["condition_order"]) == pilot.EXECUTION_ORDER)
    check("mechanism schema 2.0", pilot.MECHANISM_SCHEMA == "2.0")
    check("mechanism records schema 1.2", pilot.MECHANISM_RECORDS_SCHEMA == "1.2")
    check("empathy weight fixed", pilot.EMPATHY_REPAIR_WEIGHT == 0.50)
    check("estimand independent unit", estimand["independent_unit"] == "replication_block")
    check("agent n firewall", estimand["agent_level_n_used_for_power"] is False)
    check("p value firewall", estimand["firewalls"]["p_values_computed"] is False)


def _fixture_rows(exp_id: str, trust_by_tick: dict[int, float], buyers: set[str]) -> list[dict]:
    rows = []
    for tick in range(1, 31):
        for idx in range(20):
            aid = f"A{idx:02d}"
            rows.append({
                "schema_version": "1.2",
                "exp_id": exp_id,
                "tick": tick,
                "agent_id": aid,
                "trust_final": trust_by_tick.get(tick, 1.0),
                "is_buying": aid in buyers and tick in (2, 3, 4),
                "empathy_repair_weight": 0.50,
            })
    return rows


def test_estimand_boundaries() -> None:
    control = [cfg for cfg in pilot.select_variance_conditions() if cfg.is_control][0]
    post_ticks = {tick: float(tick) for tick in range(1, 31)}
    rows = _fixture_rows(control.exp_id, post_ticks, {"A00", "A01"})
    metric = pilot.compute_condition_metrics(
        replicate_id="R001",
        config=control,
        mechanism_rows=rows,
        exposure_rows=[],
    )
    expected_post = sum((tick + tick + 1) / 2 for tick in range(6, 30)) / 24
    expected_early = sum((tick + tick + 1) / 2 for tick in range(6, 10)) / 4
    check("POST AUC Tick6-Tick30", metric["POST_TRUST_AUC"] == expected_post, metric)
    check("EARLY AUC Tick6-Tick10", metric["EARLY_TRUST_AUC"] == expected_early, metric)
    check("purchase unique agents", metric["PURCHASE_RATE_T30"] == 2 / 20, metric)
    check("control reach NA", metric["REACH_RATE"] is None, metric)

    strategy = [cfg for cfg in pilot.select_variance_conditions() if not cfg.is_control][0]
    srows = _fixture_rows(strategy.exp_id, post_ticks, {"A00"})
    exposure = [{"exp_id": strategy.exp_id, "agent_id": f"A{i:02d}", "reached": i < 7} for i in range(20)]
    smetric = pilot.compute_condition_metrics(
        replicate_id="R001",
        config=strategy,
        mechanism_rows=srows,
        exposure_rows=exposure,
    )
    check("strategy reach rate", smetric["REACH_RATE"] == 7 / 20, smetric)


def test_block_estimands_and_variance() -> None:
    conditions = pilot.select_variance_conditions()
    metrics = []
    for cfg in conditions:
        content_sign = 1 if cfg.content_factor == "rational-evidence" else -1
        channel_sign = 1 if cfg.channel_factor == "hub" else -1
        timing_sign = 1 if cfg.timing_factor == "immediate" else -1
        post_auc = (
            10.0 if cfg.is_control
            else 12.0 + content_sign + (0.5 * channel_sign) + (0.25 * timing_sign)
            + (0.75 * content_sign * timing_sign)
        )
        purchase_rate = (
            0.2 if cfg.is_control
            else 0.35 + (0.02 * content_sign * channel_sign)
        )
        metrics.append({
            "replicate_id": "R001",
            "exp_id": cfg.exp_id,
            "content_factor": cfg.content_factor,
            "channel_factor": cfg.channel_factor,
            "timing_factor": cfg.timing_factor,
            "is_control": cfg.is_control,
            "POST_TRUST_AUC": post_auc,
            "EARLY_TRUST_AUC": 5.0 if cfg.timing_factor == "immediate" else 4.0,
            "PURCHASE_RATE_T30": purchase_rate,
            "REACH_RATE": None if cfg.is_control else (0.9 if cfg.channel_factor == "hub" else 0.6),
            "FINAL_TRUST_T30": 9.0,
        })
    est = pilot.build_block_estimands("R001", metrics)
    check("P1 manual", est["P1_OVERALL_CLARIFICATION_POST_TRUST"] == 2.0, est)
    check("P3 manual", est["P3_TIMING_EARLY_TRUST"] == 1.0, est)
    check("P4 manual", abs(est["P4_CHANNEL_REACH"] - 0.3) < 1e-12, est)
    check("P5 manual", abs(est["P5_OVERALL_CLARIFICATION_PURCHASE"] - 0.15) < 1e-12, est)
    check("secondary fields present", all(field in est for field in pilot.SECONDARY_ESTIMANDS), est)
    ri = [row for row in metrics if row["content_factor"] == "rational-evidence" and row["timing_factor"] == "immediate"]
    rd = [row for row in metrics if row["content_factor"] == "rational-evidence" and row["timing_factor"] == "delayed"]
    ei = [row for row in metrics if row["content_factor"] == "emotional-empathy" and row["timing_factor"] == "immediate"]
    ed = [row for row in metrics if row["content_factor"] == "emotional-empathy" and row["timing_factor"] == "delayed"]
    expected_ct = (
        sum(row["POST_TRUST_AUC"] for row in ri) / len(ri)
        - sum(row["POST_TRUST_AUC"] for row in rd) / len(rd)
        - sum(row["POST_TRUST_AUC"] for row in ei) / len(ei)
        + sum(row["POST_TRUST_AUC"] for row in ed) / len(ed)
    )
    check("content x timing equal-weight", abs(est["CONTENT_x_TIMING_POST_TRUST_AUC"] - expected_ct) < 1e-12, est)
    expected_cp = (
        sum(row["PURCHASE_RATE_T30"] for row in metrics if row["content_factor"] == "rational-evidence" and row["channel_factor"] == "hub") / 2
        - sum(row["PURCHASE_RATE_T30"] for row in metrics if row["content_factor"] == "rational-evidence" and row["channel_factor"] == "random") / 2
        - sum(row["PURCHASE_RATE_T30"] for row in metrics if row["content_factor"] == "emotional-empathy" and row["channel_factor"] == "hub") / 2
        + sum(row["PURCHASE_RATE_T30"] for row in metrics if row["content_factor"] == "emotional-empathy" and row["channel_factor"] == "random") / 2
    )
    check("content x channel purchase equal-weight", abs(est["CONTENT_x_CHANNEL_PURCHASE_RATE_T30"] - expected_cp) < 1e-12, est)
    est2 = dict(est, replicate_id="R002", P1_OVERALL_CLARIFICATION_POST_TRUST=3.0)
    summary = pilot.summarize_variance([est, est2])
    check("ddof1 variance", summary["primary_estimands"]["P1_OVERALL_CLARIFICATION_POST_TRUST"]["sample_variance"] == 0.5, summary)
    check("covariance 5x5 rows", len(summary["covariance_matrix"]) == 5, summary)
    check("correlation 5x5 rows", len(summary["correlation_matrix"]) == 5, summary)
    check("leave one out rows", len(summary["leave_one_out_sd"]) == 10, summary)
    check("no p values", summary["p_values_computed"] is False, summary)


def test_dry_run_and_cli() -> None:
    with tempfile.TemporaryDirectory(prefix="task005_variance_test_") as tmp:
        root = Path(tmp)
        result = pilot.write_offline_dry_run_artifacts(root, synthetic_blocks=2)
        check("dry run pass", result["status"] == "DRY_RUN_PASS", result)
        for rid in ("R001", "R002"):
            block = root / rid
            check(f"{rid} attempt marker", (block / "attempt_marker.json").exists())
            check(f"{rid} mechanism rows", len(_rows(block / "mechanism_records.csv")) == 5400)
            check(f"{rid} condition metrics rows", len(_rows(block / "condition_metrics.csv")) == 9)
            check(f"{rid} block estimands rows", len(_rows(block / "block_estimands.csv")) == 1)
        all_metrics = _rows(root / "all_condition_metrics.csv")
        all_est = _rows(root / "all_block_estimands.csv")
        check("2x9 condition metrics", len(all_metrics) == 18, len(all_metrics))
        check("2 block estimands", len(all_est) == 2, len(all_est))
        check("control reach blank", all(row["REACH_RATE"] == "" for row in all_metrics if row["is_control"] == "True"))
        vs = json.loads((root / "variance_summary.json").read_text(encoding="utf-8"))
        check("variance summary no formal", vs["formal_execution"] is False, vs)
        check("variance summary no p", vs["p_values_computed"] is False, vs)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "run_task005_real_variance_pilot_v1.py"), "--execute-real"],
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    check("execute real rejected", proc.returncode == 2, proc.stdout)
    check("execute real label", pilot.REAL_MODE_REJECTION in proc.stdout, proc.stdout)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "run_task005_real_variance_pilot_v1.py"), "--offline-test"],
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    check("offline-test pass", proc.returncode == 0, proc.stdout + proc.stderr)
    check("offline-test zero calls", '"real_llm_calls": 0' in proc.stdout, proc.stdout)


def test_source_freeze() -> None:
    hashes = pilot.current_source_hashes()
    required = {
        "mechanism_v2.py",
        "plugins/agent/plan/ConsumerPlanPlugin.py",
        "plugins/agent/reflect/GreenCognitionPlugin.py",
        "simulation_core.py",
        "clarification_injector.py",
        "experiment_config.py",
        "replication_config.py",
        "run_experiments.py",
        "run_task005_real_variance_pilot_v1.py",
        ".kiro/specs/task005-replication-inference/task005_estimand_contract1.0.json",
        ".kiro/specs/task005-replication-inference/real_llm_variance_pilot_contract1.0.json",
        ".kiro/specs/task005-replication-inference/empathy_relational_repair_amendment1.0.json",
        ".kiro/specs/task005-replication-inference/mechanism_auditability_schema_amendment1.2.json",
        ".kiro/specs/task005-replication-inference/manipulation_stage_closure1.0.json",
    }
    check("source freeze exact keys", set(hashes) == required, sorted(set(hashes) ^ required))
    check("source hashes sha256", all(len(v) == 64 for v in hashes.values()), hashes)


def main() -> int:
    test_contract_identity()
    test_estimand_boundaries()
    test_block_estimands_and_variance()
    test_dry_run_and_cli()
    test_source_freeze()
    print("Passed:", P)
    print("Failed:", F)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
