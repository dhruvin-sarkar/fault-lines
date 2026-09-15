"""Degree-preserving randomization test for the fragility (AUC) of each removal strategy."""

import random

import igraph as ig
import numpy as np

SWAPS_PER_EDGE = 10


def rewire(graph: ig.Graph, seed: int, swaps_per_edge: int = SWAPS_PER_EDGE) -> ig.Graph:
    """Randomize edges with in/out-degree-preserving swaps.

    Every vertex keeps its exact in-degree and out-degree. Each source vertex's original set of
    out-edge synapse counts is reassigned, shuffled, to its new out-edges, so out-strength is also
    preserved while the identity of downstream partners is randomized.
    """
    null = graph.copy()
    random.seed(seed)
    null.rewire(n=swaps_per_edge * graph.ecount(), allowed_edge_types="simple")

    rng = np.random.default_rng(seed)
    old_sources = np.asarray(graph.get_edgelist(), dtype=np.int64).reshape(-1, 2)[:, 0]
    new_sources = np.asarray(null.get_edgelist(), dtype=np.int64).reshape(-1, 2)[:, 0]
    old_weights = np.asarray(graph.es["weight"])
    old_order = np.lexsort((rng.random(len(old_sources)), old_sources))
    new_order = np.argsort(new_sources, kind="stable")
    weights = np.empty_like(old_weights)
    weights[new_order] = old_weights[old_order]
    null.es["weight"] = weights.tolist()
    if "input_fraction" in null.es.attributes():
        del null.es["input_fraction"]
    return null


def empirical_p_value_lower(real: float, null: np.ndarray) -> float:
    """One-sided permutation p-value for real < null, with the +1 correction so it is never exactly zero."""
    return float((1 + np.sum(np.asarray(null) <= real)) / (1 + len(null)))
