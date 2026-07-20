# Credit risk on Lending Club

This project models default risk for Lending Club's 36-month loans using information available
at origination. It compares borrower features with Lending Club's risk assessment and evaluates
whether combining both sets improves performance.

`int_rate` and `grade` reflect Lending Club's assessment of each loan. The borrower-only model
excludes them, while the benchmark and union models use them for comparison.

## What's here

The target is lifetime default (charged off versus fully paid) on 36-month loans. A loan is
labelled only after it has been observed for its full term. Without this maturity filter, recent
vintages would have incomplete outcomes and appear safer than older vintages. The filter is
applied in SQL when the modelling table is built.

Feature availability is handled in two places:

- **SQL:** Post-origination columns such as payments, recoveries, and last FICO are excluded from
  the modelling table.
- **Python:** Feature lists separate borrower variables from Lending Club's assessment. The
  underwriter model excludes `int_rate` and `grade`.

The split is out-of-time: train on the oldest vintages, tune on the middle, test on the most
recent. This setup evaluates performance on loans issued after those used for training. Logistic
regression and LightGBM are fitted on three feature sets: Lending Club's verdict, borrower data,
and the union of both.

## Results (validation)

```
               roc_auc   pr_auc   brier
logistic
  lc_verdict     0.679    0.252   0.122
  underwriter    0.663    0.244   0.122
  union          0.691    0.266   0.121
lgbm
  lc_verdict     0.675    0.247   0.122
  underwriter    0.674    0.253   0.122
  union          0.696    0.275   0.120
```

- The borrower-only model performs close to the Lending Club verdict model. The union model
  performs better than either feature set alone.
- An `LGBMRegressor` explains approximately 40% of the variance in `int_rate`, so the available
  borrower variables do not fully reproduce Lending Club's pricing.
- LightGBM performs better on the borrower and union sets. Logistic regression performs better
  on the Lending Club verdict set, which consists of smooth, monotonic risk information.
- Validation results show good overall calibration, with mild underprediction in the high-risk
  tail. This may reflect changes in the loan population over time.

## Layout

```
sql/        ingestion, the modelling table, and the EDA behind every feature choice
src/        data loading, out-of-time split, model pipelines, evaluation
scripts/    train_baseline.py: the reproducible run, two models by three feature sets
notebooks/  underwriter and Lending Club feature-set analysis
reports/    saved figures
```

## Running

```
pip install -e .                 # into a Python 3.11 environment
# build data/credit_risk.duckdb from the raw CSVs by running the files in sql/ in order
python scripts/train_baseline.py
```

## Roadmap

Everything that selects the model runs before the test set is opened. The test is scored once,
after these steps are frozen.

- **Validation rigor.** Compare the temporal split with a random split and measure feature shift
  using PSI and adversarial validation. Add a `drift` module, a random split implementation, and
  a supporting notebook.
- **Hyperparameter tuning.** Tune the LightGBM union model with Optuna after the validation work
  is complete.
- **Final test.** Evaluate the selected model once on the untouched test set.

## Production layer

- **Serving.** A batch scoring script and a minimal FastAPI endpoint with a single route, not a
  full service.
- **Quality gates.** Tests with pytest covering data validation, model invariances, and the API
  contract; a Dockerfile; and GitHub Actions for lint and tests.
- **Model card.** Assumptions, target population, known bias, limits, and guidance on when not to
  use the model.

## Later, if time

These studies do not change the 36-month model that was tested, so they can follow it.

- **Selection bias.** The model only ever sees accepted loans. The rejected file is ingested but
  unused; bring it into a comparable table and characterise how accepted and rejected applicants
  differ on shared fields such as amount, DTI, risk score, and employment. Add SQL staging and a
  supporting notebook.
- **60-month loans.** The current model covers 36-month loans only, which keeps a single
  observation horizon. Applying the same fixed-window target to 60-month loans would reintroduce
  the maturity bias, since those loans take 60 months to mature and few recent vintages would
  qualify. A survival or discrete-time hazard model handles this by using each loan for the
  period it was observed and treating the term as a covariate, covering both terms in one model.
