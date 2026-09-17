"""Check the synthetic-lethal pair search: complete pair coverage, synergy arithmetic and agreement with single removals."""

from math import comb

import numpy as np

from pipeline.synthetic_lethal_pairs import POOL_SIZE, TOP_REPORTED
from verify.common import first_difference, result_csv, result_json, result_text, run


def check() -> str:
    summary = result_json("synthetic_lethal_pairs.json")
    pairs = result_csv("synthetic_lethal_pairs.csv")
    pool = result_csv("synthetic_lethal_pool.csv")
    intact = summary["intact_flow"]

    assert summary["pool_size"] == len(pool) == POOL_SIZE and pool["cell_type"].is_unique, f"Pool has {len(pool)} types"
    expected = comb(POOL_SIZE, 2)
    assert summary["pairs_evaluated"] == len(pairs) == expected, f"{len(pairs)} pairs evaluated, expected {expected}"
    members = set(pool["cell_type"])
    assert set(pairs["type_a"]) | set(pairs["type_b"]) <= members, "A pair uses a type outside the pool"
    keys = {frozenset(p) for p in zip(pairs["type_a"], pairs["type_b"])}
    assert len(keys) == expected and all(len(k) == 2 for k in keys), "Pairs are duplicated or pair a type with itself"

    assert (pairs["joint_impact"] == intact - pairs["flow_after"]).all(), "joint_impact != intact flow - flow_after"
    assert (pairs["synergy"] == pairs["joint_impact"] - pairs["impact_a"] - pairs["impact_b"]).all(), "synergy arithmetic"
    impact = pool.set_index("cell_type")["flow_drop"]
    assert (pairs["impact_a"] == pairs["type_a"].map(impact)).all(), "impact_a differs from the pool table"
    assert (pairs["impact_b"] == pairs["type_b"].map(impact)).all(), "impact_b differs from the pool table"

    single = result_csv("single_removal_impacts.csv").set_index("cell_type")
    assert (pool["flow_drop"] == pool["cell_type"].map(single["flow_drop"])).all(), "Pool impacts differ from single removal"
    assert (pool["intact_flow"] == intact).all(), "Pool intact flow differs"
    assert np.allclose(pool["impact_per_edge"], pool["flow_drop"] / pool["degree"], rtol=1e-5), "impact_per_edge arithmetic"
    assert pool["impact_per_edge"].is_monotonic_decreasing, "Pool is not ordered by impact per edge"

    order = pairs.sort_values(["synergy", "joint_impact"], ascending=False, kind="stable")
    assert order[["synergy", "joint_impact"]].equals(pairs[["synergy", "joint_impact"]]), "CSV not sorted by synergy"
    assert summary["pairs_with_positive_synergy"] == int((pairs["synergy"] > 0).sum()), "Positive synergy count differs"
    assert summary["pairs_with_negative_synergy"] == int((pairs["synergy"] < 0).sum()), "Negative synergy count differs"
    assert summary["max_synergy"] == int(pairs["synergy"].max()), "max_synergy differs"
    assert summary["pool_types_with_nonzero_single_impact"] == int((pool["flow_drop"] > 0).sum()), "Nonzero pool count"
    top = pairs.head(TOP_REPORTED).to_dict("records")
    difference = first_difference(summary["top_pairs"], top)
    assert difference is None, f"top_pairs differs from the head of the CSV at {difference}"

    text = result_text("synthetic_lethal_pairs.md")
    assert f"{summary['pairs_with_positive_synergy']} pairs have positive synergy" in text, "Report count differs"
    for row in pairs.head(TOP_REPORTED).itertuples():
        assert f"| {row.impact_a} | {row.impact_b} | {row.flow_after} | {row.joint_impact} | {row.synergy:+d} |" in text, \
            f"Report row for {row.type_a} and {row.type_b} differs"
    best = pairs.iloc[0]
    return (f"all {expected:,} pairs of {POOL_SIZE} types, synergy arithmetic exact; {summary['pairs_with_positive_synergy']} "
            f"positive, max {summary['max_synergy']} ({best['type_a']} + {best['type_b']})")


if __name__ == "__main__":
    run(check)
