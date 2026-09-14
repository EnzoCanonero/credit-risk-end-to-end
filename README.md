# Credit risk on Lending Club

[![Tests](https://github.com/EnzoCanonero/credit-risk-end-to-end/actions/workflows/ci.yml/badge.svg)](https://github.com/EnzoCanonero/credit-risk-end-to-end/actions/workflows/ci.yml)

This project connects default prediction to lending decisions using Lending Club's accepted
36-month loans. It examines what borrower information adds to the lender's own assessment, how
models perform on later vintages, and whether predictive gains translate into better economic
outcomes.

The emphasis is on putting results in perspective: their magnitude, uncertainty and practical
meaning. Combining information sources improves ranking on validation, but the selected model
still underpredicts average default risk. A per-loan expected-profit rule also earns less than a
single break-even threshold in the historical comparisons. The analysis examines why, separating
the contribution of probability errors from the assumptions used to value repayment and default.

## What's here

- **A defined modelling population:** SQL and DuckDB establish the target, maturity requirements,
  data-quality checks and features available at origination.
- **Five connected studies:** information value, temporal validation, decision economics, tuning
  and final evaluation, with confidence intervals and interpretation alongside the results.
- **A scoring demonstration:** preprocessing and model packaged together, with shared inference
  for batch scoring, a tested FastAPI app packaged in Docker and an AWS Lambda implementation.
- **Supporting engineering:** versioned Parquet, S3 and Athena analysis checked against DuckDB,
  automated tests and a [model card](docs/model_card.md) documenting scope and limitations.

[Results](#results) · [Walkthrough](#walkthrough) · [Serving and deployment](#serving-and-deployment) ·
[Repository guide](#repository-guide) · [Run locally](#run-locally)

## Results

The selected LightGBM combines borrower information with Lending Club's interest rate and grade.
[Notebook 25](notebooks/25_final_test.ipynb) evaluates it on **178,453 test loans** (default rate
**15.46%**) after fitting on training and validation. Test loans are excluded from that fit,
parameter search and the [split-design diagnostics](#time-and-tuning).

### Model performance

| Metric | Test estimate | 95% confidence interval |
|---|---:|---:|
| ROC AUC | 0.7099 | [0.7066, 0.7130] |
| PR AUC (average precision) | 0.3031 | [0.2978, 0.3082] |
| Brier score | 0.1214 | [0.1203, 0.1226] |
| Log-loss | 0.3950 | [0.3919, 0.3981] |

Higher ROC AUC and PR AUC indicate better ranking; lower Brier score and log-loss indicate better
probability predictions. PR AUC also depends on the book's default prevalence. The narrow
intervals quantify precision within this test period.

Calibration requires a separate check: the mean observed default rate exceeds
the mean prediction by **2.03 percentage points [1.86, 2.20]**. Ranking performance therefore
coexists with a clear underestimate of average risk.

### Economic comparison

Three fixed policies are applied to the same test loans. The single break-even threshold uses
the amount-weighted rate across training and validation; the expected-profit rule uses each loan's
rate. Neither rule is adjusted using test profits.

| Policy | Approved loans | Cash-flow profit | Gain over approve all [95% CI] |
|---|---:|---:|---:|
| Approve all | 178,453 | $124.9M | — |
| Single break-even threshold | 171,276 | $129.8M | +$4.84M [$3.84M, $5.90M] |
| Per-loan expected profit | 177,219 | $126.5M | +$1.56M [$1.14M, $2.00M] |

Cash-flow profit is principal repayments, interest and recoveries less amounts lent, over the
loans' lives. Figures are undiscounted millions of US dollars and exclude funding and operating
costs. Rejected loans contribute zero.

The single threshold adds about **3.9% of the approve-all cash-flow profit**. It also earns
**$3.28M [$2.39M, $4.23M]** more than the per-loan rule. The intervals support this ordering,
but the incremental value is modest within a book already screened by Lending Club.

Intervals are 95% percentile intervals from 1,000 bootstrap samples of loans. Models and policies
stay fixed, and comparisons use the same loans on both sides. Profit intervals describe
differences for comparable books of the same size; recorded cash totals are known. They exclude
refitting, future drift and uncertainty in the economic assumptions.

## Walkthrough

### Define the population before fitting the model

The curated archive contains 2.26 million accepted-loan records; the modelling cohort contains
**708,368 mature 36-month loans** with `Fully Paid` or `Charged Off` outcomes. A full observation
term prevents recent vintages from appearing artificially safe; post-origination payment and
recovery fields are excluded from features.

[Cohort construction](sql/01_clean_schema.sql), [maturation analysis](sql/04_default_maturation.sql)
and [vintage analysis](sql/11_monthly_originations.sql) establish these choices before the Python
studies. Results concern loans Lending Club accepted, with its assigned rate and grade available;
they do not establish performance across the full applicant population.

### What adds predictive information?

[Notebook 21](notebooks/21_underwriter_vs_lc.ipynb) compares borrower data, Lending Club's verdict
(`int_rate` and `grade`), and their union, using logistic regression and LightGBM.

| Validation comparison | ROC AUC gain [95% CI] |
|---|---:|
| Add borrower information to the verdict, using LightGBM | +0.0215 [0.0196, 0.0238] |
| Switch from logistic regression to LightGBM, using union features | +0.0054 [0.0042, 0.0066] |

Combining information sources contributes more here than changing the model class. For LightGBM,
borrower data and the verdict perform similarly alone: their ROC AUC and Brier differences remain
uncertain, while borrower data has a small PR AUC advantage.

### Time and tuning

[Notebook 22](notebooks/22_validation.ipynb) finds detectable population change between training
and validation. A separate split-design experiment stays within those development loans: models
train on past-only or period-mixed samples and score the same **106,588 loans from October 2014
to March 2015**. Period-mixed training adds **0.0033 [0.0020, 0.0046]** to ROC AUC for seed 0;
the other two seeds support similarly small gains. Later information comes only from development
vintages, with the final test period excluded. These intervals describe the internal comparison;
small changes in ranking do not guarantee stable calibration.

[Notebook 24](notebooks/24_tuning.ipynb) reports a tuned-minus-baseline log-loss difference of
**−0.0011 [−0.0013, −0.0008]**, about a **0.3% reduction** from the baseline validation score.
The gain is small, and the interval does not correct the optimism from selecting parameters on
that same validation set. Notebook 25 evaluates the selected configuration on test; it does not
measure a test improvement over the baseline.

### Why the simpler lending rule earns more

[Notebook 23](notebooks/23_decision_economics.ipynb) translates probabilities into decisions using
[payoffs estimated from training loans](sql/30_loan_economics.sql). The per-loan rule tolerates a
higher default probability when a higher interest rate appears to compensate for losses. That
flexibility depends on both the probabilities and the assumed payoffs being realistic.

The [test diagnostics](notebooks/25_final_test.ipynb) examine **6,066 loans** approved only by the
per-loan rule. Their mean predicted default risk is **35.3%**, against **41.3%** observed, and
their realised cash-flow profit is **−$3.3M**.

| Valuation of those 6,066 loans | Profit |
|---|---:|
| Training payoff formula at predicted probabilities | $3.1M |
| Same formula at observed outcomes | −$0.2M |
| Realised cash flows | −$3.3M |

Both substitutions reduce profit. Underestimated default risk and favourable payoff assumptions
therefore contribute to the result; the policy gap cannot be attributed to calibration alone.

On validation, the per-loan rule's gain over approving all is **$0.143M [−$0.041M, $0.336M]** and
remains uncertain. Notebook 23 uses the baseline model; notebook 25 uses the tuned configuration
on a different book. Their profit gaps are separate backtests, not a measured effect of tuning.

The reliability plot shows the selected configuration on validation and test. Shading gives
**95% pointwise intervals for each bin's observed default rate**, with quantile bins fixed.
The gap intervals assess underprediction directly; the bands do not provide whole-curve coverage.

![Tuned union LightGBM reliability on validation and test, with 95% pointwise bootstrap bands](reports/reliability_test.png)

<details>
<summary>Earlier calibration check: baseline LightGBM, raw versus isotonic</summary>

The [baseline script](scripts/train_baseline.py) fits the isotonic check inside older training
vintages. Both validation Brier scores round to 0.1200. The bands use shared sampled validation
loans across both models.

![Baseline union LightGBM reliability on validation, raw versus isotonic, with 95% pointwise bootstrap bands](reports/reliability_lgbm.png)

</details>

A further calibration study would reserve a chronological calibration block after model
selection and a later evaluation block. The current probability and economic results remain
uncalibrated. Extending them to new applicants, longer loan terms or later lending conditions
would require a corresponding population and outcome design.

## Serving and deployment

After evaluation, [the artifact builder](scripts/build_model.py) refits the selected configuration
on all mature loans, saving preprocessing, model and metadata. The test metrics belong to the
earlier fit on training and validation. [Shared scoring code](src/credit_risk/serving.py) supports batch
inference and both API adapters, with tests for consistent predictions.

Approval uses a **single portfolio-wide break-even threshold**, calculated from the amount-weighted
interest rate on training and validation as in [notebook 25](notebooks/25_final_test.ipynb) and saved
in the model metadata. FastAPI, Lambda and batch scoring approve below this threshold; `int_rate`
remains a model feature. This demonstrates a decision rule, without establishing a validated
lending policy.

| Component | What is demonstrated |
|---|---|
| [FastAPI](app/main.py) | Validated `/score` requests, `/health` and startup model loading; tested app packaged in Docker, not hosted |
| [Lambda and ECR](infra/aws/lambda/README.md) | A direct AWS invocation recorded on 2026-08-10, matching local scoring at that time; no public HTTP endpoint |
| [S3](infra/aws/s3/README.md), Glue and [Athena](infra/aws/athena/README.md) | A separate data and analytical layer, with four query results checked against DuckDB |

FastAPI defines the HTTP application; Lambda runs a separate handler around the same inference
code. Hosting FastAPI would be the next deployment step, with access, monitoring and
capacity decisions based on an actual workload. Neither route queries S3 or Athena during scoring.

The infrastructure notes retain configuration, measured timings and cost assumptions. Lending
use would additionally need further calibration and policy validation, decision governance and
monitoring beyond this personal project's demonstration.

## Repository guide

| Location | Role in the project |
|---|---|
| [`sql/`](sql/) | Ingestion, cohort construction, data checks, portfolio analysis and economic assumptions |
| [`notebooks/`](notebooks/), [`reports/`](reports/) | Studies 21–25, saved figures and verified analytical results |
| [`src/credit_risk/`](src/credit_risk/), [`scripts/`](scripts/) | Reusable modelling/scoring code and database, export, tuning and artifact jobs |
| [`app/`](app/), [`Dockerfile`](Dockerfile), [`Dockerfile.lambda`](Dockerfile.lambda) | HTTP and Lambda adapters and their container builds |
| [`infra/aws/`](infra/aws/) | Cloud configuration and deployment records |
| [`tests/`](tests/), [CI](.github/workflows/ci.yml), [`docs/`](docs/) | Automated checks and the model's intended use and limitations |
| `data/`, `models/` | Local datasets and fitted model binaries; generated model metadata is version-controlled |

## Run locally

Use Python 3.12 and place the source CSVs at the paths specified in [the ingestion SQL](sql/ingest.sql).
From the repository root:

```bash
pip install -e ".[dev]"
python scripts/build_db.py        # build the modelling database
python scripts/export_curated.py  # export versioned Parquet
```

Read or run notebooks 21–25 for the analysis, using the installed environment as their kernel.
To build and serve the demonstration artifact using the saved configuration:

```bash
python scripts/build_model.py
uvicorn app.main:app
```

For an existing model, `python scripts/build_model.py --policy-only` updates the approval metadata
without refitting. Restart serving processes to load updated metadata. Rebuild container images
after updating code or metadata; Lambda also requires publishing the image and updating the function.

Open [the local API documentation](http://localhost:8000/docs), or use the
[batch scorer](scripts/score_batch.py). The [standard Dockerfile](Dockerfile) provides the
container alternative. Cloud setup and its separate credentials are documented under
[`infra/aws/`](infra/aws/).
