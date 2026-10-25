"""Price providers. `synthetic` is deterministic (seeded by symbol) so the
project runs offline, in CI and in demos; `yfinance` uses live Yahoo data."""
from __future__ import annotations

import hashlib
import time

import numpy as np

from . import config

_cache: dict[str, tuple[float, list[float]]] = {}


def _synthetic(symbol: str, days: int) -> list[float]:
    seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    base = 20 + (seed % 400)
    drift, vol = rng.uniform(-0.0002, 0.0012), rng.uniform(0.008, 0.025)
    return [round(float(x), 4) for x in base * np.exp(np.cumsum(rng.normal(drift, vol, days)))]


def _yf(symbol: str, days: int) -> list[float]:
    import yfinance as yf
    df = yf.Ticker(symbol).history(period=f"{max(days, 90)}d", auto_adjust=True)
    closes = [float(x) for x in df["Close"].dropna().tolist()]
    if len(closes) < 61:
        raise ValueError(f"not enough price history for {symbol}")
    return closes[-days:]


def history(symbol: str, days: int = 250) -> list[float]:
    key = f"{config.PRICE_PROVIDER}:{symbol}:{days}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < config.PRICE_TTL_S:
        return hit[1]
    data = _yf(symbol, days) if config.PRICE_PROVIDER == "yfinance" else _synthetic(symbol, days)
    _cache[key] = (time.time(), data)
    return data


def latest(symbol: str) -> float:
    return history(symbol)[-1]
