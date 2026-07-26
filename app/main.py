# Step 4 — the online endpoint. One route: send one loan, get its default probability and the
# approve/reject decision back. A minimal FastAPI app, not a full service.
#
# Two ideas carry it:
#   - The model is loaded once (serving.load_model is cached), never per request.
#   - The request body is validated at the boundary by a pydantic model. That schema IS the API's
#     data contract: anything that does not fit is rejected with a 422 before it ever reaches the
#     model. Validation at the edge is what keeps garbage out of a served model.

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd

from credit_risk.serving import score, load_model
from credit_risk.evaluate import breakeven_probability

# The seven categorical fields. Every other feature is numeric, which is how we coerce a payload
# back to float below.
CATEGORICAL = (
    "home_ownership", "purpose", "addr_state", "verification_status",
    "application_type", "emp_length", "grade",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the model at startup, not on the first request: the app fails fast if the artifact is
    # missing, and no single request pays the one-off load cost.
    load_model()
    yield


app = FastAPI(title="Credit risk scoring", lifespan=lifespan)


class Loan(BaseModel):
    # The request schema, and the API's data contract: FastAPI rejects anything that does not fit
    # with a 422 before it reaches the model.
    #
    # Borrower numerics are optional. Some are missing by nature, mths_since_last_delinq is undefined
    # for a borrower who was never delinquent, and the pipeline imputes any that are absent, so a
    # caller sends what it has. int_rate stays required: it is Lending Club's price, always set, and
    # the approve decision needs it. Categoricals are required too, because the encoder needs a known
    # category; handling unseen ones is a later refinement.
    loan_amnt: Optional[float] = None
    annual_inc: Optional[float] = None
    dti: Optional[float] = None
    fico_range_low: Optional[float] = None
    inq_last_6mths: Optional[float] = None
    open_acc: Optional[float] = None
    pub_rec: Optional[float] = None
    revol_bal: Optional[float] = None
    revol_util: Optional[float] = None
    total_acc: Optional[float] = None
    delinq_2yrs: Optional[float] = None
    pub_rec_bankruptcies: Optional[float] = None
    credit_history_months: Optional[float] = None
    loan_to_income: Optional[float] = None
    active_acct_ratio: Optional[float] = None
    collections_12_mths_ex_med: Optional[float] = None
    tax_liens: Optional[float] = None
    delinq_amnt: Optional[float] = None
    acc_now_delinq: Optional[float] = None
    chargeoff_within_12_mths: Optional[float] = None
    mths_since_last_delinq: Optional[float] = None
    int_rate: float

    home_ownership: str
    purpose: str
    addr_state: str
    verification_status: str
    application_type: str
    emp_length: str
    grade: str

    # A real loan, so the /docs "Try it out" form is filled in and testable straight away.
    model_config = {
        "json_schema_extra": {
            "example": {
                "loan_amnt": 5000.0, "annual_inc": 62000.0, "dti": 10.28, "fico_range_low": 660.0,
                "inq_last_6mths": 3.0, "open_acc": 11.0, "pub_rec": 1.0, "revol_bal": 7837.0,
                "revol_util": 31.2, "total_acc": 32.0, "delinq_2yrs": 0.0, "pub_rec_bankruptcies": 1.0,
                "credit_history_months": 269.0, "loan_to_income": 0.081, "active_acct_ratio": 0.344,
                "collections_12_mths_ex_med": 0.0, "tax_liens": 0.0, "delinq_amnt": 0.0,
                "acc_now_delinq": 0.0, "chargeoff_within_12_mths": 0.0, "mths_since_last_delinq": None,
                "int_rate": 17.27, "home_ownership": "RENT", "purpose": "credit_card",
                "addr_state": "WI", "verification_status": "Source Verified",
                "application_type": "Individual", "emp_length": "10+ years", "grade": "D",
            }
        }
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/score")
def score_loan(loan: Loan):
    df = pd.DataFrame([loan.model_dump()])

    # A missing numeric arrives as None, which makes its column object dtype and LightGBM rejects
    # it. Coerce the numerics to float so None becomes NaN and the pipeline's imputer handles it.
    num = [c for c in df.columns if c not in CATEGORICAL]
    df[num] = df[num].astype(float)

    proba = float(score(df).iloc[0])
    approve = bool(proba < breakeven_probability(loan.int_rate))

    return {"default_probability": proba, "approve": approve}
