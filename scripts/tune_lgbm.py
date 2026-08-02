# Tunes the LightGBM union model on the validation set.

import json
from pathlib import Path
from typing import Any, cast

import optuna
from optuna.samplers import TPESampler
from lightgbm import LGBMClassifier, early_stopping
import pandas as pd
from sklearn.metrics import log_loss

from credit_risk.data import load_loans
from credit_risk.split import out_of_time_split
from credit_risk.model import (
    build_lgbm,
    build_tree_preprocessor,
    UNDERWRITER_NUMERIC, UNDERWRITER_CATEGORICAL,
    LC_VERDICT_NUMERIC, LC_VERDICT_CATEGORICAL,
)
from credit_risk.evaluate import discrimination_metrics

REPORTS = Path(__file__).resolve().parents[1] / "reports"

TARGET = "target_bad"
NUMERIC = UNDERWRITER_NUMERIC + LC_VERDICT_NUMERIC
CATEGORICAL = UNDERWRITER_CATEGORICAL + LC_VERDICT_CATEGORICAL
COLS = NUMERIC + CATEGORICAL

N_TRIALS = 60
MAX_TREES = 2000
EARLY_STOPPING = 50


# Fits one trial and returns its validation log loss.
def objective(
    trial: optuna.Trial,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> float:
    params: dict[str, Any] = {
        "num_leaves": trial.suggest_int("num_leaves", 15, 255),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 500, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
    }

    clf = LGBMClassifier(n_estimators=MAX_TREES, subsample_freq=1, verbose=-1, **params)
    clf.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="binary_logloss",
        callbacks=[early_stopping(EARLY_STOPPING, verbose=False)],
    )

    trial.set_user_attr("n_estimators", clf.best_iteration_)

    proba = clf.predict_proba(X_val)[:, 1]
    return log_loss(y_val, proba)


# Adds fixed settings to the best parameters from the study.
def best_params(study: optuna.Study) -> dict[str, int | float]:
    params = cast(dict[str, int | float], dict(study.best_params))
    params["subsample_freq"] = 1
    params["n_estimators"] = study.best_trial.user_attrs["n_estimators"]

    return params


# Compares the baseline and tuned models on validation data.
def compare(
    train: pd.DataFrame,
    val: pd.DataFrame,
    params: dict[str, int | float],
) -> dict[str, dict[str, float]]:
    rows = {}
    for name, model in [
        ("baseline", build_lgbm(NUMERIC, CATEGORICAL)),
        ("tuned", build_lgbm(NUMERIC, CATEGORICAL, params=params)),
    ]:
        model.fit(train[COLS], train[TARGET])
        proba = model.predict_proba(val[COLS])[:, 1]

        metrics = discrimination_metrics(val[TARGET], proba)
        metrics["log_loss"] = log_loss(val[TARGET], proba)
        rows[name] = metrics

    return rows


# Runs the search, saves the best parameters, and prints the comparison.
def main() -> None:
    df = load_loans()
    train, val, _ = out_of_time_split(df)

    prep = build_tree_preprocessor(NUMERIC, CATEGORICAL)
    X_train = prep.fit_transform(train[COLS])
    X_val = prep.transform(val[COLS])
    y_train, y_val = train[TARGET], val[TARGET]

    sampler = TPESampler(seed=0)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(
        lambda t: objective(t, X_train, y_train, X_val, y_val),
        n_trials=N_TRIALS,
    )

    params = best_params(study)

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / "lgbm_best_params.json"
    out.write_text(json.dumps(params, indent=2))
    print(f"best validation log-loss {study.best_value:.5f}")
    print(f"params -> {out}")

    print()
    for name, metrics in compare(train, val, params).items():
        print(name, {k: round(v, 4) for k, v in metrics.items()})


if __name__ == "__main__":
    main()
