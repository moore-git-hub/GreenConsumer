from __future__ import annotations

import hashlib
from typing import Mapping

from task005_fmcg_audited_router_v32 import ValidatedAuditedFMCGRouterV32
from task005_fmcg_fake_router_v32 import DeterministicFMCGSemanticRouterV32
from run_experiments import _build_real_router, _close_router_resource


class ReplayAlignmentError(RuntimeError):
    pass


def prompt_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RecordingRouter:
    """Record control-history LLM responses for within-run replay."""

    def __init__(self, inner):
        self.inner = inner
        self.tick = 0
        self.counts: dict[str, int] = {}
        self.cache: dict[tuple[str, int, int], str] = {}
        self.provider_calls = 0

    def set_tick(self, tick: int) -> None:
        self.tick = int(tick)
        self.counts = {}
        if hasattr(self.inner, "set_tick"):
            self.inner.set_tick(tick)

    async def chat(self, prompt: str) -> str:
        key = prompt_key(prompt)
        index = self.counts.get(key, 0)
        self.counts[key] = index + 1
        response = await self.inner.chat(prompt)
        self.provider_calls += 1
        self.cache[(key, self.tick, index)] = response
        return response


class ReplayRouter:
    """Replay control history before treatment onset; fail closed on a miss."""

    def __init__(
        self,
        inner,
        cache: Mapping[tuple[str, int, int], str],
        replay_until: int,
    ):
        self.inner = inner
        self.cache = cache
        self.replay_until = int(replay_until)
        self.tick = 0
        self.counts: dict[str, int] = {}
        self.provider_calls = 0
        self.replay_hits = 0
        self.replay_misses = 0

    def set_tick(self, tick: int) -> None:
        self.tick = int(tick)
        self.counts = {}
        if hasattr(self.inner, "set_tick"):
            self.inner.set_tick(tick)

    async def chat(self, prompt: str) -> str:
        key = prompt_key(prompt)
        index = self.counts.get(key, 0)
        self.counts[key] = index + 1
        cache_key = (key, self.tick, index)
        if self.tick < self.replay_until:
            if cache_key not in self.cache:
                self.replay_misses += 1
                raise ReplayAlignmentError(
                    f"replay miss tick={self.tick} index={index}"
                )
            self.replay_hits += 1
            return self.cache[cache_key]
        self.provider_calls += 1
        return await self.inner.chat(prompt)


def build_inner_router(mode: str, requested_llm_seed: int):
    if mode == "fake":
        return DeterministicFMCGSemanticRouterV32()
    if mode == "real":
        return _build_real_router(requested_llm_seed=requested_llm_seed)
    raise ValueError(mode)


def wrap_audited(
    inner,
    *,
    audit_path,
    run_id: str,
    condition: str,
    requested_llm_seed: int,
    model: str,
    temperature: float,
):
    router = ValidatedAuditedFMCGRouterV32(
        inner,
        audit_path=audit_path,
        pilot_id=run_id,
        replicate_id="engineering-demo",
        model=model,
        temperature=temperature,
        requested_llm_seed=requested_llm_seed,
    )
    router.set_context(condition=condition, tick=0)
    return router


async def close_inner_router(router) -> None:
    await _close_router_resource(router)
