# Checks the mature, common-calendar 36/60-month cohort contract.

from datetime import date
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
REJECTED_SQL = REPO_ROOT / "sql" / "00_curated_rejected.sql"

def build_fixture(db_path: Path) -> None:
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE SCHEMA raw;

            CREATE TABLE raw.loans_rejected (
              "Amount Requested" DOUBLE,
              "Application Date" DATE,
              "Loan Title" VARCHAR,
              "Risk_Score" DOUBLE,
              "Debt-To-Income Ratio" VARCHAR,
              "Zip Code" VARCHAR,
              "State" VARCHAR,
              "Employment Length" VARCHAR,
              "Policy Code" DOUBLE
            );

            INSERT INTO raw.loans_rejected (
              "Amount Requested",
              "Application Date",
              "Loan Title",
              "Risk_Score",
              "Debt-To-Income Ratio",
              "Zip Code",
              "State",
              "Employment Length",
              "Policy Code"
            ) VALUES
              (1000, DATE '2013-01-15', ' Debt consolidation ', 720, '15.5%', ' 123xx ', ' CA ', ' 10+ years ', 1),
              (2000, NULL, ' ', NULL, ' ', ' 456xx ', ' NY ', ' ', 1),
              (3000, DATE '2013-03-10', 'Credit card', 680, '-1%', '789xx', 'TX', '2 years', 0),
              (4000, DATE '2013-04-22', 'Home improvement', 650, '125%', '321xx', 'FL', '5 years', 2),
              (5000, DATE '2013-05-05', 'Other', 700, 'not available', '654xx', 'WA', '< 1 year', NULL);
            """
        )

        con.execute(REJECTED_SQL.read_text())


def test_rejected_curated_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "rejected.duckdb"
    build_fixture(db_path)

    with duckdb.connect(str(db_path), read_only=True) as con:
        row_counts = con.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM raw.loans_rejected) AS raw_count,
              (SELECT COUNT(*) FROM curated.loans_rejected) AS curated_count
            """
        ).fetchone()

        dti_results = con.execute(
            """
            SELECT
              amount_requested,
              dti,
              dti_missing,
              dti_invalid
            FROM curated.loans_rejected
            ORDER BY amount_requested
            """
        ).fetchall()

    assert row_counts == (5, 5)
    assert dti_results == [
        (1000, 15.5, False, False),
        (2000, None, True, False),
        (3000, None, False, True),
        (4000, None, False, True),
        (5000, None, False, True),
    ]

