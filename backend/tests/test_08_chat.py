"""RAG-backed chat endpoint tests."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from argus_final.api.main import create_app
from argus_final.data.providers import InMemoryMarketDataProvider
from argus_final.llm import TemplateNarrator
from argus_final.services.chat_service import (
    FULL_RAG_SECTION_MARKERS,
    RAG_SOURCE_KEYS,
    build_rag_context,
    rag_context_stats,
)


class ChatServiceUnitTests(unittest.TestCase):
    def test_build_rag_context_includes_math_and_lineage(self):
        payload = {
            "symbol": "COMB.N0000",
            "math_results": {
                "data_points": 120,
                "arima": {"model_used": "ARIMA(1,1,0)", "forecast": [100, 101, 102]},
                "volatility": {"risk_level": "MODERATE", "daily_volatility_pct": 1.2, "var_95_pct": 1.1, "historical_var_95_pct": 1.4},
                "confidence": {"label": "HIGH", "score": 0.85, "reasons": []},
                "indicator_vote": {"signal": "NEUTRAL", "score": 0.1, "components": {}},
                "trend": {},
                "regime": {},
                "anomaly": {},
                "drawdown": {},
            },
            "data_lineage": {"historical_source": "IN_MEMORY_DEMO", "historical_rows": 120},
            "microstructure": {"latest_price": 95.5},
            "llm_explanation": {"summary": "Test summary"},
        }
        ctx = build_rag_context("COMB.N0000", payload, copy_mode="simple")
        self.assertIn("COMB", ctx)
        self.assertIn("ARIMA", ctx)
        self.assertIn("Data lineage", ctx)
        self.assertIn("Test summary", ctx)
        self.assertIn("Bad Day Loss (95%)", ctx)
        self.assertIn("EWMA VaR 95", ctx)
        self.assertIn("Simple label:", ctx)
        self.assertIn("Experience label:", ctx)
        self.assertIn("ACTIVE_MODE", ctx)
        self.assertIn("var_95_pct", ctx)
        self.assertIn("Confidence penalties", ctx)
        self.assertIn("Full analysis payload", ctx)

    def test_rag_context_stats_and_full_demo_coverage(self):
        app = create_app(data_provider=InMemoryMarketDataProvider(), narrator=TemplateNarrator())
        client = TestClient(app)
        analyze = client.post(
            "/api/analyze",
            json={"query": "Analyze COMB", "demo_mode": True, "copy_mode": "simple"},
        )
        self.assertEqual(analyze.status_code, 200)
        payload = analyze.json()

        ctx = build_rag_context(payload["symbol"], payload, copy_mode="simple")
        stats = rag_context_stats(ctx)

        self.assertGreater(stats["char_count"], 4000, "RAG context should be substantial for full analysis")
        self.assertGreaterEqual(stats["section_count"], 12)
        for marker in FULL_RAG_SECTION_MARKERS:
            self.assertIn(marker, ctx, msg=f"Missing RAG section: {marker}")

        chat = client.post(
            "/api/chat",
            json={
                "message": "Summarize risk metrics with exact numbers",
                "analysis": payload,
                "copy_mode": "simple",
            },
        )
        self.assertEqual(chat.status_code, 200)
        body = chat.json()
        self.assertEqual(body["rag_sources"], list(RAG_SOURCE_KEYS))
        self.assertGreater(body["rag_stats"]["char_count"], 4000)
        self.assertIn("analysis", body)
        self.assertFalse(body["analysis_refreshed"])

    def test_template_bad_day_loss_explanation(self):
        from argus_final.services.chat_service import _template_chat_reply

        payload = {
            "symbol": "COMB.N0000",
            "math_results": {
                "volatility": {
                    "var_95_pct": 1.23,
                    "historical_var_95_pct": 1.56,
                    "historical_var_99_pct": 2.1,
                    "risk_level": "MODERATE",
                    "daily_volatility_pct": 1.1,
                },
                "drawdown": {"current_drawdown_pct": 3.4, "max_drawdown_pct": 12.0},
            },
        }
        reply = _template_chat_reply("What is bad day loss?", payload, "simple")
        self.assertIn("Bad Day Loss", reply)
        self.assertIn("1.23%", reply)
        self.assertIn("research analytics", reply.lower())


class ChatApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(data_provider=InMemoryMarketDataProvider(), narrator=TemplateNarrator())
        self.client = TestClient(self.app)

    def test_chat_with_bundled_analysis(self):
        analyze = self.client.post(
            "/api/analyze",
            json={"query": "Analyze COMB", "demo_mode": True, "copy_mode": "simple"},
        )
        self.assertEqual(analyze.status_code, 200)
        payload = analyze.json()

        response = self.client.post(
            "/api/chat",
            json={
                "message": "Why is confidence at this level?",
                "analysis": payload,
                "copy_mode": "simple",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("reply", body)
        self.assertEqual(body["symbol"], "COMB.N0000")
        reply_lower = body["reply"].lower()
        self.assertTrue("confidence" in reply_lower or "trust" in reply_lower)
        self.assertIn("rag_sources", body)
        self.assertFalse(body["analysis_refreshed"])

    def test_chat_bad_day_loss_with_bundled_analysis(self):
        analyze = self.client.post(
            "/api/analyze",
            json={"query": "Analyze COMB", "demo_mode": True, "copy_mode": "simple"},
        )
        self.assertEqual(analyze.status_code, 200)
        payload = analyze.json()

        response = self.client.post(
            "/api/chat",
            json={
                "message": "What is bad day loss? What does this number mean?",
                "analysis": payload,
                "copy_mode": "simple",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        reply_lower = body["reply"].lower()
        self.assertTrue(
            "bad day" in reply_lower or "var" in reply_lower or "worst" in reply_lower,
            msg=body["reply"],
        )
        self.assertIn("metric_glossary_dual", body["rag_sources"] or [])
        self.assertIn("analysis", body)

    def test_chat_refresh_reruns_symbol_not_message(self):
        analyze = self.client.post(
            "/api/analyze",
            json={"query": "Analyze COMB", "demo_mode": True, "copy_mode": "simple"},
        )
        self.assertEqual(analyze.status_code, 200)
        payload = analyze.json()

        response = self.client.post(
            "/api/chat",
            json={
                "message": "What is bad day loss?",
                "analysis": payload,
                "demo_mode": True,
                "copy_mode": "simple",
                "refresh_analysis": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["analysis_refreshed"])
        self.assertEqual(body["symbol"], "COMB.N0000")
        self.assertIn("analysis", body)
        self.assertEqual(body["analysis"]["symbol"], "COMB.N0000")
        self.assertIn("bad day", body["reply"].lower())

    def test_chat_copy_mode_in_response(self):
        analyze = self.client.post(
            "/api/analyze",
            json={"query": "Analyze COMB", "demo_mode": True, "copy_mode": "experience"},
        )
        payload = analyze.json()
        response = self.client.post(
            "/api/chat",
            json={
                "message": "Explain EWMA VaR",
                "analysis": payload,
                "copy_mode": "experience",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("copy_mode"), "experience")

    def test_chat_without_analysis_runs_pipeline(self):
        response = self.client.post(
            "/api/chat",
            json={
                "message": "What is the risk for COMB?",
                "demo_mode": True,
                "copy_mode": "simple",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["analysis_refreshed"])
        self.assertIn("risk", body["reply"].lower())

    def test_chat_requires_message(self):
        response = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
