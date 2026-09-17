"""Check the degree-preserving null-model test: number of graphs, p-value floor and every p-value against the scores."""

import numpy as np
import pandas as pd

from pipeline.common import RESULTS
from pipeline.null_model import ALPHA, N_NULLS, empirical_p_value_lower, null_seed
from pipeline.removal_strategies import STRATEGIES, STRATEGY_LABELS
from pipeline.run_percolation import RANDOM_TRIALS
from verify.common import Skip, close, result_json, result_text, run

METRICS = ("auc_flow", "auc_reachability")
# null_model_scores.csv is written with six significant digits.
REL = 2e-6


def check() -> str:
    if not (RESULTS / "null_model_summary.json").exists():
        partial = [n for n in ("null_model_scores.csv", "null_distribution.png") if (RESULTS / n).exists()]
        assert not partial, f"null_model_summary.json is absent but {', '.join(partial)} exist"
        raise Skip("results/null_model_summary.json not written yet; the null-model run has not finished")

    summary = result_json("null_model_summary.json")
    n = summary["n_nulls"]
    assert n == N_NULLS, f"{n} randomized graphs, pre-registered {N_NULLS}"
    assert close(summary["alpha"], ALPHA), f"alpha {summary['alpha']}, pre-registered {ALPHA}"
    assert set(summary["strategies"]) == set(STRATEGIES), f"Strategies {sorted(summary['strategies'])}"

    scores = pd.read_csv(RESULTS / "null_model_scores.csv")
    assert len(scores) == n * len(STRATEGIES), f"{len(scores)} score rows, expected {n} x {len(STRATEGIES)}"
    assert not scores.duplicated(["null_index", "strategy"]).any(), "Duplicate (null graph, strategy) rows"
    assert set(scores["null_index"]) == set(range(n)), "Null indices are not 0 .. N-1"
    assert (scores["seed"] == scores["null_index"].map(null_seed)).all(), "Seeds differ from the pre-registered scheme"
    expected_trials = np.where(scores["strategy"] == "random", RANDOM_TRIALS, 1)
    assert (scores["trials"] == expected_trials).all(), "Trial counts per strategy differ from the protocol"
    assert scores[list(METRICS)].apply(lambda c: c.between(0, 1)).all().all(), "Null AUC outside [0, 1]"

    real = result_json("fragility_scores.json")["strategies"]
    floor = 1 / (n + 1)
    for strategy in STRATEGIES:
        null = scores[scores["strategy"] == strategy]
        for metric in METRICS:
            s = summary["strategies"][strategy][metric]
            label = f"{strategy} {metric}"
            values = null[metric].to_numpy()
            assert close(s["real"], real[strategy][metric]), f"{label}: real AUC differs from fragility_scores.json"
            assert floor <= s["p_value"] <= 1, f"{label}: p = {s['p_value']} outside [1/{n + 1}, 1]"
            assert close(s["p_value"], (1 + s["n_at_or_below_real"]) / (1 + n)), f"{label}: p != (1 + k) / (1 + N)"
            recomputed = empirical_p_value_lower(s["real"], values)
            assert close(s["p_value"], recomputed), f"{label}: p = {s['p_value']:.4f}, scores give {recomputed:.4f}"
            assert close([s["null_mean"], s["null_sd"], s["null_min"], s["null_max"]],
                         [values.mean(), values.std(ddof=1), values.min(), values.max()], rel=1e-5), \
                f"{label}: null distribution summary differs from the scores"
            assert close(s["z_score"], (s["real"] - s["null_mean"]) / s["null_sd"]), f"{label}: z-score arithmetic"
            assert s["significant"] == (s["p_value"] < ALPHA), f"{label}: significance flag wrong"

    text = result_text("null_model_validation.md")
    assert f"N = {n} randomized graphs" in text, "null_model_validation.md states a different N"
    for strategy in STRATEGIES:
        s = summary["strategies"][strategy]["auc_flow"]
        assert f"| {STRATEGY_LABELS[strategy]} | {s['real']:.4f} |" in text and f"| {s['p_value']:.4f} |" in text, \
            f"null_model_validation.md row for {strategy} differs"
    assert (RESULTS / "null_distribution.png").exists(), "null_distribution.png missing"
    significant = [s for s in STRATEGIES if summary["strategies"][s]["auc_flow"]["significant"]]
    return (f"N = {n}, p floor 1/{n + 1}, every p reproduced from {len(scores)} scores; "
            f"significant at {ALPHA:.4f}: {', '.join(significant) or 'none'}")


if __name__ == "__main__":
    run(check)
