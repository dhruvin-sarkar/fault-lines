"""Check the degree-preserving null-model test: ensemble size, p-values, Bonferroni verdicts, report and site export."""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import export.build_static_json as site
from pipeline.common import RESULTS, WEB_DATA
from pipeline.null_model import ALPHA, N_NULLS, NULL_RUNS_DIR, empirical_p_value_lower, null_seed
from pipeline.removal_strategies import STRATEGIES, STRATEGY_LABELS
from pipeline.run_percolation import RANDOM_TRIALS
from verify.common import Skip, close, first_difference, read_json, run

METRICS = ("auc_flow", "auc_reachability")
# null_model_scores.csv is written with six significant digits.
REL = 2e-6
READINGS = {
    "more_fragile": "H is supported",
    "above_null_mean": "the real graph is, if anything, more robust",
    "not_significant": "H is not supported at the corrected threshold",
}


def ensemble_size(n: int, report: str) -> str:
    """The ensemble size against the pre-registered one; a different size must be reported as a deviation.

    Parameters: ``n`` is the number of randomized graphs scored and ``report`` the text of null_model_validation.md.
    Returns a note for the summary line, empty when ``n`` is the pre-registered size.
    """
    if n == N_NULLS:
        return ""
    gap = f"{n} randomized graphs scored, {N_NULLS} pre-registered ({abs(N_NULLS - n)} {'short' if n < N_NULLS else 'over'})"
    stated = re.search(r"deviation", report, re.IGNORECASE) and f"{n} randomized graphs" in report
    assert stated, f"{gap}, and null_model_validation.md does not report it as a deviation"
    return f"; deviation reported: {gap}"


def check_scores(scores: pd.DataFrame, n: int) -> None:
    assert len(scores) == n * len(STRATEGIES), f"{len(scores)} score rows, expected {n} x {len(STRATEGIES)}"
    assert not scores.duplicated(["null_index", "strategy"]).any(), "Duplicate (null graph, strategy) rows"
    assert set(scores["strategy"]) == set(STRATEGIES), f"Strategies in scores: {sorted(set(scores['strategy']))}"
    assert set(scores["null_index"]) == set(range(n)), "Null indices are not 0 .. N-1"
    assert (scores["seed"] == scores["null_index"].map(null_seed)).all(), "Seeds differ from the pre-registered scheme"
    expected_trials = np.where(scores["strategy"] == "random", RANDOM_TRIALS, 1)
    assert (scores["trials"] == expected_trials).all(), "Trial counts per strategy differ from the protocol"
    assert scores[list(METRICS)].apply(lambda c: c.between(0, 1)).all().all(), "Null AUC outside [0, 1]"


def check_runs(scores: pd.DataFrame, runs: Path) -> int:
    """Scores against the saved per-graph runs, when the local run cache is on disk; returns the files read."""
    if not runs.exists():
        return 0
    checked = 0
    for row in scores.itertuples():
        path = runs / f"null_{row.null_index:03d}_{row.strategy}.npz"
        assert path.exists(), f"{path.name} missing from the run cache"
        try:
            with np.load(path) as data:
                flow, reach = data["auc_flow"], data["auc_reachability"]
        except (ValueError, OSError) as error:
            raise AssertionError(f"{path.name} is unreadable: {error}") from error
        assert len(flow) == row.trials, f"{path.name}: {len(flow)} trials, scores say {row.trials}"
        assert close([flow.mean(), reach.mean()], [row.auc_flow, row.auc_reachability], rel=1e-5), \
            f"{path.name}: mean AUC differs from null_model_scores.csv"
        checked += 1
    return checked


def check_tests(summary: dict, scores: pd.DataFrame, real: dict) -> None:
    n = summary["n_nulls"]
    floor = 1 / (n + 1)
    for strategy in STRATEGIES:
        null = scores[scores["strategy"] == strategy]
        for metric in METRICS:
            s = summary["strategies"][strategy][metric]
            label = f"{strategy} {metric}"
            values = null[metric].to_numpy()
            assert close(s["real"], real[strategy][metric]), f"{label}: real AUC differs from fragility_scores.json"
            assert floor <= s["p_value"] <= 1, f"{label}: p = {s['p_value']} outside [1/{n + 1}, 1]"
            assert close(s["p_value"], (1 + s["n_at_or_below_real"]) / (1 + n)), f"{label}: p != (1 + k) / (1 + N)"
            recomputed = empirical_p_value_lower(s["real"], values)
            # A null AUC within the CSV rounding of the real AUC may fall on either side of it.
            ties = int(np.sum(np.abs(values - s["real"]) <= REL * abs(s["real"])))
            k = round(recomputed * (1 + n)) - 1
            assert abs(s["n_at_or_below_real"] - k) <= ties, \
                f"{label}: p = {s['p_value']:.4f} from {s['n_at_or_below_real']} graphs, scores give " \
                f"{recomputed:.4f} from {k}"
            assert close([s["null_mean"], s["null_min"], s["null_max"]], [values.mean(), values.min(), values.max()],
                         rel=1e-5), f"{label}: null distribution summary differs from the scores"
            # Rounding each score to six significant digits moves a narrow SD by up to about 1e-6 in absolute terms.
            assert close(s["null_sd"], values.std(ddof=1), rel=1e-5, abs_tol=2e-6), \
                f"{label}: null SD {s['null_sd']:.6g} differs from the scores ({values.std(ddof=1):.6g})"
            assert close(s["z_score"], (s["real"] - s["null_mean"]) / s["null_sd"]), f"{label}: z-score arithmetic"
            assert s["significant"] == (s["p_value"] < ALPHA), f"{label}: Bonferroni verdict wrong"


