-- What does a loan earn when it is repaid, and what does it cost when it defaults?

-- TODO — estimate both from realised outcomes, per interest-rate band.
--
--   For loans that were repaid (target_bad = 0), the margin earned:
--       total_rec_int / loan_amnt
--
--   For loans that charged off (target_bad = 1), the share of principal lost once everything
--   recovered is counted:
--       1 - (total_rec_prncp + recoveries + total_rec_int) / loan_amnt
--
--   Join stg.loans_clean to raw.loans_accepted on id: those payment columns live in raw and
--   never enter the modelling table. Band the rate with ntile(4) OVER (ORDER BY int_rate) and
--   report the two figures side by side, with the loan counts.
--
--   The two behave differently, and that is the whole point. Loss stays near 0.37 of loan_amnt
--   whatever the rate, while margin climbs with it. That is what makes the break-even
--   probability a property of each loan rather than one threshold for the portfolio.
--
--   These are post-origination columns. Calibrating business parameters with them is fine;
--   using them as model features would be leakage.

WITH bands AS (
  SELECT
    id,
    target_bad,
    int_rate,
    -- id breaks ties: int_rate has 523 distinct values over 708k loans, so a band boundary
    -- falls inside a group sharing the same rate, and without a tiebreaker which loans land on
    -- each side depends on the query plan rather than on the data.
    ntile(4) OVER(ORDER BY int_rate, id) AS rate_band
  FROM stg.loans_clean
)

SELECT
  b.rate_band,
  ROUND(MIN(b.int_rate), 1) AS rate_from,
  ROUND(MAX(b.int_rate), 1) AS rate_to,

  count(*) FILTER (WHERE b.target_bad = 0) AS loans_repaid,
  count(*) FILTER (WHERE b.target_bad = 1) AS loans_charged_off,

  -- Value weighted, not an average of per-loan ratios: portfolio profit follows the amounts.
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
JOIN raw.loans_accepted AS a ON a.id = b.id
GROUP BY b.rate_band
ORDER BY b.rate_band;


