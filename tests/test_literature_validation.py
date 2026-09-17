import pytest

from pipeline.literature_validation import CURATED, POSITIVE_CONTROL, SCORES, p_text, report_lines


def rank_result(p_value: float, auc: float, n: int) -> dict:
    return {"n_curated": n, "n_other": 100, "U": 1000.0, "p_value": p_value, "auc": auc, "rank_biserial": 2 * auc - 1,
            "median_percentile": 70.0}


def report(control_score: float, with_control_p: float) -> dict:
    types = {t: {"published_name": name, "behavior": behavior, "evidence": evidence, "superclass": "descending_neuron",
                 "n_neurons": 2, **{f"{s}_percentile": 50.0 for s in SCORES}, **{s: 10.0 for s in SCORES}}
             for t, name, behavior, evidence, _ in CURATED + [POSITIVE_CONTROL]}
    types[POSITIVE_CONTROL[0]].update(sm_betweenness=control_score, sm_betweenness_percentile=9.8, flow_drop=1.0)
    tests = {"primary": {s: rank_result(0.045, 0.63, 14) for s in SCORES},
             "with_positive_control": {s: rank_result(with_control_p, 0.59, 15) for s in SCORES},
             "DNp71_for_DNp09": {s: rank_result(0.018, 0.66, 14) for s in SCORES}}
    return {"alpha": 0.05, "tests": tests, "curated_types": types}


def test_positive_control_is_described_by_its_role_not_as_structurally_essential():
    text = "\n".join(report_lines(report(0.0, 0.10)))
    assert "structurally essential" not in text
    assert "its published importance lies in its motor output" in text
    assert "sensory-motor betweenness is 0" in text
    assert "costs 1 path of flow capacity" in text


def test_sensitivity_to_the_positive_control_is_reported_with_and_without_it():
    text = "\n".join(report_lines(report(0.0, 0.10)))
    assert "without `MN9` the sensory-motor betweenness test gives p = 0.045" in text
    assert "with it, p = 0.10 (AUC = 0.59, not significant)" in text
    assert "depends on excluding it" in text


def test_sensitivity_text_follows_the_result_when_the_conclusion_holds():
    text = "\n".join(report_lines(report(3.0, 0.03)))
    assert "Including it does not change the conclusion." in text
    assert "sensory-motor betweenness is 0" not in text


@pytest.mark.parametrize(("p", "text"), [(0.045, "0.045"), (0.10159, "0.10"), (8.7e-06, "8.7e-06")])
def test_p_values_keep_two_significant_figures(p, text):
    assert p_text(p) == text
