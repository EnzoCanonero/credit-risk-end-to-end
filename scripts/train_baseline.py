# Baseline training run: load -> split -> fit -> evaluate.
#
# Fits three feature sets with two models on train and scores them on validation.
# The comparison is the point: can borrower data alone match Lending Club's own price,
# and does the tree extract signal the linear model leaves on the table?
#
# The test set stays untouched until the final model is chosen.

from collections.abc import Callable
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive: the script saves the figure instead of showing it
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
from sklearn.pipeline import Pipeline

from credit_risk.data import load_loans
from credit_risk.split import out_of_time_split
from credit_risk.model import (
    build_logistic,
    build_lgbm,
    LC_VERDICT_NUMERIC,
    LC_VERDICT_CATEGORICAL,
    UNDERWRITER_NUMERIC,
    UNDERWRITER_CATEGORICAL,
)
from credit_risk.evaluate import (
    discrimination_metrics,
    reliability_data,
    murphy_decomposition,
    cost_sensitive_threshold,
)

REPORTS = Path(__file__).resolve().parents[1] / "reports"

TARGET = "target_bad"

FEATURE_SETS = {
    "lc_verdict": (LC_VERDICT_NUMERIC, LC_VERDICT_CATEGORICAL),
    "underwriter": (UNDERWRITER_NUMERIC, UNDERWRITER_CATEGORICAL),
    "union": (
        UNDERWRITER_NUMERIC + LC_VERDICT_NUMERIC,
        UNDERWRITER_CATEGORICAL + LC_VERDICT_CATEGORICAL,
    ),
}

MODELS: dict[str, Callable[..., Pipeline]] = {
    "logistic": build_logistic,
    "lgbm": build_lgbm,
}


def evaluate_features(
    train,
    val,
    numeric,
    categorical,
    build_model: Callable[..., Pipeline] = build_logistic,
) -> dict:
    #Fit on train, score on validation, return one flat row of metrics.
    cols = numeric + categorical
    pipe = build_model(numeric, categorical)
    pipe.fit(train[cols], train[TARGET])

    proba = pipe.predict_proba(val[cols])[:, 1]
    y = val[TARGET].values

    metrics = discrimination_metrics(y, proba)
    murphy = murphy_decomposition(y, proba)
    threshold = cost_sensitive_threshold(y, proba)

    return {
        "roc_auc": metrics["roc_auc"],
        "pr_auc": metrics["pr_auc"],
        "brier": metrics["brier"],
        "resolution": murphy["resolution"],
        "threshold": threshold["best_threshold"],
    }
    

def calibration_check(train, val, numeric, categorical) -> None:
    #Is LightGBM already calibrated, or does isotonic help? Report Brier and save the diagram.

    cols = numeric + categorical
    y = val[TARGET].values

    raw = build_lgbm(numeric, categorical)
    raw.fit(train[cols], train[TARGET])
    proba_raw = raw.predict_proba(val[cols])[:, 1]

    cal = CalibratedClassifierCV(build_lgbm(numeric, categorical), method="isotonic", cv=5)
    cal.fit(train[cols], train[TARGET])
    proba_cal = cal.predict_proba(val[cols])[:, 1]

    print()
    print("calibration (lgbm, union)")
    print(f"  Brier raw       {brier_score_loss(y, proba_raw):.4f}")
    print(f"  Brier isotonic  {brier_score_loss(y, proba_cal):.4f}")

    for label, proba in [("raw", proba_raw), ("isotonic", proba_cal)]:
        prob_true, prob_pred = reliability_data(y, proba)
        plt.plot(prob_pred, prob_true, marker="o", label=label)
    plt.plot([0, 1], [0, 1], linestyle="--", color="grey", label="perfect")
    plt.xlabel("mean predicted")
    plt.ylabel("observed default rate")
    plt.title("LightGBM reliability, union features (validation)")
    plt.legend()

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / "reliability_lgbm.png"
    plt.savefig(out, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  diagram -> {out}")


def main() -> None:
    df = load_loans()
    train, val, test = out_of_time_split(df)

    print(f"Validation: {len(val)} loans, bad rate {val[TARGET].mean():.3f}")

    for model_name, build_model in MODELS.items():
        results = {
            name: evaluate_features(train, val, numeric, categorical, build_model)
            for name, (numeric, categorical) in FEATURE_SETS.items()
        }
        print()
        print(model_name)
        print(pd.DataFrame(results).T.round(4))

    union_numeric, union_categorical = FEATURE_SETS["union"]
    calibration_check(train, val, union_numeric, union_categorical)


if __name__ == "__main__":
    main()
