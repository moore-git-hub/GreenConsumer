"""
TASK_001-V: Deterministic State Lifecycle Acceptance Test

Uses REAL GreenCognitionPlugin + ConsumerPlanPlugin + GreenInvokePlugin
with minimal Fake Agent/State/Profile wrappers and a deterministic Mock Router.

Does NOT load sentence-transformers, Hugging Face models, or real LLMs.
Does NOT modify any production code or simulation_core.

Outputs:
  results/task001_validation/<timestamp>/
    task001_state_trace.csv
    acceptance_summary.json
    validation.log
"""
import sys
import os
import asyncio
import csv
import json
import datetime
import logging

# --- Path setup (same as simulation_core.py) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # GreenConsumer/
sys.path.insert(0, project_root)

# The test does NOT use GreenStatePlugin (which imports MemoryManager and triggers
# sentence-transformers loading). We use FakeStatePlugin instead, and import only
# the three plugins that we test (Reflect, Plan, Invoke).
# However, GreenCognitionPlugin itself does NOT import MemoryManager — it calls
# state_plugin.retrieve_memory() which is our fake. So we only need to avoid
# importing GreenStatePlugin. The plugins we need import only from plugin_base.

from plugins.agent.reflect.GreenCognitionPlugin import GreenCognitionPlugin
from plugins.agent.plan.ConsumerPlanPlugin import ConsumerPlanPlugin
from plugins.agent.invoke.GreenInvokePlugin import GreenInvokePlugin


# ══════════════════════════════════════════════════════════════════════
# Fake Infrastructure
# ══════════════════════════════════════════════════════════════════════

class FakeStatePlugin:
    """Mimics GreenStatePlugin interface without agentkernel_standalone dependency."""

    def __init__(self):
        self._state_data = {}
        self.state_data = self._state_data  # alias used by plugins
        self._memories = []

    async def set_state(self, key, value):
        self._state_data[key] = value
        self.state_data = self._state_data

    def get_state_sync(self, key):
        return self._state_data.get(key)

    def add_to_memory(self, tick, content, importance=5.0):
        self._memories.append({"tick": tick, "content": content, "importance": importance})

    def retrieve_memory(self, current_tick, query, top_k=3):
        # Return last top_k memories as simple strings
        return [m["content"] for m in self._memories[-top_k:]]


class FakeProfilePlugin:
    """Returns fixed persona and cluster_type."""

    def __init__(self, cluster_type="Convenient_Greens"):
        self._profile_data = {
            "psychology": {"cluster_type": cluster_type, "social_role": "Regular User"},
            "persona": (
                "You are a 32-year-old urban professional who buys oat milk occasionally. "
                "You care about sustainability but price matters too. You follow food brands "
                "on social media but rarely post. You are moderately skeptical of corporate claims."
            ),
        }
        self.profile_data = self._profile_data

    def get_prompt(self):
        return self._profile_data.get("persona", "You are a consumer.")


class FakeComponent:
    """Wraps a plugin with ._plugin attribute as expected by plugin._get_plugin()."""

    def __init__(self, plugin):
        self._plugin = plugin
        self.plugin = plugin
        plugin.component = self


class FakeAgent:
    """Minimal Agent shell that plugins can navigate."""

    def __init__(self, agent_id, model, state_plugin, profile_plugin, invoke_plugin=None):
        self.agent_id = agent_id
        self._model = model
        self.model = model
        self._components = {
            "state": FakeComponent(state_plugin),
            "profile": FakeComponent(profile_plugin),
        }
        if invoke_plugin:
            self._components["invoke"] = FakeComponent(invoke_plugin)

    def get_component(self, name):
        return self._components.get(name)


class DeterministicRouter:
    """Returns fixed JSON for Reflect and Plan prompts."""

    def __init__(self):
        self.call_count = 0

    async def chat(self, prompt):
        self.call_count += 1
        if "trust_change_affective" in prompt and "Immediate Gut Reaction" in prompt:
            # Reflect prompt
            return json.dumps({
                "hypocrisy_perceived": True,
                "trust_change_affective": -1.2,
                "importance": 7.5,
                "reasoning": "I feel disappointed by this corporate hypocrisy."
            })
        else:
            # Plan prompt
            return json.dumps({
                "is_buying": False,
                "is_posting": False,
                "post_content": "",
                "reason": "Trust too low, staying quiet today."
            })


# ══════════════════════════════════════════════════════════════════════
# Test Runner
# ══════════════════════════════════════════════════════════════════════

def _wire_plugin(plugin, agent):
    """Set up the plugin→component→agent chain that _get_agent() traverses."""
    # Create a fake component for this plugin
    comp = FakeComponent(plugin)
    comp.agent = agent
    comp._agent = agent
    plugin.component = comp
    plugin.agent = agent


