# Provides shared fixtures for the test suite.

from typing import cast

import pytest

from credit_risk.schema import Loan


# Returns a complete request body for the scoring API.
@pytest.fixture
def valid_payload() -> dict[str, object]:
    schema_extra = cast(dict[str, object], Loan.model_config["json_schema_extra"])
    return dict(cast(dict[str, object], schema_extra["example"]))
