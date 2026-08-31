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


class ExpertNarrator:
    """Deterministic technical narrative for experience mode."""

    model = "deterministic_expert_template"

    def explain(self, symbol: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        vote = analysis["indicator_vote"]
        confidence = analysis["confidence"]
        volatility = analysis["volatility"]
        arima = analysis["arima"]
        drawdown = analysis.get("drawdown", {})
        regime = analysis.get("regime", {})

        signal = vote.get("signal", "NEUTRAL")
        label = confidence.get("label", "MODERATE")
        risk_level = volatility.get("risk_level", "MODERATE")
        short = symbol.split(".")[0]
        model_used = arima.get("model_used", "fallback")
        beats = arima.get("beats_naive", False)
        fc_conf = arima.get("forecast_confidence", "LOW")
        vol_pct = volatility.get("daily_volatility_pct", 0)
        hist_var = volatility.get("historical_var_95_pct", 0)

        risk_notes = [
            f"Daily volatility (EWMA σ): {vol_pct:.2f}%; Historical VaR 95: {hist_var:.2f}%.",
            f"Current drawdown: {drawdown.get('current_drawdown_pct', 0):.2f}% · max drawdown: {drawdown.get('max_drawdown_pct', 0):.2f}%.",
        ]
        if regime.get("liquidity_regime") == "THIN":
            risk_notes.append("liquidity_regime=THIN — lower volume percentile.")
        if not beats:
            risk_notes.append(
                f"ARIMA {model_used} FAILS NAIVE baseline; forecast_confidence={fc_conf}."
            )
        lb_p = arima.get("residual_white_noise_pvalue")
        if lb_p is not None:
            risk_notes.append(f"Ljung-Box residual white-noise p-value: {lb_p:.4f}.")

        return {
            "headline": f"{short}: {signal} · confidence {label} · risk {risk_level}",
            "summary": (
                f"{model_used} selected (order {arima.get('selected_order', 'n/a')}); "
                f"beats_naive={beats}; forecast_confidence={fc_conf}. "
                f"EWMA σ={vol_pct:.2f}%; ensemble signal={signal} @ score {vote.get('score', 0):.2f}."
            ),
            "risk_notes": risk_notes[:4],
            "confidence_explanation": (
                f"Confidence {label} ({confidence.get('score', 0):.2f}); "
                f"penalties: {len(confidence.get('reasons', []))}."
            ),
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
        f"Confidence: {confidence.get('label', 'n/a')} ({_safe_num(confidence.get('score'))} out of 1)",
        f"Confidence reasons: {'; '.join(confidence.get('reasons') or []) or 'none'}",
        f"Confidence penalties (each reduces score): {confidence.get('penalties') or {}}",
        f"Vote drivers: {'; '.join(vote.get('drivers') or []) or 'none'}",
        f"Vote confidence weight: {_safe_num(vote.get('confidence'))}",
        f"Vote components — trend: {_safe_num(components.get('trend_score'))}, "
        f"volatility: {_safe_num(components.get('volatility_score'))}, "
        f"liquidity: {_safe_num(components.get('liquidity_score'))}, "
        f"anomaly: {_safe_num(components.get('anomaly_score'))}",
        "",
        "=== ARIMA forecast ===",
        f"Model: {arima.get('model_used', 'n/a')} order {arima.get('selected_order', 'n/a')}",
        f"Candidate models: {arima.get('candidate_models', [])}",
        f"AIC: {_safe_num(arima.get('aic'))}, AICc: {_safe_num(arima.get('aicc'))}, BIC: {_safe_num(arima.get('bic'))}",
        f"Forecast trend label: {arima.get('trend', 'n/a')}",
        f"Beats naive baseline: {arima.get('beats_naive', 'n/a')}",
        f"Forecast confidence: {arima.get('forecast_confidence', 'n/a')}",
        f"Residual white-noise p-value: {_safe_num(arima.get('residual_white_noise_pvalue'))}",
        f"3-day forecast (LKR): {forecast}",
        f"95% CI lower: {ci.get('lower', [])}",
        f"95% CI upper: {ci.get('upper', [])}",
        "",
        "=== Risk & volatility ===",
        f"Daily volatility (EWMA σ): {_safe_num(volatility.get('daily_volatility_pct'))}%",
        f"EWMA lambda: {_safe_num(volatility.get('ewma_lambda'))}",
        f"Risk level: {volatility.get('risk_level', 'n/a')}",
        f"EWMA VaR 95 / Bad Day Loss (95%) [var_95_pct]: {_safe_num(volatility.get('var_95_pct'))}%",
        f"Historical VaR 95 / Worst Day (95%) [historical_var_95_pct]: {_safe_num(volatility.get('historical_var_95_pct'))}%",
        f"Historical VaR 99 / Very Bad Day (99%) [historical_var_99_pct]: {_safe_num(volatility.get('historical_var_99_pct'))}%",
        f"Parkinson volatility: {_safe_num(volatility.get('parkinson_volatility_pct'))}%",
        f"Volatility percentile (symbol-relative): {_safe_num(volatility.get('volatility_percentile'))}",
        f"Flat high-low ratio: {_safe_num(volatility.get('flat_high_low_ratio'))}",
        f"Max drawdown: {_safe_num(drawdown.get('max_drawdown_pct'))}%",
        f"Current drawdown: {_safe_num(drawdown.get('current_drawdown_pct'))}%",
        f"Drawdown duration (days): {drawdown.get('drawdown_duration_days', 'n/a')}",
        "",
        "=== Trend & regime ===",
        f"Linear trend: {trend.get('trend_direction', 'n/a')} (R² {_safe_num(trend.get('r_squared'))})",
        f"Regime — trend: {regime.get('trend_regime', 'n/a')}, "
        f"volatility: {regime.get('volatility_regime', 'n/a')}, "
        f"liquidity: {regime.get('liquidity_regime', 'n/a')}",
        "",
        "=== Anomaly flags ===",
        f"Anomalous: {anomaly.get('is_anomalous', False)}",
        f"Return anomaly: {anomaly.get('return_anomaly', False)}, price anomaly: {anomaly.get('price_anomaly', False)}, volume anomaly: {anomaly.get('volume_anomaly', False)}",
        f"Return z-score: {_safe_num(anomaly.get('return_zscore'))}, modified return z-score: {_safe_num(anomaly.get('modified_return_zscore'))}",
        f"Price z-score: {_safe_num(anomaly.get('price_zscore'))}, modified price z-score: {_safe_num(anomaly.get('modified_price_zscore'))}",
        f"Volume z-score: {_safe_num(anomaly.get('volume_zscore'))}, modified volume z-score: {_safe_num(anomaly.get('modified_volume_zscore'))}",
        f"Lookback days: {anomaly.get('lookback_days', 'n/a')}",
        "",
        "Constraints: CSE public REST history is ~120–240 daily bars. This is research analytics only — not investment advice.",
    ]
    return "\n".join(lines)


def build_narration_prompts(symbol: str, analysis: Dict[str, Any], copy_mode: str):
    """Shared narration prompt pair used by every provider translator."""
    context = build_analysis_context(symbol, analysis)

    if copy_mode == "experience":
        system_prompt = (
            "You are Argus, a quantitative CSE research analyst.\n\n"
            "WRITING RULES:\n"
            "- Use precise finance terminology: ARIMA, EWMA VaR, Historical VaR, Parkinson, drawdown, regime.\n"
            "- Reference model outputs directly (model_used, beats_naive, forecast_confidence, risk_level).\n"
            "- Keep signal enums as BULLISH/BEARISH/NEUTRAL and confidence as HIGH/MODERATE/LOW.\n"
            "- Never say buy, sell, hold, or recommend any action.\n"
            "- Use the stock short code (e.g. COMB) not the full symbol."
        )
        user_prompt = (
            f"{context}\n\n"
            "Write a concise technical research summary from the evidence above.\n"
            "Reply with ONLY valid JSON (no markdown, no text outside JSON):\n"
            "{\n"
            '  "headline": "Technical headline with signal, confidence, risk_level",\n'
            '  "summary": "2 sentences with ARIMA order, beats_naive, EWMA σ, VaR metrics.",\n'
            '  "risk_notes": ["2-4 bullets with technical metrics and regime flags"],\n'
            '  "confidence_explanation": "One sentence citing confidence label, score, penalty count",\n'
            '  "disclaimer": "Research analytics only. Not investment advice."\n'
            "}"
        )
    else:
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
    return system_prompt, user_prompt


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

    def explain(self, symbol: str, analysis: Dict[str, Any], copy_mode: str = "simple") -> Dict[str, Any]:
        return self._call(symbol, analysis, copy_mode=copy_mode)

    def complete_chat(self, messages, max_tokens: int = 800, temperature: float = 0.3) -> str:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if self._extra_headers:
            kwargs["extra_headers"] = self._extra_headers
        completion = self._client.chat.completions.create(**kwargs)
        return (completion.choices[0].message.content or "").strip()

    def _call(self, symbol: str, analysis: Dict[str, Any], copy_mode: str = "simple") -> Dict[str, Any]:
        system_prompt, user_prompt = build_narration_prompts(symbol, analysis, copy_mode)

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

    provider_name = "deepseek"

    def __init__(self, api_key: str, model: str = "deepseek-v4-flash"):
        super().__init__(api_key=api_key, model=model, base_url="https://api.deepseek.com")


class OpenRouterNarrator(OpenAICompatibleNarrator):
    """LLM narrative via OpenRouter API using the OpenAI-compatible SDK."""

    provider_name = "openrouter"

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


class OllamaNarrator:
    """Local LLM narrator (Gemma family) via the Ollama native chat API.

    First link in the fallback chain: when Ollama is not running the request
    fails fast on connection and the chain moves to the next provider.
    """

    provider_name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gemma4",
        timeout: float = 6.0,
        transport: Optional[Any] = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        import httpx

        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            resp = client.post(f"{self.base_url}{path}", json=payload)
            resp.raise_for_status()
            return resp.json()

    def explain(self, symbol: str, analysis: Dict[str, Any], copy_mode: str = "simple") -> Dict[str, Any]:
        system_prompt, user_prompt = build_narration_prompts(symbol, analysis, copy_mode)
        content = self.complete_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=900,
            temperature=0.25,
            json_mode=True,
        )
        return self._parse_explanation(content)

    def complete_chat(self, messages, max_tokens: int = 800, temperature: float = 0.3, json_mode: bool = False) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # Disable thinking for gemma4 to keep responses concise and within
            # token budget (thinking can consume 200+ tokens before content).
            "think": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        data = self._post("/api/chat", payload)
        # If thinking was enabled, content lives in message.content; thinking is separate.
        # Fallback to thinking if content is empty (should not happen with think=False).
        msg = data.get("message") or {}
        content = (msg.get("content") or "").strip()
        if not content and msg.get("thinking"):
            content = msg.get("thinking", "").strip()
        return content

    @staticmethod
    def _parse_explanation(content: str) -> Dict[str, Any]:
        parsed = extract_json_from_llm(content)
        return {
            "headline": parsed.get("headline", ""),
            "summary": parsed.get("summary", ""),
            "risk_notes": parsed.get("risk_notes", []),
            "confidence_explanation": parsed.get("confidence_explanation", ""),
            "disclaimer": parsed.get("disclaimer", "Research analytics only. Not investment advice."),
        }


