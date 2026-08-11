# Model card — Lending Club 36-month default

Following the model-card format of Mitchell et al. (2019): what the model does, on whom, how well,
and, above all, where it stops being trustworthy.

## Overview

- **Task.** Predict the probability that a 36-month Lending Club loan ends in charge-off rather than
  full repayment, using only information available at origination.
- **Model.** A LightGBM classifier on the union feature set (borrower application data together with
  Lending Club's own verdict), tuned with Optuna (`notebooks/24_tuning`). The served artifact is
  built by `scripts/build_model.py`.
- **Purpose.** To inform an approve-or-reject decision priced in currency, not to be a score read on
  its own. The decision layer is worked out in `notebooks/23_decision_economics`.

## Intended use

- **Supports** a lending decision on 36-month consumer loans of the kind Lending Club originated:
  turn the probability into an expected profit per loan and approve when it is positive, or apply a
  single break-even threshold set on the training book.
- **Primary users** are underwriting or portfolio analysts who understand the limitations below.
- **Not for**: a standalone yes/no oracle without the economic rule around it; applicants unlike
  Lending Club's accepted population; fair-lending, adverse-action, or causal reasoning. It ranks and
  prices risk under past conditions; it does not explain a decision and it does not establish cause.

## Data

- **Population.** Lending Club accepted 36-month loans with terminal `Charged Off` or `Fully Paid`
  status. The rejected-applicant file is not used (see Limitations).
- **Split.** Out-of-time: trained on the oldest vintages, tuned on the middle, tested on the newest.
  Sizes 375k / 155k / 178k.
- **Shipped artifact.** Refit on all available data (708,368 loans, vintages 2007-06 to 2016-03)
  after the final evaluation, so the deployed model is not the exact object the numbers below
  describe; those describe the same configuration fit on train and validation only.
- **Leakage discipline.** Post-origination columns (payments, recoveries, last FICO) are excluded in
  SQL when the modelling table is built, so no feature encodes the outcome.

## Features

29 features: 22 numeric and 7 categorical. Borrower application data (loan amount, income, DTI, FICO,
delinquency and derogatory history, engineered ratios) plus Lending Club's verdict, `int_rate` and
`grade`. `int_rate` is the single dominant signal; the borrower fields on their own reproduce only
about 40% of it (`notebooks/21_underwriter_vs_lc`), so the model leans on pricing information the
application data does not fully carry.

## Performance

Historical held-out test set:

| metric   | test  |
|----------|:-----:|
| ROC AUC  | 0.710 |
| PR AUC   | 0.303 |
| Brier    | 0.121 |
| log-loss | 0.395 |

In currency, on realised test outcomes, three decision policies finish within a few percent of each
other: approving everything (124.9M), a single break-even threshold (129.9M), and per-loan expected
profit (126.5M). On this pre-screened book the approve-or-reject decision is worth only a few
percent, and a single threshold captures it. Per-loan pricing does slightly worse, because it trusts
probabilities that lean low on the newest vintage (see Calibration).

## Calibration

The model is moderately undercalibrated: mean predicted default is 13.1% versus 15.0% observed on
validation, and 13.4% versus 15.5% on test. Ranking remains useful, but probabilities that are too
low can bias expected-profit estimates and approval decisions. The exploratory isotonic correction
is not preferred here: it learns a flexible mapping inside older training vintages, while the
observed pattern is consistent with a shift in probability level, and it left validation Brier
unchanged at the reported precision (`reports/reliability_lgbm.png`,
`reports/reliability_test.png`).

A proper correction would reserve four chronological blocks: **train → tuning → calibration →
final test**. After tuning, an intercept fitted only on the calibration block would update the
level, `logit(p_cal) = a + logit(p_raw)`, without changing the ranking. Tuning and the
probability-based economic evaluation would then need to be rerun before reporting calibrated
results. The current artifact and metrics remain uncalibrated.

## Limitations

- **Selection bias.** The model only ever sees loans Lending Club accepted. It is not valid on the
  applicants it rejected; its estimates hold inside the accepted region, not outside it. Quantifying
  this boundary with the rejected file is planned but not yet done.
- **Calibration.** The model underpredicts average risk by about two percentage points on both
  temporal evaluation blocks. Without a separate calibration window, the PD and currency outputs
  should be treated as approximate rather than prospectively calibrated estimates.
- **Economic assumptions.** The pricing assumes no discounting (a euro at month 36 counts as a euro
  today), past recovery behaviour, and a break-even set on the training book. The figures hold only
  while pricing and recoveries behave as they did.
- **Scope.** 36-month loans only. A 60-month extension would need either a terminal-outcome cohort
  with an additional maturity buffer, or genuine event-history data for survival modelling. Either
  design would require its own chronological calibration block rather than reuse of the 36-month
  adjustment.

## When not to use it

- 60-month loans, or any term other than 36 months.
- Populations unlike Lending Club's accepted book (different geography, product, or era).
- As a fair-lending, adverse-action, or causal tool.
- Without recalibration once the observed default rate has moved away from the training level.

## Maintenance

- **Monitor** the realised default rate against the predicted, by vintage, and the input feature
  distributions for drift (the PSI and adversarial checks in `notebooks/22_validation` are the
  template).
- **Recalibrate** only after model selection, using a later calibration block and preserving a still
  later test block; refit the intercept when monitored calibration-in-the-large moves materially.
- **Rebuild** the artifact with `scripts/build_model.py` when new matured vintages are available, and
  re-run the final test before trusting new numbers.
