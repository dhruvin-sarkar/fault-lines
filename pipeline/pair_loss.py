"""List the sensory-motor pairs each cell type disconnects when removed alone, split into its own pairs and others."""

import json
import math

import igraph as ig
import numpy as np
import pandas as pd

from pipeline.build_type_graph import load_type_graph
from pipeline.common import RESULTS
from pipeline.identify_sensory_motor_sets import MOTOR_SUPERCLASSES, load_sensory_motor_sets
from pipeline.single_removal import reachable_matrix

CSV_PATH = RESULTS / "pair_loss.csv"
JSON_PATH = RESULTS / "pair_loss.json"
REPORT_PATH = RESULTS / "pair_loss.md"
REPORT_MOTORS = 10


def pair_losses(graph: ig.Graph, sources: list[str], targets: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    """Every (sensory, motor) pair that removing a single vertex disconnects, found with dominator trees.

    A vertex v other than s and m disconnects a reachable pair (s, m) exactly when every path from s to m passes
    through v, that is when v strictly dominates m in the dominator tree rooted at s. Removing s or m itself
    disconnects the pair trivially; those pairs are not listed here but follow from the reachability matrix.

    Parameters: ``graph`` directed graph with a ``name`` vertex attribute; ``sources`` and ``targets`` disjoint
    vertex names.

    Returns: a frame with columns ``cell_type``, ``sensory``, ``motor`` holding the non-trivial losses, and the
    |sources| x |targets| boolean reachability matrix of the intact graph.
    """
    names = graph.vs["name"]
    index = {name: i for i, name in enumerate(names)}
    target_ids = [index[t] for t in targets]
    rows = []
    for s in sources:
        root = index[s]
        idom = graph.dominator(root, mode="out")
        for m, m_id in zip(targets, target_ids):
            parent = idom[m_id]
            if isinstance(parent, float) and math.isnan(parent):
                continue
            while parent != root:
                rows.append((names[parent], s, m))
                parent = idom[parent]
    losses = pd.DataFrame(rows, columns=["cell_type", "sensory", "motor"])
    return losses, reachable_matrix(graph, sources, targets)


def summarize(losses: pd.DataFrame, reach: np.ndarray, sources: list[str], targets: list[str],
              superclass: dict[str, str]) -> pd.DataFrame:
    """One row per type that disconnects at least one pair, with its own pairs and other pairs counted apart.

    ``own_pairs`` are pairs in which the type is the sensory source (every motor type it reaches) or the motor
    target (every sensory type that reaches it); ``other_pairs`` are pairs between two other types.
    """
    own = pd.concat([
        pd.Series(reach.sum(axis=1), index=sources),
        pd.Series(reach.sum(axis=0), index=targets),
    ])
    grouped = losses.groupby("cell_type")
    table = pd.DataFrame({
        "other_pairs": grouped.size(),
        "sensory_types_cut": grouped["sensory"].nunique(),
        "motor_types_cut": grouped["motor"].nunique(),
    }).reindex(own.index.union(grouped.size().index), fill_value=0)
    table["own_pairs"] = own.reindex(table.index, fill_value=0)
    table["pairs_lost"] = table["own_pairs"] + table["other_pairs"]
    table = table[table["pairs_lost"] > 0].rename_axis("cell_type").reset_index()
    sensory, motor = set(sources), set(targets)
    table["role"] = table["cell_type"].map(lambda t: "sensory" if t in sensory else "motor" if t in motor else "other")
    table["superclass"] = table["cell_type"].map(superclass)
    columns = ["cell_type", "superclass", "role", "pairs_lost", "own_pairs", "other_pairs", "sensory_types_cut",
               "motor_types_cut"]
    return table[columns].sort_values(["other_pairs", "pairs_lost", "cell_type"], ascending=[False, False, True],
                                      ignore_index=True)


def motor_order(targets: list[str], superclass: dict[str, str]) -> dict[str, int]:
    """Display rank of each motor type: descending neurons, then central brain motor, then nerve cord motor, by name."""
    rank = {c: i for i, c in enumerate(MOTOR_SUPERCLASSES)}
    ordered = sorted(targets, key=lambda t: (rank.get(superclass.get(t), len(rank)), t))
    return {t: i for i, t in enumerate(ordered)}


def grouped_pairs(losses: pd.DataFrame, reach: np.ndarray, sources: list[str], targets: list[str],
                  superclass: dict[str, str]) -> dict[str, list[dict]]:
    """Non-trivial lost pairs per removed type, grouped by sensory source.

    Sources are ordered by motor types lost (most first), then name; motors within a source by :func:`motor_order`.
    ``reach`` in each group is the number of motor types that source reaches in the intact graph.
    """
    order = motor_order(targets, superclass)
    reach_of = dict(zip(sources, reach.sum(axis=1).tolist()))
    out = {}
    for cell_type, rows in losses.groupby("cell_type", sort=True):
        groups = [{"sensory": s, "reach": int(reach_of[s]), "motors": sorted(part["motor"], key=order.__getitem__)}
                  for s, part in rows.groupby("sensory", sort=True)]
        out[cell_type] = sorted(groups, key=lambda g: (-len(g["motors"]), g["sensory"]))
    return out


def removal_check(graph: ig.Graph, sources: list[str], targets: list[str], reach: np.ndarray, cell_type: str,
                  losses: pd.DataFrame) -> None:
    """Delete ``cell_type`` and confirm the pairs that become unreachable are exactly its own plus the listed ones."""
    reduced = graph.copy()
    reduced.delete_vertices([graph.vs.find(name=cell_type).index])
    rows, cols = np.nonzero(reach & ~reachable_matrix(reduced, sources, targets))
    found = {(sources[i], targets[j]) for i, j in zip(rows, cols)}
    expected = {(s, m) for s, m in zip(losses["sensory"], losses["motor"])}
    expected |= {(sources[i], targets[j]) for i, j in zip(*np.nonzero(reach))
                 if cell_type in (sources[i], targets[j])}
    assert found == expected, f"{cell_type}: dominator pairs differ from deletion ({len(found ^ expected)} pairs)"


def report(table: pd.DataFrame, pairs: dict[str, list[dict]], meta: dict) -> str:
    others = table[table["other_pairs"] > 0]
    own_sensory = table[(table["role"] == "sensory") & (table["other_pairs"] == 0)]
    own_motor = table[(table["role"] == "motor") & (table["other_pairs"] == 0)]
    lines = [
        "# Sensory-motor pairs that lose their only path",
        "",
        f"Removing a single cell type disconnects a sensory-motor pair (s, m) when the pair is reachable in the intact "
        f"graph and no directed path from s to m avoids the removed type. The intact graph joins "
        f"{meta['intact_reachable_pairs']:,} of the {meta['n_sensory']} x {meta['n_motor']} = "
        f"{meta['n_sensory'] * meta['n_motor']:,} sensory-motor type pairs.",
        "",
        "## Procedure",
        "",
        f"1. For each of the {meta['n_sensory']} sensory types s, the dominator tree of the graph rooted at s is "
        "computed. A type v other than s and m lies on every path from s to m exactly when v is an ancestor of m in "
        "that tree, so the ancestors between m and s are the types whose removal alone disconnects (s, m).",
        "2. Pairs in which the removed type is the sensory source or the motor target are its own pairs: a sensory "
        "type loses every motor type it reaches, a motor type every sensory type that reaches it.",
        f"3. Own pairs plus other pairs reproduce `pairs_lost` in `results/single_removal_impacts.csv`, computed there "
        f"by deleting each type and recomputing reachability, for all {meta['n_types']:,} types. For every type with "
        f"other pairs, the exact set of pairs was also confirmed by deleting it and comparing reachability.",
        "",
        "## Result",
        "",
        f"{meta['types_with_pairs_lost']:,} types disconnect at least one pair when removed alone. For "
        f"{len(own_sensory):,} of them (sensory types) and {len(own_motor):,} (descending or motor types) every lost "
        f"pair is one of their own. {len(others)} types disconnect pairs between two other types, "
        f"{int(others['other_pairs'].sum()):,} such pairs in total. All counts: `results/pair_loss.csv`; the other "
        "pairs themselves: `results/pair_loss.json`.",
        "",
        "| type (superclass) | set | pairs lost | own pairs | other pairs | sensory types cut | motor types cut |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in others.itertuples():
        lines.append(f"| `{row.cell_type}` ({row.superclass}) | {row.role} | {row.pairs_lost:,} | {row.own_pairs:,} | "
                     f"{row.other_pairs:,} | {row.sensory_types_cut} | {row.motor_types_cut} |")
    lines += ["", "## Which pairs", ""]
    for row in others.itertuples():
        for group in pairs[row.cell_type]:
            lost = len(group["motors"])
            shown = ", ".join(f"`{m}`" for m in group["motors"][:REPORT_MOTORS])
            rest = f", and {lost - REPORT_MOTORS:,} more" if lost > REPORT_MOTORS else ""
            scope = (f"all {lost:,} motor types it reaches" if lost == group["reach"]
                     else f"{lost:,} of the {group['reach']:,} motor types it reaches")
            lines.append(f"Removing `{row.cell_type}` cuts `{group['sensory']}` off from {scope}: {shown}{rest}.")
            lines.append("")
    lines += [
        "Motor types are listed descending neurons first, then central brain motor and nerve cord motor types, each by "
        "name.",
        "",
        "Reachability asks only whether some path exists, so a pair counts as lost only when its last route is gone. "
        "These are structural statements about the type-level wiring diagram, not predictions of behavior.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    graph = load_type_graph()
    sources, targets = load_sensory_motor_sets()
    superclass = dict(zip(graph.vs["name"], graph.vs["superclass"]))
    losses, reach = pair_losses(graph, sources, targets)
    table = summarize(losses, reach, sources, targets, superclass)

    single = pd.read_csv(RESULTS / "single_removal_impacts.csv").set_index("cell_type")["pairs_lost"]
    counts = table.set_index("cell_type")["pairs_lost"].reindex(single.index, fill_value=0)
    mismatched = counts[counts != single]
    assert mismatched.empty, f"{len(mismatched)} types differ from single_removal_impacts.csv, e.g. {mismatched.index[:5].tolist()}"
    pairs = grouped_pairs(losses, reach, sources, targets, superclass)
    for cell_type in pairs:
        removal_check(graph, sources, targets, reach, cell_type, losses[losses["cell_type"] == cell_type])

    meta = {"intact_reachable_pairs": int(reach.sum()), "n_sensory": len(sources), "n_motor": len(targets),
            "n_types": graph.vcount(), "types_with_pairs_lost": len(table),
            "types_with_other_pairs": int((table["other_pairs"] > 0).sum()),
            "other_pairs_total": int(table["other_pairs"].sum())}
    table.to_csv(CSV_PATH, index=False)
    JSON_PATH.write_text(json.dumps({**meta, "motor_superclass_order": list(MOTOR_SUPERCLASSES), "types": pairs},
                                    indent=1) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(report(table, pairs, meta), encoding="utf-8")
    print(f"{meta['types_with_pairs_lost']} types disconnect a pair; {meta['types_with_other_pairs']} disconnect "
          f"{meta['other_pairs_total']} pairs between other types; counts match single_removal_impacts.csv")


if __name__ == "__main__":
    main()
