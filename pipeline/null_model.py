"""Degree-preserving randomization test for the fragility (AUC) of each removal strategy."""

import argparse
import json
import random
from multiprocessing import Pool

import igraph as ig
import numpy as np
import pandas as pd

from pipeline.build_type_graph import load_type_graph
from pipeline.common import DATA, RESULTS, SEED
from pipeline.connectivity_metrics import flow_capacity, reachable_pairs
from pipeline.figures import INK, INK_SECONDARY, MUTED, STRATEGY_COLORS, apply_style, plt
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets
from pipeline.removal_strategies import STRATEGIES, STRATEGY_LABELS, percolate
from pipeline.run_percolation import RANDOM_TRIALS, fragility, trial_seed

SWAPS_PER_EDGE = 10
N_NULLS = 200
NULL_SEED_OFFSET = 100_000
ALPHA = 0.05 / len(STRATEGIES)
NULL_RUNS_DIR = DATA / "null_runs"
SCORES_CSV = RESULTS / "null_model_scores.csv"
PREREGISTRATION_COMMIT = "0e72491"
HYPOTHESIS = f"""\
# Null-model validation

## Hypothesis (stated before any randomized graph was scored)

For each of the six removal strategies k:

> **H_k**: the real graph's flow-capacity AUC under strategy k is **lower** (the real network is more fragile) than \
the flow-capacity AUC of degree-preserving randomized graphs under the same strategy.

The test is one-sided in that direction for every strategy. Empirical p-value: p_k = (1 + number of randomized graphs \
with AUC ≤ real AUC) / (1 + N), with N = {N_NULLS} randomized graphs. Six tests at a Bonferroni-corrected threshold \
of α = 0.05 / 6 = {ALPHA:.4f}; the smallest attainable p is 1 / {N_NULLS + 1} = {1 / (N_NULLS + 1):.4f}. The same \
one-sided test on reachability AUC is secondary. The full plan, including every protocol parameter, was committed in \
`results/preregistration.md` (commit `{PREREGISTRATION_COMMIT}`) before any percolation run.
"""


def rewire(graph: ig.Graph, seed: int, swaps_per_edge: int = SWAPS_PER_EDGE) -> ig.Graph:
    """Randomize edges with in/out-degree-preserving swaps.

    Every vertex keeps its exact in-degree and out-degree. Each source vertex's original set of
    out-edge synapse counts is reassigned, shuffled, to its new out-edges, so out-strength is also
    preserved while the identity of downstream partners is randomized.
    """
    null = graph.copy()
    random.seed(seed)
    null.rewire(n=swaps_per_edge * graph.ecount(), allowed_edge_types="simple")

    rng = np.random.default_rng(seed)
    old_sources = np.asarray(graph.get_edgelist(), dtype=np.int64).reshape(-1, 2)[:, 0]
    new_sources = np.asarray(null.get_edgelist(), dtype=np.int64).reshape(-1, 2)[:, 0]
    old_weights = np.asarray(graph.es["weight"])
    old_order = np.lexsort((rng.random(len(old_sources)), old_sources))
    new_order = np.argsort(new_sources, kind="stable")
    weights = np.empty_like(old_weights)
    weights[new_order] = old_weights[old_order]
    null.es["weight"] = weights.tolist()
    if "input_fraction" in null.es.attributes():
        del null.es["input_fraction"]
    return null


def empirical_p_value_lower(real: float, null: np.ndarray) -> float:
    """One-sided permutation p-value for real < null, with the +1 correction so it is never exactly zero."""
    return float((1 + np.sum(np.asarray(null) <= real)) / (1 + len(null)))


def null_seed(index: int) -> int:
    return SEED + NULL_SEED_OFFSET + index


_WORKER: dict = {}


def _init_worker(graph: ig.Graph, sources: list[str], targets: list[str]) -> None:
    _WORKER.update(graph=graph, sources=sources, targets=targets)


