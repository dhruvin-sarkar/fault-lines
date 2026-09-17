"""Remove connections instead of cell types, to separate synapse count from routing capacity."""

import argparse
import json
from pathlib import Path

import igraph as ig
import numpy as np
import pandas as pd

from pipeline.build_type_graph import load_type_graph
from pipeline.common import RESULTS, SEED
from pipeline.connectivity_metrics import flow_capacity, reachable_pairs
from pipeline.figures import GRID, INK, INK_SECONDARY, STRATEGY_COLORS, apply_style, plt
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets

BATCH_FRACTION = 0.01
MAX_FRACTION = 0.5
RANDOM_TRIALS = 5
ORDERS = {
    "strongest": "strongest connections first",
    "weakest": "weakest connections first",
    "random": "random connections",
}
COLORS = {"strongest": STRATEGY_COLORS["out_strength"], "weakest": STRATEGY_COLORS["pagerank"],
          "random": STRATEGY_COLORS["random"]}


def removal_order(graph: ig.Graph, order: str, seed: int) -> np.ndarray:
    """Edge indices in the order they are removed, ties broken by a seeded random key."""
    rng = np.random.default_rng(seed)
    weights = np.asarray(graph.es["weight"], dtype=float)
    jitter = rng.random(len(weights))
    if order == "strongest":
        return np.lexsort((jitter, -weights))
    if order == "weakest":
        return np.lexsort((jitter, weights))
    if order == "random":
        return rng.permutation(len(weights))
    raise ValueError(f"Unknown order: {order}")


def percolate_edges(graph: ig.Graph, order: str, sources: list[str], targets: list[str], seed: int) -> dict:
    """Flow capacity and reachability after each batch of connection removals, up to half the connections."""
    sequence = removal_order(graph, order, seed)
    batch = max(1, int(round(BATCH_FRACTION * graph.ecount())))
    fractions = [0.0]
    flow = [flow_capacity(graph, sources, targets)]
    pairs = [reachable_pairs(graph, sources, targets)]
    for removed in range(batch, int(MAX_FRACTION * graph.ecount()) + 1, batch):
        working = graph.copy()
        working.delete_edges(sequence[:removed].tolist())
        fractions.append(removed / graph.ecount())
        flow.append(flow_capacity(working, sources, targets))
        pairs.append(reachable_pairs(working, sources, targets))
    return {"order": order, "fraction_removed": fractions, "flow": flow, "reachable_pairs": pairs}


def critical_fraction(fractions: list[float], flow: list[int]) -> float | None:
    """Removed fraction where flow first falls below half its intact value, interpolated between batches.

    Returns None when flow never halves within the removed range.
    """
    series = np.asarray(flow, dtype=float)
    half = series[0] / 2
    below = np.flatnonzero(series < half)
    if not len(below):
        return None
    crossing = int(below[0])
    x0, x1 = fractions[crossing - 1], fractions[crossing]
    y0, y1 = series[crossing - 1], series[crossing]
    return float(x0 + (x1 - x0) * (y0 - half) / (y0 - y1))


def share(fraction: float | None) -> str:
    return f"{100 * fraction:.1f}%" if fraction is not None else f"not reached by {100 * MAX_FRACTION:.0f}%"


def summarize_trials(runs: list[dict]) -> dict:
    """Critical fraction of every trial of one removal order, with their mean and range.

    Parameters: ``runs``, results of :func:`percolate_edges` for one order, in trial order.
    Returns ``critical_fraction`` (mean over trials), ``critical_fraction_trials`` and ``critical_fraction_range``
    ([min, max]). The mean and range are None when any trial does not halve flow within the removed range.
    """
    values = [critical_fraction(run["fraction_removed"], run["flow"]) for run in runs]
    reached = bool(values) and None not in values
    return {
        "critical_fraction": float(np.mean(values)) if reached else None,
        "critical_fraction_trials": values,
        "critical_fraction_range": [min(values), max(values)] if reached else None,
    }


def load_trials(path: Path, edges: int) -> dict[str, list[dict]]:
    """Runs per removal order and trial, read back from an ``edge_attack.csv`` table.

    Parameters: ``path`` to the CSV; ``edges``, the connection count of the graph, used to restore the exact
    removed fractions from their rounded values in the CSV.
    Returns a mapping from order to its runs, in trial order, shaped like :func:`percolate_edges` output.
    """
    table = pd.read_csv(path)
    trials: dict[str, list[dict]] = {}
    for order in ORDERS:
        trials[order] = [
            {"order": order,
             "fraction_removed": (np.rint(group["fraction_removed"].to_numpy() * edges) / edges).tolist(),
             "flow": group["flow"].astype(int).tolist(),
             "reachable_pairs": group["reachable_pairs"].astype(int).tolist()}
            for _, group in table[table["order"] == order].groupby("trial", sort=True)
        ]
    return trials


def build_summary(trials: dict[str, list[dict]], edges: int) -> dict:
    """Summary written to ``edge_attack.json``.

    Parameters: ``trials``, runs per order in trial order; ``edges``, the connection count of the graph.
    Returns curves from the first trial of each order and critical fractions summarised over all trials.
    """
    return {
        "edges": edges, "intact_flow": trials["strongest"][0]["flow"][0],
        "batch_fraction_of_edges": BATCH_FRACTION, "random_trials": len(trials["random"]),
        "orders": {order: {"label": ORDERS[order], "color": COLORS[order], **summarize_trials(runs),
                           "fraction_removed": runs[0]["fraction_removed"], "flow": runs[0]["flow"],
                           "reachable_pairs": runs[0]["reachable_pairs"]}
                   for order, runs in trials.items()},
    }


