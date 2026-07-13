from pathlib import Path

# Data loading from the project DuckDB database.

import duckdb
import pandas as pd

DB_PATH = Path("data/credit_risk.duckdb")


def load_loans(db_path: Path = DB_PATH, table: str = "stg.loans_clean") -> pd.DataFrame:
    #Load a table from DuckDB into a pandas DataFrame.

    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute(f"SELECT * FROM {table}").df()
