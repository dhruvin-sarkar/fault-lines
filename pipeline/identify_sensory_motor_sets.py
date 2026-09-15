"""Derive the primary sensory (S) and descending/motor (M) cell-type sets from neuPrint superclass annotations."""

import json

import pandas as pd

from pipeline.common import DATASET, RESULTS, get_client

SENSORY_SUPERCLASSES = ("cb_sensory", "ol_sensory", "vnc_sensory", "sensory_ascending", "sensory_descending")
MOTOR_SUPERCLASSES = ("descending_neuron", "cb_motor", "vnc_motor")
SETS_JSON = RESULTS / "sensory_motor_sets.json"

TYPE_SUPERCLASS_QUERY = """\
MATCH (n:Neuron)
WHERE n.type IS NOT NULL
RETURN n.type AS type, n.superclass AS superclass, count(*) AS neurons
ORDER BY type, neurons DESC"""


def assign_type_superclass(rows: pd.DataFrame) -> pd.DataFrame:
    """Give each type the superclass held by most of its neurons (ties broken alphabetically).

    Args:
        rows: columns ``type``, ``superclass`` (may be null), ``neurons``.

    Returns:
        One row per type: ``type``, ``superclass``, ``neurons`` (all neurons of the type),
        ``majority_share`` (fraction of neurons carrying the assigned superclass).
    """
    rows = rows.assign(superclass=rows["superclass"].fillna("unannotated"))
    ranked = rows.sort_values(["type", "neurons", "superclass"], ascending=[True, False, True])
    top = ranked.drop_duplicates("type").set_index("type")
    total = rows.groupby("type")["neurons"].sum()
    return pd.DataFrame(
        {"superclass": top["superclass"], "neurons": total, "majority_share": top["neurons"] / total}
    ).reset_index()


def derive_sets(types: pd.DataFrame) -> dict[str, list[str]]:
    """Sorted type names whose assigned superclass is sensory or descending/motor."""
    return {
        "sensory": sorted(types.loc[types["superclass"].isin(SENSORY_SUPERCLASSES), "type"]),
        "motor": sorted(types.loc[types["superclass"].isin(MOTOR_SUPERCLASSES), "type"]),
    }


def load_sensory_motor_sets() -> tuple[list[str], list[str]]:
    """Sensory and descending/motor type names written by :func:`main`."""
    sets = json.loads(SETS_JSON.read_text(encoding="utf-8"))
    return sets["sensory"], sets["motor"]


def main() -> None:
    client = get_client()
    types = assign_type_superclass(client.fetch_custom(TYPE_SUPERCLASS_QUERY))
    sets = derive_sets(types)

    confirmed = set(
        client.fetch_custom(
            "MATCH (n:Neuron) WHERE n.type IN $types RETURN DISTINCT n.type AS type".replace(
                "$types", json.dumps(sets["sensory"] + sets["motor"])
            )
        )["type"]
    )
    for name, members in sets.items():
        if not members:
            raise RuntimeError(f"The {name} set is empty")
        unconfirmed = set(members) - confirmed
        if unconfirmed:
            raise RuntimeError(f"{len(unconfirmed)} {name} types not found in a live query: {sorted(unconfirmed)[:10]}")
    overlap = set(sets["sensory"]) & set(sets["motor"])
    if overlap:
        raise RuntimeError(f"Types assigned to both sets: {sorted(overlap)}")

    n_types = len(types)
    mixed = types[(types["majority_share"] < 1) & types["type"].isin(sets["sensory"] + sets["motor"])]
    by_superclass = (
        types[types["superclass"].isin(SENSORY_SUPERCLASSES + MOTOR_SUPERCLASSES)]
        .groupby("superclass")
        .agg(types=("type", "size"), neurons=("neurons", "sum"))
        .reindex(list(SENSORY_SUPERCLASSES + MOTOR_SUPERCLASSES))
    )

    RESULTS.mkdir(exist_ok=True)
    SETS_JSON.write_text(
        json.dumps(
            {
                "dataset": DATASET,
                "sensory_superclasses": list(SENSORY_SUPERCLASSES),
                "motor_superclasses": list(MOTOR_SUPERCLASSES),
                "query": TYPE_SUPERCLASS_QUERY,
                **sets,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )

    def listing(members: list[str]) -> str:
        return ", ".join(f"`{t}`" for t in members)

    lines = [
        "# Sensory and descending/motor cell-type sets",
        "",
        f"Dataset `{DATASET}`. Every neuron with a cell type was grouped by type and `superclass`; each type takes "
        "the superclass held by the majority of its neurons. The sets are:",
        "",
        f"- **S, primary sensory** (superclass in {', '.join(f'`{s}`' for s in SENSORY_SUPERCLASSES)}): "
        f"{len(sets['sensory'])} types ({len(sets['sensory']) / n_types:.1%} of {n_types}).",
        f"- **M, descending and motor** (superclass in {', '.join(f'`{s}`' for s in MOTOR_SUPERCLASSES)}): "
        f"{len(sets['motor'])} types ({len(sets['motor']) / n_types:.1%} of {n_types}).",
        "",
        "Excluded on purpose: superclasses ending in `_tbc` (annotation still to be confirmed), efferent and "
        "endocrine neurons (neuromodulatory or neurosecretory outputs, not skeletal motor control), and ascending "
        "neurons that are not annotated as sensory.",
        "",
        "All type names above were confirmed to exist in a second live query "
        "(`MATCH (n:Neuron) WHERE n.type IN [...] RETURN DISTINCT n.type`).",
        "",
        "## Query",
        "",
        "```cypher",
        TYPE_SUPERCLASS_QUERY,
        "```",
        "",
        "## Counts by superclass",
        "",
        "| superclass | set | types | neurons |",
        "|---|---|---|---|",
        *[
            f"| `{sc}` | {'S' if sc in SENSORY_SUPERCLASSES else 'M'} | {int(r.types)} | {int(r.neurons)} |"
            for sc, r in by_superclass.iterrows()
        ],
        "",
        f"{len(mixed)} types in S or M contain some neurons with a different superclass; the lowest majority share "
        f"among them is {mixed['majority_share'].min():.2f}." if len(mixed) else "Every type in S or M is annotated "
        "with a single superclass.",
        "",
        f"## S: {len(sets['sensory'])} sensory types",
        "",
        listing(sets["sensory"]),
        "",
        f"## M: {len(sets['motor'])} descending and motor types",
        "",
        listing(sets["motor"]),
        "",
    ]
    (RESULTS / "sensory_motor_sets.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"S = {len(sets['sensory'])} types, M = {len(sets['motor'])} types, of {n_types}; mixed-superclass: {len(mixed)}")


if __name__ == "__main__":
    main()
