"""Export every result the site reads as static JSON, with the figures it links to."""

import argparse
import json
import re
import shutil
import sys
from datetime import date

import numpy as np
import pandas as pd

from pipeline.avalanche_analysis import PLAUSIBLE_P
from pipeline.brain_vnc_comparison import RUNS_ROOT as COMPARTMENT_RUNS
from pipeline.build_type_graph import MIN_INPUT_FRACTION, load_type_graph
from pipeline.common import ASSETS, RESULTS, TYPE_NODES_PATH, WEB_DATA
from pipeline.figures import STRATEGY_COLORS
from pipeline.removal_strategies import STRATEGIES, STRATEGY_LABELS
from pipeline.run_percolation import CURVES_CSV, RANDOM_TRIALS

DATASET = "male-cns:v1.0"
SOURCE = "Berg et al., Cell 2026"
FIGURES = ("percolation_curves.png", "null_distribution.png", "literature_rank_plot.png", "brain_vnc_curves.png",
           "avalanche_ccdf.png", "network_comparison.png", "edge_attack.png")


def read_json(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def rounded(values, digits: int = 5) -> list:
    return [None if v is None or (isinstance(v, (float, np.floating)) and np.isnan(v)) else round(float(v), digits)
            for v in values]


def strategy_meta() -> list[dict]:
    return [{"id": s, "label": STRATEGY_LABELS[s], "color": STRATEGY_COLORS[s]} for s in STRATEGIES]


def neuron_counts() -> dict | None:
    """Neurons in the dataset, typed neurons, and the range of neurons per cell type; None if not on disk."""
    schema = RESULTS / "schema.md"
    if not (schema.exists() and TYPE_NODES_PATH.exists()):
        return None
    header = re.search(r"(\d+) `:Neuron` nodes, (\d+) with a cell type", schema.read_text(encoding="utf-8"))
    if header is None:
        return None
    per_type = pd.read_parquet(TYPE_NODES_PATH)["n_neurons"]
    return {"total": int(header.group(1)), "typed": int(header.group(2)), "per_type_min": int(per_type.min()),
            "per_type_max": int(per_type.max())}


def meta() -> dict:
    scores = read_json("fragility_scores.json")
    sets = read_json("sensory_motor_sets.json")
    return {"dataset": DATASET, "source": SOURCE, "exported": date.today().isoformat(),
            "graph": {**scores["graph"], "edge_min_input_fraction": MIN_INPUT_FRACTION},
            "protocol": scores["protocol"], "strategies": strategy_meta(),
            "sets": {k: len(v) for k, v in sets.items() if isinstance(v, list)}, "neurons": neuron_counts()}


def percolation() -> dict:
    curves = pd.read_csv(CURVES_CSV)
    scores = read_json("fragility_scores.json")
    thresholds = read_json("critical_thresholds.json")["strategies"]
    out = {}
    for name in STRATEGIES:
        runs = curves[curves["strategy"] == name]
        first = runs[runs["trial"] == 0].sort_values("batch")
        entry = {
            "auc_flow": scores["strategies"][name]["auc_flow"],
            "auc_reachability": scores["strategies"][name]["auc_reachability"],
            "critical_fraction": thresholds[name]["f_c"],
            "fraction_removed": rounded(first["fraction_removed"]),
            "flow": first["flow"].astype(int).tolist(),
            "reachable_pairs": first["reachable_pairs"].astype(int).tolist(),
            "avalanche": [None if pd.isna(v) else int(v) for v in first["avalanche"]],
        }
        if name == "random":
            grouped = runs.groupby("batch")
            entry.update(
                trials=RANDOM_TRIALS,
                critical_fraction_ci95=thresholds[name]["f_c_ci95"],
                band={"fraction_removed": rounded(grouped["fraction_removed"].mean()),
                      "flow_mean": rounded(grouped["flow"].mean(), 1),
                      "flow_low": grouped["flow"].min().astype(int).tolist(),
                      "flow_high": grouped["flow"].max().astype(int).tolist(),
                      "pairs_mean": rounded(grouped["reachable_pairs"].mean(), 1),
                      "pairs_low": grouped["reachable_pairs"].min().astype(int).tolist(),
                      "pairs_high": grouped["reachable_pairs"].max().astype(int).tolist()})
        out[name] = entry
    return {"intact_flow": scores["graph"]["intact_flow"],
            "intact_reachable_pairs": scores["graph"]["intact_reachable_pairs"], "strategies": out}


def nulls() -> dict:
    summary = read_json("null_model_summary.json")
    scores = pd.read_csv(RESULTS / "null_model_scores.csv")
    samples = {s: {m: rounded(rows[m], 4) for m in ("auc_flow", "auc_reachability")}
               for s, rows in scores.groupby("strategy")}
    return {"n_nulls": summary["n_nulls"], "alpha": summary["alpha"], "strategies": summary["strategies"],
            "samples": samples}


def atlas() -> dict:
    layout = read_json("type_atlas.json")
    impact = pd.read_csv(RESULTS / "regional_impact.csv").set_index("neuropil")
    outlines = []
    for region in layout["outlines"]:
        entry = {"neuropil": region["neuropil"], "path": region["path"]}
        if region["neuropil"] in impact.index:
            row = impact.loc[region["neuropil"]]
            entry.update(types=int(row["n_types"]), sensory=int(row["n_sensory"]), motor=int(row["n_motor"]),
                         flow_drop=round(float(row["flow_drop"]), 5), random_mean=round(float(row["random_mean"]), 5),
                         p_value=round(float(row["p_value"]), 5))
        outlines.append(entry)
    return {"canvas": layout["canvas"], "cns_outline": layout["cns_outline"], "outlines": outlines,
            "replay": layout["replay"]}


def regions() -> list[dict]:
    table = pd.read_csv(RESULTS / "regional_impact.csv")
    return [{"neuropil": r.neuropil, "types": int(r.n_types), "sensory": int(r.n_sensory), "motor": int(r.n_motor),
             "flow_drop": round(r.flow_drop, 5), "random_mean": round(r.random_mean, 5),
             "random_sd": round(r.random_sd, 5), "p_value": round(r.p_value, 5)} for r in table.itertuples()]


def types() -> dict:
    """Every cell type as parallel columns, so the site can look up and place any of the 11,751."""
    graph = load_type_graph()
    degree = pd.DataFrame({"cell_type": graph.vs["name"], "in_degree": graph.indegree(),
                           "out_degree": graph.outdegree(),
                           "out_strength": graph.strength(mode="out", weights="weight"),
                           "in_strength": graph.strength(mode="in", weights="weight")})
    table = (pd.read_csv(RESULTS / "type_atlas.csv")
             .merge(pd.read_parquet(TYPE_NODES_PATH)[["cell_type", "n_neurons"]], on="cell_type")
             .merge(pd.read_csv(RESULTS / "single_removal_impacts.csv")[["cell_type", "flow_drop", "pairs_lost"]],
                    on="cell_type")
             .merge(degree, on="cell_type"))
    sets = read_json("sensory_motor_sets.json")
    role = np.where(table["cell_type"].isin(sets["sensory"]), 1, np.where(table["cell_type"].isin(sets["motor"]), 2, 0))
    superclasses = sorted(table["superclass"].fillna("unknown").unique())
    anchors = sorted(table["anchor"].dropna().unique())
    return {
        "name": table["cell_type"].tolist(),
        "superclasses": superclasses,
        "superclass": table["superclass"].fillna("unknown").map({s: i for i, s in enumerate(superclasses)}).tolist(),
        "anchors": anchors,
        "anchor": table["anchor"].map({a: i for i, a in enumerate(anchors)}).fillna(-1).astype(int).tolist(),
        "compartment": table["compartment"].map({"brain": 0, "vnc": 1}).fillna(-1).astype(int).tolist(),
        "role": role.tolist(),
        "x": rounded(table["x"], 1), "y": rounded(table["y"], 1),
        "neurons": table["n_neurons"].astype(int).tolist(),
        "in_degree": table["in_degree"].astype(int).tolist(), "out_degree": table["out_degree"].astype(int).tolist(),
        "in_strength": table["in_strength"].astype(int).tolist(),
        "out_strength": table["out_strength"].astype(int).tolist(),
        "flow_drop": table["flow_drop"].astype(int).tolist(), "pairs_lost": table["pairs_lost"].astype(int).tolist(),
        "removed": {s: table[f"removed_{s}"].astype(int).tolist() for s in STRATEGIES},
        "silenced": {s: table[f"silenced_{s}"].astype(int).tolist() for s in STRATEGIES},
    }


def avalanches() -> dict:
    report = read_json("avalanche_analysis.json")
    curves = pd.read_csv(CURVES_CSV)
    sizes = curves["avalanche"].dropna().astype(int)
    sizes = np.sort(sizes[sizes > 0].to_numpy())[::-1]
    values, counts = np.unique(sizes, return_counts=True)
    ccdf = 1 - (np.cumsum(counts) - counts) / counts.sum()
    return {"primary": report["primary"], "sensitivity": report["sensitivity_all_random_trials"],
            "per_strategy": report["per_strategy"], "plausible_p": PLAUSIBLE_P,
            "ccdf": {"size": values.tolist(), "p": rounded(ccdf, 6)}}


def compartments() -> dict:
    report = read_json("brain_vnc_comparison.json")
    for name, entry in report["compartments"].items():
        entry["curves"] = {}
        for strategy in STRATEGIES:
            run = json.loads((COMPARTMENT_RUNS / name / f"{strategy}_00.json").read_text(encoding="utf-8"))
            entry["curves"][strategy] = {"fraction_removed": rounded(run["fraction_removed"]),
                                         "flow": [int(v) for v in run["flow"]]}
        for scores in entry["scores"].values():
            for key in [k for k in scores if k.endswith("_trials")]:
                del scores[key]
    return report


def literature() -> dict:
    report = read_json("literature_validation.json")
    return {"alpha": report["alpha"], "tests": report["tests"], "curated_types": report["curated_types"]}


def comparison() -> list[dict]:
    return pd.read_csv(RESULTS / "network_comparison.csv").to_dict(orient="records")


SECTIONS = {
    "meta.json": (meta, ("fragility_scores.json", "sensory_motor_sets.json")),
    "percolation.json": (percolation, ("percolation_curves.csv", "fragility_scores.json", "critical_thresholds.json")),
    "atlas.json": (atlas, ("type_atlas.json", "regional_impact.csv")),
    "types.json": (types, ("type_atlas.csv", "single_removal_impacts.csv")),
    "regions.json": (regions, ("regional_impact.csv",)),
    "nulls.json": (nulls, ("null_model_summary.json", "null_model_scores.csv")),
    "literature.json": (literature, ("literature_validation.json",)),
    "avalanches.json": (avalanches, ("avalanche_analysis.json", "percolation_curves.csv")),
    "compartments.json": (compartments, ("brain_vnc_comparison.json",)),
    "comparison.json": (comparison, ("network_comparison.csv",)),
    "structure.json": (lambda: read_json("structure_profile.json"), ("structure_profile.json",)),
    "edges.json": (lambda: read_json("edge_attack.json"), ("edge_attack.json",)),
    "pairs.json": (lambda: read_json("synthetic_lethal_pairs.json"), ("synthetic_lethal_pairs.json",)),
    "bilateral.json": (lambda: read_json("bilateral_symmetry.json"), ("bilateral_symmetry.json",)),
    "bottleneck.json": (lambda: read_json("hidden_bottleneck.json"), ("hidden_bottleneck.json",)),
}


def copy_figures() -> list[str]:
    """Copy the result figures and the hero render next to the data."""
    destination = WEB_DATA.parent / "figures"
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in [RESULTS / name for name in FIGURES] + [ASSETS / "hero.png"]:
        if path.exists():
            shutil.copyfile(path, destination / path.name)
            copied.append(path.name)
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-missing", action="store_true",
                        help="skip sections whose results are not on disk; for local development only")
    args = parser.parse_args()

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    missing = {}
    for name, (build, requires) in SECTIONS.items():
        absent = [f for f in requires if not (RESULTS / f).exists()]
        if absent:
            missing[name] = absent
            continue
        content = json.dumps(build(), separators=(",", ":"), allow_nan=False)
        (WEB_DATA / name).write_text(content + "\n", encoding="utf-8")
        print(f"{name}: {len(content) / 1024:.1f} kB")
    (WEB_DATA / "manifest.json").write_text(
        json.dumps({"available": sorted(set(SECTIONS) - set(missing))}) + "\n", encoding="utf-8")
    print(f"figures copied: {len(copy_figures())}")
    if missing:
        for name, absent in missing.items():
            print(f"SKIPPED {name}: missing {', '.join(absent)}", file=sys.stderr)
        if not args.allow_missing:
            sys.exit(1)


if __name__ == "__main__":
    main()
