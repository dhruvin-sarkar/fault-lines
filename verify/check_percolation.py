"""Check the percolation curves are well formed, reproduce every fragility score and match the report."""

import re

import numpy as np

from pipeline.removal_strategies import MAX_FRACTION, STRATEGIES
from pipeline.run_percolation import RANDOM_TRIALS, TARGETED, fragility, jobs, mean_ci95, report_lines
from verify.common import close, result_csv, result_json, result_text, run, same_text

# Fractions in percolation_curves.csv are written with six significant digits.
TOLERANCE = 1e-5


def check() -> str:
    summary = result_json("fragility_scores.json")
    graph, protocol, scores = summary["graph"], summary["protocol"], summary["strategies"]
    assert protocol["random_trials"] == RANDOM_TRIALS, f"{protocol['random_trials']} random trials recorded"
    assert protocol["auc_range"] == [0, MAX_FRACTION], f"AUC range {protocol['auc_range']}"
    assert set(scores) == set(STRATEGIES), f"Scored strategies {sorted(scores)}"

    curves = result_csv("percolation_curves.csv")
    runs = {key: group.sort_values("batch") for key, group in curves.groupby(["strategy", "trial"])}
    assert set(runs) == set(jobs()), f"{len(runs)} runs in percolation_curves.csv, expected {len(jobs())}"

    stated = re.search(r"\((\d+) batches on this graph\)", result_text("preregistration.md"))
    windows = set()
    for (strategy, trial), run_rows in runs.items():
        label = f"{strategy} trial {trial}"
        x = run_rows["fraction_removed"].to_numpy()
        flow, pairs = run_rows["flow"].to_numpy(), run_rows["reachable_pairs"].to_numpy()
        assert (run_rows["batch"].to_numpy() == np.arange(len(run_rows))).all(), f"{label}: batches not contiguous"
        assert x[0] == 0 and (np.diff(x) > 0).all() and x[-1] <= 1, f"{label}: fraction removed not increasing in [0, 1]"
        assert (flow[0], pairs[0]) == (graph["intact_flow"], graph["intact_reachable_pairs"]), f"{label}: intact values differ"
        assert (np.diff(flow) <= 0).all(), f"{label}: flow capacity increases after a removal"
        assert (np.diff(pairs) <= 0).all(), f"{label}: reachable pairs increase after a removal"
        avalanche = run_rows["avalanche"].to_numpy()
        assert np.isnan(avalanche[0]) and not np.isnan(avalanche[1:]).any() and (avalanche[1:] >= 0).all(), \
            f"{label}: avalanche sizes malformed"
        assert x[-1] >= MAX_FRACTION and flow[-1] < 0.5 * flow[0], f"{label}: run stops before 50% removed and flow halved"
        windows.add(int(np.argmax(x >= MAX_FRACTION)))
        runs[(strategy, trial)] = {"fraction_removed": x, "flow": flow, "reachable_pairs": pairs}

    assert len(windows) == 1, f"Runs reach 50% removed after different batch counts: {sorted(windows)}"
    if stated:
        assert windows == {int(stated.group(1))}, f"Pre-registered {stated.group(1)} batches, curves take {windows}"

    intact_flow, intact_pairs = graph["intact_flow"], graph["intact_reachable_pairs"]
    for strategy in TARGETED:
        recomputed = fragility(runs[(strategy, 0)], intact_flow, intact_pairs)
        for key, value in recomputed.items():
            assert abs(value - scores[strategy][key]) < TOLERANCE, \
                f"{strategy} {key} {scores[strategy][key]:.6f} does not match the curve ({value:.6f})"
    trials = [fragility(runs[("random", t)], intact_flow, intact_pairs) for t in range(RANDOM_TRIALS)]
    random_scores = scores["random"]
    for key in ("auc_flow", "auc_reachability"):
        values = [t[key] for t in trials]
        assert close(values, random_scores[f"{key}_trials"], rel=0, abs_tol=TOLERANCE), f"random {key} trials differ"
        mean, low, high = mean_ci95(random_scores[f"{key}_trials"])
        assert close([mean, low, high], [random_scores[key], *random_scores[f"{key}_ci95"]]), f"random {key} mean or CI"
        assert low <= random_scores[key] <= high, f"random {key} CI does not contain the mean"

    checks = {s: {k: scores[s][k] < random_scores[k] for k in ("auc_flow", "auc_reachability")} for s in TARGETED}
    assert summary["checkpoint_targeted_below_random"] == checks, "Recorded targeted-below-random flags differ"
    assert summary["checkpoint_passed"] == all(all(c.values()) for c in checks.values()), "checkpoint_passed is wrong"
    batches = windows.pop()
    expected = report_lines(summary, result_json("critical_thresholds.json"), batches)
    assert same_text(result_text("fragility_scores.md"), "\n".join(expected)), "fragility_scores.md is out of date"
    lowest = min(STRATEGIES, key=lambda s: scores[s]["auc_flow"])
    return (f"{len(runs)} monotone runs, {batches} batches to 50%, every AUC reproduced, report current; "
            f"most fragile by flow AUC: {lowest} ({scores[lowest]['auc_flow']:.3f} vs random {random_scores['auc_flow']:.3f})")


if __name__ == "__main__":
    run(check)
