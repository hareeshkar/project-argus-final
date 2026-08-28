"""Unit tests for the Ollama -> Gemini -> DeepSeek fallback chain (test_10)."""

import json
import unittest

import httpx

from argus_final.llm import (
    ChainNarrator,
    GeminiNarrator,
    OllamaNarrator,
    TemplateNarrator,
)


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _gemini_ok_handler(text='{"headline": "H", "summary": "S", "risk_notes": ["r"], "confidence_explanation": "c", "disclaimer": "d"}'):
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "candidates": [
                {
                    "content": {"parts": [{"text": text}], "role": "model"},
                    "finishReason": "STOP",
                }
            ]
        }
        return httpx.Response(200, json=body)

    return handler


class TestGeminiTranslator(unittest.TestCase):
    """The translator must convert the internal call into Gemini wire format."""

    def _narrator(self, handler):
        return GeminiNarrator(api_key="test-key", model="gemini-3.5-flash-lite", transport=_mock_transport(handler))

    def test_request_shape_and_auth(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["key_header"] = request.headers.get("x-goog-api-key")
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [
                    [{"text": '{"headline": "H", "summary": "S", "risk_notes": ["r"], '
                     '"confidence_explanation": "c", "disclaimer": "d"}'}][0]
                ]}, "finishReason": "STOP"}]},
            )

        result = self._narrator(handler).explain("COMB.N0000", _sample_analysis(), copy_mode="simple")

        self.assertTrue(seen["url"].startswith("https://generativelanguage.googleapis.com/v1beta/models/"))
        self.assertIn(":generateContent", seen["url"])
        self.assertIn("gemini-3.5-flash-lite", seen["url"])
        self.assertEqual(seen["key_header"], "test-key")
        body = seen["body"]
        self.assertNotIn("system_instruction", body)
        self.assertIn("systemInstruction", body)
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"][:8], "You are ")
        self.assertEqual(body["contents"][0]["role"], "user")
        self.assertTrue(body["contents"][0]["parts"][0]["text"])
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 900)
        self.assertEqual(result["headline"], "H")
        self.assertEqual(result["disclaimer"], "d")

    def test_copy_modes_change_system_prompt(self):
        prompts = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode())
            prompts.append(body["systemInstruction"]["parts"][0]["text"])
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "{}"}]}, "finishReason": "STOP"}]},
            )

        narrator = self._narrator(handler)
        narrator.explain("COMB.N0000", _sample_analysis(), copy_mode="simple")
        narrator.explain("COMB.N0000", _sample_analysis(), copy_mode="experience")
        self.assertIn("regular investor", prompts[0])
        self.assertIn("quantitative CSE research analyst", prompts[1])

    def test_api_error_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT"}},
            )

        with self.assertRaises(RuntimeError) as ctx:
            self._narrator(handler).explain("COMB.N0000", _sample_analysis())
        self.assertIn("API key not valid", str(ctx.exception))

    def test_blocked_prompt_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})

        with self.assertRaises(RuntimeError) as ctx:
            self._narrator(handler).explain("COMB.N0000", _sample_analysis())
        self.assertIn("blocked", str(ctx.exception))

    def test_empty_text_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]},
            )

        with self.assertRaises(RuntimeError) as ctx:
            self._narrator(handler).explain("COMB.N0000", _sample_analysis())
        self.assertIn("MAX_TOKENS", str(ctx.exception))

    def test_complete_chat_role_translation(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": "  answer "}]}
                                                 , "finishReason": "STOP"}]}
            )

        narrator = self._narrator(handler)
        reply = narrator.complete_chat(
            [
                {"role": "system", "content": "sys prompt"},
                {"role": "user", "content": "question one"},
                {"role": "assistant", "content": "earlier reply"},
                {"role": "user", "content": "follow up"},
            ]
        )
        self.assertEqual(reply, "answer")
        body = seen["body"]
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "sys prompt")
        self.assertEqual([c["role"] for c in body["contents"]], ["user", "model", "user"])
        self.assertNotIn("responseMimeType", body["generationConfig"])


class TestOllamaNarrator(unittest.TestCase):
    def test_explain_uses_native_chat_api(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={"message": {"content": json.dumps({
                    "headline": "Local H", "summary": "S", "risk_notes": [],
                    "confidence_explanation": "c", "disclaimer": "d",
                })}},
            )

        narrator = OllamaNarrator(base_url="http://localhost:11434", model="gemma4", transport=_mock_transport(handler))
        result = narrator.explain("COMB.N0000", _sample_analysis())

        self.assertIn("/api/chat", seen["url"])
        body = seen["body"]
        self.assertEqual(body["model"], "gemma4")
        self.assertFalse(body["stream"])
        self.assertEqual(body["format"], "json")
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(result["headline"], "Local H")


