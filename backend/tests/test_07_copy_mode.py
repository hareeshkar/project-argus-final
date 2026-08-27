"""Copy mode API and narrative tests."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from argus_final.api.main import create_app
from argus_final.data.providers import InMemoryMarketDataProvider
from argus_final.llm import TemplateNarrator


class CopyModeApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(data_provider=InMemoryMarketDataProvider(), narrator=TemplateNarrator())
        self.client = TestClient(self.app)

    def test_simple_copy_mode_returns_plain_narrative(self):
        response = self.client.post(
            "/api/analyze",
            json={"query": "Analyze COMB", "demo_mode": True, "copy_mode": "simple"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("copy_mode"), "simple")
        self.assertEqual(payload["data_lineage"].get("copy_mode"), "simple")
        summary = payload["llm_explanation"]["summary"].lower()
        self.assertIn("for comb", summary)

    def test_experience_copy_mode_returns_technical_narrative(self):
        response = self.client.post(
            "/api/analyze",
            json={"query": "Analyze COMB", "demo_mode": True, "copy_mode": "experience"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("copy_mode"), "experience")
        headline = payload["llm_explanation"]["headline"]
        self.assertIn("COMB:", headline)
        summary = payload["llm_explanation"]["summary"]
        self.assertTrue(
            "beats_naive" in summary or "EWMA" in summary or "ARIMA" in summary,
            msg=f"expected technical tokens in summary: {summary}",
        )

    def test_invalid_copy_mode_falls_back_to_simple(self):
        response = self.client.post(
            "/api/analyze",
            json={"query": "Analyze COMB", "demo_mode": True, "copy_mode": "invalid"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("copy_mode"), "simple")

    def test_stream_includes_copy_mode_pipeline_titles(self):
        with TestClient(self.app) as client:
            response = client.get(
                "/api/analyze/stream",
                params={
                    "query": "Analyze COMB",
                    "demo_mode": "true",
                    "copy_mode": "simple",
                    "pace": "fast",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Finding the stock symbol", response.text)
        self.assertIn("event: final", response.text)


if __name__ == "__main__":
    unittest.main()
