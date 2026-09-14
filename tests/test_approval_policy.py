# Checks the shared approval rule without a trained model artifact.

import math
import runpy
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main as api
from credit_risk import serving
from scripts import score_batch


def test_approval_threshold_is_strict_and_preserves_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    threshold = 0.310123456789
    monkeypatch.setattr(serving, "_metadata", lambda: {
        "approval_policy": {"threshold": threshold},
    })
    probabilities = pd.Series(
        [math.nextafter(threshold, 0), threshold, math.nextafter(threshold, 1)],
        index=[7, 2, 9],
    )

    pd.testing.assert_series_equal(
        serving.approval_decisions(probabilities),
        pd.Series([True, False, False], index=probabilities.index),
    )


def test_missing_policy_explains_how_to_update_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(serving, "_metadata", lambda: {"features": []})
    with pytest.raises(ValueError, match="python scripts/build_model.py --policy-only"):
        serving.approval_decisions(pd.Series([0.2]))


@pytest.mark.parametrize("probability, approved", [(0.30, True), (0.31, False), (0.32, False)])
def test_api_lambda_and_batch_share_the_fixed_threshold(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    valid_payload: dict[str, object],
    probability: float,
    approved: bool,
) -> None:
    def fake_score(loans: pd.DataFrame) -> pd.Series:
        return pd.Series(probability, index=loans.index)

    monkeypatch.setattr(serving, "_metadata", lambda: {
        "approval_policy": {"threshold": 0.31},
    })
    monkeypatch.setattr(serving, "score", fake_score)
    monkeypatch.setattr(serving, "load_model", lambda: None)
    monkeypatch.setattr(api, "load_model", lambda: None)
    monkeypatch.setattr(score_batch, "score", fake_score)
    # A temporary module namespace keeps the mocked Lambda startup out of later tests.
    handler = runpy.run_path(str(Path(api.__file__).with_name("lambda_handler.py")))["handler"]
    loans = [{**valid_payload, "int_rate": rate} for rate in (6.0, 26.0)]
    expected = {"default_probability": probability, "approve": approved}

    with TestClient(api.app) as client:
        for loan in loans:
            response = client.post("/score", json=loan)
            assert response.status_code == 200
            assert response.json() == handler(loan, None) == expected

    source, output = tmp_path / "loans.csv", tmp_path / "scores.csv"
    pd.DataFrame([dict(loan, id=i) for i, loan in enumerate(loans)]).to_csv(source, index=False)
    monkeypatch.setattr(sys, "argv", ["score_batch.py", str(source), str(output)])
    score_batch.main()
    results = pd.read_csv(output)
    assert results["id"].tolist() == [0, 1]
    assert results["proba"].tolist() == [probability, probability]
    assert results["approve"].tolist() == [approved, approved]
