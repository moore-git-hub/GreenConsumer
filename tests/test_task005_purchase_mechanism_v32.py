from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fmcg_scenario_v32 as scenario
import purchase_mechanism_v31 as demand
import purchase_mechanism_v32 as adapter


class PurchaseMechanismV32Tests(unittest.TestCase):
    def setUp(self):
        self.parameters = demand.DemandParameters()
        self.personas = scenario.engineering_persona_by_id()

    def _cohort(self, relationship):
        persona = next(
            row
            for row in scenario.ENGINEERING_PERSONAS
            if row.prior_brand_relationship == relationship
        )
        return adapter.build_scenario_micro_cohort(
            seed=53201,
            persona=persona,
            parameters=self.parameters,
        )

    def test_frequency_strata_constrain_every_opportunity_interval(self):
        for persona in scenario.ENGINEERING_PERSONAS:
            cohort = adapter.build_scenario_micro_cohort(
                seed=53201,
                persona=persona,
                parameters=self.parameters,
            )
            allowed = set(
                adapter.FREQUENCY_INTERVALS[
                    persona.category_purchase_frequency
                ]
            )
            self.assertEqual(len(cohort), 25)
            self.assertTrue(
                {profile.opportunity_interval for profile in cohort} <= allowed
            )

    def test_relationship_ordering_is_present_but_not_deterministic_choice(self):
        means = {}
        loyalty = {}
        for relationship in ("loyal", "repertoire", "non-user"):
            cohort = self._cohort(relationship)
            means[relationship] = math.fsum(
                row.preference_offset for row in cohort
            ) / len(cohort)
            loyalty[relationship] = math.fsum(
                row.initial_loyalty for row in cohort
            ) / len(cohort)
            self.assertTrue(
                any(-1.0 < row.initial_loyalty < 1.0 for row in cohort)
            )
        self.assertGreater(means["loyal"], means["repertoire"])
        self.assertGreater(means["repertoire"], means["non-user"])
        self.assertGreater(loyalty["loyal"], loyalty["repertoire"])
        self.assertGreater(loyalty["repertoire"], loyalty["non-user"])

    def test_pbc_ordering_uses_declared_price_and_availability_fields(self):
        base = next(iter(scenario.ENGINEERING_PERSONAS))
        low = scenario.EngineeringPersona(
            **{
                **base.__dict__,
                "agent_id": "LowFriction",
                "price_sensitivity": "low",
                "availability_friction": "low",
            }
        )
        high = scenario.EngineeringPersona(
            **{
                **base.__dict__,
                "agent_id": "HighFriction",
                "price_sensitivity": "high",
                "availability_friction": "high",
            }
        )
        low_rows = adapter.build_scenario_micro_cohort(
            seed=53201, persona=low, parameters=self.parameters
        )
        high_rows = adapter.build_scenario_micro_cohort(
            seed=53201, persona=high, parameters=self.parameters
        )
        self.assertGreater(
            math.fsum(row.baseline_pbc for row in low_rows) / len(low_rows),
            math.fsum(row.baseline_pbc for row in high_rows) / len(high_rows),
        )

    def test_scenario_cohort_is_exactly_reproducible(self):
        persona = scenario.ENGINEERING_PERSONAS[3]
        first = adapter.build_scenario_micro_cohort(
            seed=53201, persona=persona, parameters=self.parameters
        )
        second = adapter.build_scenario_micro_cohort(
            seed=53201, persona=persona, parameters=self.parameters
        )
        self.assertEqual(first, second)

    def test_mapping_audit_discloses_noncalibration(self):
        payload = adapter.mapping_audit_payload()
        self.assertFalse(payload["empirically_calibrated"])
        self.assertEqual(payload["schema_version"], adapter.SCHEMA)


if __name__ == "__main__":
    unittest.main()
