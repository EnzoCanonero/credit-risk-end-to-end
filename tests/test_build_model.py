# Checks that model builds and policy-only updates use development data for the rule.

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from credit_risk.evaluate import breakeven_probability
from scripts import build_model


@pytest.mark.parametrize("policy_only", [True, False])
def test_build_stores_the_development_threshold(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    policy_only: bool,
) -> None:
    # The chronological split puts rows 0:3 in training, 3:5 in validation and 5:8 in test.
    loans = pd.DataFrame({
        "issue_month": pd.date_range("2014-01-01", periods=8, freq="MS"),
        "int_rate": [5, 10, 15, 20, 25, 90, 90, 90],
        "loan_amnt": [100, 100, 100, 100, 600, 10000, 10000, 10000],
        "target_bad": [0, 1, 0, 1, 0, 1, 0, 1],
    })
    artifact, metadata = tmp_path / "model.joblib", tmp_path / "model_meta.json"
    artifact.write_bytes(b"existing model")
    original_meta = {"features": ["int_rate"], "params": {"n_estimators": 10}, "n_fit_rows": 8}
    metadata.write_text(json.dumps(original_meta))
    params = tmp_path / "params.json"
    params.write_text(json.dumps(original_meta["params"]))

    model = Mock()
    build = Mock(return_value=model)
    dump = Mock()
    monkeypatch.setattr(build_model, "MODELS", tmp_path)
    monkeypatch.setattr(build_model, "ARTIFACT", artifact)
    monkeypatch.setattr(build_model, "METADATA", metadata)
    monkeypatch.setattr(build_model, "PARAMS", params)
    monkeypatch.setattr(build_model, "COLS", ["int_rate", "loan_amnt"])
    monkeypatch.setattr(build_model, "load_loans", lambda: loans)
    monkeypatch.setattr(build_model, "build_lgbm", build)
    monkeypatch.setattr(build_model.joblib, "dump", dump)
    monkeypatch.setattr(sys, "argv", ["build_model.py"] + (["--policy-only"] if policy_only else []))

    build_model.main()
    saved = json.loads(metadata.read_text())
    assert saved.pop("approval_policy") == {
        "name": "single_break_even",
        "threshold": pytest.approx(float(breakeven_probability(20.0))),
        "reference": "train+val",
        "amount_weighted_int_rate": 20.0,
        "n_reference_rows": 5,
    }
    if policy_only:
        build.assert_not_called()
        dump.assert_not_called()
        assert artifact.read_bytes() == b"existing model"
        assert saved == original_meta
    else:
        build.assert_called_once()
        dump.assert_called_once_with(model, artifact)
        pd.testing.assert_frame_equal(model.fit.call_args.args[0], loans[["int_rate", "loan_amnt"]])
        pd.testing.assert_series_equal(model.fit.call_args.args[1], loans["target_bad"])
        assert saved["n_fit_rows"] == 8
