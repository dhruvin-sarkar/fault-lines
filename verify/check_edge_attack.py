"""Check the connection-removal summary against its per-trial table, including the reported critical fractions."""

import numpy as np

from pipeline.common import RESULTS
from pipeline.edge_attack import ORDERS, build_summary, critical_fraction, load_trials, report_lines
from verify.common import close, first_difference, result_json, result_text, run, same_text


def check() -> str:
    summary = result_json("edge_attack.json")
    edges = summary["edges"]
    trials = load_trials(RESULTS / "edge_attack.csv", edges)
    assert set(trials) == set(ORDERS) and all(trials.values()), "edge_attack.csv lacks a removal order"
    assert len(trials["random"]) == summary["random_trials"], f"{len(trials['random'])} random trials in the CSV"

    for order, runs in trials.items():
        for i, run_ in enumerate(runs):
            flow, pairs = np.asarray(run_["flow"]), np.asarray(run_["reachable_pairs"])
            assert flow[0] == summary["intact_flow"], f"{order} trial {i}: intact flow differs"
            assert (np.diff(run_["fraction_removed"]) > 0).all(), f"{order} trial {i}: fractions not increasing"
            assert (np.diff(flow) <= 0).all() and (np.diff(pairs) <= 0).all(), f"{order} trial {i}: curve increases"

        entry = summary["orders"][order]
        values = [critical_fraction(r["fraction_removed"], r["flow"]) for r in runs]
        assert close(entry["critical_fraction_trials"], values), f"{order}: per-trial critical fractions differ"
        if None in values:
            assert entry["critical_fraction"] is None, f"{order}: a mean is reported although a trial never halves"
        else:
            assert close(entry["critical_fraction"], float(np.mean(values))), \
                f"{order}: reported critical fraction {entry['critical_fraction']} is not the trial mean {np.mean(values)}"
            assert close(entry["critical_fraction_range"], [min(values), max(values)]), f"{order}: range differs"
            assert entry["critical_fraction"] <= runs[0]["fraction_removed"][-1], f"{order}: f_c beyond the removed range"

    expected = build_summary(trials, edges)
    assert same_text(result_text("edge_attack.md"), "\n".join(report_lines(expected))), "edge_attack.md is out of date"
    difference = first_difference(summary, expected)
    assert difference is None, (f"edge_attack.json differs from a rebuild from edge_attack.csv at {difference} "
                                "(rebuild with python -m pipeline.edge_attack --from-csv)")
    fractions = {o: summary["orders"][o]["critical_fraction"] for o in ORDERS}
    text = ", ".join(f"{o} {'never' if v is None else f'{v:.3f}'}" for o, v in fractions.items())
    return f"{sum(len(r) for r in trials.values())} runs over {edges:,} connections; flow halves at {text}; report current"


if __name__ == "__main__":
    run(check)