def run_null_job(job: tuple[int, str]) -> tuple[int, str]:
    """Rewire the graph for one null index and apply one strategy (all random trials for ``random``)."""
    index, strategy = job
    path = NULL_RUNS_DIR / f"null_{index:03d}_{strategy}.npz"
    if path.exists():
        return job
    sources, targets = _WORKER["sources"], _WORKER["targets"]
    null = rewire(_WORKER["graph"], null_seed(index))
    intact_flow, intact_pairs = flow_capacity(null, sources, targets), reachable_pairs(null, sources, targets)
    trials = range(RANDOM_TRIALS) if strategy == "random" else range(1)
    runs = [percolate(null, strategy, sources, targets, seed=trial_seed(strategy, t)) for t in trials]
    scores = [fragility(run, intact_flow, intact_pairs) for run in runs]
    np.savez_compressed(
        path,
        fraction_removed=runs[0]["fraction_removed"],
        flow=np.array([r["flow"] for r in runs]),
        reachable_pairs=np.array([r["reachable_pairs"] for r in runs]),
        auc_flow=np.array([s["auc_flow"] for s in scores]),
        auc_reachability=np.array([s["auc_reachability"] for s in scores]),
        intact_flow=intact_flow,
        intact_pairs=intact_pairs,
    )
    return job


def collect_scores(n_nulls: int) -> pd.DataFrame:
    rows = []
    for index in range(n_nulls):
        for strategy in STRATEGIES:
            data = np.load(NULL_RUNS_DIR / f"null_{index:03d}_{strategy}.npz")
            rows.append(
                {
                    "null_index": index,
                    "seed": null_seed(index),
                    "strategy": strategy,
                    "trials": len(data["auc_flow"]),
                    "auc_flow": float(data["auc_flow"].mean()),
                    "auc_reachability": float(data["auc_reachability"].mean()),
                    "intact_flow": int(data["intact_flow"]),
                    "intact_pairs": int(data["intact_pairs"]),
                }
            )
    return pd.DataFrame(rows)


def summarize(real: dict, scores: pd.DataFrame) -> dict:
    summary = {}
    for strategy in STRATEGIES:
        null = scores[scores["strategy"] == strategy]
        summary[strategy] = {}
        for metric in ("auc_flow", "auc_reachability"):
            values = null[metric].to_numpy()
            r = real[strategy][metric]
            summary[strategy][metric] = {
                "real": r,
                "null_mean": float(values.mean()),
                "null_sd": float(values.std(ddof=1)),
                "null_min": float(values.min()),
                "null_max": float(values.max()),
                "n_at_or_below_real": int(np.sum(values <= r)),
                "z_score": float((r - values.mean()) / values.std(ddof=1)),
                "p_value": empirical_p_value_lower(r, values),
            }
            summary[strategy][metric]["significant"] = summary[strategy][metric]["p_value"] < ALPHA
    return summary


