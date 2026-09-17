"""Search a candidate pool of cell types for pairs whose joint removal hurts flow far more than each alone."""

import argparse
import itertools
import json
import sys
from multiprocessing import Pool

import igraph as ig
import pandas as pd

from pipeline.build_type_graph import load_type_graph
from pipeline.common import RESULTS
from pipeline.connectivity_metrics import flow_capacity
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets
from pipeline.removal_strategies import intact_scores
from pipeline.single_removal import load_single_removal

POOL_SIZE = 250
TOP_REPORTED = 25


def candidate_pool(scores: pd.DataFrame, size: int = POOL_SIZE) -> pd.DataFrame:
    """Types with the highest single-removal flow impact per edge (in plus out), ties by sensory-motor betweenness.

    Args:
        scores: columns ``cell_type``, ``flow_drop``, ``degree``, ``sm_betweenness``.
    """
    ranked = scores.assign(impact_per_edge=scores["flow_drop"] / scores["degree"].where(scores["degree"] > 0))
    ranked["impact_per_edge"] = ranked["impact_per_edge"].fillna(0.0)
    return ranked.sort_values(["impact_per_edge", "sm_betweenness", "cell_type"], ascending=[False, False, True]).head(size)


def synergy(intact_flow: int, flow_after_pair: int, impact_a: int, impact_b: int) -> tuple[int, int]:
    """Joint impact and its excess over the sum of the two single-removal impacts."""
    joint = intact_flow - flow_after_pair
    return joint, joint - impact_a - impact_b


_WORKER: dict = {}


def _init_worker(graph: ig.Graph, sources: list[str], targets: list[str]) -> None:
    _WORKER.update(graph=graph, sources=sources, targets=targets, index={n: i for i, n in enumerate(graph.vs["name"])})


def remove_pair(pair: tuple[str, str]) -> tuple[str, str, int]:
    reduced = _WORKER["graph"].copy()
    reduced.delete_vertices([_WORKER["index"][pair[0]], _WORKER["index"][pair[1]]])
    return pair[0], pair[1], flow_capacity(reduced, _WORKER["sources"], _WORKER["targets"])


def report_lines(table: pd.DataFrame, summary: dict, n_types: int, superclass: dict[str, str]) -> list[str]:
    """Lines of ``synthetic_lethal_pairs.md``.

    Args:
        table: all evaluated pairs sorted by synergy, as in ``synthetic_lethal_pairs.csv``.
        summary: the contents of ``synthetic_lethal_pairs.json``.
        n_types: number of cell types in the graph.
        superclass: majority superclass per cell type.
    Returns the markdown lines.
    """
    intact_flow = summary["intact_flow"]
    expected = summary["pool_size"] * (summary["pool_size"] - 1) // 2
    top = table.head(TOP_REPORTED)
    return [
        "# Synthetic-lethal cell-type pairs",
        "",
        "In genetics, two genes are synthetic lethal when losing either alone is tolerated but losing both is not. The "
        "structural analogue here: two cell types whose joint removal cuts sensory-to-motor flow capacity by more than "
        "the sum of what each removal does alone, most often because both are sensory types feeding the same "
        "downstream capacity, so either can fill it when the other is gone.",
        "",
        "## Procedure",
        "",
        f"1. Single-removal impact I(v) = intact flow ({intact_flow} edge-disjoint S→M paths) minus flow with type v "
        f"removed, for all {n_types} types.",
        f"2. Candidate pool: the {summary['pool_size']} types with the largest I(v) per incident edge (in plus out edges "
        "of the intact graph), a heuristic for types that carry a lot of flow for how connected they are; ties broken by "
        f"higher sensory-motor betweenness. {summary['pool_types_with_nonzero_single_impact']} pool members have "
        "I(v) > 0. Pool with scores: `results/synthetic_lethal_pool.csv`.",
        f"3. Every pair in the pool, {len(table)} of {expected} (all), removed together: joint impact "
        "I(u, v) = intact flow − flow without both; synergy = I(u, v) − I(u) − I(v).",
        "",
        f"{summary['pairs_with_positive_synergy']} pairs have positive synergy, "
        f"{summary['pairs_with_negative_synergy']} negative (their individual impacts overlap), the rest zero. All "
        "pairs: `results/synthetic_lethal_pairs.csv`.",
        "",
        f"## Top {TOP_REPORTED} pairs by synergy",
        "",
        "Every row can be checked from its own numbers: joint impact = intact flow − flow after; synergy = joint impact − "
        "I(a) − I(b).",
        "",
        "| type a (superclass) | type b (superclass) | I(a) | I(b) | flow after removing both | joint impact | synergy |",
        "|---|---|---|---|---|---|---|",
        *[f"| `{r.type_a}` ({superclass[r.type_a]}) | `{r.type_b}` ({superclass[r.type_b]}) | {r.impact_a} | {r.impact_b} | "
          f"{r.flow_after} | {r.joint_impact} | {r.synergy:+d} |" for r in top.itertuples()],
        "",
        "Flow capacity counts edge-disjoint paths, so a positive synergy means the two types substitute for each other "
        "at the sensory entry points into shared downstream capacity; this does not show parallel pathways deeper in "
        "the circuit. It is a structural statement about the wiring diagram, not a prediction of what silencing both "
        "types would do to a fly.",
        "",
    ]


