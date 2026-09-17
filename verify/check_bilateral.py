"""Check the bilateral redundancy test: per-type arithmetic, category counts and both Wilcoxon tests rerun."""

import pandas as pd

from pipeline.bilateral_symmetry import wilcoxon_greater
from pipeline.common import RESULTS
from verify.common import Skip, first_difference, result_json, result_text, run

IMPACTS = ["impact_left", "impact_right", "impact_both"]


def check() -> str:
    if not (RESULTS / "bilateral_symmetry.json").exists():
        partial = [n for n in ("bilateral_symmetry.csv", "bilateral_symmetry.md") if (RESULTS / n).exists()]
        assert not partial, f"bilateral_symmetry.json is absent but {', '.join(partial)} exist"
        raise Skip("results/bilateral_symmetry.json not written yet; the bilateral run has not finished")

    summary = result_json("bilateral_symmetry.json")
    table = pd.read_csv(RESULTS / "bilateral_symmetry.csv")
    assert summary["bilateral_types"] == len(table) and table["cell_type"].is_unique, \
        f"{len(table)} rows for {summary['bilateral_types']} bilateral types"
    assert sum(summary["nodes_by_side"].values()) == summary["nodes"], "Nodes by side do not sum to the node count"
    assert summary["bilateral_types"] <= min(summary["nodes_by_side"].get("L", 0), summary["nodes_by_side"].get("R", 0)), \
        "More bilateral types than nodes on one side"
    assert (table[IMPACTS] >= 0).all().all(), "Negative flow impact"
    assert (table[IMPACTS] <= summary["intact_flow"]).all().all(), "Impact larger than intact flow"
    assert (table["superadditivity"] == table["impact_both"] - table["impact_left"] - table["impact_right"]).all(), \
        "superadditivity != both - left - right"
    assert (table["impact_single_mean"] == (table["impact_left"] + table["impact_right"]) / 2).all(), "Single-side mean"

    informative = table[(table[IMPACTS] != 0).any(axis=1)]
    assert summary["informative_types"] == len(informative), f"{len(informative)} informative types in the CSV"
    counts = {"superadditive": int((informative["superadditivity"] > 0).sum()),
              "additive": int((informative["superadditivity"] == 0).sum()),
              "subadditive": int((informative["superadditivity"] < 0).sum())}
    assert summary["additivity_counts"] == counts, f"Additivity counts differ from the CSV: {counts}"
    insured = informative[(informative["impact_left"] == 0) & (informative["impact_right"] == 0) & (informative["impact_both"] > 0)]
    assert summary["fully_insured_types"] == len(insured), f"{len(insured)} fully insured types in the CSV"

    tests = {
        "both_greater_than_single_mean": wilcoxon_greater(informative["impact_both"], informative["impact_single_mean"]),
        "both_greater_than_sum_of_singles": wilcoxon_greater(informative["impact_both"],
                                                             informative["impact_left"] + informative["impact_right"]),
    }
    for name, rerun in tests.items():
        difference = first_difference(summary[name], rerun)
        assert difference is None, f"{name} does not reproduce from the CSV at {difference}"
    assert summary["both_greater_than_sum_of_singles"]["pairs_differing"] == counts["superadditive"] + counts["subadditive"], \
        "Superadditivity test size differs from the non-additive count"

    top = informative.sort_values(["superadditivity", "impact_both"], ascending=False).head(15).to_dict("records")
    difference = first_difference(summary["strongest_superadditive"], top)
    assert difference is None, f"strongest_superadditive differs from the CSV at {difference}"

    text = result_text("bilateral_symmetry.md")
    assert f"For each of the {summary['bilateral_types']} types" in text, "Report states a different number of types"
    assert (f"Of the {summary['informative_types']} informative types, {counts['superadditive']} are superadditive"
            in text), "Report states different additivity counts"
    p = summary["both_greater_than_sum_of_singles"]["p_value"]
    return (f"{summary['bilateral_types']:,} bilateral types, {summary['informative_types']:,} informative "
            f"({counts['superadditive']} superadditive, {counts['subadditive']} subadditive); both Wilcoxon tests "
            f"reproduced (superadditivity p = {p:.2g})")


if __name__ == "__main__":
    run(check)
