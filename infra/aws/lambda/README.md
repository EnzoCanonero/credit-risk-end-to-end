# Lambda scoring

The function receives one loan as a JSON object and returns the same scoring result as the
FastAPI `/score` endpoint.

The input contract is `credit_risk.schema.Loan`. `int_rate` and the seven categorical fields are
required. The other numeric fields may be omitted or set to `null`; the model pipeline imputes
them. Unknown fields are rejected.

```json
{
  "default_probability": 0.15805194933645042,
  "approve": true
}
```

This is the reference result for `sample_event.json` and the current model artifact. The exact
probability is not part of the API contract and may change when the model is rebuilt. The approval
threshold is computed from `int_rate` and is not part of the response. Invalid events fail the
Lambda invocation.

## Deployment

The image is built for `x86_64`, stored in the `credit-risk-lambda` ECR repository, and run by a
2 GB Lambda with a 30-second timeout. The execution role trusts Lambda through
`trust-policy.json` and has the AWS-managed `AWSLambdaBasicExecutionRole` policy for logs only.
The one-time setup uses an immutable, scan-on-push ECR repository and the
`credit-risk-lambda-execution-role`.

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com/credit-risk-lambda"

docker buildx build --platform linux/amd64 --provenance=false \
  --file Dockerfile.lambda --tag credit-risk-lambda:local --load .
aws ecr get-login-password --region eu-west-2 \
  | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com"
docker tag credit-risk-lambda:local "$ECR_URI:v1"
docker push "$ECR_URI:v1"
aws lambda create-function --function-name credit-risk-inference --package-type Image \
  --code ImageUri="$ECR_URI:v1" \
  --role "arn:aws:iam::$AWS_ACCOUNT_ID:role/credit-risk-lambda-execution-role" \
  --architectures x86_64 --memory-size 2048 --timeout 30 --region eu-west-2 \
  --tags Project=credit-risk
aws lambda wait function-active-v2 --function-name credit-risk-inference --region eu-west-2

aws lambda invoke --function-name credit-risk-inference --region eu-west-2 \
  --cli-binary-format raw-in-base64-out \
  --payload file://infra/aws/lambda/sample_event.json \
  /tmp/credit-risk-response.json
```

The function uses image tag `v1`; Lambda resolved it to digest
`sha256:f7227f3aae98a8f67aac71b21639f559b3a3f80cb41498b12bb4c81b3c43bb8e`.

## Recorded run

These are single-invocation measurements from 2026-08-10, not a latency benchmark.

| Invocation | Init | Duration | Billed | Max memory |
|---|---:|---:|---:|---:|
| First cold attempt | 9,999.74 ms, timed out | 8,530.94 ms | 8,531 ms | 282 MB |
| Later cold start | 4,230.06 ms | 41.92 ms | 4,272 ms | 283 MB |
| Immediate warm reuse | — | 15.38 ms | 16 ms | 283 MB |

The first initialization exceeded Lambda's 10-second on-demand init window and was retried during
the invocation. Warm inference is fast, but cold-start variability makes this container a poor fit
for a latency-sensitive synchronous API without further optimization or provisioned capacity.
FastAPI remains the better comparison for a continuously available service; Lambda fits sporadic
or event-driven scoring where cold-start latency is acceptable.
