--  How did Lending Club loan volume and risk change over time?

WITH grade_summary AS (
  SELECT
    grade,
    COUNT(*) AS loans,
    SUM(target_bad) AS bad_loans,
    AVG(target_bad) AS bad_rate,
    AVG(loan_amnt) AS avg_loan_amnt,
    AVG(annual_inc) AS avg_annual_inc
  FROM stg.loans_clean
  GROUP BY grade
)

SELECT
  grade,
  loans,
  bad_loans,

  ROUND(
    loans * 100 / SUM(loans) OVER (),
    2
  ) AS grade_share_pct,

  ROUND(
    bad_rate * 100 - ( SUM(bad_loans) OVER () * 100 ) / SUM(loans) OVER(),
    2
  ) AS bad_rate_vs_portfolio_pct,

  RANK() OVER(
    ORDER BY bad_rate DESC
  ) AS risk_rank

  FROM grade_summary
  ORDER BY grade;