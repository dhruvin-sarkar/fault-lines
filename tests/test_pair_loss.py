import igraph as ig
import numpy as np
import pandas as pd
import pytest

from pipeline.pair_loss import grouped_pairs, motor_order, pair_losses, removal_check, summarize
from pipeline.single_removal import reachable_matrix


def graph_from(names: list[str], edges: list[tuple[str, str]]) -> ig.Graph:
    graph = ig.Graph(directed=True)
    graph.add_vertices(names)
    graph.add_edges(edges)
    return graph


def bridge_and_detour() -> ig.Graph:
    """s1 reaches both motors only through the bridge b; s2 reaches m1 through a or c, so neither is needed."""
    return graph_from(
        ["s1", "s2", "b", "a", "c", "m1", "m2", "x"],
        [("s1", "b"), ("b", "m1"), ("b", "m2"), ("s2", "a"), ("s2", "c"), ("a", "m1"), ("c", "m1"), ("x", "m2")],
    )


SOURCES, TARGETS = ["s1", "s2"], ["m1", "m2"]


def as_set(losses: pd.DataFrame, cell_type: str) -> set[tuple[str, str]]:
    rows = losses[losses["cell_type"] == cell_type]
    return set(zip(rows["sensory"], rows["motor"]))


def test_only_bridge_disconnects_every_pair_it_carries():
    losses, reach = pair_losses(bridge_and_detour(), SOURCES, TARGETS)
    assert reach.tolist() == [[True, True], [True, False]]
    assert as_set(losses, "b") == {("s1", "m1"), ("s1", "m2")}


def test_types_on_redundant_routes_disconnect_nothing():
    losses, _ = pair_losses(bridge_and_detour(), SOURCES, TARGETS)
    assert set(losses["cell_type"]) == {"b"}
    assert as_set(losses, "a") == set() and as_set(losses, "c") == set()


def test_removing_the_endpoints_themselves_is_not_listed_as_another_pair():
    losses, _ = pair_losses(bridge_and_detour(), SOURCES, TARGETS)
    assert not (losses["cell_type"].isin(SOURCES + TARGETS)).any()


def test_every_vertex_on_a_chain_is_listed_in_order_from_target_to_source():
    graph = graph_from(["s", "u", "v", "m"], [("s", "u"), ("u", "v"), ("v", "m")])
    losses, _ = pair_losses(graph, ["s"], ["m"])
    assert losses.values.tolist() == [["v", "s", "m"], ["u", "s", "m"]]


def test_a_sensory_type_can_be_the_only_route_for_another_sensory_type():
    graph = graph_from(["s1", "s2", "m"], [("s2", "s1"), ("s1", "m")])
    losses, _ = pair_losses(graph, ["s1", "s2"], ["m"])
    assert losses.values.tolist() == [["s1", "s2", "m"]]


def test_summary_splits_own_pairs_from_other_pairs_and_matches_deletion_counts():
    graph = bridge_and_detour()
    losses, reach = pair_losses(graph, SOURCES, TARGETS)
    table = summarize(losses, reach, SOURCES, TARGETS, {}).set_index("cell_type")
    assert table.loc["b", ["own_pairs", "other_pairs", "pairs_lost"]].tolist() == [0, 2, 2]
    assert table.loc["b", ["sensory_types_cut", "motor_types_cut", "role"]].tolist() == [1, 2, "other"]
    assert table.loc["s1", ["own_pairs", "other_pairs", "role"]].tolist() == [2, 0, "sensory"]
    assert table.loc["m1", ["own_pairs", "other_pairs", "role"]].tolist() == [2, 0, "motor"]
    assert table.loc["m2", "own_pairs"] == 1
    assert "a" not in table.index and "x" not in table.index
    for name in graph.vs["name"]:
        reduced = graph.copy()
        reduced.delete_vertices([graph.vs.find(name=name).index])
        lost = int((reach & ~reachable_matrix(reduced, SOURCES, TARGETS)).sum())
        assert lost == (table.loc[name, "pairs_lost"] if name in table.index else 0), name


def test_summary_puts_types_with_other_pairs_first():
    losses, reach = pair_losses(bridge_and_detour(), SOURCES, TARGETS)
    assert summarize(losses, reach, SOURCES, TARGETS, {})["cell_type"].tolist()[0] == "b"


def test_removal_check_accepts_the_dominator_pairs_and_rejects_a_missing_one():
    graph = bridge_and_detour()
    losses, reach = pair_losses(graph, SOURCES, TARGETS)
    removal_check(graph, SOURCES, TARGETS, reach, "b", losses[losses["cell_type"] == "b"])
    with pytest.raises(AssertionError):
        removal_check(graph, SOURCES, TARGETS, reach, "b", losses[losses["cell_type"] == "b"].head(1))


def test_motor_order_puts_descending_neurons_first_then_names():
    superclass = {"MN1": "vnc_motor", "DNb": "descending_neuron", "DNa": "descending_neuron", "CM": "cb_motor"}
    order = motor_order(["MN1", "DNb", "CM", "DNa"], superclass)
    assert sorted(order, key=order.get) == ["DNa", "DNb", "CM", "MN1"]


def test_grouped_pairs_orders_sources_by_pairs_lost_and_records_their_reach():
    losses = pd.DataFrame({"cell_type": ["v", "v", "v"], "sensory": ["sb", "sa", "sa"], "motor": ["m1", "m2", "m1"]})
    reach = np.array([[True, True], [True, True]])
    superclass = {"m1": "vnc_motor", "m2": "descending_neuron"}
    groups = grouped_pairs(losses, reach, ["sa", "sb"], ["m1", "m2"], superclass)["v"]
    assert groups == [{"sensory": "sa", "reach": 2, "motors": ["m2", "m1"]},
                      {"sensory": "sb", "reach": 2, "motors": ["m1"]}]