def plot(summary: dict, scores: pd.DataFrame) -> None:
    apply_style()
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.2), dpi=200)
    for ax, strategy in zip(axes.flat, STRATEGIES):
        values = scores.loc[scores["strategy"] == strategy, "auc_flow"].to_numpy()
        s = summary[strategy]["auc_flow"]
        lo, hi = min(values.min(), s["real"]), max(values.max(), s["real"])
        pad = 0.08 * (hi - lo) if hi > lo else 0.01
        ax.hist(values, bins=np.linspace(lo - pad, hi + pad, 40), color=STRATEGY_COLORS[strategy], alpha=0.55,
                edgecolor="none", label=f"randomized graphs (n={len(values)})")
        ax.axvline(s["real"], color=INK, linewidth=2, label=f"real connectome {s['real']:.3f}")
        ax.set_title(STRATEGY_LABELS[strategy], loc="left")
        ax.text(0.98, 0.95, f"p = {s['p_value']:.4f}\nz = {s['z_score']:.1f}", transform=ax.transAxes,
                ha="right", va="top", fontsize=9, color=INK_SECONDARY)
        ax.set_xlabel("flow-capacity AUC (lower is more fragile)")
        ax.grid(axis="x", visible=False)
        ax.legend(loc="upper left", fontsize=7.5)
    for ax in axes[:, 0]:
        ax.set_ylabel("randomized graphs")
    fig.text(0.01, 0.005, f"One-sided empirical p = (1 + #null AUC <= real) / (1 + N); Bonferroni threshold {ALPHA:.4f}.",
             fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(RESULTS / "null_distribution.png")
    plt.close(fig)


def write_report(summary: dict, graph: ig.Graph, n_nulls: int) -> None:
    lines = [
        HYPOTHESIS,
        "## Procedure",
        "",
        f"1. {n_nulls} randomized versions of the cell-type graph ({graph.vcount()} types, {graph.ecount()} edges), each "
        f"with {SWAPS_PER_EDGE} × |E| in/out-degree-preserving edge swaps (`igraph.Graph.rewire`, simple graphs). Every "
        "type keeps its exact in-degree and out-degree; each type's outgoing synapse counts are shuffled across its new "
        "outgoing edges, preserving out-strength. Sensory and motor types keep their labels.",
        "2. On every randomized graph, the identical removal protocol as on the real graph: six adaptive strategies, "
        "1% of remaining types per batch with scores recomputed after each batch, up to 50% removed, 30 random-removal "
        "trials averaged into that graph's random-strategy AUC. Curves are normalized by the randomized graph's own "
        "intact flow capacity and reachable pairs.",
        "3. One-sided empirical p-value per strategy, in the direction stated above.",
        "",
        "## Result: flow-capacity AUC (primary)",
        "",
        "| strategy | real AUC | randomized mean ± sd | randomized range | randomized ≤ real | z | p | significant at "
        f"{ALPHA:.4f} |",
        "|---|---|---|---|---|---|---|---|",
    ]

    def row(strategy: str, metric: str) -> str:
        s = summary[strategy][metric]
        return (
            f"| {STRATEGY_LABELS[strategy]} | {s['real']:.4f} | {s['null_mean']:.4f} ± {s['null_sd']:.4f} | "
            f"{s['null_min']:.4f} to {s['null_max']:.4f} | {s['n_at_or_below_real']} / {n_nulls} | {s['z_score']:.1f} | "
            f"{s['p_value']:.4f} | {'yes' if s['significant'] else 'no'} |"
        )

    lines += [row(s, "auc_flow") for s in STRATEGIES]
    lines += [
        "",
        "## Result: reachability AUC (secondary)",
        "",
        "| strategy | real AUC | randomized mean ± sd | randomized range | randomized ≤ real | z | p | below "
        f"{ALPHA:.4f} |",
        "|---|---|---|---|---|---|---|---|",
        *[row(s, "auc_reachability") for s in STRATEGIES],
        "",
        "## Reading",
        "",
    ]
    for strategy in STRATEGIES:
        s = summary[strategy]["auc_flow"]
        if s["significant"]:
            verdict = "H is supported: the real graph is significantly more fragile than its degree-preserving randomizations"
        elif s["real"] > s["null_mean"]:
            verdict = ("H is not supported: the real graph's AUC is above the randomized mean, i.e. the real graph is, if "
                       "anything, more robust than its randomizations under this strategy")
        else:
            verdict = "H is not supported at the corrected threshold"
        lines.append(f"- **{STRATEGY_LABELS[strategy]}**: real {s['real']:.3f} vs randomized {s['null_mean']:.3f} ± "
                     f"{s['null_sd']:.3f} (p = {s['p_value']:.4f}). {verdict}.")
    lines += ["", "![Null distributions](null_distribution.png)", ""]
    (RESULTS / "null_model_validation.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-nulls", type=int, default=N_NULLS)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    graph = load_type_graph()
    sources, targets = load_sensory_motor_sets()
    NULL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    jobs = [(i, s) for i in range(args.n_nulls) for s in STRATEGIES]
    with Pool(args.workers, initializer=_init_worker, initargs=(graph, sources, targets), maxtasksperchild=2) as pool:
        for done, (index, strategy) in enumerate(pool.imap_unordered(run_null_job, jobs), start=1):
            if done % 12 == 0 or done == len(jobs):
                print(f"null jobs: {done}/{len(jobs)} (last: null {index} {strategy})", flush=True)

    scores = collect_scores(args.n_nulls)
    scores.to_csv(SCORES_CSV, index=False, float_format="%.6g")
    real = json.loads((RESULTS / "fragility_scores.json").read_text(encoding="utf-8"))["strategies"]
    summary = summarize(real, scores)
    plot(summary, scores)
    write_report(summary, graph, args.n_nulls)
    (RESULTS / "null_model_summary.json").write_text(
        json.dumps({"n_nulls": args.n_nulls, "alpha": ALPHA, "strategies": summary}, indent=2) + "\n", encoding="utf-8"
    )
    for strategy in STRATEGIES:
        s = summary[strategy]["auc_flow"]
        print(f"{strategy:>15}: real {s['real']:.4f} null {s['null_mean']:.4f}±{s['null_sd']:.4f} p={s['p_value']:.4f}")


if __name__ == "__main__":
    main()
