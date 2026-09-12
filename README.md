# Credit risk on Lending Club

[![Tests](https://github.com/EnzoCanonero/credit-risk-end-to-end/actions/workflows/ci.yml/badge.svg)](https://github.com/EnzoCanonero/credit-risk-end-to-end/actions/workflows/ci.yml)

This project models default risk for Lending Club's 36-month loans using information available to a
lender at origination. The analysis follows three questions in sequence: whose information prices
a loan, whether the resulting probabilities support a lending decision, and how much that decision
is worth.

`int_rate` and `grade` encode Lending Club's verdict on each loan. The borrower-only model excludes
them so that applicant data is evaluated on its own, while the union model adds them back. The
models train on the oldest vintages and are evaluated on newer ones.

## Contents

- [What's here](#whats-here)
- [Results](#results)
- [Data layer](#data-layer)
- [Studies](#studies)
- [Layout](#layout)
- [Running](#running)
- [Serving and cloud deployment](#serving-and-cloud-deployment)
- [Later, if time](#later-if-time)

## What's here

The repository covers the path from raw Lending Club files to scored loans. DuckDB and SQL build
the modelling data and a versioned Parquet export. Five notebooks compare feature sets, check the
temporal split, estimate loan economics, tune the model and report one held-out test. The fitted
pipeline is then reused for batch scoring, FastAPI and Lambda.

The AWS work adds raw and curated storage in S3, a Glue catalog queried through Athena, and direct
container inference with ECR and Lambda. The Athena aggregates are checked against DuckDB and the
Lambda response against local scoring. FastAPI is tested and containerised, but it is not hosted.
CI runs the tests, Ruff and mypy, while the model card records the intended use and known limits.

The target is lifetime default on 36-month loans. A loan is labelled only after its full term has
elapsed, so recent vintages do not look artificially safe. SQL also removes post-origination fields
such as payments, recoveries and last FICO. Python compares Lending Club's verdict, borrower data
without `int_rate` or `grade`, and the union of both. The split stays chronological: 375k older loans
for training, 155k for validation and the latest 178k for testing.

## Results

The union LightGBM combines borrower data with Lending Club's verdict and performed best on
validation. It was tuned with Optuna, refit on training and validation, then evaluated once on the
held-out test. The feature comparison is covered under [Whose information prices the
loan](#whose-information-prices-the-loan).

| union lgbm         | ROC AUC | PR AUC | Brier | log-loss |
|--------------------|:-------:|:------:|:-----:|:--------:|
| validation (tuned) | 0.699   | 0.279  | 0.120 | 0.392    |
| test               | 0.710   | 0.304  | 0.121 | 0.395    |

These metrics belong to the model fitted on training and validation. After the test was complete,
`scripts/build_model.py` refitted the chosen configuration on all 708,368 mature loans for serving.
The test results were not recalculated from that final artifact.

Three lending rules are compared on realised test outcomes: approve every loan, use one break-even
threshold for the whole book, or approve loans with positive expected profit. The single threshold
produced the highest total profit. The assumptions are explained under
[What a decision is worth](#what-a-decision-is-worth).

| policy            | total profit | approved | bad rate |
|-------------------|:------------:|:--------:|:--------:|
| approve all       | 124.9M       | 178,453  | 0.155    |
| single break-even | 129.8M       | 171,344  | 0.143    |
| expected profit   | 126.6M       | 177,247  | 0.153    |

Within a book already screened to Lending Club's accepted loans, the approve-or-reject decision
changes total profit by only a few percent. A single threshold derived from the training book
captures most of this difference. The per-loan rule performs worse on test, mainly because of
high-rate loans that default at 42%. Both probability underprediction and the payoff assumptions
contribute to their losses.

The cloud implementation keeps the same data and scoring contracts. Curated `v1` contains
2,260,668 accepted loans, all four Athena queries match the corresponding DuckDB aggregates, and
the sample Lambda response matches the local service. Deployment measurements and costs are
summarised under [Serving and cloud deployment](#serving-and-cloud-deployment).

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

### Calibration

The tuned model is moderately undercalibrated: it predicts 13.1% default on validation versus
15.0% observed, and 13.4% versus 15.5% on test. This does not invalidate its ranking, but it makes
the probabilities too low on average and can bias expected-profit estimates and approval decisions.
The isotonic check is not the best remedy here: it learns a flexible mapping inside the older
training sample, whereas the observed error is mainly a later shift in the probability level. Its
validation Brier score was consequently unchanged at the reported precision.

In both reliability plots, shading shows 95% pointwise bootstrap intervals for the observed
default rate in each score bin (1,000 resamples, seed 0), with predictions and the original
quantile bins fixed. These describe sampling uncertainty within each bin; notebook 25's gap
intervals assess underprediction directly. They do not give joint coverage for the whole curve
or account for future drift.

![Validation reliability, baseline union LightGBM](reports/reliability_lgbm.png)

A proper correction would use four chronological blocks: **train → tuning → calibration → final
test**. After model selection, an intercept is fitted only on the calibration block,
`logit(p_cal) = a + logit(p_raw)`, and then frozen before the final test. This preserves ranking
while updating the probability level. It would require rerunning tuning without the calibration
block and then recomputing the probability-based economic policies; the current results therefore
remain uncalibrated rather than applying a post-hoc correction.

![Validation and test reliability, tuned union LightGBM](reports/reliability_test.png)

## Layout

```
sql/        ingestion, the curated contract, the modelling table, and feature-choice EDA
src/        data loading, split, model pipelines, evaluation, drift, and serving
scripts/    build_db, export_curated, training, tuning, artifact build, and batch scoring
app/        the FastAPI scoring service
models/     the serialised model artifact and its metadata
tests/      pytest suite for curation, economics, serving and API
notebooks/  21 underwriter vs Lending Club, 22 validation, 23 decision economics, 24 tuning, 25 final test
reports/    saved figures and the verified Athena parity report
docs/       the model card
infra/      reviewed AWS service configuration applied manually with the AWS CLI
```

## Running

```
pip install -e .                 # into a Python 3.12 environment
python scripts/build_db.py       # build data/credit_risk.duckdb from the raw CSVs
python scripts/export_curated.py # write partitioned Parquet under data/curated/
python scripts/run_athena_analysis.py # verify DuckDB/Athena parity and record scan metrics
python scripts/train_baseline.py # the model comparison
python scripts/build_model.py    # fit the final model into models/
uvicorn app.main:app             # serve it, then open http://localhost:8000/docs
```

The curated export keeps every accepted-loan source column, adds typed timing and term fields, and
removes only the non-loan summary rows appended to the CSV. It writes schema version `v1`, treated
as immutable by convention, as Snappy Parquet partitioned by `source_snapshot` and `issue_year`.
The exporter refuses to overwrite an existing version directory; rebuild into a new schema version
or remove a reviewed local generated export explicitly.

Or serve it in a container (build the model first; the generated artifact is not version-controlled):

```
docker build -t credit-risk .
docker run -p 8000:8000 credit-risk
```

## Serving and cloud deployment

`scripts/build_model.py` saves the fitted preprocessing and model in one scikit-learn `Pipeline`.
`src/credit_risk/serving.py` loads that artifact once and provides the scoring code used by batch
jobs, FastAPI and Lambda. FastAPI and Lambda also use the same validated `Loan` schema and
`score_one` function. Tests include a fixed prediction to catch differences between training and
serving.

FastAPI provides an HTTP API and needs a container host. Lambda runs the same scoring logic as
managed, event-driven compute. Neither serving path queries S3 or Athena at request time. Those
services make up the separate data and analytics layer.

### FastAPI

`app/main.py` exposes `/health` and `/score`, loads the model at startup and validates requests
before scoring them. The standard `Dockerfile` packages the app as an HTTP container suited to
sustained traffic and predictable latency.

To host it on AWS, the FastAPI image could be pushed to its own ECR repository and deployed with
ECS Express Mode. The service would need a task execution role, an infrastructure role, port `8000`,
an HTTP health check at `/health` and chosen scaling limits. AWS would then create the Fargate
service, load balancer, HTTPS endpoint, networking and autoscaling configuration.

That deployment is not included here. Without a traffic profile, SLA or authentication
requirements, there is no useful target against which to size or evaluate the service. A public
endpoint would still add recurring compute, load-balancer and logging costs, along with security
and operations work. The repository provides a tested container rather than a hosted FastAPI
service, so no hosting cost is quoted.

### AWS

| Component | Result | Estimated list-price cost | Details |
|---|---|---:|---|
| S3 | 2.26M loans in raw and partitioned curated layers | $0.011/month after day 90 | [data foundation](infra/aws/s3/README.md) |
| Athena | four economic queries matching the DuckDB aggregates | $0.00025 per run | [analytical layer](infra/aws/athena/README.md) |
| Lambda + ECR | container inference using the shared scoring contract | $0.029/month at 1,000 warm calls | [Lambda scoring](infra/aws/lambda/README.md) |

Athena scanned 5.38% of the curated data for the rate-band analysis and 1.78% for the training
constants. These are shares of the stored data, not savings against a `SELECT *` control query.
Lambda returned the same prediction as the local service. Its measured cold initialization took
4.23 seconds, while an immediate warm invocation took 15.38 ms. The query results and scan metrics
are recorded in the [Athena report](reports/athena/2018Q4_v1.md).

### When to use each

At the current data volume, storage after the day-90 transition, one Athena analysis and 1,000 warm
Lambda calls total about $0.04 per month at AWS list prices. This excludes free-tier credits, tax,
request charges, logs and a public API. There is no FastAPI estimate because hosting was not
implemented and its cost would depend on the chosen task size and minimum capacity.

A hosted FastAPI service fits steady HTTP traffic and tighter latency requirements. Lambda fits
occasional or event-driven scoring when a multi-second cold start is acceptable. Exposing the
current Lambda through HTTP would also require an HTTP adapter and either API Gateway or a Function
URL. The choice between them does not affect the S3 and Athena analytics layer.

## Later, if time

These studies do not affect the tested 36-month model and can be addressed later.

- **60-month loans.** The current model covers 36-month loans only, which keeps a single
  observation horizon. Applying the same fixed-window target to 60-month loans would reintroduce
  the maturity bias, since those loans take 60 months to mature and few recent vintages would
  qualify. A survival or discrete-time hazard model handles this by using each loan for the
  period it was observed and treating the term as a covariate, covering both terms in one model.
  Its cumulative default probabilities would then be calibrated at the relevant horizons on a
  separate chronological calibration block, rather than reusing the 36-month adjustment.
- **Selection bias.** The model only ever sees accepted loans, while the rejected file is ingested
  but unused. A later study could place it in a comparable table and examine how accepted and
  rejected applicants differ on shared fields such as amount, DTI, risk score, and employment.
  This would require SQL staging and a supporting notebook.
