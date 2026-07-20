# Build the DuckDB database from the raw CSVs.
#
# Runs the SQL files that create tables, in order. The rest of sql/ is checks and EDA,
# run by hand. Safe to re-run, since the SQL uses CREATE OR REPLACE.

import os
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "credit_risk.duckdb"
SQL_DIR = REPO_ROOT / "sql"

# The files that build tables, in dependency order.
BUILD_FILES = ["ingest.sql", "01_clean_schema.sql"]


def main() -> None:
    # ingest.sql reads the CSVs with paths relative to the repo root.
    os.chdir(REPO_ROOT)

    with duckdb.connect(str(DB_PATH)) as con:
        for name in BUILD_FILES:
            print(f"running {name}")
            con.execute((SQL_DIR / name).read_text())

        rows = con.execute("SELECT count(*) FROM stg.loans_clean").fetchone()[0]
        print(f"done: stg.loans_clean has {rows:,} rows")


if __name__ == "__main__":
    main()
