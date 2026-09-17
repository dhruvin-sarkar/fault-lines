"""Check the site data in web/public/data matches the results it is exported from, and the manifest lists it exactly."""

import json

import numpy as np
import pandas as pd

import export.build_static_json as site
from pipeline.common import ASSETS, RESULTS, WEB_DATA
from pipeline.removal_strategies import STRATEGIES
from verify.common import Skip, data_available, first_difference, read_json, result_csv, result_json, run

# Sections rebuilt from committed results alone; types.json and compartments.json also read the local data cache.
DATA_FREE = ("meta.json", "percolation.json", "atlas.json", "regions.json", "nulls.json", "literature.json",
             "avalanches.json", "comparison.json", "structure.json", "edges.json", "pairs.json", "bilateral.json",
             "bottleneck.json", "pair_loss.json")


def roundtrip(value):
    return json.loads(json.dumps(value, allow_nan=False))


def check_types(exported: dict) -> str | None:
    """Columns of types.json that can be derived from committed results."""
    atlas = result_csv("type_atlas.csv")
    single = result_csv("single_removal_impacts.csv").set_index("cell_type").reindex(atlas["cell_type"])
    sets = result_json("sensory_motor_sets.json")
    superclasses = sorted(atlas["superclass"].fillna("unknown").unique())
    anchors = sorted(atlas["anchor"].dropna().unique())
    expected = {
        "name": atlas["cell_type"].tolist(),
        "superclasses": superclasses,
        "superclass": atlas["superclass"].fillna("unknown").map({s: i for i, s in enumerate(superclasses)}).tolist(),
        "anchors": anchors,
        "anchor": atlas["anchor"].map({a: i for i, a in enumerate(anchors)}).fillna(-1).astype(int).tolist(),
        "compartment": atlas["compartment"].map({"brain": 0, "vnc": 1}).fillna(-1).astype(int).tolist(),
        "role": np.where(atlas["cell_type"].isin(sets["sensory"]), 1,
                         np.where(atlas["cell_type"].isin(sets["motor"]), 2, 0)).tolist(),
        "x": site.rounded(atlas["x"], 1), "y": site.rounded(atlas["y"], 1),
        "flow_drop": single["flow_drop"].astype(int).tolist(), "pairs_lost": single["pairs_lost"].astype(int).tolist(),
        "removed": {s: atlas[f"removed_{s}"].astype(int).tolist() for s in STRATEGIES},
        "silenced": {s: atlas[f"silenced_{s}"].astype(int).tolist() for s in STRATEGIES},
    }
    n = len(expected["name"])
    lengths = {k: len(v) for k, v in exported.items() if isinstance(v, list) and k not in ("superclasses", "anchors")}
    if set(lengths.values()) != {n}:
        return f"column lengths {lengths}, expected {n}"
    return first_difference({k: exported[k] for k in expected}, expected)


def check_compartments(exported: dict) -> str | None:
    """compartments.json against brain_vnc_comparison.json, with the stored curves checked for shape."""
    report = result_json("brain_vnc_comparison.json")
    stripped = json.loads(json.dumps(exported))
    for name, entry in stripped["compartments"].items():
        curves = entry.pop("curves")
        if set(curves) != set(STRATEGIES):
            return f"{name}: curves for {sorted(curves)}"
        for strategy, curve in curves.items():
            x, flow = np.asarray(curve["fraction_removed"]), np.asarray(curve["flow"])
            if len(x) != len(flow) or x[0] != 0 or (np.diff(x) <= 0).any() or (np.diff(flow) > 0).any():
                return f"{name} {strategy}: malformed curve"
            if flow[0] != entry["intact_flow"]:
                return f"{name} {strategy}: curve starts at {flow[0]}, intact flow is {entry['intact_flow']}"
    for entry in report["compartments"].values():
        for scores in entry["scores"].values():
            for key in [k for k in scores if k.endswith("_trials")]:
                del scores[key]
    return first_difference(stripped, report)


def check() -> str:
    if not (WEB_DATA / "manifest.json").exists():
        raise Skip("web/public/data has not been exported")
    problems = []
    files = {p.name for p in WEB_DATA.glob("*.json")} - {"manifest.json"}
    manifest = read_json(WEB_DATA / "manifest.json")["available"]
    if sorted(manifest) != sorted(files):
        problems.append(f"manifest lists {sorted(set(manifest) ^ files)} differently from the files present")
    if set(files) - set(site.SECTIONS):
        problems.append(f"files not produced by the exporter: {sorted(files - set(site.SECTIONS))}")
    missing = sorted(name for name, (_, requires) in site.SECTIONS.items()
                     if name not in files and all((RESULTS / r).exists() for r in requires))
    if missing:
        problems.append(f"not exported although their results exist: {', '.join(missing)}")

    exported = {}
    for name in sorted(files):
        try:
            exported[name] = read_json(WEB_DATA / name)
        except ValueError as error:
            problems.append(f"{name}: {error}")

    has_data = data_available()
    for name, content in exported.items():
        if name not in site.SECTIONS:
            continue
        if name in DATA_FREE:
            expected = roundtrip(site.SECTIONS[name][0]())
            if name == "meta.json":
                for key in ("exported", *(() if has_data else ("neurons",))):
                    expected.pop(key)
                    content = {k: v for k, v in content.items() if k != key}
            difference = first_difference(content, expected)
        elif has_data:
            difference = first_difference(content, roundtrip(site.SECTIONS[name][0]()))
        elif name == "types.json":
            difference = check_types(content)
        else:
            difference = check_compartments(content)
        if difference:
            problems.append(f"{name} differs from its results at {difference}")

    figures = WEB_DATA.parent / "figures"
    sources = {name: RESULTS / name for name in site.FIGURES} | {"hero.png": ASSETS / "hero.png"}
    for path in sorted(figures.glob("*")) if figures.exists() else []:
        source = sources.get(path.name)
        if source is None:
            problems.append(f"figures/{path.name} is not a result figure")
        elif not source.exists() or source.read_bytes() != path.read_bytes():
            problems.append(f"figures/{path.name} differs from {source.relative_to(RESULTS.parent).as_posix()}")
    for name, source in sources.items():
        if source.exists() and not (figures / name).exists():
            problems.append(f"figures/{name} not copied")

    assert not problems, "; ".join(problems)
    mode = "all sections rebuilt" if has_data else "data-free sections rebuilt, types and compartments checked column-wise"
    return f"{len(files)} data files listed exactly in the manifest, no NaN, {mode}; figures identical"


if __name__ == "__main__":
    run(check)
