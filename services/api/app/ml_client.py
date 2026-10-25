import httpx
from fastapi import HTTPException

from . import config


def _post(path: str, payload: dict) -> dict:
    try:
        r = httpx.post(f"{config.ML_URL}{path}", json=payload, timeout=20)
    except httpx.HTTPError as e:
        raise HTTPException(503, f"ML service unavailable: {e.__class__.__name__}")
    if r.status_code != 200:
        raise HTTPException(502, f"ML service error: {r.text}")
    return r.json()


def forecast(prices: list[float], horizon: int) -> dict:
    return _post("/forecast", {"prices": prices, "horizon": horizon})


def risk(prices: dict[str, list[float]], weights: dict[str, float]) -> dict:
    return _post("/risk", {"prices": prices, "weights": weights})
