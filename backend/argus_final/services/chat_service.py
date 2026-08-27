from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from argus_final.copy import normalize_copy_mode
from argus_final.copy.chat import build_chat_copy_context
from argus_final.copy.glossary import build_dual_metric_glossary_block
from argus_final.core.settings import Settings
from argus_final.llm.adapter import build_analysis_context
from argus_final.llm import DeepSeekNarrator, OpenRouterNarrator
from argus_final.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

RAG_SOURCE_KEYS = (
    "copy_mode_context",
    "math_results",
    "metric_glossary_dual",
    "confidence",
    "indicator_vote",
    "microstructure",
    "order_book",
    "intraday_context",
    "llm_explanation",
    "data_lineage",
    "quality_flags",
    "price_history",
    "node_status",
    "full_analysis_payload",
)

# Section markers expected when a full dashboard analysis payload is supplied.
FULL_RAG_SECTION_MARKERS = (
    "=== UI copy mode (Simple vs Experience) ===",
    "Symbol:",
    "=== Signal & confidence ===",
    "=== Dashboard metrics (dual labels, values, meanings) ===",
    "=== Dashboard summary ===",
    "=== Confidence breakdown ===",
    "=== Indicator vote breakdown ===",
    "=== ARIMA model ===",
    "=== Volatility model ===",
    "=== Data lineage ===",
    "=== Microstructure / live price ===",
    "=== Quality flags ===",
    "=== Full analysis payload (complete JSON) ===",
)


def rag_context_stats(context: str) -> Dict[str, Any]:
    """Summarize assembled RAG evidence for tests and API transparency."""
    sections = [
        line.removeprefix("=== ").removesuffix(" ===").strip()
        for line in context.splitlines()
        if line.startswith("=== ") and line.endswith(" ===")
    ]
    return {
        "char_count": len(context),
        "section_count": len(sections),
        "sections": sections,
    }


def _compact_json_block(title: str, data: Any) -> str:
    if not data:
        return ""
    return f"=== {title} ===\n{json.dumps(data, separators=(',', ':'), default=str)}"


def _resolve_analysis_query(
    message: str,
    symbol: Optional[str],
    analysis_payload: Optional[Dict[str, Any]],
    refresh_analysis: bool,
    analysis_service: AnalysisService,
) -> str:
    """Pick an analyze query — on refresh, re-run the dashboard symbol, not the chat message."""
    if refresh_analysis or analysis_payload:
        sym = (analysis_payload or {}).get("symbol") or symbol
        if sym:
            prior = (analysis_payload or {}).get("query")
            if prior and str(prior).strip().lower().startswith("analyze"):
                return str(prior).strip()
            return f"Analyze {str(sym).split('.')[0]}"
    if symbol:
        return f"Analyze {symbol.split('.')[0]}"
    extracted = analysis_service.extract_symbol(message)
    if re.search(r"[A-Za-z]{3,4}", message):
        return message
    return f"Analyze {extracted.split('.')[0]}"


def _safe_json_block(title: str, data: Any) -> str:
    if not data:
        return ""
    return f"=== {title} ===\n{json.dumps(data, indent=2, default=str)}"