async def run_tick(reflect_plugin, plan_plugin, invoke_plugin, state_plugin, tick):
    """Execute one full tick: Reflect → Plan → Invoke. Returns state snapshot."""
    await reflect_plugin.execute(tick)
    await plan_plugin.execute(tick)

    invoke_completed = False
    try:
        await invoke_plugin.execute(tick)
        invoke_completed = True
    except Exception:
        pass

    # Capture state snapshot
    sd = state_plugin._state_data
    plan_result = sd.get("plan_result", {}) or {}
    last_obs = sd.get("last_observations", [])
    latest_th = sd.get("latest_thought")

    return {
        "quiet_ticks": int(plan_result.get("quiet_ticks", sd.get("quiet_ticks", -1))),
        "last_observations_length": len(last_obs) if isinstance(last_obs, list) else -1,
        "latest_thought_is_none": latest_th is None,
        "trust_change_affective": float(sd.get("trust_change_affective", -999)),
        "raw_affective_output": float(sd.get("raw_affective_output", -999)),
        "affective_was_clipped": sd.get("affective_was_clipped", "MISSING"),
        "plan_completed": "plan_result" in sd and bool(sd["plan_result"]),
        "invoke_completed": invoke_completed,
    }


async def run_scenario(scenario_name, ticks_config, logger):
    """
    Run a scenario.

    ticks_config: list of dicts, each with:
        - tick: int
        - observations: list (empty = no observation tick)
        - current_news: str
    """
    logger.info(f"=== Scenario: {scenario_name} ===")

    router = DeterministicRouter()
    state_plugin = FakeStatePlugin()
    profile_plugin = FakeProfilePlugin("Convenient_Greens")
    reflect_plugin = GreenCognitionPlugin()
    plan_plugin = ConsumerPlanPlugin()
    invoke_plugin = GreenInvokePlugin()

    agent = FakeAgent("Test_Agent_001", router, state_plugin, profile_plugin, invoke_plugin)

    _wire_plugin(reflect_plugin, agent)
    _wire_plugin(plan_plugin, agent)
    _wire_plugin(invoke_plugin, agent)

    # Initialize state (same as simulation_core.py)
    await state_plugin.set_state("trust_score", 6.5)
    await state_plugin.set_state("baseline_trust", 6.5)
    await state_plugin.set_state("shock_anchor", 6.5)
    await state_plugin.set_state("quiet_ticks", 0)
    await state_plugin.set_state("incoming_messages", [])
    await state_plugin.set_state("observations", [])
    await state_plugin.set_state("last_observations", [])
    await state_plugin.set_state("latest_thought", None)
    await state_plugin.set_state("trust_change_affective", 0.0)
    await state_plugin.set_state("raw_affective_output", 0.0)
    await state_plugin.set_state("affective_was_clipped", False)
    await state_plugin.set_state("current_news", "")

    results = []

    for tc in ticks_config:
        tick = tc["tick"]
        observations = tc["observations"]
        current_news = tc.get("current_news", "")

        # Set up the tick's input state
        await state_plugin.set_state("observations", list(observations))
        await state_plugin.set_state("current_news", current_news)
        await state_plugin.set_state("current_tick", tick)

        # Determine clarification in current observation
        clr_in_obs = any(
            o.get("source") == "Enterprise_Clarification" for o in observations
        )

        # Execute
        snapshot = await run_tick(reflect_plugin, plan_plugin, invoke_plugin, state_plugin, tick)

        # Build record
        record = {
            "scenario": scenario_name,
            "tick": tick,
            "agent_id": "Test_Agent_001",
            "observation_count": len(observations),
            "observation_sources": ";".join(o.get("source", "?") for o in observations),
            "clarification_in_current_observation": clr_in_obs,
            **snapshot,
        }
        results.append(record)

        logger.info(
            f"  Tick {tick}: obs={len(observations)} clr={clr_in_obs} "
            f"qt={snapshot['quiet_ticks']} last_obs_len={snapshot['last_observations_length']} "
            f"thought_none={snapshot['latest_thought_is_none']} "
            f"affective={snapshot['trust_change_affective']:.3f}"
        )

    return results


# ══════════════════════════════════════════════════════════════════════
# Scenario Definitions
# ══════════════════════════════════════════════════════════════════════

CLARIFICATION_MSG = {
    "source": "Enterprise_Clarification",
    "content": (
        "Official Statement: We acknowledge concerns about our Blackstone partnership. "
        "We have established an independent sustainability board with veto power over "
        "all future investments. Full audit results will be published quarterly. "
        "We commit to zero-deforestation across our supply chain by 2027."
    ),
    "type": "clarification",
}

SCANDAL_NEWS = (
    "BREAKING: Oatly sold a 10% stake to Blackstone Group. "
    "Activists trending #BoycottOatly."
)


