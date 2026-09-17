"""Check the type atlas: placement bounds, neuropil outlines and the removal replay against the percolation curves."""

import numpy as np

from pipeline.removal_strategies import STRATEGIES
from verify.common import result_csv, result_json, run


def check() -> str:
    layout = result_json("type_atlas.json")
    atlas = result_csv("type_atlas.csv")
    types = len(atlas)
    assert layout["types"] == types and atlas["cell_type"].is_unique, f"type_atlas.json counts {layout['types']} types"
    placed = atlas["x"].notna() & atlas["y"].notna()
    assert layout["types_placed"] == int(placed.sum()), f"types_placed {layout['types_placed']} vs {int(placed.sum())}"
    width, height = layout["canvas"]
    assert atlas.loc[placed, "x"].between(0, width).all() and atlas.loc[placed, "y"].between(0, height).all(), \
        "A type is placed outside the canvas"

    compartments = result_csv("type_compartments.csv").set_index("cell_type")["compartment"]
    assert atlas.set_index("cell_type")["compartment"].equals(compartments.reindex(atlas["cell_type"])), \
        "Atlas compartments differ from type_compartments.csv"

    outlines = {o["neuropil"]: o for o in layout["outlines"]}
    assert len(outlines) == len(layout["outlines"]), "Duplicate neuropil outlines"
    assert layout["cns_outline"].startswith("M") and all(o["path"].startswith("M") for o in outlines.values()), \
        "Empty or malformed outline path"
    scored = set(result_csv("regional_impact.csv")["neuropil"])
    drawn = {n for n, o in outlines.items() if o["scored"]}
    assert drawn <= scored, f"Outlines marked scored but absent from regional_impact.csv: {sorted(drawn - scored)}"
    assert not scored & {n for n, o in outlines.items() if not o["scored"]}, "A scored neuropil is drawn as unscored"
    unmeshed = sorted(scored - drawn)

    curves = result_csv("percolation_curves.csv")
    for strategy in STRATEGIES:
        replay = layout["replay"][strategy]
        rows = curves[(curves["strategy"] == strategy) & (curves["trial"] == 0)].sort_values("batch")
        fractions = np.asarray(replay["fraction_removed"])
        assert len(fractions) == len(rows) and np.allclose(fractions, rows["fraction_removed"], rtol=0, atol=1e-6), \
            f"{strategy}: replay fractions differ from percolation_curves.csv"
        removed_types = np.asarray(replay["removed_types"])
        assert (removed_types == np.rint(fractions * types)).all(), f"{strategy}: removed counts differ from fractions"

        removed, silenced = atlas[f"removed_{strategy}"].to_numpy(), atlas[f"silenced_{strategy}"].to_numpy()
        batches = len(fractions) - 1
        per_batch = np.bincount(removed[removed > 0], minlength=batches + 1)
        assert (per_batch[1:] == np.diff(removed_types)).all() and per_batch[0] == 0, \
            f"{strategy}: types removed per batch differ from the replay counts"
        assert int((removed == -1).sum()) == types - removed_types[-1], f"{strategy}: never-removed count differs"
        assert ((removed == -1) | (silenced == -1) | (removed > silenced)).all(), \
            f"{strategy}: a type is recorded as cut off after it was removed"

        newly = np.bincount(silenced[silenced >= 0], minlength=batches + 1)
        avalanche = rows["avalanche"].to_numpy()[1:].astype(int)
        assert (newly[1:] == avalanche).all(), f"{strategy}: types newly cut off per batch differ from the avalanche sizes"
        counts = np.asarray(replay["silenced_types"])
        assert counts[0] == newly[0], f"{strategy}: initially unreachable count differs"
        for b in range(1, batches + 1):
            lost = int(((removed == b) & (silenced >= 0) & (silenced < b)).sum())
            assert counts[b] == counts[b - 1] + newly[b] - lost, f"{strategy}: cut-off count at batch {b} does not add up"
    missing = f" (no published mesh for {', '.join(unmeshed)})" if unmeshed else ""
    return (f"{int(placed.sum()):,} of {types:,} types placed, {len(drawn)} of {len(scored)} scored neuropils outlined"
            f"{missing}; removal and cut-off replay for {len(STRATEGIES)} strategies matches the curves and avalanche sizes")


if __name__ == "__main__":
    run(check)
