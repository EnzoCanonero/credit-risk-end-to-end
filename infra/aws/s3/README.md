# S3 data foundation

## Cost forecast

The persistent dataset is 782,601,392 bytes, or 0.729 GB in the binary units
used by S3 billing: 0.366 GB of raw gzip and 0.363 GB of curated Parquet. At the
eu-west-2 USD list prices checked on 2026-08-10, the storage forecast is:

| Period | Storage state | Estimated cost |
|---|---|---:|
| First 90 days | 0.729 GB in S3 Standard | $0.0175/month |
| After day 90 | 0.363 GB Standard + 0.366 GB Glacier Instant Retrieval | $0.0105/month |
| First year | Lifecycle applied after 90 days | $0.15 total |
| Three years | No new versions or data | $0.40 total |

The estimate uses $0.024/GB-month for S3 Standard and $0.005/GB-month for
Glacier Instant Retrieval. It excludes free-tier credits, tax, requests,
retrievals and extra object versions. Query-result storage is negligible and
becomes eligible for expiration after seven days. See the official [S3 pricing](https://aws.amazon.com/s3/pricing/)
and [Glacier storage-class](https://docs.aws.amazon.com/AmazonS3/latest/userguide/glacier-storage-classes.html)
documentation. The forecast assumes the raw object remains in Glacier Instant
Retrieval for at least 90 days after transition; deleting or replacing it
earlier would still incur the remainder of that class's minimum-duration charge.

At the same roughly 50/50 raw-to-curated mix, one TB of retained data would
cost about $14.82/month after transition. That is a linear storage projection,
not a complete operating-cost forecast: extra versions and Glacier retrieval
frequency become the main variables as the dataset grows.

## Achievement

The bucket holds the published `v1` curated contract for **2,260,668 unique
accepted loans**. A 392.6 MB compressed CSV source became 12 Snappy Parquet
objects, partitioned by source snapshot and issue year, without changing the
source of truth used by the local analysis.

```text
s3://enzo-credit-risk-eu-west-2/
├── raw/lending_club/2018Q4/accepted_2007_to_2018Q4.csv.gz
├── curated/lending_club/accepted_loans/v1/
│   └── source_snapshot=2018Q4/
│       ├── issue_year=2007/data_0.parquet
│       ├── ...
│       └── issue_year=2018/data_0.parquet
└── athena-results/                 # ephemeral query output
```

The raw, curated and query-result boundaries make retention, permissions and
query cost independently manageable. Only the accepted-loan source is present;
the rejected-loan file is deliberately outside this version.

## How it was built

The bucket was created with the AWS CLI rather than infrastructure as code so
that the first implementation exposed the AWS resources and controls directly.
Its baseline controls are:

| Control | Implementation |
|---|---|
| Public access | All four S3 public-access-block settings enabled |
| Encryption | Default SSE-S3 (`AES256`) at rest; SSE-C blocked |
| Recovery | Bucket versioning enabled |
| Transfer integrity | SHA-256 recorded as a composite multipart checksum for the source upload |
| Cost and cleanup | Reviewed lifecycle in [`lifecycle.json`](lifecycle.json) |

The lifecycle configuration was applied from the repository root:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket enzo-credit-risk-eu-west-2 \
  --lifecycle-configuration file://infra/aws/s3/lifecycle.json \
  --region eu-west-2
```

The source was uploaded without unpacking or transforming it:

```bash
aws s3 cp \
  data/raw/accepted_2007_to_2018Q4.csv.gz \
  s3://enzo-credit-risk-eu-west-2/raw/lending_club/2018Q4/accepted_2007_to_2018Q4.csv.gz \
  --content-type application/gzip \
  --checksum-algorithm SHA256
```

DuckDB infers the source CSV types during ingest. The curated view then removes
non-loan footer rows and adds a canonical numeric ID, dates, term length,
snapshot and issue-year keys while retaining every source column.
[`scripts/export_curated.py`](../../../scripts/export_curated.py) writes that
contract as Hive-style Snappy Parquet and refuses to overwrite an existing
local `v1`:

```bash
python scripts/export_curated.py
aws s3 sync \
  data/curated/lending_club/accepted_loans/v1/ \
  s3://enzo-credit-risk-eu-west-2/curated/lending_club/accepted_loans/v1/
```

`sync` uploads missing files, files with a different size and files whose local
source is newer. It does not compare the Parquet content by checksum. No
`--delete` is used, so it does not remove remote objects.

## Lifecycle decisions

The checked-in lifecycle configuration does four things:

- aborts incomplete multipart uploads after seven days;
- makes current Athena results eligible for expiration after seven days, which
  creates delete markers in this versioned bucket;
- permanently removes their noncurrent data versions after one day and cleans
  up expired delete markers;
- moves raw current and noncurrent objects larger than 128 KiB to Glacier
  Instant Retrieval after 90 days.

Curated Parquet stays in S3 Standard because it is the interactive analytical
layer. Raw data is retained but becomes cheaper after its normal recovery
window. Glacier retrieval and version growth are deliberately excluded from
the steady-state forecast because they depend on future use.

`v1` is treated as immutable by convention; Object Lock and a write-deny policy
do not enforce that rule. S3 versioning can recover an overwritten key, but
Athena reads the current object version. A schema change should therefore be
exported to a new prefix such as `v2` rather than overwriting this dataset.
