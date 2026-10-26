# Portfolio Tracker + ML Signal Microservice

A two-service backend:

- **Django REST API** (`django_backend/`): portfolios, transactions, live prices from Yahoo Finance, FIFO profit and loss, and a `whatif` endpoint that returns buy/hold signals.
- **Flask ML microservice** (`ml_service/`): a stateless service that trains a logistic-regression classifier on price features and returns a signal plus accuracy/precision metrics.

Django calls Flask over HTTP. If the ML service is down, slow or returns a bad response, Django **automatically falls back** to a rolling-mean signal, so the endpoint keeps working.

## Architecture

```
Django REST API (:8000)  --POST /predict/signal-->  Flask ML service (:5001)
  - Portfolios, transactions                          - Feature engineering
  - Yahoo Finance price sync (cached in SQLite)       - Chronological 75/25 train/test split
  - FIFO holdings and P&L                             - Logistic regression + baseline
  - /whatif/ with automatic fallback  <-- signal + metrics --
```

## Repository structure

```
.
├── docker-compose.yml
├── django_backend/
│   ├── Dockerfile, requirements.txt, manage.py
│   ├── config/            # settings, urls
│   └── portfolio/
│       ├── models.py      # Portfolio, Transaction, PriceCache
│       ├── views.py       # REST endpoints
│       ├── serializers.py # validation (e.g. no overselling)
│       ├── services/      # analytics (FIFO), prices, ml_client, signals
│       └── tests/
└── ml_service/            # Flask app: app.py, model.py, feature_engineering.py, Dockerfile
```

## Run with Docker Compose

```
docker compose up --build
```

- Django API: http://localhost:8000/api/
- Django admin: http://localhost:8000/admin/
- Flask health check: http://localhost:5001/health

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/api/portfolios/` | List / create portfolios |
| GET/POST | `/api/transactions/` | List / record buys and sells (overselling is rejected) |
| GET | `/api/portfolios/{id}/holdings/` | FIFO positions, average cost, realized and unrealized P&L |
| POST | `/api/portfolios/{id}/refresh_prices/` | Pull daily closes from Yahoo Finance into the cache |
| GET | `/api/portfolios/{id}/whatif/?engine=simple\|ml&ticker=AAPL` | Buy/hold signal per ticker |

### Example

```
curl -X POST localhost:8000/api/portfolios/ -H "Content-Type: application/json" \
  -d '{"name": "Demo", "owner_email": "me@example.com"}'

curl -X POST localhost:8000/api/transactions/ -H "Content-Type: application/json" \
  -d '{"portfolio": 1, "ticker": "AAPL", "transaction_type": "BUY", "quantity": 10, "price_per_unit": 180.50, "executed_at": "2025-06-01T14:30:00Z"}'

curl -X POST localhost:8000/api/portfolios/1/refresh_prices/
curl "localhost:8000/api/portfolios/1/whatif/?engine=ml"
```

If the ML service is unreachable, the `engine=ml` response still succeeds and reports it:

```
{"engine_used": "simple", "fallback": true, "fallback_reason": "ML service is unreachable", "signal": "BUY", ...}
```

## ML approach

- **Chronological split:** the first 75% of a ticker's history trains the model and the last 25% tests it. Data is never shuffled, so there is no look-ahead bias.
- **Model:** logistic-regression classifier on multi-horizon momentum and volatility features.
- **Baseline:** compared against an "always up" classifier.
- **Results ([TICKER], [DATE RANGE]):** accuracy [X]% vs baseline [Y]%, precision [Z]%.

## Tests

```
cd django_backend
pip install -r requirements.txt
python manage.py test
```

Covers FIFO P&L, overselling rejection, both signal engines, ML client error handling, and the automatic fallback.

## Notes

- The Flask service is stateless: it trains on demand from the price history Django sends.
- The rolling-mean signal is BUY when the latest close is above the 20-day mean, otherwise HOLD.
- Prices are cached in SQLite. For production, switch to PostgreSQL and replace `runserver` with gunicorn.
