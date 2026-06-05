"""
Offline demo end-to-end test.

This test uses only deterministic in-memory data. It is the safest test for
agents, CI, and viva demos because it does not need CSE internet access or LLM
API keys.

Run:
    PYTHONPATH=. ../project-argus/venv/bin/python -m unittest tests.test_01_offline_demo -v
"""

from __future__ import annotations

import json
import unittest

from argus_final.data.providers import InMemoryMarketDataProvider
from argus_final.services import AnalysisService


def print_payload(title: str, payload) -> None:
    print(f"\n\n=== {title} ===")
    print(json.dumps(payload, indent=2, default=str, sort_keys=True))


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


class OfflineDemoE2ETests(unittest.TestCase):
    def test_offline_demo_analyze_comb_prints_full_enterprise_payload(self):
        print_section("PROJECT ARGUS FINAL - OFFLINE DEMO TEST")
        print("Data source: deterministic in-memory provider")
        print("Network required: no")
        print("LLM/API key required: no")
        print("Purpose: stable CI/viva fallback that exercises the final analytics payload")

        service = AnalysisService(data_provider=InMemoryMarketDataProvider(rows=120))

        payload = service.analyze("Analyze COMB")

        self.assertEqual(payload["symbol"], "COMB.N0000")
        self.assertEqual(payload["data_source_mode"], "offline_demo")
        self.assertIsNone(payload["error"])

        required_top_level = {
            "query",
            "symbol",
            "timestamp",
            "processing_time",
            "data_source_mode",
            "data_lineage",
            "confidence",
            "indicator_vote",
            "math_results",
            "order_book",
            "microstructure",
            "llm_explanation",
            "quality_flags",
        }
        self.assertTrue(required_top_level.issubset(payload.keys()))

        math = payload["math_results"]
        for section in ["arima", "volatility", "anomaly", "drawdown", "trend", "regime", "confidence", "indicator_vote"]:
            self.assertIn(section, math)

        self.assertEqual(len(math["arima"]["forecast"]), 3)
        self.assertIn(math["arima"]["forecast_confidence"], {"LOW", "MODERATE", "HIGH"})
        self.assertGreater(math["volatility"]["historical_var_95_pct"], 0)
        self.assertGreater(math["volatility"]["parkinson_volatility_pct"], 0)
        self.assertIn(math["indicator_vote"]["signal"], {"BULLISH", "BEARISH", "NEUTRAL"})
        self.assertGreaterEqual(math["confidence"]["score"], 0.0)
        self.assertLessEqual(math["confidence"]["score"], 1.0)
        self.assertLess(
            abs(math["anomaly"]["modified_return_zscore"]),
            8.0,
            "Offline demo data should stay statistically believable for viva demos",
        )

        print_payload(
            "offline_demo_health",
            {
                "query": payload["query"],
                "symbol": payload["symbol"],
                "processing_time": payload["processing_time"],
                "top_level_keys": sorted(payload.keys()),
                "math_sections": sorted(math.keys()),
            },
        )
        print_payload(
            "offline_demo_summary",
            {
                "symbol": payload["symbol"],
                "mode": payload["data_source_mode"],
                "signal": payload["indicator_vote"],
                "confidence": payload["confidence"],
                "arima": math["arima"],
                "volatility": math["volatility"],
                "anomaly": math["anomaly"],
                "drawdown": math["drawdown"],
                "regime": math["regime"],
                "data_lineage": payload["data_lineage"],
                "quality_flags": payload["quality_flags"],
                "narrative": payload["llm_explanation"],
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
