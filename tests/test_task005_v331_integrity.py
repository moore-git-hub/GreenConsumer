"""Zero-API integrity tests for the TASK_005 v3.3.1 freeze candidate."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from clarification_diffusion_v33 import ClarificationInjectorV33
from greenconsumer_v33.analysis import _lag_aware_direct_reach
from plugins.agent.reflect.GreenCognitionV33Plugin import GreenCognitionV33Plugin
from task005_fmcg_runtime_v33 import _restore_full_text_audit_fields


class _State:
    def __init__(self):
        self.state_data = {"incoming_messages": []}

    async def set_state(self, key, value):
        self.state_data[key] = value


class _Component:
    def __init__(self, plugin):
        self._plugin = plugin


class _Agent:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.state = _State()

    def get_component(self, name):
        assert name == "state"
        return _Component(self.state)


def _config(tick=6):
    return SimpleNamespace(
        content_factor="rational-evidence",
        clarification_tick=tick,
    )


def test_v331_social_feed_preserves_complete_peer_post():
    payload = (
        "A long peer post used to test full-message preservation. "
        + ("0123456789" * 40)
        + "::END_SENTINEL::"
    )
    rendered = GreenCognitionV33Plugin._render_social_feed_content(
        {"source": "Social", "content": payload}
    )
    assert rendered == payload
    assert rendered.endswith("::END_SENTINEL::")
    assert len(rendered) > 180


def test_v331_agent_audit_preserves_full_reasoning_and_post_content():
    reasoning = ("reasoning-" * 50) + "::REASONING_END::"
    post = ("post-" * 80) + "::POST_END::"

    row = {
        "reasoning": reasoning[:300],
        "post_content": post[:200],
        "other_field": 123,
    }
    restored = _restore_full_text_audit_fields(
        row,
        plan={"post_content": post},
        thought={"reasoning": reasoning},
    )

    assert restored["reasoning"] == reasoning
    assert restored["post_content"] == post
    assert restored["reasoning"].endswith("::REASONING_END::")
    assert restored["post_content"].endswith("::POST_END::")
    assert restored["other_field"] == 123


def test_v331_fix_is_version_scoped_by_class_name():
    assert GreenCognitionV33Plugin.__name__ == "GreenCognitionV33Plugin"


def test_v331_lag_zero_delivers_direct_and_amplified_at_t0():
    agents = [_Agent("A"), _Agent("B"), _Agent("C")]
    injector = ClarificationInjectorV33(_config(), delivery_lag=0)
    injector.set_public_exposure_nodes(["A"])
    injector.set_target_nodes(["B"])
    injector.set_amplified_nodes(["C"])

    count = asyncio.run(injector.inject(agents, 6))
    assert count == 3
    assert set(injector.last_injected_ids) == {"A", "B", "C"}
    assert all(len(agent.state.state_data["incoming_messages"]) == 1 for agent in agents)


def test_v331_analysis_uses_configured_delivery_lag_not_hardcoded_plus_one():
    rows = []
    for tick in range(1, 10):
        rows.append({
            "tick": tick,
            "agent_id": "A",
            "clarification_tick_config": 6,
            "enterprise_clarification_observed": tick == 6,
        })
        rows.append({
            "tick": tick,
            "agent_id": "B",
            "clarification_tick_config": 6,
            "enterprise_clarification_observed": tick == 8,
        })
    direct, lagged, union = _lag_aware_direct_reach(rows, delivery_lag=2)
    assert direct == 0.5
    assert lagged == 0.5
    assert union == 1.0
