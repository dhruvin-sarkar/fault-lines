import json
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import export.build_static_json as static_export
from export.build_static_json import NULL_BINS, NULL_QUANTILES, null_distribution, null_verdict, nulls, split_missing
import pipeline.null_model as null_model
from pipeline.null_model import ALPHA, N_NULLS, null_seed, summarize
from pipeline.removal_strategies import STRATEGIES
from verify.check_null_model import check, ensemble_size
from verify.common import Skip


def write_null_results(folder, n: int = 40, shift: dict | None = None) -> dict:
    """Scores for ``n`` randomized graphs and the summary the null model would write for them."""
    rng = np.random.default_rng(3)
    shift = shift or {}
    rows, real = [], {}
    for strategy in STRATEGIES:
        flow = rng.normal(0.4, 0.01, n)
        reach = rng.normal(0.5, 0.02, n)
        real[strategy] = {"auc_flow": 0.4 + shift.get(strategy, -0.1), "auc_reachability": 0.5}
        for i in range(n):
            rows.append({"null_index": i, "seed": null_seed(i), "strategy": strategy,
                         "trials": 30 if strategy == "random" else 1, "auc_flow": flow[i],
                         "auc_reachability": reach[i], "intact_flow": 100, "intact_pairs": 1000})
    scores = pd.DataFrame(rows)
    scores.to_csv(folder / "null_model_scores.csv", index=False, float_format="%.6g")
    scores = pd.read_csv(folder / "null_model_scores.csv")
    summary = {"n_nulls": n, "alpha": ALPHA, "strategies": summarize(real, scores)}
    (folder / "null_model_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return summary


def test_verdict_separates_significant_non_significant_and_above_the_null_mean():
    assert null_verdict({"significant": True, "real": 0.1, "null_mean": 0.3}) == "more_fragile"
    assert null_verdict({"significant": False, "real": 0.29, "null_mean": 0.3}) == "not_significant"
    assert null_verdict({"significant": False, "real": 0.3, "null_mean": 0.3}) == "not_significant"
    assert null_verdict({"significant": False, "real": 0.31, "null_mean": 0.3}) == "above_null_mean"


def test_distribution_bins_cover_every_value_once():
    values = np.random.default_rng(1).normal(0.5, 0.01, 200)
    d = null_distribution(values)
    assert len(d["counts"]) == NULL_BINS and sum(d["counts"]) == 200
    assert d["lo"] == pytest.approx(values.min(), rel=1e-5)
    assert d["lo"] + NULL_BINS * d["step"] == pytest.approx(values.max(), rel=1e-5)
    assert d["counts"][0] >= 1 and d["counts"][-1] >= 1
    assert d["quantiles"] == sorted(d["quantiles"]) and len(d["quantiles"]) == len(NULL_QUANTILES)
    assert d["quantiles"][2] == pytest.approx(np.median(values), rel=1e-5)


def test_distribution_of_identical_values_has_a_positive_width():
    d = null_distribution([0.25] * 10)
    assert d["step"] > 0 and sum(d["counts"]) == 10
    assert d["lo"] < 0.25 < d["lo"] + NULL_BINS * d["step"]


def test_nulls_section_keeps_every_test_and_adds_verdicts(tmp_path):
    summary = write_null_results(tmp_path, n=N_NULLS, shift={"random": 0.05, "pagerank": -0.001})
    section = nulls(tmp_path)
    assert section["n_nulls"] == N_NULLS and section["n_preregistered"] == N_NULLS
    assert section["p_floor"] == pytest.approx(1 / (N_NULLS + 1), rel=1e-5)
    assert section["alpha"] == pytest.approx(ALPHA)
    assert list(section["strategies"]) == list(STRATEGIES)
    for strategy in STRATEGIES:
        for metric in ("auc_flow", "auc_reachability"):
            entry, test = section["strategies"][strategy][metric], summary["strategies"][strategy][metric]
            for key, value in test.items():
                assert entry[key] == pytest.approx(value, rel=1e-5), (strategy, metric, key)
            assert entry["verdict"] == null_verdict(test)
            assert sum(entry["distribution"]["counts"]) == N_NULLS
    flow = {s: section["strategies"][s]["auc_flow"]["verdict"] for s in STRATEGIES}
    assert flow["random"] == "above_null_mean"
    assert flow["out_strength"] == "more_fragile"


def test_a_small_ensemble_cannot_reach_the_corrected_threshold(tmp_path):
    write_null_results(tmp_path, n=40)
    section = nulls(tmp_path)
    assert section["p_floor"] > section["alpha"]
    assert all(section["strategies"][s]["auc_flow"]["verdict"] != "more_fragile" for s in STRATEGIES)


def test_nulls_section_is_compact_valid_json(tmp_path):
    write_null_results(tmp_path, n=N_NULLS)
    text = json.dumps(nulls(tmp_path), separators=(",", ":"), allow_nan=False)
    assert len(text) < 8000


def test_split_missing_waits_for_the_null_summary_but_not_for_other_inputs():
    pending, failed = split_missing({"nulls.json": ["null_model_summary.json", "null_model_scores.csv"],
                                     "edges.json": ["edge_attack.json"]})
    assert pending == ["nulls.json"] and failed == {"edges.json": ["edge_attack.json"]}
    pending, failed = split_missing({"nulls.json": ["null_model_scores.csv"]})
    assert pending == [] and failed == {"nulls.json": ["null_model_scores.csv"]}


def isolate_nulls(monkeypatch, tmp_path):
    results, web_data, assets = tmp_path / "results", tmp_path / "web" / "public" / "data", tmp_path / "assets"
    results.mkdir()
    assets.mkdir()
    monkeypatch.setattr(static_export, "RESULTS", results)
    monkeypatch.setattr(static_export, "WEB_DATA", web_data)
    monkeypatch.setattr(static_export, "ASSETS", assets)
    monkeypatch.setattr(static_export, "SECTIONS", {"nulls.json": static_export.SECTIONS["nulls.json"]})
    monkeypatch.setattr(sys, "argv", ["build_static_json.py"])
    return results, web_data


def manifest(web_data) -> list[str]:
    return json.loads((web_data / "manifest.json").read_text(encoding="utf-8"))["available"]


def test_export_skips_the_unfinished_null_model_without_failing(monkeypatch, tmp_path, capsys):
    _, web_data = isolate_nulls(monkeypatch, tmp_path)
    static_export.main()
    assert manifest(web_data) == []
    assert not (web_data / "nulls.json").exists()
    assert "PENDING nulls.json" in capsys.readouterr().out


def test_export_fails_when_the_summary_exists_without_its_scores(monkeypatch, tmp_path):
    results, web_data = isolate_nulls(monkeypatch, tmp_path)
    write_null_results(results)
    (results / "null_model_scores.csv").unlink()
    with pytest.raises(SystemExit) as exit_info:
        static_export.main()
    assert exit_info.value.code == 1
    assert manifest(web_data) == []


def test_export_writes_and_lists_the_finished_null_model(monkeypatch, tmp_path):
    results, web_data = isolate_nulls(monkeypatch, tmp_path)
    write_null_results(results)
    static_export.main()
    assert manifest(web_data) == ["nulls.json"]
    exported = json.loads((web_data / "nulls.json").read_text(encoding="utf-8"))
    assert exported == json.loads(json.dumps(nulls(results)))


def finished_run(monkeypatch, folder, n: int = N_NULLS, shift: dict | None = None):
    """Every null-model output in ``folder`` and its site export in ``folder / 'web'``."""
    summary = write_null_results(folder, n=n, shift=shift)
    real = {s: {m: summary["strategies"][s][m]["real"] for m in ("auc_flow", "auc_reachability")} for s in STRATEGIES}
    (folder / "fragility_scores.json").write_text(json.dumps({"strategies": real}), encoding="utf-8")
    monkeypatch.setattr(null_model, "RESULTS", folder)
    null_model.write_report(summary["strategies"], SimpleNamespace(vcount=lambda: 10, ecount=lambda: 20), n)
    (folder / "null_distribution.png").write_bytes(b"png")
    web = folder / "web"
    web.mkdir()
    (web / "nulls.json").write_text(json.dumps(nulls(folder)), encoding="utf-8")
    (web / "manifest.json").write_text(json.dumps({"available": ["nulls.json"]}), encoding="utf-8")
    return summary, web


def test_check_accepts_a_finished_run_whatever_its_outcome(monkeypatch, tmp_path):
    summary, web = finished_run(monkeypatch, tmp_path, shift={"random": 0.05, "pagerank": 0.0})
    line = check(tmp_path, web, tmp_path / "no-runs")
    significant = [s for s in STRATEGIES if summary["strategies"][s]["auc_flow"]["significant"]]
    assert "random" not in significant and "out_strength" in significant
    assert line.endswith(", ".join(significant))


def test_check_rejects_a_wrong_verdict_and_a_stale_export(monkeypatch, tmp_path):
    summary, web = finished_run(monkeypatch, tmp_path)
    exported = json.loads((web / "nulls.json").read_text(encoding="utf-8"))
    exported["strategies"]["pagerank"]["auc_flow"]["distribution"]["counts"][0] += 1
    (web / "nulls.json").write_text(json.dumps(exported), encoding="utf-8")
    with pytest.raises(AssertionError, match="nulls.json differs"):
        check(tmp_path, web, tmp_path / "no-runs")
    summary["strategies"]["pagerank"]["auc_flow"]["significant"] = False
    (tmp_path / "null_model_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(AssertionError, match="Bonferroni verdict"):
        check(tmp_path, web, tmp_path / "no-runs")


def test_check_reports_a_short_ensemble_only_as_a_stated_deviation(monkeypatch, tmp_path):
    assert ensemble_size(N_NULLS, "") == ""
    _, web = finished_run(monkeypatch, tmp_path, n=150)
    with pytest.raises(AssertionError, match=r"150 randomized graphs scored, 200 pre-registered \(50 short\)"):
        check(tmp_path, web, tmp_path / "no-runs")
    report = tmp_path / "null_model_validation.md"
    report.write_text(report.read_text(encoding="utf-8") + "\nDeviation: 150 randomized graphs were scored.\n",
                      encoding="utf-8")
    assert "deviation reported: 150 randomized graphs scored" in check(tmp_path, web, tmp_path / "no-runs")


def test_check_skips_before_the_run_finishes_and_rejects_partial_outputs(tmp_path):
    with pytest.raises(Skip):
        check(tmp_path, tmp_path, tmp_path / "no-runs")
    (tmp_path / "null_model_scores.csv").write_text("", encoding="utf-8")
    with pytest.raises(AssertionError, match="absent"):
        check(tmp_path, tmp_path, tmp_path / "no-runs")
