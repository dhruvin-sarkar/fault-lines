"""Remove each cell type on its own and record the change in sensory-to-motor connectivity."""

import argparse
from multiprocessing import Pool

import igraph as ig
import numpy as np
import pandas as pd

from pipeline.build_type_graph import load_type_graph
from pipeline.common import DATA, RESULTS
from pipeline.connectivity_metrics import flow_capacity, present_indices
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets

SINGLE_PATH = DATA / "single_removal.parquet"
LOST_PAIRS_PATH = DATA / "lost_pairs.parquet"


def reachable_matrix(graph: ig.Graph, sources: list[str], targets: list[str]) -> np.ndarray:
    """Boolean |sources| x |targets| matrix of directed reachability; absent names give all-False rows or columns."""
    names = set(graph.vs["name"])
    matrix = np.zeros((len(sources), len(targets)), dtype=bool)
    rows = [i for i, s in enumerate(sources) if s in names]
    cols = [j for j, t in enumerate(targets) if t in names]
    if rows and cols:
        distances = graph.distances(
            source=present_indices(graph, [sources[i] for i in rows]),
            target=present_indices(graph, [targets[j] for j in cols]),
            mode="out",
        )
        matrix[np.ix_(rows, cols)] = np.isfinite(np.asarray(distances))
    return matrix


_WORKER: dict = {}


def _init_worker(graph: ig.Graph, sources: list[str], targets: list[str], intact: np.ndarray, intact_flow: int) -> None:
    _WORKER.update(graph=graph, sources=sources, targets=targets, intact=intact, intact_flow=intact_flow)


def remove_one(index: int) -> tuple[dict, np.ndarray]:
    graph, sources, targets = _WORKER["graph"], _WORKER["sources"], _WORKER["targets"]
    reduced = graph.copy()
    name = graph.vs[index]["name"]
    reduced.delete_vertices([index])
    after = reachable_matrix(reduced, sources, targets)
    lost = np.argwhere(_WORKER["intact"] & ~after)
    flow = flow_capacity(reduced, sources, targets)
    row = {
        "cell_type": name,
        "flow": flow,
        "flow_drop": _WORKER["intact_flow"] - flow,
        "reachable_pairs": int(after.sum()),
        "pairs_lost": int(len(lost)),
    }
    return row, lost


def load_single_removal() -> pd.DataFrame:
    return pd.read_parquet(SINGLE_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    graph = load_type_graph()
    sources, targets = load_sensory_motor_sets()
    intact = reachable_matrix(graph, sources, targets)
    intact_flow = flow_capacity(graph, sources, targets)
    rows, lost_parts = [], []
    with Pool(args.workers, initializer=_init_worker, initargs=(graph, sources, targets, intact, intact_flow)) as pool:
        for i, (row, lost) in enumerate(pool.imap(remove_one, range(graph.vcount()), chunksize=16), start=1):
            rows.append(row)
            if len(lost):
                lost_parts.append(pd.DataFrame({
                    "cell_type": row["cell_type"],
                    "sensory": np.asarray(sources)[lost[:, 0]],
                    "motor": np.asarray(targets)[lost[:, 1]],
                }))
            if i % 500 == 0:
                print(f"single removals: {i}/{graph.vcount()}", flush=True)

    table = pd.DataFrame(rows)
    table["intact_flow"] = intact_flow
    table["intact_reachable_pairs"] = int(intact.sum())
    table.to_parquet(SINGLE_PATH, index=False)
    lost_pairs = pd.concat(lost_parts, ignore_index=True) if lost_parts else pd.DataFrame(columns=["cell_type", "sensory", "motor"])
    lost_pairs.to_parquet(LOST_PAIRS_PATH, index=False)
    table.sort_values(["flow_drop", "pairs_lost"], ascending=False).to_csv(
        RESULTS / "single_removal_impacts.csv", index=False
    )
    print(
        f"intact flow {intact_flow}; {int((table['flow_drop'] > 0).sum())} types reduce flow when removed alone, "
        f"{int((table['pairs_lost'] > 0).sum())} disconnect at least one sensory-motor pair; "
        f"{len(lost_pairs)} lost pairs in total"
    )


if __name__ == "__main__":
    main()
