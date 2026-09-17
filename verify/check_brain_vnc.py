"""Check the brain versus nerve cord comparison against the compartment table, the sets and its own trials."""

import numpy as np
from scipy import stats

from pipeline.brain_vnc_comparison import COMPARTMENTS
from pipeline.removal_strategies import STRATEGIES, STRATEGY_LABELS
from pipeline.run_percolation import RANDOM_TRIALS, mean_ci95
from verify.common import close, result_csv, result_json, result_text, run


def check() -> str:
    report = result_json("brain_vnc_comparison.json")
    graph = result_json("fragility_scores.json")["graph"]
    sets = result_json("sensory_motor_sets.json")
    table = result_csv("type_compartments.csv")

    assert set(table["compartment"].dropna()) <= set(COMPARTMENTS), "Unknown compartment labels"
    share = table["brain_share"]
    total = table["brain_synapses"] + table["vnc_synapses"]
    assert np.allclose(share[total > 0], (table["brain_synapses"] / total)[total > 0], atol=6e-5), "brain_share arithmetic"
    assert ((share > 0.5) == (table["compartment"] == "brain")).all(), "A type is labeled against its brain share"
    assert ((share < 0.5) == (table["compartment"] == "vnc")).all(), "A type is labeled against its VNC share"
    assert report["unclassified_types"] == int(table["compartment"].isna().sum()), "Unclassified count differs"

    by_type = table.set_index("cell_type")["compartment"]
    compartments = report["compartments"]
    assert set(compartments) == set(COMPARTMENTS), f"Compartments {sorted(compartments)}"
    assert sum(c["types"] for c in compartments.values()) + report["unclassified_types"] == graph["cell_types"], \
        "Brain, VNC and unclassified types do not add up to the graph"
    assert sum(c["edges"] for c in compartments.values()) <= graph["edges"], "Subgraphs hold more edges than the graph"
    motor_split = {}
    for name, c in compartments.items():
        assert c["types"] == int((by_type == name).sum()), f"{name}: {c['types']} types, table gives {(by_type == name).sum()}"
        sensory = int((by_type.reindex(sets["sensory"]) == name).sum())
        motor = int((by_type.reindex(sets["motor"]) == name).sum())
        assert (c["sensory"], c["motor"]) == (sensory, motor), f"{name}: |S|, |M| = {c['sensory']}, {c['motor']}, table gives {sensory}, {motor}"
        motor_split[name] = motor
        assert 0 < c["intact_flow"] <= graph["intact_flow"], f"{name}: intact flow {c['intact_flow']} out of range"
        assert 0 < c["intact_pairs"] <= c["sensory"] * c["motor"], f"{name}: intact pairs out of range"

        scores = c["scores"]
        assert set(scores) == set(STRATEGIES) and set(c["f_c"]) == set(STRATEGIES), f"{name}: strategies missing"
        for key in ("auc_flow", "auc_reachability"):
            trials = scores["random"][f"{key}_trials"]
            assert len(trials) == RANDOM_TRIALS, f"{name}: {len(trials)} random trials"
            mean, low, high = mean_ci95(trials)
            assert close([mean, low, high], [scores["random"][key], *scores["random"][f"{key}_ci95"]]), f"{name}: random {key} CI"
            assert low <= mean <= high, f"{name}: random {key} CI does not contain the mean"
            assert all(0 <= scores[s][key] <= 1 for s in STRATEGIES), f"{name}: {key} outside [0, 1]"
        assert all(0 < v <= 1 for v in c["f_c"].values()), f"{name}: f_c outside (0, 1]"

    for key, recorded in report["welch_random_trials"].items():
        t, p = stats.ttest_ind(compartments["brain"]["scores"]["random"][f"{key}_trials"],
                               compartments["vnc"]["scores"]["random"][f"{key}_trials"], equal_var=False)
        assert close([recorded["t"], recorded["p_value"]], [t, p]), f"Welch test on {key} does not reproduce"
    assert report["descending_motor_types_by_compartment"] == {k: v for k, v in motor_split.items() if v}, \
        "Descending/motor split differs from the compartment table"

    text = result_text("brain_vnc_comparison.md")
    b, v = compartments["brain"], compartments["vnc"]
    assert f"| cell types | {b['types']} | {v['types']} |" in text, "Report shows different type counts"
    assert f"| intact flow capacity | {b['intact_flow']} | {v['intact_flow']} |" in text, "Report shows different flows"
    for s in STRATEGIES:
        assert f"| {STRATEGY_LABELS[s]} | {b['scores'][s]['auc_flow']:.3f}" in text, f"Report row for {s} differs"
    welch = report["welch_random_trials"]["auc_flow"]
    return (f"{b['types']:,} brain + {v['types']:,} VNC types agree with type_compartments.csv; sets split "
            f"{b['sensory']}/{v['sensory']} and {b['motor']}/{v['motor']}; Welch flow AUC p = {welch['p_value']:.2g} reproduced")


if __name__ == "__main__":
    run(check)
