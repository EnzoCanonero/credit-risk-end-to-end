# Step 1 — build the production model artifact.
#
# The deployable unit is not this script, it is what it writes: the fitted Pipeline serialised to
# disk, plus a small metadata file describing it. Everything downstream (batch scoring, the API)
# loads that artifact and never retrains. A model that retrains per request is the surest sign of
# code that has never been served.
#
# The shipped model is refit on all available data, train, validation and test together. The test
# has already done its job in notebook 25, giving the unbiased estimate on the same configuration
# fit on train+val; once that estimate exists, holding data back from the model that actually goes
# out only wastes it. So the reported numbers describe the configuration, not this exact object,
# and the metadata says as much.

import json
from datetime import date
from pathlib import Path

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


def main():
    df = load_loans()
    train, val, test = out_of_time_split(df)

    # All available data. The test already gave its unbiased estimate in notebook 25, so holding it
    # out of the shipped model now would only waste it.
    fit_df = pd.concat([train, val, test])

    best = json.loads(PARAMS.read_text())
    pipe = build_lgbm(NUMERIC, CATEGORICAL, params=best)
    pipe.fit(fit_df[COLS], fit_df[TARGET])

    MODELS.mkdir(exist_ok=True)
    joblib.dump(pipe, ARTIFACT)

    # A small json next to the artifact so the file is self-describing: what it is, what it was
    # fitted on, and where its measured performance lives.
    vintages = pd.to_datetime(fit_df["issue_month"])
    meta = {
        "params": best,
        "features": COLS,
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
