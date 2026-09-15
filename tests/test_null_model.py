import random

import igraph as ig
import numpy as np
import pytest

from pipeline.null_model import empirical_p_value_lower, rewire


@pytest.fixture
def weighted_graph() -> ig.Graph:
    random.seed(7)
    graph = ig.Graph.Erdos_Renyi(n=200, m=2000, directed=True, loops=False)
    rng = np.random.default_rng(7)
    graph.es["weight"] = rng.integers(1, 500, graph.ecount()).tolist()
    graph.es["input_fraction"] = [0.5] * graph.ecount()
    graph.vs["name"] = [f"t{i}" for i in range(graph.vcount())]
    return graph


def test_rewiring_preserves_exact_in_and_out_degree(weighted_graph):
    null = rewire(weighted_graph, seed=1)
    assert null.indegree() == weighted_graph.indegree()
    assert null.outdegree() == weighted_graph.outdegree()
    assert null.ecount() == weighted_graph.ecount()
    assert null.is_simple()


def test_rewiring_preserves_out_strength_and_weight_multiset(weighted_graph):
    null = rewire(weighted_graph, seed=1)
    assert null.strength(mode="out", weights="weight") == weighted_graph.strength(mode="out", weights="weight")
    assert sorted(null.es["weight"]) == sorted(weighted_graph.es["weight"])
    assert "input_fraction" not in null.es.attributes()
    assert null.vs["name"] == weighted_graph.vs["name"]


def test_rewiring_randomizes_most_edges(weighted_graph):
    original = set(weighted_graph.get_edgelist())
    null = rewire(weighted_graph, seed=1)
    changed = sum(edge not in original for edge in null.get_edgelist()) / null.ecount()
    assert changed > 0.9


def test_rewiring_is_reproducible_for_a_seed(weighted_graph):
    a, b = rewire(weighted_graph, seed=3), rewire(weighted_graph, seed=3)
    assert a.get_edgelist() == b.get_edgelist()
    assert a.es["weight"] == b.es["weight"]
    assert rewire(weighted_graph, seed=4).get_edgelist() != a.get_edgelist()


def test_rewiring_keeps_vertex_attributes(weighted_graph):
    weighted_graph.vs["superclass"] = ["cb_sensory"] * 100 + ["vnc_motor"] * 100
    null = rewire(weighted_graph, seed=2)
    assert null.vs["superclass"] == weighted_graph.vs["superclass"]


def test_lower_tail_p_value_counts_ties_and_never_reaches_zero():
    null = np.array([0.3, 0.2, 0.1, 0.1])
    assert empirical_p_value_lower(0.1, null) == pytest.approx(3 / 5)
    assert empirical_p_value_lower(0.05, null) == pytest.approx(1 / 5)
    assert empirical_p_value_lower(0.25, null) == pytest.approx(4 / 5)
