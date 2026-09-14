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

The selected LightGBM combines borrower information with Lending Club’s interest rate and grade, using only origination-time predictors and excluding repayment and recovery information to prevent outcome leakage. From approximately 2.26 million accepted-loan records, the analysis retains 708,368 36-month loans with Charged Off or Fully Paid outcomes, issued at least 36 months before the observation cutoff to allow a full term for outcomes to mature. Splitting chronologically by issue month gives approximately 53% training, 22% validation and 25% test, keeping each vintage together.

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

Higher ROC AUC and PR AUC indicate better ranking. Here, ROC AUC of 0.710 suggests useful but imperfect risk separation, while PR AUC of 0.303 is roughly twice the 15.46% prevalence, the random-ranking reference for this book. Brier score and log-loss assess overall probability accuracy, with lower values indicating better predictions. The narrow confidence intervals indicate limited sampling uncertainty within this test period, conditional on the fitted model.

Calibration requires a separate check. The mean prediction is 13.44%, against 15.46% observed defaults: an underestimate of 2.03 percentage points [1.86, 2.20]. The interval lies clearly above zero, supporting underprediction of average risk in this book. The model can therefore rank loans usefully while understating their default probabilities. This matters economically: understated risk can inflate expected-profit estimates and make probability-based approval rules too permissive.

### Economic comparison

Three fixed policies are applied to the same test loans: approve all, a single break-even threshold, and a per-loan expected-profit rule. The single threshold uses the amount-weighted interest rate across training and validation to set one maximum acceptable default probability for the whole book. The expected-profit rule uses each loan’s own rate, allowing higher rates to compensate for higher predicted default risk under the assumed payoffs. Both rules use the same model predictions and payoff assumptions, and neither is adjusted using test profits.

| Policy | Approved loans | Cash-flow profit | Gain over approve all [95% CI] |
|---|---:|---:|---:|
| Approve all | 178,453 | $124.9M | — |
| Single break-even threshold | 171,276 | $129.8M | +$4.84M [$3.84M, $5.90M] |
| Per-loan expected profit | 177,219 | $126.5M | +$1.56M [$1.14M, $2.00M] |

Cash-flow profit is the cash received over each loan’s life—principal repayments, interest and recoveries—less the amount originally lent. Figures are reported in millions of US dollars, without discounting future payments or deducting funding and operating costs, so they represent profit before these adjustments.

The single threshold adds about **3.9% of the approve-all cash-flow profit**. It also earns
**$3.28M [$2.39M, $4.23M]** more than the per-loan rule. The intervals support this ordering,
but the incremental value is modest within a book already screened by Lending Club.

Intervals are 95% percentile intervals from 1,000 bootstrap samples of loans. Models and policies remain fixed, and each comparison uses the same sampled loans for both alternatives, preserving their shared observations. For profit comparisons, the intervals express uncertainty in the expected policy gain for a comparable book of the same size; the recorded cash totals themselves are known. They capture sampling uncertainty within the evaluated population, excluding model refitting, future drift and uncertainty in the economic assumptions.

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

[Notebook 22](notebooks/22_validation.ipynb) measures population change using PSI, which compares individual feature distributions, and adversarial validation, which tests whether features distinguish training from validation loans. Borrower features individually show little movement, with PSI below 0.04, yet together identify the period with ROC AUC 0.67. Adding Lending Club’s rate and grade raises this to 0.96, indicating more pronounced changes in the lender’s assessment and pricing.

A separate experiment examines the benefit of including later information in training, as random splits allow. Using development data only, models train on equally sized past-only or period-mixed samples and score the same 106,588 loans from October 2014 to March 2015. Period-mixed training adds only 0.0033 [0.0020, 0.0046] to ROC AUC for seed 0; the other two seeds support similarly small gains.

A plausible explanation is that some temporal changes, such as shifts in pricing levels, help identify the vintage without greatly changing the relative ordering of default risk. Detectable population change can therefore coexist with fairly stable ranking, while probability calibration may still shift.

[Notebook 24](notebooks/24_tuning.ipynb) reports a tuned-minus-baseline log-loss difference of
**−0.0011 [−0.0013, −0.0008]**, about a **0.3% reduction** from the baseline validation score.
The gain is small, and the interval does not correct the optimism from selecting parameters on
that same validation set. Notebook 25 evaluates the selected configuration on test.

### Why the simpler lending rule earns more

[Notebook 23](notebooks/23_decision_economics.ipynb) translates default probabilities into approval
decisions using [payoffs estimated from training loans](sql/30_loan_economics.sql): gains on repaid
loans and losses on defaults. The single-threshold policy applies one maximum acceptable default
probability across the portfolio. The per-loan rule allows higher predicted risk when a higher
interest rate appears to compensate for potential losses. This flexibility depends on both the
probabilities and the payoff assumptions being realistic.

