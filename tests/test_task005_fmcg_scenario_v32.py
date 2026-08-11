from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fmcg_scenario_v32 as scenario
import mechanism_v31_cognition as cognition
import mechanism_v32_semantics as semantics


class FMCGScenarioV32Tests(unittest.TestCase):
    def test_scenario_is_product_specific_and_fictional(self):
        text = " ".join(
            [
                scenario.CRISIS_STIMULUS,
                *scenario.CLARIFICATION_TEMPLATES.values(),
                scenario.CONVERSION_SUPPORT_STIMULUS,
            ]
        )
        self.assertIn("plant-based-milk", text)
        self.assertIn("fictional", text.lower())
        self.assertNotIn("Oatly", text)
        self.assertNotIn("Blackstone", text)

    def test_clarifications_share_all_stipulated_facts(self):
        rational = scenario.CLARIFICATION_TEMPLATES["rational-evidence"]
        empathy = scenario.CLARIFICATION_TEMPLATES["emotional-empathy"]
        for fact in scenario.SHARED_CLARIFICATION_FACTS:
            self.assertIn(fact, rational)
            self.assertIn(fact, empathy)

    def test_conversion_support_is_construct_separated(self):
        support = scenario.CONVERSION_SUPPORT_STIMULUS.lower()
        self.assertIn("voucher", support)
        self.assertIn("availability", support)
        self.assertIn(
            "does not contain a crisis explanation, sustainability claim, apology, endorsement",
            support,
        )

    def test_engineering_panel_has_required_coverage(self):
        rows = scenario.ENGINEERING_PERSONAS
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({row.agent_id for row in rows}), 20)
        self.assertEqual({row.green_orientation for row in rows}, set(scenario._GREEN))
        self.assertEqual({row.category_purchase_frequency for row in rows}, set(scenario._FREQUENCY))
        self.assertEqual({row.prior_brand_relationship for row in rows}, set(scenario._RELATIONSHIP))
        self.assertEqual({row.price_sensitivity for row in rows}, set(scenario._SENSITIVITY))
        self.assertEqual({row.availability_friction for row in rows}, set(scenario._FRICTION))
        for profile in scenario.engineering_profiles():
            self.assertIn("regular plant-based-milk category buyer", profile["persona"])
            self.assertEqual(
                profile["psychology"]["cluster_type"],
                profile["consumer_context"]["green_orientation"],
            )
            self.assertEqual(
                profile["psychology"]["social_role"],
                profile["consumer_context"]["social_posting_role"],
            )

    def test_subjective_norm_does_not_move_without_social_observation(self):
        self.assertEqual(
            cognition.update_subjective_norm(
                previous_sn=0.43,
                social_observation_count=0,
                perceived_peer_approval=None,
            ),
            0.43,
        )

    def test_subjective_norm_uses_peer_approval_with_diminishing_weight(self):
        one = cognition.update_subjective_norm(
            previous_sn=0.5,
            social_observation_count=1,
            perceived_peer_approval=0.8,
        )
        three = cognition.update_subjective_norm(
            previous_sn=0.5,
            social_observation_count=3,
            perceived_peer_approval=0.8,
        )
        ten = cognition.update_subjective_norm(
            previous_sn=0.5,
            social_observation_count=10,
            perceived_peer_approval=0.8,
        )
        self.assertGreater(one, 0.5)
        self.assertGreater(three, one)
        self.assertEqual(ten, three)

    def test_peer_approval_is_required_for_social_messages(self):
        with self.assertRaises(ValueError):
            cognition.update_subjective_norm(
                previous_sn=0.5,
                social_observation_count=1,
                perceived_peer_approval=None,
            )
        self.assertIsNone(
            cognition.validate_peer_approval_output(
                social_observation_count=0,
                perceived_peer_approval=None,
            )
        )

    def test_cognitive_transition_cannot_read_general_valence(self):
        function = cognition.update_subjective_norm
        runtime_names = {
            str(name).lower()
            for name in (*function.__code__.co_varnames, *function.__code__.co_names)
        }
        self.assertNotIn("valence", runtime_names)
        self.assertNotIn("enterprise", runtime_names)
        self.assertNotIn("global", runtime_names)

    def test_semantic_schema_requires_null_peer_approval_without_social(self):
        payload = {
            "valence": -0.2,
            "arousal": 0.4,
            "credibility": 0.7,
            "evidence_strength": 0.3,
            "topic_relevance": 0.8,
            "perceived_empathy": 0.1,
            "perceived_peer_approval": None,
            "hypocrisy_perceived": True,
            "importance": 6,
            "reasoning": "I am concerned.",
        }
        normalized = semantics.validate_semantic_payload(
            payload,
            social_observation_count=0,
        )
        self.assertIsNone(normalized["perceived_peer_approval"])
        payload["perceived_peer_approval"] = 0.2
        with self.assertRaises(semantics.SemanticV32ValidationError):
            semantics.validate_semantic_payload(
                payload,
                social_observation_count=0,
            )

    def test_semantic_schema_requires_numeric_peer_approval_with_social(self):
        payload = {
            "valence": 0.1,
            "arousal": 0.3,
            "credibility": 0.5,
            "evidence_strength": 0.2,
            "topic_relevance": 0.5,
            "perceived_empathy": 0.1,
            "perceived_peer_approval": 0.75,
            "hypocrisy_perceived": False,
            "importance": 4,
            "reasoning": "My peers seem supportive.",
        }
        normalized = semantics.validate_semantic_payload(
            payload,
            social_observation_count=2,
        )
        self.assertEqual(normalized["perceived_peer_approval"], 0.75)
        payload["perceived_peer_approval"] = None
        with self.assertRaises(semantics.SemanticV32ValidationError):
            semantics.validate_semantic_payload(
                payload,
                social_observation_count=1,
            )


if __name__ == "__main__":
    unittest.main()
