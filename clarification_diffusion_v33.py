"""TASK_005 FMCG v3.3 clarification reach.

This module keeps the v3.2 communication budget and network topology while
changing how exposure is realised:

- public organic exposure is Bernoulli by Agent rather than an exact fixed share;
- paid seeds still receive the enterprise clarification with certainty at t0;
- one-hop paid amplification is a reproducible probability process over actual
  directed edges and is delivered at t0 + lag instead of the same Tick;
- downstream organic diffusion still occurs only through consumers' own posts in
  SocialNetworkPlugin.

The probabilities below are development engineering assumptions and require
sensitivity analysis.  They are not empirical reach estimates.
"""
from __future__ import annotations

from clarification_injector import ClarificationInjector
from mechanism_v2 import clip01, deterministic_uniform

SCHEMA = "clarification-diffusion-3.3"
DEFAULT_PUBLIC_EXPOSURE_RATE = 0.25
DEFAULT_PAID_EDGE_PROBABILITY = 0.55
DEFAULT_PAID_DELIVERY_LAG = 1


def select_public_exposure_nodes_v33(
    nodes,
    base_seed: int,
    rate: float = DEFAULT_PUBLIC_EXPOSURE_RATE,
):
    """Condition-blocked Bernoulli public exposure using deterministic draws."""

    r = clip01(rate)
    selected = []
    for node in sorted(str(value) for value in nodes):
        draw = deterministic_uniform(
            int(base_seed), node, 0, "v33_public_organic_exposure"
        )
        if draw < r:
            selected.append(node)
    return selected


def select_paid_amplification_nodes_v33(
    graph,
    seed_nodes,
    *,
    base_seed: int,
    edge_probability: float = DEFAULT_PAID_EDGE_PROBABILITY,
):
    """Return actual successful one-hop paid amplification recipients.

    Each directed seed->successor edge receives an independent deterministic
    Bernoulli draw.  A target reached by at least one successful edge is included
    once.  Paid seeds themselves are excluded from the amplified set.
    """

    p = clip01(edge_probability)
    seeds = {str(node) for node in seed_nodes}
    reached = set()
    if not seeds or p <= 0.0:
        return []

    for seed in sorted(seeds):
        if seed not in graph:
            continue
        neighbors = (
            graph.successors(seed)
            if graph.is_directed()
            else graph.neighbors(seed)
        )
        for target in sorted(str(node) for node in neighbors):
            if target in seeds:
                continue
            edge_id = f"{seed}->{target}"
            draw = deterministic_uniform(
                int(base_seed), edge_id, 0, "v33_paid_one_hop_delivery"
            )
            if draw < p:
                reached.add(target)
    return sorted(reached)


class ClarificationInjectorV33(ClarificationInjector):
    """Two-stage enterprise clarification injector compatible with simulation_core.

    t0: public organic recipients + paid seed recipients
    t0+lag: successful one-hop paid amplification recipients not already exposed

    The base class still supplies the message template and audit setters.
    """

    def __init__(self, config, delivery_lag: int = DEFAULT_PAID_DELIVERY_LAG):
        super().__init__(config)
        self.delivery_lag = int(delivery_lag)
        if self.delivery_lag < 0:
            raise ValueError("delivery_lag must be non-negative")
        self._already_injected = set()

    async def inject(self, agents, current_tick: int) -> int:
        self.last_injected_ids = []
        self.last_exposure_modes = {}

        if self.clarification_tick is None:
            return 0

        t0 = int(self.clarification_tick)
        tick = int(current_tick)
        if tick == t0:
            recipients = set(self.public_exposure_nodes) | set(self.target_nodes)
            stage = "direct"
        elif tick == t0 + self.delivery_lag and self.delivery_lag > 0:
            recipients = set(self.amplified_nodes) - set(self._already_injected)
            stage = "paid_one_hop_lagged"
        elif tick == t0 and self.delivery_lag == 0:
            recipients = (
                set(self.public_exposure_nodes)
                | set(self.target_nodes)
                | set(self.amplified_nodes)
            )
            stage = "direct_plus_one_hop"
        else:
            return 0

        if not recipients:
            return 0

        base_msg = self.get_message()
        injected_ids = []
        for ag in agents:
            if ag.agent_id not in recipients:
                continue

            modes = []
            if ag.agent_id in self.public_exposure_nodes:
                modes.append("public_organic")
            if ag.agent_id in self.target_nodes:
                modes.append("paid_seed")
            if ag.agent_id in self.amplified_nodes:
                modes.append("paid_one_hop")

            msg = dict(base_msg)
            msg["exposure_modes"] = list(modes)
            msg["delivery_stage"] = stage
            msg["diffusion_schema"] = SCHEMA

            state_plugin = ag.get_component("state")._plugin
            s_data = getattr(
                state_plugin,
                "state_data",
                getattr(state_plugin, "_state_data", {}),
            )
            inbox = s_data.get("incoming_messages", [])
            await state_plugin.set_state(
                "incoming_messages", list(inbox) + [msg]
            )
            injected_ids.append(ag.agent_id)
            self.last_exposure_modes[ag.agent_id] = list(modes)

        self.last_injected_ids = injected_ids
        self._already_injected.update(injected_ids)

        if injected_ids:
            content_short = (
                "Rational"
                if self.content_factor == "rational-evidence"
                else "Empathy"
            )
            print(
                f"[Clarification-v3.3] Tick {tick} | Stage={stage} | "
                f"Content={content_short} | Reached={len(injected_ids)}"
            )
        return len(injected_ids)
