from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import purchase_mechanism_v3 as p3


class PurchaseMechanismV3Tests(unittest.TestCase):
    def test_opportunities_are_reproducible_and_condition_free(self):
        ticks_a = [
            tick
            for tick in range(1, 31)
            if p3.is_post_crisis_purchase_opportunity(
                seed=91, agent_id="Consumer_001", tick=tick
            )
        ]
        ticks_b = [
            tick
            for tick in range(1, 31)
            if p3.is_post_crisis_purchase_opportunity(
                seed=91, agent_id="Consumer_001", tick=tick
            )
        ]
        self.assertEqual(ticks_a, ticks_b)
        self.assertIn(len(ticks_a), (3, 4))
        self.assertTrue(all(tick > 5 for tick in ticks_a))
        self.assertTrue(all(b - a == 7 for a, b in zip(ticks_a, ticks_a[1:])))

    def test_choice_is_conditional_on_opportunity(self):
        rows = [
            p3.purchase_choice(
                seed=91,
                agent_id="Consumer_001",
                tick=tick,
                purchase_intention=0.63,
            )
            for tick in range(1, 31)
        ]
        opportunities = [row for row in rows if row.opportunity]
        non_opportunities = [row for row in rows if not row.opportunity]
        self.assertIn(len(opportunities), (3, 4))
        self.assertTrue(all(row.choice_probability == 0.63 for row in opportunities))
        self.assertTrue(all(row.choice_draw is not None for row in opportunities))
        self.assertTrue(all(row.choice_probability is None for row in non_opportunities))
        self.assertTrue(all(row.choice_draw is None for row in non_opportunities))

    def test_repeat_choice_is_not_absorbing(self):
        opportunities = [
            p3.purchase_choice(
                seed=33,
                agent_id="Consumer_002",
                tick=tick,
                purchase_intention=1.0,
            )
            for tick in range(1, 31)
        ]
        chosen = [row for row in opportunities if row.focal_brand_chosen]
        self.assertGreaterEqual(len(chosen), 3)

    def test_pbc_requires_separate_observed_facilitation(self):
        unchanged = p3.update_pbc_from_facilitation(
            previous_pbc=0.5,
            facilitation_observed=False,
            facilitation_signal=1.0,
            update_rate=1.0,
        )
        changed = p3.update_pbc_from_facilitation(
            previous_pbc=0.5,
            facilitation_observed=True,
            facilitation_signal=0.8,
            update_rate=0.25,
        )
        self.assertEqual(unchanged, 0.5)
        self.assertGreater(changed, unchanged)

    def test_tpb_equation_is_monotone_without_winner_labels(self):
        base = dict(attitude_att=0.5, subjective_norm_sn=0.5, pbc=0.5, trust=5.0)
        low = p3.tpb_purchase_intention(**base)
        high = p3.tpb_purchase_intention(**{**base, "trust": 6.0})
        self.assertGreater(high, low)
        source = inspect.getsource(p3).lower()
        for forbidden in (
            "rational-evidence",
            "emotional-empathy",
            "hub",
            "random",
            "immediate",
            "delayed",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
