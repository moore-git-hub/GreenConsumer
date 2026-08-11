from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiment_config import generate_experiment_matrix
from fmcg_scenario_v32 import CLARIFICATION_TEMPLATES, CRISIS_STIMULUS
import task005_fmcg_runtime_v32 as runtime


class ReflectOld:
    pass


class PlanOld:
    pass


class ReflectNew:
    pass


class PlanNew:
    pass


class FMCGRuntimeV32Tests(unittest.TestCase):
    def _modules(self):
        original_profile_builder = lambda num_agents, seed: ["old"]

        def original_record_builder(*args, **kwargs):
            return {"subjective_norm_sn": 0.5, "original": True}

        simulation = SimpleNamespace(
            _generate_profiles_inline=original_profile_builder,
            build_mechanism_record=original_record_builder,
            ENTERPRISE_STRATEGY={1: "legacy"},
            resource_maps={
                "agent_plugins": {
                    "GreenCognitionPlugin": ReflectOld,
                    "ConsumerPlanPlugin": PlanOld,
                }
            },
        )
        clarification = SimpleNamespace(CONTENT_TEMPLATES={"legacy": "old"})
        return simulation, clarification, original_profile_builder, original_record_builder

    def test_runtime_patch_supplies_v32_assets_and_extended_audit(self):
        simulation, clarification, _, _ = self._modules()
        with runtime._isolated_runtime_patch(
            simulation,
            clarification,
            ReflectNew,
            PlanNew,
        ):
            profiles = simulation._generate_profiles_inline(20, 999)
            self.assertEqual(len(profiles), 20)
            self.assertTrue(
                all("VerdantCo Oat" in row["persona"] for row in profiles)
            )
            self.assertEqual(simulation.ENTERPRISE_STRATEGY, {5: CRISIS_STIMULUS})
            self.assertEqual(
                clarification.CONTENT_TEMPLATES,
                CLARIFICATION_TEMPLATES,
            )
            self.assertIs(
                simulation.resource_maps["agent_plugins"]["GreenCognitionPlugin"],
                ReflectNew,
            )
            row = simulation.build_mechanism_record(
                s_data={
                    "semantic_social_observation_count": 1,
                    "semantic_schema_version": "semantic-appraisal-3.2",
                    "semantic_perceived_peer_approval": 0.7,
                },
                plan={
                    "subjective_norm_before": 0.5,
                    "subjective_norm_after": 0.54,
                    "legacy_purchase_endpoint_retired": True,
                },
            )
            self.assertEqual(row["semantic_perceived_peer_approval"], 0.7)
            self.assertTrue(row["subjective_norm_peer_update_applied"])
            self.assertTrue(row["legacy_purchase_endpoint_retired"])

    def test_runtime_patch_restores_every_active_object_after_exception(self):
        simulation, clarification, old_profile, old_record = self._modules()
        with self.assertRaises(RuntimeError):
            with runtime._isolated_runtime_patch(
                simulation,
                clarification,
                ReflectNew,
                PlanNew,
            ):
                raise RuntimeError("sentinel")
        self.assertIs(simulation._generate_profiles_inline, old_profile)
        self.assertIs(simulation.build_mechanism_record, old_record)
        self.assertEqual(simulation.ENTERPRISE_STRATEGY, {1: "legacy"})
        self.assertEqual(clarification.CONTENT_TEMPLATES, {"legacy": "old"})
        self.assertIs(
            simulation.resource_maps["agent_plugins"]["GreenCognitionPlugin"],
            ReflectOld,
        )
        self.assertIs(
            simulation.resource_maps["agent_plugins"]["ConsumerPlanPlugin"],
            PlanOld,
        )

    def test_implicit_router_is_prohibited_before_kernel_import(self):
        config = generate_experiment_matrix()[-1]
        with self.assertRaises(ValueError):
            asyncio.run(runtime.run_scenario_v32(config, override_router=None))


if __name__ == "__main__":
    unittest.main()
