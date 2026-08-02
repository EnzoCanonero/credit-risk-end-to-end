# Checks the health and scoring API endpoints.

import pytest
from fastapi.testclient import TestClient

from credit_risk.serving import ARTIFACT
from app.main import app

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(),
    reason="model artifact missing; run: python scripts/build_model.py",
)


# Checks that the health endpoint reports a healthy service.
def test_health():
    with TestClient(app) as client:
        r = client.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# Checks that a valid loan receives a probability and decision.
def test_score_ok(valid_payload):
    with TestClient(app) as client:
        r = client.post("/score", json=valid_payload)
    assert r.status_code == 200

    body = r.json()
    assert 0.0 <= body["default_probability"] <= 1.0
    assert isinstance(body["approve"], bool)


# Checks that the scoring endpoint rejects an incomplete loan.
def test_score_rejects_incomplete(valid_payload):
    bad = {k: v for k, v in valid_payload.items() if k != "int_rate"}
    with TestClient(app) as client:
        r = client.post("/score", json=bad)
    assert r.status_code == 422
