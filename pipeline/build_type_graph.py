"""Fetch neuron-level connectivity and collapse it into weighted, directed cell-type graphs."""

import time

import igraph as ig
import pandas as pd
import requests
from neuprint import NeuronCriteria as NC, NotNull, fetch_adjacencies, fetch_neurons

from pipeline.common import (
    DATA,
    DATASET,
    NEURON_ROI_PATH,
    NEURONS_PATH,
    TYPE_EDGES_PATH,
    TYPE_NODES_PATH,
    get_client,
)

CHUNK = 10_000
NEURON_COLUMNS = ["bodyId", "type", "instance", "superclass", "class", "somaSide", "rootSide", "pre", "post"]
COMPARTMENT_ROIS = ("CentralBrain", "Optic(L)", "Optic(R)", "VNC", "CV")
SIDE_NODES_PATH = DATA / "side_nodes.parquet"
SIDE_EDGES_PATH = DATA / "side_edges.parquet"
# A type-to-type connection enters the graph only if it supplies at least this fraction of the
# postsynaptic type's input synapses (from all typed neurons, within-type synapses included).
MIN_INPUT_FRACTION = 0.01


def hemisphere(neurons: pd.DataFrame) -> pd.Series:
    """Hemisphere per neuron: ``somaSide`` when it is L/R/M, otherwise ``rootSide`` when L/R, else ``unknown``."""
    soma = neurons["somaSide"].where(neurons["somaSide"].isin(["L", "R", "M"]))
    root = neurons["rootSide"].where(neurons["rootSide"].isin(["L", "R"]))
    return soma.fillna(root).fillna("unknown")


def aggregate_type_edges(connections: pd.DataFrame, body_labels: pd.Series) -> pd.DataFrame:
    """Sum neuron-to-neuron synapse counts into node-to-node edges.

    Args:
        connections: columns ``bodyId_pre``, ``bodyId_post``, ``weight``.
        body_labels: node label (cell type, or type and hemisphere) indexed by bodyId.

    Returns:
        Columns ``type_pre``, ``type_post``, ``weight`` (summed synapses) and
        ``n_connections`` (number of contributing neuron pairs).
    """
    edges = connections.assign(
        type_pre=connections["bodyId_pre"].map(body_labels),
        type_post=connections["bodyId_post"].map(body_labels),
    )
    missing = edges[["type_pre", "type_post"]].isna().any(axis=1)
    if missing.any():
        raise ValueError(f"{int(missing.sum())} connections reference bodies without a cell type")
    return edges.groupby(["type_pre", "type_post"], as_index=False, sort=True).agg(
        weight=("weight", "sum"), n_connections=("weight", "size")
    )


