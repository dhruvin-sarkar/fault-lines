import igraph as ig
import pytest

from pipeline.connectivity_metrics import flow_capacity, reachable_pairs, reachability, unreachable_from


def toy_graph() -> ig.Graph:
    """Sensory s1, s2; motor m1, m2; interneurons a, b; c feeds m1 but receives no input.

    s1 -> a -> m1, a -> b -> m2, s2 -> a, s2 -> b, c -> m1, plus a motor-to-sensory edge m1 -> s1.
    """
    graph = ig.Graph(directed=True)
    graph.add_vertices(["s1", "s2", "a", "b", "c", "m1", "m2"])
    graph.add_edges(
        [("s1", "a"), ("s2", "a"), ("a", "m1"), ("a", "b"), ("b", "m2"), ("s2", "b"), ("c", "m1"), ("m1", "s1")]
    )
    return graph


S, M = ["s1", "s2"], ["m1", "m2"]


def test_all_pairs_reachable_in_intact_toy_graph():
    graph = toy_graph()
    assert reachable_pairs(graph, S, M) == 4
    assert reachability(graph, S, M) == pytest.approx(1.0)


def test_flow_counts_edge_disjoint_paths():
    # Min cut {a->m1, b->m2}: two edge-disjoint paths, s1->a->m1 and s2->b->m2.
    assert flow_capacity(toy_graph(), S, M) == 2


def test_removing_the_hub_breaks_three_of_four_pairs():
    graph = toy_graph()
    graph.delete_vertices(["a"])
    # Only s2 -> b -> m2 survives.
    assert reachable_pairs(graph, S, M) == 1
    assert reachability(graph, S, M) == pytest.approx(0.25)
    assert flow_capacity(graph, S, M) == 1


def test_flow_is_not_capped_by_the_number_of_sources():
    # One sensory node with three disjoint routes to one motor node.
    graph = ig.Graph(directed=True)
    graph.add_vertices(["s", "x", "y", "z", "m"])
    graph.add_edges([("s", "x"), ("s", "y"), ("s", "z"), ("x", "m"), ("y", "m"), ("z", "m")])
    assert flow_capacity(graph, ["s"], ["m"]) == 3


def test_direction_matters():
    graph = ig.Graph(directed=True)
    graph.add_vertices(["s", "i", "m"])
    graph.add_edges([("m", "i"), ("i", "s")])
    assert reachable_pairs(graph, ["s"], ["m"]) == 0
    assert flow_capacity(graph, ["s"], ["m"]) == 0


def test_absent_sources_and_targets_are_ignored():
    graph = toy_graph()
    graph.delete_vertices(["s1", "m2"])
    assert reachable_pairs(graph, S, M) == 1
    assert flow_capacity(graph, S, M) == 1


def test_overlapping_sets_are_rejected():
    with pytest.raises(ValueError, match="both"):
        flow_capacity(toy_graph(), ["s1", "a"], ["a", "m1"])


def test_unreachable_from_lists_nodes_cut_off_from_every_source():
    graph = toy_graph()
    assert unreachable_from(graph, S) == {"c"}
    graph.delete_vertices(["a"])
    assert unreachable_from(graph, S) == {"c", "m1"}
