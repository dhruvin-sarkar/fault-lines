"""Check the hidden-bottleneck candidates meet their criteria and the featured case agrees with the other tables."""

import pandas as pd

from pipeline.hidden_bottleneck import HIGH_PERCENTILE, LOW_PERCENTILE, TOP_PARTNERS
from verify.common import close, first_difference, result_csv, result_json, result_text, run

REL = 1e-5


def check() -> str:
    report = result_json("hidden_bottleneck.json")
    graph = result_json("fragility_scores.json")["graph"]
    criteria = report["criteria"]
    assert (criteria["degree_percentile_below"], criteria["pagerank_percentile_below"],
            criteria["sm_betweenness_percentile_at_least"]) == (LOW_PERCENTILE, LOW_PERCENTILE, HIGH_PERCENTILE), \
        f"Recorded criteria {criteria} differ from the pipeline"

    candidates = pd.DataFrame(report["candidates"])
    table = result_csv("hidden_bottleneck_candidates.csv")
    assert report["n_candidates"] == len(candidates) == len(table) > 0, \
        f"n_candidates {report['n_candidates']}, JSON rows {len(candidates)}, CSV rows {len(table)}"
    assert list(table["cell_type"]) == list(candidates["cell_type"]), "CSV and JSON list different candidates"
    for column in ("degree", "degree_pct", "pagerank_pct", "sm_betweenness", "sm_betweenness_pct"):
        difference = first_difference(table[column].tolist(), candidates[column].tolist(), rel=REL)
        assert difference is None, f"Candidate column {column} differs between CSV and JSON at {difference}"
    assert (candidates["degree_pct"] < LOW_PERCENTILE).all(), "A candidate is not in the bottom half by degree"
    assert (candidates["pagerank_pct"] < LOW_PERCENTILE).all(), "A candidate is not in the bottom half by PageRank"
    assert (candidates["sm_betweenness_pct"] >= HIGH_PERCENTILE).all(), "A candidate is below the betweenness cutoff"
    assert (table["degree"] == table["in_degree"] + table["out_degree"]).all(), "degree != in_degree + out_degree"
    assert candidates["sm_betweenness"].is_monotonic_decreasing, "Candidates are not ordered most extreme first"

    ex = report["example"]
    first = candidates.iloc[0]
    assert ex["cell_type"] == first["cell_type"], "The featured case is not the most extreme candidate"
    assert close([ex["degree_percentile"], ex["pagerank_percentile"], ex["sm_betweenness_percentile"], ex["sm_betweenness"]],
                 [first["degree_pct"], first["pagerank_pct"], first["sm_betweenness_pct"], first["sm_betweenness"]]), \
        "Featured case scores differ from its candidate row"
    assert ex["degree"] == ex["in_degree"] + ex["out_degree"], "Featured degree != in + out"
    n = graph["cell_types"]
    implied = 100 * (n - ex["sm_betweenness_rank"] + 0.5) / n
    assert abs(implied - ex["sm_betweenness_percentile"]) < 100 / n, \
        f"Rank {ex['sm_betweenness_rank']} implies percentile {implied:.3f}, recorded {ex['sm_betweenness_percentile']:.3f}"
    assert ex["reachable_pairs"] == graph["intact_reachable_pairs"], "Featured case uses different reachable pairs"
    assert close(ex["share_of_shortest_routes"], ex["sm_betweenness"] / ex["reachable_pairs"]), "Route share arithmetic"
    assert len(ex["strongest_inputs"]) <= TOP_PARTNERS and len(ex["strongest_outputs"]) <= TOP_PARTNERS, "Too many partners"
    for side in ("strongest_inputs", "strongest_outputs"):
        synapses = [p["synapses"] for p in ex[side]]
        assert synapses == sorted(synapses, reverse=True), f"{side} not ordered strongest first"
    assert sum(p["synapses"] for p in ex["strongest_inputs"]) <= ex["in_strength"], "Inputs exceed in-strength"
    assert sum(p["synapses"] for p in ex["strongest_outputs"]) <= ex["out_strength"], "Outputs exceed out-strength"

    single = result_csv("single_removal_impacts.csv").set_index("cell_type").loc[ex["cell_type"]]
    assert ex["intact_flow"] - ex["flow_after_removal"] == single["flow_drop"], \
        f"Flow lost without {ex['cell_type']} is {ex['intact_flow'] - ex['flow_after_removal']}, single removal gives {single['flow_drop']}"
    assert ex["pairs_lost_when_removed"] == single["pairs_lost"], "Pairs lost differ from single_removal_impacts.csv"

    text = result_text("hidden_bottleneck.md")
    assert f"{len(candidates)} types qualify" in text and f"## The most extreme case: `{ex['cell_type']}`" in text, \
        "hidden_bottleneck.md names a different candidate count or case"
    assert f"| flow capacity, intact → without it | {ex['intact_flow']} → {ex['flow_after_removal']} |" in text, \
        "hidden_bottleneck.md shows different flow numbers"
    return (f"{len(candidates)} candidates meet the criteria; {ex['cell_type']} carries "
            f"{100 * ex['share_of_shortest_routes']:.2f}% of shortest routes, costs {single['flow_drop']} of flow, "
            "agrees with single removal")


if __name__ == "__main__":
    run(check)
