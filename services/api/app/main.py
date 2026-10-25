from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import analytics, config, ml_client, prices
from .db import Base, engine, get_db
from .models import Portfolio, Transaction
from .schemas import PortfolioIn, PortfolioOut, TransactionIn, TransactionOut


@asynccontextmanager
async def lifespan(_):
    Base.metadata.create_all(engine)
    yield


def auth(x_api_key: str = Header(default="")):
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(401, "invalid API key")


app = FastAPI(title="Portfolio Tracker API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    ml = "down"
    try:
        ml = "ok" if httpx.get(f"{config.ML_URL}/health", timeout=2).status_code == 200 else "down"
    except httpx.HTTPError:
        pass
    return {"status": "ok", "service": "api", "ml": ml, "price_provider": config.PRICE_PROVIDER}


def _portfolio(db: Session, pid: int) -> Portfolio:
    p = db.get(Portfolio, pid)
    if not p:
        raise HTTPException(404, "portfolio not found")
    return p


@app.post("/portfolios", response_model=PortfolioOut, status_code=201, dependencies=[Depends(auth)])
def create_portfolio(body: PortfolioIn, db: Session = Depends(get_db)):
    p = Portfolio(name=body.name, currency=body.currency.upper())
    db.add(p); db.commit(); db.refresh(p)
    return p


@app.get("/portfolios", response_model=list[PortfolioOut], dependencies=[Depends(auth)])
def list_portfolios(db: Session = Depends(get_db)):
    return db.query(Portfolio).order_by(Portfolio.id).all()


@app.delete("/portfolios/{pid}", status_code=204, dependencies=[Depends(auth)])
def delete_portfolio(pid: int, db: Session = Depends(get_db)):
    db.delete(_portfolio(db, pid)); db.commit()


@app.post("/portfolios/{pid}/transactions", response_model=TransactionOut, status_code=201, dependencies=[Depends(auth)])
def add_transaction(pid: int, body: TransactionIn, db: Session = Depends(get_db)):
    p = _portfolio(db, pid)
    t = Transaction(portfolio_id=pid, **body.model_dump())
    try:  # validate the ledger stays consistent (no oversell)
        analytics.positions([*p.transactions, t])
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.add(t); db.commit(); db.refresh(t)
    return t


@app.get("/portfolios/{pid}/transactions", response_model=list[TransactionOut], dependencies=[Depends(auth)])
def list_transactions(pid: int, db: Session = Depends(get_db)):
    return sorted(_portfolio(db, pid).transactions, key=lambda t: (t.trade_date, t.id))


@app.get("/portfolios/{pid}/summary", dependencies=[Depends(auth)])
def summary(pid: int, db: Session = Depends(get_db)):
    return analytics.summary(_portfolio(db, pid).transactions)


@app.get("/prices/{symbol}", dependencies=[Depends(auth)])
def price_history(symbol: str, days: int = 120):
    try:
        h = prices.history(symbol.upper(), max(61, min(days, 750)))
    except Exception as e:
        raise HTTPException(404, f"no price data for {symbol}: {e}")
    return {"symbol": symbol.upper(), "prices": h}


@app.get("/portfolios/{pid}/insights", dependencies=[Depends(auth)])
def insights(pid: int, horizon: int = 5, db: Session = Depends(get_db)):
    """ML-backed: per-holding forecast + portfolio risk metrics."""
    s = analytics.summary(_portfolio(db, pid).transactions)
    if not s["holdings"]:
        raise HTTPException(422, "portfolio has no holdings")
    hist = {h["symbol"]: prices.history(h["symbol"], 250) for h in s["holdings"]}
    weights = {h["symbol"]: h["weight"] for h in s["holdings"]}
    return {
        "risk": ml_client.risk(hist, weights),
        "forecasts": {sym: ml_client.forecast(px, horizon) for sym, px in hist.items()},
    }
