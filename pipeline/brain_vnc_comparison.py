"""Compare the fragility of the brain-dominant and ventral-nerve-cord-dominant cell-type subgraphs."""

import argparse
import json

import numpy as np
import pandas as pd
from scipy import stats

from pipeline.build_type_graph import load_type_graph
from pipeline.common import DATA, NEURON_ROI_PATH, NEURONS_PATH, RESULTS
from pipeline.connectivity_metrics import flow_capacity, reachable_pairs
from pipeline.critical_thresholds import critical_fraction
from pipeline.figures import INK_SECONDARY, STRATEGY_COLORS, apply_style, plt
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets
from pipeline.removal_strategies import MAX_FRACTION, STRATEGIES, STRATEGY_LABELS
from pipeline.run_percolation import (RANDOM_TRIALS, TARGETED, auc_window, load_all_runs, mean_ci95, run_protocol,
                                      score_runs)

BRAIN_ROIS = ("CentralBrain", "Optic(L)", "Optic(R)")
VNC_ROIS = ("VNC",)
COMPARTMENTS = ("brain", "vnc")
COMPARTMENT_LABELS = {"brain": "brain-dominant", "vnc": "VNC-dominant"}
RUNS_ROOT = DATA / "compartment_runs"


def classify_types(roi_counts: pd.DataFrame, neurons: pd.DataFrame) -> pd.DataFrame:
    """Brain or VNC compartment per type by majority of its synapses (pre + post) in the two compartments.

    Synapses in the neck connective and elsewhere are ignored; types with no synapses in either compartment,
    or exactly half in each, get compartment ``None``.
    """
    counts = roi_counts[roi_counts["roi"].isin(BRAIN_ROIS + VNC_ROIS)].merge(neurons[["bodyId", "type"]], on="bodyId")
    counts = counts.assign(
        synapses=counts["pre"] + counts["post"],
        compartment=np.where(counts["roi"].isin(BRAIN_ROIS), "brain", "vnc"),
    )
    table = counts.pivot_table(index="type", columns="compartment", values="synapses", aggfunc="sum", fill_value=0)
    table = table.reindex(columns=list(COMPARTMENTS), fill_value=0).reindex(sorted(neurons["type"].unique()), fill_value=0)
    total = table["brain"] + table["vnc"]
    share = (table["brain"] / total.where(total > 0)).rename("brain_share")
    compartment = pd.Series(np.select([share > 0.5, share < 0.5], ["brain", "vnc"], default=None), index=table.index)
    return pd.DataFrame(
        {
            "cell_type": table.index,
            "brain_synapses": table["brain"].to_numpy(),
            "vnc_synapses": table["vnc"].to_numpy(),
            "brain_share": share.to_numpy(),
            "compartment": compartment.to_numpy(),
        }
    ).reset_index(drop=True)


