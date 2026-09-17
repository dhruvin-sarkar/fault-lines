import numpy as np
import pandas as pd
import pytest

from pipeline.removal_strategies import STRATEGIES
from pipeline.run_percolation import report_lines, runs_from_curves

FLOW = {"out_strength": 0.20, "sm_betweenness": 0.23, "betweenness": 0.31, "in_strength": 0.37, "pagerank": 0.44}
PAIRS = {"sm_betweenness": 0.25, "betweenness": 0.27, "out_strength": 0.35, "pagerank": 0.46, "in_strength": 0.48}


def summary(flow: dict = FLOW, passed: bool = True) -> dict:
    strategies = {s: {"auc_flow": flow[s], "auc_reachability": PAIRS[s]} for s in FLOW}
    strategies["random"] = {
        "trials": 3, "auc_flow": 0.57, "auc_flow_ci95": [0.56, 0.58], "auc_flow_trials": [0.55, 0.57, 0.59],
        "auc_reachability": 0.59, "auc_reachability_ci95": [0.58, 0.60],
        "auc_reachability_trials": [0.58, 0.59, 0.60],
    }
    checks = {s: {"auc_flow": True, "auc_reachability": True} for s in FLOW}
    if not passed:
        checks["pagerank"]["auc_flow"] = False
    return {
        "graph": {"cell_types": 11751, "edges": 243439, "sensory_types": 368, "motor_types": 665,
                  "intact_flow": 10647, "intact_reachable_pairs": 237405, "sensory_motor_pairs": 244720},
        "protocol": {"batch_fraction_of_remaining": 0.01, "auc_range": [0, 0.5], "random_trials": 3, "seed": 20260915},
        "strategies": strategies,
        "checkpoint_targeted_below_random": checks,
        "checkpoint_passed": passed,
    }


def thresholds(f_c: dict | None = None) -> dict:
    f_c = f_c or {"out_strength": 0.041, "sm_betweenness": 0.096, "betweenness": 0.090, "in_strength": 0.139,
                  "pagerank": 0.187}
    table = {s: {"f_c": v, "f_c_batch": v} for s, v in f_c.items()}
    table["random"] = {"f_c": 0.283, "f_c_ci95": [0.277, 0.289], "f_c_trials": [0.27, 0.28, 0.30]}
    return {"cutoff": 0.5, "strategies": table}


def text(**kwargs) -> str:
    return "\n".join(report_lines(kwargs.get("summary", summary()), kwargs.get("thresholds", thresholds()), 69))


def table_rows(report: str) -> list[list[str]]:
    lines = report.split("\n")
    start = lines.index("| strategy | AUC, flow capacity | AUC, reachability | f_c |") + 2
    rows = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def test_graph_and_protocol_numbers_come_from_the_summary():
    report = text()
    assert "| cell types | 11,751 |" in report
    assert "| intact reachable S-M pairs | 237,405 of 244,720 (97.0%) |" in report
    assert "removes the 1% of remaining cell types" in report
    assert "Reaching 50% removed takes 69 batches." in report
    assert "- Random removal: 3 trials" in report
    assert "- Seed: 20260915." in report


def test_table_lists_every_strategy_ordered_by_flow_auc_with_its_threshold():
    rows = table_rows(text())
    assert [r[0] for r in rows] == ["weighted out-degree", "sensory-motor betweenness", "betweenness",
                                    "weighted in-degree", "PageRank", "random"]
    assert rows[0][1:] == ["0.200", "0.350", "0.041"]
    assert rows[-1][1:] == ["0.570 (95% CI 0.560 to 0.580)", "0.590 (95% CI 0.580 to 0.600)",
                            "0.283 (95% CI 0.277 to 0.289)"]
    assert len(rows) == len(STRATEGIES)


def test_random_spread_is_the_range_and_sd_over_trials():
    assert "flow capacity AUC ranges from 0.550 to 0.590 (SD 0.020)" in text()


def test_ranking_names_the_most_damaging_strategy_for_each_metric():
    report = text()
    assert "By flow capacity AUC the most damaging order is weighted out-degree (0.200)" in report
    assert "PageRank (0.440); random removal scores 0.570" in report
    assert "By reachability AUC the order is sensory-motor betweenness (0.250), betweenness (0.270)" in report


def test_threshold_order_is_mentioned_only_when_it_differs_from_the_auc_order():
    assert "Ordered by f_c instead, the sequence is weighted out-degree, betweenness, sensory-motor betweenness" in text()
    same_order = thresholds({"out_strength": 0.04, "sm_betweenness": 0.05, "betweenness": 0.06, "in_strength": 0.07,
                             "pagerank": 0.08})
    assert "Ordered by f_c" not in text(thresholds=same_order)


def test_checkpoint_reports_which_strategy_fails():
    assert "on both metrics: met. Every targeted score also lies below" in text()
    assert "on both metrics: not met for PageRank." in text(summary=summary(passed=False))


def test_report_points_to_the_null_model_and_figure_without_quoting_null_results():
    report = text()
    assert "[null_model_validation.md](null_model_validation.md)" in report
    assert "![Flow capacity and reachable sensory-motor pairs under each removal strategy](percolation_curves.png)" in report
    null_section = report.split("## Null model")[1].split("## Figure")[0]
    assert not any(ch.isdigit() for ch in null_section)


def test_report_prose_uses_no_dashes_or_middle_dots():
    report = text()
    for character in (chr(0x2013), chr(0x2014), chr(0x00B7)):
        assert character not in report


def test_runs_from_curves_restores_exact_fractions_in_batch_order():
    n = 7
    curves = pd.DataFrame({
        "strategy": ["random", "random", "random", "pagerank", "pagerank"],
        "trial": [0, 0, 0, 0, 0],
        "batch": [2, 0, 1, 0, 1],
        "fraction_removed": [round(2 / n, 6), 0.0, round(1 / n, 6), 0.0, round(1 / n, 6)],
        "flow": [5, 9, 7, 9, 4],
        "reachable_pairs": [3, 6, 4, 6, 2],
    })
    runs = runs_from_curves(curves, n)
    assert set(runs) == {("random", 0), ("pagerank", 0)}
    assert np.array_equal(runs[("random", 0)]["fraction_removed"], np.array([0, 1, 2]) / n)
    assert runs[("random", 0)]["flow"].tolist() == [9, 7, 5]
    assert runs[("pagerank", 0)]["reachable_pairs"].tolist() == [6, 2]


@pytest.mark.parametrize("missing", ["auc_flow_ci95", "auc_reachability_trials"])
def test_random_entry_must_carry_its_interval_and_trials(missing):
    broken = summary()
    del broken["strategies"]["random"][missing]
    with pytest.raises(KeyError):
        text(summary=broken)
