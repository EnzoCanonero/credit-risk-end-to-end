# Lambda scoring

## Cost forecast

ECR reports a compressed image size of 303,533,893 bytes, or 0.283 GB using a
binary conversion. At the eu-west-2 USD list prices checked on 2026-08-10,
low-volume cost is dominated by storing that image rather than invoking the
function.

| Monthly usage | ECR storage | Warm invocation estimate | Estimated total |
|---|---:|---:|---:|
| No invocations | $0.028 | $0.000 | $0.028/month |
| 1,000 invocations | $0.028 | $0.0007 | $0.029/month |
| 10,000 invocations | $0.028 | $0.0073 | $0.036/month |
| 100,000 invocations | $0.028 | $0.0733 | $0.102/month |
| 1,000,000 invocations | $0.028 | $0.7333 | $0.762/month |

The ECR estimate uses $0.10/GB-month. The invocation estimate uses 2 GB for the
measured 16 ms warm billing period, $0.0000166667 per GB-second and $0.20 per
million requests. Each representative 4.272-second cold invocation adds about
**$0.000143**; the actual number of cold starts depends on idle time and
concurrency. The table excludes free-tier
credits, tax, CloudWatch ingestion and storage, and any trigger or public API.
ECR-to-Lambda image transfer in the same region is free. The storage estimate
assumes one retained image; immutable future tags add storage for layers not
already shared unless an ECR lifecycle policy removes old releases. See the
official [Lambda pricing](https://aws.amazon.com/lambda/pricing/) and
[ECR pricing](https://aws.amazon.com/ecr/pricing/). Pricing should be rechecked
before budgeting.

Compute cost scales with requests, allocated memory and billed duration. At
this model's measured warm duration, even one million direct invocations cost
less than one dollar before the free tier; concurrency, cold-start rate and
tail latency would become business constraints before compute spend does.

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
is a probability and approval decision. Approval means the estimated default
probability is below the break-even probability implied by `int_rate`.

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
Unknown fields are rejected. For a synchronous Invoke API call, a validation
exception appears as `FunctionError` and an error payload; `StatusCode: 200`
alone only confirms that the Invoke request completed.

The handler expects the event itself to be the loan object. An API Gateway
proxy event has an envelope and would need a separate adapter before it could
reuse this contract.

## Container and registry

[`Dockerfile.lambda`](../../../Dockerfile.lambda) starts from the official
Python 3.12 Lambda image, installs `libgomp` for LightGBM, installs the pinned
runtime dependencies, and copies only the scoring package, handler and model
artifact into `/var/task`. It sets one OpenMP thread and declares
`lambda_handler.handler` as the handler command consumed by the AWS base
image's entry point.

The image is built as `linux/amd64` because the deployed function is x86_64.
The model artifact and its metadata are generated and gitignored. After
building the local `data/credit_risk.duckdb`, generate both before Docker tries
to copy them:

```bash
python scripts/build_model.py
```

The dedicated ECR repository uses AES-256 encryption, immutable tags and
scan-on-push. Create it once:

```bash
aws ecr create-repository \
  --repository-name credit-risk-lambda \
  --region eu-west-2 \
  --image-scanning-configuration scanOnPush=true \
  --image-tag-mutability IMMUTABLE \
  --tags Key=Project,Value=credit-risk
```

Build and push a release from the repository root:

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
The next image must use a new tag such as `v2`; `v1` cannot be overwritten.

## IAM and function creation

The execution role is `credit-risk-lambda-execution-role`. Its
[`trust-policy.json`](trust-policy.json) allows the Lambda service to assume
the role. The attached AWS-managed `AWSLambdaBasicExecutionRole` policy permits
CloudWatch log creation and writes only.

```bash
aws iam create-role \
  --role-name credit-risk-lambda-execution-role \
  --assume-role-policy-document file://infra/aws/lambda/trust-policy.json

aws iam attach-role-policy \
  --role-name credit-risk-lambda-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam wait role-exists \
  --role-name credit-risk-lambda-execution-role
```

IAM changes are eventually consistent, so function creation can still require
a brief propagation delay after this one-time setup.

The function does not read S3 at runtime and does not need ECR permissions on
its execution role because the model is inside the image. Image retrieval is
authorized separately by the ECR repository policy for the
`lambda.amazonaws.com` service principal. Lambda can add the same-account
policy during function creation. The deployer therefore needs
`GetRepositoryPolicy`, `SetRepositoryPolicy`, `BatchGetImage` and
`GetDownloadUrlForLayer` on this repository. Keeping the runtime role log-only
makes its permission boundary explicit. See the AWS
[ECR permission requirements](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html#images-create-permissions).

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com/credit-risk-lambda"

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

The ECR tag `v1` is not a published Lambda version. The recorded invocation ran
the mutable Lambda configuration named `$LATEST`; a production rollout would
publish a numbered Lambda version and move an alias deliberately.

## Validation and measured latency

```bash
aws lambda invoke \
  --function-name credit-risk-inference \
  --region eu-west-2 \
  --cli-binary-format raw-in-base64-out \
  --payload file://infra/aws/lambda/sample_event.json \
  /tmp/credit-risk-response.json

jq . /tmp/credit-risk-response.json

aws logs tail \
  /aws/lambda/credit-risk-inference \
  --since 5m \
  --region eu-west-2 \
  --format short
```

After the first invocation creates the log group, retain its logs for seven
days rather than indefinitely:

```bash
aws logs put-retention-policy \
  --log-group-name /aws/lambda/credit-risk-inference \
  --retention-in-days 7 \
  --region eu-west-2
```

These are single invocations from 2026-08-10, not a latency benchmark:

| Invocation | `INIT_REPORT` | `REPORT` duration | Billed | Max memory |
|---|---:|---:|---:|---:|
| First cold attempt | 9,999.74 ms, timed out | 8,530.94 ms | 8,531 ms | 282 MB |
| Later cold start | 4,230.06 ms | 41.92 ms | 4,272 ms | 283 MB |
| Immediate warm reuse | — | 15.38 ms | 16 ms | 283 MB |

The first initialization exceeded Lambda's on-demand initialization window and
was retried during the invocation. Its 8.53-second `REPORT` duration includes
the suppressed retry initialization, so it is not handler latency. The
`joblib` serial-mode warning is benign for single-record inference; the handler
still returned the expected result.

## Engineering conclusion

Warm inference is fast and the serverless cost is very low for sporadic work,
but the measured multi-second and variable cold start makes this image a poor
latency-sensitive HTTP endpoint without further optimization or provisioned
concurrency. FastAPI remains the cleaner continuously available API; Lambda is a
credible option for asynchronous or event-driven scoring where startup latency
is acceptable. The observed 283 MB maximum does not by itself justify reducing
the 2 GB allocation because Lambda CPU also scales with memory; memory and
latency tuning were not performed here.
