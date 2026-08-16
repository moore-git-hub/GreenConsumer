"""Selected Real-LLM robustness blocks for TASK_005 v3.3.1.

Two engineering questions are separated:
1. prompt-layout sensitivity at fixed model/temperature/seeds;
2. provider/runtime stochasticity under the exact frozen baseline prompt.

The suite never changes Trust, clarification, network, demand, treatment, or
T35 settings. It requires explicit Real-LLM authorization and is not formal
inference. The requested model seed is intentionally held constant across the
baseline repeats so observed variation measures practical non-determinism under
nominally identical settings.
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import pandas as pd

from greenconsumer_v32.config import (
    DEFAULT_DEMAND_SEED,
    DEFAULT_LLM_SEED,
    DEFAULT_SIMULATION_SEED,
    PROJECT_ROOT,
)
from greenconsumer_v32.io import write_csv, write_json

from .analysis import analyze_run
from .config import DEFAULT_TOTAL_TICKS, RunSettings
from .prompt_profiles import (
    BASELINE_PROMPT_PROFILE,
    PROMPT_PROFILES,
    PromptProfileRouter,
)
from . import runner as runner_module

SCHEMA = "task005_fmcg_v331_real_llm_robustness1.0"


def profile_table() -> pd.DataFrame:
    """Five unique blocks: three prompt profiles + two extra baseline repeats."""

    return pd.DataFrame(
        [
            {
                "profile_id": "baseline_r1",
                "prompt_profile": "baseline_exact",
                "baseline_repeat": 1,
                "role": "prompt-anchor-and-stochasticity-repeat",
            },
            {
                "profile_id": "compact_r1",
                "prompt_profile": "compact_separator",
                "baseline_repeat": 0,
                "role": "prompt-layout-robustness",
            },
            {
                "profile_id": "schema_first_r1",
                "prompt_profile": "schema_first",
                "baseline_repeat": 0,
                "role": "prompt-order-robustness",
            },
            {
                "profile_id": "baseline_r2",
                "prompt_profile": "baseline_exact",
                "baseline_repeat": 2,
                "role": "provider-stochasticity-repeat",
            },
            {
                "profile_id": "baseline_r3",
                "prompt_profile": "baseline_exact",
                "baseline_repeat": 3,
                "role": "provider-stochasticity-repeat",
            },
        ]
    )


@contextlib.contextmanager
def _prompt_router_patch(profile: str, holder: dict):
    """Patch only v3.3 runner router construction for one labelled block."""

    original_builder = runner_module.build_inner_router

    def builder(
        mode: str,
        requested_llm_seed: int,
        *,
        model_override: str | None = None,
    ):
        base = original_builder(
            mode,
            requested_llm_seed,
            model_override=model_override,
        )
        wrapped = PromptProfileRouter(base, profile)
        holder["router"] = wrapped
        return wrapped

    runner_module.build_inner_router = builder
    try:
        yield
    finally:
        runner_module.build_inner_router = original_builder


def _estimands(run_dir: Path, profile_row: dict) -> pd.DataFrame:
    frame = pd.read_csv(run_dir / "single_block_estimands.csv")
    frame.insert(0, "profile_id", str(profile_row["profile_id"]))
    frame.insert(1, "prompt_profile", str(profile_row["prompt_profile"]))
    frame.insert(2, "baseline_repeat", int(profile_row["baseline_repeat"]))
    return frame


def _semantic_summary(run_dir: Path, profile_row: dict) -> pd.DataFrame:
    path = run_dir / "agent_thoughts.csv"
    df = pd.read_csv(path)
    clarification = df[df["clarification_received"].astype(str).str.lower().isin({"true", "1", "yes"})].copy()
    metrics = [
        "semantic_credibility",
        "semantic_evidence_strength",
        "semantic_perceived_empathy",
        "semantic_valence",
        "semantic_arousal",
        "semantic_topic_relevance",
    ]
    for col in metrics:
        clarification[col] = pd.to_numeric(clarification[col], errors="coerce")
    rows = []
    for content, group in clarification.groupby("content_factor", dropna=False):
        row = {
            "profile_id": str(profile_row["profile_id"]),
            "prompt_profile": str(profile_row["prompt_profile"]),
            "baseline_repeat": int(profile_row["baseline_repeat"]),
            "content_factor": str(content),
            "clarification_rows": int(len(group)),
        }
        for col in metrics:
            row[f"mean_{col}"] = float(group[col].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def _profile_stability(estimands: pd.DataFrame) -> pd.DataFrame:
    prompt = estimands[estimands["profile_id"].isin({"baseline_r1", "compact_r1", "schema_first_r1"})].copy()
    rows = []
    for eid, group in prompt.groupby("estimand_id"):
        values = pd.to_numeric(group["value"], errors="raise")
        signs = ["positive" if x > 0 else "negative" if x < 0 else "zero" for x in values]
        rows.append(
            {
                "estimand_id": str(eid),
                "prompt_profiles": ";".join(group["prompt_profile"].astype(str)),
                "values": ";".join(f"{float(x):.12g}" for x in values),
                "min": float(values.min()),
                "max": float(values.max()),
                "range": float(values.max() - values.min()),
                "sign_stable": len(set(signs)) == 1,
                "analysis_role": "three-profile Real-LLM prompt-layout robustness; descriptive only",
            }
        )
    return pd.DataFrame(rows)


def _stochasticity_summary(estimands: pd.DataFrame) -> pd.DataFrame:
    base = estimands[estimands["prompt_profile"] == BASELINE_PROMPT_PROFILE].copy()
    rows = []
    for eid, group in base.groupby("estimand_id"):
        values = pd.to_numeric(group["value"], errors="raise")
        signs = ["positive" if x > 0 else "negative" if x < 0 else "zero" for x in values]
        rows.append(
            {
                "estimand_id": str(eid),
                "baseline_repeats": int(len(values)),
                "mean": float(values.mean()),
                "sd_descriptive": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                "min": float(values.min()),
                "max": float(values.max()),
                "range": float(values.max() - values.min()),
                "sign_stable": len(set(signs)) == 1,
                "analysis_role": "same-seed practical provider/runtime stochasticity; descriptive only",
            }
        )
    return pd.DataFrame(rows)


def _invariants(run_payloads: list[dict], audits: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for item in run_payloads:
        p = item["profile"]
        payload = item["payload"]
        cond = payload.get("condition_meta") or []
        replay_miss = sum(int(x.get("replay_misses", 0)) for x in cond)
        frozen_real_llm_settings = (
            payload.get("llm_mode") == "real"
            and payload.get("llm_model") == runner_module.MODEL
            and abs(float(payload.get("llm_temperature", -1)) - 0.3) < 1e-12
            and int(payload.get("total_ticks", -1)) == 35
        )
        rows.extend(
            [
                {
                    "check_id": "RUN_STATUS",
                    "profile_id": p["profile_id"],
                    "status": "PASS" if payload.get("status") == "PASS" else "FAIL",
                    "observed": payload.get("status"),
                    "criterion": "run status PASS",
                },
                {
                    "check_id": "SEMANTIC_FALLBACK_ZERO",
                    "profile_id": p["profile_id"],
                    "status": "PASS" if int(payload.get("semantic_fallback_events", -1)) == 0 else "FAIL",
                    "observed": payload.get("semantic_fallback_events"),
                    "criterion": "zero semantic fallback events",
                },
                {
                    "check_id": "COMMON_HISTORY_REPLAY_MISS_ZERO",
                    "profile_id": p["profile_id"],
                    "status": "PASS" if replay_miss == 0 else "FAIL",
                    "observed": replay_miss,
                    "criterion": "zero replay misses within each block",
                },
                {
                    "check_id": "FROZEN_REAL_LLM_SETTINGS",
                    "profile_id": p["profile_id"],
                    "status": "PASS" if frozen_real_llm_settings else "FAIL",
                    "observed": (
                        f"mode={payload.get('llm_mode')}; "
                        f"model={payload.get('llm_model')}; "
                        f"temp={payload.get('llm_temperature')}; "
                        f"T={payload.get('total_ticks')}"
                    ),
                    "criterion": f"real {runner_module.MODEL} path at temperature .3 and T35",
                },
            ]
        )

    for profile_id, group in audits.groupby("profile_id"):
        lexical_ok = group["lexical_multiset_equal"].astype(bool).all()
        profile = str(group["prompt_profile"].iloc[0])
        changed = group["changed"].astype(bool)
        expected_changed = profile != BASELINE_PROMPT_PROFILE
        change_ok = (not changed.any()) if not expected_changed else changed.all()
        rows.extend(
            [
                {
                    "check_id": "PROMPT_LEXICAL_MULTISET_PRESERVED",
                    "profile_id": profile_id,
                    "status": "PASS" if lexical_ok else "FAIL",
                    "observed": f"all_equal={lexical_ok}; calls={len(group)}",
                    "criterion": "whitespace-insensitive lexical multiset preserved for every provider prompt",
                },
                {
                    "check_id": "PROMPT_TRANSFORM_ROLE",
                    "profile_id": profile_id,
                    "status": "PASS" if change_ok else "FAIL",
                    "observed": f"profile={profile}; changed_calls={int(changed.sum())}/{len(group)}",
                    "criterion": "baseline unchanged; non-baseline profiles transformed on every provider call",
                },
            ]
        )
    return pd.DataFrame(rows)


def _plot_estimand_by_prompt(estimands: pd.DataFrame, eid: str, path: Path) -> str:
    df = estimands[
        (estimands["estimand_id"] == eid)
        & (estimands["profile_id"].isin({"baseline_r1", "compact_r1", "schema_first_r1"}))
    ].copy()
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.scatter(df["prompt_profile"], pd.to_numeric(df["value"], errors="raise"), s=70)
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xlabel("Pre-specified prompt layout profile")
    ax.set_ylabel(str(df["unit"].iloc[0]))
    ax.set_title(
        f"Real-LLM prompt-layout robustness: {eid}\n"
        f"{runner_module.MODEL}, temperature .3, T35; descriptive only"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)
    return str(path)


def _plot_baseline_repeats(estimands: pd.DataFrame, eid: str, path: Path) -> str:
    df = estimands[(estimands["estimand_id"] == eid) & (estimands["prompt_profile"] == BASELINE_PROMPT_PROFILE)].copy()
    df = df.sort_values("baseline_repeat")
    fig, ax = plt.subplots(figsize=(7, 4.8))
    ax.plot(df["baseline_repeat"], pd.to_numeric(df["value"], errors="raise"), marker="o")
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("Identical baseline-prompt provider repeat")
    ax.set_ylabel(str(df["unit"].iloc[0]))
    ax.set_title(f"Real-LLM practical stochasticity: {eid}\nSame requested seed/model/temperature; descriptive only")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)
    return str(path)


async def run_suite(*, output_root: Path, allow_real_llm: bool) -> dict:
    if not allow_real_llm:
        raise ValueError("Real-LLM robustness requires explicit allow_real_llm=True")

    suite_id = dt.datetime.now().strftime("llmrob_%Y%m%d_%H%M%S")
    suite_dir = Path(output_root) / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)
    profiles = profile_table()
    profiles.to_csv(suite_dir / "llm_robustness_profiles.csv", index=False, encoding="utf-8-sig")

    payloads = []
    estimand_frames = []
    semantic_frames = []
    prompt_audit_frames = []

    for row in profiles.to_dict(orient="records"):
        profile_root = suite_dir / "profiles" / str(row["profile_id"])
        settings = RunSettings(
            llm_mode="real",
            condition="all",
            simulation_seed=DEFAULT_SIMULATION_SEED,
            requested_llm_seed=DEFAULT_LLM_SEED,
            demand_seed=DEFAULT_DEMAND_SEED,
            output_dir=profile_root,
            run_demand=True,
            support_mode="both",
            allow_real_llm=True,
            total_ticks=DEFAULT_TOTAL_TICKS,
            prompt_profile=str(row["prompt_profile"]),
        )
        holder: dict = {}
        with _prompt_router_patch(str(row["prompt_profile"]), holder):
            payload = await runner_module.execute(settings)
        run_dir = Path(payload["output_dir"])
        analyze_run(run_dir)

        wrapper = holder["router"]
        audit = pd.DataFrame(wrapper.records)
        audit.insert(0, "profile_id", str(row["profile_id"]))
        prompt_audit_frames.append(audit)
        audit.to_csv(run_dir / "prompt_transform_audit.csv", index=False, encoding="utf-8-sig")

        summary_path = run_dir / "run_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["prompt_robustness"] = {
            "prompt_profile": str(row["prompt_profile"]),
            "profile_id": str(row["profile_id"]),
            "baseline_repeat": int(row["baseline_repeat"]),
            "prompt_transform_audit_file": "prompt_transform_audit.csv",
            "provider_prompt_records": int(len(audit)),
            "lexical_multiset_preserved_all": bool(audit["lexical_multiset_equal"].all()),
        }
        write_json(summary_path, summary)
        payload = summary
        payloads.append({"profile": row, "payload": payload})
        estimand_frames.append(_estimands(run_dir, row))
        semantic_frames.append(_semantic_summary(run_dir, row))

    estimands = pd.concat(estimand_frames, ignore_index=True)
    semantics = pd.concat(semantic_frames, ignore_index=True)
    audits = pd.concat(prompt_audit_frames, ignore_index=True)
    prompt_stability = _profile_stability(estimands)
    stochasticity = _stochasticity_summary(estimands)
    invariants = _invariants(payloads, audits)

    estimands.to_csv(suite_dir / "llm_robustness_estimands.csv", index=False, encoding="utf-8-sig")
    semantics.to_csv(suite_dir / "llm_robustness_semantics.csv", index=False, encoding="utf-8-sig")
    audits.to_csv(suite_dir / "prompt_transform_audit.csv", index=False, encoding="utf-8-sig")
    prompt_stability.to_csv(suite_dir / "prompt_profile_stability.csv", index=False, encoding="utf-8-sig")
    stochasticity.to_csv(suite_dir / "baseline_stochasticity.csv", index=False, encoding="utf-8-sig")
    invariants.to_csv(suite_dir / "llm_robustness_invariants.csv", index=False, encoding="utf-8-sig")

    figures = []
    for eid in (
        "P1_OVERALL_CLARIFICATION_POST_TRUST_V33",
        "P2_CONTENT_POST_TRUST_V33",
        "P3_TIMING_PRE_DELAY_TRUST_V33",
        "P5_OVERALL_CLARIFICATION_EXPECTED_REPEAT_CHOICE_V33",
    ):
        figures.append(_plot_estimand_by_prompt(estimands, eid, suite_dir / "figures" / f"PROMPT_{eid}.png"))
        figures.append(_plot_baseline_repeats(estimands, eid, suite_dir / "figures" / f"STOCHASTICITY_{eid}.png"))

    failures = int((invariants["status"] == "FAIL").sum())
    provider_calls = sum(
        int(meta.get("provider_calls", 0))
        for item in payloads
        for meta in (item["payload"].get("condition_meta") or [])
    )
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS" if failures == 0 else "FAIL",
        "scope": "selected Real-LLM prompt-layout and practical-stochasticity engineering robustness; descriptive only",
        "formal_inference_performed": False,
        "p_values_computed": False,
        "confidence_intervals_computed": False,
        "prompt_selection_permitted": False,
        "baseline_prompt_profile": BASELINE_PROMPT_PROFILE,
        "prompt_profiles": list(PROMPT_PROFILES),
        "baseline_repeats": 3,
        "profiles_run": int(len(profiles)),
        "requested_llm_seed_held_constant": DEFAULT_LLM_SEED,
        "llm_model": runner_module.MODEL,
        "simulation_seed": DEFAULT_SIMULATION_SEED,
        "demand_seed": DEFAULT_DEMAND_SEED,
        "temperature": 0.3,
        "horizon": 35,
        "invariant_failures": failures,
        "provider_calls_total": int(provider_calls),
        "prompt_sign_unstable_estimands": int((~prompt_stability["sign_stable"]).sum()),
        "baseline_repeat_sign_unstable_estimands": int((~stochasticity["sign_stable"]).sum()),
        "figures": figures,
        "interpretation_rule": (
            "Do not select a prompt profile or requested seed based on favorable outcomes. "
            "Prompt-profile variation is format/order sensitivity; baseline-repeat variation is practical provider/runtime stochasticity."
        ),
        "output_dir": str(suite_dir),
    }
    write_json(suite_dir / "llm_robustness_summary.json", summary)
    return summary


def plan_payload() -> dict:
    profiles = profile_table()
    return {
        "schema_version": SCHEMA,
        "status": "PLAN_ONLY",
        "real_llm_calls_started": False,
        "profiles": profiles.to_dict(orient="records"),
        "profiles_count": int(len(profiles)),
        "prompt_profiles": list(PROMPT_PROFILES),
        "baseline_repeats": 3,
        "same_requested_seed_across_repeats": True,
        "llm_model": runner_module.MODEL,
        "estimated_cost_note": "Five full 9-condition Real-LLM engineering blocks; actual provider-call count is runtime-dependent.",
    }


def run_sync(**kwargs) -> dict:
    return asyncio.run(run_suite(**kwargs))
