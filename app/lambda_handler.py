from credit_risk.schema import Loan
from credit_risk.serving import load_model, score_one

load_model()


def handler(
    event: dict[str, object],
    _context: object,
) -> dict[str, float | bool]:
    return score_one(Loan.model_validate(event))