def combine_type_edges(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge edge tables computed on disjoint sets of source neurons."""
    return pd.concat(parts, ignore_index=True).groupby(["type_pre", "type_post"], as_index=False, sort=True)[
        ["weight", "n_connections"]
    ].sum()


def summarize_nodes(neurons: pd.DataFrame, label: str = "type") -> pd.DataFrame:
    """One row per node label: neuron count, majority superclass, synapse totals."""

    def mode(series: pd.Series) -> str:
        values = series.dropna()
        return values.mode().sort_values().iloc[0] if len(values) else "unannotated"

    return (
        neurons.groupby(label, sort=True)
        .agg(
            n_neurons=("bodyId", "size"),
            superclass=("superclass", mode),
            total_pre=("pre", "sum"),
            total_post=("post", "sum"),
        )
        .reset_index()
        .rename(columns={label: "cell_type"})
    )


def build_graph(
    nodes: pd.DataFrame, edges: pd.DataFrame, min_input_fraction: float = MIN_INPUT_FRACTION
) -> ig.Graph:
    """Build a directed igraph graph with one vertex per node label.

    Self-loops and connections below ``min_input_fraction`` of the target's input are dropped.
    Vertex attributes: ``name`` and the node-table columns. Edge attributes: ``weight``
    (synapses) and ``input_fraction``.
    """
    unknown = set(edges["type_pre"]).union(edges["type_post"]) - set(nodes["cell_type"])
    if unknown:
        raise ValueError(f"{len(unknown)} edge endpoints are not in the node table")
    synapses_in = edges.groupby("type_post")["weight"].sum()
    input_fraction = edges["weight"] / edges["type_post"].map(synapses_in)
    kept = edges.assign(input_fraction=input_fraction)
    kept = kept[(kept["type_pre"] != kept["type_post"]) & (kept["input_fraction"] >= min_input_fraction)]

    graph = ig.Graph(directed=True)
    graph.add_vertices(nodes["cell_type"].tolist())
    graph.add_edges(
        list(zip(kept["type_pre"], kept["type_post"])),
        attributes={"weight": kept["weight"].tolist(), "input_fraction": kept["input_fraction"].tolist()},
    )
    for column in nodes.columns.drop("cell_type"):
        graph.vs[column] = nodes[column].tolist()
    return graph


def load_type_graph(min_input_fraction: float = MIN_INPUT_FRACTION) -> ig.Graph:
    """Load the cached cell-type graph built by :func:`main`."""
    return build_graph(pd.read_parquet(TYPE_NODES_PATH), pd.read_parquet(TYPE_EDGES_PATH), min_input_fraction)


def load_side_graph(min_input_fraction: float = MIN_INPUT_FRACTION) -> ig.Graph:
    """Load the cached graph whose vertices are (cell type, hemisphere) pairs, named ``type|side``."""
    return build_graph(pd.read_parquet(SIDE_NODES_PATH), pd.read_parquet(SIDE_EDGES_PATH), min_input_fraction)


def side_labels(neurons: pd.DataFrame) -> pd.Series:
    return neurons["type"] + "|" + neurons["side"]


def with_retries(fetch, *args, attempts: int = 5, **kwargs):
    """Call a neuPrint fetch, retrying only on dropped connections and timeouts."""
    for attempt in range(1, attempts + 1):
        try:
            return fetch(*args, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as error:
            if attempt == attempts:
                raise
            print(f"{type(error).__name__}; retry {attempt}/{attempts - 1}", flush=True)
            time.sleep(30 * attempt)


def fetch_neuron_tables(client, roi_names: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    cache = DATA / "neuron_chunks"
    cache.mkdir(parents=True, exist_ok=True)
    body_ids = with_retries(
        client.fetch_custom, "MATCH (n:Neuron) WHERE n.type IS NOT NULL RETURN n.bodyId AS bodyId ORDER BY bodyId"
    )["bodyId"].tolist()
    neuron_parts, roi_parts = [], []
    for i, start in enumerate(range(0, len(body_ids), CHUNK)):
        neuron_path, roi_path = cache / f"neurons_{i:03d}.parquet", cache / f"rois_{i:03d}.parquet"
        if not (neuron_path.exists() and roi_path.exists()):
            neurons, roi_counts = with_retries(fetch_neurons, NC(bodyId=body_ids[start : start + CHUNK]))
            neurons.reindex(columns=NEURON_COLUMNS).to_parquet(neuron_path, index=False)
            roi_counts.loc[roi_counts["roi"].isin(roi_names), ["bodyId", "roi", "pre", "post"]].to_parquet(
                roi_path, index=False
            )
        neuron_parts.append(pd.read_parquet(neuron_path))
        roi_parts.append(pd.read_parquet(roi_path))
        print(f"neurons: {min(start + CHUNK, len(body_ids))}/{len(body_ids)}", flush=True)
    neurons = pd.concat(neuron_parts, ignore_index=True)
    if len(neurons) != len(body_ids) or neurons["type"].isna().any():
        raise RuntimeError(f"Expected {len(body_ids)} typed neurons, fetched {len(neurons)}")
    neurons["side"] = hemisphere(neurons)
    return neurons, pd.concat(roi_parts, ignore_index=True)


def fetch_edges(neurons: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Type-level and (type, hemisphere)-level edge tables, cached per chunk of source neurons."""
    cache = DATA / "adjacency_chunks"
    cache.mkdir(parents=True, exist_ok=True)
    by_body = neurons.set_index("bodyId")
    types, sides = by_body["type"], side_labels(by_body)
    body_ids = by_body.index.tolist()
    type_parts, side_parts = [], []
    for i, start in enumerate(range(0, len(body_ids), CHUNK)):
        type_path, side_path = cache / f"type_{i:03d}.parquet", cache / f"side_{i:03d}.parquet"
        if not (type_path.exists() and side_path.exists()):
            _, conn = with_retries(
                fetch_adjacencies,
                NC(bodyId=body_ids[start : start + CHUNK]),
                NC(type=NotNull),
                omit_rois=True,
                weight_props=["weight"],
                batch_size=200,
                threads=4,
            )
            aggregate_type_edges(conn, types).to_parquet(type_path, index=False)
            aggregate_type_edges(conn, sides).to_parquet(side_path, index=False)
        type_parts.append(pd.read_parquet(type_path))
        side_parts.append(pd.read_parquet(side_path))
        print(f"adjacency: {min(start + CHUNK, len(body_ids))}/{len(body_ids)}", flush=True)
    return combine_type_edges(type_parts), combine_type_edges(side_parts)


def main() -> None:
    client = get_client()
    DATA.mkdir(exist_ok=True)
    if NEURONS_PATH.exists() and NEURON_ROI_PATH.exists():
        neurons = pd.read_parquet(NEURONS_PATH)
    else:
        roi_names = set(client.fetch_datasets()[DATASET]["superLevelROIs"]) | set(COMPARTMENT_ROIS)
        neurons, roi_counts = fetch_neuron_tables(client, roi_names)
        neurons.to_parquet(NEURONS_PATH, index=False)
        roi_counts.to_parquet(NEURON_ROI_PATH, index=False)

    summarize_nodes(neurons).to_parquet(TYPE_NODES_PATH, index=False)
    summarize_nodes(neurons.assign(type_side=side_labels(neurons)), label="type_side").to_parquet(
        SIDE_NODES_PATH, index=False
    )
    type_edges, side_edges = fetch_edges(neurons)
    type_edges.to_parquet(TYPE_EDGES_PATH, index=False)
    side_edges.to_parquet(SIDE_EDGES_PATH, index=False)

    graph = load_type_graph()
    print(
        f"Type graph: {graph.vcount()} types, {graph.ecount()} edges; "
        f"{int(type_edges['weight'].sum())} synapses between typed neurons in {len(type_edges)} type pairs "
        f"({int(type_edges.loc[type_edges['type_pre'] == type_edges['type_post'], 'weight'].sum())} within-type)"
    )
    side = load_side_graph()
    print(f"Side-resolved graph: {side.vcount()} nodes, {side.ecount()} edges")


if __name__ == "__main__":
    main()
