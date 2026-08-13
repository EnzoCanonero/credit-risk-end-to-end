-- Checks the quality of the multi-term modelling cohort.

SUMMARIZE stg.loans_multiterm;

-- Cohort reconciliation
WITH population_counts AS (
  SELECT
    term_months,
    loan_status,
    COUNT(*) AS loans
  FROM stg.loans_multiterm_population
  GROUP BY term_months, loan_status
),

retained_counts AS (
  SELECT
    term_months,
    loan_status,
    COUNT(*) AS loans
  FROM stg.loans_multiterm
  GROUP BY term_months, loan_status
)

SELECT
  population.term_months,
  population.loan_status,
  population.loans AS population_loans,
  COALESCE(retained.loans, 0) AS retained_loans,
  population.loans - COALESCE(retained.loans, 0) AS excluded_loans
FROM population_counts AS population
LEFT JOIN retained_counts AS retained
  ON population.term_months = retained.term_months
  AND population.loan_status = retained.loan_status
ORDER BY population.term_months, population.loan_status;

WITH population_totals AS (
  SELECT
    COUNT(*) AS population_loans,
    COUNT(*) FILTER (WHERE target_bad IS NULL) AS excluded_loans
  FROM stg.loans_multiterm_population
),

retained_totals AS (
  SELECT COUNT(*) AS retained_loans
  FROM stg.loans_multiterm
)

SELECT
  population.population_loans,
  retained.retained_loans,
  population.excluded_loans,
  population.population_loans =
    population.excluded_loans + retained.retained_loans AS cohort_reconciles
FROM population_totals AS population
CROSS JOIN retained_totals AS retained;

-- ID integrity
WITH population_ids AS (
  SELECT
    COUNT(*) AS loans,
    COUNT(*) FILTER (WHERE loan_id IS NULL) AS null_ids,
    COUNT(*) - COUNT(*) FILTER (WHERE loan_id IS NULL) AS non_null_ids,
    COUNT(DISTINCT loan_id) AS distinct_ids,
    COUNT(*) FILTER (WHERE loan_id IS NOT NULL)
      - COUNT(DISTINCT loan_id) AS duplicate_rows
  FROM stg.loans_multiterm_population
),

retained_ids AS (
  SELECT
    COUNT(*) AS loans,
    COUNT(*) FILTER (WHERE loan_id IS NULL) AS null_ids,
    COUNT(*) - COUNT(*) FILTER (WHERE loan_id IS NULL) AS non_null_ids,
    COUNT(DISTINCT loan_id) AS distinct_ids,
    COUNT(*) FILTER (WHERE loan_id IS NOT NULL)
      - COUNT(DISTINCT loan_id) AS duplicate_rows
  FROM stg.loans_multiterm
)

SELECT
  'population' AS dataset,
  loans,
  null_ids,
  non_null_ids,
  distinct_ids,
  duplicate_rows
FROM population_ids

UNION ALL

SELECT
  'retained' AS dataset,
  loans,
  null_ids,
  non_null_ids,
  distinct_ids,
  duplicate_rows
FROM retained_ids;

SELECT
  COUNT(*) AS orphan_loans
FROM stg.loans_multiterm AS retained
WHERE retained.loan_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM stg.loans_multiterm_population AS population
    WHERE population.loan_id = retained.loan_id
  );

-- Temporal integrity
SELECT
  COUNT(*) AS unexpected_observation_months
FROM stg.loans_multiterm_population
WHERE observation_month IS NOT NULL
  AND observation_month <> DATE '2019-03-01';

SELECT
  COUNT(*) AS invalid_terms
FROM stg.loans_multiterm_population
WHERE term_months IS NOT NULL
  AND term_months NOT IN (36, 60);

SELECT
  COUNT(*) AS inconsistent_required_followup
FROM stg.loans_multiterm_population
WHERE required_followup_months IS NOT NULL
  AND term_months IS NOT NULL
  AND required_followup_months <> term_months + 6;

SELECT
  COUNT(*) AS insufficient_followup_loans
FROM stg.loans_multiterm_population
WHERE observation_month IS NOT NULL
  AND issue_month IS NOT NULL
  AND term_months IS NOT NULL
  AND DATE_DIFF('month', issue_month, observation_month) < term_months + 6;