def build_rag_context(symbol: str, payload: Dict[str, Any], copy_mode: str = "simple") -> str:
    """Assemble retrieval context from accumulated analysis payload (analysis-backed RAG)."""
    mode = normalize_copy_mode(copy_mode)
    math = payload.get("math_results") or {}
    # Prefer top-level confidence/vote (localized reasons) while keeping full math for numbers.
    confidence = payload.get("confidence") or math.get("confidence") or {}
    vote = payload.get("indicator_vote") or math.get("indicator_vote") or {}
    math_for_context = {
        **math,
        "confidence": confidence,
        "indicator_vote": vote,
    }

    blocks = [
        build_chat_copy_context(mode, payload),
        build_analysis_context(symbol, math_for_context),
        build_dual_metric_glossary_block(math, active_mode=mode),
    ]

    lineage = payload.get("data_lineage") or {}
    micro = payload.get("microstructure") or {}
    order_book = payload.get("order_book") or {}
    intraday = payload.get("intraday_context") or {}
    llm = payload.get("llm_explanation")
    quality = payload.get("quality_flags") or {}
    price_history = payload.get("price_history") or {}
    node_status = payload.get("node_status") or {}

    blocks.append(
        _safe_json_block(
            "Dashboard summary",
            {
                "query": payload.get("query"),
                "symbol": symbol,
                "company_name": payload.get("company_name"),
                "timestamp": payload.get("timestamp"),
                "processing_time": payload.get("processing_time"),
                "data_source_mode": payload.get("data_source_mode"),
                "copy_mode": payload.get("copy_mode") or mode,
                "ensemble_signal": vote.get("signal") or payload.get("ensemble_signal"),
                "ensemble_score": vote.get("score"),
                "daily_score": vote.get("daily_score"),
                "intraday_nudge": vote.get("intraday_nudge"),
                "confidence_label": confidence.get("label"),
                "confidence_score": confidence.get("score"),
                "confidence_penalties": confidence.get("penalties"),
                "confidence_reasons": confidence.get("reasons"),
                "indicator_vote_score": vote.get("score"),
                "indicator_vote_components": vote.get("components"),
                "indicator_vote_drivers": vote.get("drivers"),
                "latest_price": micro.get("latest_price"),
                "vwap": micro.get("vwap"),
                "trade_intensity": micro.get("trade_intensity"),
                "price_momentum": micro.get("price_momentum"),
                "order_book_bids": order_book.get("bids"),
                "order_book_asks": order_book.get("asks"),
                "order_book_pressure": order_book.get("pressure"),
                "order_book_spread": order_book.get("spread_estimate"),
                "intraday_context_source": intraday.get("source"),
                "intraday_available": intraday.get("available"),
                "intraday_price_divergence_pct": intraday.get("price_divergence_pct"),
                "intraday_vwap_deviation_pct": intraday.get("vwap_deviation_pct"),
                "intraday_is_stale": intraday.get("is_stale"),
                "quality_warnings": quality.get("warnings"),
                "overall_health": math.get("overall_health"),
            },
        )
    )
    blocks.append(_safe_json_block("Confidence breakdown", confidence))
    blocks.append(_safe_json_block("Indicator vote breakdown", vote))
    blocks.append(_safe_json_block("ARIMA model", math.get("arima")))
    blocks.append(_safe_json_block("Volatility model", math.get("volatility")))
    blocks.append(_safe_json_block("Drawdown model", math.get("drawdown")))
    blocks.append(_safe_json_block("Trend model", math.get("trend")))
    blocks.append(_safe_json_block("Regime model", math.get("regime")))
    blocks.append(_safe_json_block("Anomaly model", math.get("anomaly")))
    blocks.append(_safe_json_block("Data lineage", lineage))
    blocks.append(_safe_json_block("Node status", node_status))
    blocks.append(_safe_json_block("Microstructure / live price", micro))
    blocks.append(_safe_json_block("Order book", order_book))
    blocks.append(_safe_json_block("Intraday context", intraday))
    blocks.append(_safe_json_block("Price history (chart window)", price_history))
    blocks.append(_safe_json_block("Quality flags", quality))
    if llm:
        blocks.append(_safe_json_block("Prior analyst summary", llm))
    blocks.append(_compact_json_block("Full analysis payload (complete JSON)", payload))

    return "\n\n".join(block for block in blocks if block)


def _build_chat_client(settings: Settings):
    deepseek_key = settings.deepseek_api_key
    if deepseek_key and deepseek_key != "REPLACE_WITH_DEEPSEEK_API_KEY":
        return DeepSeekNarrator(api_key=deepseek_key, model=settings.deepseek_model), settings.deepseek_model
    key = settings.openrouter_api_key
    if key and key != "REPLACE_WITH_OPENROUTER_API_KEY":
        model = settings.openrouter_model
        if model in ("openrouter/auto", ""):
            model = "openrouter/free"
        return OpenRouterNarrator(api_key=key, model=model), model
    return None, "deterministic_template"


def _chat_system_prompt(copy_mode: str, payload: Optional[Dict[str, Any]] = None) -> str:
    mode = normalize_copy_mode(copy_mode)
    copy_context = build_chat_copy_context(mode, payload or {})
    shared_rules = (
        "- Ground every answer ONLY in the EVIDENCE block; cite exact numbers (%, scores, LKR prices).\n"
        "- When the user asks what a metric or number means, use the dual-label glossary: give the "
        f"{'Experience' if mode == 'experience' else 'Simple'} label for the active UI mode, the exact value, "
        "and a clear explanation. You may mention the alternate label in parentheses.\n"
        "- If evidence is missing for a question, say what is not in the data.\n"
        "- Never recommend buy, sell, or hold.\n"
        "- End with: This is research analytics, not investment advice."
    )
    role = (
        "You are Argus Chat, a CSE research assistant grounded ONLY in the EVIDENCE block below."
        if mode == "experience"
        else "You are Argus Chat, a friendly CSE research assistant grounded ONLY in the EVIDENCE block below."
    )
    return (
        f"{role}\n\n{copy_context}\n\nRules:\n{shared_rules}\n"
        "- Keep answers concise (2-5 sentences) unless the user asks for detail."
    )


