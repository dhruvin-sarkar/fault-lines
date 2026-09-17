"""Check the literature validation tests: group sizes, effect sizes, the flow-drop test rerun and the report."""

import numpy as np

from pipeline.hidden_bottleneck import percentile_ranks
from pipeline.literature_validation import ALTERNATIVE_P9, CURATED, POSITIVE_CONTROL, SCORES, rank_test, report_lines
from verify.common import close, first_difference, result_csv, result_json, result_text, run, same_text


def check() -> str:
    report = result_json("literature_validation.json")
    types = result_json("fragility_scores.json")["graph"]["cell_types"]
    curated = [c[0] for c in CURATED]
    control = POSITIVE_CONTROL[0]
    sets = {"primary": curated, "with_positive_control": curated + [control],
            "DNp71_for_DNp09": [ALTERNATIVE_P9 if t == "DNp09" else t for t in curated]}
    assert set(report["tests"]) == set(sets), f"Test sets {sorted(report['tests'])}"
    assert list(report["curated_types"]) == curated + [control], "Curated types differ from the pre-registered list"

    for name, members in sets.items():
        assert set(report["tests"][name]) == set(SCORES), f"{name}: scores {sorted(report['tests'][name])}"
        for score, r in report["tests"][name].items():
            label = f"{name}/{score}"
            assert r["n_curated"] == len(members) and r["n_curated"] + r["n_other"] == types, f"{label}: group sizes"
            assert 0 <= r["p_value"] <= 1 and 0 <= r["auc"] <= 1, f"{label}: p or AUC out of range"
            assert close(r["auc"], r["U"] / (r["n_curated"] * r["n_other"])), f"{label}: AUC != U / (n1 n2)"
            assert close(r["rank_biserial"], 2 * r["auc"] - 1), f"{label}: rank-biserial != 2 AUC - 1"
            assert 0 <= r["median_percentile"] <= 100, f"{label}: median percentile out of range"
            if name != "DNp71_for_DNp09":
                percentiles = [report["curated_types"][t][f"{score}_percentile"] for t in members]
                assert close(r["median_percentile"], float(np.median(percentiles))), f"{label}: median percentile differs"

    single = result_csv("single_removal_impacts.csv").set_index("cell_type")["flow_drop"].astype(float)
    percentile = percentile_ranks(single)
    for t, entry in report["curated_types"].items():
        assert entry["flow_drop"] == single[t], f"{t}: flow_drop {entry['flow_drop']} vs single removal {single[t]}"
        assert close(entry["flow_drop_percentile"], percentile[t]), f"{t}: flow-drop percentile differs"
        assert all(0 <= entry[f"{s}_percentile"] <= 100 for s in SCORES), f"{t}: percentile out of range"
    for name, members in sets.items():
        rerun = rank_test(single, members)
        difference = first_difference(report["tests"][name]["flow_drop"], rerun)
        assert difference is None, f"{name}/flow_drop test does not reproduce from single_removal_impacts.csv at {difference}"

    assert same_text(result_text("literature_validation.md"), "\n".join(report_lines(report))), \
        "literature_validation.md is out of date with the JSON"
    primary = report["tests"]["primary"]["sm_betweenness"]
    verdict = "significant" if primary["p_value"] < report["alpha"] else "not significant"
    return (f"{len(sets) * len(SCORES)} tests consistent, flow-drop tests reproduced; primary U = {primary['U']:.0f}, "
            f"p = {primary['p_value']:.2g}, AUC = {primary['auc']:.2f} ({verdict}); report current")


if __name__ == "__main__":
    run(check)