def plot(results: dict) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), dpi=200, sharey=True)
    for ax, compartment in zip(axes, COMPARTMENTS):
        r = results[compartment]
        runs, flow0 = r["runs"], r["intact_flow"]
        trials = np.array([runs[("random", t)]["flow"][: auc_window(runs[("random", t)]["fraction_removed"])] / flow0
                           for t in range(RANDOM_TRIALS)])
        x = 100 * runs[("random", 0)]["fraction_removed"][: trials.shape[1]]
        ax.plot(x, trials.mean(axis=0), color=STRATEGY_COLORS["random"], linestyle="--",
                label=f"random (mean of {RANDOM_TRIALS}), AUC {r['scores']['random']['auc_flow']:.3f}")
        for strategy in TARGETED:
            run = runs[(strategy, 0)]
            k = auc_window(run["fraction_removed"])
            ax.plot(100 * run["fraction_removed"][:k], run["flow"][:k] / flow0, color=STRATEGY_COLORS[strategy],
                    label=f"{STRATEGY_LABELS[strategy]}, AUC {r['scores'][strategy]['auc_flow']:.3f}")
        ax.set_title(f"{COMPARTMENT_LABELS[compartment]} subgraph: {r['types']} types, |S| = {r['sensory']}, "
                     f"|M| = {r['motor']}", loc="left")
        ax.set_xlabel("cell types removed (%)")
        ax.set_xlim(0, 100 * MAX_FRACTION)
        ax.set_ylim(0, 1.02)
        ax.legend(loc="upper right", fontsize=7.5)
    axes[0].set_ylabel("flow capacity, fraction of intact")
    fig.text(0.01, 0.01, "Same adaptive protocol as the whole-CNS graph, applied to each induced subgraph separately.",
             fontsize=8, color=INK_SECONDARY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(RESULTS / "brain_vnc_curves.png")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--from-results", action="store_true",
                        help="redraw the figure from results/brain_vnc_comparison.json and the cached runs without "
                             "rerunning percolation")
    args = parser.parse_args()

    if args.from_results:
        summary = json.loads((RESULTS / "brain_vnc_comparison.json").read_text(encoding="utf-8"))
        plot({c: {**summary["compartments"][c], "runs": load_all_runs(RUNS_ROOT / c)} for c in COMPARTMENTS})
        return

    graph = load_type_graph()
    sources, targets = load_sensory_motor_sets()
    classes = classify_types(pd.read_parquet(NEURON_ROI_PATH), pd.read_parquet(NEURONS_PATH))
    classes.to_csv(RESULTS / "type_compartments.csv", index=False, float_format="%.4f")

    results = {}
    for compartment in COMPARTMENTS:
        members = set(classes.loc[classes["compartment"] == compartment, "cell_type"])
        sub = graph.induced_subgraph([v.index for v in graph.vs if v["name"] in members])
        sub_sources = [s for s in sources if s in members]
        sub_targets = [t for t in targets if t in members]
        intact_flow = flow_capacity(sub, sub_sources, sub_targets)
        intact_pairs = reachable_pairs(sub, sub_sources, sub_targets)
        runs = run_protocol(sub, sub_sources, sub_targets, RUNS_ROOT / compartment, args.workers)
        scores = score_runs(runs, intact_flow, intact_pairs)
        f_c = {s: critical_fraction(runs[(s, 0)]["fraction_removed"], runs[(s, 0)]["flow"])[0] for s in TARGETED}
        f_c["random"] = mean_ci95([critical_fraction(runs[("random", t)]["fraction_removed"], runs[("random", t)]["flow"])[0]
                                   for t in range(RANDOM_TRIALS)])[0]
        results[compartment] = {
            "types": sub.vcount(), "edges": sub.ecount(), "sensory": len(sub_sources), "motor": len(sub_targets),
            "intact_flow": intact_flow, "intact_pairs": intact_pairs, "scores": scores, "f_c": f_c, "runs": runs,
        }

    welch = {}
    for key in ("auc_flow", "auc_reachability"):
        t, p = stats.ttest_ind(results["brain"]["scores"]["random"][f"{key}_trials"],
                               results["vnc"]["scores"]["random"][f"{key}_trials"], equal_var=False)
        welch[key] = {"t": float(t), "p_value": float(p)}
    plot(results)

    unclassified = classes["compartment"].isna()
    counts = classes["compartment"].value_counts()
    motor_split = classes[classes["cell_type"].isin(targets)]["compartment"].value_counts(dropna=False)
    summary = {
        "rule": "brain-dominant if more than half of the type's synapses (pre + post, summed over its neurons) in "
                "CentralBrain, Optic(L), Optic(R) or VNC lie in the first three; VNC-dominant if less than half",
        "unclassified_types": int(unclassified.sum()),
        "compartments": {c: {k: v for k, v in r.items() if k != "runs"} for c, r in results.items()},
        "welch_random_trials": welch,
        "descending_motor_types_by_compartment": {str(k): int(v) for k, v in motor_split.items()},
    }
    (RESULTS / "brain_vnc_comparison.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    b, v = results["brain"], results["vnc"]
    lines = [
        "# Brain versus ventral nerve cord",
        "",
        "## Classification rule",
        "",
        "For every cell type, the synapses of all its neurons (presynaptic plus postsynaptic sites) are counted in two "
        "compartments of the neuPrint ROI hierarchy: the brain (`CentralBrain`, `Optic(L)`, `Optic(R)`) and the "
        "ventral nerve cord (`VNC`). A type is **brain-dominant** if more than half of those synapses are in the "
        "brain and **VNC-dominant** if more than half are in the VNC. Synapses in the neck connective (`CV`) are not "
        f"counted. {int(unclassified.sum())} types with no synapses in either compartment, or exactly half in each, "
        "are left out. Per-type counts: `results/type_compartments.csv`.",
        "",
        f"Brain-dominant: {int(counts.get('brain', 0))} types. VNC-dominant: {int(counts.get('vnc', 0))} types. "
        "Each subgraph is the induced subgraph of the whole-CNS type graph (edges keep the whole-CNS 1% input "
        "threshold), with its own sensory set S and descending/motor set M: the members of S and M whose types fall in "
        "that compartment. Descending and motor types by compartment: "
        + ", ".join(f"{k}: {int(n)}" for k, n in motor_split.items()) + ".",
        "",
        "| | brain-dominant | VNC-dominant |",
        "|---|---|---|",
        f"| cell types | {b['types']} | {v['types']} |",
        f"| edges | {b['edges']} | {v['edges']} |",
        f"| sensory types (S) | {b['sensory']} | {v['sensory']} |",
        f"| descending/motor types (M) | {b['motor']} | {v['motor']} |",
        f"| intact flow capacity | {b['intact_flow']} | {v['intact_flow']} |",
        f"| intact reachable S-M pairs | {b['intact_pairs']} of {b['sensory'] * b['motor']} | "
        f"{v['intact_pairs']} of {v['sensory'] * v['motor']} |",
        "",
        "## Fragility",
        "",
        "Same protocol as the whole CNS: six adaptive strategies, 1% of remaining types per batch, AUC over the first "
        f"50% of removals, {RANDOM_TRIALS} random trials. No direction was hypothesized; the comparison is descriptive.",
        "",
        "| strategy | brain AUC (flow) | VNC AUC (flow) | brain AUC (reachability) | VNC AUC (reachability) | brain f_c | VNC f_c |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in STRATEGIES:
        def cell(r: dict, key: str) -> str:
            value = r["scores"][s][key]
            if s == "random":
                lo, hi = r["scores"][s][f"{key}_ci95"]
                return f"{value:.3f} ({lo:.3f} to {hi:.3f})"
            return f"{value:.3f}"
        lines.append(f"| {STRATEGY_LABELS[s]} | {cell(b, 'auc_flow')} | {cell(v, 'auc_flow')} | "
                     f"{cell(b, 'auc_reachability')} | {cell(v, 'auc_reachability')} | {b['f_c'][s]:.3f} | {v['f_c'][s]:.3f} |")
    lines += [
        "",
        f"Random removal, brain versus VNC (Welch two-sided t-test over {RANDOM_TRIALS} trials each): flow AUC "
        f"t = {welch['auc_flow']['t']:.2f}, p = {welch['auc_flow']['p_value']:.2g}; reachability AUC "
        f"t = {welch['auc_reachability']['t']:.2f}, p = {welch['auc_reachability']['p_value']:.2g}.",
        "",
        "Caveat: the two subgraphs differ in size, density and in the composition of S and M, and the targeted "
        "strategies are single deterministic runs, so differences in AUC describe these two graphs rather than "
        "estimating a population effect.",
        "",
        "![Brain and VNC percolation curves](brain_vnc_curves.png)",
        "",
    ]
    (RESULTS / "brain_vnc_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
