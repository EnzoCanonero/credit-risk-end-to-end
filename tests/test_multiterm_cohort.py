# Checks the mature, common-calendar 36/60-month cohort contract.

from datetime import date
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
MULTITERM_SQL = REPO_ROOT / "sql" / "06_multiterm_cohort.sql"


def build_fixture(db_path: Path) -> None:
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE SCHEMA curated;
            CREATE TABLE curated.loans_accepted (
              loan_id BIGINT,
              loan_amnt DOUBLE,
              loan_status VARCHAR,
              term_months SMALLINT,
              issue_month DATE,
              int_rate DOUBLE,
              grade VARCHAR,
              annual_inc DOUBLE,
              dti DOUBLE,
              fico_range_low DOUBLE,
              inq_last_6mths DOUBLE,
              open_acc DOUBLE,
              pub_rec DOUBLE,
              revol_bal DOUBLE,
              revol_util DOUBLE,
              total_acc DOUBLE,
              delinq_2yrs DOUBLE,
              pub_rec_bankruptcies DOUBLE,
              collections_12_mths_ex_med DOUBLE,
              tax_liens DOUBLE,
              delinq_amnt DOUBLE,
              acc_now_delinq DOUBLE,
              chargeoff_within_12_mths DOUBLE,
              mths_since_last_delinq DOUBLE,
              home_ownership VARCHAR,
              purpose VARCHAR,
              addr_state VARCHAR,
              verification_status VARCHAR,
              application_type VARCHAR,
              emp_length VARCHAR,
              earliest_credit_month DATE,
              last_payment_month DATE,
              next_payment_month DATE,
              last_credit_pull_month DATE,
              total_rec_int DOUBLE,
              total_rec_prncp DOUBLE,
              recoveries DOUBLE
            );

            INSERT INTO curated.loans_accepted (
              loan_id,
              loan_amnt,
              loan_status,
              term_months,
              issue_month,
              earliest_credit_month
            ) VALUES
              (1, 10000, ' Fully Paid ', 36, DATE '2013-09-01',
               DATE '2000-09-01'),
              (2, 20000, ' Charged Off ', 60, DATE '2013-09-01',
               DATE '2000-09-01'),
              (3, 12000, 'Current', 36, DATE '2012-01-01',
               DATE '2001-01-01'),
              (4, 15000, 'Does not meet the credit policy. Status:Fully Paid',
               60, DATE '2012-02-01', DATE '2001-02-01'),
              (5, 18000, 'Fully Paid', 36, DATE '2013-10-01',
               DATE '2002-10-01'),
              (6, 9000, 'Fully Paid', 36, NULL, DATE '2003-01-01'),
              (7, 11000, 'Fully Paid', 48, DATE '2012-03-01',
               DATE '2000-03-01'),
              (8, 8000, 'Fully Paid', NULL, DATE '2012-04-01',
               DATE '2000-04-01'),
              (9, 13000,
               'Does not meet the credit policy. Status:Charged Off',
               36, DATE '2012-03-01', DATE '2000-03-01');
            """
        )
        con.execute(MULTITERM_SQL.read_text())


def test_multiterm_cohort_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "multiterm.duckdb"
    build_fixture(db_path)

    with duckdb.connect(str(db_path), read_only=True) as con:
        population = con.execute(
            """
            SELECT
              loan_id,
              loan_status,
              term_months,
              issue_month,
              observation_month,
              required_followup_months,
              months_observed,
              target_bad
            FROM stg.loans_multiterm_population
            ORDER BY loan_id
            """
        ).fetchall()
        retained = con.execute(
            """
            SELECT loan_id, target_bad
            FROM stg.loans_multiterm
            ORDER BY loan_id
            """
        ).fetchall()
        counts = con.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM stg.loans_multiterm_population),
              (SELECT COUNT(*) FROM stg.loans_multiterm),
              (SELECT COUNT(*)
               FROM stg.loans_multiterm_population
               WHERE target_bad IS NULL)
            """
        ).fetchone()
        id_integrity = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT loan_id)
            FROM stg.loans_multiterm
            """
        ).fetchone()
        output_columns = {
            row[0]
            for row in con.execute("DESCRIBE stg.loans_multiterm").fetchall()
        }

    assert population == [
        (
            1,
            "Fully Paid",
            36,
            date(2013, 9, 1),
            date(2019, 3, 1),
            42,
            66,
            0,
        ),
        (
            2,
            "Charged Off",
            60,
            date(2013, 9, 1),
            date(2019, 3, 1),
            66,
            66,
            1,
        ),
        (
            3,
            "Current",
            36,
            date(2012, 1, 1),
            date(2019, 3, 1),
            42,
            86,
            None,
        ),
        (
            4,
            "Does not meet the credit policy. Status:Fully Paid",
            60,
            date(2012, 2, 1),
            date(2019, 3, 1),
            66,
            85,
            None,
        ),
        (
            9,
            "Does not meet the credit policy. Status:Charged Off",
            36,
            date(2012, 3, 1),
            date(2019, 3, 1),
            42,
            84,
            None,
        ),
    ]
    assert retained == [(1, 0), (2, 1)]
    assert counts == (5, 2, 3)
    assert counts[0] == counts[1] + counts[2]
    assert id_integrity == (2, 2)

    post_origination_columns = {
        "last_payment_month",
        "next_payment_month",
        "last_credit_pull_month",
        "total_rec_int",
        "total_rec_prncp",
        "recoveries",
    }
    assert output_columns.isdisjoint(post_origination_columns)
