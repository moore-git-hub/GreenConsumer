import json
from pathlib import Path

import test_task005_production_path_fake_model_smoke_v2 as base

ROOT = Path(__file__).resolve().parents[1]
V3_RESULT_PATH = (
    ROOT
    / ".kiro"
    / "specs"
    / "task005-replication-inference"
    / "production_path_fake_model_smoke_v3_result1.0.json"
)


class DeterministicSemanticFakeRouterV3:
    def __init__(self):
        self.call_count = 0
        self.categories = []
        self.prompts = []
        self.current_tick = None

    def set_tick(self, tick):
        self.current_tick = tick

    async def chat(self, prompt):
        self.call_count += 1
        self.prompts.append(prompt)
        if "[Breaking News]" in prompt:
            self.categories.append("breaking_news")
            return base._json_response(
                -0.85,
                0.80,
                0.80,
                0.65,
                0.95,
                0.10,
                True,
                8,
                "I am concerned because the hypothetical controversy appears relevant and credible.",
            )
        if "[Brand Statement]" in prompt:
            if (
                "VerdantCo Structured Evidence Summary" in prompt
                or "checkable evidence" in prompt
                or "procedural transparency" in prompt
            ):
                self.categories.append("rational_statement")
                return base._json_response(
                    0.50,
                    0.45,
                    0.90,
                    0.95,
                    0.90,
                    0.30,
                    False,
                    7,
                    "I see structured, checkable evidence in the fictional brand statement.",
                )
            if (
                "VerdantCo Responsibility and Relationship Message" in prompt
                or "consumer frustration" in prompt
                or "relationship repair" in prompt
            ):
                self.categories.append("empathy_statement")
                return base._json_response(
                    0.75,
                    0.75,
                    0.72,
                    0.35,
                    0.90,
                    0.88,
                    False,
                    7,
                    "I feel the fictional brand acknowledges consumer concern.",
                )
            raise RuntimeError("unknown post-amendment brand-statement prompt")
        if "[Social Feed]" in prompt:
            self.categories.append("social_feed")
            return base._json_response(
                0.10,
                0.30,
                0.45,
                0.20,
                0.50,
                0.10,
                False,
                4,
                "A social post mildly shaped my perception.",
            )
        raise RuntimeError("unknown observed prompt")


def main():
    base.RESULT_PATH = V3_RESULT_PATH
    base.DeterministicSemanticFakeRouter = DeterministicSemanticFakeRouterV3
    try:
        base.main()
    except SystemExit as exc:
        if exc.code == 0 and V3_RESULT_PATH.exists():
            payload = json.loads(V3_RESULT_PATH.read_text(encoding="utf-8"))
            payload["stage"] = "TASK_005 production-path-fake-model-smoke-v3"
            payload["post_amendment_stimuli"] = True
            payload["authorized_brand"] = "VerdantCo"
            payload["pre_amendment_evidence_preserved"] = True
            V3_RESULT_PATH.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        raise


if __name__ == "__main__":
    main()
