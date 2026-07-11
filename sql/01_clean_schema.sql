-- Lifetime default target on matured 36-month loans (status-based).
-- `months_observed >= 36` filters out still-open recent vintages, removing the maturity bias.

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
  id, loan_amnt, loan_status, term, int_rate, grade, annual_inc,
  issue_month, months_to_outcome, months_observed, target_bad
FROM derived
WHERE months_observed >= 36;
