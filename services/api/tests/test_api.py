import os
import pytest
from fastapi.testclient import TestClient

from app import ml_client
from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    monkeypatch.setattr(ml_client, "risk", lambda p, w: {"annual_volatility": 0.2, "symbols": list(w)})
    monkeypatch.setattr(ml_client, "forecast", lambda p, h: {"forecast": [p[-1]] * h})
    with TestClient(app) as c:
        yield c
    os.path.exists("test.db") and None


def mk(c):
    return c.post("/portfolios", json={"name": "Main"}).json()["id"]


def tx(c, pid, **kw):
    body = {"symbol": "aapl", "side": "buy", "quantity": 10, "price": 100, "trade_date": "2026-01-02", **kw}
    return c.post(f"/portfolios/{pid}/transactions", json=body)


def test_crud_and_summary(client):
    pid = mk(client)
    assert tx(client, pid).status_code == 201
    assert tx(client, pid, symbol="msft", quantity=5, price=200).status_code == 201
    s = client.get(f"/portfolios/{pid}/summary").json()
    assert {h["symbol"] for h in s["holdings"]} == {"AAPL", "MSFT"}
    assert abs(sum(h["weight"] for h in s["holdings"]) - 1) < 1e-3
    assert s["totals"]["cost_basis"] == 2000


def test_realized_pnl_avg_cost(client):
    pid = mk(client)
    tx(client, pid, quantity=10, price=100)
    tx(client, pid, quantity=10, price=200, trade_date="2026-01-03")
    tx(client, pid, side="sell", quantity=10, price=180, trade_date="2026-01-04")  # avg 150 -> +300
    assert client.get(f"/portfolios/{pid}/summary").json()["totals"]["realized_pnl"] == 300


def test_oversell_rejected(client):
    pid = mk(client)
    tx(client, pid, quantity=5)
    assert tx(client, pid, side="sell", quantity=6, trade_date="2026-01-05").status_code == 422


def test_insights(client):
    pid = mk(client)
    tx(client, pid)
    j = client.get(f"/portfolios/{pid}/insights?horizon=3").json()
    assert "AAPL" in j["forecasts"] and len(j["forecasts"]["AAPL"]["forecast"]) == 3


def test_404_and_validation(client):
    assert client.get("/portfolios/999/summary").status_code == 404
    pid = mk(client)
    assert tx(client, pid, quantity=-1).status_code == 422
