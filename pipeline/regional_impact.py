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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draws", type=int, default=RANDOM_DRAWS)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

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
    print(f"{len(table)} neuropils, {int(table['n_types'].sum())} of {graph.vcount()} types anchored")
    print(table.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
