# Loads the trained model and scores loan applications.

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import cast

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

from credit_risk.evaluate import breakeven_probability
from credit_risk.schema import Loan

DEFAULT_MODELS = Path(__file__).resolve().parents[2] / "models"
MODELS = Path(os.getenv("CREDIT_RISK_MODEL_DIR", str(DEFAULT_MODELS)))
ARTIFACT = MODELS / "model.joblib"
METADATA = MODELS / "model_meta.json"


# Loads and caches the trained model.
@lru_cache(maxsize=1)
def load_model(path: Path = ARTIFACT) -> Pipeline:
    return cast(Pipeline, joblib.load(path))


@lru_cache(maxsize=1)
def _metadata() -> dict[str, object]:
    return json.loads(METADATA.read_text())


# Loads the model feature names.
def feature_columns() -> list[str]:
    return cast(list[str], _metadata()["features"])


# Loads the numeric feature names.
def numeric_columns() -> list[str]:
    return cast(list[str], _metadata()["numeric"])


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


# Scores one loan and returns the approval decision.
def score_one(loan: Loan) -> dict[str, float | bool]:
    probability = float(score(pd.DataFrame([loan.model_dump()])).iloc[0])
    approve = bool(probability < breakeven_probability(loan.int_rate))

    return {"default_probability": probability, "approve": approve}
