# Provides shared fixtures for the test suite.

import pytest

from app.main import Loan


# Returns a complete request body for the scoring API.
@pytest.fixture
def valid_payload() -> dict:
    return dict(Loan.model_config["json_schema_extra"]["example"])
