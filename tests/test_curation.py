# Checks the raw-to-curated contract and its Parquet export.

from datetime import date
from pathlib import Path

import duckdb
import pytest

from scripts.export_curated import export_curated

REPO_ROOT = Path(__file__).resolve().parents[1]
CURATED_SQL = REPO_ROOT / "sql" / "00_curated_accepted.sql"


def build_fixture(db_path: Path) -> None:
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE SCHEMA raw;
            CREATE TABLE raw.loans_accepted (
              id VARCHAR,
              term VARCHAR,
              issue_d VARCHAR,
              earliest_cr_line VARCHAR,
              last_pymnt_d VARCHAR,
              next_pymnt_d VARCHAR,
              last_credit_pull_d VARCHAR,
              loan_status VARCHAR,
              total_rec_int DOUBLE,
              total_rec_prncp DOUBLE,
              recoveries DOUBLE
            );

            INSERT INTO raw.loans_accepted VALUES
              ('1', ' 36 months', 'Jan-2014', 'Jan-2000', 'Jan-2017', NULL,
               'Feb-2017', 'Fully Paid', 1200, 10000, 0),
              ('2', ' 60 months', 'Jan-2015', 'Jan-2001', 'Mar-2019', NULL,
               'Mar-2019', 'Charged Off', 800, 4000, 500),
              ('3', 'unknown', 'Jan-2018', 'Jan-2002', 'Mar-2019', 'Apr-2019',
               'Mar-2019', 'Current', 200, 1000, 0),
              ('Total amount funded: 1000', NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL);
            """
        )
        con.execute(CURATED_SQL.read_text())


def test_curated_contract_and_export(tmp_path: Path) -> None:
    db_path = tmp_path / "credit_risk.duckdb"
    output_dir = tmp_path / "curated" / "accepted_loans" / "v1"
    build_fixture(db_path)

    with duckdb.connect(str(db_path), read_only=True) as con:
        loans = con.execute(
            """
            SELECT loan_id, issue_month, term_months, issue_year, source_snapshot
            FROM curated.loans_accepted
            ORDER BY loan_id
            """
        ).fetchall()
        columns = {
            row[0]: row[1]
            for row in con.execute("DESCRIBE curated.loans_accepted").fetchall()
        }

    assert loans == [
        (1, date(2014, 1, 1), 36, 2014, "2018Q4"),
        (2, date(2015, 1, 1), 60, 2015, "2018Q4"),
        (3, date(2018, 1, 1), None, 2018, "2018Q4"),
    ]
    assert columns["loan_id"] == "BIGINT"
    assert columns["issue_month"] == "DATE"
    assert columns["term_months"] == "SMALLINT"
    assert columns["issue_year"] == "SMALLINT"
    assert {"total_rec_int", "total_rec_prncp", "recoveries"} <= columns.keys()

    rows, partitions = export_curated(db_path, output_dir)
    parquet_files = list(output_dir.glob("**/*.parquet"))

    assert (rows, partitions) == (3, 3)
    assert len(parquet_files) == 3
    assert not list(output_dir.glob("**/issue_year=NULL"))

    with duckdb.connect() as con:
        round_trip = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT loan_id) "
            "FROM read_parquet(?, hive_partitioning = true)",
            [str(output_dir / "**" / "*.parquet")],
        ).fetchone()
        compression = con.execute(
            "SELECT DISTINCT compression FROM parquet_metadata(?)",
            [str(parquet_files[0])],
        ).fetchall()

    assert round_trip == (3, 3)
    assert compression == [("SNAPPY",)]

    with pytest.raises(FileExistsError, match="already exists"):
        export_curated(db_path, output_dir)
