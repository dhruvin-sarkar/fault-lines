"""Adaptive, batched node-removal strategies and the percolation loop that applies them."""

import math
from collections.abc import Sequence

import igraph as ig
import numpy as np
import pandas as pd

from pipeline.connectivity_metrics import flow_capacity, present_indices, reachable_pairs, unreachable_from

STRATEGIES = ("random", "out_strength", "in_strength", "betweenness", "pagerank", "sm_betweenness")
STRATEGY_LABELS = {
    "random": "random",
    "out_strength": "weighted out-degree",
    "in_strength": "weighted in-degree",
    "betweenness": "betweenness",
    "pagerank": "PageRank",
    "sm_betweenness": "sensory-motor betweenness",
}
BATCH_FRACTION = 0.01
MAX_FRACTION = 0.5


def strategy_scores(
    graph: ig.Graph, strategy: str, sources: Sequence[str], targets: Sequence[str], rng: np.random.Generator | None
) -> np.ndarray:
    """Current removal priority of every vertex; higher is removed first.

    Degree and PageRank use synapse counts (edge attribute ``weight``). Betweenness counts shortest paths
    by hop number. ``sm_betweenness`` counts only shortest paths from a source to a target.
    """
    if strategy == "random":
        return rng.random(graph.vcount())
    if strategy == "out_strength":
        return np.asarray(graph.strength(mode="out", weights="weight"), dtype=float)
    if strategy == "in_strength":
        return np.asarray(graph.strength(mode="in", weights="weight"), dtype=float)
    if strategy == "betweenness":
        return np.asarray(graph.betweenness(directed=True), dtype=float)
    if strategy == "pagerank":
        return np.asarray(graph.pagerank(directed=True, weights="weight"), dtype=float)
    if strategy == "sm_betweenness":
        src, tgt = present_indices(graph, sources), present_indices(graph, targets)
        if not src or not tgt:
            return np.zeros(graph.vcount())
        return np.asarray(graph.betweenness(directed=True, sources=src, targets=tgt), dtype=float)
    raise ValueError(f"Unknown strategy {strategy!r}; expected one of {STRATEGIES}")


def intact_scores(
    graph: ig.Graph, sources: Sequence[str], targets: Sequence[str], include_betweenness: bool = True
) -> pd.DataFrame:
    """Every deterministic strategy score on the given graph, plus unweighted in/out/total degree, one row per vertex."""
    table = pd.DataFrame(
        {
            "cell_type": graph.vs["name"],
            "in_degree": graph.indegree(),
            "out_degree": graph.outdegree(),
            "degree": graph.degree(mode="all"),
        }
    )
    for strategy in STRATEGIES:
        if strategy == "random" or (strategy == "betweenness" and not include_betweenness):
            continue
        table[strategy] = strategy_scores(graph, strategy, sources, targets, None)
    return table


def select_top(scores: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """Indices of the ``k`` highest scores, with ties broken in random order."""
    order = np.lexsort((rng.random(len(scores)), -scores))
    return order[:k]


def removal_schedule(n: int, batch_fraction: float = BATCH_FRACTION, max_fraction: float = MAX_FRACTION) -> list[int]:
    """Batch sizes: ceil(batch_fraction x remaining vertices), until at least max_fraction of n is removed."""
    sizes, removed = [], 0
    while removed < max_fraction * n and removed < n:
        size = min(max(1, math.ceil(batch_fraction * (n - removed))), n - removed)
        sizes.append(size)
        removed += size
    return sizes


def percolate(
    graph: ig.Graph,
    strategy: str,
    sources: Sequence[str],
    targets: Sequence[str],
    seed: int,
    max_fraction: float = MAX_FRACTION,
    batch_fraction: float = BATCH_FRACTION,
    continue_until_flow_below: float | None = None,
) -> dict:
    """Remove vertices in adaptive batches and track sensory-to-motor connectivity after each batch.

    Removal stops once ``max_fraction`` of the vertices are gone. With ``continue_until_flow_below`` set,
    it carries on past that point (same batch rule, same random stream) until flow falls below the given
    value, so the first ``max_fraction`` of the run is identical either way.

    Returns:
        ``fraction_removed``, ``flow`` and ``reachable_pairs`` (one entry for the intact graph, then one per
        batch); ``avalanche`` (per batch: vertices still present that lost every path from the remaining
        sources because of that batch); ``removed`` (per batch: names removed, highest priority first).
    """
    rng = np.random.default_rng(seed)
    working = graph.copy()
    n = graph.vcount()
    fraction, flow, pairs = [0.0], [flow_capacity(working, sources, targets)], [reachable_pairs(working, sources, targets)]
    cut = unreachable_from(working, sources)
    removed_batches, avalanche, removed = [], [], 0
    for size in removal_schedule(n, batch_fraction, max_fraction=1.0):
        if fraction[-1] >= max_fraction and (continue_until_flow_below is None or flow[-1] < continue_until_flow_below):
            break
        chosen = select_top(strategy_scores(working, strategy, sources, targets, rng), size, rng)
        removed_batches.append([working.vs[int(i)]["name"] for i in chosen])
        working.delete_vertices(chosen.tolist())
        removed += size
        fraction.append(removed / n)
        flow.append(flow_capacity(working, sources, targets))
        pairs.append(reachable_pairs(working, sources, targets))
        now_cut = unreachable_from(working, sources)
        avalanche.append(len(now_cut - cut))
        cut = now_cut
    return {
        "strategy": strategy,
        "seed": seed,
        "fraction_removed": np.asarray(fraction),
        "flow": np.asarray(flow),
        "reachable_pairs": np.asarray(pairs),
        "avalanche": np.asarray(avalanche),
        "removed": removed_batches,
    }


def normalized_auc(fraction_removed: np.ndarray, values: np.ndarray, baseline: float) -> float:
    """Area under ``values / baseline`` against fraction removed, divided by the x-range.

    Equals the mean retained fraction over the removal range: 1 for a curve that never drops, 0 for one
    that is zero immediately. Lower means more fragile.
    """
    if baseline <= 0:
        raise ValueError("Baseline must be positive to normalize a percolation curve")
    x = np.asarray(fraction_removed, dtype=float)
    return float(np.trapezoid(np.asarray(values, dtype=float) / baseline, x) / (x[-1] - x[0]))
