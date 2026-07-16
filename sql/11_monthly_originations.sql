-- How did Lending Club loan volume and bad-loan rate change over time, and did
-- underwriting standards drift along with them?

WITH month_summary AS (
  SELECT
    issue_month,
    COUNT(*) AS loans,
    SUM(loan_amnt) AS month_amnt,
    AVG(target_bad) AS bad_rate,
    AVG(fico_range_low) AS avg_fico,
    AVG(dti) AS avg_dti
  FROM stg.loans_clean
  GROUP BY issue_month
)

SELECT
  issue_month,
  loans,
  month_amnt,
  bad_rate,

  ROUND( 
    loans * 100 / SUM(loans) OVER (),
    2
   ) AS month_share_pct,

  ROUND(
    AVG(loans) OVER(
      ORDER BY issue_month
      ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
      ),
      2
    ) AS loans_3_month_avg,
   
  ROUND(
    AVG(bad_rate) OVER(
      ORDER BY issue_month
      ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) * 100,
    2
  ) AS bad_rate_3_month_avg,

  -- Borrower quality over time. If bad rate rises while FICO falls or DTI climbs,
  -- the rising risk is a lending-standards story, not bad luck.
  ROUND(avg_fico, 0) AS avg_fico,
  ROUND(avg_dti, 2) AS avg_dti

  FROM month_summary
  ORDER BY issue_month;