import pandas as pd
import pytest

from pipeline.synthetic_lethal_pairs import candidate_pool, synergy


def test_synergy_is_joint_impact_beyond_the_two_single_impacts():
    assert synergy(intact_flow=10, flow_after_pair=4, impact_a=2, impact_b=1) == (6, 3)


def test_overlapping_impacts_give_negative_synergy():
    assert synergy(intact_flow=10, flow_after_pair=8, impact_a=2, impact_b=1) == (2, -1)


def test_mutually_backed_up_types_have_synergy_equal_to_the_joint_impact():
    assert synergy(intact_flow=7, flow_after_pair=5, impact_a=0, impact_b=0) == (2, 2)


SCORES = pd.DataFrame(
    {
        "cell_type": ["A", "B", "C", "D", "E", "F"],
        "flow_drop": [4, 3, 0, 2, 0, 0],
        "degree": [2, 1, 0, 1, 5, 3],
        "sm_betweenness": [1.0, 0.0, 0.0, 9.0, 7.0, 7.0],
    }
)


def test_pool_ranks_by_impact_per_edge_then_betweenness_then_name():
    pool = candidate_pool(SCORES, size=len(SCORES))
    # B = 3/1, then A and D tie at 2/1 (D has higher betweenness), then zeros ordered by betweenness and name.
    assert pool["cell_type"].tolist() == ["B", "D", "A", "E", "F", "C"]
    assert pool.set_index("cell_type")["impact_per_edge"].to_dict() == pytest.approx(
        {"A": 2.0, "B": 3.0, "C": 0.0, "D": 2.0, "E": 0.0, "F": 0.0})


def test_zero_degree_types_score_zero_instead_of_dividing_by_zero():
    pool = candidate_pool(SCORES.assign(flow_drop=[4, 3, 5, 2, 0, 0]), size=len(SCORES))
    assert pool.set_index("cell_type").loc["C", "impact_per_edge"] == 0.0
    assert pool["impact_per_edge"].notna().all()


def test_pool_is_truncated_to_the_requested_size_without_changing_the_input():
    before = SCORES.copy()
    assert candidate_pool(SCORES, size=3)["cell_type"].tolist() == ["B", "D", "A"]
    pd.testing.assert_frame_equal(SCORES, before)