def check_report(summary: dict, report: str) -> None:
    n = summary["n_nulls"]
    assert "one-sided" in report and "**lower**" in report, "null_model_validation.md lost the directional hypothesis"
    assert f"{ALPHA:.4f}" in report, "null_model_validation.md states a different threshold"
    for strategy in STRATEGIES:
        for metric in METRICS:
            s = summary["strategies"][strategy][metric]
            row = f"| {STRATEGY_LABELS[strategy]} | {s['real']:.4f} |"
            assert row in report and f"| {s['p_value']:.4f} |" in report and f"| {s['n_at_or_below_real']} / {n} |" \
                in report, f"null_model_validation.md row for {strategy} {metric} differs"
        s = summary["strategies"][strategy]["auc_flow"]
        reading = next(line for line in report.splitlines() if line.startswith(f"- **{STRATEGY_LABELS[strategy]}**"))
        expected = READINGS[site.null_verdict(s)]
        assert expected in reading, f"null_model_validation.md reading for {strategy} should say '{expected}'"


def check_export(summary: dict, results: Path, web_data: Path) -> None:
    path = web_data / "nulls.json"
    assert path.exists(), "web/public/data/nulls.json not exported although the null model has finished"
    manifest = read_json(web_data / "manifest.json")["available"]
    assert "nulls.json" in manifest, "nulls.json is not listed in the site manifest"
    exported = read_json(path)
    difference = first_difference(exported, json.loads(json.dumps(site.nulls(results))))
    assert difference is None, f"nulls.json differs from the results at {difference}"
    assert exported["n_nulls"] == summary["n_nulls"] and close(exported["alpha"], ALPHA)
    for strategy in STRATEGIES:
        for metric in METRICS:
            entry = exported["strategies"][strategy][metric]
            assert entry["significant"] == (entry["p_value"] < exported["alpha"]), f"nulls.json {strategy} {metric}"
            assert sum(entry["distribution"]["counts"]) == summary["n_nulls"], f"nulls.json {strategy} {metric} counts"


def check(results: Path = RESULTS, web_data: Path = WEB_DATA, runs: Path = NULL_RUNS_DIR) -> str:
    if not (results / "null_model_summary.json").exists():
        partial = [n for n in ("null_model_scores.csv", "null_distribution.png") if (results / n).exists()]
        assert not partial, f"null_model_summary.json is absent but {', '.join(partial)} exist"
        assert not (web_data / "nulls.json").exists(), "nulls.json is exported but null_model_summary.json is absent"
        raise Skip("results/null_model_summary.json not written yet; the null-model run has not finished")

    summary = read_json(results / "null_model_summary.json")
    report = (results / "null_model_validation.md").read_text(encoding="utf-8")
    n = summary["n_nulls"]
    note = ensemble_size(n, report)
    assert f"N = {N_NULLS} randomized graphs" in report, "null_model_validation.md changed the pre-registered N"
    assert close(summary["alpha"], ALPHA) and close(ALPHA, 0.05 / 6), f"alpha {summary['alpha']}, pre-registered 0.05 / 6"
    assert set(summary["strategies"]) == set(STRATEGIES), f"Strategies {sorted(summary['strategies'])}"

    scores = pd.read_csv(results / "null_model_scores.csv")
    check_scores(scores, n)
    files = check_runs(scores, runs)
    check_tests(summary, scores, read_json(results / "fragility_scores.json")["strategies"])
    check_report(summary, report)
    assert (results / "null_distribution.png").exists(), "null_distribution.png missing"
    check_export(summary, results, web_data)

    significant = [s for s in STRATEGIES if summary["strategies"][s]["auc_flow"]["significant"]]
    cache = f", {files} run files match" if files else ""
    return (f"N = {n}, p floor 1/{n + 1}, every p reproduced from {len(scores)} scores{cache}; nulls.json matches; "
            f"significant at {ALPHA:.4f}: {', '.join(significant) or 'none'}{note}")


if __name__ == "__main__":
    run(check)
