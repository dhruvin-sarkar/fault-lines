import igraph as ig
import numpy as np
import pandas as pd
import pytest

from pipeline.hidden_bottleneck import distance_matrix, find_candidates, partners, percentile_ranks, report_lines


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


def test_report_gives_degree_and_pagerank_percentiles_to_one_decimal():
    candidates = pd.DataFrame([{"cell_type": "ALIN7", "superclass": "cb_intrinsic", "degree": 34,
                                "degree_pct": 45.65994, "pagerank_pct": 9.84172, "sm_betweenness": 1881.328,
                                "sm_betweenness_pct": 99.82555}])
    partner = [{"cell_type": "p", "superclass": "cb_sensory", "synapses": 3}]
    stats = {"cell_type": "ALIN7", "superclass": "cb_intrinsic", "n_neurons": 2, "in_degree": 19, "out_degree": 15,
             "degree": 34, "median_degree": 36.0, "degree_percentile": 45.65994, "in_strength": 3699.0,
             "out_strength": 4753.0, "pagerank_percentile": 9.84172, "sm_betweenness": 1881.328,
             "sm_betweenness_rank": 21, "sm_betweenness_percentile": 99.82555, "share_of_shortest_routes": 0.0079,
             "reachable_pairs": 237405, "pairs_lost_when_removed": 0, "pairs_with_longer_shortest_path_when_removed": 849,
             "intact_flow": 10647, "flow_after_removal": 10638, "strongest_inputs": partner, "strongest_outputs": partner}
    lines = report_lines(candidates, stats, 11751)
    assert "| `ALIN7` | cb_intrinsic | 34 (45.7) | 9.8 | 1,881 (99.83) |" in lines
    assert "| degree percentile | 45.7 |" in lines and "| PageRank percentile | 9.8 |" in lines
    assert any("rank 21 of 11751" in line for line in lines)
