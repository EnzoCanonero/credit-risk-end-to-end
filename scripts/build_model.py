# Builds the credit risk model and its approval policy.

import argparse
import json
import platform
from datetime import date
from importlib.metadata import version

import joblib
import pandas as pd

from credit_risk.data import load_loans, REPO_ROOT
from credit_risk.split import out_of_time_split
from credit_risk.evaluate import breakeven_probability
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


# Builds the model and metadata, or refreshes only the approval policy.
def main() -> None:
    parser = argparse.ArgumentParser(description="Build the model and its approval policy.")
    parser.add_argument(
        "--policy-only", action="store_true",
        help="Update existing approval metadata without refitting the model.",
    )
    args = parser.parse_args()

    df = load_loans()
    train, val, test = out_of_time_split(df)

    # Matches notebook 25: estimate the threshold before the final test period.
    reference = pd.concat([train, val])
    r_bar = (reference["int_rate"] * reference["loan_amnt"]).sum() / reference["loan_amnt"].sum()
    policy = {
        "name": "single_break_even",
        "threshold": float(breakeven_probability(r_bar)),
        "reference": "train+val",
        "amount_weighted_int_rate": float(r_bar),
        "n_reference_rows": len(reference),
    }

    if args.policy_only:
        meta = json.loads(METADATA.read_text())
        meta["approval_policy"] = policy
        METADATA.write_text(json.dumps(meta, indent=2))
        print(f"approval policy -> {METADATA}")
        return

    fit_df = pd.concat([train, val, test])

    best = json.loads(PARAMS.read_text())
    pipe = build_lgbm(NUMERIC, CATEGORICAL, params=best)
    pipe.fit(fit_df[COLS], fit_df[TARGET])

    MODELS.mkdir(exist_ok=True)
    joblib.dump(pipe, ARTIFACT)

    vintages = pd.to_datetime(fit_df["issue_month"])
    meta = {
        "approval_policy": policy,
        "params": best,
        "features": COLS,
        "numeric": NUMERIC,
        "categorical": CATEGORICAL,
        "n_fit_rows": len(fit_df),
        "fit_vintages": [vintages.min().strftime("%Y-%m"), vintages.max().strftime("%Y-%m")],
        "built": date.today().isoformat(),
        "python": platform.python_version(),
        "dependencies": {
            package: version(package)
            for package in (
                "joblib",
                "lightgbm",
                "numpy",
                "pandas",
                "scipy",
                "scikit-learn",
            )
        },
        "fit_on": "train+val+test, all available data",
        "performance": "unbiased estimate in notebooks/25_final_test (same config fit on train+val)",
    }
    METADATA.write_text(json.dumps(meta, indent=2))

    print(f"artifact  -> {ARTIFACT}")
    print(f"metadata  -> {METADATA}")
    print(f"fitted on {len(fit_df)} loans, vintages {meta['fit_vintages'][0]} to {meta['fit_vintages'][1]}")


if __name__ == "__main__":
    main()
