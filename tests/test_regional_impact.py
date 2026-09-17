import numpy as np
import pandas as pd
import pytest

from pipeline.regional_impact import anchor_neuropils, report_lines, upper_p_value

NEURONS = pd.DataFrame({"bodyId": [1, 2, 3], "type": ["A", "A", "B"]})


def roi_counts(rows):
    return pd.DataFrame(rows, columns=["bodyId", "roi", "pre", "post"])


def test_type_is_anchored_where_most_of_its_synapses_are():
    counts = roi_counts([(1, "AL(R)", 10, 5), (1, "GNG", 1, 1), (2, "AL(R)", 0, 4), (3, "LegNp(T1)(L)", 2, 2)])
    anchors = anchor_neuropils(counts, NEURONS)
    assert anchors["A"] == "AL(R)"
    assert anchors["B"] == "LegNp(T1)(L)"


def test_aggregate_compartments_and_unspecified_remainders_are_ignored():
    counts = roi_counts([(1, "CentralBrain", 500, 500), (1, "CentralBrain-unspecified", 300, 300), (1, "AL(R)", 1, 0)])
    assert anchor_neuropils(counts, NEURONS)["A"] == "AL(R)"


def test_ties_go_to_the_alphabetically_first_neuropil():
    counts = roi_counts([(1, "PLP(L)", 3, 3), (1, "AL(R)", 3, 3)])
    assert anchor_neuropils(counts, NEURONS)["A"] == "AL(R)"


def test_types_without_synapses_in_any_neuropil_are_dropped():
    counts = roi_counts([(3, "GNG", 0, 0)])
    assert "B" not in anchor_neuropils(counts, NEURONS).index


def test_untyped_bodies_do_not_produce_an_anchor():
    counts = roi_counts([(4, "GNG", 5, 5)])
    neurons = pd.DataFrame({"bodyId": [4], "type": [None]})
    assert anchor_neuropils(counts, neurons).empty


def test_upper_p_value_counts_the_observation_itself():
    null = np.array([0.1, 0.2, 0.3, 0.4])
    assert upper_p_value(null, 0.5) == pytest.approx(1 / 5)
    assert upper_p_value(null, 0.25) == pytest.approx(3 / 5)
    assert upper_p_value(null, 0.0) == pytest.approx(1.0)


def impact_table(p_values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"neuropil": [f"N{i}" for i in range(len(p_values))], "p_value": p_values})


def test_report_states_that_no_neuropil_can_pass_bonferroni_with_too_few_draws():
    text = "\n".join(report_lines(impact_table([1 / 201, 1 / 201, 0.03] + [0.5] * 88), draws=200))
    assert "smallest attainable p is 1/201 = 0.0050" in text
    assert "0.05/91 = 0.00055, which no neuropil can reach" in text
    assert "3 neuropils have p < 0.05 and 2 reach the minimum" in text


def test_report_allows_bonferroni_when_draws_suffice():
    text = "\n".join(report_lines(impact_table([0.5, 0.5]), draws=1000))
    assert "which the smallest attainable p can reach" in text
