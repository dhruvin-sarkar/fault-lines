"""Record the live neuPrint schema: neuron properties, superclass annotations, laterality encoding, ROI groups."""

import pandas as pd
from neuprint import fetch_roi_hierarchy

from pipeline.common import DATASET, RESULTS, get_client

# Properties the pipeline depends on, keyed by the role they play downstream.
REQUIRED_FIELDS = {
    "cell type": "type",
    "superclass (sensory / descending / motor)": "superclass",
    "sensory modality": "class",
    "soma hemisphere": "somaSide",
    "nerve-root hemisphere (neurons without a CNS soma)": "rootSide",
    "hemisphere-suffixed instance name": "instance",
    "per-ROI synapse counts": "roiInfo",
}
# Top-level children of CNS in the ROI hierarchy, grouped into the two compartments compared downstream.
COMPARTMENT_ROIS = {"brain": ("CentralBrain", "Optic(L)", "Optic(R)"), "vnc": ("VNC",)}


def markdown_table(frame: pd.DataFrame) -> list[str]:
    header = "| " + " | ".join(frame.columns) + " |"
    rule = "|" + "---|" * len(frame.columns)
    rows = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return [header, rule, *rows]


def main() -> None:
    client = get_client()
    roi_names = set(client.fetch_datasets()[DATASET]["ROIs"])
    counts = client.fetch_custom(
        "MATCH (n:Neuron) UNWIND keys(n) AS k WITH k WHERE NOT k CONTAINS '(' "
        "RETURN k AS property, count(*) AS non_null ORDER BY non_null DESC"
    )
    counts = counts[~counts["property"].isin(roi_names)]
    missing = set(REQUIRED_FIELDS.values()) - set(counts["property"])
    if missing:
        raise RuntimeError(f"Required neuron properties absent from {DATASET}: {sorted(missing)}")

    totals = {
        "neurons": client.fetch_custom("MATCH (n:Neuron) RETURN count(n) AS c")["c"].iloc[0],
        "typed_neurons": client.fetch_custom("MATCH (n:Neuron) WHERE n.type IS NOT NULL RETURN count(n) AS c")["c"].iloc[0],
        "types": client.fetch_custom("MATCH (n:Neuron) WHERE n.type IS NOT NULL RETURN count(DISTINCT n.type) AS c")["c"].iloc[0],
    }
    superclasses = client.fetch_custom(
        "MATCH (n:Neuron) WHERE n.type IS NOT NULL "
        "RETURN n.superclass AS superclass, n.class AS class, count(*) AS neurons, count(DISTINCT n.type) AS types "
        "ORDER BY superclass, neurons DESC"
    )
    sides = client.fetch_custom(
        "MATCH (n:Neuron) WHERE n.type IS NOT NULL "
        "WITH n, CASE WHEN n.instance ENDS WITH '_L' THEN 'L' WHEN n.instance ENDS WITH '_R' THEN 'R' "
        "WHEN n.instance ENDS WITH '_M' THEN 'M' WHEN n.instance IS NULL THEN 'none' ELSE 'other' END AS suffix "
        "RETURN n.somaSide AS somaSide, n.rootSide AS rootSide, suffix AS instance_suffix, count(*) AS neurons "
        "ORDER BY neurons DESC"
    )
    hierarchy = fetch_roi_hierarchy(include_subprimary=False, format="dict")["CNS"]
    top_level = sorted(hierarchy)
    for rois in COMPARTMENT_ROIS.values():
        absent = set(rois) - set(top_level)
        if absent:
            raise RuntimeError(f"Expected top-level ROIs {sorted(absent)} under CNS, found {top_level}")

    lines = [
        f"# neuPrint schema: {DATASET}",
        "",
        f"{int(totals['neurons'])} `:Neuron` nodes, {int(totals['typed_neurons'])} with a cell type, "
        f"{int(totals['types'])} distinct types.",
        "",
        "## Neuron properties",
        "",
        *markdown_table(counts.rename(columns={"non_null": "non-null neurons"})),
        "",
        "## Fields used downstream",
        "",
        *[f"- {role}: `{prop}`" for role, prop in REQUIRED_FIELDS.items()],
        "",
        "## Superclass and class annotations (typed neurons)",
        "",
        *markdown_table(superclasses),
        "",
        "## Laterality encoding (typed neurons)",
        "",
        "`somaSide` records the hemisphere of the cell body. Neurons without a soma in the CNS (sensory neurons) "
        "carry `rootSide`, the hemisphere of the nerve root they enter through. The `instance` suffix repeats "
        "whichever of the two is set.",
        "",
        *markdown_table(sides),
        "",
        "## Top-level ROIs under CNS",
        "",
        *[f"- `{name}`" for name in top_level],
        "",
        "Compartments used for the brain / ventral nerve cord comparison: "
        + "; ".join(f"{k} = {', '.join(f'`{r}`' for r in v)}" for k, v in COMPARTMENT_ROIS.items())
        + ". `CV` (the neck connective) belongs to neither.",
    ]
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / "schema.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(counts)} properties, {int(totals['types'])} types)")


if __name__ == "__main__":
    main()
