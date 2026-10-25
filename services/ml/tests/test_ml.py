import numpy as np
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)


def series(n=200, seed=1, drift=0.0005, vol=0.01):
    rng = np.random.default_rng(seed)
    return list(100 * np.exp(np.cumsum(rng.normal(drift, vol, n))))


def test_health():
    assert c.get("/health").json()["status"] == "ok"


def test_forecast_shape_and_bands():
    r = c.post("/forecast", json={"prices": series(), "horizon": 7})
    assert r.status_code == 200
    j = r.json()
    assert len(j["forecast"]) == 7
    assert all(lo < f < hi for lo, f, hi in zip(j["lower_95"], j["forecast"], j["upper_95"]))


def test_forecast_rejects_short():
    assert c.post("/forecast", json={"prices": series(30)}).status_code == 422


def test_risk():
    r = c.post("/risk", json={"prices": {"A": series(seed=1), "B": series(seed=2)},
                              "weights": {"A": 0.6, "B": 0.4}})
    assert r.status_code == 200
    j = r.json()
    assert j["annual_volatility"] > 0 and -1 < j["max_drawdown"] <= 0
    assert abs(sum(j["weights"]) - 1) < 1e-3
    assert j["correlation"][0][0] == 1.0
