# Athena analytical layer

## Cost forecast

The recorded four-query analysis read 41,031,610 bytes. Athena bills each query
to the next MB with a 10 MB minimum, so this run is approximately 52 billable
MB at the $5/TB list price checked on 2026-08-10.

| Usage | Estimated Athena scan cost |
|---|---:|
| One complete four-query run | $0.00026 |
| One run per month | $0.0031/year |
| One run per day | $0.0078/month, $0.095/year |
| 100 runs per month | $0.026/month |

This excludes free-tier credits, tax, S3 requests and result storage. The Glue
catalog contains only one database, one table and 12 partitions, well within
the current free allowance for its first million metadata objects and monthly
accesses. No Glue crawler or ETL job runs. See the official
[Athena pricing](https://aws.amazon.com/athena/pricing/) and
[Glue pricing](https://aws.amazon.com/glue/pricing/). Pricing should be
rechecked before using these estimates as a budget.

## Achievement

Athena reproduced four local DuckDB analyses with the same ordered aggregate
results. It queried **2,260,668 loans in place** from the 390,019,161-byte
curated S3 dataset; it did not ingest or copy them into a database.

| Query | Bytes scanned | Share of curated bytes | DuckDB parity |
|---|---:|---:|:---:|
| Curated reconciliation | 10,525,726 | 2.70% | yes |
| Vintage maturity | 2,604,455 | 0.67% | yes |
| Rate-band economics | 20,978,451 | 5.38% | yes |
| Training economics | 6,922,978 | 1.78% | yes |

These percentages are measured scan shares, not claimed savings against an
unmeasured `SELECT *` baseline. The durable query IDs, timings and byte counts
are in [`reports/athena/2018Q4_v1.json`](../../../reports/athena/2018Q4_v1.json);
the economic interpretation is in the accompanying
[report](../../../reports/athena/2018Q4_v1.md).

## Architecture

```text
S3 Parquet objects
        │ read in place
        ▼
Athena engine ─── resolves schema and partitions ─── Glue Data Catalog
        │
        └── writes temporary CSV/metadata ──► s3://.../athena-results/
```

The catalog objects have distinct jobs:

- `AwsDataCatalog` identifies the regional Glue catalog;
- `credit_risk` is its database namespace;
- `accepted_loans_v1` stores the Parquet schema, input `LOCATION` and partition-key definitions;
- 12 partition entries map one snapshot and years 2007–2018 to concrete S3 prefixes.

The table `LOCATION` is the input root. Query output goes to the workgroup's
`athena-results/` prefix and expires after seven days.

## Catalog setup

The setup was deliberately explicit instead of using a Glue crawler. The
schema was already known from DuckDB, so checked-in DDL avoids inference drift.

First, the database DDL created the Glue namespace:

```bash
aws athena start-query-execution \
  --query-string "CREATE DATABASE IF NOT EXISTS credit_risk" \
  --work-group credit-risk-lab \
  --region eu-west-2
```

Next, [`accepted_loans_v1.sql`](accepted_loans_v1.sql) registered 158 physical
Parquet columns and two virtual string partition columns:

```bash
aws athena start-query-execution \
  --query-string file://infra/aws/athena/accepted_loans_v1.sql \
  --work-group credit-risk-lab \
  --region eu-west-2
```

`CREATE EXTERNAL TABLE` has no `FROM` because it describes existing files. It
creates metadata only; `PARTITIONED BY` declares keys and does not reorganize
the Parquet objects.

Finally, the Hive directories already written by DuckDB were registered:

```bash
aws athena start-query-execution \
  --query-string "MSCK REPAIR TABLE credit_risk.accepted_loans_v1" \
  --work-group credit-risk-lab \
  --region eu-west-2
```

Before `MSCK`, Glue knew the table schema and partition-key names but not the
12 concrete values and locations. `MSCK` added that metadata; it created no
directories and copied no data. For a recurring production load, explicit
`ALTER TABLE ADD PARTITION` or partition projection would avoid repeatedly
scanning the layout.

## Cost controls and reproducibility

The `credit-risk-lab` workgroup enforces an encrypted S3 result location,
CloudWatch query metrics and a 1 GiB per-query scan cutoff. The cutoff is a
runaway-query guardrail, not an optimization, and bytes read before cancellation
can still be billed.

The shared SQL under [`sql/athena/`](../../../sql/athena/) uses two independent
cost controls:

- partition predicates on `source_snapshot` and `issue_year` avoid unrelated locations;
- explicit column projection lets Parquet read only the required column chunks.

The exact date filters still enforce the economic cohort. Athena cannot infer
that a predicate on `issue_month` should prune an `issue_year` partition, so
both coarse year and exact date conditions are present. `LIMIT` is not used as
a cost control because it does not guarantee fewer bytes read.

Run the saved analysis after the catalog and workgroup exist:

```bash
python scripts/run_athena_analysis.py
```

[`scripts/run_athena_analysis.py`](../../../scripts/run_athena_analysis.py)
runs the same four SQL files in DuckDB and Athena, disables result reuse so scan
measurements remain comparable, and writes the JSON evidence only after all
ordered results match.

## Credit-risk result

The mature 36-month cohort contains 708,368 loans and 100,413 charge-offs.
Realised repayment margin rises from 9.5% to 22.1% across interest-rate
quartiles, while charge-off loss remains between 36.4% and 38.1% of principal.

The more important modelling result is censoring: 90.01% of 2018 60-month loans
were unresolved at the 2019-03 observation date. Their resolved-only bad rate
is therefore not a lifetime probability of default. The current model stays on
fully matured 36-month loans; a survival or hazard model is the natural
extension for mixed terms.
