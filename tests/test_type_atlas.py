import json

import igraph as ig
import numpy as np
import pytest

import pipeline.type_atlas as type_atlas
from pipeline.render_hero import rotation
from pipeline.type_atlas import CANVAS, PITCH, RASTER, YAW, outline_path, project, rdp


def test_rdp_keeps_endpoints_and_drops_collinear_points():
    line = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [3.0, 3.0]])
    assert rdp(line, tolerance=0.01) == pytest.approx(np.array([[0.0, 0.0], [3.0, 3.0]]))


def test_rdp_keeps_a_corner_beyond_the_tolerance():
    line = np.array([[0.0, 0.0], [5.0, 0.0], [10.0, 0.0], [10.0, 5.0], [10.0, 10.0]])
    assert rdp(line, tolerance=0.5) == pytest.approx(np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]))


def test_rdp_tolerance_decides_whether_a_small_bump_survives():
    line = np.array([[0.0, 0.0], [5.0, 1.0], [10.0, 0.0]])
    assert len(rdp(line, tolerance=0.5)) == 3
    assert len(rdp(line, tolerance=1.0)) == 2
    assert len(rdp(line, tolerance=2.0)) == 2


def test_rdp_leaves_short_lines_untouched():
    line = np.array([[0.0, 0.0], [4.0, 3.0]])
    assert rdp(line, tolerance=100.0) is line


def test_rdp_handles_closed_rings_whose_ends_coincide():
    ring = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]])
    simplified = rdp(ring, tolerance=0.5)
    assert simplified[0] == pytest.approx(ring[0]) and simplified[-1] == pytest.approx(ring[-1])
    assert len(simplified) == len(ring)


def test_projection_is_the_hero_rotation_about_the_center():
    rng = np.random.default_rng(0)
    points, center = rng.normal(size=(20, 3)) * 1000, np.array([10.0, -5.0, 3.0])
    expected = (points - center) @ rotation(PITCH, YAW).T
    assert project(points, center) == pytest.approx(expected)
    assert (PITCH, YAW) == (18.0, 0.0)


def test_projection_preserves_distances_and_maps_the_center_to_the_origin():
    center = np.array([100.0, 200.0, 300.0])
    points = np.array([center, center + [0.0, 1.0, 0.0], center + [3.0, 4.0, 12.0]])
    screen = project(points, center)
    assert screen[0] == pytest.approx([0.0, 0.0, 0.0])
    assert np.linalg.norm(screen, axis=1) == pytest.approx([0.0, 1.0, 13.0])
    pitch = np.radians(18.0)
    assert screen[1] == pytest.approx([0.0, np.cos(pitch), -np.sin(pitch)])


def test_outline_of_one_triangle_is_a_single_closed_path():
    triangle = np.array([[[100.0, 100.0], [600.0, 100.0], [100.0, 600.0]]])
    path = outline_path(triangle, lambda points: points * RASTER / CANVAS)
    assert path.startswith("M") and path.endswith("Z")
    assert path.count("M") == 1
    corners = np.array([[float(v) for v in p.split()] for p in path[1:-1].split("L")])
    assert corners.min(axis=0) == pytest.approx([100.0, 100.0], abs=1.0)
    assert corners.max(axis=0) == pytest.approx([600.0, 600.0], abs=1.0)


def test_outline_drops_specks_below_the_minimum_area():
    speck = np.array([[[10.0, 10.0], [11.0, 10.0], [10.0, 11.0]]])
    assert outline_path(speck, lambda points: points * RASTER / CANVAS, min_area=12.0) == ""


def downstream_graph() -> ig.Graph:
    """s is sensory; h fans out to a and b, a feeds c; d has no input and also feeds c."""
    graph = ig.Graph(directed=True)
    graph.add_vertices(["s", "h", "a", "b", "c", "d"])
    graph.add_edges([("s", "h"), ("h", "a"), ("h", "b"), ("a", "c"), ("d", "c")])
    return graph


def write_run(directory, strategy: str, removed: list[list[str]]) -> None:
    fractions = [0.0] + [sum(len(b) for b in removed[: i + 1]) / 6 for i in range(len(removed))]
    (directory / f"{strategy}_00.json").write_text(
        json.dumps({"removed": removed, "fraction_removed": fractions}), encoding="utf-8")


def test_replay_records_removal_and_silencing_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(type_atlas, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(type_atlas, "STRATEGIES", ("out_strength",))
    write_run(tmp_path, "out_strength", [["h"], ["d"]])

    table, counts = type_atlas.replay(downstream_graph(), ["s"])
    table = table.set_index("cell_type")
    assert table["removed_out_strength"].to_dict() == {"s": -1, "h": 1, "a": -1, "b": -1, "c": -1, "d": 2}
    # d never had input; a, b and c lose their only route when h goes.
    assert table["silenced_out_strength"].to_dict() == {"s": -1, "h": -1, "a": 1, "b": 1, "c": 1, "d": 0}
    assert counts["out_strength"]["removed_types"] == [0, 1, 2]
    assert counts["out_strength"]["silenced_types"] == [1, 4, 3]
    assert counts["out_strength"]["fraction_removed"] == pytest.approx([0.0, 1 / 6, 2 / 6])


def test_replay_starts_every_strategy_from_the_intact_graph(tmp_path, monkeypatch):
    monkeypatch.setattr(type_atlas, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(type_atlas, "STRATEGIES", ("out_strength", "random"))
    write_run(tmp_path, "out_strength", [["h"]])
    write_run(tmp_path, "random", [["b"], ["a"]])

    table, counts = type_atlas.replay(downstream_graph(), ["s"])
    table = table.set_index("cell_type")
    assert table["removed_random"].to_dict() == {"s": -1, "h": -1, "a": 2, "b": 1, "c": -1, "d": -1}
    # Removing a cuts c off, since d has no input of its own.
    assert table["silenced_random"].to_dict() == {"s": -1, "h": -1, "a": -1, "b": -1, "c": 2, "d": 0}
    assert counts["random"]["removed_types"] == [0, 1, 2]
    assert counts["random"]["silenced_types"] == [1, 1, 2]