SELECT
  COUNT(*) AS inconsistent_months_observed
FROM stg.loans_multiterm_population
WHERE issue_month IS NOT NULL
  AND observation_month IS NOT NULL
  AND months_observed IS NOT NULL
  AND DATE_DIFF('month', issue_month, observation_month) <> months_observed;

SELECT
  COUNT(*) AS post_cutoff_loans
FROM stg.loans_multiterm_population
WHERE issue_month IS NOT NULL
  AND issue_month >= DATE '2013-10-01';

SELECT
  COUNT(*) FILTER (WHERE issue_month IS NULL) AS null_issue_months,
  COUNT(*) FILTER (
    WHERE observation_month IS NULL
  ) AS null_observation_months,
  COUNT(*) FILTER (WHERE term_months IS NULL) AS null_term_months,
  COUNT(*) FILTER (
    WHERE required_followup_months IS NULL
  ) AS null_required_followup_months,
  COUNT(*) FILTER (
    WHERE months_observed IS NULL
  ) AS null_months_observed,
  COUNT(*) FILTER (
    WHERE issue_month IS NULL
      OR observation_month IS NULL
      OR term_months IS NULL
      OR required_followup_months IS NULL
      OR months_observed IS NULL
  ) AS loans_with_null_temporal_fields
FROM stg.loans_multiterm_population;

-- Temporal summary by term
SELECT
  term_months,
  COUNT(*) AS loans,
  MIN(issue_month) AS earliest_issue_month,
  MAX(issue_month) AS latest_issue_month,
  MIN(months_observed) AS min_months_observed,
  MIN(months_observed - term_months) AS min_maturity_buffer
FROM stg.loans_multiterm_population
GROUP BY term_months
ORDER BY term_months;

-- Target integrity
SELECT
  COUNT(*) FILTER (
    WHERE loan_status = 'Charged Off'
      AND target_bad IS DISTINCT FROM 1
  ) AS charged_off_target_mismatches,
  COUNT(*) FILTER (
    WHERE loan_status = 'Fully Paid'
      AND target_bad IS DISTINCT FROM 0
  ) AS fully_paid_target_mismatches,
  COUNT(*) FILTER (
    WHERE (
      loan_status IS NULL
      OR loan_status NOT IN ('Charged Off', 'Fully Paid')
    )
      AND target_bad IS NOT NULL
  ) AS nonstandard_status_with_target
FROM stg.loans_multiterm_population;

SELECT
  COUNT(*) FILTER (
    WHERE loan_status IS NULL
      OR loan_status NOT IN ('Charged Off', 'Fully Paid')
  ) AS invalid_statuses,
  COUNT(*) FILTER (WHERE target_bad IS NULL) AS null_targets,
  COUNT(*) FILTER (
    WHERE target_bad NOT IN (0, 1)
  ) AS nonbinary_targets,
  COUNT(*) FILTER (
    WHERE loan_status = 'Charged Off'
      AND target_bad IS DISTINCT FROM 1
  ) AS charged_off_target_mismatches,
  COUNT(*) FILTER (
    WHERE loan_status = 'Fully Paid'
      AND target_bad IS DISTINCT FROM 0
  ) AS fully_paid_target_mismatches
FROM stg.loans_multiterm;

-- Feature validity
SELECT
  COUNT(*) FILTER (
    WHERE (
      dti < 0
      OR dti > 100
    )
      AND dti IS NOT NULL
  ) AS invalid_dti,
  COUNT(*) FILTER (
    WHERE (
      loan_to_income < 0
      OR loan_to_income > 1
    )
      AND loan_to_income IS NOT NULL
  ) AS invalid_loan_to_income,
  COUNT(*) FILTER (
    WHERE (
      active_acct_ratio < 0
      OR active_acct_ratio > 1
    )
      AND active_acct_ratio IS NOT NULL
  ) AS invalid_active_acct_ratio,
  COUNT(*) FILTER (
    WHERE credit_history_months < 0
      AND credit_history_months IS NOT NULL
  ) AS invalid_credit_history_months
FROM stg.loans_multiterm_population;
