"""
Full API integration tests — exercises every public endpoint and validates contracts.

Offline tests always run. Live CSE tests run when network is available; WebSocket
capture assertions are strict only during market hours (Mon–Fri 09:30–14:30 SLT).

Run:
    PYTHONPATH=. ../../project-argus/venv/bin/python -m unittest tests.test_05_full_api_integration -v
"""

from __future__ import annotations

import json
import os
import unittest

from fastapi.testclient import TestClient

from argus_final.api.main import create_app
from argus_final.data.providers import InMemoryMarketDataProvider
from tests.test_helpers import (
    PIPELINE_STAGE_ORDER,
    assert_analyze_contract,
    assert_pipeline_sse,
    is_cse_market_hours,
    parse_sse,
)


def print_payload(title: str, payload) -> None:
    print(f"\n\n=== {title} ===")
    print(json.dumps(payload, indent=2, default=str, sort_keys=True))


class FullApiOfflineTests(unittest.TestCase):
    """Deterministic contract tests — no network required."""

    def setUp(self):
        self.app = create_app(data_provider=InMemoryMarketDataProvider())
        self.client = TestClient(self.app)

    def test_all_endpoints_respond_with_valid_shapes(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        health_payload = health.json()
        self.assertEqual(health_payload["status"], "ok")
        self.assertIn("components", health_payload)

        analyze = self.client.post("/api/analyze", json={"query": "Analyze JKH", "demo_mode": True})
        self.assertEqual(analyze.status_code, 200)
        analyze_payload = analyze.json()
        assert_analyze_contract(analyze_payload)
        self.assertEqual(analyze_payload["symbol"], "JKH.N0000")
        self.assertEqual(analyze_payload["data_source_mode"], "offline_demo")

        snapshot = self.client.get("/api/live-snapshot?duration=1&real=false")
        self.assertEqual(snapshot.status_code, 200)
        snap_payload = snapshot.json()
        self.assertIn("symbol_metrics", snap_payload)
        self.assertIn("memory_stats", snap_payload)
        self.assertGreater(snap_payload["memory_stats"]["total_ticks"], 0)

        prices = self.client.get("/api/market-prices")
        self.assertEqual(prices.status_code, 200)
        prices_payload = prices.json()
        self.assertIn("prices", prices_payload)
        self.assertGreaterEqual(prices_payload["count"], 0)

        print_payload(
            "full_api_offline_summary",
            {
                "health": health_payload["components"],
                "analyze_symbol": analyze_payload["symbol"],
                "analyze_signal": analyze_payload["indicator_vote"]["signal"],
                "snapshot_mode": snap_payload["mode"],
                "snapshot_ticks": snap_payload["memory_stats"]["total_ticks"],
                "market_prices_count": prices_payload["count"],
            },
        )

    def test_sse_stream_emits_ordered_pipeline_then_final(self):
        response = self.client.get(
            "/api/analyze/stream?query=Analyze%20COMB&demo_mode=true&pace=fast"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])

        final_payload = assert_pipeline_sse(response.text)
        events = parse_sse(response.text)
        pipeline_stages = [p for name, p in events if name == "pipeline"]

        seen_order = [stage["stage_id"] for stage in pipeline_stages]
        last_index = -1
        for stage_id in PIPELINE_STAGE_ORDER:
            if stage_id in seen_order:
                idx = seen_order.index(stage_id)
                self.assertGreater(idx, last_index, f"Pipeline stage {stage_id} out of order")
                last_index = idx

        self.assertEqual(final_payload["symbol"], "COMB.N0000")
        done_stages = {s["stage_id"] for s in pipeline_stages if s["status"] in {"done", "degraded"}}
        self.assertEqual(done_stages, set(PIPELINE_STAGE_ORDER))

        print_payload(
            "full_api_sse_summary",
            {
                "stage_count": len(pipeline_stages),
                "stages": [
                    {"id": s["stage_id"], "status": s["status"], "elapsed_ms": s.get("elapsed_ms")}
                    for s in pipeline_stages
                ],
                "final_symbol": final_payload["symbol"],
                "final_signal": final_payload["indicator_vote"]["signal"],
            },
        )

    def test_symbol_extraction_from_natural_language_queries(self):
        cases = [
            ("Analyze COMB", "COMB.N0000"),
            ("What about JKH?", "JKH.N0000"),
            ("HNB.N0000 risk profile", "HNB.N0000"),
            ("Tell me about DIAL stock", "DIAL.N0000"),
        ]
        for query, expected in cases:
            with self.subTest(query=query):
                response = self.client.post("/api/analyze", json={"query": query, "demo_mode": True})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["symbol"], expected)


