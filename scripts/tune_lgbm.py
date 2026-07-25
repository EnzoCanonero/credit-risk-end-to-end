# Hyperparameter search for the LightGBM union model.
#
# Fit on train, score on validation, minimise log-loss: it rewards ranking and calibration at
# once, and the whole economics layer in notebooks/23 rests on the probabilities being honest,
# not only well ordered. The test set stays closed; the tuned params it produces are scored there
# once, in the next step.
#
# Writes the winning params to reports/lgbm_best_params.json so the final model is reproducible
# without re-running the study.

import json
from pathlib import Path

import optuna
from optuna.samplers import TPESampler
from lightgbm import LGBMClassifier, early_stopping
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
MAX_TREES = 2000        # a ceiling; early stopping picks the real count each trial
EARLY_STOPPING = 50


def objective(trial, X_train, y_train, X_val, y_val):
    # One trial: a param set, fit with early stopping on val, report the validation log-loss.
    params = {
        "num_leaves": trial.suggest_int("num_leaves", 15, 255),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 500, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
    }

    # subsample only bites when bagging runs every round, so pin the frequency at 1.
    clf = LGBMClassifier(n_estimators=MAX_TREES, subsample_freq=1, verbose=-1, **params)
    clf.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="binary_logloss",
        callbacks=[early_stopping(EARLY_STOPPING, verbose=False)],
    )

    # Keep how many trees this trial actually used, so the saved params can rebuild the model.
    trial.set_user_attr("n_estimators", clf.best_iteration_)

    proba = clf.predict_proba(X_val)[:, 1]
    return log_loss(y_val, proba)


def best_params(study):
    # The winning suggestions, plus the two settings that were fixed rather than searched.
    params = dict(study.best_params)
    params["subsample_freq"] = 1
    params["n_estimators"] = study.best_trial.user_attrs["n_estimators"]

    return params


def compare(train, val, params):
    # Baseline against tuned on the same loans. discrimination_metrics carries roc/pr/brier;
    # add log-loss so calibration sits next to ranking.
    # Pass the union feature lists explicitly: build_lgbm defaults to the underwriter set, which
    # would silently drop int_rate and grade and score the wrong model.
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


def main():
    df = load_loans()
    train, val, _ = out_of_time_split(df)

    # Fit the preprocessor once and reuse the matrices. Every trial would otherwise repeat the
    # same transform, and early stopping needs val already transformed, which the pipeline cannot
    # do mid-fit. So we step outside it here for the search.
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
