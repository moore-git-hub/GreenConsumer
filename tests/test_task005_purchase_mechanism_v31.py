from __future__ import annotations

import inspect
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import purchase_mechanism_v31 as p31


class PurchaseMechanismV31Tests(unittest.TestCase):
    def setUp(self):
        self.params = p31.DemandParameters()
        self.cohort = p31.build_micro_cohort(
            seed=91,
            archetype_id="Consumer_001",
            archetype_pbc=0.5,
            parameters=self.params,
        )

    def test_balanced_micro_heterogeneity_preserves_centres(self):
        self.assertEqual(len(self.cohort), 25)
        self.assertAlmostEqual(
            math.fsum(row.preference_offset for row in self.cohort) / 25,
            0.0,
            places=14,
        )
        self.assertAlmostEqual(
            math.fsum(row.baseline_pbc for row in self.cohort) / 25,
            0.5,
            places=14,
        )
        self.assertAlmostEqual(
            math.fsum(row.initial_loyalty for row in self.cohort) / 25,
            0.0,
            places=14,
        )

    def test_profile_and_opportunities_are_reproducible(self):
        again = p31.build_micro_cohort(
            seed=91,
            archetype_id="Consumer_001",
            archetype_pbc=0.5,
            parameters=self.params,
        )
        self.assertEqual(self.cohort, again)
        schedule_a = {
            row.buyer_id: [
                tick for tick in range(1, 31) if p31.is_purchase_opportunity(row, tick)
            ]
            for row in self.cohort
        }
        schedule_b = {
            row.buyer_id: [
                tick for tick in range(1, 31) if p31.is_purchase_opportunity(row, tick)
            ]
            for row in again
        }
        self.assertEqual(schedule_a, schedule_b)
        self.assertEqual(
            {row.opportunity_interval for row in self.cohort},
            {5, 7, 10, 14},
        )

    def test_no_effect_setting_collapses_to_tpb_intention(self):
        params = p31.no_effect_parameters(micro_buyers_per_archetype=1)
        profile = p31.build_micro_profile(
            seed=5,
            archetype_id="Consumer_000",
            micro_index=0,
            archetype_pbc=0.5,
            parameters=params,
        )
        intention, probability = p31.focal_choice_probability(
            attitude_att=0.63,
            subjective_norm_sn=0.48,
            pbc=0.5,
            trust=6.2,
            profile=profile,
            state=p31.DemandState(loyalty=0.0),
            parameters=params,
        )
        self.assertAlmostEqual(probability, intention, places=14)

    def test_facilitation_changes_pbc_only_inside_frozen_window(self):
        profile = self.cohort[0]
        baseline = profile.baseline_pbc
        before = p31.current_pbc(
            profile=profile,
            tick=5,
            facilitation_present=True,
            parameters=self.params,
        )
        active = p31.current_pbc(
            profile=profile,
            tick=6,
            facilitation_present=True,
            parameters=self.params,
        )
        after = p31.current_pbc(
            profile=profile,
            tick=20,
            facilitation_present=True,
            parameters=self.params,
        )
        absent = p31.current_pbc(
            profile=profile,
            tick=6,
            facilitation_present=False,
            parameters=self.params,
        )
        self.assertEqual(before, baseline)
        self.assertGreater(active, baseline)
        self.assertEqual(after, baseline)
        self.assertEqual(absent, baseline)

    def test_probability_is_monotone_in_facilitation_for_fixed_state(self):
        profile = self.cohort[0]
        state = p31.DemandState(loyalty=profile.initial_loyalty)
        base_pbc = p31.current_pbc(
            profile=profile,
            tick=7,
            facilitation_present=False,
            parameters=self.params,
        )
        high_pbc = p31.current_pbc(
            profile=profile,
            tick=7,
            facilitation_present=True,
            parameters=self.params,
        )
        _, low = p31.focal_choice_probability(
            attitude_att=0.55,
            subjective_norm_sn=0.49,
            pbc=base_pbc,
            trust=5.9,
            profile=profile,
            state=state,
            parameters=self.params,
        )
        _, high = p31.focal_choice_probability(
            attitude_att=0.55,
            subjective_norm_sn=0.49,
            pbc=high_pbc,
            trust=5.9,
            profile=profile,
            state=state,
            parameters=self.params,
        )
        self.assertGreaterEqual(high, low)

    def test_repeat_choice_updates_but_does_not_absorb(self):
        profile = self.cohort[0]
        state = p31.DemandState(loyalty=profile.initial_loyalty)
        opportunity_count = 0
        choice_count = 0
        for tick in range(1, 61):
            result, state = p31.purchase_step(
                seed=91,
                tick=tick,
                attitude_att=1.0,
                subjective_norm_sn=1.0,
                trust=10.0,
                profile=profile,
                state=state,
                facilitation_present=False,
                parameters=self.params,
            )
            opportunity_count += int(result.opportunity)
            choice_count += int(result.focal_brand_chosen)
        self.assertGreater(opportunity_count, 3)
        self.assertGreater(choice_count, 1)

    def test_common_draw_is_invariant_to_psychological_state(self):
        profile = next(
            row for row in self.cohort if p31.is_purchase_opportunity(row, 10)
        )
        low, _ = p31.purchase_step(
            seed=91,
            tick=10,
            attitude_att=0.2,
            subjective_norm_sn=0.2,
            trust=2.0,
            profile=profile,
            state=p31.DemandState(loyalty=0.0),
            facilitation_present=False,
            parameters=self.params,
        )
        high, _ = p31.purchase_step(
            seed=91,
            tick=10,
            attitude_att=0.8,
            subjective_norm_sn=0.8,
            trust=8.0,
            profile=profile,
            state=p31.DemandState(loyalty=0.0),
            facilitation_present=True,
            parameters=self.params,
        )
        self.assertTrue(low.opportunity and high.opportunity)
        self.assertEqual(low.choice_draw, high.choice_draw)
        self.assertGreater(high.choice_probability, low.choice_probability)

    def test_module_contains_no_communication_winner_labels(self):
        source = inspect.getsource(p31).lower()
        for forbidden in (
            "rational-evidence",
            "emotional-empathy",
            "no-clarification",
            "hub",
            "random",
            "immediate",
            "delayed",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
