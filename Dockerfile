# Builds the container used to serve the scoring API.
FROM python:3.11-slim

LABEL org.opencontainers.image.description="FastAPI service scoring 36-month Lending Club loans for default risk" \
LABEL org.opencontainers.image.source="https://github.com/EnzoCanonero/credit-risk-end-to-end"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install -e .

COPY app/ ./app/
COPY models/ ./models/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
