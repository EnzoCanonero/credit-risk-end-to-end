# Evaluation: how well the model ranks and how honest its probabilities are, then what a
# decision made on them is worth.

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.calibration import calibration_curve


def discrimination_metrics(y_true, y_proba) -> dict:
    
    dis = {
        "roc_auc": roc_auc_score(y_true, y_proba),
        "pr_auc": average_precision_score(y_true, y_proba),
        "brier": brier_score_loss(y_true, y_proba)
    }

    return dis


def reliability_data(y_true, y_proba, n_bins: int = 10):

    return calibration_curve(y_true, y_proba, n_bins=n_bins, strategy='quantile')


def murphy_decomposition(y_true, y_proba, n_bins: int = 20) -> dict:

    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)

    n = len(y_true)
    o_bar = y_true.mean()

    bin_edges = np.linspace(0, 1, n_bins + 1)
    bins_id = np.digitize(y_proba, bin_edges[1:-1])

    reliability = 0.0
    resolution = 0.0

    for k in range(n_bins):

        in_bin = (bins_id == k)
        n_k = in_bin.sum()

        if n_k == 0:
            continue

        p_k = y_proba[in_bin].mean()
        o_k = y_true[in_bin].mean()

        reliability += n_k * (p_k - o_k)**2
        resolution += n_k * (o_k - o_bar)**2

    reliability /= n
    resolution /= n

    # A property of the data, not of any bin: the Brier you get predicting o_bar for everyone.
    uncertainty = o_bar * (1 - o_bar)
    brier = reliability - resolution + uncertainty
    bss = (resolution - reliability) / uncertainty

    return {
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
        "brier": brier,
        "bss": bss,
    }


# Decision economics.
# Constants are calibrated on the training vintages in sql/30_loan_economics.sql

MARGIN_PER_RATE_POINT = 0.0133   # share of principal earned per point of int_rate
LOSS_FRACTION = 0.3543           # share of principal lost when a loan charges off


def loan_economics(loan_amnt, int_rate):
    # What a loan is worth either way, in currency.
    margin = loan_amnt * MARGIN_PER_RATE_POINT * int_rate
    loss = loan_amnt * LOSS_FRACTION

    return margin, loss


def expected_profit(y_proba, loan_amnt, int_rate):
    # Profit rather than a boolean, so the caller can both decide and add it up.
    margin, loss = loan_economics(loan_amnt, int_rate)

    earned = (1 - y_proba) * margin
    lost = y_proba * loss

    return earned - lost


def breakeven_probability(int_rate):
    # Setting expected_profit to zero gives p = margin / (margin + loss), and loan_amnt cancels
    # because it multiplies both. So the threshold follows the rate alone: size decides how much
    # a decision is worth, never which way it goes.
    margin_fraction = MARGIN_PER_RATE_POINT * int_rate

    return margin_fraction / (margin_fraction + LOSS_FRACTION)
