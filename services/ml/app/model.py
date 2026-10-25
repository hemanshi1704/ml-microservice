"""Forecasting + risk analytics. Pure functions, no I/O, easy to test."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import Ridge

TRADING_DAYS = 252
LAGS = 5


def log_returns(prices: list[float]) -> np.ndarray:
    p = np.asarray(prices, dtype=float)
    if np.any(p <= 0):
        raise ValueError("prices must be positive")
    return np.diff(np.log(p))


def _features(r: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Lagged returns + rolling vol/momentum -> next-day return."""
    X, y = [], []
    for t in range(20, len(r)):
        lags = r[t - LAGS:t]
        X.append(np.concatenate([lags, [r[t - 20:t].std(), r[t - 10:t].mean()]]))
        y.append(r[t])
    return np.asarray(X), np.asarray(y)


def forecast(prices: list[float], horizon: int = 5) -> dict:
    """Ridge on lagged returns, iterated `horizon` days ahead.

    Daily returns are close to unpredictable, so the model is shrunk hard and
    the confidence band comes from out-of-sample residual std, not in-sample.
    """
    r = log_returns(prices)
    if len(r) < 60:
        raise ValueError("need at least 61 prices")
    X, y = _features(r)
    split = int(len(X) * 0.8)
    model = Ridge(alpha=10.0).fit(X[:split], y[:split])
    resid = y[split:] - model.predict(X[split:])
    sigma = float(resid.std()) or float(r.std())
    # directional accuracy on hold-out (honest signal-quality metric)
    hit = float(np.mean(np.sign(model.predict(X[split:])) == np.sign(y[split:])))
    model = Ridge(alpha=10.0).fit(X, y)

    hist = list(r)
    last = float(prices[-1])
    path, lo, hi = [], [], []
    price = last
    for h in range(1, horizon + 1):
        t = len(hist)
        x = np.concatenate([hist[t - LAGS:t], [np.std(hist[t - 20:t]), np.mean(hist[t - 10:t])]])
        nr = float(model.predict(x.reshape(1, -1))[0])
        hist.append(nr)
        price *= float(np.exp(nr))
        band = 1.96 * sigma * np.sqrt(h)
        path.append(round(price, 4))
        lo.append(round(last * float(np.exp(np.log(price / last) - band)), 4))
        hi.append(round(last * float(np.exp(np.log(price / last) + band)), 4))
    return {
        "horizon": horizon,
        "last_price": last,
        "forecast": path,
        "lower_95": lo,
        "upper_95": hi,
        "expected_return_pct": round((path[-1] / last - 1) * 100, 3),
        "holdout_directional_accuracy": round(hit, 3),
        "model": "ridge-lagged-returns-v1",
    }


def max_drawdown(series: np.ndarray) -> float:
    peak = np.maximum.accumulate(series)
    return float(((series - peak) / peak).min())


def risk(prices: dict[str, list[float]], weights: dict[str, float], rf: float = 0.04) -> dict:
    syms = [s for s in weights if s in prices and weights[s] > 0]
    if not syms:
        raise ValueError("no overlapping symbols")
    n = min(len(prices[s]) for s in syms)
    if n < 30:
        raise ValueError("need at least 30 prices per symbol")
    R = np.column_stack([log_returns(prices[s][-n:]) for s in syms])
    w = np.array([weights[s] for s in syms], dtype=float)
    w = w / w.sum()
    port = R @ w
    ann_ret = float(port.mean() * TRADING_DAYS)
    ann_vol = float(port.std(ddof=1) * np.sqrt(TRADING_DAYS))
    var95 = float(-np.percentile(port, 5))
    tail = port[port <= np.percentile(port, 5)]
    cvar95 = float(-tail.mean()) if len(tail) else var95
    equity = np.exp(np.cumsum(port))
    corr = np.corrcoef(R, rowvar=False) if len(syms) > 1 else np.array([[1.0]])
    return {
        "symbols": syms,
        "weights": [round(float(x), 4) for x in w],
        "annual_return": round(ann_ret, 4),
        "annual_volatility": round(ann_vol, 4),
        "sharpe": round((ann_ret - rf) / ann_vol, 3) if ann_vol else 0.0,
        "var_95_1d": round(var95, 4),
        "cvar_95_1d": round(cvar95, 4),
        "max_drawdown": round(max_drawdown(equity), 4),
        "correlation": np.round(corr, 3).tolist(),
    }
