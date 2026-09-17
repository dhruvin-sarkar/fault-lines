"""Check the sensory and descending/motor sets: pre-registered sizes, disjointness and agreement with their report."""

import re

from pipeline.identify_sensory_motor_sets import MOTOR_SUPERCLASSES, SENSORY_SUPERCLASSES
from verify.common import result_csv, result_json, result_text, run

# results/preregistration.md: "S: 368 primary sensory types; M: 665 descending and motor types".
SENSORY_TYPES = 368
MOTOR_TYPES = 665


def check() -> str:
    sets = result_json("sensory_motor_sets.json")
    sensory, motor = sets["sensory"], sets["motor"]
    assert len(sensory) == SENSORY_TYPES, f"{len(sensory)} sensory types, pre-registered {SENSORY_TYPES}"
    assert len(motor) == MOTOR_TYPES, f"{len(motor)} descending/motor types, pre-registered {MOTOR_TYPES}"
    for name, members in (("sensory", sensory), ("motor", motor)):
        assert members == sorted(set(members)), f"The {name} set is not sorted and unique"
    shared = set(sensory) & set(motor)
    assert not shared, f"{len(shared)} types in both sets, e.g. {sorted(shared)[:5]}"
    assert tuple(sets["sensory_superclasses"]) == SENSORY_SUPERCLASSES, "Sensory superclasses differ from the pipeline"
    assert tuple(sets["motor_superclasses"]) == MOTOR_SUPERCLASSES, "Motor superclasses differ from the pipeline"

    graph = result_json("fragility_scores.json")["graph"]
    assert (graph["sensory_types"], graph["motor_types"]) == (len(sensory), len(motor)), "Graph summary set sizes differ"
    assert graph["sensory_motor_pairs"] == len(sensory) * len(motor), "sensory_motor_pairs is not |S| x |M|"

    text = result_text("sensory_motor_sets.md")
    for label, members in (("S", sensory), ("M", motor)):
        section = re.search(rf"^## {label}: (\d+) [^\n]*\n\n([^\n]*)$", text, re.MULTILINE)
        assert section, f"sensory_motor_sets.md has no {label} listing"
        assert int(section.group(1)) == len(members), f"Report heading gives {section.group(1)} {label} types"
        assert re.findall(r"`([^`]+)`", section.group(2)) == members, f"Report listing of {label} differs from the JSON"
        rows = re.findall(rf"^\| `\w+` \| {label} \| (\d+) \| \d+ \|$", text, re.MULTILINE)
        assert sum(map(int, rows)) == len(members), f"Superclass table counts for {label} do not sum to {len(members)}"

    names = set(result_csv("single_removal_impacts.csv")["cell_type"])
    absent = (set(sensory) | set(motor)) - names
    assert not absent, f"{len(absent)} set members are not cell types of the graph, e.g. {sorted(absent)[:5]}"
    return f"|S| = {len(sensory)}, |M| = {len(motor)}, disjoint, all graph types, report agrees"


if __name__ == "__main__":
    run(check)
