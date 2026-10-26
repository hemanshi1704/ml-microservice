"""
HTTP client for the Flask ML microservice.

CONTRACT (adjust the two marked spots if your ml_service/app.py differs):
  POST {ML_SERVICE_URL}/predict/signal
  request : {"ticker": "AAPL", "prices": [{"date": "2025-06-01", "close": 180.5}, ...]}   <-- REQUEST SHAPE
  response: {"signal": "BUY" | "HOLD", "metrics": {"accuracy": 0.54, "precision": 0.57, ...}}  <-- RESPONSE SHAPE
"""
import os

import requests


class MLServiceError(Exception):
    """Raised for any failure talking to the ML service (down, slow, bad response)."""


def get_ml_signal(ticker, prices, url=None, timeout=None):
    url = (url or os.environ.get("ML_SERVICE_URL", "http://localhost:5001")).rstrip("/")
    timeout = timeout or float(os.environ.get("ML_SERVICE_TIMEOUT", "10"))

    try:
        resp = requests.post(
            f"{url}/predict/signal",
            json={"ticker": ticker, "prices": prices},          # <-- REQUEST SHAPE
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout as exc:
        raise MLServiceError(f"ML service timed out after {timeout}s") from exc
    except requests.exceptions.ConnectionError as exc:
        raise MLServiceError("ML service is unreachable") from exc
    except requests.exceptions.HTTPError as exc:
        raise MLServiceError(f"ML service returned an error: {exc}") from exc
    except ValueError as exc:
        raise MLServiceError("ML service returned invalid JSON") from exc

    signal = data.get("signal")                                  # <-- RESPONSE SHAPE
    if signal is None and isinstance(data.get("signals"), list) and data["signals"]:
        last = data["signals"][-1]
        signal = last.get("signal") if isinstance(last, dict) else last
    if signal is None:
        raise MLServiceError("ML service response did not contain a signal")

    return {"signal": signal, "metrics": data.get("metrics", {})}
