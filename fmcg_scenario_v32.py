"""Scenario-aligned fictional FMCG assets for TASK_005 v3.2.

These assets are parallel prototypes.  Importing this module performs no model
call and does not alter the active mechanism-v2 experiment path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


SCHEMA = "fmcg-scenario-3.2"
FOCAL_BRAND = "VerdantCo Oat"
PRODUCT_CATEGORY = "plant-based milk"

CRISIS_STIMULUS = (
    "[Hypothetical experimental stimulus; wholly fictional brand and event] "
    "VerdantCo Oat is a fictional plant-based-milk brand that has built its "
    "identity around lower-impact everyday consumption. A hypothetical report "
    "states that the brand accepted a minority equity investment from a "
    "fictional investment group criticised within the scenario for holding "
    "environmentally controversial assets. The investor has no majority "
    "ownership and no board control over VerdantCo Oat's sustainability policy, "
    "but category buyers question whether the relationship is consistent with "
    "the brand's environmental claims. Some regular buyers are considering a "
    "different plant-based-milk brand at their next category-purchase occasion. "
    "This vignette does not refer to any real company, investor, person, report "
    "or public event."
)

SHARED_CLARIFICATION_FACTS = (
    "The fictional investor holds only a minority stake.",
    "The investor has no board control over VerdantCo Oat's sustainability policy.",
    "VerdantCo Oat's prior communication about the relationship was insufficient.",
    "Partnership-governance information will be published for inspection.",
    "An independent sustainability review will be published.",
    "A future-investment review safeguard will be used before a similar partnership.",
    "Trust must be rebuilt through observable actions rather than slogans.",
)


def _fact_block() -> str:
    return " ".join(
        f"Fact {index}: {fact}" for index, fact in enumerate(SHARED_CLARIFICATION_FACTS, 1)
    )


CLARIFICATION_TEMPLATES = {
    "rational-evidence": (
        "[Hypothetical experimental stimulus; wholly fictional brand and event] "
        "VerdantCo Oat provides a structured response for regular plant-based-milk "
        "buyers. The response prioritises verification, auditability, procedural "
        "transparency and evidence that consumers can inspect. "
        + _fact_block()
    ),
    "emotional-empathy": (
        "[Hypothetical experimental stimulus; wholly fictional brand and event] "
        "VerdantCo Oat acknowledges why regular plant-based-milk buyers may feel "
        "frustrated, misled or uncertain about choosing the brand again. The "
        "response prioritises responsibility, care, relationship repair and the "
        "consumer concern created by the controversy. "
        + _fact_block()
    ),
}

CONVERSION_SUPPORT_STIMULUS = (
    "[Hypothetical operational offer; wholly fictional brand] From Tick 6 through "
    "Tick 19, VerdantCo Oat offers one price-protection voucher redeemable on the "
    "buyer's next plant-based-milk purchase and a verified store-availability "
    "service. The offer does not contain a crisis explanation, sustainability "
    "claim, apology, endorsement or evidence statement."
)


@dataclass(frozen=True)
class EngineeringPersona:
    agent_id: str
    green_orientation: str
    category_purchase_frequency: str
    prior_brand_relationship: str
    price_sensitivity: str
    availability_friction: str
    social_posting_role: str

    def to_profile(self) -> dict:
        relationship_text = {
            "loyal": "I usually choose VerdantCo Oat when it is available.",
            "repertoire": "I rotate among several plant-based-milk brands, including VerdantCo Oat.",
            "non-user": "I buy plant-based milk but do not currently choose VerdantCo Oat.",
        }[self.prior_brand_relationship]
        persona = (
            f"I am a regular plant-based-milk category buyer in the "
            f"{self.green_orientation} green-orientation segment. "
            f"My usual category-purchase interval is {self.category_purchase_frequency}. "
            f"{relationship_text} My price sensitivity is {self.price_sensitivity}, "
            f"my retail-availability friction is {self.availability_friction}, and "
            f"my social posting role is {self.social_posting_role}. I evaluate the "
            "actual message I observe and may respond positively, neutrally or negatively."
        )
        return {
            "id": self.agent_id,
            "name": self.agent_id,
            "scenario_schema": SCHEMA,
            # The production Builder and network audit read these two fields.
            # They mirror the explicitly declared scenario fields; they do not
            # create a second, hidden segmentation scheme.
            "psychology": {
                "cluster_type": self.green_orientation,
                "social_role": self.social_posting_role,
            },
            "consumer_context": asdict(self),
            "persona": persona,
        }


_GREEN = ("Non_Greens", "Convenient_Greens", "Active_Greens", "Dormant_Greens")
_FREQUENCY = ("5-7 days", "7-10 days", "10-14 days", "14-28 days")
_RELATIONSHIP = ("loyal", "repertoire", "non-user")
_SENSITIVITY = ("low", "medium", "high")
_FRICTION = ("low", "medium", "high")


def _build_engineering_personas() -> tuple[EngineeringPersona, ...]:
    rows = []
    for index in range(20):
        rows.append(
            EngineeringPersona(
                agent_id=f"Consumer_{index:03d}",
                green_orientation=_GREEN[index % len(_GREEN)],
                category_purchase_frequency=_FREQUENCY[(3 * index + index // 4) % len(_FREQUENCY)],
                prior_brand_relationship=_RELATIONSHIP[(2 * index + index // 4) % len(_RELATIONSHIP)],
                price_sensitivity=_SENSITIVITY[(index + 2 * (index // 4)) % len(_SENSITIVITY)],
                availability_friction=_FRICTION[(2 * index + index // 5) % len(_FRICTION)],
                social_posting_role=(
                    "Frequent Poster" if index % 3 == 0 else "Regular User"
                ),
            )
        )
    return tuple(rows)


ENGINEERING_PERSONAS = _build_engineering_personas()


def engineering_profiles() -> tuple[dict, ...]:
    """Return a balanced mechanism-coverage panel, never population weights."""

    return tuple(row.to_profile() for row in ENGINEERING_PERSONAS)


def engineering_persona_by_id() -> dict[str, EngineeringPersona]:
    """Return the immutable engineering panel keyed by production agent id."""

    return {row.agent_id: row for row in ENGINEERING_PERSONAS}
