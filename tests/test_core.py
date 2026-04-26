import unittest
from fastapi.testclient import TestClient

from main import app, build_signal, run_sma_backtest, simple_moving_average


class CoreLogicTests(unittest.TestCase):
    def test_sma_length_and_initial_nones(self):
        values = [1, 2, 3, 4, 5]
        sma = simple_moving_average(values, 3)
        self.assertEqual(len(sma), len(values))
        self.assertEqual(sma[:2], [None, None])
        self.assertAlmostEqual(sma[2], 2.0)

    def test_build_signal_bullish(self):
        signal = build_signal(100.0, "bullish_HH_HL")
        self.assertEqual(signal.side, "long")
        self.assertAlmostEqual(signal.entry, 100.0)
        self.assertGreater(signal.take_profit, signal.entry)
        self.assertLess(signal.stop_loss, signal.entry)

    def test_backtest_returns_metrics(self):
        ohlcv = []
        price = 100.0
        for i in range(300):
            price += 0.2 if i % 30 < 15 else -0.1
            ohlcv.append([i * 60_000, price, price + 1, price - 1, price, 1.0])

        metrics, trades = run_sma_backtest(ohlcv, fast_period=10, slow_period=30, fee_bps=4)

        self.assertGreaterEqual(metrics.trades, 0)
        self.assertLessEqual(len(trades), 10)
        self.assertIsInstance(metrics.total_return_pct, float)

    def test_health_endpoint(self):
        client = TestClient(app)
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("status"), "ok")

    def test_frontend_route(self):
        client = TestClient(app)
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
