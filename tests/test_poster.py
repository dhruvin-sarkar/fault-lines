import numpy as np
import pandas as pd
import pytest

from pipeline.poster import (
    atlas_bounds,
    ccdf,
    column_edges,
    count,
    disk,
    fit_box,
    half_flow_batch,
    linear,
    log1p_scale,
    ordinal,
    p_value,
    parse_markup,
    pct,
    split_cells,
    spread_labels,
    svg_path,
    wrap_widths,
)


def test_columns_fill_the_width_between_margins_with_equal_gutters():
    edges = column_edges(3508, 128, 88, 3)
    assert edges[0][0] == pytest.approx(128)
    assert edges[-1][1] == pytest.approx(3508 - 128)
    widths = [right - left for left, right in edges]
    assert widths == pytest.approx([widths[0]] * 3)
    assert edges[1][0] - edges[0][1] == pytest.approx(88)
    assert edges[2][0] - edges[1][1] == pytest.approx(88)


def test_split_cells_divides_a_span_into_equal_cells():
    cells = split_cells(100, 700, 3, 30)
    assert cells[0] == pytest.approx((100, 280))
    assert cells[1] == pytest.approx((310, 490))
    assert cells[2] == pytest.approx((520, 700))


def test_linear_scale_maps_endpoints_and_can_invert_direction():
    sy = linear(0, 1, 500, 100)
    assert sy(0) == pytest.approx(500)
    assert sy(1) == pytest.approx(100)
    assert sy(0.25) == pytest.approx(400)
    assert np.allclose(linear(0, 10, 0, 100)([0, 5, 10]), [0, 50, 100])


def test_log_scale_keeps_zero_on_the_axis_and_reaches_the_top():
    sy = log1p_scale(9999, 300, 0)
    assert sy(0) == pytest.approx(300)
    assert sy(9999) == pytest.approx(0)
    assert sy(99) == pytest.approx(150)


def test_spread_labels_only_moves_labels_that_are_too_close():
    assert spread_labels([10, 100, 200], 30) == [10, 100, 200]
    assert spread_labels([10, 20, 25], 30) == [10, 40, 70]


def test_percentages_round_halves_up():
    assert pct(0.04111045) == "4.1%"
    assert pct(0.28321) == "28.3%"
    assert pct(0.2055) == "20.6%"
    assert pct(0.5, 0) == "50%"
    assert pct(0.0) == "0.0%"


def test_counts_use_thousands_separators():
    assert count(11751) == "11,751"
    assert count(2362060) == "2,362,060"
    assert count(37.0) == "37"


def test_p_values_keep_significant_figures_and_bound_small_values():
    assert p_value(0.04538707) == "0.045"
    assert p_value(0.10159) == "0.10"
    assert p_value(0.2021, 3) == "0.202"
    assert p_value(5.17e-37) == "< 0.001"


def test_ordinals():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 77, 101)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "77th", "101st"]


def test_wrap_breaks_before_the_word_that_would_overflow():
    assert wrap_widths([30, 30, 30, 30], 10, 70) == [[0, 1], [2, 3]]
    assert wrap_widths([30, 30, 30], 10, 110) == [[0, 1, 2]]


def test_a_word_wider_than_the_line_gets_a_line_of_its_own():
    assert wrap_widths([10, 200, 10], 5, 50) == [[0], [1], [2]]
    assert wrap_widths([], 5, 50) == []


def test_markup_toggles_styles_and_attaches_scripts_to_their_word():
    words = parse_markup("The **flow capacity** of *Drosophila*,^1^ as *f*~c~ here")
    assert words[0] == [("The", "regular")]
    assert words[1] == [("flow", "bold")]
    assert words[2] == [("capacity", "bold")]
    assert words[4] == [("Drosophila", "italic"), (",", "regular"), ("1", "sup")]
    assert words[6] == [("f", "italic"), ("c", "sub")]
    assert words[7] == [("here", "regular")]


def test_half_flow_batch_is_the_first_batch_strictly_below_half():
    assert half_flow_batch([100, 80, 50, 49, 10], 100) == 3
    assert half_flow_batch([100, 90, 60], 100) is None


def test_svg_path_reads_move_line_and_close_commands():
    path = svg_path("M0 0L10 0L10 10ZM20 20L30 20L30 30Z")
    assert path.codes.tolist() == [1, 2, 2, 79, 1, 2, 2, 79]
    assert path.vertices[3].tolist() == [0, 0]
    assert path.vertices[7].tolist() == [20, 20]
    assert path.vertices[5].tolist() == [30, 20]


def test_fit_box_scales_to_the_limiting_side_and_centres():
    scale, ox, oy = fit_box((0, 0, 100, 50), 400, 400)
    assert scale == pytest.approx(4)
    assert ox == pytest.approx(0)
    assert oy == pytest.approx(100)
    scale, ox, oy = fit_box((10, 10, 20, 30), 100, 100)
    assert scale == pytest.approx(5)
    assert 10 * scale + ox == pytest.approx(25)
    assert 30 * scale + oy == pytest.approx(100)


def test_atlas_bounds_cover_the_outline_and_every_placed_point():
    types = pd.DataFrame({"x": [5.0, 50.0, np.nan], "y": [70.0, 20.0, 999.0]})
    assert atlas_bounds(types, "M10 10L40 10L40 60Z", pad=1) == (4.0, 9.0, 51.0, 71.0)


def test_ccdf_counts_the_share_at_least_each_value_and_ignores_zeros():
    values, share = ccdf([0, 1, 1, 2, 8])
    assert values.tolist() == [1, 2, 8]
    assert share.tolist() == pytest.approx([1.0, 0.5, 0.25])


def test_disk_kernel_is_round_and_odd_sized():
    kernel = disk(5)
    assert kernel.shape == (5, 5)
    assert kernel[2, 2] == 1 and kernel[0, 2] == 1
    assert kernel[0, 0] == 0
    assert np.array_equal(kernel, kernel.T)
    assert disk(1).tolist() == [[1.0]]
