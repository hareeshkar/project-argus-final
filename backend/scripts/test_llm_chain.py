#!/usr/bin/env python3
"""Live verification of the Ollama -> Gemini -> DeepSeek fallback chain.

Run from backend/:  python3 scripts/test_llm_chain.py
Requires .env.local with GEMINI_API_KEY (and optionally DEEPSEEK_API_KEY).
Ollama steps fail fast (and fall through) when no local server is running.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from argus_final.core.settings import Settings  # noqa: E402  (loads .env.local on import)
from argus_final.llm import (  # noqa: E402
    ChainNarrator,
    DeepSeekNarrator,
    GeminiNarrator,
    OllamaNarrator,
)

SAMPLE = {
    "symbol": "COMB.N0000",
    "indicator_vote": {
        "signal": "BULLISH",
        "score": 0.34,
        "confidence": 0.78,
        "drivers": ["trend UP", "arima positive", "liquidity normal"],
    },
    "confidence": {"score": 0.78, "label": "HIGH", "penalties": {"flat_high_low": 0.1}, "reasons": []},
    "volatility": {"ewma_daily_vol": 0.012, "var_95": 0.021, "var_99": 0.038, "risk_level": "MODERATE"},
    "arima": {"order": [1, 1, 1], "forecast": [132.4, 132.8, 133.1], "beats_naive": True,
              "forecast_confidence": 0.7},
    "drawdown": {"current_pct": -1.2, "max_pct": -18.0, "duration_days": 40},
    "regime": {"trend": "UP", "volatility": "HIGH", "liquidity": "NORMAL"},
    "trend": {"direction": "UP", "r_squared": 0.64},
}


def main():
    settings = Settings()

    print("=" * 62)
    print("1) Gemini raw generateContent (JSON mode)")
    gemini = GeminiNarrator(api_key=settings.gemini_api_key, model=settings.gemini_model)
    raw = gemini._generate(
        "Reply with ONLY a JSON object.",
        [("user", 'Return {"ok": true, "model_says": "hello"}')],
        max_tokens=100,
        temperature=0,
        json_mode=True,
    )
    parsed = json.loads(raw)
    assert parsed["ok"] is True, parsed
    print(f"   PASS raw JSON mode -> {parsed}")

    print("=" * 62)
    print("2) GeminiNarrator.explain, simple mode")
    simple = gemini.explain("COMB.N0000", SAMPLE, copy_mode="simple")
    assert simple["headline"], "empty headline"
    print(f"   headline   : {simple['headline']}")
    print(f"   summary    : {simple['summary'][:110]}")
    print(f"   risk_notes : {simple['risk_notes'][:2]}")
    print(f"   disclaimer : {simple['disclaimer'][:60]}")

    print("=" * 62)
    print("3) GeminiNarrator.explain, experience mode")
    expert = gemini.explain("COMB.N0000", SAMPLE, copy_mode="experience")
    assert expert["headline"], "empty headline"
    print(f"   headline   : {expert['headline']}")
    print(f"   summary    : {expert['summary'][:110]}")

    print("=" * 62)
    print("4) ChainNarrator: ollama (down?) -> gemini -> deepseek")
    members = [OllamaNarrator(model=settings.ollama_model, timeout=settings.ollama_timeout)]
    if settings.gemini_api_key:
        members.append(GeminiNarrator(api_key=settings.gemini_api_key, model=settings.gemini_model))
    if settings.deepseek_api_key != "REPLACE_WITH_DEEPSEEK_API_KEY":
        members.append(DeepSeekNarrator(api_key=settings.deepseek_api_key, model=settings.deepseek_model))
    chain = ChainNarrator(members)
    print(f"   chain order: {[getattr(m, 'provider_name', m.model) for m in members]}")
    result = chain.explain("COMB.N0000", SAMPLE, copy_mode="simple")
    print(f"   served by  : {chain.last_provider} ({chain.model})")
    print(f"   headline   : {result['headline']}")

    print("=" * 62)
    print("5) ChainNarrator.complete_chat (chat path)")
    reply = chain.complete_chat(
        [
            {"role": "system", "content": "Answer in one short sentence."},
            {"role": "user", "content": "In one sentence, what does VaR 95 mean for a stock position?"},
        ]
    )
    print(f"   served by  : {chain.last_provider}")
    print(f"   reply      : {reply[:150]}")

    print("=" * 62)
    print("ALL LIVE CHECKS PASSED")


if __name__ == "__main__":
    main()
