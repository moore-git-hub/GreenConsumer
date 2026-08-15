"""Auditable, descriptive cognition-evolution outputs for TASK_005 v3.3.1.

This module is offline post-processing only.  It never calls an LLM and never
changes simulation state.  ``reasoning`` is preserved as the model's explicit
one-sentence appraisal; it is not treated as hidden chain-of-thought or coded
into new psychological constructs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SCHEMA_VERSION = "task005_fmcg_v331_cognition_outputs1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROL = "NoClarification-Control"
STATE_FIELDS = (
    "trust_final",
    "attitude_att",
    "subjective_norm_after",
    "pbc",
    "purchase_intention",
    "crisis_memory",
    "repair_memory",
)
THOUGHT_REQUIRED = {
    "exp_id", "tick", "agent_id", "thought_present", "reasoning",
    "clarification_received", "semantic_observation_present",
    "semantic_social_observation_count", "semantic_fallback_used",
}
COGNITIVE_REQUIRED = {"exp_id", "tick", "agent_id", *STATE_FIELDS}
TRANSITIONS = (
    ("crisis_shock", 4, 5),
    ("immediate_response", 5, 6),
    ("delayed_onset", 9, 10),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_provenance(project_root: Path = PROJECT_ROOT) -> dict:
    """Return the post-processor Git identity without mutating the repository."""

    def run_git(*args: str) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(project_root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""

    status = run_git("status", "--porcelain", "--untracked-files=normal")
    return {
        "git_head": run_git("rev-parse", "HEAD"),
        "git_branch": run_git("branch", "--show-current"),
        "git_dirty": bool(status),
        "git_status_short": status,
    }


def _as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})


def _write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _write_json(payload: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _require_columns(frame: pd.DataFrame, required: set[str], source: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{source} missing required columns: {missing}")


def _validate_and_load(run_dir: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame, int]:
    paths = {
        "summary": run_dir / "run_summary.json",
        "thoughts": run_dir / "agent_thoughts.csv",
        "cognitive": run_dir / "cognitive_records.csv",
    }
    for path in paths.values():
        if not path.exists():
            raise FileNotFoundError(path)
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    thoughts = pd.read_csv(paths["thoughts"], keep_default_na=False)
    cognitive = pd.read_csv(paths["cognitive"])
    _require_columns(thoughts, THOUGHT_REQUIRED, "agent_thoughts.csv")
    _require_columns(cognitive, COGNITIVE_REQUIRED, "cognitive_records.csv")

    keys = ["exp_id", "tick", "agent_id"]
    for name, frame in (("agent_thoughts.csv", thoughts), ("cognitive_records.csv", cognitive)):
        frame["exp_id"] = frame["exp_id"].astype(str)
        frame["agent_id"] = frame["agent_id"].astype(str)
        frame["tick"] = pd.to_numeric(frame["tick"], errors="raise").astype(int)
        if frame.duplicated(keys).any():
            raise ValueError(f"{name} contains duplicate Agent x Tick keys")
    thought_keys = set(map(tuple, thoughts[keys].itertuples(index=False, name=None)))
    cognitive_keys = set(map(tuple, cognitive[keys].itertuples(index=False, name=None)))
    if thought_keys != cognitive_keys:
        raise ValueError(
            "agent_thoughts.csv and cognitive_records.csv have different Agent x Tick keys"
        )

    for field in STATE_FIELDS:
        cognitive[field] = pd.to_numeric(cognitive[field], errors="coerce")
        if cognitive[field].isna().any():
            raise ValueError(f"cognitive_records.csv has non-numeric or missing {field}")
    end_tick = int(cognitive["tick"].max())
    declared = int(summary.get("total_ticks", end_tick))
    if declared != end_tick:
        raise ValueError(f"time-horizon mismatch: summary={declared}, observed={end_tick}")
    if end_tick < 10:
        raise ValueError("cognition transition design requires an observed horizon of at least T10")
    expected_ticks = set(range(1, end_tick + 1))
    incomplete = []
    for (exp_id, agent_id), group in cognitive.groupby(["exp_id", "agent_id"], sort=True):
        observed_ticks = set(group["tick"].astype(int))
        if observed_ticks != expected_ticks:
            incomplete.append((exp_id, agent_id, sorted(expected_ticks - observed_ticks)))
    if incomplete:
        example = incomplete[0]
        raise ValueError(
            "incomplete Agent x Tick panel: "
            f"exp_id={example[0]}, agent_id={example[1]}, missing_ticks={example[2]}"
        )
    return summary, thoughts, cognitive, end_tick


def _reasoning_ledger(thoughts: pd.DataFrame) -> pd.DataFrame:
    frame = thoughts.copy()
    for field in (
        "thought_present", "clarification_received", "semantic_observation_present",
        "semantic_fallback_used",
    ):
        frame[field] = _as_bool(frame[field])
    frame["reasoning"] = frame["reasoning"].astype(str)
    frame = frame[frame["thought_present"] & frame["reasoning"].str.strip().ne("")].copy()
    preferred = [
        "exp_id", "tick", "agent_id", "cluster_type", "social_role",
        "content_factor", "channel_factor", "timing_factor",
        "observation_count", "observation_sources", "clarification_received",
        "semantic_observation_present", "semantic_social_observation_count",
        "semantic_valence", "semantic_arousal", "semantic_credibility",
        "semantic_evidence_strength", "semantic_topic_relevance",
        "semantic_perceived_empathy", "semantic_hypocrisy_perceived",
        "importance", "reasoning", "semantic_fallback_used",
    ]
    available = [column for column in preferred if column in frame.columns]
    frame = frame[available].sort_values(["exp_id", "tick", "agent_id"])
    frame.insert(len(frame.columns), "interpretation_scope", "explicit_appraisal_only_not_hidden_CoT")
    return frame


def _tick_summary(thoughts: pd.DataFrame, cognitive: pd.DataFrame) -> pd.DataFrame:
    flags = thoughts[[
        "exp_id", "tick", "agent_id", "thought_present", "clarification_received",
        "semantic_observation_present", "semantic_social_observation_count",
        "semantic_fallback_used",
    ]].copy()
    for field in (
        "thought_present", "clarification_received", "semantic_observation_present",
        "semantic_fallback_used",
    ):
        flags[field] = _as_bool(flags[field]).astype(int)
    flags["semantic_social_observation_count"] = pd.to_numeric(
        flags["semantic_social_observation_count"], errors="coerce"
    ).fillna(0)
    merged = cognitive.merge(flags, on=["exp_id", "tick", "agent_id"], validate="one_to_one")
    aggregations = {field: (field, "mean") for field in STATE_FIELDS}
    aggregations.update({
        "agents": ("agent_id", "nunique"),
        "thought_rate": ("thought_present", "mean"),
        "clarification_exposure_rate": ("clarification_received", "mean"),
        "semantic_observation_rate": ("semantic_observation_present", "mean"),
        "mean_social_observation_count": ("semantic_social_observation_count", "mean"),
        "semantic_fallback_rate": ("semantic_fallback_used", "mean"),
    })
    out = merged.groupby(["exp_id", "tick"], dropna=False).agg(**aggregations).reset_index()
    out["analysis_role"] = "single_run_descriptive_group_mean"
    return out


def _window_summary(cognitive: pd.DataFrame, end_tick: int) -> pd.DataFrame:
    windows = (
        ("pre_crisis", 1, 4),
        ("crisis_event", 5, 5),
        ("immediate_response_window", 6, 9),
        ("delayed_and_recovery_window", 10, end_tick),
    )
    rows: list[dict] = []
    for label, start, stop in windows:
        subset = cognitive[cognitive["tick"].between(start, stop)]
        for exp_id, group in subset.groupby("exp_id", sort=True):
            row = {
                "exp_id": exp_id,
                "window": label,
                "start_tick": start,
                "end_tick": stop,
                "agent_tick_rows": len(group),
                "agents": group["agent_id"].nunique(),
                "analysis_role": "single_run_descriptive_window_mean",
            }
            row.update({field: group[field].mean() for field in STATE_FIELDS})
            rows.append(row)
    return pd.DataFrame(rows)


def _agent_transitions(cognitive: pd.DataFrame, end_tick: int) -> pd.DataFrame:
    transitions = (*TRANSITIONS, ("recovery_to_endpoint", 5, end_tick))
    rows: list[pd.DataFrame] = []
    keys = ["exp_id", "agent_id"]
    for label, before_tick, after_tick in transitions:
        before = cognitive[cognitive["tick"] == before_tick][keys + list(STATE_FIELDS)].copy()
        after = cognitive[cognitive["tick"] == after_tick][keys + list(STATE_FIELDS)].copy()
        merged = before.merge(after, on=keys, suffixes=("_before", "_after"), validate="one_to_one")
        if len(merged) != len(before) or len(merged) != len(after):
            raise ValueError(f"incomplete agent coverage for transition {label}")
        out = merged[keys].copy()
        out["transition"] = label
        out["before_tick"] = before_tick
        out["after_tick"] = after_tick
        for field in STATE_FIELDS:
            out[f"delta_{field}"] = merged[f"{field}_after"] - merged[f"{field}_before"]
        rows.append(out)
    result = pd.concat(rows, ignore_index=True)
    result["analysis_role"] = "individual_descriptive_change_no_inference"
    return result


def _transition_summary(agent_transitions: pd.DataFrame) -> pd.DataFrame:
    delta_fields = [field for field in agent_transitions if field.startswith("delta_")]
    rows: list[dict] = []
    for (exp_id, transition, before_tick, after_tick), group in agent_transitions.groupby(
        ["exp_id", "transition", "before_tick", "after_tick"], sort=True
    ):
        for field in delta_fields:
            values = group[field]
            rows.append({
                "exp_id": exp_id,
                "transition": transition,
                "before_tick": before_tick,
                "after_tick": after_tick,
                "state": field.removeprefix("delta_"),
                "agents": len(values),
                "mean_delta": values.mean(),
                "sd_across_agents": values.std(ddof=1) if len(values) > 1 else np.nan,
                "minimum_delta": values.min(),
                "maximum_delta": values.max(),
                "analysis_role": "single_run_descriptive_not_formal_inference",
            })
    return pd.DataFrame(rows)


def _figures(tick: pd.DataFrame, transition: pd.DataFrame, out_dir: Path) -> list[Path]:
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    colors = plt.get_cmap("tab10")
    conditions = sorted(tick["exp_id"].astype(str).unique(), key=lambda x: (x != CONTROL, x))

    display_fields = (
        ("trust_final", "Trust"),
        ("attitude_att", "Attitude"),
        ("subjective_norm_after", "Subjective norm"),
        ("purchase_intention", "Purchase intention"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True)
    for ax, (field, label) in zip(axes.flat, display_fields):
        for index, exp_id in enumerate(conditions):
            part = tick[tick["exp_id"].astype(str) == exp_id]
            ax.plot(part["tick"], part[field], linewidth=1.2, color=colors(index), label=exp_id)
        ax.axvline(5, color="#555555", linestyle="--", linewidth=0.8)
        ax.axvline(6, color="#888888", linestyle=":", linewidth=0.8)
        ax.axvline(10, color="#888888", linestyle=":", linewidth=0.8)
        ax.set_title(label)
        ax.set_xlabel("Tick")
        ax.set_ylabel("Agent mean")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.04),
        ncol=3, fontsize=8,
    )
    fig.suptitle("Descriptive cognition-state trajectories by condition")
    fig.text(0.5, 0.01, "Single run; lines are agent means, not population estimates.", ha="center", fontsize=9)
    path = fig_dir / "01_cognition_state_trajectories.png"
    fig.tight_layout(rect=(0, 0.13, 1, 0.96)); fig.savefig(path, dpi=180); plt.close(fig)
    outputs.append(path)

    recovery = transition[transition["transition"] == "recovery_to_endpoint"].copy()
    states = ["trust_final", "attitude_att", "subjective_norm_after", "purchase_intention"]
    matrix = recovery.pivot(index="exp_id", columns="state", values="mean_delta").reindex(conditions)
    matrix = matrix.reindex(columns=states)
    scale = max(float(np.nanmax(np.abs(matrix.to_numpy()))), 1e-12)
    fig, ax = plt.subplots(figsize=(10, 6))
    image = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="coolwarm", vmin=-scale, vmax=scale)
    ax.set_yticks(range(len(matrix.index))); ax.set_yticklabels(matrix.index, fontsize=8)
    ax.set_xticks(range(len(states))); ax.set_xticklabels([x.replace("_", " ") for x in states], rotation=20, ha="right")
    ax.set_title("Mean within-agent change: T5 to observed endpoint")
    fig.colorbar(image, ax=ax, label="Mean descriptive change")
    path = fig_dir / "02_recovery_transition_heatmap.png"
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)
    outputs.append(path)

    fig, ax = plt.subplots(figsize=(12, 5))
    for index, exp_id in enumerate(conditions):
        part = tick[tick["exp_id"].astype(str) == exp_id]
        ax.plot(part["tick"], part["thought_rate"], linewidth=1.2, color=colors(index), label=exp_id)
    ax.set(xlabel="Tick", ylabel="Fraction with explicit appraisal", ylim=(-0.02, 1.02),
           title="Availability of explicit appraisal records")
    ax.legend(fontsize=7, ncol=3)
    path = fig_dir / "03_explicit_appraisal_availability.png"
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)
    outputs.append(path)
    return outputs


def build_cognition_outputs(run_dir: Path) -> dict:
    """Build auditable cognition-evolution tables, figures and a hash manifest."""
    run_dir = Path(run_dir).resolve()
    summary, thoughts, cognitive, end_tick = _validate_and_load(run_dir)
    out_dir = run_dir / "thesis_outputs" / "cognition"
    table_dir = out_dir / "tables"
    ledger = _reasoning_ledger(thoughts)
    tick = _tick_summary(thoughts, cognitive)
    window = _window_summary(cognitive, end_tick)
    agents = _agent_transitions(cognitive, end_tick)
    transition = _transition_summary(agents)

    generated = [
        _write_csv(ledger, table_dir / "01_explicit_appraisal_ledger.csv"),
        _write_csv(tick, table_dir / "02_cognition_tick_summary.csv"),
        _write_csv(window, table_dir / "03_cognition_window_summary.csv"),
        _write_csv(agents, table_dir / "04_agent_transition_ledger.csv"),
        _write_csv(transition, table_dir / "05_transition_summary.csv"),
    ]
    generated.extend(_figures(tick, transition, out_dir))

    sources = [run_dir / "run_summary.json", run_dir / "agent_thoughts.csv", run_dir / "cognitive_records.csv"]
    analysis_files = [
        Path(__file__).resolve(),
        PROJECT_ROOT / "run_v33_cognition.py",
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": summary.get("run_id", ""),
        "code_release": summary.get("code_release", ""),
        "resolved_end_tick": end_tick,
        "scope": "offline descriptive cognition post-processing; no model-state mutation",
        "reasoning_semantics": "explicit one-sentence appraisal only; not hidden chain-of-thought",
        "formal_inference_performed": False,
        "external_validity_claimed": False,
        "text_coding_performed": False,
        "source_run_git_provenance": summary.get("git_provenance", {}),
        "postprocessor_git_provenance": _git_provenance(),
        "analysis_code_hashes": [
            {
                "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in analysis_files
        ],
        "source_evidence_hashes": [
            {"path": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in sources
        ],
        "generated_outputs": [
            {
                "path": str(path.relative_to(run_dir)).replace("\\", "/"),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in generated
        ],
    }
    manifest_path = _write_json(manifest, out_dir / "cognition_output_manifest.json")
    return {
        "status": "PASS",
        "run_id": summary.get("run_id", ""),
        "resolved_end_tick": end_tick,
        "output_dir": str(out_dir),
        "tables": [str(path) for path in generated if path.suffix == ".csv"],
        "figures": [str(path) for path in generated if path.suffix == ".png"],
        "manifest": str(manifest_path),
        "formal_inference_performed": False,
    }
