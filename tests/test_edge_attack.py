import igraph as ig
import numpy as np
import pandas as pd
import pytest

from pipeline.edge_attack import (build_summary, critical_fraction, load_trials, percolate_edges, removal_order,
                                   report_lines, share, summarize_trials)


def weighted(edges: list[tuple[str, str, int]]) -> ig.Graph:
    graph = ig.Graph(directed=True)
    graph.add_vertices(sorted({n for e in edges for n in e[:2]}))
    graph.add_edges([e[:2] for e in edges], attributes={"weight": [e[2] for e in edges]})
    return graph


def tied_graph() -> ig.Graph:
    """Edge weights by index: 5, 1, 5, 3, 5."""
    return weighted([("a", "b", 5), ("b", "c", 1), ("c", "d", 5), ("d", "e", 3), ("e", "a", 5)])


def test_strongest_first_orders_by_descending_weight():
    order = removal_order(tied_graph(), "strongest", seed=0)
    assert sorted(order[:3]) == [0, 2, 4]
    assert list(order[3:]) == [3, 1]


def test_weakest_first_orders_by_ascending_weight():
    order = removal_order(tied_graph(), "weakest", seed=0)
    assert list(order[:2]) == [1, 3]
    assert sorted(order[2:]) == [0, 2, 4]


def test_random_order_is_a_permutation_of_every_edge():
    order = removal_order(tied_graph(), "random", seed=0)
    assert sorted(order) == [0, 1, 2, 3, 4]


@pytest.mark.parametrize("order", ["strongest", "weakest", "random"])
def test_orderings_are_reproducible_for_a_seed(order):
    graph = tied_graph()
    assert np.array_equal(removal_order(graph, order, seed=7), removal_order(graph, order, seed=7))


def test_ties_are_broken_by_the_seed_not_by_edge_index():
    graph = weighted([(f"u{i}", f"v{i}", 4) for i in range(8)])
    orders = {tuple(removal_order(graph, "strongest", seed=s)) for s in range(10)}
    assert len(orders) > 1
    assert all(sorted(order) == list(range(8)) for order in orders)


def test_unknown_order_is_rejected():
    graph = tied_graph()
    with pytest.raises(ValueError, match="Unknown order"):
        removal_order(graph, "heaviest", seed=0)


def test_percolating_edges_records_each_batch_up_to_half_the_edges():
    # Two disjoint s->m routes, one heavy (via a) and one light (via b).
    graph = weighted([("s", "a", 10), ("a", "m", 10), ("s", "b", 1), ("b", "m", 1)])
    run = percolate_edges(graph, "strongest", ["s"], ["m"], seed=0)
    assert run["fraction_removed"] == pytest.approx([0.0, 0.25, 0.5])
    assert run["flow"] == [2, 1, 1]
    assert run["reachable_pairs"] == [1, 1, 1]
    assert graph.ecount() == 4


def test_critical_fraction_interpolates_the_half_capacity_crossing():
    # Crosses 50 between 0.2 (60) and 0.3 (20): 0.2 + 0.1 * (60 - 50) / (60 - 20).
    assert critical_fraction([0.0, 0.1, 0.2, 0.3], [100, 80, 60, 20]) == pytest.approx(0.225)


def test_critical_fraction_requires_flow_strictly_below_half():
    assert critical_fraction([0.0, 0.5, 1.0], [10, 5, 0]) == pytest.approx(0.5)
    assert critical_fraction([0.0, 0.25, 0.5], [10, 6, 5]) is None


def test_critical_fraction_is_none_without_intact_flow():
    assert critical_fraction([0.0, 0.5], [0, 0]) is None


def test_share_formats_percentages_and_the_unreached_case():
    assert share(0.1234) == "12.3%"
    assert share(0.0) == "0.0%"
    assert share(None) == "not reached by 50%"


def run(order: str, fractions: list[float], flow: list[int]) -> dict:
    return {"order": order, "fraction_removed": fractions, "flow": flow, "reachable_pairs": [1] * len(flow)}


def test_trial_summary_reports_the_mean_every_trial_and_the_range():
    runs = [run("random", [0.0, 0.1, 0.2], [100, 60, 20]), run("random", [0.0, 0.1, 0.2], [100, 40, 20])]
    summary = summarize_trials(runs)
    assert summary["critical_fraction_trials"] == pytest.approx([0.125, 0.0833333])
    assert summary["critical_fraction"] == pytest.approx((0.125 + 0.0833333) / 2)
    assert summary["critical_fraction_range"] == pytest.approx([0.0833333, 0.125])


def test_trial_summary_has_no_mean_when_a_trial_never_halves():
    runs = [run("random", [0.0, 0.1], [100, 40]), run("random", [0.0, 0.1], [100, 60])]
    summary = summarize_trials(runs)
    assert summary["critical_fraction_trials"][1] is None
    assert summary["critical_fraction"] is None
    assert summary["critical_fraction_range"] is None


def trials_fixture() -> dict[str, list[dict]]:
    fractions = [0.0, 0.25, 0.5]
    return {
        "strongest": [run("strongest", fractions, [8, 2, 0])],
        "weakest": [run("weakest", fractions, [8, 8, 7])],
        "random": [run("random", fractions, [8, 6, 2]), run("random", fractions, [8, 4, 3]),
                   run("random", fractions, [8, 6, 1])],
    }


def test_summary_keeps_first_trial_curves_and_summarises_all_random_trials():
    summary = build_summary(trials_fixture(), edges=4)
    random_order = summary["orders"]["random"]
    assert summary["random_trials"] == 3
    assert summary["intact_flow"] == 8
    assert random_order["flow"] == [8, 6, 2]
    assert random_order["critical_fraction_trials"] == pytest.approx([0.375, 0.25, 0.35])
    assert random_order["critical_fraction"] == pytest.approx(0.325)
    assert random_order["critical_fraction_range"] == pytest.approx([0.25, 0.375])
    assert summary["orders"]["weakest"]["critical_fraction"] is None


def test_report_quotes_the_random_mean_and_range():
    text = "\n".join(report_lines(build_summary(trials_fixture(), edges=4)))
    assert "| random connections | 32.5% (mean of 3 trials, range 25.0% to 37.5%) |" in text
    assert "a mean of 32.5% for random connections (25.0% to 37.5% over 3 random orders)" in text
    assert "| strongest connections first | 16.7% |" in text


def test_trials_read_back_from_csv_restore_exact_fractions(tmp_path):
    edges = 7
    rows = []
    for order, trials in {"strongest": 1, "weakest": 1, "random": 2}.items():
        for trial in range(trials):
            for k, flow in enumerate([5, 3, 1]):
                rows.append({"order": order, "trial": trial, "fraction_removed": k / edges, "flow": flow,
                             "reachable_pairs": 2})
    path = tmp_path / "edge_attack.csv"
    pd.DataFrame(rows).to_csv(path, index=False, float_format="%.6g")
    trials = load_trials(path, edges)
    assert [len(trials[o]) for o in ("strongest", "weakest", "random")] == [1, 1, 2]
    assert trials["random"][1]["fraction_removed"] == [0.0, 1 / 7, 2 / 7]
    assert trials["random"][1]["flow"] == [5, 3, 1]
