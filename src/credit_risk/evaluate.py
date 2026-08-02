# Evaluates model quality and lending decisions.

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.calibration import calibration_curve


# Calculates discrimination and calibration metrics.
def discrimination_metrics(y_true, y_proba) -> dict:
    
    dis = {
        "roc_auc": roc_auc_score(y_true, y_proba),
        "pr_auc": average_precision_score(y_true, y_proba),
        "brier": brier_score_loss(y_true, y_proba)
    }

    return dis


# Returns data for a reliability curve.
def reliability_data(y_true, y_proba, n_bins: int = 10):

    return calibration_curve(y_true, y_proba, n_bins=n_bins, strategy='quantile')


# Breaks the Brier score into its components.
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


MARGIN_PER_RATE_POINT = 0.0133
LOSS_FRACTION = 0.3543


# Calculates the margin and loss for a loan.
def loan_economics(loan_amnt, int_rate):
    margin = loan_amnt * MARGIN_PER_RATE_POINT * int_rate
    loss = loan_amnt * LOSS_FRACTION

    return margin, loss


# Calculates the expected profit for a loan.
def expected_profit(y_proba, loan_amnt, int_rate):
    margin, loss = loan_economics(loan_amnt, int_rate)

    earned = (1 - y_proba) * margin
    lost = y_proba * loss

    return earned - lost


# Calculates the default probability at break-even.
def breakeven_probability(int_rate):
    margin_fraction = MARGIN_PER_RATE_POINT * int_rate

    return margin_fraction / (margin_fraction + LOSS_FRACTION)
