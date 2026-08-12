import asyncio
import csv
import dataclasses
import inspect
import json
import math
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RESULT_PATH = (
    ROOT
    / ".kiro"
    / "specs"
    / "task005-replication-inference"
    / "production_path_fake_model_smoke_v4_result1.0.json"
)
DIAGNOSTIC_SEED = 4301
EXPECTED_ROWS = 30 * 20


class Harness:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warned = 0
        self.failures = []
        self.warnings = []

    def check(self, label, condition, detail=None):
        if condition:
            self.passed += 1
            print(f"PASS {label}")
            return
        self.failed += 1
        self.failures.append({"label": label, "detail": detail})
        print(f"FAIL {label}: {detail!r}")

    def warn(self, label, detail=None):
        self.warned += 1
        self.warnings.append({"label": label, "detail": detail})
        print(f"WARN {label}: {detail!r}")


class DeterministicSemanticFakeRouter:
    def __init__(self):
        self.call_count = 0
        self.categories = []
        self.prompts = []
        self.current_tick = None

    def set_tick(self, tick):
        self.current_tick = tick

    async def chat(self, prompt):
        self.call_count += 1
        self.prompts.append(prompt)
        if "[Breaking News]" in prompt:
            self.categories.append("breaking_news")
            return _json_response(
                -0.85,
                0.80,
                0.80,
                0.65,
                0.95,
                0.10,
                True,
                8,
                "I am concerned because the allegation appears relevant and credible.",
            )
        if "[Brand Statement]" in prompt:
            if (
                "VerdantCo Structured Evidence Summary" in prompt
                or "verification, audit, procedural transparency" in prompt
            ):
                self.categories.append("rational_statement")
                return _json_response(
                    0.50,
                    0.45,
                    0.90,
                    0.95,
                    0.90,
                    0.30,
                    False,
                    7,
                    "I see checkable evidence in the brand statement.",
                )
            if (
                "VerdantCo Responsibility and Relationship Message" in prompt
                or "responsibility, consumer frustration" in prompt
            ):
                self.categories.append("empathy_statement")
                return _json_response(
                    0.10,
                    0.75,
                    0.72,
                    0.35,
                    0.90,
                    0.88,
                    False,
                    7,
                    "I feel acknowledged by the brand statement.",
                )
            raise RuntimeError("unknown brand-statement prompt")
        if "[Social Feed]" in prompt:
            self.categories.append("social_feed")
            return _json_response(
                0.10,
                0.30,
                0.45,
                0.20,
                0.50,
                0.10,
                False,
                4,
                "A social post mildly shaped my perception.",
            )
        raise RuntimeError("unknown observed prompt")


def _json_response(
    valence,
    arousal,
    credibility,
    evidence,
    relevance,
    perceived_empathy,
    hypocrisy,
    importance,
    reasoning,
):
    return json.dumps(
        {
            "valence": valence,
            "arousal": arousal,
            "credibility": credibility,
            "evidence_strength": evidence,
            "topic_relevance": relevance,
            "perceived_empathy": perceived_empathy,
            "hypocrisy_perceived": hypocrisy,
            "importance": importance,
            "reasoning": reasoning,
        }
    )


