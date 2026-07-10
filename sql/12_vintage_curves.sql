-- For loans issued in each quarter, how quickly do bad outcomes accumulate as the loans age?

-- This query uses last_pymnt_d from the raw table to estimate when the loan outcome happened. 
-- That is fine for portfolio analysis, but it should not be used as a model input feature.

WITH loans AS (
  SELECT
    id,
    loan_amnt,
    date_trunc('quarter', try_strptime(issue_d, '%b-%Y')::DATE)::DATE AS vintage_quarter,
    try_strptime(issue_d, '%b-%Y')::DATE AS issue_month,
    try_strptime(last_pymnt_d, '%b-%Y')::DATE AS outcome_month,
    CASE
      WHEN loan_status = 'Charged Off' THEN 1
      WHEN loan_status = 'Fully Paid' THEN 0
    END AS target_bad
  FROM raw.loans_accepted
  WHERE loan_status IN ('Charged Off', 'Fully Paid')
    AND issue_d IS NOT NULL
    AND last_pymnt_d IS NOT NULL
),

loan_outcomes AS (
  SELECT
    *,
    date_diff('month', issue_month, outcome_month) AS months_to_outcome
  FROM loans
),

dataset_bounds AS (
  SELECT
    max(outcome_month) AS observation_month
  FROM loan_outcomes
),

mob_grid AS (
  SELECT months_on_book 
  FROM( VALUES
    (0),
    (6),
    (12),
    (18),
    (24),
    (36),
    (48),
    (60)
  ) AS t(months_on_book)
),

vintage_curve AS (
  SELECT
    l.vintage_quarter,
    g.months_on_book,
    COUNT(*) as loans_obs,
    SUM(
      CASE
        WHEN l.target_bad = 1
          AND l.months_to_outcome <= g.months_on_book
        THEN 1
        ELSE 0
      END
    ) AS cumul_bad_loans,
    SUM(l.loan_amnt) AS loan_amount_obs,
    SUM(
      CASE
        WHEN l.target_bad = 1
          AND l.months_to_outcome <= g.months_on_book
        THEN l.loan_amnt
        ELSE 0 
      END
    ) AS cumul_bad_amnt
  FROM loan_outcomes AS l
  CROSS JOIN mob_grid AS g
  CROSS JOIN dataset_bounds AS b
  WHERE date_diff('month', l.issue_month, b.observation_month) >= g.months_on_book
  GROUP BY
    l.vintage_quarter,
    g.months_on_book
),

curve_rates AS (
  SELECT
    vintage_quarter,
    months_on_book,
    loans_obs,
    loan_amount_obs,
    cumul_bad_loans,
    cumul_bad_amnt,
    ROUND(
      cumul_bad_loans * 100 / loans_obs
    ) AS cumul_bad_loans_pct,
    ROUND(
      cumul_bad_amnt * 100 / loan_amount_obs,
      2
    ) AS cumul_bad_amnt_pct
  FROM vintage_curve
)

SELECT
  vintage_quarter,
  months_on_book,
  cumul_bad_loans_pct,
  cumul_bad_amnt_pct,
  cumul_bad_loans_pct -
    LAG(cumul_bad_loans_pct) OVER(
      PARTITION BY vintage_quarter
      ORDER BY months_on_book ASC
    ) AS bad_rate_change,
  RANK() OVER(
    PARTITION BY months_on_book
    ORDER BY cumul_bad_loans_pct DESC
  ) AS risk_rank

FROM curve_rates
ORDER BY
  vintage_quarter DESC,
  months_on_book;



