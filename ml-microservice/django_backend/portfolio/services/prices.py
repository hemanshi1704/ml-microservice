"""Live/historical prices from Yahoo Finance (via yfinance)."""


class PriceFetchError(Exception):
    pass


def fetch_history(ticker, period="2y"):
    """Return [{"date": date, "close": float}, ...] oldest -> newest."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    except Exception as exc:  # network errors, bad ticker, library errors
        raise PriceFetchError(f"Yahoo Finance request failed for {ticker}: {exc}") from exc

    if df is None or df.empty:
        raise PriceFetchError(f"No price data returned for {ticker}")

    return [{"date": idx.date(), "close": float(row["Close"])} for idx, row in df.iterrows()]
