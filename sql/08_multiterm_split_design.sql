-- Derives chronological train, tuning, calibration, and backtest splits from
-- cumulative monthly origination volume across the pooled 36/60-month cohort.

WITH loans_by_month_and_term AS (
  SELECT
    issue_month,
    term_months,
    COUNT(*) AS loans,
    COUNT(*) FILTER (WHERE target_bad = 1) AS bad_loans
  FROM stg.loans_multiterm
  GROUP BY issue_month, term_months
),

loans_by_month AS (
  SELECT
    issue_month,
    SUM(loans) AS loans
  FROM loans_by_month_and_term
  GROUP BY issue_month
),

cumulative_volume AS (
  SELECT
    issue_month,
    SUM(loans) OVER (
      ORDER BY issue_month
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_loans,
    100.0 * SUM(loans) OVER (
      ORDER BY issue_month
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / SUM(loans) OVER () AS cumulative_pct
  FROM loans_by_month
),

split_bounds AS (
  SELECT
    MIN(issue_month) FILTER (WHERE cumulative_pct >= 50) AS tuning_start,
    MIN(issue_month) FILTER (WHERE cumulative_pct >= 65) AS calibration_start,
    MIN(issue_month) FILTER (WHERE cumulative_pct >= 80) AS backtest_start
  FROM cumulative_volume
),

split_loans AS (
  SELECT
    monthly.issue_month,
    monthly.term_months,
    monthly.loans,
    monthly.bad_loans,
    bounds.tuning_start,
    bounds.calibration_start,
    bounds.backtest_start,
    CASE
      WHEN monthly.issue_month < bounds.tuning_start THEN 'train'
      WHEN monthly.issue_month < bounds.calibration_start THEN 'tuning'
      WHEN monthly.issue_month < bounds.backtest_start THEN 'calibration'
      ELSE 'backtest'
    END AS split
  FROM loans_by_month_and_term AS monthly
  CROSS JOIN split_bounds AS bounds
)

SELECT
  split,
  term_months,
  tuning_start,
  calibration_start,
  backtest_start,
  SUM(loans) AS loans,
  SUM(bad_loans) AS bad_loans,
  ROUND(
    100.0 * SUM(bad_loans) / SUM(loans),
    2
  ) AS bad_rate,
  ROUND(
    100.0 * SUM(loans) / SUM(SUM(loans)) OVER (),
    2
  ) AS loans_pct
FROM split_loans
GROUP BY
  split,
  term_months,
  tuning_start,
  calibration_start,
  backtest_start
ORDER BY
  CASE split
    WHEN 'train' THEN 1
    WHEN 'tuning' THEN 2
    WHEN 'calibration' THEN 3
    WHEN 'backtest' THEN 4
  END,
  term_months;

