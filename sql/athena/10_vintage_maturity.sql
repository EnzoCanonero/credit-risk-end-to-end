-- Shows why recent vintages and 60-month loans cannot use a naive binary label.

WITH classified AS (
  SELECT
    issue_year,
    term_months,
    last_payment_month,
    CASE
      WHEN loan_status IN (
        'Charged Off',
        'Does not meet the credit policy. Status:Charged Off'
      ) THEN 'bad'
      WHEN loan_status IN (
        'Fully Paid',
        'Does not meet the credit policy. Status:Fully Paid'
      ) THEN 'good'
      ELSE 'unresolved'
    END AS outcome_state
  FROM accepted_loans_v1
  WHERE source_snapshot = '2018Q4'
    AND term_months IN (36, 60)
),

vintage_term AS (
  SELECT
    issue_year,
    term_months,
    COUNT(*) AS total_loans,
    SUM(CASE WHEN outcome_state = 'bad' THEN 1 ELSE 0 END) AS bad_loans,
    SUM(CASE WHEN outcome_state = 'good' THEN 1 ELSE 0 END) AS good_loans,
    SUM(
      CASE WHEN outcome_state = 'unresolved' THEN 1 ELSE 0 END
    ) AS unresolved_loans,
    MAX(last_payment_month) AS latest_payment_month
  FROM classified
  GROUP BY issue_year, term_months
)

SELECT
  issue_year,
  term_months,
  total_loans,
  bad_loans,
  good_loans,
  unresolved_loans,
  latest_payment_month,
  ROUND(
    100.0 * unresolved_loans / NULLIF(total_loans, 0),
    2
  ) AS unresolved_pct,
  ROUND(
    100.0 * bad_loans / NULLIF(bad_loans + good_loans, 0),
    2
  ) AS resolved_bad_rate_pct
FROM vintage_term
ORDER BY issue_year, term_months;
