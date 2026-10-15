import numpy as np

from lab import stats


def test_t_stat_basics():
    assert stats.t_stat(np.array([1.0])) == 0.0 and stats.t_stat(np.array([2.0, 2.0])) == 0.0
    assert stats.t_stat(np.array([1.0, 2.0, 3.0, 4.0])) > 2.5


def test_threshold_rises_with_trials_and_never_below_base():
    assert stats.deflated_threshold(1, 2.5) == 2.5
    assert stats.deflated_threshold(10, 2.5) >= 2.5
    assert stats.deflated_threshold(10_000, 2.5) > stats.deflated_threshold(100, 2.5) >= 2.5
