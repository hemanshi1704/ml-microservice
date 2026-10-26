"""API tests (need Django: run with `python manage.py test`)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from rest_framework.test import APITestCase

from portfolio.models import PriceCache
from portfolio.services.ml_client import MLServiceError


class PortfolioApiTests(APITestCase):
    def setUp(self):
        r = self.client.post("/api/portfolios/", {"name": "Demo", "owner_email": "me@example.com"}, format="json")
        self.pid = r.data["id"]

    def _tx(self, kind, qty, price, when):
        return self.client.post("/api/transactions/", {
            "portfolio": self.pid, "ticker": "aapl", "transaction_type": kind,
            "quantity": qty, "price_per_unit": price, "executed_at": when,
        }, format="json")

    def _seed_prices(self, n=40, close="100"):
        start = date(2025, 1, 1)
        PriceCache.objects.bulk_create([
            PriceCache(ticker="AAPL", date=start + timedelta(days=i), close=Decimal(close))
            for i in range(n)
        ])

    def test_ticker_is_uppercased_and_oversell_rejected(self):
        self.assertEqual(self._tx("BUY", "10", "100", "2025-06-01T10:00:00Z").data["ticker"], "AAPL")
        self.assertEqual(self._tx("SELL", "20", "110", "2025-06-02T10:00:00Z").status_code, 400)

    def test_holdings_use_fifo(self):
        self._tx("BUY", "10", "100", "2025-06-01T10:00:00Z")
        self._tx("BUY", "10", "120", "2025-06-02T10:00:00Z")
        self._tx("SELL", "15", "130", "2025-06-03T10:00:00Z")
        self._seed_prices(close="140")
        data = self.client.get(f"/api/portfolios/{self.pid}/holdings/").data
        row = data["holdings"][0]
        self.assertEqual(row["realized_pnl"], 350.0)
        self.assertEqual(row["quantity"], 5.0)
        self.assertEqual(row["unrealized_pnl"], 100.0)  # 5 * (140 - 120)

    @mock.patch("portfolio.views.get_ml_signal", side_effect=MLServiceError("ML service is unreachable"))
    def test_whatif_ml_falls_back_when_service_down(self, _):
        self._tx("BUY", "10", "100", "2025-06-01T10:00:00Z")
        self._seed_prices()
        data = self.client.get(f"/api/portfolios/{self.pid}/whatif/?engine=ml").data
        result = data["results"][0]
        self.assertEqual(result["engine_used"], "simple")
        self.assertTrue(result["fallback"])

    def test_whatif_requires_cached_prices(self):
        self._tx("BUY", "10", "100", "2025-06-01T10:00:00Z")
        data = self.client.get(f"/api/portfolios/{self.pid}/whatif/").data
        self.assertIn("error", data["results"][0])
