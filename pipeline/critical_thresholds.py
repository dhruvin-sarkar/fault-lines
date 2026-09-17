"""Critical removal fraction per strategy: where sensory-to-motor flow capacity first falls below half."""

import json
import sys

import numpy as np

from pipeline.common import RESULTS
from pipeline.removal_strategies import STRATEGIES, STRATEGY_LABELS
from pipeline.run_percolation import RANDOM_TRIALS, SCORES_JSON, TARGETED, load_all_runs, mean_ci95

CUTOFF = 0.5


def critical_fraction(fraction_removed: np.ndarray, flow: np.ndarray, cutoff: float = CUTOFF) -> tuple[float, float]:
    """Fraction removed at which flow first drops below ``cutoff`` x its intact value.

    Returns:
        (interpolated, batch_level): the linear interpolation between the last point at or above the cutoff
        and the first point below it, and the fraction removed at that first point below.
    """
    x, y = np.asarray(fraction_removed, dtype=float), np.asarray(flow, dtype=float)
    threshold = cutoff * y[0]
    below = np.flatnonzero(y < threshold)
    if len(below) == 0:
        raise ValueError(f"Flow never falls below {cutoff:.0%} of its intact value in this run")
    i = int(below[0])
    interpolated = x[i - 1] + (x[i] - x[i - 1]) * (y[i - 1] - threshold) / (y[i - 1] - y[i])
    return float(interpolated), float(x[i])


def main() -> None:
    runs = load_all_runs()
    table = {}
    for strategy in TARGETED:
        run = runs[(strategy, 0)]
        interpolated, batch = critical_fraction(run["fraction_removed"], run["flow"])
        table[strategy] = {"f_c": interpolated, "f_c_batch": batch}
    per_trial = [critical_fraction(runs[("random", t)]["fraction_removed"], runs[("random", t)]["flow"]) for t in range(RANDOM_TRIALS)]
    mean, lo, hi = mean_ci95([p[0] for p in per_trial])
    batch_mean, batch_lo, batch_hi = mean_ci95([p[1] for p in per_trial])
    table["random"] = {
        "f_c": mean, "f_c_ci95": [lo, hi], "f_c_batch": batch_mean, "f_c_batch_ci95": [batch_lo, batch_hi],
        "f_c_trials": [p[0] for p in per_trial],
    }

    checks = {s: table[s]["f_c"] < table["random"]["f_c_ci95"][0] for s in TARGETED}
    most = min(TARGETED, key=lambda s: table[s]["f_c"])
    intact_flow = json.loads(SCORES_JSON.read_text(encoding="utf-8"))["graph"]["intact_flow"]
    summary = {"cutoff": CUTOFF, "intact_flow": intact_flow, "strategies": table, "most_damaging": most,
               "checkpoint_targeted_below_random": checks, "checkpoint_passed": all(checks.values())}
    (RESULTS / "critical_thresholds.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    order = sorted(STRATEGIES, key=lambda s: table[s]["f_c"])
    lines = [
        "# Critical removal thresholds",
        "",
        f"f_c is the fraction of cell types removed at which sensory-to-motor flow capacity (edge-disjoint S→M paths; "
        f"{intact_flow} in the intact graph) first falls below {CUTOFF:.0%} of its intact value. The same cutoff is "
        "applied to every strategy. The primary value interpolates linearly between the last removal batch at or above "
        "the cutoff and the first batch below it; the batch-level value is the fraction removed at that first batch. "
        f"Random removal: mean over {RANDOM_TRIALS} trials with a Student-t 95% confidence interval.",
        "",
        "| strategy | f_c (interpolated) | f_c (first batch below) |",
        "|---|---|---|",
    ]
    for s in order:
        r = table[s]
        if s == "random":
            lines.append(f"| {STRATEGY_LABELS[s]} | {r['f_c']:.4f} (95% CI {r['f_c_ci95'][0]:.4f} to {r['f_c_ci95'][1]:.4f}) | "
                         f"{r['f_c_batch']:.4f} (95% CI {r['f_c_batch_ci95'][0]:.4f} to {r['f_c_batch_ci95'][1]:.4f}) |")
        else:
            lines.append(f"| {STRATEGY_LABELS[s]} | {r['f_c']:.4f} | {r['f_c_batch']:.4f} |")
    lines += [
        "",
        f"Under {STRATEGY_LABELS[most]} removal, sensory-to-motor flow capacity halves after removing "
        f"{100 * table[most]['f_c']:.1f}% of cell types; under random removal it takes {100 * table['random']['f_c']:.1f}%.",
        "",
        "Check: every targeted strategy's f_c lies below the lower bound of the random-removal confidence interval: "
        + ("yes." if all(checks.values()) else f"no ({', '.join(s for s, ok in checks.items() if not ok)})."),
        "",
    ]
    (RESULTS / "critical_thresholds.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    if not all(checks.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
