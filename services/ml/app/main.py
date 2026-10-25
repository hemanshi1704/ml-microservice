import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import model

app = FastAPI(title="Portfolio ML Service", version="1.0.0")
START = time.time()


class ForecastIn(BaseModel):
    prices: list[float] = Field(min_length=61)
    horizon: int = Field(5, ge=1, le=30)


class RiskIn(BaseModel):
    prices: dict[str, list[float]]
    weights: dict[str, float]
    risk_free_rate: float = 0.04


@app.get("/health")
def health():
    return {"status": "ok", "service": "ml", "uptime_s": round(time.time() - START, 1)}


@app.post("/forecast")
def forecast(body: ForecastIn):
    try:
        return model.forecast(body.prices, body.horizon)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/risk")
def risk(body: RiskIn):
    try:
        return model.risk(body.prices, body.weights, body.risk_free_rate)
    except ValueError as e:
        raise HTTPException(422, str(e))
