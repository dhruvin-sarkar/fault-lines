import numpy as np
import pytest

from pipeline.render_hero import rotation, simplify


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
