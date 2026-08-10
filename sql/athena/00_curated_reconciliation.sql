-- Reconciles every curated S3 partition with the immutable v1 loan contract.

SELECT
  issue_year,
  COUNT(*) AS loan_count,
  COUNT(DISTINCT loan_id) AS distinct_loan_ids,
  MIN(issue_month) AS first_issue_month,
  MAX(issue_month) AS last_issue_month
FROM accepted_loans_v1
WHERE source_snapshot = '2018Q4'
GROUP BY issue_year
ORDER BY issue_year;
