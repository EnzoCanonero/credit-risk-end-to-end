# Trains and saves the final credit risk model.

import json
from datetime import date

import joblib
import pandas as pd

from credit_risk.data import load_loans, REPO_ROOT
from credit_risk.split import out_of_time_split
from credit_risk.model import (
    build_lgbm,
    UNDERWRITER_NUMERIC, UNDERWRITER_CATEGORICAL,
    LC_VERDICT_NUMERIC, LC_VERDICT_CATEGORICAL,
)

MODELS = REPO_ROOT / "models"
ARTIFACT = MODELS / "model.joblib"
METADATA = MODELS / "model_meta.json"
PARAMS = REPO_ROOT / "reports" / "lgbm_best_params.json"

TARGET = "target_bad"
NUMERIC = UNDERWRITER_NUMERIC + LC_VERDICT_NUMERIC
CATEGORICAL = UNDERWRITER_CATEGORICAL + LC_VERDICT_CATEGORICAL
COLS = NUMERIC + CATEGORICAL


# Fits the tuned model on all available data and writes its artifacts.
def main() -> None:
    df = load_loans()
    train, val, test = out_of_time_split(df)

    fit_df = pd.concat([train, val, test])

    best = json.loads(PARAMS.read_text())
    pipe = build_lgbm(NUMERIC, CATEGORICAL, params=best)
    pipe.fit(fit_df[COLS], fit_df[TARGET])

    MODELS.mkdir(exist_ok=True)
    joblib.dump(pipe, ARTIFACT)

    vintages = pd.to_datetime(fit_df["issue_month"])
    meta = {
        "params": best,
        "features": COLS,
        "numeric": NUMERIC,
        "categorical": CATEGORICAL,
        "n_fit_rows": len(fit_df),
        "fit_vintages": [vintages.min().strftime("%Y-%m"), vintages.max().strftime("%Y-%m")],
        "built": date.today().isoformat(),
        "fit_on": "train+val+test, all available data",
        "performance": "unbiased estimate in notebooks/25_final_test (same config fit on train+val)",
    }
    METADATA.write_text(json.dumps(meta, indent=2))

    print(f"artifact  -> {ARTIFACT}")
    print(f"metadata  -> {METADATA}")
    print(f"fitted on {len(fit_df)} loans, vintages {meta['fit_vintages'][0]} to {meta['fit_vintages'][1]}")


if __name__ == "__main__":
    main()
