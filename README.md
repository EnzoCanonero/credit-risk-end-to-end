# Credit risk on Lending Club

[![Tests](https://github.com/EnzoCanonero/credit-risk-end-to-end/actions/workflows/ci.yml/badge.svg)](https://github.com/EnzoCanonero/credit-risk-end-to-end/actions/workflows/ci.yml)

This project models default risk for Lending Club's 36-month loans using information available to a
lender at origination. The analysis follows three questions in sequence: whose information prices
a loan, whether the resulting probabilities support a lending decision, and how much that decision
is worth.

`int_rate` and `grade` encode Lending Club's verdict on each loan. The borrower-only model excludes
them so that applicant data is evaluated on its own, while the union model adds them back. The
models train on the oldest vintages and are evaluated on newer ones.

## What's here

The target is lifetime default on 36-month loans, and each loan is labelled only after its full
term has elapsed. Without this maturity filter, recent vintages would appear safer because some
defaults would not yet have occurred. SQL applies the filter when building the modelling table.

Leakage is controlled in two stages. SQL removes post-origination columns, including payments,
recoveries and last FICO, from the modelling table. Python then divides the remaining fields into
borrower data and Lending Club's verdict, producing three feature sets: the verdict alone, the
borrower data alone (the underwriter model, which excludes `int_rate` and `grade`), and their union.
The split remains out of time throughout: the oldest vintages form the 375k-loan training set, the
middle vintages form the 155k-loan validation set, and the latest 178k loans form the test set.

## Results

The selected model is a union LightGBM that combines borrower data with Lending Club's verdict.
This feature set outperformed either one alone on validation ([Whose information prices the
loan](#whose-information-prices-the-loan), below). It is then tuned with Optuna, refit on training
and validation data, and scored once on the held-out test. The validation and test metrics are:

| union lgbm         | ROC AUC | PR AUC | Brier | log-loss |
|--------------------|:-------:|:------:|:-----:|:--------:|
| validation (tuned) | 0.699   | 0.279  | 0.120 | 0.392    |
| test               | 0.710   | 0.304  | 0.121 | 0.395    |

Three decision rules are evaluated on realised outcomes: approve every loan, apply one break-even
threshold to the whole book, or approve when each loan's expected profit is positive. Their results
are close, with the single threshold producing the highest total profit. The rules and their
economics are described under [What a decision is worth](#what-a-decision-is-worth):

| policy            | total profit | approved | bad rate |
|-------------------|:------------:|:--------:|:--------:|
| approve all       | 124.9M       | 178,453  | 0.155    |
| single break-even | 129.8M       | 171,344  | 0.143    |
| expected profit   | 126.6M       | 177,247  | 0.153    |

Within a book already screened to Lending Club's accepted loans, the approve-or-reject decision
changes total profit by only a few percent. A single threshold derived from the training book
captures most of this difference. The per-loan rule performs worse on test, mainly because of
high-rate loans that default at 42%; both probability underprediction and the payoff assumptions
contribute to their losses.

### Calibration

The expected-profit calculation uses predicted default probabilities directly, so calibration
affects the decision. On validation, the tuned union model predicts an average default rate of
13.1%, compared with 15.0% observed. The baseline check below shows the same pattern, and isotonic
calibration leaves its validation Brier score unchanged at three decimal places, so the correction
is not carried forward.

![Validation reliability, baseline union LightGBM](reports/reliability_lgbm.png)

On test, the model predicts 13.4% on average, compared with 15.5% observed. The overall gap remains
similar, although it increases in the high-risk tail. Both this underprediction and the high-rate
payoff assumptions contribute to per-loan pricing trailing the single threshold, and the evaluation
does not isolate their effects.

![Validation and test reliability, tuned union LightGBM](reports/reliability_test.png)

## Data layer

The analysis uses two layers: `sql/` prepares and checks the data, while the notebooks handle the
modelling. The SQL files are numbered in groups:

- **`ingest`, `01`** load the raw CSVs into DuckDB and build the modelling table, including the
  lifetime-default target, maturity filter, and exclusions for post-origination columns.
- **`02` to `05`** validate that table through data-quality checks, status mix and default maturation,
  and define the out-of-time split cutoffs.
- **`10` to `12`** provide portfolio context by examining what a Lending Club grade encodes, how
  originations and bad rates changed, and how defaults accumulate as each vintage ages.
- **`20`** contains the feature EDA used to define the underwriter feature list, including
  distributions, outliers, and each field's relationship with default.
- **`30`** estimates the loan economics: interest earned on repaid loans, principal lost on
  defaults, and the two constants used by the decision layer.

## Studies

Five notebooks build towards the result above, with each addressing one question. The first four
train on the training vintages and are evaluated on validation, while the test set remains sealed
until the last notebook.

- [`21_underwriter_vs_lc`](notebooks/21_underwriter_vs_lc.ipynb): whose information prices the loan.
- [`22_validation`](notebooks/22_validation.ipynb): whether scoring out-of-time costs anything.
- [`23_decision_economics`](notebooks/23_decision_economics.ipynb): what a decision on the
  probabilities is worth.
- [`24_tuning`](notebooks/24_tuning.ipynb): whether tuning the model moves it.
- [`25_final_test`](notebooks/25_final_test.ipynb): the single scored look reported above.

### Whose information prices the loan?

Logistic regression and LightGBM are each fitted to three feature sets: Lending Club's verdict,
borrower data, and their union.

| model    | features    | ROC AUC | PR AUC | Brier |
|----------|-------------|:-------:|:------:|:-----:|
| logistic | lc_verdict  | 0.679   | 0.252  | 0.122 |
| logistic | underwriter | 0.663   | 0.244  | 0.122 |
| logistic | union       | 0.691   | 0.266  | 0.121 |
| lgbm     | lc_verdict  | 0.675   | 0.247  | 0.122 |
| lgbm     | underwriter | 0.674   | 0.253  | 0.122 |
| lgbm     | union       | 0.696   | 0.275  | 0.120 |

Borrower data alone performs just below Lending Club's verdict, while their union outperforms both.
LightGBM scores higher on the borrower and union sets, whereas logistic regression scores higher on
the verdict set, which is driven mainly by one monotonic feature. An `LGBMRegressor` recovers about
40% of the variance in `int_rate`, so borrower fields do not reconstruct the price on their own.

### Does the temporal split cost anything?

Every borrower feature has a PSI below 0.04, and an adversarial classifier separates the two
periods with a ROC AUC of 0.63. Adding `int_rate` raises that value to 0.96, yet out-of-time scoring
changes ROC AUC by only 0.003 relative to a random split. `int_rate` shifts in level without
changing the ranking much, and the split remains temporal because it reflects how the model would
be used.

### What a decision is worth

Training-vintage outcomes in `sql/30_loan_economics.sql` estimate a loss of about 0.35 of principal
after recoveries when a loan defaults, while a repaid loan earns interest that rises with the rate.
Because these amounts do not scale together, each loan has its own break-even probability rather
than one threshold for the whole book.

| policy            | total profit | approved | bad rate |
|-------------------|:------------:|:--------:|:--------:|
| approve all       | 132.2M       | 154,703  | 0.150    |
| single break-even | 133.1M       | 151,052  | 0.144    |
| expected profit   | 132.4M       | 154,273  | 0.149    |

On validation, the three policies finish within 1% of each other, with the single threshold ahead
of per-loan pricing. The final test keeps the same ordering and widens the gap. Within a book of
accepted loans, the approve-or-reject decision adds little, and the single threshold returns more
in both periods.

### Tuning

An Optuna search fits the union LightGBM on training data and uses validation log-loss as its
objective rather than a ranking-only metric.

| union lgbm | ROC AUC | PR AUC | Brier | log-loss |
|------------|:-------:|:------:|:-----:|:--------:|
| baseline   | 0.696   | 0.275  | 0.120 | 0.393    |
| tuned      | 0.699   | 0.279  | 0.120 | 0.392    |

The selected configuration uses a 0.01 learning rate and 1734 trees, with little change in the
reported metrics. Notebook 23 evaluates the currency results with the baseline union model, so it
does not measure the effect of tuning on profit. The selected configuration is carried to the final
test.

## Layout

```
sql/        ingestion, the modelling table, and the EDA behind every feature choice
src/        data loading, split, model pipelines, evaluation, drift, and serving
scripts/    build_db, train_baseline, tune_lgbm, build_model (the artifact), score_batch
app/        the FastAPI scoring service
models/     the serialised model artifact and its metadata
tests/      pytest suite for the economics, serving and API
notebooks/  21 underwriter vs Lending Club, 22 validation, 23 decision economics, 24 tuning, 25 final test
reports/    saved figures
docs/       the model card
```

## Running

```
pip install -e .                 # into a Python 3.11 environment
python scripts/build_db.py       # build data/credit_risk.duckdb from the raw CSVs
python scripts/train_baseline.py # the model comparison
python scripts/build_model.py    # fit the final model into models/
uvicorn app.main:app             # serve it, then open http://localhost:8000/docs
```

Or serve it in a container (build the model first, the artifact is not in the image by default):

```
docker build -t credit-risk .
docker run -p 8000:8000 credit-risk
```

## Production layer

`scripts/build_model.py` refits the tuned configuration on all available data and serialises the
Pipeline to `models/`, so scoring does not retrain and preprocessing remains part of the artifact.
`src/credit_risk/serving.py` loads it once and exposes a `score` function used by both
`scripts/score_batch.py` for CSV scoring and `app/main.py` for the FastAPI `/score` route, so batch
and online scoring follow the same path.

The tests cover the economics, serving contract, and model behaviour, while a golden test checks
for train/serve skew (`tests/`). A `Dockerfile` packages the API, and GitHub Actions runs ruff and
the tests on every push (`.github/workflows`). The model card in `docs/model_card.md` records the
model's scope, selection bias, calibration drift on newer vintages, and the economic assumptions
behind the pricing.

## Later, if time

These studies do not affect the tested 36-month model and can be addressed later.

- **60-month loans.** The current model covers 36-month loans only, which keeps a single
  observation horizon. Applying the same fixed-window target to 60-month loans would reintroduce
  the maturity bias, since those loans take 60 months to mature and few recent vintages would
  qualify. A survival or discrete-time hazard model handles this by using each loan for the
  period it was observed and treating the term as a covariate, covering both terms in one model.
- **Selection bias.** The model only ever sees accepted loans, while the rejected file is ingested
  but unused. A later study could place it in a comparable table and examine how accepted and
  rejected applicants differ on shared fields such as amount, DTI, risk score, and employment.
  This would require SQL staging and a supporting notebook.
