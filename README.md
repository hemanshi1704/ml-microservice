# Portfolio Tracker + ML Microservice

Track holdings and P&L, with a separate ML service that provides price forecasts and portfolio risk analytics.

```
 browser ──► web (nginx, static dashboard) ──/api──► api (FastAPI) ──► Postgres
                                                       │
                                                       └──HTTP──► ml (FastAPI + scikit-learn)
```

| Service | Port | Responsibility |
|---|---|---|
| `web` | 8080 | Dashboard (Chart.js), reverse-proxies `/api/*` to the API |
| `api` | 8000 | Portfolios, transactions, average-cost P&L, price providers, orchestrates ML calls |
| `ml`  | 8001 | `/forecast` (Ridge on lagged returns, 95% bands) and `/risk` (vol, Sharpe, VaR/CVaR, drawdown, correlation) |
| `db`  | 5432 | Postgres (SQLite when running locally without Docker) |

## Run it (Docker)
```bash
cp .env.example .env
docker compose up --build        # → http://localhost:8080
```
Swagger docs: the API and ML services expose `/docs` on their own ports (add `ports:` to compose to reach them).

## Run it (no Docker)
```bash
pip install -r services/ml/requirements.txt -r services/api/requirements.txt
make dev-ml     # terminal 1
make dev-api    # terminal 2
open web/index.html   # set window.API_BASE="http://localhost:8000" in the console, or serve via nginx
make test
```

## API
- `POST /portfolios`, `GET /portfolios`, `DELETE /portfolios/{id}`
- `POST|GET /portfolios/{id}/transactions` (oversells rejected with 422)
- `GET /portfolios/{id}/summary` holdings, weights, unrealized/realized P&L
- `GET /portfolios/{id}/insights?horizon=5` ML forecasts per holding + portfolio risk
- `GET /prices/{symbol}`, `GET /health`

## Deploy the dashboard to GitHub Pages
1. Deploy the API + ML + DB (Render blueprint above) and note the API's public HTTPS URL.
2. Set `CORS_ORIGINS` on the API to `https://<user>.github.io`.
3. In the GitHub repo: Settings → Pages → Source: **GitHub Actions**; Settings → Secrets and variables → Actions → Variables → add `API_URL` = your API URL.
4. Push to `main` (or run the *deploy-dashboard* workflow). The workflow writes `web/config.js` and publishes `web/`.

The forecast chart supports zoom (mouse wheel / pinch / +, − buttons), drag-to-pan, and reset (button or double-click).

## Config (env vars)
`DATABASE_URL`, `ML_URL`, `PRICE_PROVIDER` (`synthetic` default, deterministic and offline; `yfinance` for live data), `API_KEY` (optional `X-API-Key` auth), `CORS_ORIGINS`.

## Deploy
- **Any VPS:** install Docker, copy repo + `.env`, `docker compose up -d`, put Caddy/Traefik in front for HTTPS.
- **Render:** `render.yaml` is a blueprint for the API, ML and DB (host `web/` as a static site with `/api` rewritten to the API URL, and set `window.API_BASE`).
- **CI/CD:** `.github/workflows/ci.yml` runs tests for both services and pushes images to GHCR from `main`.

## Honest notes on the ML
Daily returns are close to unpredictable. The forecaster is deliberately heavily regularised, and the dashboard shows its **hold-out directional accuracy** (typically ~50%) beside each forecast. Treat the forecast as a demonstration of the service architecture, not trading advice. Swap `model.forecast` for your own model without touching the API.

## Next steps
User auth (JWT), Alembic migrations, scheduled price snapshots for portfolio value history, model versioning/registry.
