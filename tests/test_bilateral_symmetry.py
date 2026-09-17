import math

import pandas as pd
import pytest
from scipy import stats

from pipeline.bilateral_symmetry import (COLUMNS, bilateral_types, completed_rows, p_text, split_name, statistic_text,
                                        wilcoxon_greater)


def test_split_name_separates_type_from_hemisphere():
    assert split_name("DNa02|L") == ("DNa02", "L")
    assert split_name("AN_GNG_1|unknown") == ("AN_GNG_1", "unknown")


def test_split_name_uses_the_last_separator():
    assert split_name("odd|type|R") == ("odd|type", "R")


def test_bilateral_types_need_both_a_left_and_a_right_node():
    names = ["A|L", "A|R", "B|L", "B|M", "C|R", "D|R", "D|L", "D|M", "E|unknown", "E|L"]
    assert bilateral_types(names) == ["A", "D"]


def test_bilateral_types_are_sorted_and_unique():
    assert bilateral_types(["Z|R", "Z|L", "Z|L", "A|L", "A|R"]) == ["A", "Z"]


def test_wilcoxon_detects_a_consistent_excess_and_skips_ties():
    x = pd.Series([5, 6, 7, 8, 9, 10, 11, 12, 3, 4])
    y = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 3, 4])
    result = wilcoxon_greater(x, y)
    assert result["pairs_differing"] == 8
    # Every one of the 8 differences is positive: the exact one-sided p is 1 / 2**8.
    assert result["p_value"] == pytest.approx(1 / 256)
    assert result["statistic"] == pytest.approx(36.0)


def test_wilcoxon_is_one_sided():
    x = pd.Series([1, 2, 3, 4, 5, 6, 7, 8])
    y = pd.Series([5, 6, 7, 8, 9, 10, 11, 12])
    assert wilcoxon_greater(x, y)["p_value"] > 0.99


def test_completed_rows_is_empty_without_a_checkpoint(tmp_path):
    rows = completed_rows(tmp_path / "missing.csv")
    assert rows.empty and list(rows.columns) == COLUMNS


def test_completed_rows_keeps_the_latest_measurement_per_type(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("cell_type,impact_left,impact_right,impact_both\nA,1,2,3\nB,0,0,1\nA,4,5,9\n", encoding="utf-8")
    rows = completed_rows(path).set_index("cell_type")
    assert len(rows) == 2 and rows.loc["A", "impact_both"] == 9


def test_wilcoxon_reports_z_and_log10_p_consistent_with_p():
    x = pd.Series(range(10, 70))
    y = pd.Series(range(0, 60)) + pd.Series([0, 1] * 30)
    result = wilcoxon_greater(x, y)
    assert result["z_statistic"] > 0
    assert result["log10_p_value"] == pytest.approx(math.log10(result["p_value"]))


def test_wilcoxon_gives_a_finite_log10_p_when_p_underflows():
    x = pd.Series(range(5000, 10000))
    y = pd.Series(range(0, 5000))
    result = wilcoxon_greater(x, y)
    assert result["p_value"] == 0.0
    assert math.isfinite(result["log10_p_value"]) and result["log10_p_value"] < -323
    assert result["log10_p_value"] == pytest.approx(stats.norm.logsf(result["z_statistic"]) / math.log(10))


def test_statistic_text_keeps_half_integers_exact():
    assert statistic_text(22235.5) == "22235.5"
    assert statistic_text(9899025.0) == "9899025"


def test_p_text_states_underflow_as_a_bound_with_log10_p():
    assert p_text({"p_value": 5.1717e-37, "log10_p_value": -36.29}) == "p = 5.2e-37"
    assert p_text({"p_value": 0.0, "log10_p_value": -728.18}) == "p < 1e-323, log10 p = -728.2"
