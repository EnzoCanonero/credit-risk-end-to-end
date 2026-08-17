-- Defines the typed, analysis-ready rejected-loan contract.

CREATE SCHEMA IF NOT EXISTS curated;

CREATE OR REPLACE VIEW curated.loans_rejected AS

WITH records AS (
  SELECT
    loans.*,
    TRY_CAST(loans."Application Date" AS DATE) AS application_date,
    DATE_TRUNC(
      'month',
      TRY_CAST(loans."Application Date" AS DATE)
    )::DATE AS application_month,
    TRY_CAST(loans."Amount Requested" AS DOUBLE) AS amount_requested,
    NULLIF(TRIM(loans."Loan Title"), '') AS loan_title,
    loans."Risk_Score" AS risk_score_raw,
    loans."Debt-To-Income Ratio" AS dti_raw,
    NULLIF(TRIM(loans."Zip Code"), '') AS zip_code,
    NULLIF(TRIM(loans."State"), '') AS addr_state,
    NULLIF(TRIM(loans."Employment Length"), '') AS emp_length,
    loans."Policy Code" AS policy_code,
    CAST('2018Q4' AS VARCHAR) AS source_snapshot
  FROM raw.loans_rejected AS loans
),

parsed AS (
  SELECT
    records.*,
    NULLIF(TRIM(dti_raw), '') AS dti_text,
    TRY_CAST(
      REGEXP_REPLACE(NULLIF(TRIM(dti_raw), ''), '%$', '')
      AS DOUBLE
    ) AS dti_candidate
  FROM records
),

classified AS (
  SELECT
    parsed.*,
    dti_candidate IS NOT NULL
      AND ISFINITE(dti_candidate)
      AND dti_candidate BETWEEN 0 AND 100 AS dti_valid
  FROM parsed
)

SELECT
  classified.* EXCLUDE (dti_text, dti_candidate, dti_valid),
  CASE
    WHEN dti_valid THEN dti_candidate
  END AS dti,
  dti_text IS NULL AS dti_missing,
  dti_text IS NOT NULL AND NOT dti_valid AS dti_invalid
FROM classified;
