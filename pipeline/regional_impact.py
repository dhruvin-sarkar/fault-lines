"""Remove every cell type anchored in a neuropil and measure the loss of sensory-to-motor flow capacity."""

import argparse
from multiprocessing import Pool

import igraph as ig
import numpy as np
import pandas as pd

from pipeline.build_type_graph import load_type_graph
from pipeline.common import NEURON_ROI_PATH, NEURONS_PATH, RESULTS, SEED
from pipeline.connectivity_metrics import flow_capacity
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets

AGGREGATE_ROIS = ("CentralBrain", "Optic(L)", "Optic(R)", "VNC", "CV")
RANDOM_DRAWS = 200
REGIONAL_IMPACT_CSV = RESULTS / "regional_impact.csv"


def anchor_neuropils(roi_counts: pd.DataFrame, neurons: pd.DataFrame) -> pd.Series:
    """Neuropil holding the largest share of each cell type's synapses (pre + post), indexed by type.

    Aggregate compartments and unassigned remainders are excluded; ties go to the alphabetically first neuropil.
    """
    counts = roi_counts[~roi_counts["roi"].isin(AGGREGATE_ROIS) & ~roi_counts["roi"].str.contains("unspecified")]
    merged = counts.merge(neurons[["bodyId", "type"]].dropna(), on="bodyId")
    merged["synapses"] = merged["pre"] + merged["post"]
    per_type = merged.groupby(["type", "roi"], as_index=False)["synapses"].sum()
    per_type = per_type[per_type["synapses"] > 0].sort_values(["type", "synapses", "roi"], ascending=[True, False, True])
    return per_type.drop_duplicates("type").set_index("type")["roi"]


def upper_p_value(null: np.ndarray, observed: float) -> float:
    """One-sided empirical p-value that ``observed`` exceeds the null draws."""
    return float((1 + np.sum(null >= observed)) / (1 + len(null)))


_WORKER: dict = {}


def _init_worker(graph: ig.Graph, sources: list[str], targets: list[str]) -> None:
    _WORKER.update(graph=graph, sources=sources, targets=targets)


def flow_without(vertices: list[int]) -> int:
    reduced = _WORKER["graph"].copy()
    reduced.delete_vertices(vertices)
    return flow_capacity(reduced, _WORKER["sources"], _WORKER["targets"])


def load_regional_impact() -> pd.DataFrame:
    return pd.read_csv(REGIONAL_IMPACT_CSV)


def report_lines(table: pd.DataFrame, draws: int, alpha: float = 0.05) -> list[str]:
    """Lines of ``regional_impact.md``, which documents ``regional_impact.csv``.

    Parameters: ``table``, the regional impact table; ``draws``, random sets per neuropil size; ``alpha``, the
    family-wise level used to state the Bonferroni threshold.
    Returns the markdown lines.
    """
    tests = len(table)
    floor = 1 / (1 + draws)
    bonferroni = alpha / tests
    return [
        "# Regional impact",
        "",
        "Each cell type is anchored to the neuropil holding the largest share of its synapses (pre plus post), "
        "excluding aggregate compartments and unassigned remainders. For every neuropil, all types anchored in it are "
        "removed together and the loss of sensory-to-motor flow capacity is compared with random sets of the same "
        f"number of types. The table is `regional_impact.csv`, one row per neuropil ({tests} neuropils).",
        "",
        "| column | meaning |",
        "|---|---|",
        "| neuropil | anchor neuropil |",
        "| intact_flow | flow capacity of the intact graph |",
        "| n_types | cell types anchored in the neuropil |",
        "| n_sensory, n_motor | of those, types in the sensory set and in the descending or motor set |",
        "| flow_after | flow capacity with every anchored type removed |",
        "| flow_drop | share of intact flow capacity lost |",
        f"| random_mean, random_sd | mean and standard deviation of the share lost over {draws} same-size random sets |",
        "| excess_over_random | flow_drop minus random_mean |",
        f"| p_value | one-sided empirical p = (1 + k) / (1 + {draws}), k = random sets losing at least as much flow |",
        "",
        f"With {draws} random sets the smallest attainable p is 1/{draws + 1} = {floor:.4f}. A Bonferroni correction "
        f"across the {tests} neuropils requires p < {alpha}/{tests} = {bonferroni:.5f}, "
        + ("which no neuropil can reach with this number of draws. " if floor >= bonferroni else
           "which the smallest attainable p can reach. ")
        + f"{int((table['p_value'] < alpha).sum())} neuropils have p < {alpha} and "
        f"{int(np.isclose(table['p_value'], floor).sum())} reach the minimum, but these p-values are uncorrected and "
        "serve to rank regions, not to establish significance for any one of them. This analysis is exploratory.",
        "",
    ]


def write_report(table: pd.DataFrame, draws: int) -> None:
    """Write ``regional_impact.md`` next to the CSV and print it."""
    lines = report_lines(table, draws)
    (RESULTS / "regional_impact.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draws", type=int, default=RANDOM_DRAWS)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--from-csv", action="store_true",
                        help="rebuild regional_impact.md from results/regional_impact.csv instead of recomputing")
    args = parser.parse_args()

    if args.from_csv:
        write_report(load_regional_impact(), args.draws)
        return

    graph = load_type_graph()
    sources, targets = load_sensory_motor_sets()
    intact = flow_capacity(graph, sources, targets)
    anchors = anchor_neuropils(pd.read_parquet(NEURON_ROI_PATH), pd.read_parquet(NEURONS_PATH))
    index = {name: i for i, name in enumerate(graph.vs["name"])}
    members = {roi: [index[t] for t in types if t in index] for roi, types in anchors.groupby(anchors).groups.items()}
    members = {roi: v for roi, v in members.items() if v}
    sensory = {index[s] for s in sources if s in index}
    motor = {index[t] for t in targets if t in index}

    rng = np.random.default_rng(SEED)
    sizes = sorted({len(v) for v in members.values()})
    draws = [sorted(rng.choice(graph.vcount(), size=k, replace=False).tolist()) for k in sizes for _ in range(args.draws)]
    with Pool(args.workers, initializer=_init_worker, initargs=(graph, sources, targets)) as pool:
        flows = pool.map(flow_without, list(members.values()) + draws, chunksize=16)
    region_flow = dict(zip(members, flows[: len(members)]))
    random_flows = np.asarray(flows[len(members) :]).reshape(len(sizes), args.draws)
    random_drop = {k: 1 - random_flows[i] / intact for i, k in enumerate(sizes)}

    rows = []
    for roi, vertices in members.items():
        drop = 1 - region_flow[roi] / intact
        null = random_drop[len(vertices)]
        rows.append({
            "neuropil": roi, "intact_flow": intact, "n_types": len(vertices),
            "n_sensory": len(sensory.intersection(vertices)), "n_motor": len(motor.intersection(vertices)),
            "flow_after": region_flow[roi], "flow_drop": drop, "random_mean": float(null.mean()),
            "random_sd": float(null.std(ddof=1)), "excess_over_random": drop - float(null.mean()),
            "p_value": upper_p_value(null, drop),
        })
    table = pd.DataFrame(rows).sort_values("flow_drop", ascending=False)
    table.to_csv(REGIONAL_IMPACT_CSV, index=False, float_format="%.5g")
    write_report(table, args.draws)
    print(f"{len(table)} neuropils, {int(table['n_types'].sum())} of {graph.vcount()} types anchored")
    print(table.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
