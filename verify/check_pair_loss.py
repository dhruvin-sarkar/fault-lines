"""Check the lost sensory-motor pairs: counts agree with single removals, and the listed pairs with their counts."""

from pipeline.identify_sensory_motor_sets import MOTOR_SUPERCLASSES
from verify.common import result_csv, result_json, result_text, run


def check() -> str:
    table = result_csv("pair_loss.csv")
    report = result_json("pair_loss.json")
    single = result_csv("single_removal_impacts.csv")
    sets = result_json("sensory_motor_sets.json")
    sensory, motor = set(sets["sensory"]), set(sets["motor"])

    assert table["cell_type"].is_unique, "A type appears twice in pair_loss.csv"
    losing = single[single["pairs_lost"] > 0].set_index("cell_type")["pairs_lost"]
    assert set(table["cell_type"]) == set(losing.index), \
        f"{len(set(table['cell_type']) ^ set(losing.index))} types differ from those with pairs_lost > 0"
    indexed = table.set_index("cell_type")
    assert (indexed["pairs_lost"] == losing.reindex(indexed.index)).all(), "pairs_lost differs from single removal"
    assert (table["pairs_lost"] == table["own_pairs"] + table["other_pairs"]).all(), "pairs_lost != own + other"
    role = table["cell_type"].map(lambda t: "sensory" if t in sensory else "motor" if t in motor else "other")
    assert (table["role"] == role).all(), "role differs from the sensory and motor sets"
    assert (table.loc[table["role"] == "other", "own_pairs"] == 0).all(), "A type outside both sets has own pairs"
    assert (table.loc[table["role"] == "sensory", "own_pairs"] <= len(motor)).all(), "Sensory own pairs exceed |M|"
    assert (table.loc[table["role"] == "motor", "own_pairs"] <= len(sensory)).all(), "Motor own pairs exceed |S|"
    order = table.sort_values(["other_pairs", "pairs_lost", "cell_type"], ascending=[False, False, True])
    assert order["cell_type"].tolist() == table["cell_type"].tolist(), "pair_loss.csv is not in its stated order"

    others = indexed[indexed["other_pairs"] > 0]
    assert set(report["types"]) == set(others.index), "pair_loss.json lists different types from the CSV"
    assert report["types_with_pairs_lost"] == len(table), "types_with_pairs_lost differs"
    assert report["types_with_other_pairs"] == len(others), "types_with_other_pairs differs"
    assert report["other_pairs_total"] == int(table["other_pairs"].sum()), "other_pairs_total differs"
    assert report["intact_reachable_pairs"] == int(single["intact_reachable_pairs"].iloc[0]), "intact pairs differ"
    assert report["motor_superclass_order"] == list(MOTOR_SUPERCLASSES), "motor superclass order differs"

    superclass = result_csv("type_atlas.csv").set_index("cell_type")["superclass"]
    rank = {c: i for i, c in enumerate(MOTOR_SUPERCLASSES)}
    own_sensory = indexed.loc[indexed["role"] == "sensory", "own_pairs"]
    for name, groups in report["types"].items():
        pairs = [(g["sensory"], m) for g in groups for m in g["motors"]]
        row = others.loc[name]
        assert len(pairs) == len(set(pairs)) == row["other_pairs"], f"{name}: listed pairs differ from other_pairs"
        assert len({s for s, _ in pairs}) == row["sensory_types_cut"], f"{name}: sensory_types_cut differs"
        assert len({m for _, m in pairs}) == row["motor_types_cut"], f"{name}: motor_types_cut differs"
        assert all(s in sensory and m in motor and name not in (s, m) for s, m in pairs), f"{name}: a pair is invalid"
        assert [(-len(g["motors"]), g["sensory"]) for g in groups] == sorted((-len(g["motors"]), g["sensory"])
                                                                              for g in groups), f"{name}: source order"
        for g in groups:
            assert len(g["motors"]) <= g["reach"] == own_sensory.get(g["sensory"], 0), \
                f"{name}: reach of {g['sensory']} differs from its own pairs"
            keys = [(rank.get(superclass.get(m), len(rank)), m) for m in g["motors"]]
            assert keys == sorted(keys), f"{name}: motors of {g['sensory']} are not in the stated order"

    text = result_text("pair_loss.md")
    assert f"{len(table):,} types disconnect at least one pair" in text, "Report type count differs"
    for row in others.itertuples():
        assert (f"| `{row.Index}` ({row.superclass}) | {row.role} | {row.pairs_lost:,} | {row.own_pairs:,} | "
                f"{row.other_pairs:,} |") in text, f"Report row for {row.Index} differs"
    return (f"{len(table)} types reproduce pairs_lost exactly; {len(others)} disconnect "
            f"{int(others['other_pairs'].sum())} pairs between other types, each listed once in its stated order")


if __name__ == "__main__":
    run(check)
