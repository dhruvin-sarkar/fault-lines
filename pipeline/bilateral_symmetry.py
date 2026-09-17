"""Test whether a cell type's contralateral homolog provides structural insurance for sensory-to-motor flow."""

import argparse
import json
from multiprocessing import Pool

import igraph as ig
import pandas as pd
from scipy import stats

from pipeline.build_type_graph import load_side_graph
from pipeline.common import DATA, RESULTS
from pipeline.connectivity_metrics import flow_capacity
from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets

ALPHA = 0.05
CHECKPOINT = DATA / "bilateral_rows.csv"
COLUMNS = ["cell_type", "impact_left", "impact_right", "impact_both"]


def split_name(node: str) -> tuple[str, str]:
    cell_type, _, side = node.rpartition("|")
    return cell_type, side


def bilateral_types(names: list[str]) -> list[str]:
    """Types that have both a left and a right node in the hemisphere-resolved graph."""
    sides: dict[str, set[str]] = {}
    for name in names:
        cell_type, side = split_name(name)
        sides.setdefault(cell_type, set()).add(side)
    return sorted(t for t, s in sides.items() if {"L", "R"} <= s)


def completed_rows(path=CHECKPOINT) -> pd.DataFrame:
    """Rows already measured by an earlier, interrupted run; empty when none exist."""
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path).drop_duplicates("cell_type", keep="last")


def wilcoxon_greater(x: pd.Series, y: pd.Series) -> dict:
    """One-sided Wilcoxon signed-rank test that x exceeds y, over pairs where they differ."""
    differ = x != y
    result = stats.wilcoxon(x[differ], y[differ], alternative="greater")
    return {"pairs_differing": int(differ.sum()), "statistic": float(result.statistic), "p_value": float(result.pvalue)}


_WORKER: dict = {}


def _init_worker(graph: ig.Graph, sources: list[str], targets: list[str], intact_flow: int) -> None:
    _WORKER.update(graph=graph, sources=sources, targets=targets, intact_flow=intact_flow,
                   index={n: i for i, n in enumerate(graph.vs["name"])})


