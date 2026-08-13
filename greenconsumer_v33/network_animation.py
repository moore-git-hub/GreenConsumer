"""Network-state and information-flow animation for TASK_005 v3.3.1 runs.

The BA topology is static in the current model. Therefore these GIFs must not
be described as *topology evolution*. They visualize evolution of node states
(Trust), enterprise clarification exposure, posting activity, and UGC broadcast
edges on a fixed directed network for every Tick actually present in the run.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import networkx as nx
import pandas as pd


CONTROL = "NoClarification-Control"


def _as_bool(series):
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})


def _load_network(run_dir: Path) -> tuple[nx.DiGraph, pd.DataFrame]:
    nodes_path = run_dir / "network_nodes.csv"
    edges_path = run_dir / "network_edges.csv"
    if not nodes_path.exists() or not edges_path.exists():
        raise FileNotFoundError(
            "network_nodes.csv/network_edges.csv are required. "
            "Re-run with the v3.3.1 runner that persists actual topology audit files."
        )

    nodes = pd.read_csv(nodes_path)
    edges = pd.read_csv(edges_path)
    graph = nx.DiGraph()
    for node in nodes["agent_id"].astype(str):
        graph.add_node(node)
    for row in edges.itertuples(index=False):
        graph.add_edge(str(row.source_agent_id), str(row.target_agent_id))
    return graph, nodes


def animate_network_state(
    run_dir: Path,
    *,
    condition: str,
    output_path: Path | None = None,
    fps: int = 3,
    layout_seed: int = 20260815,
) -> str:
    """Create a GIF spanning the complete realized Tick horizon of one condition.

    Visual encodings:
    - node fill: Trust score (fixed 0..10 scale);
    - node size: out-degree (structural prominence);
    - gold ring: enterprise clarification observed on this Tick;
    - black ring: Agent posts UGC on this Tick;
    - orange edges: UGC broadcast edges from posting Agents after this Tick.
    """

    run_dir = Path(run_dir)
    graph, nodes = _load_network(run_dir)
    records = pd.read_csv(run_dir / "agent_records.csv")
    records = records[records["exp_id"].astype(str) == str(condition)].copy()
    if records.empty:
        raise ValueError(f"condition not found in agent_records.csv: {condition}")

    records["tick"] = records["tick"].astype(int)
    records["agent_id"] = records["agent_id"].astype(str)
    records["trust_score"] = pd.to_numeric(records["trust_score"], errors="coerce")
    records["is_posting"] = _as_bool(records["is_posting"])
    records["clarification_received"] = _as_bool(records["clarification_received"])

    node_order = list(nodes["agent_id"].astype(str))
    out_degree = dict(
        zip(
            node_order,
            pd.to_numeric(nodes["out_degree"], errors="coerce").fillna(0),
        )
    )
    sizes = [360 + 90 * float(out_degree.get(node, 0)) for node in node_order]

    # Fix layout across all frames so node motion is not mistaken for topology change.
    pos = nx.spring_layout(graph.to_undirected(), seed=int(layout_seed), k=0.7)
    ticks = sorted(records["tick"].unique())

    if output_path is None:
        out_dir = run_dir / "thesis_outputs" / "animations"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = condition.replace("/", "_").replace(" ", "_")
        output_path = out_dir / f"network_state_diffusion_{safe}.gif"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 8))

    def draw_frame(tick: int):
        ax.clear()
        frame = records[records["tick"] == int(tick)].set_index("agent_id")
        trust = [float(frame.loc[node, "trust_score"]) for node in node_order]
        posting = {
            node
            for node in node_order
            if node in frame.index and bool(frame.loc[node, "is_posting"])
        }
        clarification = {
            node
            for node in node_order
            if node in frame.index and bool(frame.loc[node, "clarification_received"])
        }
        active_edges = [(u, v) for u, v in graph.edges() if u in posting]
        quiet_edges = [(u, v) for u, v in graph.edges() if u not in posting]

        nx.draw_networkx_edges(
            graph,
            pos,
            edgelist=quiet_edges,
            ax=ax,
            edge_color="#c7c7c7",
            alpha=0.28,
            arrows=True,
            arrowsize=10,
            width=0.7,
        )
        if active_edges:
            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=active_edges,
                ax=ax,
                edge_color="#e67e22",
                alpha=0.9,
                arrows=True,
                arrowsize=13,
                width=2.0,
            )

        nodes_artist = nx.draw_networkx_nodes(
            graph,
            pos,
            nodelist=node_order,
            node_color=trust,
            cmap="viridis",
            vmin=0.0,
            vmax=10.0,
            node_size=sizes,
            linewidths=0.7,
            edgecolors="#555555",
            ax=ax,
        )

        if clarification:
            ordered = sorted(clarification)
            nx.draw_networkx_nodes(
                graph,
                pos,
                nodelist=ordered,
                node_color="none",
                node_size=[sizes[node_order.index(n)] + 120 for n in ordered],
                edgecolors="#f1c40f",
                linewidths=3.0,
                ax=ax,
            )
        if posting:
            ordered = sorted(posting)
            nx.draw_networkx_nodes(
                graph,
                pos,
                nodelist=ordered,
                node_color="none",
                node_size=[sizes[node_order.index(n)] + 55 for n in ordered],
                edgecolors="#111111",
                linewidths=2.0,
                ax=ax,
            )

        nx.draw_networkx_labels(
            graph,
            pos,
            labels={n: n.replace("Consumer_", "C") for n in node_order},
            font_size=7,
            ax=ax,
        )

        event = ""
        if tick == 5:
            event = " | Crisis"
        elif tick == 6 and condition.endswith("Immediate"):
            event = " | Immediate clarification"
        elif tick == 10 and condition.endswith("Delayed"):
            event = " | Delayed clarification"

        ax.set_title(
            f"Fixed network, evolving Trust and information flow\n"
            f"{condition} | Tick {tick}{event}"
        )
        ax.text(
            0.01,
            0.01,
            "Node fill = Trust | size = out-degree | gold = enterprise clarification | "
            "black = posting | orange = UGC broadcast",
            transform=ax.transAxes,
            fontsize=8,
            va="bottom",
        )
        ax.axis("off")
        return [nodes_artist]

    animation = FuncAnimation(
        fig,
        draw_frame,
        frames=ticks,
        interval=1000 / max(1, int(fps)),
        blit=False,
        repeat=True,
    )
    animation.save(output_path, writer=PillowWriter(fps=max(1, int(fps))))
    plt.close(fig)
    return str(output_path)