class TestChainNarrator(unittest.TestCase):
    def test_falls_through_to_next_provider(self):
        calls = []

        class Flaky:
            model = "broken"
            provider_name = "broken"

            def explain(self, symbol, analysis, copy_mode="simple"):
                calls.append("broken")
                raise RuntimeError("connection refused")

        class Working:
            model = "gemini-3.5-flash-lite"
            provider_name = "gemini"

            def explain(self, symbol, analysis, copy_mode="simple"):
                calls.append("gemini")
                return {"headline": "ok", "summary": "", "risk_notes": [], "confidence_explanation": "", "disclaimer": ""}

        chain = ChainNarrator([Flaky(), Working()])
        result = chain.explain("COMB.N0000", {})
        self.assertEqual(calls, ["broken", "gemini"])
        self.assertEqual(result["headline"], "ok")
        self.assertEqual(chain.last_provider, "gemini")
        self.assertEqual(chain.model, "gemini-3.5-flash-lite")

    def test_all_fail_raises(self):
        class Bad:
            model = "bad"
            provider_name = "bad"

            def explain(self, symbol, analysis, copy_mode="simple"):
                raise RuntimeError("down")

        with self.assertRaises(RuntimeError) as ctx:
            ChainNarrator([Bad(), Bad()]).explain("COMB.N0000", {})
        self.assertIn("all narrators failed", str(ctx.exception))

    def test_chat_fallback(self):
        class No:
            model = "no"
            provider_name = "no"

            def complete_chat(self, messages, max_tokens=800, temperature=0.3):
                raise RuntimeError("offline")

        class Yes:
            model = "gem"
            provider_name = "gem"

            def complete_chat(self, messages, max_tokens=800, temperature=0.3):
                return "reply"

        chain = ChainNarrator([No(), Yes()])
        self.assertEqual(chain.complete_chat([{"role": "user", "content": "hi"}]), "reply")
        self.assertEqual(chain.last_provider, "gem")


class TestSelectionOrder(unittest.TestCase):
    def test_build_narrator_prefers_ollama_gemini_deepseek_order(self):
        import os
        from types import SimpleNamespace

        from argus_final.services.analysis_service import AnalysisService

        settings = SimpleNamespace(
            ollama_enabled=True,
            ollama_base_url="http://localhost:11434",
            ollama_model="gemma4",
            ollama_timeout=6,
            gemini_api_key="g-key",
            gemini_model="gemini-3.5-flash-lite",
            deepseek_api_key="d-key",
            deepseek_model="deepseek-v4-flash",
            openrouter_api_key="REPLACE_WITH_OPENROUTER_API_KEY",
            openrouter_model="openrouter/auto",
        )
        narrator = AnalysisService._build_narrator(settings)
        self.assertIsInstance(narrator, ChainNarrator)
        names = [getattr(n, "provider_name", None) for n in narrator._chain]
        self.assertEqual(names, ["ollama", "gemini", "deepseek"])

    def test_no_credentials_gives_template(self):
        from types import SimpleNamespace

        from argus_final.services.analysis_service import AnalysisService

        settings = SimpleNamespace(
            ollama_enabled=False,
            gemini_api_key="",
            deepseek_api_key="REPLACE_WITH_DEEPSEEK_API_KEY",
            openrouter_api_key="REPLACE_WITH_OPENROUTER_API_KEY",
        )
        narrator = AnalysisService._build_narrator(settings)
        self.assertIsInstance(narrator, TemplateNarrator)


def _sample_analysis():
    return {
        "symbol": "COMB.N0000",
        "indicator_vote": {"signal": "BULLISH", "score": 0.3, "confidence": 0.7, "drivers": ["trend"]},
        "confidence": {"score": 0.78, "label": "HIGH", "penalties": {}, "reasons": []},
        "volatility": {"ewma_daily_vol": 0.012, "var_95": 0.021, "risk_level": "MODERATE"},
        "arima": {"order": [1, 1, 1], "forecast": [1.0, 1.0, 1.0], "beats_naive": True},
        "drawdown": {"current_pct": -1.2, "max_pct": -18.0, "duration_days": 40},
        "regime": {"trend": "UP", "volatility": "HIGH", "liquidity": "NORMAL"},
    }


if __name__ == "__main__":
    unittest.main()