def remove_sides(cell_type: str) -> dict:
    graph, index = _WORKER["graph"], _WORKER["index"]

    def impact(nodes: list[str]) -> int:
        reduced = graph.copy()
        reduced.delete_vertices([index[n] for n in nodes])
        return _WORKER["intact_flow"] - flow_capacity(reduced, _WORKER["sources"], _WORKER["targets"])

    left, right = f"{cell_type}|L", f"{cell_type}|R"
    return {"cell_type": cell_type, "impact_left": impact([left]), "impact_right": impact([right]),
            "impact_both": impact([left, right])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    graph = load_side_graph()
    sensory, motor = load_sensory_motor_sets()
    sensory, motor = set(sensory), set(motor)
    sources = [n for n in graph.vs["name"] if split_name(n)[0] in sensory]
    targets = [n for n in graph.vs["name"] if split_name(n)[0] in motor]
    intact_flow = flow_capacity(graph, sources, targets)
    eligible = bilateral_types(graph.vs["name"])
    side_counts = pd.Series([split_name(n)[1] for n in graph.vs["name"]]).value_counts()

    done = completed_rows()
    pending = [t for t in eligible if t not in set(done["cell_type"])]
    print(f"bilateral types: {len(done)}/{len(eligible)} already measured", flush=True)
    write_header = not CHECKPOINT.exists()
    with open(CHECKPOINT, "a", encoding="utf-8", newline="") as checkpoint,             Pool(args.workers, initializer=_init_worker, initargs=(graph, sources, targets, intact_flow)) as pool:
        for i, row in enumerate(pool.imap_unordered(remove_sides, pending, chunksize=8), start=len(done) + 1):
            pd.DataFrame([row], columns=COLUMNS).to_csv(checkpoint, header=write_header, index=False)
            write_header = False
            if i % 100 == 0:
                checkpoint.flush()
            if i % 500 == 0:
                print(f"bilateral types: {i}/{len(eligible)}", flush=True)
    table = completed_rows()
    table = table[table["cell_type"].isin(eligible)].reset_index(drop=True)
    table["impact_single_mean"] = (table["impact_left"] + table["impact_right"]) / 2
    table["superadditivity"] = table["impact_both"] - table["impact_left"] - table["impact_right"]
    table.sort_values(["superadditivity", "impact_both"], ascending=False).to_csv(RESULTS / "bilateral_symmetry.csv", index=False)

    informative = table[(table[["impact_left", "impact_right", "impact_both"]] != 0).any(axis=1)]
    test_both_vs_single = wilcoxon_greater(informative["impact_both"], informative["impact_single_mean"])
    test_superadditive = wilcoxon_greater(informative["impact_both"], informative["impact_left"] + informative["impact_right"])
    counts = {
        "superadditive": int((informative["superadditivity"] > 0).sum()),
        "additive": int((informative["superadditivity"] == 0).sum()),
        "subadditive": int((informative["superadditivity"] < 0).sum()),
    }
    insured = informative[(informative["impact_left"] == 0) & (informative["impact_right"] == 0) & (informative["impact_both"] > 0)]
    summary = {
        "intact_flow": intact_flow, "nodes": graph.vcount(), "edges": graph.ecount(),
        "nodes_by_side": {str(k): int(v) for k, v in side_counts.items()},
        "bilateral_types": len(eligible), "informative_types": len(informative),
        "both_greater_than_single_mean": test_both_vs_single, "both_greater_than_sum_of_singles": test_superadditive,
        "additivity_counts": counts, "fully_insured_types": int(len(insured)),
        "strongest_superadditive": informative.sort_values(["superadditivity", "impact_both"], ascending=False)
        .head(15).to_dict("records"),
    }
    (RESULTS / "bilateral_symmetry.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    top = informative.sort_values(["superadditivity", "impact_both"], ascending=False).head(15)

    def result(test: dict) -> str:
        return (f"W = {test['statistic']:.0f} over {test['pairs_differing']} types with unequal values, one-sided "
                f"p = {test['p_value']:.2g} ({'significant' if test['p_value'] < ALPHA else 'not significant'} at {ALPHA})")

    lines = [
        "# Bilateral redundancy",
        "",
        "## Is laterality encoded cleanly?",
        "",
        "Yes. neuPrint's male CNS dataset has a dedicated `somaSide` field (L, R or M for midline) for neurons with a "
        "cell body in the CNS and a `rootSide` field (L or R) for sensory neurons, which enter through a nerve root. "
        "Among 164,506 typed neurons only one has conflicting values (the soma side is used). See `results/schema.md`. "
        "No side was inferred from names.",
        "",
        "## Procedure",
        "",
        f"A hemisphere-resolved graph was built from the same neuron-level connectivity, with one node per (type, "
        f"hemisphere) and the same rule for keeping edges (at least 1% of the target node's input): {graph.vcount()} "
        f"nodes ({', '.join(f'{k}: {v}' for k, v in side_counts.items())}) and {graph.ecount()} edges. Sensory and "
        f"descending/motor nodes are those whose type is in S or M. Intact flow capacity: {intact_flow}.",
        "",
        f"For each of the {len(eligible)} types with both a left and a right node, flow capacity was measured after "
        "removing the left node, the right node, and both. Impact = intact flow minus flow after removal. Superadditivity "
        f"= impact(both) − impact(left) − impact(right). {len(informative)} types have a non-zero impact in at least "
        "one of the three removals and enter the tests.",
        "",
        "## Results",
        "",
        f"1. Removing both sides versus the mean of removing one side: {result(test_both_vs_single)}.",
        f"2. Removing both sides versus the sum of the two single-side removals (superadditivity): {result(test_superadditive)}.",
        "",
        f"Of the {len(informative)} informative types, {counts['superadditive']} are superadditive (the two sides back each "
        f"other up), {counts['additive']} additive and {counts['subadditive']} subadditive (the two sides share a "
        f"bottleneck, so removing one already removes most of what both carry). {len(insured)} types lose no flow when "
        "either side is removed alone but do lose flow when both are removed: for these, the contralateral homolog is "
        "complete structural insurance.",
        "",
        "## Strongest superadditive types",
        "",
        "| type | impact, left removed | impact, right removed | impact, both removed | superadditivity |",
        "|---|---|---|---|---|",
        *[f"| `{r.cell_type}` | {r.impact_left} | {r.impact_right} | {r.impact_both} | {r.superadditivity:+d} |" for r in top.itertuples()],
        "",
        "All types: `results/bilateral_symmetry.csv`.",
        "",
    ]
    (RESULTS / "bilateral_symmetry.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[20:34]))


if __name__ == "__main__":
    main()
