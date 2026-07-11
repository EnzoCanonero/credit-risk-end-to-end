-- Checks loans maturation timeframes.

WITH loans AS (
  SELECT
    id, loan_amnt, trim(term) AS term, int_rate, grade, annual_inc,
    loan_status,
    try_strptime(issue_d, '%b-%Y')::DATE AS issue_month,
    try_strptime(last_pymnt_d, '%b-%Y')::DATE AS outcome_month
  FROM raw.loans_accepted
  WHERE issue_d IS NOT NULL
),

dataset_bounds AS (
  SELECT
    max(outcome_month) AS observation_month
  FROM loans
),

derived AS (
  SELECT
    l.*,
    date_diff('month', l.issue_month, l.outcome_month) AS months_to_outcome,
    date_diff('month', l.issue_month, b.observation_month) AS months_observed
  FROM loans AS l
  CROSS JOIN dataset_bounds AS b
)

SELECT
  term,
  COUNT(*) AS total_defaults,

  ROUND(
    COUNT(*) FILTER(WHERE months_to_outcome <= 6) * 100 / COUNT(*),
    2
  ) AS pct_by_6,

  ROUND(
    COUNT(*) FILTER(WHERE months_to_outcome <= 12) * 100 / COUNT(*),
    2
  ) AS pct_by_12,

  ROUND(
    COUNT(*) FILTER(WHERE months_to_outcome <= 18) * 100 / COUNT(*),
    2
  ) AS pct_by_18,

  ROUND(
    COUNT(*) FILTER(WHERE months_to_outcome <= 24) * 100 / COUNT(*),
    2
  ) AS pct_by_24,

  ROUND(
    COUNT(*) FILTER(WHERE months_to_outcome <= 30) * 100 / COUNT(*),
    2
  ) AS pct_by_30,

  ROUND(
    COUNT(*) FILTER(WHERE months_to_outcome <= 36) * 100 / COUNT(*),
    2
  ) AS pct_by_36,

  ROUND(
    COUNT(*) FILTER(WHERE months_to_outcome <= 42) * 100 / COUNT(*),
    2
  ) AS pct_by_42,

  ROUND(
    COUNT(*) FILTER(WHERE months_to_outcome <= 48) * 100 / COUNT(*),
    2
  ) AS pct_by_48,

  ROUND(
    COUNT(*) FILTER(WHERE months_to_outcome <= 54) * 100 / COUNT(*),
    2
  ) AS pct_by_54

FROM derived 
WHERE months_observed  >= 60
  AND loan_status = 'Charged Off'
  AND months_to_outcome IS NOT NULL
GROUP BY term;
