# Lambda scoring

## Cost forecast

The ECR image is 303,533,893 bytes. At the eu-west-2 list prices checked on
2026-08-10, low-volume cost is dominated by storing that image rather than by
invoking the function.

| Monthly usage | ECR storage | Warm invocation estimate | Estimated total |
|---|---:|---:|---:|
| No invocations | $0.030 | $0.000 | $0.030/month |
| 1,000 invocations | $0.030 | $0.0007 | $0.031/month |
| 10,000 invocations | $0.030 | $0.0073 | $0.038/month |
| 100,000 invocations | $0.030 | $0.0733 | $0.104/month |

The invocation estimate uses 2 GB for the measured 16 ms warm billing period,
$0.0000166667 per GB-second and $0.20 per million requests. Each representative
4.272-second cold invocation adds about **$0.000143**; the actual number of cold
starts depends on idle time and concurrency. The table excludes free-tier
credits, tax and negligible logs retained for seven days. ECR-to-Lambda image
transfer in the same region is free. See the official
[Lambda pricing](https://aws.amazon.com/lambda/pricing/) and
[ECR pricing](https://aws.amazon.com/ecr/pricing/). Pricing should be rechecked
before budgeting.

## Achievement

The same validated loan contract and model artifact now run in a direct-invoke
AWS Lambda container. The deployed function returned:

```json
{
  "default_probability": 0.15805194933645042,
  "approve": true
}
```

This matches local serving for [`sample_event.json`](sample_event.json). The
exact probability can change when the model is rebuilt; the response contract
is a probability and approval decision.

## Request path

```text
JSON event
   │
   ▼
lambda_handler.handler
   ├── Loan.model_validate(event)       request contract
   ├── cached LightGBM pipeline         preprocessing + model
   └── score_one(...)                   shared with FastAPI
   │
   ▼
JSON response
```

[`app/lambda_handler.py`](../../../app/lambda_handler.py) is a thin adapter. It
translates Lambda's `event, context` interface into the existing
`credit_risk.schema.Loan` and `score_one` application interface. The model is
loaded during environment initialization and reused by warm invocations.

`int_rate` and the seven categorical fields are required. Other numeric fields
may be omitted or set to `null` because the model pipeline imputes them.
Unknown fields are rejected, and invalid events fail the invocation.

## Container and registry

[`Dockerfile.lambda`](../../../Dockerfile.lambda) starts from the official
Python 3.12 Lambda image, installs `libgomp` for LightGBM, installs the pinned
runtime dependencies, and copies only the scoring package, handler and model
artifact into `/var/task`. It sets one OpenMP thread and declares
`lambda_handler.handler` as the entry point.

The image is built as `linux/amd64` because the deployed function is x86_64.
The dedicated ECR repository has immutable tags and scan-on-push enabled:

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com/credit-risk-lambda"

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --file Dockerfile.lambda \
  --tag credit-risk-lambda:local \
  --load .

aws ecr get-login-password --region eu-west-2 \
  | docker login \
      --username AWS \
      --password-stdin \
      "$AWS_ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com"

docker tag credit-risk-lambda:local "$ECR_URI:v1"
docker push "$ECR_URI:v1"
```

The registry tag names the remote destination; `docker push` uploads the layers
associated with that local tag. Lambda resolved `v1` to immutable digest
`sha256:f7227f3aae98a8f67aac71b21639f559b3a3f80cb41498b12bb4c81b3c43bb8e`.

## IAM and function creation

The execution role is `credit-risk-lambda-execution-role`. Its
[`trust-policy.json`](trust-policy.json) allows the Lambda service to assume
the role. The attached AWS-managed `AWSLambdaBasicExecutionRole` policy permits
CloudWatch log creation and writes only.

The function does not read S3 at runtime and does not need ECR permissions on
its execution role: the model is inside the image, and Lambda retrieves the
image through its service integration. Keeping the role log-only makes the
runtime permission boundary explicit.

```bash
aws lambda create-function \
  --function-name credit-risk-inference \
  --package-type Image \
  --code ImageUri="$ECR_URI:v1" \
  --role "arn:aws:iam::$AWS_ACCOUNT_ID:role/credit-risk-lambda-execution-role" \
  --architectures x86_64 \
  --memory-size 2048 \
  --timeout 30 \
  --region eu-west-2 \
  --tags Project=credit-risk

aws lambda wait function-active-v2 \
  --function-name credit-risk-inference \
  --region eu-west-2
```

Creating the function links the image digest, execution role and runtime
configuration into a Lambda resource. It does not create a public HTTP route;
this implementation is invoked directly through the AWS API.

## Validation and measured latency

```bash
aws lambda invoke \
  --function-name credit-risk-inference \
  --region eu-west-2 \
  --cli-binary-format raw-in-base64-out \
  --payload file://infra/aws/lambda/sample_event.json \
  /tmp/credit-risk-response.json

aws logs tail \
  /aws/lambda/credit-risk-inference \
  --since 5m \
  --region eu-west-2 \
  --format short
```

These are single invocations from 2026-08-10, not a latency benchmark:

| Invocation | Init | Handler duration | Billed | Max memory |
|---|---:|---:|---:|---:|
| First cold attempt | 9,999.74 ms, timed out | 8,530.94 ms | 8,531 ms | 282 MB |
| Later cold start | 4,230.06 ms | 41.92 ms | 4,272 ms | 283 MB |
| Immediate warm reuse | — | 15.38 ms | 16 ms | 283 MB |

The first initialization exceeded Lambda's on-demand initialization window and
was retried during the invocation. The `joblib` serial-mode warning is benign
for single-record inference; the handler still returned the expected result.

## Engineering conclusion

Warm inference is fast and the serverless cost is very low for sporadic work,
but the measured multi-second and variable cold start makes this image a poor
latency-sensitive HTTP endpoint without further optimization or provisioned
capacity. FastAPI remains the cleaner continuously available API; Lambda is a
credible option for asynchronous or event-driven scoring where startup latency
is acceptable.
