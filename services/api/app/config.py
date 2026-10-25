import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portfolio.db")
ML_URL = os.getenv("ML_URL", "http://localhost:8001")
PRICE_PROVIDER = os.getenv("PRICE_PROVIDER", "synthetic")  # synthetic | yfinance
API_KEY = os.getenv("API_KEY", "")  # if set, required in X-API-Key header
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
PRICE_TTL_S = int(os.getenv("PRICE_TTL_S", "300"))
