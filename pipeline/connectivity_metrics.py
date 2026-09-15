"""Sensory-to-motor connectivity metrics on a directed cell-type graph."""

from collections.abc import Iterable

import igraph as ig
import numpy as np


def present_indices(graph: ig.Graph, names: Iterable[str]) -> list[int]:
    """Vertex indices of the given names that are still in the graph, in input order."""
    index = {name: i for i, name in enumerate(graph.vs["name"])}
    return [index[n] for n in names if n in index]


def _check_disjoint(sources: list[int], targets: list[int]) -> None:
    shared = set(sources) & set(targets)
    if shared:
        raise ValueError(f"{len(shared)} vertices are in both the source and target sets")


def reachable_pairs(graph: ig.Graph, sources: Iterable[str], targets: Iterable[str]) -> int:
    """Number of (source, target) pairs joined by at least one directed path.

    Names not present in ``graph`` (for example removed vertices) are ignored.
    """
    src, tgt = present_indices(graph, sources), present_indices(graph, targets)
    _check_disjoint(src, tgt)
    if not src or not tgt:
        return 0
    return int(np.isfinite(np.asarray(graph.distances(source=src, target=tgt, mode="out"))).sum())


def reachability(graph: ig.Graph, sources: Iterable[str], targets: Iterable[str]) -> float:
    """Fraction of (source, target) pairs, among those present in ``graph``, joined by a directed path."""
    sources, targets = list(sources), list(targets)
    n_pairs = len(present_indices(graph, sources)) * len(present_indices(graph, targets))
    return reachable_pairs(graph, sources, targets) / n_pairs if n_pairs else 0.0


def flow_capacity(graph: ig.Graph, sources: Iterable[str], targets: Iterable[str]) -> int:
    """Maximum flow from a supersource feeding every source to a supersink fed by every target.

    Graph edges have unit capacity and the supersource/supersink edges are unbounded, so the value is
    the maximum number of edge-disjoint source-to-target paths (equivalently, the size of the smallest
    set of graph edges whose removal disconnects every target from every source).
    """
    src, tgt = present_indices(graph, sources), present_indices(graph, targets)
    _check_disjoint(src, tgt)
    if not src or not tgt:
        return 0
    n, edges = graph.vcount(), graph.get_edgelist()
    supersource, supersink = n, n + 1
    terminal_edges = [(supersource, s) for s in src] + [(t, supersink) for t in tgt]
    augmented = ig.Graph(n=n + 2, edges=edges + terminal_edges, directed=True)
    unbounded = len(edges) + 1
    capacity = [1] * len(edges) + [unbounded] * len(terminal_edges)
    return int(augmented.maxflow_value(supersource, supersink, capacity=capacity))


def unreachable_from(graph: ig.Graph, sources: Iterable[str]) -> set[str]:
    """Names of vertices with no directed path from any source present in ``graph``."""
    src = present_indices(graph, sources)
    n = graph.vcount()
    augmented = ig.Graph(n=n + 1, edges=graph.get_edgelist() + [(n, s) for s in src], directed=True)
    reached = set(augmented.subcomponent(n, mode="out"))
    names = graph.vs["name"]
    return {names[i] for i in range(n) if i not in reached}
