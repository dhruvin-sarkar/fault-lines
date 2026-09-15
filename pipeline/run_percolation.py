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
    args = parser.parse_args()

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
