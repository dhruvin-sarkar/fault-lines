"""Run the six removal strategies on the real cell-type graph and score their fragility."""

import argparse
import json
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd
from scipy import stats

from pipeline.build_type_graph import load_type_graph
from pipeline.common import DATA, RESULTS, SEED
from pipeline.connectivity_metrics import flow_capacity, reachable_pairs
from pipeline.figures import INK_SECONDARY, STRATEGY_COLORS, apply_style, plt
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets
from pipeline.removal_strategies import (
    BATCH_FRACTION,
    MAX_FRACTION,
    STRATEGIES,
    STRATEGY_LABELS,
    normalized_auc,
    percolate,
)

RANDOM_TRIALS = 30
RUNS_DIR = DATA / "percolation_runs"
CURVES_CSV = RESULTS / "percolation_curves.csv"
SCORES_JSON = RESULTS / "fragility_scores.json"
SCORES_MD = RESULTS / "fragility_scores.md"
THRESHOLDS_JSON = RESULTS / "critical_thresholds.json"
TARGETED = tuple(s for s in STRATEGIES if s != "random")


def trial_seed(strategy: str, trial: int) -> int:
    return SEED + 1000 * STRATEGIES.index(strategy) + trial


def auc_window(fraction_removed: np.ndarray) -> int:
    """Number of curve points up to and including the first point with at least MAX_FRACTION removed."""
    reached = np.asarray(fraction_removed) >= MAX_FRACTION
    if not reached.any():
        raise ValueError(f"Run stops before {MAX_FRACTION:.0%} of vertices are removed")
    return int(np.argmax(reached)) + 1


def fragility(run: dict, intact_flow: float, intact_pairs: float) -> dict[str, float]:
    """Normalized AUC of the flow and reachability curves over the first MAX_FRACTION of removals."""
    k = auc_window(run["fraction_removed"])
    x = run["fraction_removed"][:k]
    return {
        "auc_flow": normalized_auc(x, run["flow"][:k], intact_flow),
        "auc_reachability": normalized_auc(x, run["reachable_pairs"][:k], intact_pairs),
    }


def mean_ci95(values) -> tuple[float, float, float]:
    """Mean and Student-t 95% confidence interval of the mean."""
    values = np.asarray(values, dtype=float)
    half = stats.t.ppf(0.975, len(values) - 1) * values.std(ddof=1) / np.sqrt(len(values))
    return float(values.mean()), float(values.mean() - half), float(values.mean() + half)


def load_run(path) -> dict:
    run = json.loads(path.read_text(encoding="utf-8"))
    for key in ("fraction_removed", "flow", "reachable_pairs", "avalanche"):
        run[key] = np.asarray(run[key])
    return run


def save_run(run: dict, path) -> None:
    serializable = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in run.items()}
    path.write_text(json.dumps(serializable), encoding="utf-8")


_WORKER: dict = {}


def _init_worker(graph, sources, targets, intact_flow, runs_dir) -> None:
    _WORKER.update(graph=graph, sources=sources, targets=targets, intact_flow=intact_flow, runs_dir=runs_dir)


def _run_job(job: tuple[str, int]) -> tuple[str, int]:
    strategy, trial = job
    path = _WORKER["runs_dir"] / f"{strategy}_{trial:02d}.json"
    if not path.exists():
        run = percolate(
            _WORKER["graph"],
            strategy,
            _WORKER["sources"],
            _WORKER["targets"],
            seed=trial_seed(strategy, trial),
            continue_until_flow_below=0.5 * _WORKER["intact_flow"],
        )
        save_run(run, path)
    return strategy, trial


def jobs() -> list[tuple[str, int]]:
    return [(s, 0) for s in ("betweenness", "sm_betweenness", "pagerank", "out_strength", "in_strength")] + [
        ("random", t) for t in range(RANDOM_TRIALS)
    ]


