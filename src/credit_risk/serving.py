# Step 2 — serving: load the artifact once, and turn feature rows into default probabilities.
#
# Both the batch script and the API import from here, so the prediction path exists in exactly one
# place. If loading and scoring lived in two files they could drift apart, and batch and online
# serving would quietly disagree. One function, one truth.

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


def score(loans: pd.DataFrame) -> pd.Series:
    cols = feature_columns()
    
    missing = [c for c in cols if c not in loans.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(missing)}"
        )

    model = load_model()
    probs = model.predict_proba(loans[cols])[:, 1]
    
    return pd.Series(probs, index=loans.index)
