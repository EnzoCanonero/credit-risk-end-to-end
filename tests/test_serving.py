import pandas as pd
import pytest

from credit_risk.serving import score, ARTIFACT

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(),
    reason="model artifact missing; run: python scripts/build_model.py",
)


def test_score_shape_and_range(valid_payload):
    df = pd.DataFrame([valid_payload, valid_payload])
    s = score(df)
    assert len(s) == 2
    assert list(s.index) == list(df.index)
    assert ((s >= 0) & (s <= 1)).all()


def test_score_missing_column_raises(valid_payload):
    df = pd.DataFrame([valid_payload]).drop(columns=["int_rate"])
    with pytest.raises(ValueError) as exc:
        score(df)

    assert "int_rate" in str(exc.value)


def test_higher_rate_scores_higher(valid_payload):
    low = {**valid_payload, "int_rate": 6.0}
    high = {**valid_payload, "int_rate": 26.0}
    s = score(pd.DataFrame([low, high]))

    assert s.iloc[1] > s.iloc[0]


def test_score_is_stable(valid_payload):
    s = score(pd.DataFrame([valid_payload]))

    assert s.iloc[0] == pytest.approx(0.163, abs=1e-2)