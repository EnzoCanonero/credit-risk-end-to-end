# Evaluation: discrimination, calibration, and cost-sensitive thresholding.

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


def cost_sensitive_threshold(y_true, y_proba, cost_fn: float = 5.0, cost_fp: float = 1.0):
    
    thresholds = np.linspace(0.01, 0.99, 99)
    total_cost = np.zeros(len(thresholds))

    for i, t in enumerate(thresholds):
        pred_bad = y_proba >= t
        FN_t = ((y_true==1) & ~pred_bad).sum()
        FP_t = ((y_true==0) & pred_bad).sum()
        total_cost[i] = cost_fn * FN_t + cost_fp * FP_t
    
    best_t = thresholds[np.argmin(total_cost)]

    return {
        'best_threshold': best_t,
        'thresholds': thresholds,
        'costs': total_cost,
    }