class FullApiLiveTests(unittest.TestCase):
    """Live CSE REST/WebSocket tests — require network."""

    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        self.market_open = is_cse_market_hours()

    def test_live_rest_analyze_returns_cse_data_lineage(self):
        response = self.client.post("/api/analyze", json={"query": "Analyze COMB", "demo_mode": False})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        assert_analyze_contract(payload)

        self.assertEqual(payload["data_source_mode"], "live_cse_rest")
        self.assertEqual(payload["data_lineage"]["historical_source"], "CSE_REST")
        self.assertGreater(payload["math_results"]["data_points"], 0)
        self.assertGreater(payload["microstructure"]["latest_price"], 0)

        print_payload(
            "full_api_live_rest_summary",
            {
                "market_open": self.market_open,
                "symbol": payload["symbol"],
                "data_points": payload["math_results"]["data_points"],
                "signal": payload["indicator_vote"]["signal"],
                "confidence": payload["confidence"]["label"],
                "arima_order": payload["math_results"]["arima"]["selected_order"],
                "latest_price": payload["microstructure"]["latest_price"],
                "quality_warnings": payload["quality_flags"]["warnings"],
            },
        )

    def test_market_prices_returns_symbol_map(self):
        response = self.client.get("/api/market-prices")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload["count"], 100)
        self.assertIn("COMB.N0000", payload["prices"])
        comb = payload["prices"]["COMB.N0000"]
        self.assertIsNotNone(comb.get("price"))
        self.assertIn("change", comb)
        self.assertIn("pct_change", comb)

    def test_live_price_returns_single_symbol(self):
        response = self.client.get("/api/live-price?symbol=COMB.N0000")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("found"))
        self.assertEqual(payload["symbol"], "COMB.N0000")
        self.assertIsNotNone(payload.get("price"))
        self.assertEqual(payload.get("source"), "CSE_REST_TRADE_SUMMARY")
        self.assertIn("sharevolume", payload)
        self.assertIn("last_traded_time", payload)

    def test_live_snapshot_real_capture_during_market_hours(self):
        run_real = os.getenv("ARGUS_RUN_REAL_WEBSOCKET", "1" if self.market_open else "0") == "1"
        duration = int(os.getenv("ARGUS_WEBSOCKET_SECONDS", "8"))
        response = self.client.get(f"/api/live-snapshot?duration={duration}&real={str(run_real).lower()}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("mode", payload)
        self.assertIn("symbol_metrics", payload)
        self.assertIn("metadata", payload)
        self.assertEqual(payload["metadata"]["live_source"], "CSE_WEBSOCKET_DAYTRADE")

        if run_real and self.market_open:
            self.assertEqual(payload["mode"], "live_cse_websocket")
            self.assertGreater(payload["live_ticks_captured"], 0)
            self.assertGreater(payload["memory_stats"]["total_symbols"], 0)
            sample_symbol = payload["symbols"][0]
            metrics = payload["symbol_metrics"][sample_symbol]
            self.assertGreater(metrics["latest_price"], 0)
        else:
            self.assertIn(payload["mode"], {"deterministic_fallback", "live_cse_websocket"})

        print_payload(
            "full_api_live_snapshot_summary",
            {
                "market_open": self.market_open,
                "run_real": run_real,
                "mode": payload["mode"],
                "ticks_captured": payload["live_ticks_captured"],
                "symbols": len(payload["symbols"]),
                "last_error": payload.get("last_error"),
            },
        )

    def test_live_sse_stream_with_rest_data(self):
        response = self.client.get(
            "/api/analyze/stream?query=Analyze%20SAMP&demo_mode=false&pace=fast"
        )
        self.assertEqual(response.status_code, 200)
        final_payload = assert_pipeline_sse(response.text)
        self.assertEqual(final_payload["data_source_mode"], "live_cse_rest")
        self.assertEqual(final_payload["symbol"], "SAMP.N0000")
        self.assertGreater(final_payload["processing_time"], 0)


if __name__ == "__main__":
    unittest.main()
