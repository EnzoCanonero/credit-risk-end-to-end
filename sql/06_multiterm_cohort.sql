-- Builds the mature, common-calendar 36/60-month modelling cohort.

CREATE SCHEMA IF NOT EXISTS stg;

CREATE OR REPLACE TABLE stg.loans_multiterm_population AS

WITH prepared AS (
  SELECT
    loan_id,
    loan_amnt,
    TRIM(loan_status) AS loan_status,
    term_months,
    issue_month,

    DATE '2019-03-01' AS observation_month,
    term_months + 6 AS required_followup_months,
    DATE_DIFF(
      'month',
      issue_month,
      DATE '2019-03-01'
    ) AS months_observed,

    int_rate,
    TRIM(grade) AS grade,

    annual_inc,
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

    TRIM(home_ownership) AS home_ownership,
    TRIM(purpose) AS purpose,
    TRIM(addr_state) AS addr_state,
    TRIM(verification_status) AS verification_status,
    TRIM(application_type) AS application_type,
    TRIM(emp_length) AS emp_length,

    DATE_DIFF(
      'month',
      earliest_credit_month,
      issue_month
    ) AS credit_history_months,

    CASE
      WHEN annual_inc >= loan_amnt
      THEN loan_amnt / NULLIF(annual_inc, 0)
    END AS loan_to_income,

    CASE
      WHEN open_acc <= total_acc
      THEN open_acc / NULLIF(total_acc, 0)
    END AS active_acct_ratio,

    CASE
      WHEN TRIM(loan_status) = 'Charged Off' THEN 1
      WHEN TRIM(loan_status) = 'Fully Paid' THEN 0
    END AS target_bad

  FROM curated.loans_accepted
  WHERE issue_month IS NOT NULL
    AND term_months IN (36, 60)
    AND issue_month < DATE '2013-10-01'
)

SELECT *
FROM prepared
WHERE months_observed >= required_followup_months;


CREATE OR REPLACE TABLE stg.loans_multiterm AS

SELECT *
FROM stg.loans_multiterm_population
WHERE target_bad IS NOT NULL;