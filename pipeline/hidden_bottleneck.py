"""Find cell types that look unimportant by connection count but carry a large share of sensory-to-motor routes."""

import json
import sys

import igraph as ig
import numpy as np
import pandas as pd

from pipeline.build_type_graph import load_type_graph
from pipeline.common import RESULTS
from pipeline.connectivity_metrics import flow_capacity, present_indices
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets
from pipeline.removal_strategies import intact_scores

LOW_PERCENTILE = 50.0
HIGH_PERCENTILE = 99.0
TOP_PARTNERS = 5


def percentile_ranks(values: pd.Series) -> pd.Series:
    """Mid-rank percentile of each value among all values."""
    return 100 * (values.rank(method="average") - 0.5) / len(values)


def find_candidates(scores: pd.DataFrame) -> pd.DataFrame:
    """Bottom half by total degree and by PageRank, top 1% by sensory-motor betweenness, most extreme first."""
    table = scores.assign(
        degree_pct=percentile_ranks(scores["degree"]),
        pagerank_pct=percentile_ranks(scores["pagerank"]),
        sm_betweenness_pct=percentile_ranks(scores["sm_betweenness"]),
    )
    hits = table[
        (table["degree_pct"] < LOW_PERCENTILE)
        & (table["pagerank_pct"] < LOW_PERCENTILE)
        & (table["sm_betweenness_pct"] >= HIGH_PERCENTILE)
    ]
    return hits.sort_values(["sm_betweenness", "degree"], ascending=[False, True])


def distance_matrix(graph: ig.Graph, sources: list[str], targets: list[str]) -> np.ndarray:
    """|sources| x |targets| hop distances; infinite where unreachable or where either endpoint is absent."""
    names = set(graph.vs["name"])
    matrix = np.full((len(sources), len(targets)), np.inf)
    rows = [i for i, s in enumerate(sources) if s in names]
    cols = [j for j, t in enumerate(targets) if t in names]
    if rows and cols:
        matrix[np.ix_(rows, cols)] = np.asarray(graph.distances(
            source=present_indices(graph, [sources[i] for i in rows]),
            target=present_indices(graph, [targets[j] for j in cols]),
            mode="out",
        ))
    return matrix


def partners(graph: ig.Graph, vertex: int, mode: str) -> list[dict]:
    """Partner types of ``vertex`` along incoming or outgoing edges, strongest first."""
    rows = []
    for edge in graph.es[graph.incident(vertex, mode=mode)]:
        other = graph.vs[edge.target if mode == "out" else edge.source]
        rows.append({"cell_type": other["name"], "superclass": other["superclass"], "synapses": int(edge["weight"])})
    return sorted(rows, key=lambda r: -r["synapses"])