class GeminiNarrator:
    """LLM narrator via the native Google Gemini generateContent API.

    Translates the internal OpenAI-style semantic call into Gemini wire format:
    system message -> systemInstruction.parts, assistant role -> "model",
    max_tokens -> maxOutputTokens, JSON mode -> responseMimeType.
    """

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash-lite",
        timeout: float = 30.0,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        transport: Optional[Any] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def _generate(
        self,
        system_instruction: str,
        turns,
        max_tokens: int,
        temperature: float,
        json_mode: bool = False,
    ) -> str:
        import httpx

        contents = []
        for role, content in turns:
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})

        generation_config: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        body: Dict[str, Any] = {"contents": contents, "generationConfig": generation_config}
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{self.base_url}/models/{self.model}:generateContent"
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            resp = client.post(url, json=body, headers={"x-goog-api-key": self.api_key})

        try:
            data = resp.json()
        except ValueError:
            raise RuntimeError(f"gemini non-JSON response (http {resp.status_code})")

        if resp.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise RuntimeError(
                f"gemini api error {err.get('code', resp.status_code)} {err.get('status', '')}: "
                f"{err.get('message', str(data)[:200])}"
            )
        if data.get("promptFeedback", {}).get("blockReason"):
            raise RuntimeError(f"gemini blocked prompt: {data['promptFeedback']['blockReason']}")

        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("gemini returned no candidates")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise RuntimeError(
                f"gemini empty response (finishReason={candidates[0].get('finishReason')})"
            )
        return text

    def explain(self, symbol: str, analysis: Dict[str, Any], copy_mode: str = "simple") -> Dict[str, Any]:
        system_prompt, user_prompt = build_narration_prompts(symbol, analysis, copy_mode)
        text = self._generate(
            system_prompt,
            [("user", user_prompt)],
            max_tokens=900,
            temperature=0.25,
            json_mode=True,
        )
        parsed = extract_json_from_llm(text)
        return {
            "headline": parsed.get("headline", ""),
            "summary": parsed.get("summary", ""),
            "risk_notes": parsed.get("risk_notes", []),
            "confidence_explanation": parsed.get("confidence_explanation", ""),
            "disclaimer": parsed.get("disclaimer", "Research analytics only. Not investment advice."),
        }

    def complete_chat(self, messages, max_tokens: int = 800, temperature: float = 0.3) -> str:
        system_instruction = ""
        turns = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue
            if role == "system":
                system_instruction = content
                continue
            turns.append((role, content))
        return self._generate(
            system_instruction, turns, max_tokens=max_tokens, temperature=temperature, json_mode=False
        ).strip()


