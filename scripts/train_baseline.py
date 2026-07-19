# Baseline training run: load -> split -> fit -> evaluate.
#
# Fits three feature sets on train and scores them on validation. The comparison is
# the point: can borrower data alone match Lending Club's own price?
#
# The test set stays untouched until the final model is chosen.

import pandas as pd

from credit_risk.data import load_loans
from credit_risk.split import out_of_time_split
from credit_risk.model import (
    build_logistic,
    LC_VERDICT_NUMERIC,
    LC_VERDICT_CATEGORICAL,
    UNDERWRITER_NUMERIC,
    UNDERWRITER_CATEGORICAL,
)
from credit_risk.evaluate import (
    discrimination_metrics,
    murphy_decomposition,
    cost_sensitive_threshold,
)

TARGET = "target_bad"

FEATURE_SETS = {
    "lc_verdict": (LC_VERDICT_NUMERIC, LC_VERDICT_CATEGORICAL),
    "underwriter": (UNDERWRITER_NUMERIC, UNDERWRITER_CATEGORICAL),
    "union": (
        UNDERWRITER_NUMERIC + LC_VERDICT_NUMERIC,
        UNDERWRITER_CATEGORICAL + LC_VERDICT_CATEGORICAL,
    ),
}


def evaluate_features(train, val, numeric, categorical) -> dict:
    #Fit on train, score on validation, return one flat row of metrics
    
    cols = numeric + categorical
    pipe = build_logistic(numeric, categorical)
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


def main() -> None:

    df = load_loans()
    train, val, test = out_of_time_split(df)

    results = {
        name: evaluate_features(train, val, numeric, categorical)
        for name, (numeric, categorical) in FEATURE_SETS.items()
    }

    print(f"Validation, {len(val)} loans, bad rate {val[TARGET].mean():.3f}")
    print(pd.DataFrame(results).T.round(4))


if __name__ == "__main__":
    main()
