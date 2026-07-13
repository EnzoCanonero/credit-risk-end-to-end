-- How are originations distributed over time, and where do the train / validation / test cutoffs fall?

WITH by_quarter AS (
  SELECT
    date_trunc('quarter', issue_month)::DATE AS issue_quarter,
    COUNT(*) AS loans
  FROM stg.loans_clean
  GROUP BY issue_quarter
)

SELECT
  issue_quarter,
  loans,

  ROUND(
    100.0 * SUM(loans) OVER (ORDER BY issue_quarter) / SUM(loans) OVER (),
    2
  ) AS cumulative_pct,

  CASE
    WHEN issue_quarter < DATE '2015-04-01' THEN 'train'
    WHEN issue_quarter < DATE '2015-10-01' THEN 'validation'
    ELSE 'test'
  END AS split

FROM by_quarter
ORDER BY issue_quarter;


-- Resulting size of each split.

WITH labelled AS (
  SELECT
    issue_month,
    CASE
      WHEN issue_month < DATE '2015-04-01' THEN 'train'
      WHEN issue_month < DATE '2015-10-01' THEN 'validation'
      ELSE 'test'
    END AS split
  FROM stg.loans_clean
)

SELECT
  split,
  COUNT(*) AS loans,

  ROUND(
    100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
    2
  ) AS share_pct

FROM labelled
GROUP BY split
ORDER BY MIN(issue_month);
