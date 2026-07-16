-- Data quality checks on the modelling table.

-- Null rate, range and cardinality for every column at once. Replaces the old
-- hand-written missing-value block, which needed editing on every new feature.
SUMMARIZE stg.loans_clean;

-- Check that each loan has a unique id
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT id) AS unique_ids,
  COUNT(*) - COUNT(DISTINCT id) AS duplicate_ids
FROM stg.loans_clean;

--  Check the target mapping
SELECT
  loan_status,
  target_bad,
  COUNT(*) AS loans
FROM stg.loans_clean
GROUP BY loan_status, target_bad
ORDER BY target_bad ASC;

-- Check overall bad-loan rate
SELECT
  COUNT(*) AS total_loans,
  SUM(target_bad) AS bad_loans,
  AVG(target_bad) AS bad_rate
FROM stg.loans_clean;

-- Check risk by grade
SELECT
  grade,
  COUNT(*) AS loans,
  AVG(target_bad) AS bad_rate
FROM stg.loans_clean
GROUP BY grade
ORDER BY grade;

-- The maturity filter must leave no immature vintage behind, and every loan must
-- be labelled. Both should return zero.
SELECT
  COUNT(*) FILTER (WHERE months_observed < 36) AS immature_loans,
  COUNT(*) FILTER (WHERE target_bad IS NULL) AS unlabelled_loans,
  MAX(issue_month) AS last_vintage
FROM stg.loans_clean;

-- credit_history_months is derived, so it deserves its own check: a negative value
-- would mean earliest_cr_line falls after issue_month, i.e. corrupt source dates.
SELECT
  COUNT(*) FILTER (WHERE credit_history_months < 0) AS negative_history,
  MIN(credit_history_months) AS min_months,
  MEDIAN(credit_history_months) AS median_months,
  MAX(credit_history_months) AS max_months
FROM stg.loans_clean;