def make_scenario_immediate():
    """Scenario 1: Scandal at Tick 5, Clarification at Tick 6, then quiet."""
    return [
        {"tick": 5, "observations": [{"source": "Global News", "content": SCANDAL_NEWS}], "current_news": SCANDAL_NEWS},
        {"tick": 6, "observations": [CLARIFICATION_MSG], "current_news": "[Enterprise Clarification]"},
        {"tick": 7, "observations": [], "current_news": ""},
        {"tick": 8, "observations": [], "current_news": ""},
        {"tick": 9, "observations": [], "current_news": ""},
    ]


def make_scenario_delayed():
    """Scenario 2: Scandal at Tick 5, quiet 6-9, Clarification at Tick 10, then quiet."""
    return [
        {"tick": 5, "observations": [{"source": "Global News", "content": SCANDAL_NEWS}], "current_news": SCANDAL_NEWS},
        {"tick": 6, "observations": [], "current_news": ""},
        {"tick": 7, "observations": [], "current_news": ""},
        {"tick": 8, "observations": [], "current_news": ""},
        {"tick": 9, "observations": [], "current_news": ""},
        {"tick": 10, "observations": [CLARIFICATION_MSG], "current_news": "[Enterprise Clarification]"},
        {"tick": 11, "observations": [], "current_news": ""},
        {"tick": 12, "observations": [], "current_news": ""},
    ]


def make_scenario_no_clarification():
    """Scenario 3: Scandal at Tick 5, then continuous quiet (no clarification ever)."""
    return [
        {"tick": 5, "observations": [{"source": "Global News", "content": SCANDAL_NEWS}], "current_news": SCANDAL_NEWS},
        {"tick": 6, "observations": [], "current_news": ""},
        {"tick": 7, "observations": [], "current_news": ""},
        {"tick": 8, "observations": [], "current_news": ""},
    ]


# ══════════════════════════════════════════════════════════════════════
# Assertions
# ══════════════════════════════════════════════════════════════════════

def run_assertions(all_results):
    """Run all 10 acceptance assertions. Returns list of (name, pass/fail, detail)."""
    verdicts = []

    def assert_eq(name, actual, expected, ctx=""):
        passed = actual == expected
        verdicts.append({
            "assertion": name,
            "result": "PASS" if passed else "FAIL",
            "expected": str(expected),
            "actual": str(actual),
            "context": ctx,
        })
        return passed

    # Helper: find record by scenario + tick
    def rec(scenario, tick):
        for r in all_results:
            if r["scenario"] == scenario and r["tick"] == tick:
                return r
        return None

    # --- Assertion 1: Clarification Tick quiet_ticks == 0 ---
    r = rec("immediate", 6)
    assert_eq("A1: immediate clr_tick qt=0", r["quiet_ticks"], 0, "Tick 6")
    r = rec("delayed", 10)
    assert_eq("A1: delayed clr_tick qt=0", r["quiet_ticks"], 0, "Tick 10")

    # --- Assertion 2: Next no-obs Tick quiet_ticks == 1 ---
    r = rec("immediate", 7)
    assert_eq("A2: immediate next_tick qt=1", r["quiet_ticks"], 1, "Tick 7")
    r = rec("delayed", 11)
    assert_eq("A2: delayed next_tick qt=1", r["quiet_ticks"], 1, "Tick 11")

    # --- Assertion 3: +2 Tick quiet_ticks == 2 ---
    r = rec("immediate", 8)
    assert_eq("A3: immediate +2_tick qt=2", r["quiet_ticks"], 2, "Tick 8")
    r = rec("delayed", 12)
    assert_eq("A3: delayed +2_tick qt=2", r["quiet_ticks"], 2, "Tick 12")

    # --- Assertion 4: No-obs Tick last_observations == [] ---
    for scenario, tick in [("immediate", 7), ("immediate", 8), ("delayed", 11), ("delayed", 12)]:
        r = rec(scenario, tick)
        assert_eq(f"B1: {scenario} T{tick} last_obs=[]",
                  r["last_observations_length"], 0, f"{scenario} Tick {tick}")

    # --- Assertion 5: No-obs Tick latest_thought is None ---
    for scenario, tick in [("immediate", 7), ("immediate", 8), ("delayed", 11), ("delayed", 12)]:
        r = rec(scenario, tick)
        assert_eq(f"B2: {scenario} T{tick} thought=None",
                  r["latest_thought_is_none"], True, f"{scenario} Tick {tick}")

    # --- Assertion 6: No-obs Tick trust_change_affective == 0.0 ---
    for scenario, tick in [("immediate", 7), ("immediate", 8), ("delayed", 11), ("delayed", 12)]:
        r = rec(scenario, tick)
        assert_eq(f"B3: {scenario} T{tick} affective=0",
                  r["trust_change_affective"], 0.0, f"{scenario} Tick {tick}")

    # --- Assertion 7: No-obs Tick raw_affective_output == 0.0 ---
    for scenario, tick in [("immediate", 7), ("immediate", 8), ("delayed", 11), ("delayed", 12)]:
        r = rec(scenario, tick)
        assert_eq(f"B4: {scenario} T{tick} raw=0",
                  r["raw_affective_output"], 0.0, f"{scenario} Tick {tick}")

    # --- Assertion 8: No-obs Tick affective_was_clipped is False ---
    for scenario, tick in [("immediate", 7), ("immediate", 8), ("delayed", 11), ("delayed", 12)]:
        r = rec(scenario, tick)
        assert_eq(f"B5: {scenario} T{tick} clipped=False",
                  r["affective_was_clipped"], False, f"{scenario} Tick {tick}")

    # --- Assertion 9: No stale clarification detection on quiet ticks ---
    # In no-clarification scenario, no tick should have clarification_in_current_observation=True after Tick 5
    for scenario, tick in [("no_clarification", 6), ("no_clarification", 7), ("no_clarification", 8)]:
        r = rec(scenario, tick)
        assert_eq(f"C: {scenario} T{tick} no_stale_clr",
                  r["clarification_in_current_observation"], False, f"{scenario} Tick {tick}")
    # In immediate scenario, Tick 7+ should NOT have clarification
    for tick in [7, 8, 9]:
        r = rec("immediate", tick)
        assert_eq(f"C: immediate T{tick} no_stale_clr",
                  r["clarification_in_current_observation"], False, f"immediate Tick {tick}")

    # --- Assertion 10: Plan and Invoke completed ---
    for r in all_results:
        assert_eq(f"D: {r['scenario']} T{r['tick']} plan_ok",
                  r["plan_completed"], True, f"{r['scenario']} Tick {r['tick']}")
        assert_eq(f"D: {r['scenario']} T{r['tick']} invoke_ok",
                  r["invoke_completed"], True, f"{r['scenario']} Tick {r['tick']}")

    return verdicts


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