def load_all_runs(runs_dir=RUNS_DIR) -> dict[tuple[str, int], dict]:
    return {job: load_run(runs_dir / f"{job[0]}_{job[1]:02d}.json") for job in jobs()}


def run_protocol(graph, sources: list[str], targets: list[str], runs_dir, workers: int) -> dict[tuple[str, int], dict]:
    """Every targeted strategy once and random removal RANDOM_TRIALS times; cached per run in ``runs_dir``."""
    intact_flow = flow_capacity(graph, sources, targets)
    runs_dir.mkdir(parents=True, exist_ok=True)
    with Pool(workers, initializer=_init_worker, initargs=(graph, sources, targets, intact_flow, runs_dir)) as pool:
        for i, (strategy, trial) in enumerate(pool.imap_unordered(_run_job, jobs()), start=1):
            print(f"[{i}/{len(jobs())}] {runs_dir.name}: {strategy} trial {trial}", flush=True)
    return load_all_runs(runs_dir)


def score_runs(runs: dict, intact_flow: int, intact_pairs: int) -> dict:
    """Per-strategy AUCs; random removal as the mean over trials with a 95% CI."""
    scores: dict = {}
    random_scores = [fragility(runs[("random", t)], intact_flow, intact_pairs) for t in range(RANDOM_TRIALS)]
    scores["random"] = {"trials": RANDOM_TRIALS}
    for key in ("auc_flow", "auc_reachability"):
        mean, lo, hi = mean_ci95([s[key] for s in random_scores])
        scores["random"].update({key: mean, f"{key}_ci95": [lo, hi], f"{key}_trials": [s[key] for s in random_scores]})
    for strategy in TARGETED:
        scores[strategy] = fragility(runs[(strategy, 0)], intact_flow, intact_pairs)
    return scores


def runs_from_curves(curves: pd.DataFrame, cell_types: int) -> dict[tuple[str, int], dict]:
    """Runs keyed by (strategy, trial), read back from a ``percolation_curves.csv`` table.

    Parameters: ``curves``, the table; ``cell_types``, the vertex count of the graph, used to restore the exact
    removed fractions from their rounded values in the CSV.
    Returns ``fraction_removed``, ``flow`` and ``reachable_pairs`` arrays per run, in batch order.
    """
    return {
        (strategy, int(trial)): {
            "fraction_removed": np.rint(rows["fraction_removed"].to_numpy() * cell_types) / cell_types,
            "flow": rows["flow"].to_numpy(),
            "reachable_pairs": rows["reachable_pairs"].to_numpy(),
        }
        for (strategy, trial), rows in curves.sort_values("batch").groupby(["strategy", "trial"])
    }