def write_report(table: pd.DataFrame, summary: dict, graph: ig.Graph) -> None:
    """Write ``synthetic_lethal_pairs.md`` and print its table section."""
    superclass = dict(zip(graph.vs["name"], graph.vs["superclass"]))
    lines = report_lines(table, summary, graph.vcount(), superclass)
    (RESULTS / "synthetic_lethal_pairs.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[-TOP_REPORTED - 6:]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--from-results", action="store_true",
                        help="rebuild the report from results/synthetic_lethal_pairs.csv and .json instead of "
                             "recomputing")
    args = parser.parse_args()

    graph = load_type_graph()
    if args.from_results:
        summary = json.loads((RESULTS / "synthetic_lethal_pairs.json").read_text(encoding="utf-8"))
        write_report(pd.read_csv(RESULTS / "synthetic_lethal_pairs.csv"), summary, graph)
        return
    sources, targets = load_sensory_motor_sets()
    single = load_single_removal()
    intact_flow = int(single["intact_flow"].iloc[0])
    if intact_flow != flow_capacity(graph, sources, targets):
        raise RuntimeError("Single-removal table was computed on a different graph")
    scores = intact_scores(graph, sources, targets, include_betweenness=False).merge(single, on="cell_type")
    pool = candidate_pool(scores)
    impact = pool.set_index("cell_type")["flow_drop"].to_dict()

    pairs = list(itertools.combinations(pool["cell_type"], 2))
    rows = []
    with Pool(args.workers, initializer=_init_worker, initargs=(graph, sources, targets)) as workers:
        for i, (a, b, flow) in enumerate(workers.imap(remove_pair, pairs, chunksize=32), start=1):
            joint, excess = synergy(intact_flow, flow, impact[a], impact[b])
            rows.append({"type_a": a, "type_b": b, "impact_a": impact[a], "impact_b": impact[b],
                         "flow_after": flow, "joint_impact": joint, "synergy": excess})
            if i % 2000 == 0:
                print(f"pairs: {i}/{len(pairs)}", flush=True)
    table = pd.DataFrame(rows).sort_values(["synergy", "joint_impact"], ascending=False)
    expected = POOL_SIZE * (POOL_SIZE - 1) // 2
    if len(table) != expected:
        print(f"Evaluated {len(table)} pairs, expected {expected}", file=sys.stderr)
        sys.exit(1)
    table.to_csv(RESULTS / "synthetic_lethal_pairs.csv", index=False)
    pool.to_csv(RESULTS / "synthetic_lethal_pool.csv", index=False, float_format="%.6g")

    positive = table[table["synergy"] > 0]
    top = table.head(TOP_REPORTED)
    summary = {
        "intact_flow": intact_flow, "pool_size": len(pool), "pairs_evaluated": len(table),
        "pool_types_with_nonzero_single_impact": int((pool["flow_drop"] > 0).sum()),
        "pairs_with_positive_synergy": int(len(positive)), "pairs_with_negative_synergy": int((table["synergy"] < 0).sum()),
        "max_synergy": int(table["synergy"].max()), "top_pairs": top.to_dict("records"),
    }
    (RESULTS / "synthetic_lethal_pairs.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_report(table, summary, graph)


if __name__ == "__main__":
    main()
