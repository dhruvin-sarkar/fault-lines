import igraph as ig
import numpy as np
import pandas as pd
import pytest

from pipeline.hidden_bottleneck import distance_matrix, find_candidates, partners, percentile_ranks


def test_percentile_ranks_use_mid_ranks():
    assert percentile_ranks(pd.Series([10, 40, 20, 30])).tolist() == pytest.approx([12.5, 87.5, 37.5, 62.5])


def test_tied_values_share_the_average_percentile():
    assert percentile_ranks(pd.Series([5, 5, 1, 9])).tolist() == pytest.approx([50.0, 50.0, 12.5, 87.5])


def background(n: int) -> pd.DataFrame:
    """n types whose degree, PageRank and betweenness all rise together, so none is hidden."""
    ranks = np.arange(n, dtype=float)
    return pd.DataFrame({"cell_type": [f"t{i}" for i in range(n)], "degree": ranks + 10,
                         "pagerank": ranks + 10, "sm_betweenness": ranks})


def with_rows(table: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    return pd.concat([table, pd.DataFrame(rows)], ignore_index=True)


def test_candidates_are_low_degree_low_pagerank_and_top_betweenness():
    # With 400 types the four added rows all sit in the top 1% by betweenness, so each fails on one criterion only.
    scores = with_rows(background(396), [
        {"cell_type": "hidden", "degree": 1.0, "pagerank": 1.0, "sm_betweenness": 1000.0},
        {"cell_type": "hub", "degree": 900.0, "pagerank": 900.0, "sm_betweenness": 999.0},
        {"cell_type": "low_pagerank_only", "degree": 900.0, "pagerank": 1.0, "sm_betweenness": 998.0},
        {"cell_type": "low_degree_only", "degree": 1.0, "pagerank": 900.0, "sm_betweenness": 997.0},
    ])
    candidates = find_candidates(scores)
    assert candidates["cell_type"].tolist() == ["hidden"]
    row = candidates.iloc[0]
    assert row["degree_pct"] < 50 and row["pagerank_pct"] < 50 and row["sm_betweenness_pct"] >= 99


def test_candidates_are_ordered_by_betweenness_then_by_lower_degree():
    scores = with_rows(background(197), [
        {"cell_type": "second", "degree": 3.0, "pagerank": 1.0, "sm_betweenness": 1000.0},
        {"cell_type": "first", "degree": 2.0, "pagerank": 1.0, "sm_betweenness": 1000.0},
        {"cell_type": "third", "degree": 1.0, "pagerank": 1.0, "sm_betweenness": 900.0},
    ])
    candidates = find_candidates(scores)
    assert candidates["cell_type"].tolist()[:2] == ["first", "second"]
    assert "third" not in candidates["cell_type"].tolist()


def test_no_type_can_reach_the_top_percentile_in_a_small_graph():
    scores = with_rows(background(10), [{"cell_type": "x", "degree": 0.0, "pagerank": 0.0, "sm_betweenness": 99.0}])
    assert find_candidates(scores).empty


def chain() -> ig.Graph:
    graph = ig.Graph(directed=True)
    graph.add_vertices(["s1", "s2", "a", "m1", "m2"])
    graph.add_edges([("s1", "a"), ("a", "m1"), ("s2", "m2"), ("m1", "m2")],
                    attributes={"weight": [4, 7, 2, 9]})
    graph.vs["superclass"] = ["sensory", "sensory", "intrinsic", "motor", "motor"]
    return graph


def test_distance_matrix_counts_hops_in_input_order():
    matrix = distance_matrix(chain(), ["s1", "s2"], ["m2", "m1"])
    assert matrix.tolist() == [[3.0, 2.0], [1.0, np.inf]]


def test_distance_matrix_marks_absent_endpoints_unreachable():
    graph = chain()
    graph.delete_vertices(["s2"])
    matrix = distance_matrix(graph, ["s1", "s2", "gone"], ["m1", "absent"])
    assert matrix.shape == (3, 2)
    assert matrix[0, 0] == 2.0
    assert np.isinf(matrix[1:, :]).all() and np.isinf(matrix[:, 1]).all()


def test_distance_matrix_without_any_present_endpoint_is_all_infinite():
    matrix = distance_matrix(chain(), ["nobody"], ["m1", "m2"])
    assert matrix.shape == (1, 2) and np.isinf(matrix).all()


def test_partners_are_listed_strongest_first_with_their_superclass():
    graph = chain()
    graph.add_edges([("s2", "a")], attributes={"weight": [11]})
    vertex = graph.vs.find(name="a").index
    assert partners(graph, vertex, "in") == [
        {"cell_type": "s2", "superclass": "sensory", "synapses": 11},
        {"cell_type": "s1", "superclass": "sensory", "synapses": 4},
    ]
    assert partners(graph, vertex, "out") == [{"cell_type": "m1", "superclass": "motor", "synapses": 7}]
