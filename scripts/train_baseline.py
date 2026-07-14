# Baseline training run: load -> split -> fit -> evaluate.
#
# Evaluates on VALIDATION only. The test set stays untouched until the final
# model is chosen, otherwise every number it produces is optimistic.

from credit_risk.data import load_loans
from credit_risk.split import out_of_time_split
from credit_risk.model import build_logistic, NUMERIC, CATEGORICAL
from credit_risk.evaluate import (
    discrimination_metrics,
    reliability_data,
    cost_sensitive_threshold,
)

FEATURES = NUMERIC + CATEGORICAL
TARGET = "target_bad"


def main() -> None:

    df = load_loans()
    train, val, test = out_of_time_split(df)

    pipe = build_logistic()
    pipe.fit(train[FEATURES], train[TARGET])

    y_proba = pipe.predict_proba(val[FEATURES])[:,1]
    y_true  = val[TARGET].values


    metrics = discrimination_metrics(y_true, y_proba)
    best_t, (thresholds, costs) = cost_sensitive_threshold(y_true, y_proba)
    prob_true, prob_pred = reliability_data(y_true, y_proba)

    print("Baseline logistic, validation set")
    for name, value in metrics.items():
        print(f"  {name}: {value:.4f}")

    print()
    print(f"Best threshold: {best_t:.2f} (cost {costs.min():.0f})")

    print()
    print("Reliability, predicted vs observed:")
    for pred, obs in zip(prob_pred, prob_true):
        print(f"  {pred:.3f} -> {obs:.3f}")


if __name__ == "__main__":
    main()
