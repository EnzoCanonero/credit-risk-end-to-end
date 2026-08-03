-- Builds the modelling table from matured 36-month loans.

CREATE SCHEMA IF NOT EXISTS stg;

CREATE OR REPLACE TABLE stg.loans_clean AS

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

    collections_12_mths_ex_med,
    tax_liens,
    delinq_amnt,
    acc_now_delinq,
    chargeoff_within_12_mths,

    mths_since_last_delinq,

    trim(home_ownership) AS home_ownership,
    trim(purpose) AS purpose,
    trim(addr_state) AS addr_state,
    trim(verification_status) AS verification_status,
    trim(application_type) AS application_type,
    trim(emp_length) AS emp_length,

    date_diff(
      'month',
      try_strptime(earliest_cr_line, '%b-%Y')::DATE,
      try_strptime(issue_d, '%b-%Y')::DATE
    ) AS credit_history_months,

    CASE WHEN annual_inc >= loan_amnt THEN loan_amnt / nullif(annual_inc, 0) END AS loan_to_income,
    CASE WHEN open_acc <= total_acc THEN open_acc / nullif(total_acc, 0) END AS active_acct_ratio,

    CASE
      WHEN loan_status = 'Charged Off' THEN 1
      WHEN loan_status = 'Fully Paid' THEN 0
    END AS target_bad

  FROM curated.loans_accepted
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

  int_rate, grade,

  annual_inc, dti, fico_range_low, inq_last_6mths, open_acc, pub_rec,
  revol_bal, revol_util, total_acc, delinq_2yrs, pub_rec_bankruptcies,
  credit_history_months, loan_to_income, active_acct_ratio,
  collections_12_mths_ex_med, tax_liens, delinq_amnt,
  acc_now_delinq, chargeoff_within_12_mths, mths_since_last_delinq,
  home_ownership, purpose, addr_state, verification_status,
  application_type, emp_length

FROM derived
WHERE months_observed >= 36;
