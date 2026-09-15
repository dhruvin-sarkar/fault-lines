import numpy as np
import pytest

from pipeline.critical_thresholds import critical_fraction
from pipeline.removal_strategies import normalized_auc


def test_critical_fraction_interpolates_between_batches():
    x = np.array([0.0, 0.1, 0.2, 0.3])
    flow = np.array([100, 80, 60, 20])
    interpolated, batch = critical_fraction(x, flow)
    # Crosses 50 between 0.2 (60) and 0.3 (20): 0.2 + 0.1 * (60 - 50) / (60 - 20).
    assert interpolated == pytest.approx(0.225)
    assert batch == pytest.approx(0.3)


def test_critical_fraction_uses_strictly_below_the_cutoff():
    interpolated, batch = critical_fraction(np.array([0.0, 0.5, 1.0]), np.array([10, 5, 0]))
    assert batch == pytest.approx(1.0)
    assert interpolated == pytest.approx(0.5)


def test_critical_fraction_requires_a_crossing():
    with pytest.raises(ValueError, match="never falls"):
        critical_fraction(np.array([0.0, 0.5]), np.array([10, 9]))


def test_normalized_auc_is_the_mean_retained_fraction():
    x = np.array([0.0, 0.25, 0.5])
    assert normalized_auc(x, np.array([8, 8, 8]), 8) == pytest.approx(1.0)
    assert normalized_auc(x, np.array([10, 5, 0]), 10) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        normalized_auc(x, np.array([0, 0, 0]), 0)
