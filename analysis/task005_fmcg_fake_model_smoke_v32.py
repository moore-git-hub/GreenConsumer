"""Deterministic 9 x 2 offline smoke test for TASK_005 FMCG scenario-v3.2.

This script deliberately avoids AgentKernel and networkx so it can validate the
new scientific contracts in restricted environments.  It does not replace the
versioned AgentKernel runtime gate in ``task005_fmcg_runtime_v32.py``.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiment_config import generate_experiment_matrix
from fmcg_scenario_v32 import (
    CLARIFICATION_TEMPLATES,
    CRISIS_STIMULUS,
    ENGINEERING_PERSONAS,
    SCHEMA as SCENARIO_SCHEMA,
)
from mechanism_v2 import (
    behavior_probabilities,
    deterministic_uniform,
    update_psychological_state,
)
from mechanism_v31_cognition import update_subjective_norm
from mechanism_v32_semantics import SCHEMA as SEMANTIC_SCHEMA
from mechanism_v32_semantics import validate_semantic_payload
from purchase_mechanism_v3 import tpb_purchase_intention
from purchase_mechanism_v31 import DemandParameters, DemandState, purchase_step
from purchase_mechanism_v32 import (
    SCHEMA as DEMAND_ADAPTER_SCHEMA,
    build_scenario_micro_cohort,
    mapping_audit_payload,
)
from task005_fmcg_fake_router_v32 import DeterministicFMCGSemanticRouterV32


CONTRACT_SEED = 53201
TOTAL_TICKS = 30
SCANDAL_TICK = 5
MICRO_BUYERS_PER_ARCHETYPE = 25
OUT_DIR = ROOT / ".kiro" / "specs" / "task005-replication-inference"
COGNITIVE_PATH = OUT_DIR / "fmcg_v32_fake_cognitive_records1.0.csv"
DEMAND_PATH = OUT_DIR / "fmcg_v32_fake_demand_opportunities1.0.csv"
CURVE_PATH = OUT_DIR / "fmcg_v32_fake_choice_curves1.0.csv"
SUMMARY_PATH = OUT_DIR / "fmcg_v32_fake_condition_summary1.0.csv"
PROFILE_PATH = OUT_DIR / "fmcg_v32_engineering_profiles1.0.jsonl"
RESULT_PATH = OUT_DIR / "fmcg_v32_fake_model_smoke_result1.0.json"


INITIAL_TRUST = {
    "Active_Greens": 8.0,
    "Convenient_Greens": 6.5,
    "Dormant_Greens": 5.5,
    "Non_Greens": 5.0,
}


@dataclass
class CognitiveState:
    baseline_trust: float
    trust: float
    attitude: float
    subjective_norm: float = 0.5
    pbc: float = 0.5
    crisis_memory: float = 0.0
    repair_memory: float = 0.0
    last_post_tick: int | None = None


class GateReport:
    def __init__(self):
        self.rows: list[dict] = []

    def check(self, gate: str, condition: bool, detail=None) -> None:
        self.rows.append(
            {
                "gate": gate,
                "status": "PASS" if condition else "FAIL",
                "detail": detail,
            }
        )
        print(("PASS" if condition else "FAIL") + f" {gate}")

    @property
    def passed(self) -> bool:
        return all(row["status"] == "PASS" for row in self.rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty audit file: {path}")
    fieldnames = list(rows[0])
    if any(list(row) != fieldnames for row in rows):
        raise ValueError(f"inconsistent field order for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _weighted_sample(repeated_nodes: list[int], m: int, rng: random.Random) -> set[int]:
    targets: set[int] = set()
    while len(targets) < m:
        targets.add(rng.choice(repeated_nodes))
    return targets


def _directed_ba_edges(n: int, m: int, seed: int) -> tuple[list[str], list[tuple[str, str]]]:
    """Small pure-Python equivalent of the NetworkX default BA construction."""

    if not 1 <= m < n:
        raise ValueError("BA graph requires 1 <= m < n")
    rng = random.Random(seed)
    undirected: set[tuple[int, int]] = {(0, node) for node in range(1, m + 1)}
    degree = Counter()
    for left, right in undirected:
        degree[left] += 1
        degree[right] += 1
    repeated = [node for node in range(m + 1) for _ in range(degree[node])]
    source = m + 1
    while source < n:
        targets = _weighted_sample(repeated, m, rng)
        for target in targets:
            undirected.add((min(source, target), max(source, target)))
        repeated.extend(targets)
        repeated.extend([source] * m)
        source += 1

    degree = Counter()
    for left, right in undirected:
        degree[left] += 1
        degree[right] += 1
    directed = []
    for left, right in sorted(undirected):
        source, target = (
            (left, right) if degree[left] >= degree[right] else (right, left)
        )
        directed.append((f"Consumer_{source:03d}", f"Consumer_{target:03d}"))
    nodes = [f"Consumer_{index:03d}" for index in range(n)]
    return nodes, directed


def _successors(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    result = {node: [] for node in nodes}
    for source, target in edges:
        result[source].append(target)
    for node in result:
        result[node].sort()
    return result


def _reach_set(config, nodes, successors) -> set[str]:
    if config.is_control:
        return set()
    public_rng = random.Random(int(config.random_seed) + 92317)
    public = set(public_rng.sample(sorted(nodes), round(len(nodes) * 0.25)))
    if config.channel_factor == "hub":
        paid = set(
            sorted(nodes, key=lambda node: (-len(successors[node]), node))[
                : config.budget_k
            ]
        )
    else:
        paid_rng = random.Random(int(config.random_seed) + 7777)
        paid = set(paid_rng.sample(nodes, config.budget_k))
    amplified = {target for source in paid for target in successors[source]}
    return public | paid | amplified


def _semantic_prompt(persona, observations: list[dict]) -> tuple[str, int]:
    global_news = [row for row in observations if row["source"] == "Global News"]
    clarification = [
        row for row in observations if row["source"] == "Enterprise_Clarification"
    ]
    social = [row for row in observations if row["source"] == "Social"]
    parts = []
    if global_news:
        parts.append(f"[Breaking News] {global_news[0]['content']}")
    if clarification:
        parts.append(f"[Brand Statement] {clarification[0]['content']}")
    for row in social[:2]:
        parts.append(f"[Social Feed] {row['content']}")
    prompt = (
        f"[Character Persona]\n{persona.to_profile()['persona']}\n"
        + "\n".join(parts)
        + "\nReturn semantic JSON including perceived_peer_approval."
    )
    return prompt, len(social)


async def _run_cognitive_condition(config) -> tuple[list[dict], dict]:
    nodes, edges = _directed_ba_edges(config.num_agents, 2, config.random_seed)
    successors = _successors(nodes, edges)
    reach = _reach_set(config, nodes, successors)
    personas = {row.agent_id: row for row in ENGINEERING_PERSONAS}
    states = {}
    for agent_id, persona in personas.items():
        trust = INITIAL_TRUST[persona.green_orientation]
        states[agent_id] = CognitiveState(
            baseline_trust=trust,
            trust=trust,
            attitude=trust / 10.0,
        )

    router = DeterministicFMCGSemanticRouterV32()
    incoming: dict[str, list[dict]] = {node: [] for node in nodes}
    records: list[dict] = []
    reach_tick = config.clarification_tick
    for tick in range(1, TOTAL_TICKS + 1):
        router.set_tick(tick)
        observations_by_agent = {
            agent_id: list(incoming[agent_id]) for agent_id in nodes
        }
        incoming = {node: [] for node in nodes}
        if tick == SCANDAL_TICK:
            for agent_id in nodes:
                observations_by_agent[agent_id].append(
                    {"source": "Global News", "content": CRISIS_STIMULUS}
                )
        if reach_tick == tick:
            for agent_id in reach:
                observations_by_agent[agent_id].append(
                    {
                        "source": "Enterprise_Clarification",
                        "content": CLARIFICATION_TEMPLATES[config.content_factor],
                    }
                )

        posts: dict[str, str] = {}
        for agent_id in nodes:
            persona = personas[agent_id]
            state = states[agent_id]
            observations = observations_by_agent[agent_id]
            had_observation = bool(observations)
            social_count = 0
            if had_observation:
                prompt, social_count = _semantic_prompt(persona, observations)
                payload = json.loads(await router.chat(prompt))
                semantic = validate_semantic_payload(
                    payload,
                    social_observation_count=social_count,
                )
            else:
                semantic = {
                    "valence": 0.0,
                    "arousal": 0.0,
                    "credibility": 0.5,
                    "evidence_strength": 0.0,
                    "topic_relevance": 0.0,
                    "perceived_empathy": 0.0,
                    "perceived_peer_approval": None,
                    "hypocrisy_perceived": False,
                    "importance": 0.0,
                    "reasoning": "",
                }
            clarification_observed = any(
                row["source"] == "Enterprise_Clarification" for row in observations
            )
            previous_sn = state.subjective_norm
            transition = update_psychological_state(
                baseline_trust=state.baseline_trust,
                previous_trust=state.trust,
                attitude_att=state.attitude,
                subjective_norm_sn=previous_sn,
                pbc=state.pbc,
                crisis_memory=state.crisis_memory,
                repair_memory=state.repair_memory,
                valence=semantic["valence"],
                arousal=semantic["arousal"],
                credibility=semantic["credibility"],
                evidence_strength=semantic["evidence_strength"],
                topic_relevance=semantic["topic_relevance"],
                had_observation=had_observation,
                social_observation_count=0,
                perceived_empathy=semantic["perceived_empathy"],
                enterprise_clarification_observed=clarification_observed,
            )
            updated_sn = update_subjective_norm(
                previous_sn=previous_sn,
                social_observation_count=social_count,
                perceived_peer_approval=semantic["perceived_peer_approval"],
            )
            purchase_intention = tpb_purchase_intention(
                attitude_att=transition["attitude_att"],
                subjective_norm_sn=updated_sn,
                pbc=state.pbc,
                trust=transition["trust_final"],
            )
            ticks_since_post = (
                None if state.last_post_tick is None else tick - state.last_post_tick
            )
            _, post_probability = behavior_probabilities(
                purchase_intention=purchase_intention,
                posting_intention=transition["posting_intention"],
                had_observation=had_observation,
                already_purchased=True,
                ticks_since_last_post=ticks_since_post,
            )
            post_draw = deterministic_uniform(
                CONTRACT_SEED, agent_id, tick, "post"
            )
            is_posting = post_draw < post_probability
            if is_posting:
                state.last_post_tick = tick
                posts[agent_id] = semantic["reasoning"] or "I am evaluating the brand."

            state.trust = transition["trust_final"]
            state.attitude = transition["attitude_att"]
            state.subjective_norm = updated_sn
            state.crisis_memory = transition["crisis_memory"]
            state.repair_memory = transition["repair_memory"]
            records.append(
                {
                    "scenario_schema_version": SCENARIO_SCHEMA,
                    "semantic_schema_version": SEMANTIC_SCHEMA,
                    "exp_id": config.exp_id,
                    "content_factor": config.content_factor,
                    "channel_factor": config.channel_factor,
                    "timing_factor": config.timing_factor,
                    "tick": tick,
                    "agent_id": agent_id,
                    "green_orientation": persona.green_orientation,
                    "category_purchase_frequency": persona.category_purchase_frequency,
                    "prior_brand_relationship": persona.prior_brand_relationship,
                    "price_sensitivity": persona.price_sensitivity,
                    "availability_friction": persona.availability_friction,
                    "social_posting_role": persona.social_posting_role,
                    "observation_present": had_observation,
                    "social_observation_count": social_count,
                    "perceived_peer_approval": semantic[
                        "perceived_peer_approval"
                    ],
                    "semantic_valence": semantic["valence"],
                    "semantic_arousal": semantic["arousal"],
                    "semantic_credibility": semantic["credibility"],
                    "semantic_evidence_strength": semantic["evidence_strength"],
                    "semantic_topic_relevance": semantic["topic_relevance"],
                    "semantic_perceived_empathy": semantic["perceived_empathy"],
                    "semantic_hypocrisy_perceived": semantic[
                        "hypocrisy_perceived"
                    ],
                    "subjective_norm_before": previous_sn,
                    "subjective_norm_after": updated_sn,
                    "attitude_att": transition["attitude_att"],
                    "pbc": state.pbc,
                    "trust_final": transition["trust_final"],
                    "purchase_intention": purchase_intention,
                    "posting_probability": post_probability,
                    "post_draw": post_draw,
                    "is_posting": is_posting,
                    "enterprise_clarification_observed": clarification_observed,
                    "semantic_fallback_used": False,
                    "plan_fallback_used": False,
                    "legacy_purchase_endpoint_retired": True,
                    "is_buying": False,
                }
            )

        for author_id, content in posts.items():
            for receiver_id in successors[author_id]:
                incoming[receiver_id].append(
                    {
                        "source": "Social",
                        "content": (
                            f'[Social Media Feed] Connection {author_id} posted: '
                            f'"{content}"'
                        ),
                    }
                )
        for agent_id in nodes:
            incoming[agent_id] = incoming[agent_id][-3:]

    return records, {
        "fake_router_calls": router.call_count,
        "fake_router_categories": dict(Counter(router.categories)),
        "reach_count": len(reach),
        "network_nodes": len(nodes),
        "network_edges": len(edges),
        "effective_event_timeline": [
            {"tick": SCANDAL_TICK, "content": CRISIS_STIMULUS}
        ],
    }


def _simulate_demand(cognitive_rows: list[dict], support_present: bool):
    exp_id = cognitive_rows[0]["exp_id"]
    cognitive = {
        (int(row["tick"]), row["agent_id"]): row for row in cognitive_rows
    }
    parameters = DemandParameters(
        micro_buyers_per_archetype=MICRO_BUYERS_PER_ARCHETYPE
    )
    cohorts = {
        persona.agent_id: build_scenario_micro_cohort(
            seed=CONTRACT_SEED,
            persona=persona,
            parameters=parameters,
        )
        for persona in ENGINEERING_PERSONAS
    }
    personas = {row.agent_id: row for row in ENGINEERING_PERSONAS}
    states = {
        profile.buyer_id: DemandState(loyalty=profile.initial_loyalty)
        for cohort in cohorts.values()
        for profile in cohort
    }
    rows = []
    tick_accumulator = {
        tick: {"opportunities": 0, "expected": 0.0, "chosen": 0}
        for tick in range(1, TOTAL_TICKS + 1)
    }
    cumulative_opportunities = 0
    cumulative_expected = 0.0
    cumulative_chosen = 0
    curves = []
    for tick in range(1, TOTAL_TICKS + 1):
        for persona in ENGINEERING_PERSONAS:
            psych = cognitive[(tick, persona.agent_id)]
            for profile in cohorts[persona.agent_id]:
                choice, next_state = purchase_step(
                    seed=CONTRACT_SEED,
                    tick=tick,
                    attitude_att=float(psych["attitude_att"]),
                    subjective_norm_sn=float(psych["subjective_norm_after"]),
                    trust=float(psych["trust_final"]),
                    profile=profile,
                    state=states[profile.buyer_id],
                    facilitation_present=support_present,
                    parameters=parameters,
                )
                states[profile.buyer_id] = next_state
                if not choice.opportunity:
                    continue
                tick_accumulator[tick]["opportunities"] += 1
                tick_accumulator[tick]["expected"] += choice.choice_probability
                tick_accumulator[tick]["chosen"] += int(choice.focal_brand_chosen)
                rows.append(
                    {
                        "scenario_schema_version": SCENARIO_SCHEMA,
                        "demand_adapter_schema_version": DEMAND_ADAPTER_SCHEMA,
                        "exp_id": exp_id,
                        "conversion_support": (
                            "present" if support_present else "absent"
                        ),
                        "tick": tick,
                        "agent_id": persona.agent_id,
                        "buyer_id": profile.buyer_id,
                        "micro_index": profile.micro_index,
                        "green_orientation": persona.green_orientation,
                        "category_purchase_frequency": persona.category_purchase_frequency,
                        "prior_brand_relationship": persona.prior_brand_relationship,
                        "price_sensitivity": persona.price_sensitivity,
                        "availability_friction": persona.availability_friction,
                        "opportunity_interval": profile.opportunity_interval,
                        "opportunity_phase": profile.opportunity_phase,
                        "preference_offset": profile.preference_offset,
                        "baseline_pbc": profile.baseline_pbc,
                        "current_pbc": choice.pbc,
                        "attitude_att": psych["attitude_att"],
                        "subjective_norm_sn": psych["subjective_norm_after"],
                        "trust": psych["trust_final"],
                        "purchase_intention": choice.purchase_intention,
                        "choice_probability": choice.choice_probability,
                        "choice_draw": choice.choice_draw,
                        "focal_brand_chosen": choice.focal_brand_chosen,
                        "loyalty_before": choice.loyalty_before,
                        "loyalty_after": choice.loyalty_after,
                    }
                )
        current = tick_accumulator[tick]
        cumulative_opportunities += current["opportunities"]
        cumulative_expected += current["expected"]
        cumulative_chosen += current["chosen"]
        curves.append(
            {
                "exp_id": exp_id,
                "conversion_support": (
                    "present" if support_present else "absent"
                ),
                "tick": tick,
                "opportunities": current["opportunities"],
                "expected_choice_share": (
                    current["expected"] / current["opportunities"]
                    if current["opportunities"]
                    else ""
                ),
                "realized_choice_share": (
                    current["chosen"] / current["opportunities"]
                    if current["opportunities"]
                    else ""
                ),
                "cumulative_opportunities": cumulative_opportunities,
                "cumulative_expected_choice_share": (
                    cumulative_expected / cumulative_opportunities
                    if cumulative_opportunities
                    else ""
                ),
                "cumulative_realized_choice_share": (
                    cumulative_chosen / cumulative_opportunities
                    if cumulative_opportunities
                    else ""
                ),
            }
        )
    return rows, curves


def _condition_summary(rows: list[dict]) -> dict:
    post = [row for row in rows if int(row["tick"]) >= SCANDAL_TICK]
    opportunities = len(post)
    expected = math.fsum(float(row["choice_probability"]) for row in post)
    chosen = sum(bool(row["focal_brand_chosen"]) for row in post)
    return {
        "exp_id": rows[0]["exp_id"],
        "conversion_support": rows[0]["conversion_support"],
        "post_crisis_opportunities": opportunities,
        "expected_choice_share": expected / opportunities,
        "realized_choice_share": chosen / opportunities,
        "expected_choices_per_1000": 1000.0 * expected / opportunities,
        "realized_choices_per_1000": 1000.0 * chosen / opportunities,
    }


def _schedule_signature(rows: list[dict]) -> dict[tuple, tuple]:
    return {
        (row["agent_id"], row["buyer_id"], int(row["tick"])): (
            int(row["opportunity_interval"]),
            int(row["opportunity_phase"]),
            float(row["choice_draw"]),
        )
        for row in rows
    }


def _pre_signature(rows: list[dict]) -> list[tuple]:
    return [
        (
            int(row["tick"]),
            row["buyer_id"],
            float(row["current_pbc"]),
            float(row["choice_probability"]),
            float(row["choice_draw"]),
            bool(row["focal_brand_chosen"]),
            float(row["loyalty_before"]),
            float(row["loyalty_after"]),
        )
        for row in rows
        if int(row["tick"]) < SCANDAL_TICK
    ]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gate = GateReport()
    configs = [
        config.__class__(
            content_factor=config.content_factor,
            channel_factor=config.channel_factor,
            timing_factor=config.timing_factor,
            budget_k=config.budget_k,
            random_seed=CONTRACT_SEED,
            num_agents=20,
            total_ticks=TOTAL_TICKS,
            scandal_tick=SCANDAL_TICK,
        )
        for config in generate_experiment_matrix()
    ]

    import asyncio

    cognitive_by_condition = {}
    runtime_meta = {}
    for config in configs:
        rows, meta = asyncio.run(_run_cognitive_condition(config))
        cognitive_by_condition[config.exp_id] = rows
        runtime_meta[config.exp_id] = meta
    cognitive_rows = [
        row for config in configs for row in cognitive_by_condition[config.exp_id]
    ]

    demand_by_condition = {}
    curve_rows = []
    summary_rows = []
    for config in configs:
        for support_present in (False, True):
            rows, curves = _simulate_demand(
                cognitive_by_condition[config.exp_id], support_present
            )
            key = (
                config.exp_id,
                "present" if support_present else "absent",
            )
            demand_by_condition[key] = rows
            curve_rows.extend(curves)
            summary_rows.append(_condition_summary(rows))
    demand_rows = [
        row
        for config in configs
        for support in ("absent", "present")
        for row in demand_by_condition[(config.exp_id, support)]
    ]

    gate.check("nine cognitive conditions", len(cognitive_by_condition) == 9)
    gate.check("eighteen demand conditions", len(demand_by_condition) == 18)
    gate.check(
        "600 unique cognitive rows per condition",
        all(
            len(rows) == 600
            and len({(row["tick"], row["agent_id"]) for row in rows}) == 600
            for rows in cognitive_by_condition.values()
        ),
    )
    gate.check(
        "no semantic or plan fallback",
        not any(
            row["semantic_fallback_used"] or row["plan_fallback_used"]
            for row in cognitive_rows
        ),
    )
    gate.check(
        "fictional Tick-5 event only",
        all(
            [entry["tick"] for entry in meta["effective_event_timeline"]] == [5]
            and "VerdantCo Oat" in meta["effective_event_timeline"][0]["content"]
            for meta in runtime_meta.values()
        ),
    )
    gate.check(
        "peer approval null without social observations",
        all(
            row["perceived_peer_approval"] is None
            for row in cognitive_rows
            if int(row["social_observation_count"]) == 0
        ),
    )
    social_rows = [
        row for row in cognitive_rows if int(row["social_observation_count"]) > 0
    ]
    gate.check(
        "peer approval numeric with social observations",
        bool(social_rows)
        and all(
            row["perceived_peer_approval"] is not None
            and 0.0 <= float(row["perceived_peer_approval"]) <= 1.0
            for row in social_rows
        ),
        {"social_rows": len(social_rows)},
    )
    gate.check(
        "SN unchanged without social observations",
        all(
            abs(
                float(row["subjective_norm_after"])
                - float(row["subjective_norm_before"])
            )
            <= 1e-14
            for row in cognitive_rows
            if int(row["social_observation_count"]) == 0
        ),
    )
    gate.check(
        "SN peer pathway exercised",
        any(
            abs(
                float(row["subjective_norm_after"])
                - float(row["subjective_norm_before"])
            )
            > 1e-12
            for row in social_rows
        ),
    )
    gate.check(
        "legacy cumulative purchase endpoint retired",
        all(
            row["legacy_purchase_endpoint_retired"] and not row["is_buying"]
            for row in cognitive_rows
        ),
    )

    schedules = [_schedule_signature(rows) for rows in demand_by_condition.values()]
    gate.check(
        "opportunity schedules and draws condition invariant",
        all(signature == schedules[0] for signature in schedules[1:]),
    )
    pre = [_pre_signature(rows) for rows in demand_by_condition.values()]
    gate.check(
        "all eighteen demand conditions align before crisis",
        all(signature == pre[0] for signature in pre[1:]),
    )
    gate.check(
        "choice probabilities and PBC in bounds",
        all(
            0.0 <= float(row["choice_probability"]) <= 1.0
            and 0.0 <= float(row["current_pbc"]) <= 1.0
            for row in demand_rows
        ),
    )
    repeat_counts = Counter(
        (row["exp_id"], row["conversion_support"], row["buyer_id"])
        for row in demand_rows
        if bool(row["focal_brand_chosen"])
    )
    gate.check(
        "repeat focal-brand choices occur",
        any(count > 1 for count in repeat_counts.values()),
    )

    support_gate = True
    for config in configs:
        absent = {
            (row["buyer_id"], row["tick"]): row
            for row in demand_by_condition[(config.exp_id, "absent")]
        }
        present = {
            (row["buyer_id"], row["tick"]): row
            for row in demand_by_condition[(config.exp_id, "present")]
        }
        for key, base_row in absent.items():
            support_row = present[key]
            tick = int(base_row["tick"])
            if any(
                base_row[field] != support_row[field]
                for field in ("attitude_att", "subjective_norm_sn", "trust")
            ):
                support_gate = False
            pbc_equal = math.isclose(
                float(base_row["current_pbc"]),
                float(support_row["current_pbc"]),
                rel_tol=0.0,
                abs_tol=1e-15,
            )
            if 6 <= tick <= 19:
                if float(support_row["current_pbc"]) < float(base_row["current_pbc"]):
                    support_gate = False
            elif not pbc_equal:
                support_gate = False
    gate.check("conversion support obeys PBC-only window", support_gate)

    base_rows = cognitive_by_condition["NoClarification-Control"]
    replay_a, _ = _simulate_demand(base_rows, False)
    replay_b, _ = _simulate_demand(base_rows, False)
    gate.check("demand audit exactly reproducible", replay_a == replay_b)

    _write_csv(COGNITIVE_PATH, cognitive_rows)
    _write_csv(DEMAND_PATH, demand_rows)
    _write_csv(CURVE_PATH, curve_rows)
    _write_csv(SUMMARY_PATH, summary_rows)
    with PROFILE_PATH.open("w", encoding="utf-8") as handle:
        for persona in ENGINEERING_PERSONAS:
            handle.write(json.dumps(persona.to_profile(), sort_keys=True) + "\n")

    kernel_missing = [
        package
        for package in ("networkx", "agentkernel_standalone")
        if importlib.util.find_spec(package) is None
    ]
    output_paths = [
        COGNITIVE_PATH,
        DEMAND_PATH,
        CURVE_PATH,
        SUMMARY_PATH,
        PROFILE_PATH,
    ]
    payload = {
        "schema_version": "fmcg_v32_fake_model_smoke_result1.0",
        "offline_result": "PASS" if gate.passed else "FAIL",
        "overall_release_status": (
            "PASS_OFFLINE_KERNEL_PENDING" if gate.passed else "BLOCKED_OFFLINE_FAILURE"
        ),
        "scenario_schema_version": SCENARIO_SCHEMA,
        "semantic_schema_version": SEMANTIC_SCHEMA,
        "demand_adapter_schema_version": DEMAND_ADAPTER_SCHEMA,
        "diagnostic_seed": CONTRACT_SEED,
        "cognitive_conditions": len(cognitive_by_condition),
        "demand_conditions": len(demand_by_condition),
        "cognitive_rows": len(cognitive_rows),
        "demand_opportunity_rows": len(demand_rows),
        "curve_rows": len(curve_rows),
        "fake_semantic_calls": sum(
            meta["fake_router_calls"] for meta in runtime_meta.values()
        ),
        "real_llm_calls": 0,
        "external_api_calls": 0,
        "p_values_computed": False,
        "effect_size_acceptance_gate": False,
        "formal_reuse_forbidden": True,
        "engineering_pilot_authorized": False,
        "kernel_runtime_executed": False,
        "kernel_runtime_status": (
            "BLOCKED_MISSING_DEPENDENCIES" if kernel_missing else "PENDING_SEPARATE_GATE"
        ),
        "kernel_missing_dependencies": kernel_missing,
        "runtime_meta": runtime_meta,
        "mapping_audit": mapping_audit_payload(),
        "gates": gate.rows,
        "output_sha256": {
            str(path.relative_to(ROOT)): _sha256(path) for path in output_paths
        },
        "condition_summaries": summary_rows,
    }
    RESULT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "offline_result": payload["offline_result"],
        "cognitive_rows": len(cognitive_rows),
        "demand_opportunity_rows": len(demand_rows),
        "fake_semantic_calls": payload["fake_semantic_calls"],
        "kernel_runtime_status": payload["kernel_runtime_status"],
    }, sort_keys=True))
    return 0 if gate.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
