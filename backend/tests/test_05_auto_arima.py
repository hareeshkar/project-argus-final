import unittest

from argus_final.analytics.engine import AnalyticsConfig, AnalyticsEngine
from argus_final.data.providers import InMemoryMarketDataProvider


class AutoArimaTests(unittest.TestCase):
    def test_auto_arima_output_schema(self):
        provider = InMemoryMarketDataProvider(rows=120)
        frame = provider.historical_ohlcv("COMB.N0000")
        engine = AnalyticsEngine(AnalyticsConfig(arima_mode="auto"))
        result = engine.run(frame)
        arima = result["arima"]
        self.assertIn("selected_order", arima)
        self.assertEqual(len(arima["forecast"]), 3)
        self.assertEqual(len(arima["confidence_interval"]["lower"]), 3)
        self.assertEqual(len(arima["confidence_interval"]["upper"]), 3)
        self.assertIn("beats_naive", arima)
        self.assertIn("forecast_confidence", arima)

    def test_grid_mode_still_available(self):
        provider = InMemoryMarketDataProvider(rows=120)
        frame = provider.historical_ohlcv("LOLC.N0000")
        engine = AnalyticsEngine(AnalyticsConfig(arima_mode="grid"))
        result = engine.run(frame)
        self.assertIn("ARIMA", result["arima"]["model_used"])


if __name__ == "__main__":
    unittest.main()
