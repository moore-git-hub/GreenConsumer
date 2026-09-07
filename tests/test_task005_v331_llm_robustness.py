from __future__ import annotations

from pathlib import Path

import pytest

from greenconsumer_v33.config import RunSettings
from greenconsumer_v33.llm_robustness import plan_payload, profile_table
from greenconsumer_v33.prompt_profiles import (
    BASELINE_PROMPT_PROFILE,
    PROMPT_PROFILES,
    lexical_multiset,
    transform_prompt,
)


FIXTURE_PROMPT = """
[Character Persona]
You are a consumer.
[Past Experiences]
None
[Information]
Source: Global News
[Breaking News] Example factual message.

Return one JSON object only. Appraise the information actually observed. Do not
decide buying, brand choice, or posting. `perceived_peer_approval` measures only
whether observed peers approve choosing VerdantCo Oat; never infer it from news,
the brand statement, general valence, or your own opinion.
{
 "valence": <float -1 to 1>,
 "arousal": <float 0 to 1>,
 "credibility": <float 0 to 1>,
 "evidence_strength": <float 0 to 1>,
 "topic_relevance": <float 0 to 1>,
 "perceived_empathy": <float 0 to 1>,
 "perceived_peer_approval": null,
 "hypocrisy_perceived": <boolean>,
 "importance": <float 1 to 10>,
 "reasoning": "<one concise first-person sentence in English>"
}
"""


def test_prompt_profiles_are_pre_specified_and_baseline_exact():
    assert PROMPT_PROFILES == ("baseline_exact", "compact_separator", "schema_first")
    assert transform_prompt(FIXTURE_PROMPT, BASELINE_PROMPT_PROFILE) == FIXTURE_PROMPT


def test_nonbaseline_prompt_profiles_preserve_lexical_multiset():
    for profile in ("compact_separator", "schema_first"):
        transformed = transform_prompt(FIXTURE_PROMPT, profile)
        assert transformed != FIXTURE_PROMPT
        assert lexical_multiset(transformed) == lexical_multiset(FIXTURE_PROMPT)
        for required in (
            "perceived_peer_approval",
            "evidence_strength",
            "perceived_empathy",
            "hypocrisy_perceived",
            "Do not",
            "brand choice",
        ):
            assert required in transformed


def test_real_llm_profile_grid_has_five_unique_blocks_and_three_baseline_repeats():
    df = profile_table()
    assert len(df) == 5
    assert df["profile_id"].is_unique
    baseline = df[df["prompt_profile"] == BASELINE_PROMPT_PROFILE]
    assert len(baseline) == 3
    assert set(baseline["baseline_repeat"]) == {1, 2, 3}
    assert set(df["prompt_profile"]) == set(PROMPT_PROFILES)


def test_nonbaseline_prompt_profile_cannot_run_through_fake_fixture():
    settings = RunSettings(
        llm_mode="fake",
        condition="all",
        simulation_seed=1,
        requested_llm_seed=2,
        demand_seed=3,
        output_dir=Path("results"),
        prompt_profile="schema_first",
    )
    with pytest.raises(ValueError):
        settings.validate()


def test_real_llm_still_requires_explicit_authorization():
    settings = RunSettings(
        llm_mode="real",
        condition="all",
        simulation_seed=1,
        requested_llm_seed=2,
        demand_seed=3,
        output_dir=Path("results"),
        prompt_profile="baseline_exact",
        allow_real_llm=False,
    )
    with pytest.raises(ValueError):
        settings.validate()


def test_plan_only_is_zero_api_and_explicit_about_cost_scope():
    plan = plan_payload()
    assert plan["status"] == "PLAN_ONLY"
    assert plan["real_llm_calls_started"] is False
    assert plan["profiles_count"] == 5
    assert plan["baseline_repeats"] == 3
