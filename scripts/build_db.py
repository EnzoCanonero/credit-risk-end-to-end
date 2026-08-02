# Builds the DuckDB database from the raw CSV files.

import os
from pathlib import Path
from typing import cast

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "credit_risk.duckdb"
SQL_DIR = REPO_ROOT / "sql"

BUILD_FILES = ["ingest.sql", "01_clean_schema.sql"]


# Runs the table-building SQL files in dependency order.
def main() -> None:
    os.chdir(REPO_ROOT)

    with duckdb.connect(str(DB_PATH)) as con:
        for name in BUILD_FILES:
            print(f"running {name}")
            con.execute((SQL_DIR / name).read_text())

        rows = cast(
            tuple[int],
            con.execute("SELECT count(*) FROM stg.loans_clean").fetchone(),
        )[0]
        print(f"done: stg.loans_clean has {rows:,} rows")


if __name__ == "__main__":
    main()
