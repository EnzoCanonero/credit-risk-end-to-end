-- How are originations distributed over time, and where do the train / validation / test cutoffs fall?

WITH by_month AS (
    SELECT
        issue_month,
        COUNT(*) AS loans
    FROM stg.loans_clean
    WHERE issue_month IS NOT NULL
    GROUP BY issue_month
),

cumulative AS (
    SELECT
        issue_month,
        loans,
        ROUND(
            100.0
            * SUM(loans) OVER (ORDER BY issue_month)
            / SUM(loans) OVER (),
            2
        ) AS cumulative_pct
    FROM by_month
),

split_bounds AS (
    SELECT
        MIN(issue_month)
            FILTER (WHERE cumulative_pct >= 55) AS val_start,
        MIN(issue_month)
            FILTER (WHERE cumulative_pct >= 75) AS test_start
    FROM cumulative
),

labelled AS (
    SELECT
        l.issue_month,
        s.val_start,
        s.test_start,
        CASE
            WHEN l.issue_month < s.val_start THEN 'train'
            WHEN l.issue_month < s.test_start THEN 'validation'
            ELSE 'test'
        END AS split
    FROM stg.loans_clean AS l
    CROSS JOIN split_bounds AS s
)

SELECT
    split,
    MIN(val_start) AS val_start,
    MIN(test_start) AS test_start,
    COUNT(*) AS loans,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS share_pct
FROM labelled
GROUP BY split
ORDER BY MIN(issue_month);