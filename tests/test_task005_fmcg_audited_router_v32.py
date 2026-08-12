from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from task005_fmcg_audited_router_v32 import ValidatedAuditedFMCGRouterV32


class Inner:
    def __init__(self, payload):
        self.payload = payload
        self.ticks = []

    def set_tick(self, tick):
        self.ticks.append(tick)

    async def chat(self, prompt):
        return json.dumps(self.payload)


def payload(peer):
    return {
        "valence": 0.1,
        "arousal": 0.3,
        "credibility": 0.6,
        "evidence_strength": 0.4,
        "topic_relevance": 0.8,
        "perceived_empathy": 0.2,
        "perceived_peer_approval": peer,
        "hypocrisy_perceived": False,
        "importance": 5,
        "reasoning": "I evaluated the observed message.",
    }


PROMPT = """
[Information]
{social}
Return valence, arousal, credibility, evidence_strength,
perceived_peer_approval, topic_relevance and perceived_empathy as JSON.
"""


class AuditedRouterV32Tests(unittest.TestCase):
    def test_valid_non_social_response_is_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            inner = Inner(payload(None))
            router = ValidatedAuditedFMCGRouterV32(
                inner,
                audit_path=audit,
                pilot_id="pilot",
                replicate_id="R001",
            )
            router.set_context(condition="Control", tick=5)
            asyncio.run(router.chat(PROMPT.format(social="[Breaking News] x")))
            row = json.loads(audit.read_text())
            self.assertTrue(row["semantic_schema_ok"])
            self.assertEqual(row["social_observation_count"], 0)

    def test_social_response_requires_peer_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            router = ValidatedAuditedFMCGRouterV32(
                Inner(payload(None)),
                audit_path=audit,
                pilot_id="pilot",
                replicate_id="R001",
            )
            with self.assertRaises(ValueError):
                asyncio.run(
                    router.chat(PROMPT.format(social="[Social Feed] peer post"))
                )
            row = json.loads(audit.read_text())
            self.assertFalse(row["semantic_schema_ok"])
            self.assertTrue(row["error_type"])

    def test_social_response_with_peer_approval_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            router = ValidatedAuditedFMCGRouterV32(
                Inner(payload(0.7)),
                audit_path=audit,
                pilot_id="pilot",
                replicate_id="R001",
            )
            asyncio.run(router.chat(PROMPT.format(social="[Social Feed] peer post")))
            row = json.loads(audit.read_text())
            self.assertTrue(row["semantic_schema_ok"])
            self.assertEqual(row["social_observation_count"], 1)


if __name__ == "__main__":
    unittest.main()
