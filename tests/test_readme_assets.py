import math
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from pipeline import readme_assets as ra


def test_linear_maps_endpoints_and_midpoint():
    to_x = ra.linear(0, 0.5, 100, 200)
    assert to_x(0) == 100
    assert to_x(0.5) == 200
    assert to_x(0.25) == 150


def test_linear_can_invert_an_axis():
    to_y = ra.linear(0, 1, 800, 200)
    assert to_y(1) == 200
    assert to_y(0.5) == 500


@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [(0.04111, 1, "4.1%"), (0.28321, 1, "28.3%"), (0.5, 0, "50%"), (0.0, 1, "0.0%")],
)
def test_pct(value, digits, expected):
    assert ra.pct(value, digits) == expected


def test_count_and_p_formatting():
    assert ra.count(11751) == "11,751"
    assert ra.count(243439.4) == "243,439"
    assert ra.fmt_p(0.0049751) == "0.005"


@pytest.mark.parametrize(("value", "expected"), [(12.0, "12"), (12.34, "12.3"), (-0.01, "0"), (0.05, "0.1")])
def test_num_drops_trailing_zeros(value, expected):
    assert ra.num(value) == expected


def test_text_width_grows_with_length_size_and_weight():
    base = ra.text_width("Flow capacity", 26)
    assert ra.text_width("Flow capacity retained", 26) > base
    assert ra.text_width("Flow capacity", 52) == pytest.approx(2 * base)
    assert ra.text_width("Flow capacity", 26, bold=True) > base


def test_wrap_keeps_every_word_and_respects_width():
    text = "Each dot marks where a curve first crosses half of the intact flow capacity"
    lines = ra.wrap(text, 26, 300)
    assert " ".join(lines) == text
    assert len(lines) > 1
    assert all(ra.text_width(line, 26) <= 300 or " " not in line for line in lines)


def test_wrap_returns_single_line_when_it_fits():
    assert ra.wrap("short line", 26, 1000) == ["short line"]


def test_spread_separates_close_labels_and_keeps_order():
    positions = [100, 105, 110, 400]
    placed = ra.spread(positions, 30)
    ordered = sorted(placed)
    assert all(b - a >= 30 - 1e-6 for a, b in zip(ordered, ordered[1:]))
    assert placed[0] < placed[1] < placed[2] < placed[3]
    assert placed[3] == 400


def test_spread_respects_bounds():
    placed = ra.spread([0, 1, 2], 20, lo=10, hi=100)
    assert min(placed) >= 10 - 1e-6
    assert max(placed) <= 100 + 1e-6


def test_spread_leaves_distant_labels_alone():
    assert ra.spread([10, 200, 500], 30) == [10, 200, 500]


def test_ramp_color_endpoints_and_midpoint():
    stops = ("#000000", "#ffffff")
    assert ra.ramp_color(stops, 0) == "#000000"
    assert ra.ramp_color(stops, 1) == "#ffffff"
    assert ra.ramp_color(stops, 0.5) == "#808080"
    assert ra.ramp_color(stops, 2) == "#ffffff"


def test_ramp_color_walks_multiple_stops():
    stops = ("#000000", "#ff0000", "#ffffff")
    assert ra.ramp_color(stops, 0.5) == "#ff0000"
    assert ra.ramp_color(stops, 0.75) == "#ff8080"


def test_impact_position_compresses_small_values():
    assert ra.impact_position(0.35, 0.35) == pytest.approx(1)
    assert ra.impact_position(0, 0.35) == 0
    assert ra.impact_position(0.0875, 0.35) == pytest.approx(0.5)
    assert ra.impact_position(0.1, 0) == 0


def test_path_bounds():
    assert ra.path_bounds("M10 20L30.5 5L-4 12.25Z") == (-4, 5, 30.5, 20)


def test_mean_ci_matches_student_t():
    trials = np.array([[1.0, 0.5], [0.8, 0.3], [0.9, 0.4]])
    mean, half = ra.mean_ci(trials)
    assert mean == pytest.approx([0.9, 0.4])
    assert half[0] == pytest.approx(4.302653 * 0.1 / math.sqrt(3), rel=1e-5)


def test_half_flow_batch():
    assert ra.half_flow_batch([100, 80, 51, 50, 49, 10], 100) == 4
    assert ra.half_flow_batch([100, 90, 60], 100) is None


def test_italicize_wraps_words():
    assert ra.italicize("adult Drosophila CNS", ["Drosophila"]) == (
        'adult <tspan font-style="italic">Drosophila</tspan> CNS'
    )


def test_svg_render_is_well_formed_and_accessible():
    svg = ra.Svg(200, "dark")
    svg.text(10, 20, "Flow & reachability < 50%")
    svg.line(0, 0, 10, 10, "signal", dash="4 4")
    svg.polyline([0, 5, 10], [0, 5, 0], "sm_betweenness")
    svg.dot(5, 5, 4, "random", hollow=True, ring=2)
    document = svg.render("Title", "A description")
    root = ET.fromstring(document)
    assert root.get("viewBox") == f"0 0 {ra.WIDTH} 200"
    assert root.get("role") == "img"
    ns = "{http://www.w3.org/2000/svg}"
    assert root.find(f"{ns}title").text == "Title"
    assert root.find(f"{ns}desc").text == "A description"
    assert "Flow &amp; reachability &lt; 50%" in document
    assert ra.STRATEGY_INK["dark"]["sm_betweenness"] in document


def test_theme_tokens_resolve_per_theme():
    assert ra.Svg(10, "light").c("signal") == "#c21f3a"
    assert ra.Svg(10, "dark").c("signal") == "#ff4b63"
    assert ra.Svg(10, "light").c("pagerank") == ra.STRATEGY_INK["light"]["pagerank"]
    assert ra.Svg(10, "light").c("#123456") == "#123456"


def test_every_asset_builds_from_the_committed_results(tmp_path):
    data = ra.load_inputs()
    written = ra.build_all(data, tmp_path)
    names = {p.name for p in written}
    assert "plate-title.svg" in names
    for stem in ("stat-plate", "fig-curves", "fig-thresholds", "fig-regions", "fig-classes",
                 "fig-compartments", "methods-pipeline"):
        assert {f"{stem}-light.svg", f"{stem}-dark.svg"} <= names
    for path in written:
        text = path.read_text(encoding="utf-8")
        ET.fromstring(text)
        for forbidden in (chr(0x2014), chr(0x2013), chr(0x00B7)):
            assert forbidden not in text, (path.name, forbidden)
        assert "<text" in text


def test_headline_numbers_come_from_the_results():
    h = ra.headline(ra.load_inputs())
    assert ra.pct(h["fc_top"]) == "4.1%"
    assert ra.pct(h["fc_random"]) == "28.3%"
    assert h["types"] == 11751
    assert h["silenced_at_half_max"] == 37
    assert h["avalanche"] == 6046
    assert h["silenced_end"]["sm_betweenness"] == 5306
    assert h["survivors_end"] == 5846
