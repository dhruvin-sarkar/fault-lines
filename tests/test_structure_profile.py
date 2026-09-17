import igraph as ig
import numpy as np
import pytest

from pipeline.structure_profile import ccdf_points, core_layers


def test_ccdf_starts_at_one_and_never_increases():
    values = np.array([1, 1, 2, 3, 5, 8, 13, 100])
    ccdf = ccdf_points(values)
    assert ccdf["x"][0] == 1.0 and ccdf["x"][-1] == 100.0
    assert ccdf["p"][0] == pytest.approx(1.0)
    assert np.all(np.diff(ccdf["p"]) <= 0)
    assert np.all(np.diff(ccdf["x"]) > 0)


def test_ccdf_is_the_fraction_at_or_above_each_point():
    ccdf = dict(zip(*ccdf_points(np.array([1, 1, 2, 3, 5, 8, 13, 100])).values()))
    assert ccdf[2.0] == pytest.approx(6 / 8)
    assert ccdf[5.0] == pytest.approx(4 / 8)
    assert ccdf[100.0] == pytest.approx(1 / 8)


def test_ccdf_ignores_zeros():
    with_zeros = ccdf_points(np.array([0, 0, 0, 1, 2, 4]))
    assert with_zeros == ccdf_points(np.array([1, 2, 4]))
    assert with_zeros["p"][0] == pytest.approx(1.0)


def test_ccdf_of_a_constant_sequence_is_a_single_point():
    assert ccdf_points(np.array([3, 3, 3])) == {"x": [3.0], "p": [1.0]}


def test_ccdf_grid_is_capped_at_the_requested_number_of_points():
    ccdf = ccdf_points(np.arange(1, 10_001), points=50)
    assert len(ccdf["x"]) <= 50


def test_core_layers_match_a_hand_computed_decomposition():
    # a, b, c, d form a 4-clique once direction is ignored (coreness 3); e hangs off a (1); f is isolated (0).
    graph = ig.Graph(directed=True)
    graph.add_vertices(["a", "b", "c", "d", "e", "f"])
    edges = [("a", "b"), ("a", "c"), ("c", "d"), ("b", "c"), ("d", "a"), ("b", "d"), ("e", "a")]
    graph.add_edges(edges, attributes={"weight": [1] * len(edges)})
    cores = core_layers(graph).set_index("cell_type")["coreness"].to_dict()
    assert cores == {"a": 3, "b": 3, "c": 3, "d": 3, "e": 1, "f": 0}


def test_reciprocal_connections_count_once_in_the_undirected_projection():
    graph = ig.Graph(directed=True)
    graph.add_vertices(["a", "b", "c"])
    graph.add_edges([("a", "b"), ("b", "a"), ("b", "c"), ("c", "b")], attributes={"weight": [2, 3, 1, 1]})
    cores = core_layers(graph).set_index("cell_type")["coreness"].to_dict()
    assert cores == {"a": 1, "b": 1, "c": 1}
    assert graph.ecount() == 4 and graph.is_directed()
