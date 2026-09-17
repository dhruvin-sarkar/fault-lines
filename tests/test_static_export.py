import json
import sys

import numpy as np
import pandas as pd
import pytest

import export.build_static_json as static_export
from export.build_static_json import FIGURES, SECTIONS, rounded


def test_rounded_turns_missing_values_into_none():
    assert rounded([None, float("nan"), np.float64("nan"), 1.234567, 3]) == [None, None, None, 1.23457, 3.0]


def test_rounded_accepts_series_and_digits():
    assert rounded(pd.Series([0.123456, np.nan, 2.0]), 2) == [0.12, None, 2.0]


def test_rounded_turns_float32_nan_into_none():
    assert rounded(np.array([np.nan, 1.5], dtype=np.float32)) == [None, 1.5]


def test_every_section_is_a_json_file_built_from_named_result_files():
    assert SECTIONS and "manifest.json" not in SECTIONS
    for name, (build, requires) in SECTIONS.items():
        assert name.endswith(".json")
        assert callable(build)
        assert requires, name
        for required in requires:
            assert isinstance(required, str) and required.endswith((".json", ".csv")), (name, required)
            assert "/" not in required and "\\" not in required


def isolate(monkeypatch, tmp_path):
    results, web_data, assets = tmp_path / "results", tmp_path / "web" / "public" / "data", tmp_path / "assets"
    results.mkdir()
    assets.mkdir()
    monkeypatch.setattr(static_export, "RESULTS", results)
    monkeypatch.setattr(static_export, "WEB_DATA", web_data)
    monkeypatch.setattr(static_export, "ASSETS", assets)
    return results, web_data, assets


def manifest(web_data) -> list[str]:
    return json.loads((web_data / "manifest.json").read_text(encoding="utf-8"))["available"]


def test_missing_results_fail_the_export_by_default(monkeypatch, tmp_path):
    _, web_data, _ = isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_static_json.py"])
    with pytest.raises(SystemExit) as exit_info:
        static_export.main()
    assert exit_info.value.code == 1
    assert manifest(web_data) == []


def test_allow_missing_skips_every_absent_section(monkeypatch, tmp_path):
    _, web_data, _ = isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_static_json.py", "--allow-missing"])
    static_export.main()
    assert manifest(web_data) == []
    assert sorted(p.name for p in web_data.iterdir()) == ["manifest.json"]


def test_sections_whose_inputs_exist_are_written_and_listed(monkeypatch, tmp_path):
    results, web_data, _ = isolate(monkeypatch, tmp_path)
    report = {"edges": 12, "orders": {"strongest": {"critical_fraction": 0.1}}}
    (results / "edge_attack.json").write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build_static_json.py", "--allow-missing"])
    static_export.main()
    assert manifest(web_data) == ["edges.json"]
    assert json.loads((web_data / "edges.json").read_text(encoding="utf-8")) == report


def test_copy_figures_copies_what_exists_and_skips_the_rest(monkeypatch, tmp_path):
    results, web_data, assets = isolate(monkeypatch, tmp_path)
    (results / FIGURES[0]).write_bytes(b"png")
    (assets / "hero.png").write_bytes(b"hero")
    copied = static_export.copy_figures()
    assert copied == [FIGURES[0], "hero.png"]
    figures = web_data.parent / "figures"
    assert (figures / FIGURES[0]).read_bytes() == b"png"
    assert sorted(p.name for p in figures.iterdir()) == sorted(copied)


def test_copy_figures_with_nothing_on_disk_copies_nothing(monkeypatch, tmp_path):
    _, web_data, _ = isolate(monkeypatch, tmp_path)
    assert static_export.copy_figures() == []
    assert (web_data.parent / "figures").is_dir()


def test_pair_loss_cuts_long_lists_and_keeps_the_full_counts(monkeypatch, tmp_path):
    results, _, _ = isolate(monkeypatch, tmp_path)
    limit = static_export.PAIR_LIMIT
    motors = [f"DN{i:03d}" for i in range(limit + 5)]
    groups = [{"sensory": f"S{i:02d}", "reach": len(motors), "motors": motors} for i in range(limit + 2)]
    report = {"types_with_pairs_lost": 7, "types": {"hub": groups, "bridge": [groups[0] | {"motors": motors[:2]}]}}
    (results / "pair_loss.json").write_text(json.dumps(report), encoding="utf-8")
    pd.DataFrame({"cell_type": ["hub", "bridge"], "own_pairs": [0, 3],
                  "other_pairs": [len(groups) * len(motors), 2]}).to_csv(results / "pair_loss.csv", index=False)
    exported = static_export.pair_loss()
    assert exported["limit"] == limit and exported["types_with_pairs_lost"] == 7
    hub = exported["types"]["hub"]
    assert hub["other"] == len(groups) * len(motors) and hub["own"] == 0 and hub["sources_total"] == len(groups)
    assert [s["sensory"] for s in hub["sources"]] == [g["sensory"] for g in groups[:limit]]
    assert all(s["lost"] == len(motors) and s["motors"] == motors[:limit] for s in hub["sources"])
    assert exported["types"]["bridge"] == {"own": 3, "other": 2, "sources_total": 1, "sources": [
        {"sensory": "S00", "reach": len(motors), "lost": 2, "motors": motors[:2]}]}
