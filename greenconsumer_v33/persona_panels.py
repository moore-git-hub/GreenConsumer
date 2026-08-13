"""Nested mechanism-coverage persona panels for TASK_005 v3.3.1 size checks.

These panels are engineering design objects, not empirical population samples.
N=20 exactly preserves the frozen EngineeringPersona panel. N=40/N=80 add
unique categorical profiles while preserving the N=20 marginal proportions.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import product

from fmcg_scenario_v32 import ENGINEERING_PERSONAS, EngineeringPersona

PANEL_SCHEMA = "task005_fmcg_v331_nested_persona_panel1.0"
SUPPORTED_SIZES = (20, 40, 80)

_GREEN = ("Non_Greens", "Convenient_Greens", "Active_Greens", "Dormant_Greens")
_FREQUENCY = ("5-7 days", "7-10 days", "10-14 days", "14-28 days")
_RELATIONSHIP = ("loyal", "repertoire", "non-user")
_SENSITIVITY = ("low", "medium", "high")
_FRICTION = ("low", "medium", "high")
_POSTING = ("Frequent Poster", "Regular User")
_LEVELS = (_GREEN, _FREQUENCY, _RELATIONSHIP, _SENSITIVITY, _FRICTION, _POSTING)


def persona_tuple(persona: EngineeringPersona) -> tuple[str, ...]:
    return (
        persona.green_orientation,
        persona.category_purchase_frequency,
        persona.prior_brand_relationship,
        persona.price_sensitivity,
        persona.availability_friction,
        persona.social_posting_role,
    )


def _target_counts(size: int) -> list[dict[str, int]]:
    if int(size) not in SUPPORTED_SIZES:
        raise ValueError(f"size must be one of {SUPPORTED_SIZES}; got {size}")
    multiplier = int(size) // len(ENGINEERING_PERSONAS)
    baseline = [Counter(persona_tuple(p)[j] for p in ENGINEERING_PERSONAS) for j in range(6)]
    return [
        {level: int(baseline[j][level]) * multiplier for level in _LEVELS[j]}
        for j in range(6)
    ]


def build_nested_persona_panel(size: int) -> tuple[EngineeringPersona, ...]:
    """Return the deterministic N=20/40/80 nested mechanism-coverage panel."""

    size = int(size)
    if size not in SUPPORTED_SIZES:
        raise ValueError(f"size must be one of {SUPPORTED_SIZES}; got {size}")
    if size == len(ENGINEERING_PERSONAS):
        return tuple(ENGINEERING_PERSONAS)

    selected = [persona_tuple(p) for p in ENGINEERING_PERSONAS]
    selected_set = set(selected)
    targets = _target_counts(size)
    current = [Counter(row[j] for row in selected) for j in range(6)]
    remaining = [
        {level: int(targets[j][level] - current[j][level]) for level in _LEVELS[j]}
        for j in range(6)
    ]

    pair_counts: dict[tuple, int] = defaultdict(int)
    for row in selected:
        for a in range(6):
            for b in range(a + 1, 6):
                pair_counts[(a, row[a], b, row[b])] += 1

    universe = tuple(product(*_LEVELS))
    while len(selected) < size:
        candidates = []
        for row in universe:
            if row in selected_set:
                continue
            if any(remaining[j][row[j]] <= 0 for j in range(6)):
                continue

            need_score = sum(
                remaining[j][row[j]] / max(1, targets[j][row[j]])
                for j in range(6)
            )
            pairwise_novelty = sum(
                1.0 / (1.0 + pair_counts[(a, row[a], b, row[b])])
                for a in range(6)
                for b in range(a + 1, 6)
            )
            candidates.append((need_score, pairwise_novelty, row))

        if not candidates:
            raise RuntimeError(
                f"persona panel construction became infeasible at n={len(selected)} for target {size}"
            )

        max_need = max(item[0] for item in candidates)
        best_need = [item for item in candidates if abs(item[0] - max_need) <= 1e-12]
        max_novelty = max(item[1] for item in best_need)
        best = [item[2] for item in best_need if abs(item[1] - max_novelty) <= 1e-12]
        chosen = min(best)

        selected.append(chosen)
        selected_set.add(chosen)
        for j in range(6):
            remaining[j][chosen[j]] -= 1
        for a in range(6):
            for b in range(a + 1, 6):
                pair_counts[(a, chosen[a], b, chosen[b])] += 1

    panel = []
    for index, row in enumerate(selected):
        if index < len(ENGINEERING_PERSONAS):
            panel.append(ENGINEERING_PERSONAS[index])
            continue
        panel.append(
            EngineeringPersona(
                agent_id=f"Consumer_{index:03d}",
                green_orientation=row[0],
                category_purchase_frequency=row[1],
                prior_brand_relationship=row[2],
                price_sensitivity=row[3],
                availability_friction=row[4],
                social_posting_role=row[5],
            )
        )

    validate_persona_panel(tuple(panel), expected_size=size)
    return tuple(panel)


def validate_persona_panel(panel: tuple[EngineeringPersona, ...], *, expected_size: int) -> None:
    expected_size = int(expected_size)
    if len(panel) != expected_size:
        raise ValueError(f"panel length {len(panel)} != expected_size {expected_size}")
    ids = [p.agent_id for p in panel]
    expected_ids = [f"Consumer_{index:03d}" for index in range(expected_size)]
    if ids != expected_ids:
        raise ValueError("persona IDs must be sequential and deterministic")

    tuples = [persona_tuple(p) for p in panel]
    if len(set(tuples)) != len(tuples):
        raise ValueError("persona panel contains duplicate six-attribute tuples")

    targets = _target_counts(expected_size)
    for j in range(6):
        observed = Counter(row[j] for row in tuples)
        if observed != Counter(targets[j]):
            raise ValueError(
                f"persona marginal target mismatch on dimension {j}: observed={observed}, target={targets[j]}"
            )

    baseline = tuple(ENGINEERING_PERSONAS)
    if tuple(panel[: len(baseline)]) != baseline:
        raise ValueError("N20 baseline persona prefix was not preserved exactly")


def panel_audit_rows(panel: tuple[EngineeringPersona, ...]) -> list[dict]:
    return [
        {
            "panel_schema": PANEL_SCHEMA,
            "panel_size": len(panel),
            "agent_id": p.agent_id,
            "green_orientation": p.green_orientation,
            "category_purchase_frequency": p.category_purchase_frequency,
            "prior_brand_relationship": p.prior_brand_relationship,
            "price_sensitivity": p.price_sensitivity,
            "availability_friction": p.availability_friction,
            "social_posting_role": p.social_posting_role,
            "baseline_n20_member": index < len(ENGINEERING_PERSONAS),
        }
        for index, p in enumerate(panel)
    ]


def panel_marginal_rows(panel: tuple[EngineeringPersona, ...]) -> list[dict]:
    names = (
        "green_orientation",
        "category_purchase_frequency",
        "prior_brand_relationship",
        "price_sensitivity",
        "availability_friction",
        "social_posting_role",
    )
    tuples = [persona_tuple(p) for p in panel]
    rows = []
    for j, name in enumerate(names):
        counts = Counter(row[j] for row in tuples)
        for level in _LEVELS[j]:
            rows.append(
                {
                    "panel_schema": PANEL_SCHEMA,
                    "panel_size": len(panel),
                    "dimension": name,
                    "level": level,
                    "count": int(counts[level]),
                    "share": float(counts[level] / len(panel)),
                }
            )
    return rows
