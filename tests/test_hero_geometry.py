import numpy as np
import pytest
from PIL import Image

from pipeline.render_hero import (HERO_SIZE, MAP_MESH_BOX, MAP_SCALE_BOX, PAPER, crop_regional_map,
                                 mesh_cache_path, rotation, simplify)


def cube(scale=1.0):
    vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                         [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], dtype=float) * scale
    faces = np.array([[0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6], [0, 4, 5], [0, 5, 1],
                      [2, 6, 7], [2, 7, 3], [1, 5, 6], [1, 6, 2], [0, 3, 7], [0, 7, 4]])
    return vertices, faces


def test_clustering_merges_vertices_inside_one_cell_and_removes_collapsed_triangles():
    merged, kept = simplify(*cube(scale=1.0), cell=10.0)
    assert len(merged) == 1
    assert len(kept) == 0


def test_a_mesh_coarser_than_the_cell_is_left_intact():
    vertices, faces = cube(scale=100.0)
    merged, kept = simplify(vertices, faces, cell=10.0)
    assert len(merged) == len(vertices)
    assert len(kept) == len(faces)


def test_clustering_moves_vertices_to_their_cluster_centroid():
    vertices = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [100.0, 0.0, 0.0], [0.0, 100.0, 0.0]])
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    merged, kept = simplify(vertices, faces, cell=10.0)
    assert len(merged) == 3
    assert merged[0] == pytest.approx([1.0, 0.0, 0.0])
    assert len(kept) == 1


def test_duplicate_triangles_are_kept_once():
    vertices = np.array([[0.0, 0.0, 0.0], [50.0, 0.0, 0.0], [0.0, 50.0, 0.0]])
    faces = np.array([[0, 1, 2], [1, 2, 0], [0, 2, 1]])
    _, kept = simplify(vertices, faces, cell=10.0)
    assert len(kept) == 1


def test_rotation_is_orthonormal_and_identity_at_zero():
    assert rotation(0, 0) == pytest.approx(np.eye(3))
    view = rotation(23.0, -14.0)
    assert view @ view.T == pytest.approx(np.eye(3))
    assert np.linalg.det(view) == pytest.approx(1.0)


def test_pitch_rotates_the_vertical_axis_into_the_depth_axis():
    assert rotation(90.0, 0.0) @ np.array([0.0, 1.0, 0.0]) == pytest.approx([0.0, 0.0, -1.0], abs=1e-12)
    assert rotation(0.0, 90.0) @ np.array([0.0, 0.0, 1.0]) == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)


def test_mesh_names_differing_only_in_case_get_distinct_cache_files():
    antennal, alpha = mesh_cache_path("brain", "AL(R)"), mesh_cache_path("brain", "aL(R)")
    assert antennal.name.lower() != alpha.name.lower()
    assert mesh_cache_path("brain", "AL(R)") == antennal


def test_regional_map_is_the_mesh_box_with_the_scale_box_beneath(tmp_path):
    rng = np.random.default_rng(0)
    hero = rng.integers(0, 256, size=(HERO_SIZE[1], HERO_SIZE[0], 3), dtype=np.uint8)
    Image.fromarray(hero).save(tmp_path / "hero.png")
    crop_regional_map(tmp_path / "hero.png", tmp_path / "map.png")
    figure = np.asarray(Image.open(tmp_path / "map.png"))

    left, top, right, bottom = MAP_MESH_BOX
    assert figure.shape == (bottom - top + MAP_SCALE_BOX[3] - MAP_SCALE_BOX[1], right - left, 3)
    assert (figure[: bottom - top] == hero[top:bottom, left:right]).all()
    s_left, s_top, s_right, s_bottom = MAP_SCALE_BOX
    scale = figure[bottom - top :]
    assert (scale[:, : s_right - s_left] == hero[s_top:s_bottom, s_left:s_right]).all()
    paper = np.array([int(PAPER[i : i + 2], 16) for i in (1, 3, 5)])
    assert (scale[:, s_right - s_left :] == paper).all()


def test_regional_map_rejects_a_hero_of_another_size(tmp_path):
    Image.new("RGB", (100, 100)).save(tmp_path / "small.png")
    with pytest.raises(ValueError):
        crop_regional_map(tmp_path / "small.png", tmp_path / "map.png")
