from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class LLMNarrator(Protocol):
    model: str

    def explain(self, symbol: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        ...


class TemplateNarrator:
    """Deterministic narrative fallback. LLMs are optional presentation layers."""

    model = "deterministic_template"

    def explain(self, symbol: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        vote = analysis["indicator_vote"]
        confidence = analysis["confidence"]
        volatility = analysis["volatility"]
        arima = analysis["arima"]
        drawdown = analysis.get("drawdown", {})
        regime = analysis.get("regime", {})

        signal = vote.get("signal", "NEUTRAL")
        lean = {
            "BULLISH": "the numbers lean slightly positive",
            "BEARISH": "the numbers lean slightly negative",
            "NEUTRAL": "the numbers are mixed — no clear lean",
        }.get(signal, "the picture is mixed")

        trust = {
            "HIGH": "We have good-quality data and the models agree reasonably well.",
            "MODERATE": "The data is usable, but some model checks raised small warnings.",
            "LOW": "Treat this cautiously — data or model quality is limited.",
        }.get(confidence.get("label", "MODERATE"), "Trust is moderate.")

        short = symbol.split(".")[0]
        vol_pct = volatility.get("daily_volatility_pct", 0)
        risk_notes = [
            f"Typical daily price swing is about {vol_pct:.1f}%.",
            f"Currently {abs(drawdown.get('current_drawdown_pct', 0)):.1f}% below its recent peak."
            if drawdown.get("current_drawdown_pct")
            else "Drawdown is within a normal range for this window.",
        ]
        if regime.get("liquidity_regime") == "THIN":
            risk_notes.append("Trading has been thinner than usual — prices can move more on small volume.")
        if not arima.get("beats_naive"):
            risk_notes.append("The short-term price forecast did not beat a simple baseline — expect uncertainty.")

        return {
            "headline": f"{short}: {signal.lower()} lean, {confidence.get('label', 'moderate').lower()} trust",
            "summary": (
                f"For {short}, {lean}. "
                f"Day-to-day moves have averaged about {vol_pct:.1f}% recently."
            ),
            "risk_notes": risk_notes[:4],
            "confidence_explanation": trust,
            "disclaimer": "Research analytics only. Not investment advice.",
        }


def extract_json_from_llm(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from model output, tolerating prose and truncation."""
    import re

    text = text.strip()

    fence = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, start)
            return obj  # type: ignore[return-value]
        except json.JSONDecodeError:
            pass

    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass

    result: Dict[str, Any] = {}
    m = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if m:
        result["summary"] = m.group(1)
    m = re.search(r'"risk_notes"\s*:\s*\[([^\]]*)\]', text)
    if m:
        result["risk_notes"] = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
    m = re.search(r'"confidence_explanation"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if m:
        result["confidence_explanation"] = m.group(1)
    m = re.search(r'"disclaimer"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if m:
        result["disclaimer"] = m.group(1)
    if result:
        return result

    raise ValueError(f"No valid JSON object found in model response: {text[:200]!r}")


def _safe_num(value: Any, digits: int = 2) -> str:
    try:
        if value is None:
            return "n/a"
        return f"{float(value):.{digits}f}"
    except Exception:
        return "n/a"


def build_analysis_context(symbol: str, analysis: Dict[str, Any]) -> str:
    """Structured evidence block for LLM narrative generation."""
    arima = analysis.get("arima", {})
    volatility = analysis.get("volatility", {})
    trend = analysis.get("trend", {})
    regime = analysis.get("regime", {})
    anomaly = analysis.get("anomaly", {})
    drawdown = analysis.get("drawdown", {})
    confidence = analysis.get("confidence", {})
    vote = analysis.get("indicator_vote", {})
    components = vote.get("components", {})

    forecast = arima.get("forecast") or []
    ci = arima.get("confidence_interval") or {}

    lines = [
        f"Symbol: {symbol}",
        f"Data points (daily): {analysis.get('data_points', 'n/a')}",
        "",
        "=== Signal & confidence ===",
        f"Ensemble signal: {vote.get('signal', 'n/a')} (score {_safe_num(vote.get('score'))}, range -1 bearish to +1 bullish)",
        f"Confidence: {confidence.get('label', 'n/a')} ({_safe_num(confidence.get('score'))})",
        f"Confidence reasons: {'; '.join(confidence.get('reasons') or []) or 'none'}",
        f"Vote components — trend: {_safe_num(components.get('trend_score'))}, "
        f"volatility: {_safe_num(components.get('volatility_score'))}, "
        f"liquidity: {_safe_num(components.get('liquidity_score'))}, "
        f"anomaly: {_safe_num(components.get('anomaly_score'))}",
        "",
        "=== ARIMA forecast ===",
        f"Model: {arima.get('model_used', 'n/a')} order {arima.get('selected_order', 'n/a')}",
        f"Forecast trend label: {arima.get('trend', 'n/a')}",
        f"Beats naive baseline: {arima.get('beats_naive', 'n/a')}",
        f"Forecast confidence: {arima.get('forecast_confidence', 'n/a')}",
        f"3-day forecast (LKR): {forecast}",
        f"95% CI lower: {ci.get('lower', [])}",
        f"95% CI upper: {ci.get('upper', [])}",
        "",
        "=== Risk & volatility ===",
        f"Daily volatility (EWMA): {_safe_num(volatility.get('daily_volatility_pct'))}%",
        f"Risk level: {volatility.get('risk_level', 'n/a')}",
        f"VaR 95 (EWMA): {_safe_num(volatility.get('var_95_pct'))}%",
        f"Historical VaR 95: {_safe_num(volatility.get('historical_var_95_pct'))}%",
        f"Max drawdown: {_safe_num(drawdown.get('max_drawdown_pct'))}%",
        f"Current drawdown: {_safe_num(drawdown.get('current_drawdown_pct'))}%",
        "",
        "=== Trend & regime ===",
        f"Linear trend: {trend.get('trend_direction', 'n/a')} (R² {_safe_num(trend.get('r_squared'))})",
        f"Regime — trend: {regime.get('trend_regime', 'n/a')}, "
        f"volatility: {regime.get('volatility_regime', 'n/a')}, "
        f"liquidity: {regime.get('liquidity_regime', 'n/a')}",
        "",
        "=== Anomaly flags ===",
        f"Anomalous: {anomaly.get('is_anomalous', False)}",
        f"Return z-score: {_safe_num(anomaly.get('return_zscore'))}",
        f"Volume z-score: {_safe_num(anomaly.get('volume_zscore'))}",
        "",
        "Constraints: CSE public REST history is ~120–240 daily bars. This is research analytics only — not investment advice.",
    ]
    return "\n".join(lines)


class OpenAICompatibleNarrator:
    """Shared OpenAI-format chat narrator for DeepSeek, OpenRouter, etc."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 30.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        from openai import OpenAI

        self.api_key = api_key
        self.model = model
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._extra_headers = extra_headers or {}
        self._fallback = TemplateNarrator()

    def explain(self, symbol: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._call(symbol, analysis)
        except Exception as exc:
            logger.warning("%s call failed (%s), falling back to template", self.model, exc)
            return self._fallback.explain(symbol, analysis)

    def _call(self, symbol: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        context = build_analysis_context(symbol, analysis)

        system_prompt = (
            "You are Argus, explaining Colombo Stock Exchange stock analytics to a regular investor — "
            "not a quant or data scientist.\n\n"
            "WRITING RULES:\n"
            "- Use short, everyday sentences. Avoid jargon.\n"
            "- Do NOT use these words unless you immediately explain them in plain English: "
            "ARIMA, VaR, EWMA, z-score, ensemble, baseline, residual, parametric.\n"
            "- Translate signals: BULLISH = data tilts positive, BEARISH = data tilts negative, "
            "NEUTRAL = mixed / no clear direction.\n"
            "- Translate confidence: HIGH = trustworthy data, MODERATE = usable with caveats, "
            "LOW = treat cautiously.\n"
            "- Mention specific numbers from the evidence (prices, %, drawdown) when helpful.\n"
            "- Be balanced — include one positive and one cautionary point when both exist.\n"
            "- Never say buy, sell, hold, or recommend any action.\n"
            "- Use the stock short code (e.g. COMB) not the full symbol."
        )

        user_prompt = (
            f"{context}\n\n"
            "Write a friendly research summary from the evidence above.\n"
            "Reply with ONLY valid JSON (no markdown, no text outside JSON):\n"
            "{\n"
            '  "headline": "6-12 word plain-English headline (e.g. COMB: mixed signals, trust is high)",\n'
            '  "summary": "Exactly 2 short sentences. First: overall lean and why. Second: key risk or caveat.",\n'
            '  "risk_notes": ["2-3 bullets, max 15 words each, plain language only"],\n'
            '  "confidence_explanation": "One sentence a non-expert understands — why trust is high/moderate/low",\n'
            '  "disclaimer": "Research analytics only. Not investment advice."\n'
            "}"
        )

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 900,
            "temperature": 0.25,
        }
        if self._extra_headers:
            kwargs["extra_headers"] = self._extra_headers

        completion = self._client.chat.completions.create(**kwargs)
        content = completion.choices[0].message.content or ""
        parsed = extract_json_from_llm(content)
        return {
            "headline": parsed.get("headline", ""),
            "summary": parsed.get("summary", ""),
            "risk_notes": parsed.get("risk_notes", []),
            "confidence_explanation": parsed.get("confidence_explanation", ""),
            "disclaimer": parsed.get("disclaimer", "Research analytics only. Not investment advice."),
        }


class DeepSeekNarrator(OpenAICompatibleNarrator):
    """LLM narrative via DeepSeek API (OpenAI-compatible). Default model: deepseek-v4-flash."""

    def __init__(self, api_key: str, model: str = "deepseek-v4-flash"):
        super().__init__(api_key=api_key, model=model, base_url="https://api.deepseek.com")


class OpenRouterNarrator(OpenAICompatibleNarrator):
    """LLM narrative via OpenRouter API using the OpenAI-compatible SDK."""

    def __init__(self, api_key: str, model: str = "openrouter/free"):
        super().__init__(
            api_key=api_key,
            model=model,
            base_url="https://openrouter.ai/api/v1",
            extra_headers={
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "Project Argus CSE Analytics",
            },
        )
