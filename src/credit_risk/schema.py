from pydantic import BaseModel, ConfigDict


class Loan(BaseModel):
    loan_amnt: float | None = None
    annual_inc: float | None = None
    dti: float | None = None
    fico_range_low: float | None = None
    inq_last_6mths: float | None = None
    open_acc: float | None = None
    pub_rec: float | None = None
    revol_bal: float | None = None
    revol_util: float | None = None
    total_acc: float | None = None
    delinq_2yrs: float | None = None
    pub_rec_bankruptcies: float | None = None
    credit_history_months: float | None = None
    loan_to_income: float | None = None
    active_acct_ratio: float | None = None
    collections_12_mths_ex_med: float | None = None
    tax_liens: float | None = None
    delinq_amnt: float | None = None
    acc_now_delinq: float | None = None
    chargeoff_within_12_mths: float | None = None
    mths_since_last_delinq: float | None = None
    int_rate: float

    home_ownership: str
    purpose: str
    addr_state: str
    verification_status: str
    application_type: str
    emp_length: str
    grade: str

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "loan_amnt": 5000.0,
                "annual_inc": 62000.0,
                "dti": 10.28,
                "fico_range_low": 660.0,
                "inq_last_6mths": 3.0,
                "open_acc": 11.0,
                "pub_rec": 1.0,
                "revol_bal": 7837.0,
                "revol_util": 31.2,
                "total_acc": 32.0,
                "delinq_2yrs": 0.0,
                "pub_rec_bankruptcies": 1.0,
                "credit_history_months": 269.0,
                "loan_to_income": 0.081,
                "active_acct_ratio": 0.344,
                "collections_12_mths_ex_med": 0.0,
                "tax_liens": 0.0,
                "delinq_amnt": 0.0,
                "acc_now_delinq": 0.0,
                "chargeoff_within_12_mths": 0.0,
                "mths_since_last_delinq": None,
                "int_rate": 17.27,
                "home_ownership": "RENT",
                "purpose": "credit_card",
                "addr_state": "WI",
                "verification_status": "Source Verified",
                "application_type": "Individual",
                "emp_length": "10+ years",
                "grade": "D",
            }
        },
    )