def critical_label(order: dict) -> str:
    """Critical fraction of one order for the report table, with the range when several trials were run."""
    trials = order["critical_fraction_trials"]
    if len(trials) < 2 or order["critical_fraction"] is None:
        return share(order["critical_fraction"])
    low, high = order["critical_fraction_range"]
    return f"{share(order['critical_fraction'])} (mean of {len(trials)} trials, range {share(low)} to {share(high)})"


def report_lines(summary: dict) -> list[str]:
    """Lines of ``edge_attack.md`` for a summary returned by :func:`build_summary`."""
    orders = summary["orders"]
    strongest = orders["strongest"]["critical_fraction"]
    weakest = orders["weakest"]["critical_fraction"]
    random_order = orders["random"]
    n_random = len(random_order["critical_fraction_trials"])
    if n_random > 1 and random_order["critical_fraction"] is not None:
        low, high = random_order["critical_fraction_range"]
        random_text = (f"a mean of {share(random_order['critical_fraction'])} for random connections ({share(low)} to "
                       f"{share(high)} over {n_random} random orders)")
    else:
        random_text = f"{share(random_order['critical_fraction'])} for random connections"
    return [
        "# Removing connections instead of cell types",
        "",
        "Flow capacity counts edge-disjoint routes, so in this metric every connection between two cell types counts "
        "once whatever its synapse count. Ordering connections by strength therefore tests something specific: "
        "whether the connections carrying the most synapses are also the ones carrying the routing.",
        "",
        f"Connections are removed in batches of {100 * BATCH_FRACTION:.0f}% of the {summary['edges']:,} connections, up "
        "to half of them, with flow capacity and sensory-motor reachability measured after every batch. The random "
        f"order is drawn {n_random} times; the figure shows the first draw.",
        "",
        "| order | connections removed when flow halves |",
        "|---|---|",
        *[f"| {ORDERS[order]} | {critical_label(orders[order])} |" for order in ORDERS],
        "",
        f"Removing the strongest connections first halves routing capacity after {share(strongest)} of them are "
        f"gone, against {random_text}"
        + (f" and {share(weakest)} for the weakest first. " if weakest is not None else
           f"; removing the weakest first never halves it within the first {100 * MAX_FRACTION:.0f}%. ") +
        "Synapse count and routing capacity are related but not the same: a heavy connection can be redundant, and a "
        "thin one can be the only way across.",
        "",
        "![Flow capacity under connection removal](edge_attack.png)",
        "",
    ]


def plot(runs: dict, intact_flow: int) -> None:
    apply_style()
    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=200)
    for order, run in runs.items():
        ax.plot(run["fraction_removed"], np.asarray(run["flow"]) / intact_flow, color=COLORS[order],
                linewidth=2, label=ORDERS[order])
    ax.axhline(0.5, color=GRID, linestyle="--", linewidth=1)
    ax.set_xlabel("fraction of connections removed")
    ax.set_ylabel("flow capacity remaining")
    ax.set_ylim(0, 1.02)
    ax.set_title("Removing connections rather than cell types", loc="left", color=INK)
    ax.text(0.005, 0.52, "half of intact capacity", color=INK_SECONDARY, fontsize=8.5)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(RESULTS / "edge_attack.png")
    plt.close(fig)


def write_outputs(trials: dict[str, list[dict]], edges: int, figure: bool = True) -> None:
    """Write ``edge_attack.json``, ``edge_attack.md`` and optionally the figure from runs per order."""
    summary = build_summary(trials, edges)
    if figure:
        plot({order: runs[0] for order, runs in trials.items()}, summary["intact_flow"])
    (RESULTS / "edge_attack.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = report_lines(summary)
    (RESULTS / "edge_attack.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=RANDOM_TRIALS)
    parser.add_argument("--from-csv", action="store_true",
                        help="rebuild the JSON and report from results/edge_attack.csv instead of recomputing")
    args = parser.parse_args()

    graph = load_type_graph()
    if args.from_csv:
        write_outputs(load_trials(RESULTS / "edge_attack.csv", graph.ecount()), graph.ecount(), figure=False)
        return

    sources, targets = load_sensory_motor_sets()
    trials, rows = {}, []
    for order in ORDERS:
        trials[order] = []
        for trial in range(args.trials if order == "random" else 1):
            run = percolate_edges(graph, order, sources, targets, SEED + 31 * trial)
            trials[order].append(run)
            for i, fraction in enumerate(run["fraction_removed"]):
                rows.append({"order": order, "trial": trial, "fraction_removed": fraction,
                             "flow": run["flow"][i], "reachable_pairs": run["reachable_pairs"][i]})
            print(f"{order} trial {trial}: f_c = {share(critical_fraction(run['fraction_removed'], run['flow']))}",
                  flush=True)
    pd.DataFrame(rows).to_csv(RESULTS / "edge_attack.csv", index=False, float_format="%.6g")
    write_outputs(trials, graph.ecount())


if __name__ == "__main__":
    main()
