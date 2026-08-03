# Athena analytical layer

This directory registers the immutable curated v1 Parquet dataset as an
external Athena table. The setup is deliberately AWS CLI based: S3 owns the
files, Glue owns their metadata, and Athena reads only the partitions and
columns required by each query.

## Data prepared before Athena

`scripts/export_curated.py` writes Snappy Parquet under the Hive layout:

```text
s3://enzo-credit-risk-eu-west-2/curated/lending_club/accepted_loans/v1/
└── source_snapshot=2018Q4/
    ├── issue_year=2007/data_0.parquet
    ├── ...
    └── issue_year=2018/data_0.parquet
```

The 12 partitions contain 2,260,668 unique accepted loans. The table has 158
physical Parquet columns and two virtual partition columns. Bucket versioning,
SSE-S3, public-access blocking, the reviewed lifecycle in
`infra/aws/s3/lifecycle.json`, and the `credit-risk-lab` Athena workgroup must
already exist.

The workgroup used for the recorded run enforces:

- query results under `s3://enzo-credit-risk-eu-west-2/athena-results/`;
- SSE-S3 result encryption;
- a 1 GiB per-query scan cutoff;
- CloudWatch query metrics.

The result prefix expires after seven days. Durable evidence belongs in the
generated report, not in the query-result bucket.

## Catalog bootstrap

Create the logical database once:

```bash
aws athena start-query-execution \
  --query-string "CREATE DATABASE IF NOT EXISTS credit_risk" \
  --work-group credit-risk-lab \
  --region eu-west-2
```

Register the physical Parquet schema and its partition-key definition:

```bash
aws athena start-query-execution \
  --query-string file://infra/aws/athena/accepted_loans_v1.sql \
  --work-group credit-risk-lab \
  --region eu-west-2
```

Discover the existing Hive directories and add their concrete partition
entries to Glue:

```bash
aws athena start-query-execution \
  --query-string \
    "MSCK REPAIR TABLE credit_risk.accepted_loans_v1" \
  --work-group credit-risk-lab \
  --region eu-west-2
```

`CREATE EXTERNAL TABLE` and `MSCK REPAIR TABLE` create metadata only. They do
not copy, aggregate, or rewrite the Parquet files.

## Reproducible analysis

The SQL under `sql/athena/` is intentionally column-explicit. Economic queries
also include `issue_year` predicates so Athena can prune partitions before
applying exact date conditions. Once the catalog setup above exists, run the
queries and check their results against DuckDB with:

```bash
python scripts/run_athena_analysis.py
```

The project constants are visible at the top of the script. For a non-default
AWS CLI profile, set `AWS_PROFILE=NAME` before the command. The runner writes
only the query IDs, scan metrics and parity result to
`reports/athena/2018Q4_v1.json`; the accompanying Markdown report is the
reviewed interpretation of that run.
