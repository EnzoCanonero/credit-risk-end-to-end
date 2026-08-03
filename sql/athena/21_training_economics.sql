-- Reproduces the economic constants calibrated on the training vintages.

WITH train_outcomes AS (
  SELECT
    int_rate,
    loan_amnt,
    total_rec_int,
    total_rec_prncp,
    recoveries,
    CASE
      WHEN loan_status = 'Charged Off' THEN 1
      WHEN loan_status = 'Fully Paid' THEN 0
    END AS target_bad
  FROM accepted_loans_v1
  WHERE source_snapshot = '2018Q4'
    AND issue_year <= '2015'
    AND term_months = 36
    AND issue_month IS NOT NULL
    AND issue_month < DATE '2015-03-01'
    AND loan_status IN ('Charged Off', 'Fully Paid')
    AND DATE_DIFF('month', issue_month, DATE '2019-03-01') >= 36
)

SELECT
  ROUND(
    REGR_SLOPE(
      total_rec_int / loan_amnt,
      int_rate
    ) FILTER (WHERE target_bad = 0),
    4
  ) AS margin_per_rate_point,
  ROUND(
    REGR_INTERCEPT(
      total_rec_int / loan_amnt,
      int_rate
    ) FILTER (WHERE target_bad = 0),
    4
  ) AS margin_intercept,
  ROUND(
    1 - SUM(
      total_rec_prncp + recoveries + total_rec_int
    ) FILTER (WHERE target_bad = 1)
    / SUM(loan_amnt) FILTER (WHERE target_bad = 1),
    4
  ) AS loss_fraction
FROM train_outcomes;
