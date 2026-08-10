# Checks the shared Athena SQL and the small cross-engine helpers.

import duckdb

from scripts import run_athena_analysis as athena


def test_shared_sql_keeps_the_credit_risk_cohort_rules() -> None:
    with duckdb.connect() as con:
        con.execute(
            """
            CREATE TABLE accepted_loans_v1 (
              id VARCHAR,
              loan_id BIGINT,
              source_snapshot VARCHAR,
              issue_year VARCHAR,
              issue_month DATE,
              term_months SMALLINT,
              last_payment_month DATE,
              loan_status VARCHAR,
              loan_amnt DOUBLE,
              int_rate DOUBLE,
              total_rec_int DOUBLE,
              total_rec_prncp DOUBLE,
              recoveries DOUBLE
            )
            """
        )
        con.execute(
            """
            INSERT INTO accepted_loans_v1 VALUES
              ('a', 1, '2018Q4', '2014', DATE '2014-01-01', 36,
               DATE '2017-01-01', 'Fully Paid', 100, 10, 10, 100, 0),
              ('b', 2, '2018Q4', '2014', DATE '2014-01-01', 36,
               DATE '2015-01-01', 'Charged Off', 100, 15, 5, 35, 10),
              ('c', 3, '2018Q4', '2015', DATE '2015-02-01', 36,
               DATE '2018-02-01', 'Fully Paid', 100, 20, 20, 100, 0),
              ('d', 4, '2018Q4', '2015', DATE '2015-03-01', 36,
               DATE '2018-03-01', 'Fully Paid', 100, 30, 90, 100, 0),
              ('e', 5, '2018Q4', '2016', DATE '2016-03-01', 36,
               DATE '2019-03-01', 'Fully Paid', 100, 25, 25, 100, 0),
              ('f', 6, '2018Q4', '2016', DATE '2016-04-01', 36,
               DATE '2019-03-01', 'Fully Paid', 100, 5, 5, 100, 0),
              ('g', 7, '2018Q4', '2018', DATE '2018-01-01', 60,
               DATE '2019-03-01', 'Current', 100, 12, 2, 10, 0)
            """
        )

        results = {}
        for query_name in athena.QUERY_FILES:
            sql = (athena.QUERY_DIR / query_name).read_text()
            results[query_name] = con.execute(sql).fetchall()

    reconciliation = results["00_curated_reconciliation.sql"]
    assert sum(row[1] for row in reconciliation) == 7

    maturity = results["10_vintage_maturity.sql"]
    recent_60_month = next(
        row for row in maturity if row[0] == "2018" and row[1] == 60
    )
    assert recent_60_month[2:6] == (1, 0, 0, 1)

    rate_bands = results["20_rate_band_economics.sql"]
    assert sum(row[3] + row[4] for row in rate_bands) == 5

    training_constants = results["21_training_economics.sql"]
    assert training_constants == [(0.01, 0.0, 0.5)]
