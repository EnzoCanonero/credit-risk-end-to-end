import json
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from credit_risk.data import REPO_ROOT

MODELS = REPO_ROOT / "models"
ARTIFACT = MODELS / "model.joblib"
METADATA = MODELS / "model_meta.json"


@lru_cache(maxsize=1)
def load_model(path: Path = ARTIFACT):
    model = joblib.load(path)

    return model


def feature_columns() -> list[str]:
    meta = json.loads(METADATA.read_text())
    features = meta["features"]

    return features


def numeric_columns() -> list[str]:
    meta = json.loads(METADATA.read_text())

    return meta["numeric"]


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