def main() -> None:
    graph = load_type_graph()
    sources, targets = load_sensory_motor_sets()
    scores = intact_scores(graph, sources, targets)
    scores["superclass"] = graph.vs["superclass"]
    scores["n_neurons"] = graph.vs["n_neurons"]
    candidates = find_candidates(scores)
    candidates.to_csv(RESULTS / "hidden_bottleneck_candidates.csv", index=False, float_format="%.6g")
    if candidates.empty:
        (RESULTS / "hidden_bottleneck.md").write_text(
            "# Hidden bottleneck\n\nNo cell type is in the bottom half by both total degree and PageRank while in the "
            "top 1% by sensory-motor betweenness.\n", encoding="utf-8")
        print("No candidates", file=sys.stderr)
        return

    best = candidates.iloc[0]
    vertex = graph.vs.find(name=best["cell_type"]).index
    reduced = graph.copy()
    reduced.delete_vertices([vertex])
    before, after = distance_matrix(graph, sources, targets), distance_matrix(reduced, sources, targets)
    still_reachable = np.isfinite(before) & np.isfinite(after)
    intact_flow = flow_capacity(graph, sources, targets)
    reachable = int(np.isfinite(before).sum())

    stats = {
        "cell_type": best["cell_type"],
        "superclass": best["superclass"],
        "n_neurons": int(best["n_neurons"]),
        "in_degree": int(best["in_degree"]),
        "out_degree": int(best["out_degree"]),
        "degree": int(best["degree"]),
        "degree_percentile": float(best["degree_pct"]),
        "in_strength": float(best["in_strength"]),
        "out_strength": float(best["out_strength"]),
        "pagerank": float(best["pagerank"]),
        "pagerank_percentile": float(best["pagerank_pct"]),
        "betweenness": float(best["betweenness"]),
        "sm_betweenness": float(best["sm_betweenness"]),
        "sm_betweenness_percentile": float(best["sm_betweenness_pct"]),
        "sm_betweenness_rank": int((scores["sm_betweenness"] > best["sm_betweenness"]).sum() + 1),
        "reachable_pairs": reachable,
        "share_of_shortest_routes": float(best["sm_betweenness"] / reachable),
        "pairs_lost_when_removed": int((np.isfinite(before) & ~np.isfinite(after)).sum()),
        "pairs_with_longer_shortest_path_when_removed": int((after[still_reachable] > before[still_reachable]).sum()),
        "intact_flow": intact_flow,
        "flow_after_removal": flow_capacity(reduced, sources, targets),
        "median_degree": float(scores["degree"].median()),
        "strongest_inputs": partners(graph, vertex, "in")[:TOP_PARTNERS],
        "strongest_outputs": partners(graph, vertex, "out")[:TOP_PARTNERS],
    }
    (RESULTS / "hidden_bottleneck.json").write_text(
        json.dumps({"criteria": {"degree_percentile_below": LOW_PERCENTILE, "pagerank_percentile_below": LOW_PERCENTILE,
                                 "sm_betweenness_percentile_at_least": HIGH_PERCENTILE},
                    "n_candidates": len(candidates),
                    "candidates": candidates[["cell_type", "superclass", "degree", "degree_pct", "pagerank_pct",
                                              "sm_betweenness", "sm_betweenness_pct"]].to_dict("records"),
                    "example": stats}, indent=2) + "\n", encoding="utf-8")

    def partner_list(rows: list[dict]) -> str:
        return ", ".join(f"`{r['cell_type']}` ({r['superclass']}, {r['synapses']} synapses)" for r in rows)

    lines = [
        "# Hidden bottleneck",
        "",
        "## Criteria",
        "",
        f"A type qualifies if, on the intact graph of {graph.vcount()} types, it ranks in the bottom half by total "
        "degree (input partner types plus output partner types, so a partner connected in both directions counts "
        "twice) and in the bottom half by PageRank, yet in the top "
        "1% by sensory-motor betweenness (the number of shortest sensory-to-motor routes, summed over all reachable "
        "pairs, that pass through it). Percentiles are mid-rank. All numbers below come from a single run of "
        "`pipeline/hidden_bottleneck.py` on the same graph.",
        "",
        f"{len(candidates)} types qualify (`results/hidden_bottleneck_candidates.csv`):",
        "",
        "| type | superclass | degree (percentile) | PageRank percentile | sensory-motor betweenness (percentile) |",
        "|---|---|---|---|---|",
        *[f"| `{r.cell_type}` | {r.superclass} | {r.degree} ({r.degree_pct:.0f}) | {r.pagerank_pct:.0f} | "
          f"{r.sm_betweenness:,.0f} ({r.sm_betweenness_pct:.2f}) |" for r in candidates.head(20).itertuples()],
        "",
        f"## The most extreme case: `{stats['cell_type']}`",
        "",
        "| quantity | value |",
        "|---|---|",
        f"| superclass | {stats['superclass']} |",
        f"| neurons in the type | {stats['n_neurons']} |",
        f"| input / output partner types | {stats['in_degree']} / {stats['out_degree']} (total {stats['degree']}; "
        f"median over all types {stats['median_degree']:.0f}) |",
        f"| degree percentile | {stats['degree_percentile']:.1f} |",
        f"| input / output synapses (in the graph) | {stats['in_strength']:,.0f} / {stats['out_strength']:,.0f} |",
        f"| PageRank percentile | {stats['pagerank_percentile']:.1f} |",
        f"| sensory-motor betweenness | {stats['sm_betweenness']:,.1f} (rank {stats['sm_betweenness_rank']} of "
        f"{graph.vcount()}, percentile {stats['sm_betweenness_percentile']:.2f}) |",
        f"| share of sensory-to-motor shortest routes through it | {100 * stats['share_of_shortest_routes']:.2f}% of "
        f"{stats['reachable_pairs']:,} reachable pairs |",
        f"| reachable pairs lost if it alone is removed | {stats['pairs_lost_when_removed']:,} |",
        f"| pairs whose shortest route gets longer if it is removed | {stats['pairs_with_longer_shortest_path_when_removed']:,} |",
        f"| flow capacity, intact → without it | {stats['intact_flow']} → {stats['flow_after_removal']} |",
        "",
        f"Strongest inputs: {partner_list(stats['strongest_inputs'])}.",
        "",
        f"Strongest outputs: {partner_list(stats['strongest_outputs'])}.",
        "",
        "## Why it matters",
        "",
        "Degree and PageRank are the usual shortcuts for spotting important nodes, and by both this type is "
        "unremarkable. It stands out only when paths are counted between the specific start and end points that "
        "matter for behavior, sensory neurons and descending or motor neurons.",
        "",
        f"What that does and does not mean: removing this type alone cuts flow capacity by "
        f"{stats['intact_flow'] - stats['flow_after_removal']} of {stats['intact_flow']} and disconnects "
        f"{stats['pairs_lost_when_removed']:,} sensory-motor pairs, while lengthening the shortest route for "
        f"{stats['pairs_with_longer_shortest_path_when_removed']:,}. Concentrating shortest routes is therefore not "
        "the same as being indispensable: parallel routes exist, they are just longer. These are structural "
        "measurements on the wiring diagram; whether the fly depends on this type has not been tested.",
        "",
    ]
    (RESULTS / "hidden_bottleneck.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
