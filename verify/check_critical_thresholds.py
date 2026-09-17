"""Check every critical removal fraction against the stored curves, and its reuse in the network comparison."""

import numpy as np

from pipeline.critical_thresholds import CUTOFF, critical_fraction
from pipeline.removal_strategies import STRATEGIES, STRATEGY_LABELS
from pipeline.run_percolation import RANDOM_TRIALS, TARGETED, mean_ci95
from verify.common import close, result_csv, result_json, result_text, run

TOLERANCE = 1e-5


def check() -> str:
    report = result_json("critical_thresholds.json")
    table = report["strategies"]
    assert report["cutoff"] == CUTOFF, f"Cutoff {report['cutoff']}"
    assert set(table) == set(STRATEGIES), f"Thresholds for {sorted(table)}"
    assert report["intact_flow"] == result_json("fragility_scores.json")["graph"]["intact_flow"], "Intact flow differs"

    curves = result_csv("percolation_curves.csv")

    def curve(strategy: str, trial: int) -> tuple[np.ndarray, np.ndarray]:
        rows = curves[(curves["strategy"] == strategy) & (curves["trial"] == trial)].sort_values("batch")
        return rows["fraction_removed"].to_numpy(), rows["flow"].to_numpy()

    for strategy in TARGETED:
        x, flow = curve(strategy, 0)
        f_c, batch = critical_fraction(x, flow)
        entry = table[strategy]
        assert abs(entry["f_c"] - f_c) < TOLERANCE, f"{strategy} f_c {entry['f_c']:.5f} differs from the curve ({f_c:.5f})"
        assert abs(entry["f_c_batch"] - batch) < TOLERANCE, f"{strategy} batch-level f_c differs from the curve"
        assert x[0] < entry["f_c"] <= entry["f_c_batch"] <= x[-1], f"{strategy} f_c lies outside its curve"

    random_entry = table["random"]
    per_trial = [critical_fraction(*curve("random", t)) for t in range(RANDOM_TRIALS)]
    assert close([p[0] for p in per_trial], random_entry["f_c_trials"], rel=0, abs_tol=TOLERANCE), "Random f_c trials differ"
    mean, low, high = mean_ci95(random_entry["f_c_trials"])
    assert close([mean, low, high], [random_entry["f_c"], *random_entry["f_c_ci95"]]), "Random f_c mean or CI differs"
    batch_mean, batch_low, batch_high = mean_ci95([p[1] for p in per_trial])
    assert close([batch_mean, batch_low, batch_high], [random_entry["f_c_batch"], *random_entry["f_c_batch_ci95"]],
                 rel=0, abs_tol=TOLERANCE), "Random batch-level f_c mean or CI differs"
    assert low <= random_entry["f_c"] <= high, "Random f_c CI does not contain the mean"
    for t in range(RANDOM_TRIALS):
        x, _ = curve("random", t)
        assert 0 < random_entry["f_c_trials"][t] <= x[-1], f"Random trial {t} f_c lies outside its curve"

    checks = {s: table[s]["f_c"] < random_entry["f_c_ci95"][0] for s in TARGETED}
    assert report["checkpoint_targeted_below_random"] == checks, "Recorded targeted-below-random flags differ"
    assert report["checkpoint_passed"] == all(checks.values()), "checkpoint_passed is wrong"
    assert report["most_damaging"] == min(TARGETED, key=lambda s: table[s]["f_c"]), "most_damaging is not the lowest f_c"

    text = result_text("critical_thresholds.md")
    for strategy in STRATEGIES:
        assert f"| {STRATEGY_LABELS[strategy]} | {table[strategy]['f_c']:.4f}" in text, \
            f"critical_thresholds.md does not show f_c for {strategy}"

    comparison = result_csv("network_comparison.csv")
    own = comparison[comparison["group"] == "this study"]
    assert len(own) == len(STRATEGIES), f"{len(own)} rows for this study in network_comparison.csv"
    for strategy in STRATEGIES:
        row = own[own["network"] == f"Male CNS cell types, {STRATEGY_LABELS[strategy]}"]
        assert len(row) == 1, f"network_comparison.csv has no row for {strategy}"
        assert abs(row["value"].iloc[0] - table[strategy]["f_c"]) < 5e-5, \
            f"network_comparison.csv gives {row['value'].iloc[0]} for {strategy}, f_c is {table[strategy]['f_c']:.4f}"

    most = report["most_damaging"]
    return (f"{len(STRATEGIES)} strategies reproduced from the curves; {most} halves flow at {table[most]['f_c']:.3f}, "
            f"random at {random_entry['f_c']:.3f} (CI {low:.3f} to {high:.3f}); network comparison agrees")


if __name__ == "__main__":
    run(check)