def _template_chat_reply(message: str, payload: Dict[str, Any], copy_mode: str) -> str:
    """Deterministic RAG-style fallback when no LLM API key is configured."""
    msg = message.lower()
    mode = normalize_copy_mode(copy_mode)
    symbol = payload.get("symbol", "this symbol")
    short = symbol.split(".")[0]
    math = payload.get("math_results") or {}
    confidence = payload.get("confidence") or math.get("confidence") or {}
    vote = payload.get("indicator_vote") or math.get("indicator_vote") or {}
    arima = math.get("arima") or {}
    vol = math.get("volatility") or {}
    regime = math.get("regime") or {}
    drawdown = math.get("drawdown") or {}
    llm = payload.get("llm_explanation")
    summary = ""
    if isinstance(llm, dict):
        summary = llm.get("summary") or llm.get("headline") or ""
    elif isinstance(llm, str):
        summary = llm

    def _metric_reply(field: str, group: str) -> Optional[str]:
        from argus_final.copy.glossary import RISK_METRICS

        bucket = (math.get(group) or {}) if group else math
        value = bucket.get(field)
        for f, g, meta in RISK_METRICS:
            if f != field:
                continue
            copy = meta.get(mode) or meta.get("simple") or {}
            label = copy.get("label", field)
            tip = copy.get("tip", "")
            unit = meta.get("unit", "%")
            if unit == "%":
                val_txt = f"{float(value):.2f}%" if value is not None else "n/a"
            elif unit == "percentile":
                val_txt = f"{float(value):.1f}th percentile" if value is not None else "n/a"
            else:
                val_txt = str(value) if value is not None else "n/a"
            return (
                f"For {short}, **{label}** is **{val_txt}**. {tip} "
                "This is research analytics, not investment advice."
            )
        return None

    if any(w in msg for w in ("bad day", "bad day loss", "var 95", "var95", "ewma var")):
        reply = _metric_reply("var_95_pct", "volatility")
        if reply:
            return reply.replace("**", "")
    if any(w in msg for w in ("worst day", "historical var", "hist var", "95%")):
        reply = _metric_reply("historical_var_95_pct", "volatility")
        if reply:
            return reply.replace("**", "")
    if any(w in msg for w in ("very bad", "99%", "hist 99", "historical var 99")):
        reply = _metric_reply("historical_var_99_pct", "volatility")
        if reply:
            return reply.replace("**", "")
    if any(w in msg for w in ("parkinson", "range vol")):
        reply = _metric_reply("parkinson_volatility_pct", "volatility")
        if reply:
            return reply.replace("**", "")
    if any(w in msg for w in ("drawdown", "drop from peak", "largest drop", "max drawdown")):
        field = "max_drawdown_pct" if "largest" in msg or "max" in msg else "current_drawdown_pct"
        reply = _metric_reply(field, "drawdown")
        if reply:
            return reply.replace("**", "")

    if any(w in msg for w in ("confidence", "trust", "believe", "reliable")):
        penalties = confidence.get("penalties") or {}
        penalty_txt = ", ".join(f"{k}={v}" for k, v in penalties.items()) or "none"
        reasons = "; ".join(confidence.get("reasons") or []) or "no major penalties"
        return (
            f"For {short}, trust is {confidence.get('label', 'unknown')} "
            f"({confidence.get('score', 0):.2f} out of 1). Reasons: {reasons}. "
            f"Penalty breakdown: {penalty_txt}. "
            "This is research analytics, not investment advice."
        )
    if any(w in msg for w in ("risk", "volatile", "volatility")) or (
        "var" in msg and "bad day" not in msg and "worst day" not in msg
    ):
        return (
            f"For {short}, risk is rated {vol.get('risk_level', 'unknown')}. "
            f"Typical daily move ~{vol.get('daily_volatility_pct', 0):.2f}%; "
            f"Bad Day Loss (95%) / EWMA VaR ~{vol.get('var_95_pct', 0):.2f}%; "
            f"Worst Day (95%) from history ~{vol.get('historical_var_95_pct', 0):.2f}%; "
            f"Very Bad Day (99%) ~{vol.get('historical_var_99_pct', 0):.2f}%; "
            f"current drawdown ~{drawdown.get('current_drawdown_pct', 0):.2f}%. "
            "This is research analytics, not investment advice."
        )
    if any(w in msg for w in ("forecast", "arima", "predict", "price target", "tomorrow")):
        fc = arima.get("forecast") or []
        return (
            f"For {short}, the model ({arima.get('model_used', 'n/a')}) forecasts "
            f"next closes around {fc[0] if fc else 'n/a'} LKR (3-day path: {fc}). "
            f"beats_naive={arima.get('beats_naive')}. "
            "This is research analytics, not investment advice."
        )
    if any(w in msg for w in ("signal", "bullish", "bearish", "lean", "direction")):
        return (
            f"For {short}, the ensemble lean is {vote.get('signal', 'NEUTRAL')} "
            f"(score {vote.get('score', 0):.2f}). "
            "This is not a buy/sell call — research analytics only."
        )
    if any(w in msg for w in ("liquid", "volume", "thin", "trade")):
        return (
            f"For {short}, liquidity regime is {regime.get('liquidity_regime', 'unknown')} "
            f"(volume percentile {regime.get('volume_percentile', 'n/a')}). "
            "This is research analytics, not investment advice."
        )
    if any(w in msg for w in ("what does", "what's", "mean", "explain this", "explain the number")) or (
        "what is" in msg
        and not any(w in msg for w in ("risk", "confidence", "forecast", "signal", "arima"))
    ):
        glossary_block = build_dual_metric_glossary_block(math, active_mode=mode)
        if glossary_block:
            lines = [ln for ln in glossary_block.splitlines() if ln.strip() and not ln.startswith("===")]
            preview = " ".join(lines[:6])
            return (
                f"For {short}, here are the dashboard numbers from your analysis: {preview} "
                "Ask about a specific label (e.g. Bad Day Loss, Worst Day, drawdown). "
                "This is research analytics, not investment advice."
            )

    if summary:
        return f"{summary} (from computed dashboard evidence). This is research analytics, not investment advice."
    return (
        f"I have analytics loaded for {short}: signal {vote.get('signal')}, "
        f"confidence {confidence.get('label')}, risk {vol.get('risk_level')}. "
        "Ask about confidence, risk, forecast, or signal. "
        "This is research analytics, not investment advice."
    )


