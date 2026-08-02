# Loads the trained model and scores loan applications.

import json
from functools import lru_cache
from pathlib import Path
from typing import cast

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

from credit_risk.data import REPO_ROOT

MODELS = REPO_ROOT / "models"
ARTIFACT = MODELS / "model.joblib"
METADATA = MODELS / "model_meta.json"


# Loads and caches the trained model.
@lru_cache(maxsize=1)
def load_model(path: Path = ARTIFACT) -> Pipeline:
    return cast(Pipeline, joblib.load(path))


# Loads the model feature names.
def feature_columns() -> list[str]:
    meta = json.loads(METADATA.read_text())
    features = meta["features"]

    return cast(list[str], features)


# Loads the numeric feature names.
def numeric_columns() -> list[str]:
    meta = json.loads(METADATA.read_text())

    return cast(list[str], meta["numeric"])


# Scores loan applications for default risk.
def score(loans: pd.DataFrame) -> pd.Series:
    cols = feature_columns()

    missing = [c for c in cols if c not in loans.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(missing)}"
        )

    loans = loans.copy()
    num = numeric_columns()
    loans[num] = loans[num].astype(float)

    model = load_model()
    probs = model.predict_proba(loans[cols])[:, 1]

    return pd.Series(probs, index=loans.index)