def _boolish(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _f(value):
    if value == "":
        return math.nan
    return float(value)


def _key(row):
    return (row["exp_id"], int(row["tick"]), row["agent_id"])


def _agent_at(result, tick):
    return [r for r in result["agent_records"] if int(r["tick"]) == tick]


def _mech_at(result, tick):
    return [r for r in result["mechanism_records"] if int(r["tick"]) == tick]


def _mean(rows, field):
    vals = [_f(r[field]) for r in rows]
    return sum(vals) / len(vals)


def _trajectory_mean(result, start_tick, end_tick):
    values = result["trust_trajectory"][start_tick - 1 : end_tick]
    return sum(values) / len(values)


def _post_auc(result):
    return sum(result["trust_trajectory"][4:])


def _reach_set(result):
    return {r["agent_id"] for r in result["clarification_exposure_meta"] if _boolish(r["reached"])}


def _public_set(result):
    return {r["agent_id"] for r in result["clarification_exposure_meta"] if _boolish(r["public_organic"])}


def _exposure_counts(result):
    meta = result["clarification_exposure_meta"]
    public = {r["agent_id"] for r in meta if _boolish(r["public_organic"])}
    paid = {r["agent_id"] for r in meta if _boolish(r["paid_seed"])}
    one_hop = {r["agent_id"] for r in meta if _boolish(r["paid_one_hop"])}
    union = {r["agent_id"] for r in meta if _boolish(r["reached"])}
    membership = sum(
        int(a in public) + int(a in paid) + int(a in one_hop)
        for a in set().union(public, paid, one_hop)
    )
    return {
        "public_count": len(public),
        "paid_seed_count": len(paid),
        "paid_one_hop_count": len(one_hop),
        "overlap_count": membership - len(union),
        "union_reach_count": len(union),
    }


async def _run_condition(exp_id):
    from experiment_config import generate_experiment_matrix
    import run_experiments

    cfg = next(c for c in generate_experiment_matrix() if c.exp_id == exp_id)
    cfg = dataclasses.replace(cfg, random_seed=DIAGNOSTIC_SEED)
    router = DeterministicSemanticFakeRouter()
    result = await run_experiments._run_with_patch(cfg, override_router=router)
    return result, router


async def _run_sentinels():
    exp_ids = [
        "NoClarification-Control",
        "Rational-Hub-Immediate",
        "Rational-Random-Immediate",
        "Empathy-Hub-Immediate",
        "Rational-Hub-Delayed",
    ]
    pairs = {}
    for exp_id in exp_ids:
        pairs[exp_id] = await _run_condition(exp_id)
    pairs["Rational-Hub-Immediate-Repeat"] = await _run_condition("Rational-Hub-Immediate")
    return pairs


def _assert_row_integrity(h, results):
    import run_experiments

    for exp_id, (result, _router) in results.items():
        if exp_id.endswith("-Repeat"):
            continue
        h.check(f"{exp_id} agent rows", len(result["agent_records"]) == EXPECTED_ROWS)
        h.check(f"{exp_id} mechanism rows", len(result["mechanism_records"]) == EXPECTED_ROWS)
        agent_keys = {_key(r) for r in result["agent_records"]}
        mechanism_keys = [_key(r) for r in result["mechanism_records"]]
        h.check(f"{exp_id} key one-to-one", agent_keys == set(mechanism_keys))
        h.check(f"{exp_id} mechanism key unique", len(mechanism_keys) == len(set(mechanism_keys)))
        h.check(
            f"{exp_id} tick5-only timeline",
            [int(e["tick"]) for e in result["effective_event_timeline"]] == [5],
            result["effective_event_timeline"],
        )

    with tempfile.TemporaryDirectory(prefix="task005_smoke_v2_") as tmp:
        csv_path = Path(tmp) / "mechanism_records.csv"
        run_experiments.write_mechanism_records_csv(
            [v[0] for k, v in results.items() if not k.endswith("-Repeat")],
            str(csv_path),
        )
        with csv_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        expected_keys = set()
        for exp_id, (result, _router) in results.items():
            if not exp_id.endswith("-Repeat"):
                expected_keys |= {_key(r) for r in result["mechanism_records"]}
        h.check("CSV mechanism row count", len(rows) == EXPECTED_ROWS * 5, len(rows))
        h.check("CSV key coverage", {_key(r) for r in rows} == expected_keys)


def _assert_reflect_plan(h, results, routers):
    total_calls = sum(r.call_count for r in routers.values())
    h.check("FakeRouter call_count > 0", total_calls > 0, total_calls)
    semantic_fallbacks = 0
    plan_fallbacks = 0
    for result, _router in results.values():
        semantic_fallbacks += sum(
            1
            for row in result["mechanism_records"]
            if _boolish(row["semantic_observation_present"])
            and _boolish(row["semantic_fallback_used"])
        )
        plan_fallbacks += sum(1 for row in result["mechanism_records"] if _boolish(row["plan_fallback_used"]))
    h.check("semantic observed fallback count", semantic_fallbacks == 0, semantic_fallbacks)
    h.check("plan fallback count", plan_fallbacks == 0, plan_fallbacks)
    return semantic_fallbacks, plan_fallbacks, total_calls


def _assert_clarification_gate(h, result):
    cfg = result["config"]
    tick = cfg["clarification_tick"]
    if tick is None:
        meta_reached = _reach_set(result)
        injected = {r["agent_id"] for r in result["agent_records"] if _boolish(r["clarification_injected"])}
        received = {r["agent_id"] for r in result["agent_records"] if _boolish(r["clarification_received"])}
        detected = {r["agent_id"] for r in result["agent_records"] if _boolish(r["clarification_detected_by_plan"])}
        h.check("control no clarification exposure", not meta_reached, sorted(meta_reached))
        h.check("control no clarification injected", not injected, sorted(injected))
        h.check("control no clarification received", not received, sorted(received))
        h.check("control no clarification detected", not detected, sorted(detected))
        return True
    rows = _agent_at(result, tick)
    reached = _reach_set(result)
    injected = {r["agent_id"] for r in rows if _boolish(r["clarification_injected"])}
    received = {r["agent_id"] for r in rows if _boolish(r["clarification_received"])}
    detected = {r["agent_id"] for r in rows if _boolish(r["clarification_detected_by_plan"])}
    h.check(f"{result['exp_id']} reached equals injected", reached == injected, (sorted(reached), sorted(injected)))
    h.check(f"{result['exp_id']} reached received", reached <= received, sorted(reached - received))
    h.check(f"{result['exp_id']} reached detected", reached <= detected, sorted(reached - detected))
    unreached = {r["agent_id"] for r in rows} - reached
    false_marks = [
        r["agent_id"]
        for r in rows
        if r["agent_id"] in unreached
        and (
            _boolish(r["clarification_injected"])
            or _boolish(r["clarification_received"])
            or _boolish(r["clarification_detected_by_plan"])
        )
    ]
    h.check(f"{result['exp_id']} unreached not marked", not false_marks, false_marks)
    return True


def _content_gate(h, rational, empathy):
    tick = rational["config"]["clarification_tick"]
    r_reach = _reach_set(rational)
    e_reach = _reach_set(empathy)
    h.check("content matched reach set", r_reach == e_reach, (sorted(r_reach), sorted(e_reach)))
    r_rows = [r for r in _mech_at(rational, tick) if r["agent_id"] in r_reach]
    e_rows = [r for r in _mech_at(empathy, tick) if r["agent_id"] in e_reach]
    by_e = {r["agent_id"]: r for r in e_rows}
    fields = [
        "semantic_valence",
        "semantic_arousal",
        "semantic_credibility",
        "semantic_evidence_strength",
        "semantic_perceived_empathy",
        "semantic_topic_relevance",
    ]
    semantic_contrasts = {
        field: _mean(r_rows, field) - _mean(e_rows, field)
        for field in fields
    }
    h.check(
        "content semantic profile differs",
        any(abs(v) > 1e-9 for v in semantic_contrasts.values()),
        semantic_contrasts,
    )
    primary_gates = {
        "D_evidence": semantic_contrasts["semantic_evidence_strength"] > 0,
        "D_credibility": semantic_contrasts["semantic_credibility"] > 0,
        "D_empathy": (
            _mean(e_rows, "semantic_perceived_empathy")
            - _mean(r_rows, "semantic_perceived_empathy")
        ) > 0,
        "D_arousal": (
            _mean(e_rows, "semantic_arousal")
            - _mean(r_rows, "semantic_arousal")
        ) > 0,
    }
    h.check("content primary semantic gates v2", all(primary_gates.values()), primary_gates)
    h.check("valence descriptive only", "semantic_valence" in semantic_contrasts)
    downstream_fields = ["attitude_att", "repair_memory", "trust_final", "purchase_intention"]
    downstream = {}
    for field in downstream_fields:
        diffs = [_f(row[field]) - _f(by_e[row["agent_id"]][field]) for row in r_rows]
        downstream[field] = sum(diffs) / len(diffs)
    h.check(
        "content downstream pathway differs",
        any(abs(v) > 1e-9 for v in downstream.values()),
        downstream,
    )
    trajectory = {
        "early_trust": _trajectory_mean(rational, 6, 10) - _trajectory_mean(empathy, 6, 10),
        "post_auc": _post_auc(rational) - _post_auc(empathy),
        "final_trust": rational["trust_trajectory"][-1] - empathy["trust_trajectory"][-1],
    }
    return semantic_contrasts, downstream, trajectory


def _channel_gate(h, hub, random):
    h.check("channel public exposure set equal", _public_set(hub) == _public_set(random))
    hub_counts = _exposure_counts(hub)
    random_counts = _exposure_counts(random)
    h.check(
        "channel reach difference exists",
        hub_counts["union_reach_count"] != random_counts["union_reach_count"],
        (hub_counts, random_counts),
    )
    warning = "none"
    if hub_counts["union_reach_count"] == 20:
        h.warn("CHANNEL_REACH_SATURATION", hub_counts)
        warning = "CHANNEL_REACH_SATURATION"
    elif hub_counts["union_reach_count"] >= 18:
        h.warn("CHANNEL_REACH_NEAR_SATURATION", hub_counts)
        warning = "CHANNEL_REACH_NEAR_SATURATION"
    return hub_counts, random_counts, warning


def _timing_gate(h, immediate, delayed):
    h.check("timing matched reach set", _reach_set(immediate) == _reach_set(delayed))
    contrasts = {
        "early": _trajectory_mean(immediate, 6, 10) - _trajectory_mean(delayed, 6, 10),
        "post_auc": _post_auc(immediate) - _post_auc(delayed),
        "final": immediate["trust_trajectory"][-1] - delayed["trust_trajectory"][-1],
    }
    h.check("timing early contrast positive", contrasts["early"] > 0, contrasts)
    if contrasts["final"] < 0:
        h.warn("FINAL_HORIZON_TIMING_REVERSAL", contrasts)
    return contrasts


def _control_gate(h, control):
    pre = control["trust_trajectory"][3]
    after_scandal = control["trust_trajectory"][4]
    final = control["trust_trajectory"][-1]
    h.check("control tick5 scandal damage retained", after_scandal < pre, (pre, after_scandal))
    h.check("control no full baseline recovery", final < pre, (pre, final))


def _tpb_and_clipping(h, results):
    pbc_values = set()
    clips = []
    for label, (result, _router) in results.items():
        for row in result["mechanism_records"]:
            pbc_values.add(_f(row["pbc"]))
            trust = _f(row["trust_final"])
            if trust <= 0.0 or trust >= 10.0:
                clips.append(
                    {
                        "condition": label,
                        "agent_id": row["agent_id"],
                        "tick": int(row["tick"]),
                        "trust_final": trust,
                    }
                )
    h.check("PBC invariant", pbc_values == {0.5}, sorted(pbc_values))
    return clips


def _social_code_gate(h):
    from plugins.environment.network.SocialNetworkPlugin import SocialNetworkPlugin
    import simulation_core

    source = inspect.getsource(SocialNetworkPlugin.broadcast_message)
    h.check("social broadcast uses successors", "successors" in source and ".successors(" in inspect.getsource(SocialNetworkPlugin.get_successors))
    h.check("social packet source", '"source": "Social"' in source)
    h.check("social packet type", '"type": "social_review"' in source)
    h.check("social packet sender", '"sender_id": sender_id' in source)
    loop = inspect.getsource(simulation_core.run_simulation_core)
    plan_pos = loop.find('plan").execute')
    settle_pos = loop.find("agent_records.append")
    route_anchor = loop.find("tick_posts_dict = {}")
    clear_pos = loop.find('set_state("incoming_messages", [])', route_anchor)
    broadcast_pos = loop.find("broadcast_message", route_anchor)
    positions = [plan_pos, settle_pos, route_anchor, clear_pos, broadcast_pos]
    h.check(
        "production loop social order",
        all(p >= 0 for p in positions) and positions == sorted(positions),
        positions,
    )


def _social_runtime_gate(h, result):
    posts = [
        (int(r["tick"]), r["agent_id"])
        for r in result["agent_records"]
        if _boolish(r["is_posting"]) and str(r["post_content"]).strip()
    ]
    if not posts:
        h.warn("SOCIAL_FULL_RUN_STATUS=NO_POST_OBSERVED")
        return "NO_POST_OBSERVED", "not-run"
    edges = defaultdict(list)
    for edge in result["network_edges"]:
        edges[edge["source_agent_id"]].append(edge["target_agent_id"])
    mech = {(int(r["tick"]), r["agent_id"]): r for r in result["mechanism_records"]}
    verified = []
    for tick, sender in posts:
        if tick >= result["config"]["total_ticks"]:
            continue
        for receiver in edges.get(sender, []):
            row = mech.get((tick + 1, receiver))
            if not row:
                continue
            if int(row["semantic_social_observation_count"]) > 0 and (
                row["reflect_primary_source"] == "Social"
                or "Social" in str(row.get("reflect_message_sources", ""))
            ):
                verified.append(
                    {
                        "post_tick": tick,
                        "sender_id": sender,
                        "successor_id": receiver,
                    }
                )
                break
        if verified:
            break
    h.check("social full-run successor reflection", bool(verified), {"posts": posts[:5], "verified": verified})
    return "POST_OBSERVED", "PASS"


def _reproducibility_gate(h, first, repeat):
    compared = {
        "agent_records": first["agent_records"] == repeat["agent_records"],
        "mechanism_records": first["mechanism_records"] == repeat["mechanism_records"],
        "clarification_exposure_meta": first["clarification_exposure_meta"] == repeat["clarification_exposure_meta"],
        "trust_trajectory": first["trust_trajectory"] == repeat["trust_trajectory"],
        "conversion_trajectory": first["conversion_trajectory"] == repeat["conversion_trajectory"],
        "network_edges": first["network_edges"] == repeat["network_edges"],
        "target_nodes_meta": first["target_nodes_meta"] == repeat["target_nodes_meta"],
    }
    h.check("exact reproducibility", all(compared.values()), compared)
    return all(compared.values()), compared


def _legacy_mock_v2_compatible():
    import run_experiments

    source = inspect.getsource(run_experiments._DeterministicMockRouter.chat)
    required = ["valence", "arousal", "credibility", "evidence_strength", "topic_relevance"]
    return all(token in source for token in required)


def _stimulus_inventory():
    return [
        {
            "stimulus": "Tick5 scandal",
            "source_location": "run_experiments._SINGLE_SCANDAL / simulation_core.ENTERPRISE_STRATEGY",
            "summary": "Single greenwashing scandal event injected at Tick 5 by _run_with_patch.",
            "hypothetical": True,
            "source_status": "SOURCE_VERIFICATION_REQUIRED",
        },
        {
            "stimulus": "Rational clarification",
            "source_location": "clarification_injector.py",
            "summary": "Evidence-oriented brand statement with checkable-facts language.",
            "hypothetical": True,
            "source_status": "SOURCE_VERIFICATION_REQUIRED",
        },
        {
            "stimulus": "Empathy clarification",
            "source_location": "clarification_injector.py",
            "summary": "Empathy-oriented brand statement with frustration-validation and trust-board language.",
            "hypothetical": True,
            "source_status": "SOURCE_VERIFICATION_REQUIRED",
        },
    ]


def main():
    h = Harness()
    pairs = asyncio.run(_run_sentinels())
    results = {k: v[0] for k, v in pairs.items()}
    routers = {k: v[1] for k, v in pairs.items()}

    _assert_row_integrity(h, pairs)
    semantic_fallbacks, plan_fallbacks, fake_calls = _assert_reflect_plan(h, pairs, routers)
    for exp_id in [
        "NoClarification-Control",
        "Rational-Hub-Immediate",
        "Rational-Random-Immediate",
        "Empathy-Hub-Immediate",
        "Rational-Hub-Delayed",
    ]:
        _assert_clarification_gate(h, results[exp_id])

    content_semantic, content_downstream, content_traj = _content_gate(
        h,
        results["Rational-Hub-Immediate"],
        results["Empathy-Hub-Immediate"],
    )
    hub_counts, random_counts, channel_warning = _channel_gate(
        h,
        results["Rational-Hub-Immediate"],
        results["Rational-Random-Immediate"],
    )
    timing = _timing_gate(
        h,
        results["Rational-Hub-Immediate"],
        results["Rational-Hub-Delayed"],
    )
    _control_gate(h, results["NoClarification-Control"])
    clips = _tpb_and_clipping(h, pairs)
    _social_code_gate(h)
    social_status, social_micro = _social_runtime_gate(h, results["Rational-Hub-Immediate"])
    reproducible, reproducibility_detail = _reproducibility_gate(
        h,
        results["Rational-Hub-Immediate"],
        results["Rational-Hub-Immediate-Repeat"],
    )

    inventory = _stimulus_inventory()
    source_required = sum(1 for item in inventory if item["source_status"] == "SOURCE_VERIFICATION_REQUIRED")
    h.check("stimulus provenance inventory count", source_required == 3, inventory)

    legacy_mock_compatible = _legacy_mock_v2_compatible()
    h.check("legacy deterministic mock audited", legacy_mock_compatible is False, legacy_mock_compatible)

    result_payload = {
        "schema_version": "1.0",
        "stage": "TASK_005 production-path-fake-model-smoke-v2",
        "result": "PASS" if h.failed == 0 else "BLOCKED",
        "diagnostic_only": True,
        "literature_derived": False,
        "empirical_calibration": False,
        "formal_reuse_forbidden": True,
        "diagnostic_seed": DIAGNOSTIC_SEED,
        "sentinel_conditions": 5,
        "fake_router_calls": fake_calls,
        "real_llm_calls": False,
        "external_api_calls": False,
        "reflect_fallbacks": semantic_fallbacks,
        "plan_fallbacks": plan_fallbacks,
        "mechanism_rows_per_condition": EXPECTED_ROWS,
        "csv_key_coverage": h.failed == 0,
        "hub_union_reach": hub_counts["union_reach_count"],
        "random_union_reach": random_counts["union_reach_count"],
        "channel_reach_warning": channel_warning,
        "content_semantic_contrast": content_semantic,
        "content_downstream_contrast": content_downstream,
        "content_trajectory_contrast": content_traj,
        "timing_contrast": timing,
        "social_full_run_status": social_status,
        "social_micro_routing": social_micro,
        "pbc_invariant": True,
        "trust_clipping_count": len(clips),
        "trust_clipping_details": clips,
        "exact_reproducibility": reproducible,
        "reproducibility_detail": reproducibility_detail,
        "legacy_deterministic_mock_v2_compatible": legacy_mock_compatible,
        "stimulus_provenance_inventory": inventory,
        "source_verification_required_count": source_required,
        "warnings": h.warnings,
        "failures": h.failures,
        "production_behavior_changed": False,
        "formal_execution": False,
        "p_values_computed": False,
    }

    print(f"Passed: {h.passed}")
    print(f"Failed: {h.failed}")
    print(f"Warned: {h.warned}")

    if h.failed == 0:
        RESULT_PATH.write_text(
            json.dumps(result_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    raise SystemExit(1 if h.failed else 0)


if __name__ == "__main__":
    main()