class ChatService:
    def __init__(self, analysis_service: AnalysisService, app_settings: Settings):
        self.analysis_service = analysis_service
        self.settings = app_settings

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        symbol: Optional[str] = None,
        analysis_payload: Optional[Dict[str, Any]] = None,
        demo_mode: Optional[bool] = None,
        copy_mode: Optional[str] = "simple",
        refresh_analysis: bool = False,
    ) -> Dict[str, Any]:
        mode = normalize_copy_mode(copy_mode)
        history = history or []
        analysis_refreshed = False

        if analysis_payload and not refresh_analysis:
            payload = analysis_payload
            sym = payload.get("symbol") or symbol or self.analysis_service.extract_symbol(message)
        else:
            sym = symbol or (analysis_payload or {}).get("symbol") or self.analysis_service.extract_symbol(message)
            query = _resolve_analysis_query(
                message, sym, analysis_payload, refresh_analysis, self.analysis_service
            )
            payload = await self.analysis_service.analyze_async(
                query,
                demo_mode=demo_mode,
                copy_mode=mode,
            )
            analysis_refreshed = True
            sym = payload.get("symbol", sym)

        context = build_rag_context(sym, payload, copy_mode=mode)
        stats = rag_context_stats(context)
        narrator, provider = _build_chat_client(self.settings)

        result_base = {
            "symbol": sym,
            "rag_sources": list(RAG_SOURCE_KEYS),
            "rag_stats": stats,
            "disclaimer": "Research analytics only. Not investment advice.",
            "analysis_refreshed": analysis_refreshed,
            "analysis": payload,
            "copy_mode": mode,
        }

        if narrator is None:
            reply = _template_chat_reply(message, payload, mode)
            return {**result_base, "reply": reply, "provider": "deterministic_template"}

        try:
            reply = await self._llm_chat(narrator, message, history, context, mode, payload)
            return {**result_base, "reply": reply, "provider": provider}
        except Exception as exc:
            logger.warning("Chat LLM failed (%s), using template RAG fallback", exc)
            reply = _template_chat_reply(message, payload, mode)
            return {
                **result_base,
                "reply": reply,
                "provider": "deterministic_template_fallback",
            }

    async def _llm_chat(
        self,
        narrator,
        message: str,
        history: List[Dict[str, str]],
        context: str,
        copy_mode: str,
        payload: Dict[str, Any],
    ) -> str:
        import asyncio

        system = _chat_system_prompt(copy_mode, payload) + f"\n\nEVIDENCE (retrieved analysis context):\n{context}"
        messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
        for turn in history[-12:]:
            role = turn.get("role", "user")
            if role not in ("user", "assistant"):
                continue
            content = turn.get("content", "").strip()
            if content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        def _call():
            kwargs: Dict[str, Any] = {
                "model": narrator.model,
                "messages": messages,
                "max_tokens": 800,
                "temperature": 0.3,
            }
            if getattr(narrator, "_extra_headers", None):
                kwargs["extra_headers"] = narrator._extra_headers
            completion = narrator._client.chat.completions.create(**kwargs)
            return (completion.choices[0].message.content or "").strip()

        return await asyncio.to_thread(_call)