def report_lines(summary: dict, thresholds: dict, batches: int) -> list[str]:
    """Lines of ``fragility_scores.md``.

    Parameters: ``summary``, the dictionary written to ``fragility_scores.json``; ``thresholds``, the dictionary
    written to ``critical_thresholds.json``; ``batches``, the number of removal batches taken to reach the end of
    the AUC range.
    Returns the markdown lines.
    """
    graph, protocol, scores = summary["graph"], summary["protocol"], summary["strategies"]
    f_c = thresholds["strategies"]
    random_scores = scores["random"]
    trials = protocol["random_trials"]
    start, end = protocol["auc_range"]
    targeted = [s for s in STRATEGIES if s != "random"]

    def pct(value: float) -> str:
        return f"{100 * value:.0f}%"

    def with_ci(value: float, ci: list[float]) -> str:
        return f"{value:.3f} (95% CI {ci[0]:.3f} to {ci[1]:.3f})"

    def spread(values: list[float]) -> str:
        return f"{min(values):.3f} to {max(values):.3f} (SD {np.std(values, ddof=1):.3f})"

    def listing(strategies: list[str], key) -> str:
        items = [f"{STRATEGY_LABELS[s]} ({key(s):.3f})" for s in strategies]
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" and {items[-1]}"

    def auc_cell(strategy: str, key: str) -> str:
        entry = scores[strategy]
        return with_ci(entry[key], entry[f"{key}_ci95"]) if strategy == "random" else f"{entry[key]:.3f}"

    def f_c_cell(strategy: str) -> str:
        entry = f_c[strategy]
        return with_ci(entry["f_c"], entry["f_c_ci95"]) if strategy == "random" else f"{entry['f_c']:.3f}"

    by_flow = sorted(targeted, key=lambda s: scores[s]["auc_flow"])
    by_pairs = sorted(targeted, key=lambda s: scores[s]["auc_reachability"])
    by_f_c = sorted(targeted, key=lambda s: f_c[s]["f_c"])
    failed = [s for s, ok in summary["checkpoint_targeted_below_random"].items() if not all(ok.values())]
    below_ci = all(scores[s][key] < random_scores[f"{key}_ci95"][0]
                   for s in targeted for key in ("auc_flow", "auc_reachability"))

    ranking = [
        f"By flow capacity AUC the most damaging order is {STRATEGY_LABELS[by_flow[0]]} "
        f"({scores[by_flow[0]]['auc_flow']:.3f}), followed by "
        f"{listing(by_flow[1:], lambda s: scores[s]['auc_flow'])}; random removal scores "
        f"{random_scores['auc_flow']:.3f}. By reachability AUC the order is "
        f"{listing(by_pairs, lambda s: scores[s]['auc_reachability'])}, against "
        f"{random_scores['auc_reachability']:.3f} for random removal.",
    ]
    if by_f_c != by_flow:
        ranking.append(
            f" Ordered by f_c instead, the sequence is {', '.join(STRATEGY_LABELS[s] for s in by_f_c[:-1])} and "
            f"{STRATEGY_LABELS[by_f_c[-1]]}, because f_c marks the single point where flow halves while the AUC "
            f"averages over the whole first {pct(end)} of removals."
        )
    if failed:
        check = f"not met for {', '.join(STRATEGY_LABELS[s] for s in failed)}."
    else:
        check = "met." + (" Every targeted score also lies below the lower bound of the random-removal confidence "
                          "interval." if below_ci else "")

    return [
        "# Fragility scores",
        "",
        "How much sensory-to-motor routing survives as cell types are removed, and how much faster it fails when the "
        "most central types are removed first. Each strategy is summarized by the area under its removal curve, one "
        "number for the whole first half of the attack. The protocol was fixed in `results/preregistration.md` before "
        "any removal was run. Every curve is in `results/percolation_curves.csv` and every score in "
        "`results/fragility_scores.json`.",
        "",
        "## Graph",
        "",
        "| quantity | value |",
        "|---|---|",
        f"| cell types | {graph['cell_types']:,} |",
        f"| connections | {graph['edges']:,} |",
        f"| sensory types (S) | {graph['sensory_types']:,} |",
        f"| descending and motor types (M) | {graph['motor_types']:,} |",
        f"| intact flow capacity (edge-disjoint S-to-M paths) | {graph['intact_flow']:,} |",
        f"| intact reachable S-M pairs | {graph['intact_reachable_pairs']:,} of {graph['sensory_motor_pairs']:,} "
        f"({100 * graph['intact_reachable_pairs'] / graph['sensory_motor_pairs']:.1f}%) |",
        "",
        "## Protocol",
        "",
        f"- Strategies: {', '.join(STRATEGY_LABELS[s] for s in STRATEGIES[:-1])} and "
        f"{STRATEGY_LABELS[STRATEGIES[-1]]}.",
        f"- Adaptive removal: each batch removes the {pct(protocol['batch_fraction_of_remaining'])} of remaining cell "
        f"types with the highest current score, and every score is recomputed on the reduced graph before the next "
        f"batch. Reaching {pct(end)} removed takes {batches} batches.",
        f"- Fragility score: the trapezoidal area under the retained fraction of the intact value, plotted against the "
        f"fraction of cell types removed from {pct(start)} to {pct(end)}, divided by the width of that range. It is the "
        f"mean retained fraction over the range: 1 means nothing was lost, and lower is more fragile.",
        "- Metrics: flow capacity (primary) and the number of reachable sensory-motor pairs (secondary).",
        f"- Random removal: {trials} trials, reported as the mean with a Student-t 95% confidence interval. Each "
        f"targeted strategy is run once.",
        f"- Seed: {protocol['seed']}.",
        f"- f_c: the fraction of cell types removed when flow capacity first falls below {pct(thresholds['cutoff'])} "
        f"of its intact value, interpolated between batches ([critical_thresholds.md](critical_thresholds.md)).",
        "",
        "## Scores",
        "",
        "| strategy | AUC, flow capacity | AUC, reachability | f_c |",
        "|---|---|---|---|",
        *[f"| {STRATEGY_LABELS[s]} | {auc_cell(s, 'auc_flow')} | {auc_cell(s, 'auc_reachability')} | {f_c_cell(s)} |"
          for s in sorted(STRATEGIES, key=lambda s: scores[s]["auc_flow"])],
        "",
        f"Across the {trials} random trials, flow capacity AUC ranges from {spread(random_scores['auc_flow_trials'])}, "
        f"reachability AUC from {spread(random_scores['auc_reachability_trials'])}, and f_c from "
        f"{spread(f_c['random']['f_c_trials'])}.",
        "",
        "".join(ranking),
        "",
        f"Pre-registered check that every targeted strategy scores below the random mean on both metrics: {check}",
        "",
        "## Null model",
        "",
        "These scores describe one graph. Whether they are lower than the scores of degree-preserving randomized "
        "graphs, the pre-registered headline test, is reported in [null_model_validation.md](null_model_validation.md).",
        "",
        "## Figure",
        "",
        "![Flow capacity and reachable sensory-motor pairs under each removal strategy](percolation_curves.png)",
        "",
        f"Left: flow capacity. Right: reachable sensory-motor pairs. Both are shown as a fraction of the intact value "
        f"over the first {pct(end)} of removals; random removal is the mean of {trials} trials with its 95% "
        "confidence band.",
        "",
    ]


