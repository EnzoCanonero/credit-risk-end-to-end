-- Reproduces the realised economics of mature 36-month loans by rate quartile.
--
-- The immutable v1 observation month is 2019-03. The issue-year predicate lets
-- Athena prune the 2017 and 2018 partitions before applying the exact 36-month
-- maturity condition.

WITH model_loans AS (
  SELECT
    id,
    loan_amnt,
    int_rate,
    total_rec_int,
    total_rec_prncp,
    recoveries,
    CASE
      WHEN loan_status = 'Charged Off' THEN 1
      WHEN loan_status = 'Fully Paid' THEN 0
    END AS target_bad
  FROM accepted_loans_v1
  WHERE source_snapshot = '2018Q4'
    AND issue_year <= '2016'
    AND term_months = 36
    AND issue_month IS NOT NULL
    AND loan_status IN ('Charged Off', 'Fully Paid')
    AND DATE_DIFF('month', issue_month, DATE '2019-03-01') >= 36
),

bands AS (
  SELECT
    *,
    NTILE(4) OVER (ORDER BY int_rate, id) AS rate_band
  FROM model_loans
)

SELECT
  rate_band,
  ROUND(MIN(int_rate), 1) AS rate_from,
  ROUND(MAX(int_rate), 1) AS rate_to,
  COUNT(*) FILTER (WHERE target_bad = 0) AS loans_repaid,
  COUNT(*) FILTER (WHERE target_bad = 1) AS loans_charged_off,
  ROUND(
    SUM(total_rec_int) FILTER (WHERE target_bad = 0)
    / SUM(loan_amnt) FILTER (WHERE target_bad = 0),
    3
  ) AS margin_earned,
  ROUND(
    1 - SUM(
      total_rec_prncp + recoveries + total_rec_int
    ) FILTER (WHERE target_bad = 1)
    / SUM(loan_amnt) FILTER (WHERE target_bad = 1),
    3
  ) AS principal_lost
FROM bands
GROUP BY rate_band
ORDER BY rate_band;
