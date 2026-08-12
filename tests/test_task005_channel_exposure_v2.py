from __future__ import annotations

import asyncio
import inspect
import json
import sys
from pathlib import Path
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mechanism_v2 as m
from clarification_injector import ClarificationInjector
from experiment_config import (
    CONTROL_TIMING,
    NOT_APPLICABLE,
    ExperimentConfig,
)
import simulation_core
import run_experiments

P = 0
F = 0

def check(name, cond, actual=None):
    global P, F
    if cond:
        P += 1
        print("PASS", name)
    else:
        F += 1
        print("FAIL", name, actual)

nodes = [f"N{i:02d}" for i in range(20)]
p1 = m.select_public_exposure_nodes(nodes, 20260809)
p2 = m.select_public_exposure_nodes(nodes, 20260809)
check("public exposure reproducible", p1 == p2, (p1, p2))
check("default public exposure is 5 of 20", len(p1) == 5, p1)
check("public exposure unique", len(p1) == len(set(p1)), p1)

g = nx.DiGraph()
g.add_edges_from([
    ("H", "A"), ("H", "B"), ("H", "C"), ("H", "D"),
    ("R", "A"), ("A", "X"),
])
hub = m.one_hop_amplification_nodes(g, ["H"])
rnd = m.one_hop_amplification_nodes(g, ["R"])
check("hub toy one-hop > random toy one-hop", len(hub) > len(rnd), (hub, rnd))
check("seed excluded from own amplification", "H" not in hub and "R" not in rnd, (hub, rnd))

audit = m.build_exposure_audit(g, "Toy", ["A"], ["H"], hub)
by = {row["agent_id"]: row for row in audit}
check("audit public", by["A"]["public_organic"] is True, by["A"])
check("audit seed", by["H"]["paid_seed"] is True, by["H"])
check("audit one-hop", by["B"]["paid_one_hop"] is True, by["B"])

class State:
    def __init__(self):
        self._state_data = {"incoming_messages": []}
        self.state_data = self._state_data
    async def set_state(self, key, value):
        self._state_data[key] = value

class Comp:
    def __init__(self):
        self._plugin = State()

class Agent:
    def __init__(self, aid):
        self.agent_id = aid
        self.comp = Comp()
    def get_component(self, name):
        assert name == "state"
        return self.comp

cfg = ExperimentConfig(
    content_factor="rational-evidence",
    channel_factor="hub",
    timing_factor="immediate",
)
inj = ClarificationInjector(cfg)
inj.set_public_exposure_nodes(["A"])
inj.set_target_nodes(["H"])
inj.set_amplified_nodes(["A", "B", "C", "D"])
agents = [Agent(x) for x in ["H", "A", "B", "C", "D", "Z"]]
count = asyncio.run(inj.inject(agents, cfg.clarification_tick))
check("inject union exact", count == 5, count)
check("inject receipt exact", set(inj.last_injected_ids) == {"H","A","B","C","D"}, inj.last_injected_ids)
check("non-reached receives none", agents[-1].comp._plugin._state_data["incoming_messages"] == [])
check("overlap receives once", len(agents[1].comp._plugin._state_data["incoming_messages"]) == 1)
check(
    "overlap modes",
    set(inj.last_exposure_modes["A"]) == {"public_organic","paid_one_hop"},
    inj.last_exposure_modes["A"],
)

ctrl = ExperimentConfig(
    content_factor=NOT_APPLICABLE,
    channel_factor=NOT_APPLICABLE,
    timing_factor=CONTROL_TIMING,
    budget_k=0,
)
ctrl_inj = ClarificationInjector(ctrl)
ctrl_agents = [Agent(x) for x in ["A","H","B"]]
check("control inject zero", asyncio.run(ctrl_inj.inject(ctrl_agents, ctrl.clarification_tick)) == 0)
check("control receipt empty", ctrl_inj.last_injected_ids == [], ctrl_inj.last_injected_ids)

src = inspect.getsource(m.one_hop_amplification_nodes).lower()
check("no hub multiplier", "hub_multiplier" not in src)
check("no random multiplier", "random_multiplier" not in src)

sim_src = inspect.getsource(simulation_core.run_simulation_core)
check("control exposure empty", "public_exposure_nodes = []" in sim_src)
check("current_news actual receipt", "clarification_injected_ids" in sim_src)
check("runner exposure writer", hasattr(run_experiments, "write_clarification_exposure_csv"))
check("mechanism source hashed", "mechanism_v2.py" in run_experiments._HASHED_SOURCES)

registry = json.loads(
    (ROOT / ".kiro/specs/task005-replication-inference/mechanism_v2_parameter_registry.json")
    .read_text(encoding="utf-8")
)
check("public exposure assumption", registry["parameters"]["public_exposure_rate"]["source_type"] == "model_assumption")
check("paid seed assumption", registry["parameters"]["paid_seed_budget_k"]["source_type"] == "model_assumption")
check("no p tuning", registry["integrity"]["tune_until_p_lt_0_05"] is False)

print("\nTASK_005 CHANNEL EXPOSURE V2")
print("Passed:", P)
print("Failed:", F)
raise SystemExit(1 if F else 0)
