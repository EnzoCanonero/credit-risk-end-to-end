# Data loading from the project DuckDB database.

from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "credit_risk.duckdb"


def load_loans(db_path: Path = DB_PATH, table: str = "stg.loans_clean") -> pd.DataFrame:
    #Load a table from DuckDB into a pandas DataFrame.

    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute(f"SELECT * FROM {table}").df()
