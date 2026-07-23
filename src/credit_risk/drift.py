# Drift diagnostics: how far did the feature distributions move between two samples?

import numpy as np
import pandas as pd

from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from lightgbm import LGBMClassifier
from credit_risk.model import build_tree_preprocessor


def population_stability_index(expected, actual, n_bins: int = 10) -> float:
    edges = np.quantile(expected, np.linspace(0, 1, n_bins + 1))
    edges = np.unique(edges)

    # Widen the outer edges, otherwise actual values beyond the reference range become NaN and are
    # dropped. Those are the most shifted rows, so losing them understates the drift.
    edges[0], edges[-1] = -np.inf, np.inf

    e = pd.cut(expected, edges).value_counts(normalize=True).sort_index()
    a = pd.cut(actual, edges).value_counts(normalize=True).sort_index()

    eps = 1e-8
    e = e.clip(lower=eps)
    a = a.clip(lower=eps)

    psi = ((a - e) * np.log(a / e)).sum()

    return psi


def adversarial_validation(train, val, numeric, categorical, cv: int = 3) -> dict:
    cols = numeric + categorical

    X = pd.concat([train[cols], val[cols]], ignore_index=True)
    y = np.r_[np.zeros(len(train)), np.ones(len(val))]

    pipe = Pipeline([
        ('prep', build_tree_preprocessor(numeric, categorical)),
        ('clf', LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            num_leaves=31,
            verbose=-1
        ))
    ])

    # Scored out of sample: fitting and predicting on the same rows would measure memorisation.
    auc = cross_val_score(pipe, X, y, cv=cv, scoring="roc_auc").mean()

    # Refit on everything just to read which features give the period away.
    pipe.fit(X, y)
    importances = pd.Series(
        pipe.named_steps["clf"].feature_importances_,
        index=pipe.named_steps["prep"].get_feature_names_out(),
    ).sort_values(ascending=False)

    return {"roc_auc": auc, "importances": importances}
