# Shared fixtures for the test suite.

import pytest

from app.main import Loan


@pytest.fixture
def valid_payload() -> dict:
    # A complete, valid /score body. We reuse the example baked into the request schema, so the
    # tests and the API documentation stay in step: one source for "what a good request looks like".
    return dict(Loan.model_config["json_schema_extra"]["example"])
