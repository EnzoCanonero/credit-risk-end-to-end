# Exports the curated accepted loans to Hive-partitioned Parquet.

from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "credit_risk.duckdb"
OUTPUT_DIR = (
    REPO_ROOT
    / "data"
    / "curated"
    / "lending_club"
    / "accepted_loans"
    / "v1"
)


def export_curated(db_path: Path, output_dir: Path) -> tuple[int, int]:
    if not db_path.is_file():
        raise FileNotFoundError(f"database not found: {db_path}")
    if output_dir.exists():
        raise FileExistsError(f"output already exists: {output_dir}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        stats = con.execute(
            """
            SELECT
              COUNT(*) AS rows,
              COUNT(DISTINCT issue_year) AS partitions,
              COUNT(*) FILTER (
                WHERE source_snapshot IS NULL OR issue_year IS NULL
              ) AS missing_partition_keys
            FROM curated.loans_accepted
            """
        ).fetchone()
        if stats is None:
            raise RuntimeError("could not read curated.loans_accepted")

        rows, partitions, missing_partition_keys = stats
        if missing_partition_keys:
            raise ValueError("curated data contains null partition keys")

        output_dir.parent.mkdir(parents=True, exist_ok=True)
        output = str(output_dir).replace("'", "''")
        con.execute(
            f"""
            COPY curated.loans_accepted
            TO '{output}' (
              FORMAT PARQUET,
              PARTITION_BY (source_snapshot, issue_year),
              COMPRESSION SNAPPY
            )
            """
        )

    return rows, partitions


def main() -> None:
    rows, partitions = export_curated(DB_PATH, OUTPUT_DIR)
    print(f"exported {rows:,} rows in {partitions} yearly partitions")
    print(f"curated -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
