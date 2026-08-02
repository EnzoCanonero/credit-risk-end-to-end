-- Checks the quality of the modelling table.

SUMMARIZE stg.loans_clean;

SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT id) AS unique_ids,
  COUNT(*) - COUNT(DISTINCT id) AS duplicate_ids
FROM stg.loans_clean;

SELECT
  loan_status,
  target_bad,
  COUNT(*) AS loans
FROM stg.loans_clean
GROUP BY loan_status, target_bad
ORDER BY target_bad ASC;

SELECT
  COUNT(*) AS total_loans,
  SUM(target_bad) AS bad_loans,
  AVG(target_bad) AS bad_rate
FROM stg.loans_clean;

SELECT
  grade,
  COUNT(*) AS loans,
  AVG(target_bad) AS bad_rate
FROM stg.loans_clean
GROUP BY grade
ORDER BY grade;

SELECT
  COUNT(*) FILTER (WHERE months_observed < 36) AS immature_loans,
  COUNT(*) FILTER (WHERE target_bad IS NULL) AS unlabelled_loans,
  MAX(issue_month) AS last_vintage
FROM stg.loans_clean;

SELECT
  COUNT(*) FILTER (WHERE credit_history_months < 0) AS negative_history,
  MIN(credit_history_months) AS min_months,
  MEDIAN(credit_history_months) AS median_months,
  MAX(credit_history_months) AS max_months
FROM stg.loans_clean;