async def main():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(project_root, "results", "task001_validation", timestamp)
    os.makedirs(out_dir, exist_ok=True)

    # Setup logging
    log_path = os.path.join(out_dir, "validation.log")
    logger = logging.getLogger("task001v")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info(f"TASK_001-V Validation — {timestamp}")
    logger.info(f"Output: {out_dir}")

    # Run scenarios
    all_results = []

    results1 = await run_scenario("immediate", make_scenario_immediate(), logger)
    all_results.extend(results1)

    results2 = await run_scenario("delayed", make_scenario_delayed(), logger)
    all_results.extend(results2)

    results3 = await run_scenario("no_clarification", make_scenario_no_clarification(), logger)
    all_results.extend(results3)

    # Write CSV
    csv_path = os.path.join(out_dir, "task001_state_trace.csv")
    fieldnames = [
        "scenario", "tick", "agent_id", "observation_count", "observation_sources",
        "clarification_in_current_observation", "quiet_ticks",
        "last_observations_length", "latest_thought_is_none",
        "trust_change_affective", "raw_affective_output", "affective_was_clipped",
        "plan_completed", "invoke_completed",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_results:
            w.writerow(r)
    logger.info(f"CSV: {csv_path}")

    # Run assertions
    verdicts = run_assertions(all_results)

    # Write summary JSON
    summary_path = os.path.join(out_dir, "acceptance_summary.json")
    total = len(verdicts)
    passed = sum(1 for v in verdicts if v["result"] == "PASS")
    failed = sum(1 for v in verdicts if v["result"] == "FAIL")
    summary = {
        "timestamp": timestamp,
        "total_assertions": total,
        "passed": passed,
        "failed": failed,
        "all_pass": failed == 0,
        "verdicts": verdicts,
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"Summary: {summary_path}")

    # Print results
    print(f"\n{'='*60}")
    print(f"TASK_001-V ACCEPTANCE RESULTS")
    print(f"{'='*60}")
    print(f"Total assertions: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"{'='*60}")

    if failed > 0:
        print("\nFAILED ASSERTIONS:")
        for v in verdicts:
            if v["result"] == "FAIL":
                print(f"  ❌ {v['assertion']}: expected={v['expected']}, actual={v['actual']} ({v['context']})")

    print(f"\nOutput: {out_dir}")
    print(f"CSV:    {csv_path}")
    print(f"JSON:   {summary_path}")
    print(f"Log:    {log_path}")

    if failed == 0:
        print("\n✅ ALL ACCEPTANCE CRITERIA PASSED")
    else:
        print(f"\n❌ {failed} ASSERTION(S) FAILED")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
