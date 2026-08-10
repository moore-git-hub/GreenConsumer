"""Shared audited LLM router harness for TASK_005 engineering pilots.

The harness records every true inner-router chat call, validates raw semantic
JSON before production consumers parse it, and provides recording/replay router
wrappers compatible with run_experiments._run_with_patch.
"""

from __future__ import annotations

import json
import hashlib
import math
import time
from pathlib import Path
from typing import Mapping

from run_experiments import RecordingRouter, ReplayRouter


STRICT_SEMANTIC_FIELDS = (
    "valence",
    "arousal",
    "credibility",
    "evidence_strength",
    "topic_relevance",
    "perceived_empathy",
    "hypocrisy_perceived",
    "importance",
    "reasoning",
)


class AuditedRouterError(RuntimeError):
    """Raised when audited router execution violates the stage contract."""


class SemanticValidationError(AuditedRouterError):
    """Raised when a raw semantic response is not contract-compliant."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sanitize_text(text: str) -> str:
    lowered = str(text)
    for marker in ("api_key", "apikey", "authorization", "bearer", "secret", "token"):
        lowered = lowered.replace(marker, "[redacted]")
        lowered = lowered.replace(marker.upper(), "[redacted]")
    return lowered[:240]


def validate_raw_semantic_response(payload: Mapping) -> None:
    ranges = {
        "valence": (-1.0, 1.0),
        "arousal": (0.0, 1.0),
        "credibility": (0.0, 1.0),
        "evidence_strength": (0.0, 1.0),
        "topic_relevance": (0.0, 1.0),
        "perceived_empathy": (0.0, 1.0),
        "importance": (1.0, 10.0),
    }
    for field, (lo, hi) in ranges.items():
        if field not in payload:
            raise SemanticValidationError(f"semantic response missing {field}")
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SemanticValidationError(f"semantic response {field} must be numeric")
        value = float(value)
        if not math.isfinite(value) or not lo <= value <= hi:
            raise SemanticValidationError(f"semantic response {field} out of range")
    if not isinstance(payload.get("hypocrisy_perceived"), bool):
        raise SemanticValidationError("semantic response hypocrisy_perceived must be boolean")
    if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
        raise SemanticValidationError("semantic response reasoning must be non-empty")


def _looks_like_json_object(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("{") and stripped.endswith("}")


def _is_reflect_semantic_prompt(prompt: str) -> bool:
    lowered = prompt.lower()
    signals = (
        "valence",
        "arousal",
        "credibility",
        "evidence_strength",
        "topic_relevance",
        "perceived_empathy",
        "hypocrisy_perceived",
    )
    return sum(1 for signal in signals if signal in lowered) >= 4


def _prompt_category(prompt: str) -> str:
    if _is_reflect_semantic_prompt(prompt):
        return "semantic"
    lowered = prompt.lower()
    if "plan" in lowered or "purchase" in lowered:
        return "plan"
    return "other"


class ValidatedAuditedRouter:
    """Audit and validate each true inner-router chat call."""

    def __init__(
        self,
        inner_router,
        *,
        audit_path: Path,
        pilot_id: str,
        replicate_id: str,
        requested_llm_seed: int | str = 0,
        model: str = "",
        temperature: float | str = "",
    ):
        self._inner = inner_router
        self.audit_path = Path(audit_path)
        self.pilot_id = pilot_id
        self.replicate_id = replicate_id
        self.requested_llm_seed = requested_llm_seed
        self.model = model
        self.temperature = temperature
        self.call_count = 0
        self._condition = ""
        self._tick = 0
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def set_context(self, *, condition: str, tick: int) -> None:
        self._condition = condition
        self._tick = int(tick)

    async def chat(self, prompt: str) -> str:
        self.call_count += 1
        call_index = self.call_count
        started = time.perf_counter()
        response = ""
        response_parse_ok = False
        semantic_schema_ok = False
        validation_error_type = ""
        error_type = ""
        category = _prompt_category(prompt)
        try:
            response = await self._inner.chat(prompt)
            if category == "semantic" or _looks_like_json_object(response):
                payload = json.loads(response)
                response_parse_ok = True
                if category == "semantic":
                    validate_raw_semantic_response(payload)
                    semantic_schema_ok = True
            return response
        except Exception as exc:
            error_type = type(exc).__name__
            validation_error_type = type(exc).__name__
            raise
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            row = {
                "pilot_id": self.pilot_id,
                "replicate_id": self.replicate_id,
                "condition": self._condition,
                "tick": self._tick,
                "call_index": call_index,
                "prompt_sha256": _sha256_text(prompt),
                "response_sha256": _sha256_text(response),
                "response_parse_ok": response_parse_ok,
                "semantic_schema_ok": semantic_schema_ok if category == "semantic" else "",
                "validation_error_type": validation_error_type,
                "prompt_category": category,
                "latency_ms": latency_ms,
                "error_type": error_type,
                "requested_llm_seed": self.requested_llm_seed,
                "model": self.model,
                "temperature": self.temperature,
            }
            with self.audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


class AuditedRecordingRouter(RecordingRouter):
    """RecordingRouter that propagates tick/condition context to the audited inner."""

    def __init__(self, inner_router, exp_id: str):
        super().__init__(inner_router)
        self._exp_id = exp_id

    def set_tick(self, tick: int):
        super().set_tick(tick)
        if hasattr(self._inner, "set_context"):
            self._inner.set_context(condition=self._exp_id, tick=tick)


class AuditedReplayRouter(ReplayRouter):
    """ReplayRouter that propagates tick/condition context to the audited inner."""

    def __init__(self, inner_router, cache: dict, replay_until_tick: int, exp_id: str):
        super().__init__(inner_router, cache, replay_until_tick, exp_id=exp_id)
        self._exp_id = exp_id

    def set_tick(self, tick: int):
        super().set_tick(tick)
        if hasattr(self._inner, "set_context"):
            self._inner.set_context(condition=self._exp_id, tick=tick)


class DeterministicFakeInnerRouter:
    """Offline deterministic inner router that performs no network or config reads."""

    def __init__(self):
        self.call_count = 0

    async def chat(self, prompt: str) -> str:
        self.call_count += 1
        if _is_reflect_semantic_prompt(prompt):
            payload = {
                "valence": 0.15,
                "arousal": 0.25,
                "credibility": 0.82,
                "evidence_strength": 0.76,
                "topic_relevance": 0.88,
                "perceived_empathy": 0.64,
                "hypocrisy_perceived": False,
                "importance": 5,
                "reasoning": "deterministic offline semantic fixture",
            }
            return json.dumps(payload, sort_keys=True)
        return "deterministic offline response"
