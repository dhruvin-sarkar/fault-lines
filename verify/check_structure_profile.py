"""Check the structure profile: core decomposition totals, degree-tail fits and whole-superclass removals."""

import numpy as np
import pandas as pd

from pipeline.structure_profile import ALTERNATIVES, MIN_SUPERCLASS
from verify.common import close, result_csv, result_json, result_text, run

REL = 2e-4


def check() -> str:
    profile = result_json("structure_profile.json")
    types = profile["types"]

    counts = {int(k): v for k, v in profile["coreness_counts"].items()}
    assert sum(counts.values()) == types, f"Coreness counts sum to {sum(counts.values())}, not {types} types"
    assert min(counts.values()) > 0 and min(counts) >= 0, "Empty or negative core layers"
    assert profile["max_coreness"] == max(counts), f"max_coreness {profile['max_coreness']} vs deepest layer {max(counts)}"
    assert profile["types_in_deepest_core"] == counts[max(counts)], "types_in_deepest_core differs from the layer count"
    rho = profile["coreness_vs_out_strength"]
    assert -1 <= rho["spearman_rho"] <= 1 and 0 <= rho["p_value"] <= 1, "Spearman result out of range"

    for tail in profile["degree_tails"]:
        name = tail["measure"]
        assert 0 < tail["n"] <= types and 0 < tail["n_tail"] <= tail["n"], f"{name}: counts out of range"
        assert tail["median"] <= tail["max"] and 1 <= tail["xmin"] <= tail["max"], f"{name}: x_min or median out of range"
        assert tail["alpha"] > 1 and 0 <= tail["ks_distance"] <= 1, f"{name}: exponent or KS distance out of range"
        assert set(tail["comparisons"]) == set(ALTERNATIVES), f"{name}: comparisons {sorted(tail['comparisons'])}"
        survival = np.asarray(tail["ccdf"]["p"])
        assert survival[0] == 1 and (np.diff(survival) <= 0).all() and (survival > 0).all(), f"{name}: CCDF malformed"
        assert (np.diff(tail["ccdf"]["x"]) > 0).all(), f"{name}: CCDF x not increasing"

    draws = profile["random_draws"]
    classes = pd.DataFrame(profile["superclass_impact"])
    csv = result_csv("superclass_impact.csv")
    assert list(classes["superclass"]) == list(csv["superclass"]), "superclass_impact.csv lists different superclasses"
    for column in classes.columns.drop("superclass"):
        assert close(csv[column].tolist(), classes[column].tolist(), rel=REL, abs_tol=1e-8), f"superclass_impact.csv {column} differs"
    assert profile["superclass_threshold"] == MIN_SUPERCLASS and (classes["types"] >= MIN_SUPERCLASS).all(), \
        "A superclass below the size threshold was scored"
    assert classes["types"].sum() <= types, "Superclasses hold more types than the graph"
    floor = 1 / (1 + draws)
    assert classes["p_value"].between(floor * (1 - 1e-9), 1).all(), f"p-values outside [1/{draws + 1}, 1]"
    assert np.allclose(classes["flow_drop"], 1 - classes["flow_after"] / profile["intact_flow"]), "flow_drop arithmetic"
    assert np.allclose(classes["excess_over_random"], classes["flow_drop"] - classes["random_mean"]), "excess arithmetic"

    text = result_text("structure_profile.md")
    assert f"reaches k = {profile['max_coreness']}, and {profile['types_in_deepest_core']:,} of {types:,}" in text, \
        "structure_profile.md shows different core numbers"
    for row in classes.itertuples():
        assert f"| {row.superclass} | {row.types:,} | {row.neurons:,} | {100 * row.flow_drop:.1f}% |" in text, \
            f"structure_profile.md row for {row.superclass} differs"
    return (f"{types:,} types across {len(counts)} core layers (deepest k = {profile['max_coreness']} holds "
            f"{profile['types_in_deepest_core']:,}); {len(classes)} superclass removals, p in [1/{draws + 1}, 1]")


if __name__ == "__main__":
    run(check)
