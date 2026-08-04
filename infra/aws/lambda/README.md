# Lambda scoring

The function receives one loan as a JSON object and returns the same scoring result as the
FastAPI `/score` endpoint.

The input contract is `credit_risk.schema.Loan`. `int_rate` and the seven categorical fields are
required. The other numeric fields may be omitted or set to `null`; the model pipeline imputes
them. Unknown fields are rejected.

```json
{
  "default_probability": 0.162597449579,
  "approve": true
}
```

This is the reference result for `sample_event.json` and the current model artifact. The exact
probability is not part of the API contract and may change when the model is rebuilt. The approval
threshold is computed from `int_rate` and is not part of the response. Invalid events fail the
Lambda invocation.
