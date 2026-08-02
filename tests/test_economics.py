# Step 5a — unit tests for the decision economics.
#
# Pure functions: no model, no data, no artifact. They run anywhere in milliseconds and pin down
# the maths the whole decision layer rests on. This is the kind of test that always runs, in CI
# included, because it depends on nothing external.
#
# A test is three moves: arrange (set up inputs), act (call the function), assert (state what must
# be true). pytest.approx compares floats without demanding exact equality, which you almost always
# want with arithmetic.

import pytest

from credit_risk.evaluate import (
    expected_profit,
    breakeven_probability,
)


def test_breakeven_zero_rate():

    assert breakeven_probability(0) == pytest.approx(0.0)


def test_breakeven_rises_with_rate():
    low = breakeven_probability(0)
    mid = breakeven_probability(10)
    high = breakeven_probability(25)

    assert low < mid < high 


def test_expected_profit_signs():
   amnt, rate = 10_000, 12.0
   
    assert expected_profit(0.0, amnt, rate) > 0                    # certain to repay: earns margin
    assert expected_profit(1.0, amnt, rate) < 0                    # certain to default: loses
    assert expected_profit(0.1, amnt, rate) > expected_profit(0.5, amnt, rate)   # falls with risk


def test_expected_profit_zero_at_breakeven():
    rate = 15.0
    p = breakeven_probability(rate)

    assert expected_profit(p, 10_000, rate) == pytest.approx(0.0, abs=1e-6)
    assert expected_profit(p, 50_000, rate) == pytest.approx(0.0, abs=1e-6)      # amount cancels