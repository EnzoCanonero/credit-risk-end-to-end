CREATE SCHEMA IF NOT EXISTS stg;

CREATE OR REPLACE TABLE stg.loans_clean AS
SELECT
  id,
  loan_amnt,
  term,
  int_rate,
  grade,
  annual_inc,
  issue_d,
  loan_status,

  CASE
    WHEN loan_status = 'Charged Off' THEN 1
    WHEN loan_status = 'Fully Paid' THEN 0
  END AS target_bad

FROM raw.loans_accepted
WHERE loan_status IN ('Charged Off', 'Fully Paid');