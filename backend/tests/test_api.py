import unittest
import json

from fastapi.testclient import TestClient

from argus_final.api.main import create_app
from argus_final.data.providers import InMemoryMarketDataProvider
from argus_final.llm.adapter import TemplateNarrator


def print_payload(title: str, payload) -> None:
    print(f"\n\n=== {title} ===")
    print(json.dumps(payload, indent=2, default=str, sort_keys=True))


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


class ApiTests(unittest.TestCase):
    def test_analyze_endpoint_returns_enterprise_payload_without_real_llm(self):
        print_section("PROJECT ARGUS FINAL - API ANALYZE TEST")
        print("Endpoint: POST /api/analyze")
        print("Provider: deterministic in-memory provider")
        print("LLM provider: template fallback")
        print("Purpose: prove API response shape matches frontend/agent expectations")

        provider = InMemoryMarketDataProvider()
        app = create_app(data_provider=provider)

        with TestClient(app) as client:
            response = client.post("/api/analyze", json={"query": "Analyze COMB"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["symbol"], "COMB.N0000")
        self.assertIn(payload["indicator_vote"]["signal"], {"BULLISH", "BEARISH", "NEUTRAL"})
        self.assertIn("confidence", payload)
        self.assertIn("data_lineage", payload)
        self.assertIn("quality_flags", payload)
        self.assertIn("llm_explanation", payload)
        self.assertIsNone(payload["error"])

        print_payload(
            "api_contract_debug_header",
            {
                "status_code": response.status_code,
                "top_level_keys": sorted(payload.keys()),
                "math_sections": sorted(payload["math_results"].keys()),
                "data_lineage": payload["data_lineage"],
            },
        )
        print_payload(
            "api_analyze_summary",
            {
                "status_code": response.status_code,
                "symbol": payload["symbol"],
                "signal": payload["indicator_vote"],
                "confidence": payload["confidence"],
                "arima": payload["math_results"]["arima"],
                "volatility": payload["math_results"]["volatility"],
                "anomaly": payload["math_results"]["anomaly"],
                "data_lineage": payload["data_lineage"],
                "quality_flags": payload["quality_flags"],
                "llm_explanation": payload["llm_explanation"],
            },
        )

    def test_analyze_endpoint_can_toggle_demo_mode_for_frontend(self):
        app = create_app()

        with TestClient(app) as client:
            demo_response = client.post("/api/analyze", json={"query": "Analyze COMB", "demo_mode": True})
            live_response = client.post("/api/analyze", json={"query": "Analyze COMB", "demo_mode": False})

        self.assertEqual(demo_response.status_code, 200)
        self.assertEqual(live_response.status_code, 200)

        demo_payload = demo_response.json()
        live_payload = live_response.json()

        self.assertEqual(demo_payload["data_source_mode"], "offline_demo")
        self.assertEqual(demo_payload["data_lineage"]["historical_source"], "IN_MEMORY_DEMO")

        self.assertEqual(live_payload["data_source_mode"], "live_cse_rest")
        self.assertEqual(live_payload["data_lineage"]["historical_source"], "CSE_REST")
        self.assertEqual(live_payload["data_lineage"]["order_book_source"], "CSE_REST_ORDERBOOK")
        self.assertGreater(live_payload["microstructure"]["latest_price"], 0)

        print_payload(
            "api_demo_mode_toggle_summary",
            {
                "demo": {
                    "mode": demo_payload["data_source_mode"],
                    "historical_source": demo_payload["data_lineage"]["historical_source"],
                    "symbol": demo_payload["symbol"],
                    "signal": demo_payload["indicator_vote"]["signal"],
                },
                "live": {
                    "mode": live_payload["data_source_mode"],
                    "historical_source": live_payload["data_lineage"]["historical_source"],
                    "order_book_source": live_payload["data_lineage"]["order_book_source"],
                    "symbol": live_payload["symbol"],
                    "signal": live_payload["indicator_vote"]["signal"],
                    "quality_flags": live_payload["quality_flags"],
                },
            },
        )

    def test_analyze_stream_endpoint_emits_pipeline_and_final_payload(self):
        app = create_app(data_provider=InMemoryMarketDataProvider())

        with TestClient(app) as client:
            response = client.get("/api/analyze/stream?query=Analyze%20COMB&demo_mode=true&pace=fast")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        body = response.text
        self.assertIn("event: pipeline", body)
        self.assertIn("event: final", body)
        self.assertIn('"stage_id": "parse"', body)
        self.assertIn('"symbol": "COMB.N0000"', body)
        allowed_stage_statuses = {"queued", "running", "done", "degraded", "error"}
        last_event = None
        for line in body.splitlines():
            if line.startswith("event: "):
                last_event = line.removeprefix("event: ")
            if last_event == "pipeline" and line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
                self.assertIn(payload["status"], allowed_stage_statuses)

    def test_health_endpoint_reports_component_status(self):
        print_section("PROJECT ARGUS FINAL - API HEALTH TEST")
        print("Endpoint: GET /health")
        print("Purpose: prove component status is exposed for debugging")

        app = create_app(data_provider=InMemoryMarketDataProvider(), narrator=TemplateNarrator())

        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["components"]["api"], "ok")
        self.assertEqual(payload["components"]["data_provider"], "ok")
        self.assertEqual(payload["components"]["narrative_provider"], "deterministic_template")

        print_payload("api_health_summary", payload)

    def test_live_snapshot_endpoint_returns_debuggable_tape_payload(self):
        app = create_app(data_provider=InMemoryMarketDataProvider())

        with TestClient(app) as client:
            response = client.get("/api/live-snapshot?duration=1&real=false")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "deterministic_fallback")
        self.assertGreater(payload["memory_stats"]["total_ticks"], 0)
        self.assertIn("COMB.N0000", payload["symbol_metrics"])
        self.assertIn("metadata", payload)

        print_payload("api_live_snapshot_summary", payload)

    def test_optional_nodes_fail_softly_without_killing_analysis(self):
        class OptionalFailureProvider(InMemoryMarketDataProvider):
            def order_book(self, symbol):
                raise RuntimeError("order book unavailable")

            def microstructure(self, symbol):
                raise RuntimeError("microstructure unavailable")

        class FailingNarrator:
            def explain(self, symbol, analysis):
                raise RuntimeError("LLM unavailable")

        app = create_app(data_provider=OptionalFailureProvider(), narrator=FailingNarrator())

        with TestClient(app) as client:
            response = client.post("/api/analyze", json={"query": "Analyze COMB"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["symbol"], "COMB.N0000")
        self.assertEqual(payload["node_status"]["historical_data"]["status"], "ok")
        self.assertEqual(payload["node_status"]["order_book"]["status"], "degraded")
        self.assertEqual(payload["node_status"]["microstructure"]["status"], "degraded")
        self.assertEqual(payload["node_status"]["narrative"]["status"], "degraded")
        self.assertEqual(payload["data_lineage"]["llm_provider"], "deterministic_template_fallback")
        self.assertIn("fallback", payload["llm_explanation"]["summary"].lower())

    def test_cors_allows_vite_localhost_and_loopback_origins(self):
        app = create_app(data_provider=InMemoryMarketDataProvider())

        with TestClient(app) as client:
            for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
                response = client.options(
                    "/api/analyze",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["access-control-allow-origin"], origin)


if __name__ == "__main__":
    unittest.main()
