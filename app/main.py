# Exposes the credit risk model through an API.

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from credit_risk.serving import load_model, score_one
from credit_risk.schema import Loan

# Loads the model when the API starts.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_model()
    yield


app = FastAPI(title="Credit risk scoring", lifespan=lifespan)


# Reports whether the API is running.
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Scores one loan and returns the approval decision.
@app.post("/score")
def score_loan(loan: Loan) -> dict[str, float | bool]:
    return score_one(loan)
