-- Loan-status mix by vintage: shows that recent loans are still largely "Current" (not yet observable)

WITH base AS (
  SELECT
    date_trunc('quarter', try_strptime(issue_d, '%b-%Y')::DATE)::DATE AS vintage_quarter,
    loan_status
  FROM raw.loans_accepted
  WHERE issue_d IS NOT NULL
)

SELECT
  vintage_quarter,
  COUNT(*) AS total_loans,
  ROUND(
    SUM(
      CASE
        WHEN loan_status = 'Charged Off' THEN 1
        WHEN loan_status = 'Fully Paid' THEN 0
      END
    ) * 100 / COUNT(*) FILTER(
      WHERE loan_status IN ('Charged Off', 'Fully Paid')
    ),
    2
  ) AS bad_loans_pct,
  ROUND(
    SUM(
      CASE
        WHEN loan_status = 'Current' THEN 1
        ELSE 0
      END
    ) * 100 / COUNT(*),
    2
  ) AS current_pct
FROM base
WHERE loan_status IS NOT NULL
GROUP BY vintage_quarter
ORDER BY vintage_quarter;