"""
Live CSE REST end-to-end test.

This test fetches real CSE REST historical OHLCV and order-book data for
Commercial Bank (COMB.N0000), then runs the final analytics engine on that real
data. It does not use WebSocket ticks.

Run:
    PYTHONPATH=. ../project-argus/venv/bin/python -m unittest tests.test_02_live_cse_rest -v
"""

from __future__ import annotations

import asyncio
import json
import unittest

from argus_final.core.settings import Settings
from argus_final.data import CseRestMarketDataProvider
from argus_final.services import AnalysisService


def print_payload(title: str, payload) -> None:
    print(f"\n\n=== {title} ===")
    print(json.dumps(payload, indent=2, default=str, sort_keys=True))


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


async def fetch_live_comb_payload():
    provider = CseRestMarketDataProvider()
    service = AnalysisService(
        data_provider=provider,
        app_settings=Settings(data_source_mode="live_cse_rest"),
    )
    payload = service.analyze("Analyze COMB")
    math = payload["math_results"]
    latest = provider.last_historical_frame.iloc[-1]
    return {
        "mode": "LIVE_CSE_REST",
        "symbol": payload["symbol"],
        "historical_rows": payload["data_lineage"]["historical_rows"],
        "date_range": {
            "last": payload["data_lineage"]["last_historical_timestamp"],
        },
        "latest_bar": {
            "close": float(latest["close"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "volume": int(latest["volume"]),
        },
        "data_lineage": payload["data_lineage"],
        "quality_flags": payload["quality_flags"],
        "order_book": payload["order_book"],
        "indicator_vote": payload["indicator_vote"],
        "confidence": payload["confidence"],
        "arima": math["arima"],
        "volatility": math["volatility"],
        "anomaly": math["anomaly"],
        "drawdown": math["drawdown"],
        "regime": math["regime"],
        "overall_health": math["overall_health"],
    }


class LiveCseRestE2ETests(unittest.TestCase):
    def test_live_cse_rest_comb_runs_final_math_and_prints_output(self):
        print_section("PROJECT ARGUS FINAL - LIVE CSE REST TEST")
        print("Symbol: COMB.N0000")
        print("Data source: real CSE REST historical OHLCV + real CSE REST order book")
        print("WebSocket ticks used: no")
        print("Expected row cap: approximately 239-241 daily candles")
        print("Purpose: prove final analytics runs on real CSE REST data, not demo data")

        payload = asyncio.run(fetch_live_comb_payload())

        self.assertEqual(payload["mode"], "LIVE_CSE_REST")
        self.assertEqual(payload["symbol"], "COMB.N0000")
        self.assertEqual(payload["data_lineage"]["historical_source"], "CSE_REST")
        self.assertEqual(payload["data_lineage"]["order_book_source"], "CSE_REST_ORDERBOOK")
        self.assertGreaterEqual(payload["historical_rows"], 200)
        self.assertGreater(payload["latest_bar"]["close"], 0)
        self.assertGreater(payload["latest_bar"]["volume"], 0)

        self.assertIn("pressure", payload["order_book"])
        self.assertGreaterEqual(payload["order_book"]["pressure"], -1)
        self.assertLessEqual(payload["order_book"]["pressure"], 1)

        self.assertIn(payload["indicator_vote"]["signal"], {"BULLISH", "BEARISH", "NEUTRAL"})
        self.assertGreaterEqual(payload["confidence"]["score"], 0.0)
        self.assertLessEqual(payload["confidence"]["score"], 1.0)
        self.assertEqual(len(payload["arima"]["forecast"]), 3)
        self.assertGreater(payload["volatility"]["historical_var_95_pct"], 0)
        self.assertGreater(payload["volatility"]["parkinson_volatility_pct"], 0)
        self.assertEqual(payload["overall_health"], "HEALTHY")

        print_payload(
            "live_cse_rest_debug_header",
            {
                "mode": payload["mode"],
                "symbol": payload["symbol"],
                "historical_rows": payload["historical_rows"],
                "date_range": payload["date_range"],
                "latest_bar": payload["latest_bar"],
                "order_book_pressure": payload["order_book"].get("pressure"),
                "overall_health": payload["overall_health"],
            },
        )
        print_payload("live_cse_rest_comb_summary", payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