def write_report(summary: dict, thresholds: dict, runs: dict) -> None:
    """Write ``fragility_scores.md`` from the scores, the critical thresholds and the runs they were computed on."""
    batches = auc_window(runs[("random", 0)]["fraction_removed"]) - 1
    lines = report_lines(summary, thresholds, batches)
    SCORES_MD.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def plot(runs: dict, scores: dict, intact_flow: int, intact_pairs: int) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.0), dpi=200, sharex=True)
    panels = [("flow", intact_flow, "auc_flow", "Sensory-to-motor flow capacity"), ("reachable_pairs", intact_pairs, "auc_reachability", "Sensory-motor pairs still connected")]
    for ax, (key, baseline, auc_key, title) in zip(axes, panels):
        trials = [runs[("random", t)] for t in range(RANDOM_TRIALS)]
        k = auc_window(trials[0]["fraction_removed"])
        x = 100 * trials[0]["fraction_removed"][:k]
        curves = np.array([r[key][:k] / baseline for r in trials])
        mean = curves.mean(axis=0)
        half = stats.t.ppf(0.975, len(curves) - 1) * curves.std(axis=0, ddof=1) / np.sqrt(len(curves))
        ax.fill_between(x, mean - half, mean + half, color=STRATEGY_COLORS["random"], alpha=0.25, linewidth=0)
        ax.plot(x, mean, color=STRATEGY_COLORS["random"], linestyle="--",
                label=f"{STRATEGY_LABELS['random']} (mean of {RANDOM_TRIALS}, 95% CI), AUC {scores['random'][auc_key]:.3f}")
        for strategy in TARGETED:
            run = runs[(strategy, 0)]
            k = auc_window(run["fraction_removed"])
            ax.plot(100 * run["fraction_removed"][:k], run[key][:k] / baseline, color=STRATEGY_COLORS[strategy],
                    label=f"{STRATEGY_LABELS[strategy]}, AUC {scores[strategy][auc_key]:.3f}")
        ax.set_title(title, loc="left")
        ax.set_xlabel("cell types removed (%)")
        ax.set_ylabel("fraction of intact value")
        ax.set_xlim(0, 100 * MAX_FRACTION)
        ax.set_ylim(0, 1.02)
        ax.legend(loc="upper right", handlelength=2.4)
    fig.text(0.01, 0.01, f"Adaptive removal: each batch removes the top {BATCH_FRACTION:.0%} of remaining types, "
             "scores recomputed after every batch. AUC is the mean retained fraction over 0-50% removed.",
             fontsize=8, color=INK_SECONDARY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(RESULTS / "percolation_curves.png")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--from-results", action="store_true",
                        help="rebuild the report and figure from results/fragility_scores.json, "
                             "results/percolation_curves.csv and results/critical_thresholds.json without rerunning "
                             "percolation")
    args = parser.parse_args()

    if args.from_results:
        summary = json.loads(SCORES_JSON.read_text(encoding="utf-8"))
        graph = summary["graph"]
        runs = runs_from_curves(pd.read_csv(CURVES_CSV), graph["cell_types"])
        plot(runs, summary["strategies"], graph["intact_flow"], graph["intact_reachable_pairs"])
        write_report(summary, json.loads(THRESHOLDS_JSON.read_text(encoding="utf-8")), runs)
        return

    graph = load_type_graph()
    sources, targets = load_sensory_motor_sets()
    intact_flow = flow_capacity(graph, sources, targets)
    intact_pairs = reachable_pairs(graph, sources, targets)
    runs = run_protocol(graph, sources, targets, RUNS_DIR, args.workers)

    rows = []
    for (strategy, trial), run in runs.items():
        avalanche = np.concatenate([[np.nan], run["avalanche"]])
        rows.append(pd.DataFrame({
            "strategy": strategy, "trial": trial, "batch": np.arange(len(run["flow"])),
            "fraction_removed": run["fraction_removed"], "flow": run["flow"],
            "reachable_pairs": run["reachable_pairs"], "avalanche": avalanche,
        }))
    pd.concat(rows, ignore_index=True).to_csv(CURVES_CSV, index=False, float_format="%.6g")

    scores = score_runs(runs, intact_flow, intact_pairs)
    checks = {
        strategy: {key: scores[strategy][key] < scores["random"][key] for key in ("auc_flow", "auc_reachability")}
        for strategy in TARGETED
    }
    passed = all(all(c.values()) for c in checks.values())
    summary = {
        "graph": {
            "cell_types": graph.vcount(), "edges": graph.ecount(), "sensory_types": len(sources),
            "motor_types": len(targets), "intact_flow": intact_flow, "intact_reachable_pairs": intact_pairs,
            "sensory_motor_pairs": len(sources) * len(targets),
        },
        "protocol": {
            "batch_fraction_of_remaining": BATCH_FRACTION, "auc_range": [0, MAX_FRACTION],
            "auc_definition": "trapezoidal area under value / intact value against fraction removed, divided by the "
                              "fraction range; lower is more fragile",
            "random_trials": RANDOM_TRIALS, "seed": SEED,
        },
        "strategies": scores,
        "checkpoint_targeted_below_random": checks,
        "checkpoint_passed": passed,
    }
    SCORES_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    plot(runs, scores, intact_flow, intact_pairs)

    print(f"intact flow {intact_flow}, reachable pairs {intact_pairs} of {len(sources) * len(targets)}")
    for strategy in STRATEGIES:
        print(f"{strategy:>15}: AUC flow {scores[strategy]['auc_flow']:.4f}, reachability {scores[strategy]['auc_reachability']:.4f}")
    if not passed:
        print(f"CHECKPOINT FAILED: some targeted strategy is not more damaging than random: {checks}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
