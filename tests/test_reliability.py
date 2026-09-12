# Checks the sampling intervals shown on reliability plots.

import numpy as np
import pytest
from numpy.typing import NDArray
from scipy.stats import bootstrap

from credit_risk.evaluate import reliability_data, reliability_intervals


# Tied predictions leave empty quantile bins, but retain the plotted point order.
def test_intervals_follow_nonempty_reliability_bins() -> None:
    proba = np.array([0.1, 0.1, 0.1, 0.2, 0.2, 0.2, 0.9, 0.9])
    y = np.array([0, 0, 0, 1, 1, 1, 0, 0])
    observed, predicted = reliability_data(y, proba, n_bins=4)
    low, high = reliability_intervals(y, proba, n_bins=4, n_bootstrap=200)

    np.testing.assert_allclose(predicted, [0.1, 0.2, 0.9])
    np.testing.assert_allclose(observed, [0, 1, 0])
    np.testing.assert_allclose(low, observed)
    np.testing.assert_allclose(high, observed)


# Compare with an independent paired bootstrap on two fixed score regions.
def test_intervals_match_paired_resampling() -> None:
    proba = np.linspace(0.01, 0.99, 40)
    y = np.array([0, 0, 0, 1] * 5 + [0, 1, 1, 1] * 5)

    def observed_rates(y_sample: NDArray, proba_sample: NDArray) -> list[float]:
        return [y_sample[proba_sample <= 0.5].mean(), y_sample[proba_sample > 0.5].mean()]

    expected = bootstrap(
        (y, proba), observed_rates, paired=True, vectorized=False,
        n_resamples=200, batch=20, method="percentile", rng=7,
    ).confidence_interval
    low, high = reliability_intervals(y, proba, n_bins=2, n_bootstrap=200, seed=7)

    np.testing.assert_allclose(low, expected.low)
    np.testing.assert_allclose(high, expected.high)

    # Reversing the score regions uses the same rows, in the opposite bin order.
    reversed_low, reversed_high = reliability_intervals(
        y, 1 - proba, n_bins=2, n_bootstrap=200, seed=7,
    )
    np.testing.assert_allclose(reversed_low, low[::-1])
    np.testing.assert_allclose(reversed_high, high[::-1])


@pytest.mark.parametrize("outcome", [0, 1])
def test_constant_outcomes_and_predictions(outcome: int) -> None:
    low, high = reliability_intervals(
        np.full(10, outcome), np.full(10, 0.4), n_bootstrap=100,
    )

    np.testing.assert_array_equal(low, [outcome])
    np.testing.assert_array_equal(high, [outcome])
