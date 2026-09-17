"""Describe the structure the attacks act on: degree tails, core layers, and the cost of losing a whole class."""

import argparse
import json
import warnings
from multiprocessing import Pool

import igraph as ig
import numpy as np
import pandas as pd
import powerlaw
from scipy import stats

from pipeline.build_type_graph import load_type_graph
from pipeline.common import RESULTS, SEED
from pipeline.connectivity_metrics import flow_capacity
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets
from pipeline.regional_impact import upper_p_value
from pipeline.removal_strategies import intact_scores

RANDOM_DRAWS = 200
MIN_SUPERCLASS = 20
ALTERNATIVES = ("exponential", "lognormal", "truncated_power_law")


def degree_tail(values: np.ndarray, name: str) -> dict:
    """Discrete power-law fit of a degree sequence, with the alternatives Clauset, Shalizi and Newman recommend."""
    positive = values[values > 0]
    ccdf = ccdf_points(positive)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = powerlaw.Fit(positive, discrete=True, verbose=False)
        comparisons = {}
        for alternative in ALTERNATIVES:
            ratio, p = fit.distribution_compare("power_law", alternative, normalized_ratio=True)
            comparisons[alternative] = {"loglikelihood_ratio": float(ratio), "p_value": float(p)}
    return {
        "measure": name, "n": int(len(positive)), "mean": float(positive.mean()), "median": float(np.median(positive)),
        "max": int(positive.max()), "alpha": float(fit.power_law.alpha), "xmin": float(fit.xmin),
        "n_tail": int(fit.n_tail), "ks_distance": float(fit.power_law.D), "comparisons": comparisons, "ccdf": ccdf,
    }


def ccdf_points(values: np.ndarray, points: int = 120) -> dict:
    """Complementary CDF P(X >= x) of the positive values, sampled at log-spaced x for plotting."""
    positive = np.sort(values[values > 0])
    grid = np.unique(np.round(np.geomspace(positive[0], positive[-1], points)))
    survival = 1 - np.searchsorted(positive, grid, side="left") / len(positive)
    return {"x": grid.tolist(), "p": survival.tolist()}


def core_layers(graph: ig.Graph) -> pd.DataFrame:
    """Coreness of every cell type in the undirected projection of the graph."""
    undirected = graph.copy()
    undirected.to_undirected(combine_edges="sum")
    undirected.simplify(combine_edges="sum")
    return pd.DataFrame({"cell_type": graph.vs["name"], "coreness": undirected.coreness()})


_WORKER: dict = {}


def _init_worker(graph: ig.Graph, sources: list[str], targets: list[str]) -> None:
    _WORKER.update(graph=graph, sources=sources, targets=targets)


