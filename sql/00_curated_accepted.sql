-- Defines the typed, analysis-ready accepted-loan contract.

CREATE SCHEMA IF NOT EXISTS curated;

CREATE OR REPLACE VIEW curated.loans_accepted AS

WITH records AS (
  SELECT
    loans.*,
    TRY_CAST(NULLIF(TRIM(loans.id), '') AS BIGINT) AS loan_id
  FROM raw.loans_accepted AS loans
  -- Lending Club appends summary footer rows whose id contains prose. They are
  -- source-file metadata, not loan records, and cannot be partitioned by year.
  WHERE TRY_CAST(NULLIF(TRIM(loans.id), '') AS BIGINT) IS NOT NULL
),

typed AS (
  SELECT
    records.*,
    TRY_STRPTIME(NULLIF(TRIM(issue_d), ''), '%b-%Y')::DATE AS issue_month,
    TRY_CAST(
      REGEXP_EXTRACT(TRIM(term), '^([0-9]+) months$', 1)
      AS SMALLINT
    ) AS term_months,
    TRY_STRPTIME(
      NULLIF(TRIM(earliest_cr_line), ''),
      '%b-%Y'
    )::DATE AS earliest_credit_month,
    TRY_STRPTIME(
      NULLIF(TRIM(last_pymnt_d), ''),
      '%b-%Y'
    )::DATE AS last_payment_month,
    TRY_STRPTIME(
      NULLIF(TRIM(next_pymnt_d), ''),
      '%b-%Y'
    )::DATE AS next_payment_month,
    TRY_STRPTIME(
      NULLIF(TRIM(last_credit_pull_d), ''),
      '%b-%Y'
    )::DATE AS last_credit_pull_month,
    CAST('2018Q4' AS VARCHAR) AS source_snapshot
  FROM records
)

SELECT
  typed.*,
  EXTRACT(YEAR FROM issue_month)::SMALLINT AS issue_year
FROM typed;
