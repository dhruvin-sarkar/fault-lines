import igraph as ig
import numpy as np
import pytest

from pipeline.removal_strategies import STRATEGIES, percolate, removal_schedule, select_top, strategy_scores


def weighted(edges: list[tuple[str, str, int]]) -> ig.Graph:
    graph = ig.Graph(directed=True)
    graph.add_vertices(sorted({n for e in edges for n in e[:2]}))
    graph.add_edges([e[:2] for e in edges], attributes={"weight": [e[2] for e in edges]})
    return graph


def cascade_graph() -> ig.Graph:
    """Static out-strength ranking is P (18), T (16), Q (12), U (1).

    T's only target is P, so once P is removed T's out-strength drops to zero and an adaptive
    ranking must pick Q next, where a one-time ranking would pick T.
    """
    return weighted([("P", "Q", 9), ("P", "R", 9), ("Q", "S", 12), ("T", "P", 16), ("U", "S", 1)])


def test_adaptive_recomputation_changes_the_order_a_static_ranking_would_give():
    graph = cascade_graph()
    static = [graph.vs[i]["name"] for i in np.argsort(-strategy_scores(graph, "out_strength", [], [], None))]
    assert static[:2] == ["P", "T"]

    run = percolate(graph, "out_strength", sources=[], targets=[], seed=0, max_fraction=0.5, batch_fraction=0.01)
    assert run["removed"][:3] == [["P"], ["Q"], ["U"]]


def test_betweenness_scores_reflect_the_reduced_graph():
    # x->a->b->y, x->c->y, y->z: c lies on the shortest x->y and x->z paths. Once y is gone c has no
    # downstream partner, so its recomputed betweenness must fall to zero.
    graph = weighted([("x", "a", 1), ("a", "b", 1), ("b", "y", 1), ("x", "c", 1), ("c", "y", 1), ("y", "z", 1)])
    before = dict(zip(graph.vs["name"], strategy_scores(graph, "betweenness", [], [], None)))
    graph.delete_vertices(["y"])
    after = dict(zip(graph.vs["name"], strategy_scores(graph, "betweenness", [], [], None)))
    assert before["y"] > 0 and before["c"] > 0
    assert after["c"] == 0


def test_sensory_motor_betweenness_only_counts_paths_between_the_sets():
    # a lies on the only s->m path; b lies on many paths between non-terminal nodes only.
    graph = weighted([("s", "a", 1), ("a", "m", 1), ("p", "b", 1), ("q", "b", 1), ("b", "r", 1), ("b", "t", 1)])
    scores = dict(zip(graph.vs["name"], strategy_scores(graph, "sm_betweenness", ["s"], ["m"], None)))
    assert scores["a"] == 1
    assert scores["b"] == 0
    general = dict(zip(graph.vs["name"], strategy_scores(graph, "betweenness", [], [], None)))
    assert general["b"] > general["a"]


def test_batches_remove_one_percent_of_remaining_nodes_rounded_up():
    sizes = removal_schedule(1000, batch_fraction=0.01, max_fraction=0.5)
    assert sizes[:3] == [10, 10, 10]
    remaining = 1000
    for size in sizes:
        assert size == int(np.ceil(0.01 * remaining))
        remaining -= size
    assert sum(sizes) >= 500 and sum(sizes[:-1]) < 500


def test_ties_are_broken_randomly_not_by_vertex_order():
    rng = np.random.default_rng(1)
    picks = {tuple(select_top(np.zeros(10), 3, rng)) for _ in range(20)}
    assert len(picks) > 1
    assert list(select_top(np.array([0.0, 5.0, 1.0, 5.0]), 2, rng)) in ([1, 3], [3, 1])


def test_percolation_records_curves_and_never_removes_a_node_twice():
    rng = np.random.default_rng(3)
    graph = ig.Graph.Erdos_Renyi(n=120, m=600, directed=True, loops=False)
    graph.vs["name"] = [f"v{i}" for i in range(graph.vcount())]
    graph.es["weight"] = rng.integers(1, 50, graph.ecount()).tolist()
    sources, targets = [f"v{i}" for i in range(10)], [f"v{i}" for i in range(110, 120)]
    for strategy in STRATEGIES:
        run = percolate(graph, strategy, sources, targets, seed=5)
        removed = [n for batch in run["removed"] for n in batch]
        assert len(removed) == len(set(removed))
        assert len(run["fraction_removed"]) == len(run["flow"]) == len(run["reachable_pairs"]) == len(run["removed"]) + 1
        assert run["fraction_removed"][-1] >= 0.5
        assert np.all(np.diff(run["flow"]) <= 0)
        assert np.all(np.diff(run["reachable_pairs"]) <= 0)
        assert len(run["avalanche"]) == len(run["removed"])


def test_continuing_past_the_limit_keeps_the_same_prefix():
    rng = np.random.default_rng(4)
    graph = ig.Graph.Erdos_Renyi(n=150, m=900, directed=True, loops=False)
    graph.vs["name"] = [f"v{i}" for i in range(graph.vcount())]
    graph.es["weight"] = rng.integers(1, 50, graph.ecount()).tolist()
    sources, targets = [f"v{i}" for i in range(15)], [f"v{i}" for i in range(135, 150)]
    short = percolate(graph, "random", sources, targets, seed=9, max_fraction=0.2)
    long = percolate(graph, "random", sources, targets, seed=9, max_fraction=0.2, continue_until_flow_below=1)
    k = len(short["removed"])
    assert long["removed"][:k] == short["removed"]
    assert np.array_equal(long["flow"][: k + 1], short["flow"])
    assert long["flow"][-1] < 1 and long["fraction_removed"][-1] > short["fraction_removed"][-1]


def test_random_strategy_is_reproducible_for_a_seed():
    graph = cascade_graph()
    a = percolate(graph, "random", [], [], seed=11)["removed"]
    assert a == percolate(graph, "random", [], [], seed=11)["removed"]


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError, match="Unknown strategy"):
        strategy_scores(cascade_graph(), "closeness", [], [], None)
