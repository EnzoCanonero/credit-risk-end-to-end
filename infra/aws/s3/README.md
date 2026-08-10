# S3 data foundation

## Cost forecast

The persistent dataset is 0.783 GB: 392,582,231 bytes of raw gzip and
390,019,161 bytes of curated Parquet. At the eu-west-2 list prices checked on
2026-08-10, the storage forecast is:

| Period | Storage state | Estimated cost |
|---|---|---:|
| First 90 days | 0.783 GB in S3 Standard | $0.019/month |
| After day 90 | 0.390 GB Standard + 0.393 GB Glacier Instant Retrieval | $0.011/month |
| First year | Lifecycle applied after 90 days | $0.16 total |
| Three years | No new versions or data | $0.43 total |

The estimate uses $0.024/GB-month for S3 Standard and $0.005/GB-month for
Glacier Instant Retrieval. It excludes free-tier credits, tax, requests,
retrievals and extra object versions. Query-result storage is negligible and
expires after seven days. See the official [S3 pricing](https://aws.amazon.com/s3/pricing/)
and [Glacier storage-class](https://docs.aws.amazon.com/AmazonS3/latest/userguide/glacier-storage-classes.html)
documentation. The raw transition also satisfies Glacier Instant Retrieval's
90-day minimum-storage period.

## Achievement

The bucket holds an immutable curated contract for **2,260,668 unique accepted
loans**. A 392.6 MB compressed CSV source became 12 Snappy Parquet objects,
partitioned by source snapshot and issue year, without changing the source of
truth used by the local analysis.

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
| Encryption | SSE-S3 (`AES256`) at rest |
| Recovery | Bucket versioning enabled |
| Transfer integrity | SHA-256 requested on the source upload |
| Cost and cleanup | Reviewed lifecycle in [`lifecycle.json`](lifecycle.json) |

The source was uploaded without unpacking or transforming it:

```bash
aws s3 cp \
  data/raw/accepted_2007_to_2018Q4.csv.gz \
  s3://enzo-credit-risk-eu-west-2/raw/lending_club/2018Q4/accepted_2007_to_2018Q4.csv.gz \
  --content-type application/gzip \
  --checksum-algorithm SHA256
```

The local DuckDB contract casts fields once at the raw-to-curated boundary.
[`scripts/export_curated.py`](../../../scripts/export_curated.py) then writes
Hive-style Snappy Parquet and refuses to overwrite an existing local `v1`:

```bash
python scripts/export_curated.py
aws s3 sync \
  data/curated/lending_club/accepted_loans/v1/ \
  s3://enzo-credit-risk-eu-west-2/curated/lending_club/accepted_loans/v1/
```

`sync` uploads new or changed generated files without re-uploading unchanged
objects. No `--delete` is used, so it does not remove remote objects.

## Lifecycle decisions

The checked-in lifecycle configuration does four things:

- aborts incomplete multipart uploads after seven days;
- expires Athena results after seven days and their noncurrent versions after one day;
- removes expired Athena delete markers;
- moves raw current and noncurrent objects larger than 128 KiB to Glacier
  Instant Retrieval after 90 days.

Curated Parquet stays in S3 Standard because it is the interactive analytical
layer. Raw data is retained but becomes cheaper after its normal recovery
window. Glacier retrieval and version growth are deliberately excluded from
the steady-state forecast because they depend on future use.

`v1` is a data-contract convention, not snapshot isolation. S3 versioning can
recover an overwritten key, but Athena reads the current object version. A
schema change should therefore be exported to a new prefix such as `v2` rather
than overwriting this dataset.
