SHOW TABLES FROM stg;

-- Check row count
SELECT
  COUNT(*) AS total_rows
FROM stg.loans_clean;

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

-- Check missing values in the core columns
SELECT
  SUM(CASE WHEN id IS NULL THEN 1 ELSE 0 END) AS missing_id,
  SUM(CASE WHEN loan_amnt IS NULL THEN 1 ELSE 0 END) AS missing_loan_amnt,
  SUM(CASE WHEN term IS NULL THEN 1 ELSE 0 END) AS missing_term,
  SUM(CASE WHEN int_rate IS NULL THEN 1 ELSE 0 END) AS missing_int_rate,
  SUM(CASE WHEN grade IS NULL THEN 1 ELSE 0 END) AS missing_grade,
  SUM(CASE WHEN annual_inc IS NULL THEN 1 ELSE 0 END) AS missing_annual_inc,
  SUM(CASE WHEN issue_month IS NULL THEN 1 ELSE 0 END) AS missing_issue_month,
  SUM(CASE WHEN loan_status IS NULL THEN 1 ELSE 0 END) AS missing_loan_status,
  SUM(CASE WHEN target_bad IS NULL THEN 1 ELSE 0 END) AS missing_target_bad
FROM stg.loans_clean;

-- Check risk by grade
SELECT
  grade,
  COUNT(*) AS loans,
  AVG(target_bad) AS bad_rate
FROM stg.loans_clean
GROUP BY grade
ORDER BY grade;

-- Inspect a few rows manually
SELECT
  *
FROM stg.loans_clean
LIMIT 10;
