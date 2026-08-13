"""Prompt-format robustness profiles for TASK_005 v3.3.1 Real-LLM checks.

The frozen scientific prompt remains ``baseline_exact``. Robustness profiles do
not alter persona text, observed information, memory text, semantic field names,
peer-approval boundary instructions, or the prohibition on purchase/posting
decisions. They only change static prompt layout/order.

These profiles are engineering robustness probes, not alternative prompts to be
selected after inspecting outcomes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

PROMPT_PROFILES = (
    "baseline_exact",
    "compact_separator",
    "schema_first",
)
BASELINE_PROMPT_PROFILE = "baseline_exact"
_MARKER = "\n\nReturn one JSON object only."


def _split_prompt(prompt: str) -> tuple[str, str]:
    """Split the frozen v3.3.1 prompt into context and instruction/schema blocks."""

    text = str(prompt)
    if _MARKER not in text:
        raise ValueError(
            "prompt does not match the frozen v3.3.1 appraisal layout; "
            "refuse robustness transformation rather than guessing"
        )
    context, tail = text.split(_MARKER, 1)
    instruction = "Return one JSON object only." + tail
    return context, instruction


def transform_prompt(prompt: str, profile: str) -> str:
    """Return a pre-specified layout perturbation of the same appraisal prompt."""

    profile = str(profile)
    if profile not in PROMPT_PROFILES:
        raise ValueError(f"unknown prompt profile: {profile}")
    if profile == "baseline_exact":
        return str(prompt)

    context, instruction = _split_prompt(str(prompt))
    if profile == "compact_separator":
        # Preserve all substantive text and order; remove only the blank separator
        # between context and instruction/schema blocks.
        return context.rstrip("\n") + "\n" + instruction
    if profile == "schema_first":
        # Preserve both blocks verbatim while changing only their order.
        return instruction + "\n\n" + context.strip("\n") + "\n"
    raise AssertionError(profile)


def prompt_sha256(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def lexical_multiset(text: str) -> tuple[str, ...]:
    """Whitespace-insensitive lexical identity helper for zero-API validation."""

    return tuple(sorted(str(text).split()))


@dataclass
class PromptProfileRouter:
    """Router wrapper that transforms only the prompt presented to the provider.

    Recording/Replay routers still operate normally around this wrapper. The
    wrapper keeps a separate transformation audit so prompt robustness remains
    traceable even when the outer LLM audit was designed before prompt profiles.
    """

    inner: object
    profile: str

    def __post_init__(self):
        if self.profile not in PROMPT_PROFILES:
            raise ValueError(f"unknown prompt profile: {self.profile}")
        self.tick = 0
        self.records: list[dict] = []

    def __getattr__(self, name):
        # Preserve lifecycle/provenance compatibility with AgentKernel routers.
        return getattr(self.inner, name)

    def set_tick(self, tick: int) -> None:
        self.tick = int(tick)
        if hasattr(self.inner, "set_tick"):
            self.inner.set_tick(tick)

    async def chat(self, prompt: str) -> str:
        transformed = transform_prompt(prompt, self.profile)
        self.records.append(
            {
                "tick": int(self.tick),
                "prompt_profile": self.profile,
                "original_sha256": prompt_sha256(prompt),
                "transformed_sha256": prompt_sha256(transformed),
                "changed": transformed != str(prompt),
                "lexical_multiset_equal": lexical_multiset(prompt)
                == lexical_multiset(transformed),
                "original_chars": len(str(prompt)),
                "transformed_chars": len(transformed),
            }
        )
        return await self.inner.chat(transformed)
