# Baseline training run: load -> split -> fit -> evaluate.
#
# Evaluates on VALIDATION only. The test set stays untouched until the final
# model is chosen, otherwise every number it produces is optimistic.
#
# TODO D — this script fits one model on the old four-feature set. It should report the
# three feature sets side by side, because the comparison *is* the headline result:
#
#   1. LC verdict   (LC_VERDICT_*)              the benchmark, AUC 0.6793
#   2. underwriter  (UNDERWRITER_*)             borrower data only. Can it match the price?
#   3. union        (UNDERWRITER_* + LC_*)      does borrower data add to the price, or
#                                               had Lending Club already extracted it all?
#
# Notebook 21 explores this; the script is the reproducible run that prints the numbers.
# Keep the shape below (fit on train, score on val, print) and loop over the three
# configurations instead. Factoring the fit-and-score body into a small helper that takes
# (numeric, categorical) and returns the metrics dict will keep main() readable.
#
# Add murphy_decomposition to the report once it exists: resolution is the number that
# says whether the new features actually carry signal, and AUC alone will not tell you.

from credit_risk.data import load_loans
from credit_risk.split import out_of_time_split
from credit_risk.model import (
    build_logistic, 
    LC_VERDICT_NUMERIC, 
    LC_VERDICT_CATEGORICAL,
    UNDERWRITER_NUMERIC,
    UNDERWRITER_CATEGORICAL
)

from credit_risk.evaluate import (
    discrimination_metrics,
    reliability_data,
    cost_sensitive_threshold,
)

TARGET = "target_bad"

FEATURE_SETS = {
    underwriter: (UNDERWRITER_NUMERIC, UNDERWRITER_CATEGORICAL),
    lc_verdict: (LC_VERDICT_NUMERIC, LC_VERDICT_CATEGORICAL),
    union: (
        LC_VERDICT_NUMERIC + UNDERWRITER_NUMERIC, 
        LC_VERDICT_CATEGORICAL + UNDERWRITER_CATEGORICAL,
        ),
}

def evaluate_features(df, numeric, categorical):

    df = load_loans()
    train, val, test = out_of_time_split(df)

    features = numeric + categorical

    pipe = build_logistic(numeric, categorical)
    pipe.fit(train[features], train[TARGET])

    y_proba = pipe.predict_proba(val[features])[:, 1]
    y_true = val[TARGET].values

    metrics = discrimination_metrics(y_true, y_proba)
    murphy = murphy_decomposition(y_true, y_proba)
    threshold = cost_sensitive_threshold(y_true, y_proba)

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

    results{
        name: evaluate_features(train, val, numeric, categorical)
        for name, (numeric, categorical) in FEATURE_SETS.items()
    }


    print("Baseline logistic, validation set")
    for name, value in metrics.items():
        print(f"  {name}: {value:.4f}")

    print(f"Validation, {len(val)} loans, bad rate {val[TARGET].mean():.3f}")
    print(pd.DataFrame(results).T.round(4))


if __name__ == "__main__":
    main()

