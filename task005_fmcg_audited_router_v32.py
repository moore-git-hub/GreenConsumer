"""Version-scoped semantic audit wrapper for a future FMCG-v3.2 pilot.

This module performs no router construction and contains no credentials.  It
validates the raw response before returning it to the cognition plugin.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from mechanism_v32_semantics import validate_semantic_payload


SCHEMA = "task005-fmcg-audited-router-3.2"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _is_semantic_prompt(prompt: str) -> bool:
    lowered = prompt.lower()
    required = (
        "valence",
        "arousal",
        "credibility",
        "evidence_strength",
        "perceived_peer_approval",
    )
    return all(field in lowered for field in required)


class ValidatedAuditedFMCGRouterV32:
    """Audit and schema-validate an explicitly supplied inner router."""

    def __init__(
        self,
        inner_router,
        *,
        audit_path: Path,
        pilot_id: str,
        replicate_id: str,
        model: str = "",
        temperature: float | str = "",
        requested_llm_seed: int | str = "",
    ):
        if inner_router is None:
            raise ValueError("an explicit inner router is required")
        self._inner = inner_router
        self.audit_path = Path(audit_path)
        self.pilot_id = str(pilot_id)
        self.replicate_id = str(replicate_id)
        self.model = model
        self.temperature = temperature
        self.requested_llm_seed = requested_llm_seed
        self.call_count = 0
        self._condition = ""
        self._tick = 0
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def set_context(self, *, condition: str, tick: int) -> None:
        self._condition = str(condition)
        self._tick = int(tick)

    def set_tick(self, tick: int) -> None:
        self._tick = int(tick)
        if hasattr(self._inner, "set_tick"):
            self._inner.set_tick(tick)

    async def chat(self, prompt: str) -> str:
        self.call_count += 1
        call_index = self.call_count
        started = time.perf_counter()
        response = ""
        parse_ok = False
        schema_ok = False
        error_type = ""
        semantic = _is_semantic_prompt(prompt)
        social_count = prompt.count("[Social Feed]") if semantic else 0
        try:
            response = await self._inner.chat(prompt)
            if semantic:
                payload = json.loads(response)
                parse_ok = True
                validate_semantic_payload(
                    payload,
                    social_observation_count=social_count,
                )
                schema_ok = True
            return response
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            row = {
                "schema_version": SCHEMA,
                "pilot_id": self.pilot_id,
                "replicate_id": self.replicate_id,
                "condition": self._condition,
                "tick": self._tick,
                "call_index": call_index,
                "prompt_sha256": _sha256_text(prompt),
                "response_sha256": _sha256_text(response),
                "prompt_category": "semantic" if semantic else "other",
                "social_observation_count": social_count if semantic else "",
                "response_parse_ok": parse_ok if semantic else "",
                "semantic_schema_ok": schema_ok if semantic else "",
                "latency_ms": round(
                    (time.perf_counter() - started) * 1000.0, 3
                ),
                "error_type": error_type,
                "requested_llm_seed": self.requested_llm_seed,
                "model": self.model,
                "temperature": self.temperature,
            }
            with self.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