def flow_without(vertices: list[int]) -> int:
    reduced = _WORKER["graph"].copy()
    reduced.delete_vertices(vertices)
    return flow_capacity(reduced, _WORKER["sources"], _WORKER["targets"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draws", type=int, default=RANDOM_DRAWS)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    graph = load_type_graph()
    sources, targets = load_sensory_motor_sets()
    intact = flow_capacity(graph, sources, targets)
    scores = intact_scores(graph, sources, targets, include_betweenness=False)
    scores["superclass"] = graph.vs["superclass"]
    scores["n_neurons"] = graph.vs["n_neurons"]
    scores = scores.merge(core_layers(graph), on="cell_type")

    tails = [
        degree_tail(scores["out_degree"].to_numpy(), "out-degree (partner types)"),
        degree_tail(scores["in_degree"].to_numpy(), "in-degree (partner types)"),
        degree_tail(scores["out_strength"].to_numpy(), "out-strength (synapses)"),
    ]

    members = {name: list(rows.index) for name, rows in scores.groupby("superclass") if len(rows) >= MIN_SUPERCLASS}
    rng = np.random.default_rng(SEED + 7)
    sizes = sorted({len(v) for v in members.values()})
    draws = [sorted(rng.choice(graph.vcount(), size=k, replace=False).tolist()) for k in sizes for _ in range(args.draws)]
    with Pool(args.workers, initializer=_init_worker, initargs=(graph, sources, targets)) as pool:
        flows = pool.map(flow_without, list(members.values()) + draws, chunksize=8)
    class_flow = dict(zip(members, flows[: len(members)]))
    random_flows = np.asarray(flows[len(members) :]).reshape(len(sizes), args.draws)
    random_drop = {k: 1 - random_flows[i] / intact for i, k in enumerate(sizes)}

    rows = []
    for superclass, vertices in members.items():
        drop = 1 - class_flow[superclass] / intact
        null = random_drop[len(vertices)]
        rows.append({"superclass": superclass, "types": len(vertices),
                     "neurons": int(scores.loc[vertices, "n_neurons"].sum()),
                     "flow_after": class_flow[superclass], "flow_drop": drop,
                     "random_mean": float(null.mean()), "excess_over_random": drop - float(null.mean()),
                     "p_value": upper_p_value(null, drop)})
    classes = pd.DataFrame(rows).sort_values("flow_drop", ascending=False)
    classes.to_csv(RESULTS / "superclass_impact.csv", index=False, float_format="%.5g")

    spearman = stats.spearmanr(scores["coreness"], scores["out_strength"])
    summary = {
        "intact_flow": intact, "types": graph.vcount(), "edges": graph.ecount(), "degree_tails": tails,
        "max_coreness": int(scores["coreness"].max()),
        "types_in_deepest_core": int((scores["coreness"] == scores["coreness"].max()).sum()),
        "coreness_counts": {int(k): int(v) for k, v in scores["coreness"].value_counts().sort_index().items()},
        "coreness_vs_out_strength": {"spearman_rho": float(spearman.statistic), "p_value": float(spearman.pvalue)},
        "superclass_impact": classes.to_dict("records"),
        "superclass_threshold": MIN_SUPERCLASS, "random_draws": args.draws,
    }
    (RESULTS / "structure_profile.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    def tail_row(tail: dict) -> str:
        favored = [a for a, c in tail["comparisons"].items() if c["loglikelihood_ratio"] < 0 and c["p_value"] < 0.1]
        verdict = f"favors {', '.join(a.replace('_', ' ') for a in favored)}" if favored else "no alternative preferred"
        return (f"| {tail['measure']} | {tail['n']:,} | {tail['median']:.0f} | {tail['max']:,} | {tail['alpha']:.2f} | "
                f"{tail['xmin']:.0f} | {tail['n_tail']:,} | {verdict} |")

    lines = [
        "# Structure the attacks act on",
        "",
        "Three descriptive measurements on the intact cell-type graph that frame the removal results. A heavy "
        "degree tail is the classic reason targeted removal outperforms random removal; the core decomposition shows "
        "how much of the graph is densely interconnected; and removing whole superclasses tests whether routing "
        "depends on particular classes of neuron more than on their size.",
        "",
        "## Degree tails",
        "",
        "Maximum-likelihood power-law fits with x_min chosen by the Kolmogorov-Smirnov criterion (Clauset, Shalizi "
        "and Newman 2009). A fitted exponent alone is not evidence of a scale-free network, so the last column "
        "reports whether a lognormal, exponential or truncated power law fits better.",
        "",
        "| measure | types | median | maximum | exponent | x_min | types in tail | likelihood ratio |",
        "|---|---|---|---|---|---|---|---|",
        *[tail_row(tail) for tail in tails],
        "",
        "## Core layers",
        "",
        f"The k-core decomposition of the undirected projection reaches k = {summary['max_coreness']}, and "
        f"{summary['types_in_deepest_core']:,} of {graph.vcount():,} cell types sit in that deepest core. Coreness and out-strength rise "
        f"together (Spearman rho = {summary['coreness_vs_out_strength']['spearman_rho']:.2f}, "
        f"p = {summary['coreness_vs_out_strength']['p_value']:.2g}).",
        "",
        "## Losing a whole class",
        "",
        f"Every cell type of one superclass removed at once, for the {len(classes)} superclasses with at least "
        f"{MIN_SUPERCLASS} types. The null is {args.draws} random sets of the same size, and p = (1 + k) / "
        f"(1 + {args.draws}), where k is the number of those random sets that lose at least as much flow, so the "
        f"smallest attainable p is 1/{args.draws + 1} = {1 / (args.draws + 1):.3f}.",
        "",
        "| superclass | types | neurons | flow lost | same-size random | p |",
        "|---|---|---|---|---|---|",
        *[f"| {r.superclass} | {r.types:,} | {r.neurons:,} | {100 * r.flow_drop:.1f}% | "
          f"{100 * r.random_mean:.1f}% | {r.p_value:.3f} |" for r in classes.itertuples()],
        "",
    ]
    (RESULTS / "structure_profile.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:24]))


if __name__ == "__main__":
    main()
