"""Pure-Python tests: no database or Django settings needed."""
import unittest
from decimal import Decimal
from unittest import mock

import requests

from portfolio.services.analytics import compute_positions
from portfolio.services.ml_client import MLServiceError, get_ml_signal
from portfolio.services.signals import generate_signal, rolling_mean_signal


def prices(values):
    return [{"date": f"2025-01-{i + 1:02d}", "close": v} for i, v in enumerate(values)]


class FifoTests(unittest.TestCase):
    def test_fifo_realized_pnl_and_remaining_cost(self):
        txs = [
            {"ticker": "AAPL", "type": "BUY", "quantity": 10, "price": 100},
            {"ticker": "AAPL", "type": "BUY", "quantity": 10, "price": 120},
            {"ticker": "AAPL", "type": "SELL", "quantity": 15, "price": 130},
        ]
        pos = compute_positions(txs)["AAPL"]
        # 10 @100 -> +300, 5 @120 -> +50
        self.assertEqual(pos["realized_pnl"], Decimal("350"))
        self.assertEqual(pos["quantity"], Decimal("5"))
        self.assertEqual(pos["avg_cost"], Decimal("120"))

    def test_overselling_raises(self):
        txs = [{"ticker": "AAPL", "type": "BUY", "quantity": 1, "price": 100},
               {"ticker": "AAPL", "type": "SELL", "quantity": 2, "price": 100}]
        with self.assertRaises(ValueError):
            compute_positions(txs)


class SignalTests(unittest.TestCase):
    def test_rolling_mean_buy_when_above_mean(self):
        data = prices([10] * 19 + [20])
        self.assertEqual(rolling_mean_signal(data, window=20)["signal"], "BUY")

    def test_rolling_mean_hold_when_below_mean(self):
        data = prices([20] * 19 + [10])
        self.assertEqual(rolling_mean_signal(data, window=20)["signal"], "HOLD")

    def test_ml_engine_used_when_service_ok(self):
        ml = mock.Mock(return_value={"signal": "BUY", "metrics": {"accuracy": 0.55}})
        out = generate_signal("ml", "AAPL", prices([1] * 30), ml_fn=ml)
        self.assertEqual(out["engine_used"], "ml")
        self.assertFalse(out["fallback"])

    def test_falls_back_to_rolling_mean_when_ml_down(self):
        ml = mock.Mock(side_effect=MLServiceError("ML service is unreachable"))
        out = generate_signal("ml", "AAPL", prices([1] * 30), ml_fn=ml)
        self.assertEqual(out["engine_used"], "simple")
        self.assertTrue(out["fallback"])
        self.assertIn("unreachable", out["fallback_reason"])


class MLClientTests(unittest.TestCase):
    @mock.patch("portfolio.services.ml_client.requests.post",
                side_effect=requests.exceptions.ConnectionError())
    def test_connection_error_becomes_ml_service_error(self, _):
        with self.assertRaises(MLServiceError):
            get_ml_signal("AAPL", prices([1] * 30), url="http://nowhere")

    @mock.patch("portfolio.services.ml_client.requests.post",
                side_effect=requests.exceptions.Timeout())
    def test_timeout_becomes_ml_service_error(self, _):
        with self.assertRaises(MLServiceError):
            get_ml_signal("AAPL", prices([1] * 30), url="http://nowhere")

    @mock.patch("portfolio.services.ml_client.requests.post")
    def test_parses_signal_and_metrics(self, post):
        post.return_value.json.return_value = {"signal": "HOLD", "metrics": {"precision": 0.6}}
        post.return_value.raise_for_status.return_value = None
        out = get_ml_signal("AAPL", prices([1] * 30), url="http://ml")
        self.assertEqual(out, {"signal": "HOLD", "metrics": {"precision": 0.6}})


if __name__ == "__main__":
    unittest.main()
