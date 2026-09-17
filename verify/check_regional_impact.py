"""Check the per-neuropil removal table: attainable p-values, internal arithmetic and its report."""

import numpy as np

from pipeline.regional_impact import RANDOM_DRAWS, report_lines
from verify.common import result_csv, result_json, result_text, run, same_text

# regional_impact.csv is written with five significant digits.
REL = 2e-4


def check() -> str:
    table = result_csv("regional_impact.csv")
    graph = result_json("fragility_scores.json")["graph"]
    assert len(table) and table["neuropil"].is_unique, "Neuropils missing or duplicated"
    assert not table.isna().any().any(), "Missing values in regional_impact.csv"

    floor = 1 / (1 + RANDOM_DRAWS)
    p = table["p_value"]
    assert ((p >= floor * (1 - REL)) & (p <= 1)).all(), f"p-values outside [1/{RANDOM_DRAWS + 1}, 1]: {p[(p < floor * (1 - REL)) | (p > 1)].tolist()}"
    k = p * (1 + RANDOM_DRAWS)
    assert np.allclose(k, np.round(k), rtol=0, atol=0.01), "p-values are not of the form (1 + k) / (1 + draws)"

    intact = table["intact_flow"]
    assert (intact == graph["intact_flow"]).all(), "Intact flow differs from fragility_scores.json"
    assert np.allclose(table["flow_drop"], 1 - table["flow_after"] / intact, rtol=REL), "flow_drop != 1 - flow_after / intact"
    assert np.allclose(table["excess_over_random"], table["flow_drop"] - table["random_mean"], rtol=REL, atol=2e-5), \
        "excess_over_random != flow_drop - random_mean"
    assert ((table["flow_drop"] >= 0) & (table["flow_drop"] <= 1)).all(), "flow_drop outside [0, 1]"
    assert (table["n_sensory"] + table["n_motor"] <= table["n_types"]).all(), "More sensory and motor types than types"
    assert table["n_types"].sum() <= graph["cell_types"], "More anchored types than graph types"
    assert table["n_sensory"].sum() <= graph["sensory_types"] and table["n_motor"].sum() <= graph["motor_types"], \
        "More anchored sensory or motor types than the sets hold"
    assert table["flow_drop"].is_monotonic_decreasing, "regional_impact.csv is not sorted by flow_drop"

    anchors = result_csv("type_atlas.csv")["anchor"].value_counts()
    counts = table.set_index("neuropil")["n_types"]
    assert anchors.reindex(counts.index).fillna(0).astype(int).equals(counts), "Anchor counts differ from type_atlas.csv"

    expected = "\n".join(report_lines(table, RANDOM_DRAWS))
    assert same_text(result_text("regional_impact.md"), expected), "regional_impact.md is out of date with the CSV"
    top = table.iloc[0]
    return (f"{len(table)} neuropils, p in [1/{RANDOM_DRAWS + 1}, 1], {int((p < 0.05).sum())} below 0.05 uncorrected; "
            f"largest loss {top['neuropil']} ({100 * top['flow_drop']:.1f}%); report current")


if __name__ == "__main__":
    run(check)
