# Loads project data from DuckDB.

from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "credit_risk.duckdb"


# Loads the cleaned loan table.
def load_loans(db_path: Path = DB_PATH, table: str = "stg.loans_clean") -> pd.DataFrame:

    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute(f"SELECT * FROM {table}").df()


# Loads the loan outcome fields.
def load_outcomes(db_path: Path = DB_PATH, table: str = "curated.loans_accepted") -> pd.DataFrame:

    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute(
            f"SELECT id, loan_amnt, total_rec_int, total_rec_prncp, recoveries FROM {table}"
        ).df()
