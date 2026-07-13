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

    return calibration_curve(y_true, y_proba, n_bins=n_bins)


def cost_sensitive_threshold(y_true, y_proba, cost_fn: float = 5.0, cost_fp: float = 1.0):
    
    thresholds = np.linspace(0.01, 0.99, 99)
    total_cost = np.zeros(len(thresholds))

    for i, t in enumerate(thresholds):
        pred_bad = y_proba >= t
        FN_t = ((y_true==1) & ~pred_bad).sum()
        FP_t = ((y_true==0) & pred_bad).sum()
        total_cost[i] = cost_fn * FN_t + cost_fp * FP_t
    
    best_t = thresholds[np.argmin(total_cost)]
    curve = (thresholds, total_cost)
    return best_t, curve
