# Checks the decision economics calculations.

import pytest

from credit_risk.evaluate import (
    expected_profit,
    breakeven_probability,
)


# Checks that a zero interest rate has a zero break-even probability.
def test_breakeven_zero_rate():
    assert breakeven_probability(0) == pytest.approx(0.0)


# Checks that the break-even probability rises with the interest rate.
def test_breakeven_rises_with_rate():
    low = breakeven_probability(0)
    mid = breakeven_probability(10)
    high = breakeven_probability(25)

    assert low < mid < high


# Checks how repayment and default risk affect expected profit.
def test_expected_profit_signs():
   amnt, rate = 10_000, 12.0
   
    assert expected_profit(0.0, amnt, rate) > 0
    assert expected_profit(1.0, amnt, rate) < 0
    assert expected_profit(0.1, amnt, rate) > expected_profit(0.5, amnt, rate)


# Checks that expected profit is zero at the break-even probability.
def test_expected_profit_zero_at_breakeven():
    rate = 15.0
    p = breakeven_probability(rate)

    assert expected_profit(p, 10_000, rate) == pytest.approx(0.0, abs=1e-6)
    assert expected_profit(p, 50_000, rate) == pytest.approx(0.0, abs=1e-6)
