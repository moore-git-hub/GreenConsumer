"""LLM router 构建、审计与 common-history replay。

该模块是 clean workflow 中唯一负责选择 fake/real LLM 的地方。
它不再依赖历史 ``run_experiments.py``，因此旧 runner 可以安全删除。

科研边界：
1. LLM 只为 ``GreenCognitionV32Plugin`` 提供语义评价；
2. control-first 全矩阵运行时，策略条件在 treatment 前重放 control 的
   同一语义响应，降低不必要的 LLM 随机差异；
3. 所有真实/伪语义响应继续通过 v3.2 audited router 校验和记录。
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import os
from typing import Mapping

import yaml

from agentkernel_standalone.toolkit.models.router import AsyncModelRouter, ModelRouter
from task005_fmcg_audited_router_v32 import ValidatedAuditedFMCGRouterV32
from task005_fmcg_fake_router_v32 import DeterministicFMCGSemanticRouterV32

from .config import PROJECT_ROOT

_API_KEY_ENV = "DASHSCOPE_API_KEY"
_API_KEY_PLACEHOLDER = "__FROM_ENV_DASHSCOPE_API_KEY__"


class ReplayAlignmentError(RuntimeError):
    """treatment 前 common-history cache 无法严格对齐时抛出。"""


def prompt_key(text: str) -> str:
    """使用稳定 SHA256，而不是 Python ``hash()``，生成 prompt 身份。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_placeholder_secret(value) -> bool:
    """识别配置文件中的 API key 占位符/空值。"""
    if not isinstance(value, str):
        return False
    text = value.strip()
    return (
        text == ""
        or text == _API_KEY_PLACEHOLDER
        or text.startswith("__FROM_ENV_")
        or text.upper() in {"<REDACTED>", "REDACTED", "PLACEHOLDER"}
    )


def _real_model_config(
    requested_llm_seed: int,
    *,
    model_override: str | None = None,
):
    """读取共享配置，并只在内存中注入密钥、seed和可选模型覆盖。"""
    config_path = PROJECT_ROOT / "configs" / "models_config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8-sig"))
    conf = copy.deepcopy(raw)
    entries = conf if isinstance(conf, list) else [conf]

    api_key = os.environ.get(_API_KEY_ENV, "").strip()
    if _is_placeholder_secret(api_key):
        raise RuntimeError(
            "DASHSCOPE_API_KEY is required for real LLM execution; "
            "run `python run_v32.py preflight --real` first"
        )

    chat_entries = [
        entry
        for entry in entries
        if isinstance(entry, dict) and "chat" in (entry.get("capabilities") or [])
    ]
    if not chat_entries:
        raise RuntimeError("models_config.yaml has no chat-capable model entry")

    resolved_model = None
    if model_override is not None:
        resolved_model = str(model_override).strip()
        if not resolved_model:
            raise ValueError("model_override must be a non-empty model identifier")

    for entry in chat_entries:
        entry["api_key"] = api_key
        entry["seed"] = int(requested_llm_seed)
        if resolved_model is not None:
            entry["model"] = resolved_model
    return conf


def _build_real_router(
    requested_llm_seed: int,
    *,
    model_override: str | None = None,
):
    """构建 AgentKernel ModelRouter，并允许版本作用域内固定模型。

    API key 只存在于当前进程内存，不会写回 YAML 或结果文件。
    """
    async_router = AsyncModelRouter(
        _real_model_config(
            requested_llm_seed,
            model_override=model_override,
        )
    )
    router = ModelRouter(async_router)
    # 保留 inner 引用用于兼容不同 AgentKernel 版本的资源关闭方式。
    router._task005_async_router = async_router
    return router


class RecordingRouter:
    """记录 control 的 LLM 响应，供同一 run 的策略条件重放。"""

    def __init__(self, inner, *, before_provider_call=None):
        self.inner = inner
        self.before_provider_call = before_provider_call
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
        if self.before_provider_call is not None:
            self.before_provider_call()
        response = await self.inner.chat(prompt)
        self.provider_calls += 1
        self.cache[(key, self.tick, index)] = response
        return response


class ReplayRouter:
    """在 clarification onset 之前严格重放 control history。

    cache miss 被视为实验对齐失败，而不是回退为一次新的真实模型调用。
    """

    def __init__(
        self,
        inner,
        cache: Mapping[tuple[str, int, int], str],
        replay_until: int,
        *,
        before_provider_call=None,
    ):
        self.inner = inner
        self.before_provider_call = before_provider_call
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
                raise ReplayAlignmentError(f"replay miss tick={self.tick} index={index}")
            self.replay_hits += 1
            return self.cache[cache_key]

        if self.before_provider_call is not None:
            self.before_provider_call()
        self.provider_calls += 1
        return await self.inner.chat(prompt)


def build_inner_router(
    mode: str,
    requested_llm_seed: int,
    *,
    model_override: str | None = None,
):
    """按显式mode构建router；real可覆盖模型，fake忽略覆盖且绝不fallback。"""
    if mode == "fake":
        return DeterministicFMCGSemanticRouterV32()
    if mode == "real":
        return _build_real_router(
            requested_llm_seed=requested_llm_seed,
            model_override=model_override,
        )
    raise ValueError(mode)


def wrap_audited(inner, *, audit_path, run_id: str, condition: str, requested_llm_seed: int, model: str, temperature: float):
    """给当前 condition 的 router 包一层 schema validation + JSONL audit。"""
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
    """兼容 AgentKernel 不同版本，显式释放真实 router 资源。"""
    if router is None or getattr(router, "_task005_router_close_noop", False):
        return

    close_method = None
    for name in ("close", "aclose", "shutdown"):
        candidate = getattr(router, name, None)
        if callable(candidate):
            close_method = candidate
            break

    if close_method is None:
        inner = getattr(router, "_task005_async_router", None)
        candidate = getattr(inner, "close", None)
        if callable(candidate):
            close_method = candidate

    if close_method is None:
        raise AttributeError("router has no supported close/aclose/shutdown API")

    result = close_method()
    if inspect.isawaitable(result):
        await result
