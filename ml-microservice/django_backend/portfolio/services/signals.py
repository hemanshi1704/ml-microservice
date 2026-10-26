"""Signal engines: in-process rolling mean, ML service, and automatic fallback."""
from .ml_client import MLServiceError, get_ml_signal


def rolling_mean_signal(prices, window=20):
    """BUY when the latest close is above the rolling mean of the last `window` closes, else HOLD."""
    closes = [float(p["close"]) for p in prices]
    if len(closes) < window:
        raise ValueError(f"Need at least {window} prices, got {len(closes)}")
    mean = sum(closes[-window:]) / window
    last = closes[-1]
    return {
        "signal": "BUY" if last > mean else "HOLD",
        "last_close": round(last, 4),
        "rolling_mean": round(mean, 4),
        "window": window,
    }


def generate_signal(engine, ticker, prices, ml_fn=get_ml_signal, window=20):
    """
    engine="ml": ask the Flask service; if it is down, slow or returns garbage,
    fall back to the rolling-mean engine so the endpoint keeps working.
    engine="simple": rolling mean only.
    """
    if engine == "ml":
        try:
            result = ml_fn(ticker, prices)
            return {"engine_used": "ml", "fallback": False, **result}
        except MLServiceError as exc:
            result = rolling_mean_signal(prices, window)
            return {"engine_used": "simple", "fallback": True,
                    "fallback_reason": str(exc), **result}

    result = rolling_mean_signal(prices, window)
    return {"engine_used": "simple", "fallback": False, **result}
