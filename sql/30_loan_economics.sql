-- Estimates repayment margins and default losses from past loans.

WITH bands AS (
  SELECT
    id,
    target_bad,
    int_rate,
    ntile(4) OVER(ORDER BY int_rate, id) AS rate_band
  FROM stg.loans_clean
)

SELECT
  b.rate_band,
  ROUND(MIN(b.int_rate), 1) AS rate_from,
  ROUND(MAX(b.int_rate), 1) AS rate_to,

  count(*) FILTER (WHERE b.target_bad = 0) AS loans_repaid,
  count(*) FILTER (WHERE b.target_bad = 1) AS loans_charged_off,

  ROUND(
    SUM(a.total_rec_int) FILTER (WHERE b.target_bad = 0)
    / SUM(a.loan_amnt) FILTER (WHERE b.target_bad = 0),
    3
  ) AS margin_earned,

  ROUND(
    1 - SUM(a.total_rec_prncp + a.recoveries + a.total_rec_int) FILTER (WHERE b.target_bad = 1)
      / SUM(a.loan_amnt) FILTER (WHERE b.target_bad = 1),
    3
  ) AS principal_lost

FROM bands AS b
JOIN curated.loans_accepted AS a ON a.id = b.id
GROUP BY b.rate_band
ORDER BY b.rate_band;


WITH train_outcomes AS (
  SELECT
    c.target_bad,
    c.int_rate,
    a.loan_amnt,
    a.total_rec_int,
    a.total_rec_prncp,
    a.recoveries
  FROM stg.loans_clean AS c
  JOIN curated.loans_accepted AS a ON a.id = c.id
  WHERE c.issue_month < DATE '2015-03-01'
)

SELECT
  ROUND(
    regr_slope(total_rec_int / loan_amnt, int_rate) FILTER (WHERE target_bad = 0),
    4
  ) AS margin_per_rate_point,

  ROUND(
    regr_intercept(total_rec_int / loan_amnt, int_rate) FILTER (WHERE target_bad = 0),
    4
  ) AS margin_intercept,

  ROUND(
    1 - SUM(total_rec_prncp + recoveries + total_rec_int) FILTER (WHERE target_bad = 1)
      / SUM(loan_amnt) FILTER (WHERE target_bad = 1),
    4
  ) AS loss_fraction

FROM train_outcomes;
