-- Feature EDA for the underwriter model: distributions, outliers, and how each
-- feature relates to default. Justifies the preprocessing choices downstream.

-- Tail percentiles expose skew and outliers that may need robust preprocessing.
WITH feature_stats AS(
  SELECT
    feature,
    min(value) AS min_value,
    quantile_cont(value, 0.5) AS median_value,
    quantile_cont(value, 0.9) AS p90_value,
    quantile_cont(value, 0.99) AS p99_value,
    quantile_cont(value, 0.999) AS p999_value,
    max(value) AS max_value
  FROM stg.loans_clean
  UNPIVOT INCLUDE NULLS (
    value FOR feature IN(
      annual_inc,
      dti,
      revol_bal,
      revol_util,
      loan_to_income,
      active_acct_ratio
    )
  )
  GROUP BY feature
)

SELECT *
FROM feature_stats;


-- Default rate by 20-point FICO band: the clearest view of credit-quality monotonicity.
WITH fico_bands AS (
  SELECT
    floor(fico_range_low / 20)::INTEGER * 20 AS fico_band_low,
    target_bad
  FROM stg.loans_clean
  WHERE fico_range_low IS NOT NULL
)

SELECT
  fico_band_low || '-' || (fico_band_low + 19) AS fico_band,
  COUNT(*) AS loans,
  ROUND(AVG(target_bad),2) AS bad_rate
FROM fico_bands
GROUP BY fico_band_low
ORDER BY fico_band_low;


-- Default rate by 10-point DTI band: checks whether leverage risk rises monotonically.
WITH dti_bands AS(
  SELECT
   floor(dti / 10)::INTEGER * 10 AS dti_band_low,
   target_bad
  FROM stg.loans_clean
  WHERE dti IS NOT NULL
)

SELECT
  dti_band_low,
  dti_band_low || '-' || (dti_band_low + 9) AS dti_band,
  COUNT(*) AS loans,
  ROUND(AVG(target_bad), 2) AS bad_rate
FROM dti_bands
GROUP BY dti_band_low, dti_band
ORDER BY dti_band_low;
  

-- Purpose-level bad rate and portfolio share: risk matters only alongside exposure.
SELECT
  purpose,
  COUNT(*) AS loans,
  ROUND(AVG(target_bad), 2) AS bad_rate,
  ROUND(
    100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
    2
  ) AS share_pct
FROM stg.loans_clean
GROUP BY purpose
ORDER BY bad_rate DESC;


-- Engineered ratio: does the amount borrowed relative to income separate default?
WITH lti_bands AS (
  SELECT
    CASE
      WHEN loan_to_income < 0.1 THEN '1: <0.1'
      WHEN loan_to_income < 0.2 THEN '2: <0.2'
      WHEN loan_to_income < 0.3 THEN '3: <0.3'
      WHEN loan_to_income < 0.5 THEN '4: <0.5'
      ELSE '5: 0.5+'
    END AS lti_band,
    target_bad
  FROM stg.loans_clean
  WHERE loan_to_income IS NOT NULL
)

SELECT
  lti_band,
  COUNT(*) AS loans,
  ROUND(AVG(target_bad), 2) AS bad_rate
FROM lti_bands
GROUP BY lti_band
ORDER BY lti_band;


-- Engineered ratio: share of credit lines currently open, out of the borrower's history.
WITH active_bands AS (
  SELECT
    CASE
      WHEN active_acct_ratio < 0.3 THEN '1: <0.3'
      WHEN active_acct_ratio < 0.5 THEN '2: <0.5'
      WHEN active_acct_ratio < 0.7 THEN '3: <0.7'
      ELSE '4: 0.7+'
    END AS active_band,
    target_bad
  FROM stg.loans_clean
  WHERE active_acct_ratio IS NOT NULL
)

SELECT
  active_band,
  COUNT(*) AS loans,
  ROUND(AVG(target_bad), 2) AS bad_rate
FROM active_bands
GROUP BY active_band
ORDER BY active_band;


-- Derogatory events are mostly zero. The question is whether any occurrence lifts default,
-- and by how much. bad_rate_none vs bad_rate_event is the marginal signal each one carries.
WITH events AS (
  SELECT target_bad, event, value > 0 AS has_event
  FROM stg.loans_clean
  UNPIVOT (
    value FOR event IN (
      collections_12_mths_ex_med,
      tax_liens,
      delinq_amnt,
      acc_now_delinq,
      chargeoff_within_12_mths
    )
  )
)

SELECT
  event,
  COUNT(*) FILTER (WHERE has_event) AS loans_with_event,
  ROUND(AVG(target_bad) FILTER (WHERE NOT has_event), 3) AS bad_rate_none,
  ROUND(AVG(target_bad) FILTER (WHERE has_event), 3) AS bad_rate_event
FROM events
GROUP BY event
ORDER BY bad_rate_event DESC;


-- mths_since_last_delinq is NULL when the borrower has never been delinquent. That "never"
-- is information, not a gap: check whether it separates default before deciding how to impute.
SELECT
  CASE
    WHEN mths_since_last_delinq IS NULL THEN 'never delinquent'
    ELSE 'had a delinquency'
  END AS delinquency_history,
  COUNT(*) AS loans,
  ROUND(AVG(target_bad), 2) AS bad_rate
FROM stg.loans_clean
GROUP BY delinquency_history
ORDER BY bad_rate;


-- FICO-to-price correlation first, then each numeric feature's linear link to default.
WITH correlations AS (
  SELECT
    corr(fico_range_low, int_rate) AS fico_vs_int_rate,
    corr(loan_amnt, target_bad) AS loan_amnt,
    corr(annual_inc, target_bad) AS annual_inc,
    corr(dti, target_bad) AS dti,
    corr(fico_range_low, target_bad) AS fico_range_low,
    corr(inq_last_6mths, target_bad) AS inq_last_6mths,
    corr(open_acc, target_bad) AS open_acc,
    corr(pub_rec, target_bad) AS pub_rec,
    corr(revol_bal, target_bad) AS revol_bal,
    corr(revol_util, target_bad) AS revol_util,
    corr(total_acc, target_bad) AS total_acc,
    corr(delinq_2yrs, target_bad) AS delinq_2yrs,
    corr(pub_rec_bankruptcies, target_bad) AS pub_rec_bankruptcies,
    corr(credit_history_months, target_bad) AS credit_history_months
  FROM stg.loans_clean
),

correlations_vertical AS (
  UNPIVOT correlations
  ON COLUMNS(*)
  INTO
    NAME correlation_pair
    VALUE correlation
)

SELECT
  correlation_pair,
  ROUND(correlation, 2) AS correlation
FROM correlations_vertical
ORDER BY abs(correlation);
