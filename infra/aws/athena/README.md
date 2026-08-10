# Athena analytical layer

## Cost forecast

The recorded four-query analysis read 41,031,610 bytes. Athena rounds each
query up to the next MB with a 10 MB minimum, so this run represents 52
billable MB at the eu-west-2 USD list price of $5/TB checked on 2026-08-10.

| Usage | Estimated Athena scan cost |
|---|---:|
| One complete four-query run | $0.00025 |
| 30 runs per month | $0.0074/month |
| 100 runs per month | $0.0248/month |
| 365 runs per year | $0.0905/year |

This excludes free-tier credits, tax, S3 requests and result storage. This
project registers one database, one table and 12 partitions. Even allowing for
table versions, that is far below Glue's allowance of one million stored
metadata objects; the first million metadata requests each month are also free.
No Glue crawler or ETL job runs. See the official
[Athena pricing](https://aws.amazon.com/athena/pricing/) and
[Glue pricing](https://aws.amazon.com/glue/pricing/). Pricing should be
rechecked before using these estimates as a budget.

At this size, Athena's per-query billing floor materially affects the total. A
linear projection to a one-TB curated dataset in AWS billing units, with the
same layout and scan shares, would read about 108 GB across the four queries
and cost about $0.53 per run. This is a unit-cost projection, not a performance
benchmark: file layout, partition cardinality, skew and concurrency also
matter. Every projected query would exceed the current 1 GiB guardrail, so
scaling would require deliberately raising it or reducing scans through finer
pruning or materialised aggregates.

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
`athena-results/` prefix and becomes eligible for lifecycle expiration after
seven days.

## Workgroup setup

Run the setup from the repository root after uploading curated `v1` to S3. The
workgroup keeps query history and cost controls separate from the catalog:

```bash
aws athena create-work-group \
  --name credit-risk-lab \
  --description "Athena workgroup for the credit-risk data lake lab" \
  --configuration '{
    "ResultConfiguration": {
      "OutputLocation": "s3://enzo-credit-risk-eu-west-2/athena-results/",
      "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"}
    },
    "EnforceWorkGroupConfiguration": true,
    "PublishCloudWatchMetricsEnabled": true,
    "BytesScannedCutoffPerQuery": 1073741824,
    "EngineVersion": {"SelectedEngineVersion": "AUTO"}
  }' \
  --region eu-west-2
```

This is a one-time command for the deployed demo names. Another bucket,
snapshot or account must update the table `LOCATION` and the constants in
[`scripts/run_athena_analysis.py`](../../../scripts/run_athena_analysis.py).

## Catalog setup

The setup was deliberately explicit instead of using a Glue crawler. The
schema was already known from DuckDB, so checked-in DDL avoids inference drift.

Each `start-query-execution` call below is asynchronous and returns a query ID.
Before running the dependent step, poll until its status is `SUCCEEDED`:

```bash
aws athena get-query-execution \
  --query-execution-id QUERY_ID \
  --region eu-west-2 \
  --query 'QueryExecution.Status.{State:State,Reason:StateChangeReason}'
```

A successful submission does not mean the SQL execution itself succeeded.

First, the database DDL created the Glue namespace:

```bash
aws athena start-query-execution \
  --query-string "CREATE DATABASE IF NOT EXISTS credit_risk COMMENT 'Catalog metadata for the credit-risk data lake'" \
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
the Parquet objects. `IF NOT EXISTS` makes the command repeatable but does not
repair or replace an already registered schema.

Finally, the Hive directories already written by DuckDB were registered:

```bash
aws athena start-query-execution \
  --query-string "MSCK REPAIR TABLE credit_risk.accepted_loans_v1" \
  --work-group credit-risk-lab \
  --region eu-west-2
```

Before `MSCK`, Glue knew the table schema and partition-key names but not the
12 concrete values and locations. `MSCK` added that metadata; it created no
directories and copied no data. It only adds discovered partitions and does not
remove stale catalog entries. For a recurring production load, explicit
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

The runner also sets `Database=credit_risk,Catalog=AwsDataCatalog` as its query
execution context so the shared SQL can use the unqualified table name. That
context resolves names; it does not choose the workgroup, grant permissions or
move data.

The exact date filters still enforce the economic cohort. Athena cannot infer
that a predicate on `issue_month` should prune an `issue_year` partition, so
both coarse year and exact date conditions are present. `LIMIT` is not used as
a cost control because it does not guarantee fewer bytes read.

Run the saved analysis after the catalog and workgroup exist and the local
`data/credit_risk.duckdb` has been built:

```bash
python scripts/run_athena_analysis.py
```

[`scripts/run_athena_analysis.py`](../../../scripts/run_athena_analysis.py)
runs the same four SQL files in DuckDB and Athena, disables result reuse so scan
measurements remain comparable, and writes the JSON evidence only after all
ordered results match. These small aggregates fit in one Athena result page;
the runner is not a general export tool and does not paginate large results.
The committed JSON records the query IDs and metrics, but reproduction still
assumes the current `v1` S3 objects have not changed: S3 Versioning retains old
versions while Athena reads the current ones.

## Credit-risk result

The mature 36-month cohort contains 708,368 loans and 100,413 charge-offs.
Realised repayment margin rises from 9.5% to 22.1% across interest-rate
quartiles. The realised net shortfall on charged-off loans, after principal
receipts, recoveries and interest, remains between 36.4% and 38.1% of original
principal.

The more important modelling result is censoring: 90.01% of 2018 60-month loans
were unresolved at the 2019-03 observation date. Their resolved-only bad rate
is therefore not a lifetime probability of default. The current model stays on
fully matured 36-month loans; a survival or hazard model is the natural
extension for mixed terms.