class ChainNarrator:
    """Fallback chain over several narrators: tries each provider in order.

    Records the provider that actually answered so lineage stays honest.
    """

    def __init__(self, narrators):
        if not narrators:
            raise ValueError("ChainNarrator requires at least one narrator")
        self._chain = list(narrators)
        self.model = self._chain[0].model
        self.last_provider = None

    def explain(self, symbol: str, analysis: Dict[str, Any], copy_mode: str = "simple") -> Dict[str, Any]:
        errors = []
        for narrator in self._chain:
            try:
                explanation = narrator.explain(symbol, analysis, copy_mode=copy_mode)
                self.model = getattr(narrator, "model", self.model)
                self.last_provider = getattr(narrator, "provider_name", narrator.model)
                return explanation
            except Exception as exc:
                errors.append(f"{getattr(narrator, 'provider_name', narrator.model)}: {exc}")
                logger.warning("narrator chain fallback: %s", errors[-1])
        raise RuntimeError("all narrators failed: " + " | ".join(errors))

    def complete_chat(self, messages, max_tokens: int = 800, temperature: float = 0.3) -> str:
        errors = []
        for narrator in self._chain:
            try:
                reply = narrator.complete_chat(messages, max_tokens=max_tokens, temperature=temperature)
                self.model = getattr(narrator, "model", self.model)
                self.last_provider = getattr(narrator, "provider_name", narrator.model)
                return reply
            except Exception as exc:
                errors.append(f"{getattr(narrator, 'provider_name', narrator.model)}: {exc}")
                logger.warning("chat chain fallback: %s", errors[-1])
        raise RuntimeError("all chat providers failed: " + " | ".join(errors))