On validation, the single break-even threshold adds **$0.959M [95% CI: $0.294M, $1.628M]** in cash-flow
profit over approving all, equivalent to approximately **0.7%** of the approve-all profit. The
interval supports a positive gain, although its economic size remains modest within this portfolio
already screened by Lending Club.

The per-loan rule's gain over approving all is **$0.143M [−$0.041M, $0.336M]**. The interval includes
zero, so this comparison does not establish an improvement. Notebook 23 uses the baseline model,
whereas notebook 25 evaluates the tuned configuration on a later book; their profit differences
therefore cannot be interpreted as the effect of tuning.

To understand why the per-loan rule earns less than the single threshold on test, the
[diagnostics in notebook 25](notebooks/25_final_test.ipynb) examine **6,066 loans approved only by
the per-loan rule**. Their mean predicted default risk is **35.3%**, compared with **41.3%** observed,
and their realised cash-flow profit is **−$3.3M**. These additional approvals account for most of
the single threshold's advantage.

| Valuation of those 6,066 loans | Profit |
|---|---:|
| Training payoff formula at predicted probabilities | $3.1M |
| Same formula at observed outcomes | −$0.2M |
| Realised cash flows | −$3.3M |

Replacing predicted probabilities with observed outcomes brings the estimated profit close to break-even. Moving to realised cash flows then reveals a substantially larger loss, highlighting how favourable the assumed payoffs are for these loans. Underestimated default risk removes the apparent profitability, while the payoff mismatch turns a near-break-even result into a material loss. Both therefore contribute substantially to the gap between expected and realised profit.

A plausible explanation is that training-average payoffs transfer poorly to this riskier subset:
higher quoted rates may provide less realised compensation for defaults than the formula assumes.
The diagnostic does not establish whether lower interest receipts, larger principal losses or
weaker recoveries dominate that mismatch.

The reliability plot examines probability calibration across risk bands on validation and test.
Points above the diagonal indicate that observed default rates exceed predictions. Shading shows
**95% pointwise intervals for each bin's observed default rate**, with quantile bins held fixed.
These bands help assess uncertainty within individual bins; they do not provide simultaneous
coverage for the whole curve.

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

This is a **local portfolio project**. Its serving layer is an engineering demonstration of how
the model could support different workloads, with working code and limited AWS checks. No
operational lending service is deployed.

After evaluation, [the artifact builder](scripts/build_model.py) refits the selected configuration
on **all mature loans**, including the original test period. It saves preprocessing and the
classifier as one pipeline, together with metadata describing the features, fitting population
and dependency versions. The reported test metrics belong to the earlier fit on training and
validation; they do not evaluate this final serving artifact.

[Shared scoring code](src/credit_risk/serving.py) loads the pipeline, predicts default probability
and approves loans below a **single portfolio-wide break-even threshold** stored in the metadata.
As in [notebook 25](notebooks/25_final_test.ipynb), that threshold uses the amount-weighted interest
rate on training and validation, excluding test loans from its calculation. `int_rate` remains a
model feature, while the approval cutoff is common to every application. Tests check consistent
predictions and decisions across the three interfaces.

| Interface | Workload it would suit | What this project demonstrates |
|---|---|---|
| [Batch scoring](scripts/score_batch.py) | Periodic bulk processing, such as scoring a portfolio overnight, where results can be collected in a file. | A local CSV command returning loan IDs, default probabilities and approval decisions. Scheduling is a further step. |
| [FastAPI](app/main.py) | Interactive HTTP requests needing an immediate score. A continuously running deployment could suit steady traffic and predictable response times. | A tested HTTP app with validated `/score` requests, `/health`, startup model loading and [Docker packaging](Dockerfile). Hosting and operating the service would follow. |
| [Lambda](infra/aws/lambda/README.md) | Sporadic or bursty requests and independent events, where occasional cold-start delay is acceptable. | A separate handler around the same scoring code. A direct AWS invocation on 2026-08-10 matched local scoring; no public endpoint or event-triggered workflow was configured. Updated code and metadata require a new image deployment. |

FastAPI defines an HTTP application; Lambda supplies managed execution for a handler. Choosing
between these approaches would depend on request volume, latency requirements and cost. Actual
lending use would also require further calibration and policy validation, access controls and
operational monitoring.

[S3](infra/aws/s3/README.md), Glue and [Athena](infra/aws/athena/README.md) demonstrate a separate
analytical workflow for storing and querying curated exports, with four query results checked
against DuckDB. Scoring uses the bundled model and metadata. The infrastructure notes document
configuration, measured timings and cost assumptions from these exercises.

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
