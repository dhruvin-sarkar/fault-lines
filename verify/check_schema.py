"""Check the schema notes name every field the pipeline relies on and agree with the graph and other reports."""

import re

from pipeline.common import RESULTS
from pipeline.schema_discovery import COMPARTMENT_ROIS, REQUIRED_FIELDS
from verify.common import result_json, result_text, run


def check() -> str:
    text = result_text("schema.md")
    header = re.search(r"^(\d+) `:Neuron` nodes, (\d+) with a cell type, (\d+) distinct types\.$", text, re.MULTILINE)
    assert header, "schema.md lacks the neuron, typed-neuron and type totals"
    neurons, typed, types = (int(g) for g in header.groups())
    assert 0 < typed <= neurons, f"{typed} typed neurons vs {neurons} neurons"

    counts = {m.group(1): int(m.group(2)) for m in re.finditer(r"^\| (\w+) \| (\d+) \|$", text, re.MULTILINE)}
    for role, prop in REQUIRED_FIELDS.items():
        assert f"- {role}: `{prop}`" in text, f"schema.md does not list the field {prop} ({role})"
        assert prop in counts, f"schema.md has no non-null count for {prop}"
    assert counts["type"] == typed, f"type is non-null on {counts['type']} neurons, header says {typed} typed"
    for rois in COMPARTMENT_ROIS.values():
        for roi in rois:
            assert f"- `{roi}`" in text, f"Top-level ROI {roi} missing from schema.md"

    graph = result_json("fragility_scores.json")["graph"]
    assert graph["cell_types"] == types, f"Graph has {graph['cell_types']} types, schema.md reports {types}"

    if (RESULTS / "bilateral_symmetry.md").exists():
        stated = re.search(r"Among ([\d,]+) typed neurons", result_text("bilateral_symmetry.md"))
        assert stated is None or int(stated.group(1).replace(",", "")) == typed, \
            "bilateral_symmetry.md quotes a different typed-neuron count"
    return f"{neurons:,} neurons, {typed:,} typed, {types:,} types; {len(REQUIRED_FIELDS)} required fields documented"


if __name__ == "__main__":
    run(check)
