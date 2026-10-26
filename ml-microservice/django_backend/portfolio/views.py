from decimal import Decimal

from django.db import transaction as db_transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Portfolio, PriceCache, Transaction
from .serializers import PortfolioSerializer, TransactionSerializer
from .services.analytics import compute_positions
from .services.ml_client import get_ml_signal
from .services.prices import PriceFetchError, fetch_history
from .services.signals import generate_signal

MIN_PRICE_POINTS = 30


def _f(value, places=4):
    return round(float(value), places)


class PortfolioViewSet(viewsets.ModelViewSet):
    queryset = Portfolio.objects.all().order_by("id")
    serializer_class = PortfolioSerializer

    @action(detail=True, methods=["get"])
    def holdings(self, request, pk=None):
        portfolio = self.get_object()
        txs = [
            {"ticker": t.ticker, "type": t.transaction_type,
             "quantity": t.quantity, "price": t.price_per_unit}
            for t in portfolio.transactions.order_by("executed_at", "id")
        ]
        try:
            positions = compute_positions(txs)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        rows, total_value, total_unrealized, total_realized = [], Decimal("0"), Decimal("0"), Decimal("0")
        for ticker, pos in sorted(positions.items()):
            latest = PriceCache.objects.filter(ticker=ticker).order_by("-date").first()
            row = {
                "ticker": ticker,
                "quantity": _f(pos["quantity"]),
                "avg_cost": _f(pos["avg_cost"]),
                "cost_basis": _f(pos["cost_basis"]),
                "realized_pnl": _f(pos["realized_pnl"]),
                "last_price": None, "market_value": None, "unrealized_pnl": None,
            }
            total_realized += pos["realized_pnl"]
            if latest and pos["quantity"] > 0:
                value = pos["quantity"] * latest.close
                unrealized = value - pos["cost_basis"]
                row.update(last_price=_f(latest.close), market_value=_f(value),
                           unrealized_pnl=_f(unrealized))
                total_value += value
                total_unrealized += unrealized
            rows.append(row)

        return Response({
            "portfolio": portfolio.id,
            "holdings": rows,
            "totals": {"market_value": _f(total_value),
                       "unrealized_pnl": _f(total_unrealized),
                       "realized_pnl": _f(total_realized)},
        })

    @action(detail=True, methods=["post"])
    def refresh_prices(self, request, pk=None):
        portfolio = self.get_object()
        tickers = sorted(set(portfolio.transactions.values_list("ticker", flat=True)))
        if not tickers:
            return Response({"detail": "Portfolio has no transactions."},
                            status=status.HTTP_400_BAD_REQUEST)

        synced, errors = {}, {}
        for ticker in tickers:
            try:
                history = fetch_history(ticker)
            except PriceFetchError as exc:
                errors[ticker] = str(exc)
                continue
            rows = [PriceCache(ticker=ticker, date=h["date"],
                               close=Decimal(str(round(h["close"], 4)))) for h in history]
            with db_transaction.atomic():
                PriceCache.objects.filter(ticker=ticker).delete()
                PriceCache.objects.bulk_create(rows)
            synced[ticker] = len(rows)

        code = status.HTTP_502_BAD_GATEWAY if errors and not synced else status.HTTP_200_OK
        return Response({"synced": synced, "errors": errors}, status=code)

    @action(detail=True, methods=["get"])
    def whatif(self, request, pk=None):
        portfolio = self.get_object()
        engine = request.query_params.get("engine", "simple").lower()
        if engine not in ("simple", "ml"):
            return Response({"detail": "engine must be 'simple' or 'ml'."},
                            status=status.HTTP_400_BAD_REQUEST)

        ticker_param = request.query_params.get("ticker")
        if ticker_param:
            tickers = [ticker_param.strip().upper()]
        else:
            tickers = sorted(set(portfolio.transactions.values_list("ticker", flat=True)))

        results = []
        for ticker in tickers:
            rows = PriceCache.objects.filter(ticker=ticker).order_by("date").values("date", "close")
            prices = [{"date": r["date"].isoformat(), "close": float(r["close"])} for r in rows]
            if len(prices) < MIN_PRICE_POINTS:
                results.append({"ticker": ticker,
                                "error": "Not enough cached prices. Call POST refresh_prices first."})
                continue
            result = generate_signal(engine, ticker, prices, ml_fn=get_ml_signal)
            results.append({"ticker": ticker, **result})

        return Response({"portfolio": portfolio.id, "engine_requested": engine, "results": results})


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all().order_by("id")
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        portfolio = self.request.query_params.get("portfolio")
        if portfolio:
            qs = qs.filter(portfolio_id=portfolio)
        return qs
