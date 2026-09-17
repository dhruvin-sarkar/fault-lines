"""Check that every result describes the same cell-type graph: size, intact flow and intact reachability."""

import re

from verify.common import data_available, result_csv, result_json, result_text, run


def check() -> str:
    graph = result_json("fragility_scores.json")["graph"]
    types, edges = graph["cell_types"], graph["edges"]
    flow, pairs = graph["intact_flow"], graph["intact_reachable_pairs"]

    stated = re.search(r"Graph: ([\d,]+) cell types, ([\d,]+) directed edges", result_text("preregistration.md"))
    assert stated, "preregistration.md does not state the graph size"
    assert (int(stated.group(1).replace(",", "")), int(stated.group(2).replace(",", ""))) == (types, edges), \
        f"Pre-registered graph size {stated.group(1)} / {stated.group(2)} differs from {types} / {edges}"
    assert 0 < pairs <= graph["sensory_motor_pairs"], f"{pairs} reachable pairs of {graph['sensory_motor_pairs']}"

    structure = result_json("structure_profile.json")
    edge_attack = result_json("edge_attack.json")
    sizes = {"structure_profile.json": (structure["types"], structure["edges"]),
             "edge_attack.json": (types, edge_attack["edges"])}
    for name, size in sizes.items():
        assert size == (types, edges), f"{name} describes {size[0]} types and {size[1]} edges"

    flows = {
        "critical_thresholds.json": result_json("critical_thresholds.json")["intact_flow"],
        "structure_profile.json": structure["intact_flow"],
        "edge_attack.json": edge_attack["intact_flow"],
        "synthetic_lethal_pairs.json": result_json("synthetic_lethal_pairs.json")["intact_flow"],
        "hidden_bottleneck.json": result_json("hidden_bottleneck.json")["example"]["intact_flow"],
    }
    single = result_csv("single_removal_impacts.csv")
    regional = result_csv("regional_impact.csv")
    flows["single_removal_impacts.csv"] = int(single["intact_flow"].iloc[0])
    flows["regional_impact.csv"] = int(regional["intact_flow"].iloc[0])
    for name, value in flows.items():
        assert value == flow, f"{name} has intact flow {value}, fragility_scores.json has {flow}"
    assert single["intact_flow"].nunique() == 1 and regional["intact_flow"].nunique() == 1, "Intact flow varies by row"
    assert (single["intact_reachable_pairs"] == pairs).all(), "single_removal_impacts.csv intact pairs differ"
    assert result_json("hidden_bottleneck.json")["example"]["reachable_pairs"] == pairs, "hidden_bottleneck.json pairs differ"

    names = set(single["cell_type"])
    assert len(single) == types and len(names) == types, f"single_removal_impacts.csv has {len(single)} rows"
    for table in ("type_atlas.csv", "type_compartments.csv"):
        other = result_csv(table)["cell_type"]
        assert len(other) == types and set(other) == names, f"{table} does not list exactly the {types} graph types"
    assert (single["flow"] == flow - single["flow_drop"]).all(), "flow + flow_drop differs from intact flow"
    assert (single["flow_drop"] >= 0).all() and (single["pairs_lost"] >= 0).all(), "Negative single-removal impact"
    assert (single["reachable_pairs"] == pairs - single["pairs_lost"]).all(), "reachable pairs + lost differs from intact"

    detail = "graph not rebuilt (no data cache)"
    if data_available():
        from pipeline.build_type_graph import load_type_graph
        from pipeline.connectivity_metrics import flow_capacity, reachable_pairs
        from pipeline.identify_sensory_motor_sets import load_sensory_motor_sets

        g = load_type_graph()
        assert g.is_directed() and g.is_simple(), "Graph should be directed with no loops or multi-edges"
        assert (g.vcount(), g.ecount()) == (types, edges), f"Rebuilt graph has {g.vcount()} types, {g.ecount()} edges"
        assert set(g.vs["name"]) == names, "Rebuilt graph vertices differ from the result tables"
        sources, targets = load_sensory_motor_sets()
        assert flow_capacity(g, sources, targets) == flow, "Rebuilt graph gives a different intact flow"
        assert reachable_pairs(g, sources, targets) == pairs, "Rebuilt graph gives different reachable pairs"
        detail = "rebuilt graph matches"
    return f"{types:,} types, {edges:,} edges, intact flow {flow}, {pairs:,} reachable pairs in {len(flows) + 1} results; {detail}"


if __name__ == "__main__":
    run(check)
