# Runs the saved Athena queries and checks them against DuckDB.

import json
import subprocess
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "credit_risk.duckdb"
QUERY_DIR = REPO_ROOT / "sql" / "athena"
REPORT_PATH = REPO_ROOT / "reports" / "athena" / "2018Q4_v1.json"

REGION = "eu-west-2"
WORKGROUP = "credit-risk-lab"
DATABASE = "credit_risk"
CATALOG = "AwsDataCatalog"
CURATED_BYTES = 390_019_161

QUERY_FILES = [
    "00_curated_reconciliation.sql",
    "10_vintage_maturity.sql",
    "20_rate_band_economics.sql",
    "21_training_economics.sql",
]

Rows = list[list[str | None]]


def aws_json(*args: str) -> dict[str, Any]:
    command = [
        "aws",
        *args,
        "--region",
        REGION,
        "--output",
        "json",
        "--no-cli-pager",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "AWS CLI command failed")

    response = json.loads(result.stdout)
    if not isinstance(response, dict):
        raise TypeError("expected a JSON object from AWS CLI")
    return response


def parse_result(response: dict[str, Any]) -> tuple[list[str], Rows]:
    result_set = response["ResultSet"]
    columns = [column["Name"] for column in result_set["ResultSetMetadata"]["ColumnInfo"]]

    rows: Rows = []
    for raw_row in result_set.get("Rows", [])[1:]:
        data = raw_row.get("Data", [])
        row = [
            data[index].get("VarCharValue") if index < len(data) else None
            for index in range(len(columns))
        ]
        rows.append(row)
    return columns, rows


def run_athena(sql: str) -> tuple[list[str], Rows, dict[str, object]]:
    started = aws_json(
        "athena",
        "start-query-execution",
        "--query-string",
        sql,
        "--query-execution-context",
        json.dumps({"Database": DATABASE, "Catalog": CATALOG}),
        "--work-group",
        WORKGROUP,
        "--result-reuse-configuration",
        json.dumps({"ResultReuseByAgeConfiguration": {"Enabled": False}}),
    )
    query_id = started["QueryExecutionId"]

    execution: dict[str, Any] | None = None
    for _ in range(180):
        response = aws_json(
            "athena",
            "get-query-execution",
            "--query-execution-id",
            query_id,
        )
        execution = response["QueryExecution"]
        state = execution["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in {"FAILED", "CANCELLED"}:
            reason = execution["Status"].get("StateChangeReason", "")
            raise RuntimeError(f"Athena query {state.lower()}: {reason}")
        time.sleep(1)
    else:
        raise TimeoutError(f"Athena query timed out: {query_id}")

    statistics = execution["Statistics"]
    reused = statistics.get("ResultReuseInformation", {}).get(
        "ReusedPreviousResult", False
    )
    if reused:
        raise RuntimeError("Athena reused an old result; scan bytes are not comparable")

    result = aws_json(
        "athena",
        "get-query-results",
        "--query-execution-id",
        query_id,
    )
    columns, rows = parse_result(result)
    scanned = statistics["DataScannedInBytes"]
    metrics: dict[str, object] = {
        "query_execution_id": query_id,
        "data_scanned_bytes": scanned,
        "scan_share_pct": round(100 * scanned / CURATED_BYTES, 2),
        "total_time_ms": statistics["TotalExecutionTimeInMillis"],
        "engine_version": execution["EngineVersion"]["EffectiveEngineVersion"],
    }
    return columns, rows, metrics


# Accepts equivalent numeric spellings such as -0.0002 and -2E-4.
def same_value(left: str | None, right: str | None) -> bool:
    if left == right:
        return True
    if left is None or right is None:
        return False
    try:
        return Decimal(left) == Decimal(right)
    except InvalidOperation:
        return False


def check_results(
    local_columns: list[str],
    local_rows: Rows,
    athena_columns: list[str],
    athena_rows: Rows,
) -> None:
    if local_columns != athena_columns:
        raise AssertionError("DuckDB and Athena returned different columns")
    if len(local_rows) != len(athena_rows):
        raise AssertionError("DuckDB and Athena returned a different number of rows")

    paired_rows = zip(local_rows, athena_rows, strict=True)
    for row_number, (local_row, athena_row) in enumerate(paired_rows, start=1):
        values = zip(local_columns, local_row, athena_row, strict=True)
        for column, left, right in values:
            if not same_value(left, right):
                raise AssertionError(
                    f"row {row_number}, {column}: DuckDB={left!r}, Athena={right!r}"
                )


def main() -> None:
    runs: list[dict[str, object]] = []

    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        con.execute(
            """
            CREATE TEMP VIEW accepted_loans_v1 AS
            SELECT * REPLACE (CAST(issue_year AS VARCHAR) AS issue_year)
            FROM curated.loans_accepted
            """
        )

        for filename in QUERY_FILES:
            print(f"running {filename}")
            sql = (QUERY_DIR / filename).read_text()

            local = con.execute(sql)
            local_rows = [
                [None if value is None else str(value) for value in row]
                for row in local.fetchall()
            ]
            local_columns = [column[0] for column in local.description]

            athena_columns, athena_rows, metrics = run_athena(sql)
            check_results(local_columns, local_rows, athena_columns, athena_rows)

            metrics["file"] = f"sql/athena/{filename}"
            metrics["duckdb_match"] = True
            runs.append(metrics)
            print(f"  matched; {metrics['data_scanned_bytes']:,} bytes scanned")

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "region": REGION,
        "workgroup": WORKGROUP,
        "database": DATABASE,
        "source_snapshot": "2018Q4",
        "curated_bytes": CURATED_BYTES,
        "queries": runs,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(f"metrics -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
