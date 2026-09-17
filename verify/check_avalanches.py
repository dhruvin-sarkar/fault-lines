"""Check the avalanche summary against the avalanche sizes stored with the percolation curves."""

import numpy as np

from pipeline.avalanche_analysis import ALTERNATIVES, PLAUSIBLE_P
from pipeline.removal_strategies import MAX_FRACTION, STRATEGIES
from pipeline.run_percolation import RANDOM_TRIALS, TARGETED
from verify.common import result_csv, result_json, result_text, run


def sizes(curves, strategy: str, trial: int) -> np.ndarray:
    """Avalanche sizes of the batches within the first 50% of removals of one run."""
    rows = curves[(curves["strategy"] == strategy) & (curves["trial"] == trial)].sort_values("batch")
    window = int(np.argmax(rows["fraction_removed"].to_numpy() >= MAX_FRACTION))
    return rows["avalanche"].to_numpy()[1: window + 1].astype(int)


def check() -> str:
    report = result_json("avalanche_analysis.json")
    curves = result_csv("percolation_curves.csv")
    primary = {s: sizes(curves, s, 0) for s in STRATEGIES}
    sensitivity = np.concatenate([primary[s] for s in TARGETED] + [sizes(curves, "random", t) for t in range(RANDOM_TRIALS)])

    for strategy, values in primary.items():
        expected = {"batches": len(values), "zero_size": int((values == 0).sum()), "max_size": int(values.max()),
                    "total_cut_off": int(values.sum())}
        assert report["per_strategy"][strategy] == expected, f"per_strategy[{strategy}] differs from the curves: {expected}"

    for name, pooled in (("primary", np.concatenate(list(primary.values()))),
                         ("sensitivity_all_random_trials", sensitivity)):
        fit = report[name]
        assert fit["batches"] == len(pooled), f"{name}: {fit['batches']} batches, curves give {len(pooled)}"
        assert fit["zero_size"] == int((pooled == 0).sum()), f"{name}: zero-size count differs"
        assert fit["fitted"] == fit["batches"] - fit["zero_size"], f"{name}: fitted != batches - zero-size"
        assert fit["max_size"] == int(pooled.max()), f"{name}: largest avalanche differs"
        assert 1 <= fit["xmin"] <= fit["max_size"] and 0 < fit["n_tail"] <= fit["fitted"], f"{name}: tail malformed"
        assert fit["alpha"] > 1 and 0 <= fit["ks_distance"] <= 1, f"{name}: exponent or KS distance out of range"
        assert 0 <= fit["bootstrap_p"] <= 1, f"{name}: bootstrap p out of range"
        assert fit["power_law_plausible"] == (fit["bootstrap_p"] >= PLAUSIBLE_P), f"{name}: plausibility flag wrong"
        assert set(fit["comparisons"]) == set(ALTERNATIVES), f"{name}: comparisons {sorted(fit['comparisons'])}"
        assert all(0 <= c["p_value"] <= 1 for c in fit["comparisons"].values()), f"{name}: comparison p out of range"

    text = result_text("avalanche_analysis.md")
    for fit in (report["primary"], report["sensitivity_all_random_trials"]):
        assert f"| bootstrap goodness-of-fit p ({fit['bootstrap_sims']} synthetic sets) | {fit['bootstrap_p']:.3f} |" in text, \
            "avalanche_analysis.md shows a different bootstrap p"
    p = report["primary"]
    return (f"{p['batches']} primary and {report['sensitivity_all_random_trials']['batches']} sensitivity batches match "
            f"the curves; primary alpha {p['alpha']:.2f}, bootstrap p {p['bootstrap_p']:.3f}")


if __name__ == "__main__":
    run(check)
