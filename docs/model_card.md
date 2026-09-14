# Model card — Lending Club 36-month default

Following the model-card format of Mitchell et al. (2019): what the model does, on whom, how well,
and, above all, where it stops being trustworthy.

## Overview

- **Task.** Predict the probability that a 36-month Lending Club loan ends in charge-off rather than
  full repayment, using only information available at origination.
- **Model.** A LightGBM classifier on the union feature set (borrower application data together with
  Lending Club's own verdict), tuned with Optuna in [notebook 24](../notebooks/24_tuning.ipynb).
  The serving artifact is built by [scripts/build_model.py](../scripts/build_model.py).
- **Purpose.** A local portfolio project examining how default predictions translate into lending
  decisions and economic outcomes. [Notebook 23](../notebooks/23_decision_economics.ipynb) develops
  the decision layer. Serving code and limited AWS checks demonstrate possible uses; no operational
  lending service is deployed.

## Intended use

- **Supports** a demonstration lending decision on 36-month consumer loans of the kind Lending Club
  originated: approve below the single portfolio-wide break-even probability saved in the model
  metadata. The threshold uses the amount-weighted interest rate on training and validation,
  as in [notebook 25](../notebooks/25_final_test.ipynb), and is shared by FastAPI, Lambda and batch scoring.
- **Primary audience.** Underwriting or portfolio analysts reviewing the modelling and decision
  analysis, with the limitations below.
- **Not for** live lending decisions without further validation; applicants unlike Lending Club's
  accepted population; fair-lending, adverse-action, or causal reasoning. It estimates default risk
  under past conditions and does not establish causal explanations for decisions.

## Data

- **Population.** From approximately 2.26 million accepted-loan records, the analysis retains
  **708,368 36-month loans** with terminal `Charged Off` or `Fully Paid` status, issued at least
  36 months before the observation cutoff to allow a full term for outcomes to mature. The
  rejected-applicant file is not used (see Limitations).
- **Split.** Chronological by issue month, keeping each vintage together: **375,212 training,
  154,703 validation and 178,453 test loans**, approximately **53% / 22% / 25%**. The split-design
  experiment in [notebook 22](../notebooks/22_validation.ipynb) uses an internal split of training
  and validation loans, excluding the final test period.
- **Serving artifact.** Refit on all mature loans (vintages 2007-06 to 2016-03) after the final
  evaluation, including the original test period. The numbers below describe the same configuration
  fit on training and validation only; they do not evaluate the final serving artifact. The approval
  threshold is calculated on training and validation, excluding test loans.
- **Leakage discipline.** Post-origination columns (payments, recoveries, last FICO) are excluded in
  SQL when the modelling table is built to prevent direct outcome leakage.

## Features

29 features: 22 numeric and 7 categorical. Borrower application data (loan amount, income, DTI, FICO,
delinquency and derogatory history, engineered ratios) plus Lending Club's verdict, `int_rate` and
`grade`. In [notebook 21](../notebooks/21_underwriter_vs_lc.ipynb), a borrower-only regression explains
about 40% of the validation variation in `int_rate` (R² = 0.38). The available fields do not fully
reproduce the lender's pricing in this experiment.

## Performance

[Notebook 25](../notebooks/25_final_test.ipynb) evaluates the selected configuration on
**178,453 held-out test loans**, with **15.46%** observed defaults.

| Metric | Test estimate | 95% confidence interval |
|---|---:|---:|
| ROC AUC | 0.7099 | [0.7066, 0.7130] |
| PR AUC (average precision) | 0.3031 | [0.2978, 0.3082] |
| Brier score | 0.1214 | [0.1203, 0.1226] |
| Log-loss | 0.3950 | [0.3919, 0.3981] |

Ranking is useful but imperfect; PR AUC is roughly twice this book's default prevalence.
Probability accuracy also depends on calibration, discussed below.

Three fixed policies are compared on the same test loans. The per-loan rule uses each loan's own
interest rate; neither rule is adjusted using test profits. Cash-flow profit is principal repayments,
interest and recoveries less amounts lent, over the loans' lives. Figures are **undiscounted
millions of US dollars**, excluding funding and operating costs; rejected loans contribute zero.

| Policy | Cash-flow profit | Gain over approve all [95% CI] |
|---|---:|---:|
| Approve all | $124.9M | — |
| Single break-even threshold | $129.8M | +$4.84M [$3.84M, $5.90M] |
| Per-loan expected profit | $126.5M | +$1.56M [$1.14M, $2.00M] |

The single threshold adds about **3.9%** of the approve-all profit and earns
**$3.28M [$2.39M, $4.23M]** more than the per-loan rule. These gains concern this historical,
pre-screened book. The [test diagnostics](../notebooks/25_final_test.ipynb) point to both
underestimated default risk and favourable payoff assumptions behind the per-loan rule's lower
profit; calibration alone does not explain the gap.

All intervals are **95% percentile intervals from 1,000 bootstrap samples of loans**, with the
model and policies fixed. Comparisons resample the same loans on both sides. Profit intervals
quantify uncertainty in policy gains for comparable books of the same size; recorded cash totals
are known. The intervals exclude refitting, future drift and uncertainty in economic assumptions.

## Calibration

Mean predicted default risk is **13.44%**, against **15.46%** observed on test. The observed rate
exceeds the mean prediction by **2.03 percentage points [95% CI: 1.86, 2.20]**, supporting
underprediction of average risk. Probabilities that are too low can inflate expected-profit estimates and make
approval rules too permissive.

The [selected-model reliability plot](../reports/reliability_test.png) examines validation and
test, with 95% pointwise intervals for observed default rates in fixed quantile bins; these do not
provide whole-curve coverage. The earlier [baseline isotonic check](../reports/reliability_lgbm.png)
left validation Brier unchanged at the reported precision. That experiment does not establish an
adequate correction for the selected model.

A further study would reserve four chronological blocks: **train → tuning → calibration →
final test**. After model selection, an intercept-only update,
`logit(p_cal) = a + logit(p_raw)`, is one candidate if diagnostics support a shift in probability
level. It would preserve ranking, but its adequacy must be checked. Fit calibration on its own
block, then evaluate probabilities and fixed decision policies on the later held-out block.
The current artifact and reported results remain uncalibrated.

## Limitations

- **Selection bias.** The model only sees loans Lending Club accepted. Performance on rejected
  applicants has not been established, and the rejected file has not been used to assess population
  differences.
- **Calibration.** Historical ranking performance does not establish accurate default probabilities
  for a future book. The documented average-risk gap matters for probability-based decisions.
- **Economic assumptions.** Training-average repayment and default payoffs may transfer poorly to
  later or riskier loans. The break-even threshold uses the training and validation book's rate;
  historical policy gains do not establish profitability under different pricing, recovery or
  cost conditions.
- **Scope.** 36-month loans only. A 60-month extension would need either a terminal-outcome cohort
  with sufficient observation time, or genuine event-history data for survival modelling. Either
  design would require its own chronological calibration and evaluation.

## When not to use it

- 60-month loans, or any term other than 36 months.
- Populations unlike Lending Club's accepted book (different geography, product, or era).
- As a fair-lending, adverse-action, or causal tool.
- On later vintages without checking calibration and population drift.

## Maintenance

For a future operational service, the following would be needed beyond the current demonstration:

- **Monitor** observed versus predicted default rates by vintage and input feature distributions
  for drift. The PSI and adversarial checks in [notebook 22](../notebooks/22_validation.ipynb)
  provide a starting point.
- **Recalibrate** after model selection using a later calibration block. An intercept update is a
  candidate for an average-risk shift, subject to evaluation on a still later held-out block.
- **Re-evaluate** a changed model or policy on a fresh, later held-out period before fitting a new
  serving artifact. Repeated use of the original test set would not provide an independent estimate.
  After evaluation, [scripts/build_model.py](../scripts/build_model.py) refits on all mature loans.

For the existing demonstration, `python scripts/build_model.py --policy-only` updates the threshold
and its reference population without refitting the model. Restart serving processes to load updated
metadata; rebuild images and update the Lambda function separately to deploy the change.
