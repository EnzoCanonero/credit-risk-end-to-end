-- Lifetime default target on matured 36-month loans (status-based).
-- `months_observed >= 36` filters out still-open recent vintages, removing the maturity bias.

CREATE SCHEMA IF NOT EXISTS stg;

CREATE OR REPLACE TABLE stg.loans_clean AS

-- Every column here is known at origination. int_rate and grade are Lending Club's own
-- risk verdict: honest data, but the underwriter model excludes them via the feature list.
-- Post-origination columns (total_pymnt, recoveries, last_fico_*, ...) never enter this table.

WITH loans AS(
  SELECT
    id,
    loan_amnt,
    trim(term) AS term,
    int_rate,
    grade,
    annual_inc,
    loan_status,
    try_strptime(issue_d, '%b-%Y')::DATE AS issue_month,
    try_strptime(last_pymnt_d, '%b-%Y')::DATE AS outcome_month,

    -- Borrower credit profile at application. Columns added to Lending Club's form
    -- after 2015 (il_util, all_util, open_acc_6m, inq_last_12m) are 100% null over the
    -- training vintages, so they are left out.
    -- 999 is a sentinel and negatives are impossible; >100 means debt payments above income,
    -- implausible for an approved loan. Out-of-range dti becomes NULL for the imputer.
    CASE WHEN dti BETWEEN 0 AND 100 THEN dti END AS dti,
    fico_range_low,
    inq_last_6mths,
    open_acc,
    pub_rec,
    revol_bal,
    revol_util,
    total_acc,
    delinq_2yrs,
    pub_rec_bankruptcies,

    -- Past derogatory events from the bureau: collections, liens, delinquencies.
    -- Mostly zero, but monotone in default rate and Lending Club seems to underweight them.
    collections_12_mths_ex_med,
    tax_liens,
    delinq_amnt,
    acc_now_delinq,
    chargeoff_within_12_mths,

    -- Recency of last delinquency. NULL means never delinquent: good news, not missing data.
    -- The imputer's missing-indicator keeps that apart from a genuine imputed value.
    mths_since_last_delinq,

    trim(home_ownership) AS home_ownership,
    trim(purpose) AS purpose,
    trim(addr_state) AS addr_state,
    trim(verification_status) AS verification_status,
    trim(application_type) AS application_type,
    trim(emp_length) AS emp_length,

    -- Measured against issue_month, not today: history length is a fact as of origination.
    date_diff(
      'month',
      try_strptime(earliest_cr_line, '%b-%Y')::DATE,
      try_strptime(issue_d, '%b-%Y')::DATE
    ) AS credit_history_months,

    -- Engineered ratios: interactions the linear model cannot find on its own.
    -- Both climb monotonically with default. The guards enforce each ratio's invariant and
    -- drop corrupt source rows: you cannot borrow more than a year's income unsecured, and you
    -- cannot have more open accounts than total accounts. Violations become NULL for the imputer.
    CASE WHEN annual_inc >= loan_amnt THEN loan_amnt / nullif(annual_inc, 0) END AS loan_to_income,
    CASE WHEN open_acc <= total_acc THEN open_acc / nullif(total_acc, 0) END AS active_acct_ratio,

    CASE
      WHEN loan_status = 'Charged Off' THEN 1
      WHEN loan_status = 'Fully Paid' THEN 0
    END AS target_bad

  FROM raw.loans_accepted
  WHERE loan_status IN ('Charged Off', 'Fully Paid')
    AND trim(term) = '36 months'
    AND issue_d IS NOT NULL
),

dataset_bounds AS (
  SELECT
    max(outcome_month) AS observation_month
  FROM loans
),

derived AS (
  SELECT
    l.*,
    date_diff('month', l.issue_month, l.outcome_month) AS months_to_outcome,
    date_diff('month', l.issue_month, b.observation_month) AS months_observed
  FROM loans AS l
  CROSS JOIN dataset_bounds AS b
)

SELECT
  id, loan_amnt, loan_status, term, issue_month,
  months_to_outcome, months_observed, target_bad,

  -- Lending Club's own risk verdict. Benchmark only: the underwriter feature list drops these.
  int_rate, grade,

  -- Known at origination.
  annual_inc, dti, fico_range_low, inq_last_6mths, open_acc, pub_rec,
  revol_bal, revol_util, total_acc, delinq_2yrs, pub_rec_bankruptcies,
  credit_history_months, loan_to_income, active_acct_ratio,
  collections_12_mths_ex_med, tax_liens, delinq_amnt,
  acc_now_delinq, chargeoff_within_12_mths, mths_since_last_delinq,
  home_ownership, purpose, addr_state, verification_status,
  application_type, emp_length

FROM derived
WHERE months_observed >= 36;
