import pandas as pd
import pytest

from pipeline.build_type_graph import aggregate_type_edges, build_graph, combine_type_edges, hemisphere, summarize_nodes

# Five neurons in three types: A = {1, 2}, B = {3, 4}, C = {5}.
BODY_TYPES = pd.Series({1: "A", 2: "A", 3: "B", 4: "B", 5: "C"})
CONNECTIONS = pd.DataFrame(
    {
        "bodyId_pre": [1, 1, 2, 3, 4, 5, 1],
        "bodyId_post": [3, 4, 3, 5, 5, 1, 2],
        "weight": [5, 2, 7, 4, 6, 3, 9],
    }
)


def test_aggregation_sums_weights_across_neuron_pairs():
    edges = aggregate_type_edges(CONNECTIONS, BODY_TYPES).set_index(["type_pre", "type_post"])
    assert edges.loc[("A", "B"), "weight"] == 14
    assert edges.loc[("A", "B"), "n_connections"] == 3
    assert edges.loc[("B", "C"), "weight"] == 10
    assert edges.loc[("C", "A"), "weight"] == 3
    assert edges.loc[("A", "A"), "weight"] == 9
    assert edges["weight"].sum() == CONNECTIONS["weight"].sum()
    assert len(edges) == 4


def test_aggregation_rejects_untyped_bodies():
    connections = pd.concat([CONNECTIONS, pd.DataFrame({"bodyId_pre": [99], "bodyId_post": [1], "weight": [1]})])
    with pytest.raises(ValueError, match="without a cell type"):
        aggregate_type_edges(connections, BODY_TYPES)


def test_combining_chunks_matches_single_aggregation():
    whole = aggregate_type_edges(CONNECTIONS, BODY_TYPES)
    parts = [aggregate_type_edges(CONNECTIONS.iloc[:3], BODY_TYPES), aggregate_type_edges(CONNECTIONS.iloc[3:], BODY_TYPES)]
    pd.testing.assert_frame_equal(combine_type_edges(parts), whole)


def test_side_resolved_aggregation_keeps_hemispheres_apart():
    labels = pd.Series({1: "A|L", 2: "A|R", 3: "B|L", 4: "B|R", 5: "C|M"})
    edges = aggregate_type_edges(CONNECTIONS, labels).set_index(["type_pre", "type_post"])
    assert edges.loc[("A|L", "B|L"), "weight"] == 5
    assert edges.loc[("A|L", "B|R"), "weight"] == 2
    assert edges.loc[("A|L", "A|R"), "weight"] == 9
    assert edges["weight"].sum() == CONNECTIONS["weight"].sum()


def test_hemisphere_prefers_soma_side_then_root_side():
    neurons = pd.DataFrame(
        {
            "somaSide": ["L", "R", "M", None, None, None, "L"],
            "rootSide": [None, None, None, "R", "unknown", None, "R"],
        }
    )
    assert hemisphere(neurons).tolist() == ["L", "R", "M", "R", "unknown", "unknown", "L"]


def test_graph_drops_self_loops_and_weak_inputs():
    neurons = pd.DataFrame(
        {
            "bodyId": [1, 2, 3, 4, 5],
            "type": ["A", "A", "B", "B", "C"],
            "superclass": ["cb_sensory", "cb_sensory", "cb_intrinsic", None, "descending_neuron"],
            "pre": [10, 20, 30, 40, 50],
            "post": [1, 2, 3, 4, 5],
        }
    )
    nodes = summarize_nodes(neurons).set_index("cell_type")
    assert nodes.loc["A", "n_neurons"] == 2
    assert nodes.loc["B", "superclass"] == "cb_intrinsic"
    assert nodes.loc["C", "total_pre"] == 50
    nodes = nodes.reset_index()

    # Type A receives 12 synapses: 3 from C (25%) and 9 from itself.
    graph = build_graph(nodes, aggregate_type_edges(CONNECTIONS, BODY_TYPES), min_input_fraction=0.3)
    assert graph.vcount() == 3
    pairs = {(graph.vs[e.source]["name"], graph.vs[e.target]["name"]): e["weight"] for e in graph.es}
    assert pairs == {("A", "B"): 14, ("B", "C"): 10}

    graph = build_graph(nodes, aggregate_type_edges(CONNECTIONS, BODY_TYPES), min_input_fraction=0.25)
    assert graph.es[graph.get_eid("C", "A")]["input_fraction"] == pytest.approx(0.25)
