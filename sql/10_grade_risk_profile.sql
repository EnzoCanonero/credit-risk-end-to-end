--  What does a Lending Club grade actually encode about the borrower?

WITH grade_summary AS (
  SELECT
    grade,
    COUNT(*) AS loans,
    SUM(target_bad) AS bad_loans,
    AVG(target_bad) AS bad_rate,
    AVG(int_rate) AS avg_int_rate,
    AVG(loan_amnt) AS avg_loan_amnt,
    AVG(annual_inc) AS avg_annual_inc,
    AVG(fico_range_low) AS avg_fico,
    AVG(dti) AS avg_dti,
    AVG(credit_history_months) AS avg_credit_history_months
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

  ROUND(avg_int_rate, 2) AS avg_int_rate,

  -- The borrower profile behind the grade: this is what Lending Club priced on.
  ROUND(avg_fico, 0) AS avg_fico,
  ROUND(avg_dti, 2) AS avg_dti,
  ROUND(avg_credit_history_months, 0) AS avg_credit_history_months,
  ROUND(avg_annual_inc, 0) AS avg_annual_inc,

  RANK() OVER(
    ORDER BY bad_rate DESC
  ) AS risk_rank

  FROM grade_summary
  ORDER BY grade;
