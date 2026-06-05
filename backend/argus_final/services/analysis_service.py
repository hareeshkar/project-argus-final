from __future__ import annotations

import re
import time
from typing import Any, Dict, Iterator, Optional

from argus_final.analytics import AnalyticsEngine
from argus_final.core.settings import Settings, settings
from argus_final.data.cse_provider import CseRestMarketDataProvider
from argus_final.data.providers import InMemoryMarketDataProvider, MarketDataProvider
from argus_final.llm import DeepSeekNarrator, LLMNarrator, OpenRouterNarrator, TemplateNarrator


COMMON_SYMBOLS = {
    "JKH": "JKH.N0000",
    "COMB": "COMB.N0000",
    "LOLC": "LOLC.N0000",
    "DIAL": "DIAL.N0000",
    "HNB": "HNB.N0000",
    "SAMP": "SAMP.N0000",
    "NTB": "NTB.N0000",
    "EXP": "EXP.N0000",
}

QUERY_STOP_WORDS = {
    "ANALYZE",
    "CHECK",
    "WHAT",
    "ABOUT",
    "TELL",
    "SHOW",
    "STOCK",
    "SYMBOL",
    "MARKET",
    "PRICE",
    "TODAY",
    "HERE",
    "THIS",
    "THAT",
    "WITH",
    "FROM",
    "PLEASE",
}


class AnalysisService:
    def __init__(
        self,
        data_provider: Optional[MarketDataProvider] = None,
        analytics_engine: Optional[AnalyticsEngine] = None,
        narrator: Optional[LLMNarrator] = None,
        app_settings: Settings = settings,
    ):
        self.data_provider = data_provider or self._provider_for_mode(app_settings.demo_mode)
        self.analytics_engine = analytics_engine or AnalyticsEngine()
        self.narrator = narrator or self._build_narrator(app_settings)
        self.settings = app_settings

    def analyze(self, query: str, demo_mode: Optional[bool] = None) -> Dict[str, Any]:
        final_payload = None
        for event in self.iter_analysis_events(query, demo_mode=demo_mode):
            if event["event"] == "final":
                final_payload = event["data"]
        if final_payload is None:
            raise RuntimeError("analysis pipeline ended without a final payload")
        return final_payload

    def iter_analysis_events(
        self,
        query: str,
        demo_mode: Optional[bool] = None,
        academic_pace: bool = False,
    ) -> Iterator[Dict[str, Any]]:
        started = time.time()
        min_stage_seconds = {
            "parse": 0.30,
            "fetch": 0.70,
            "models": 0.90,
            "confidence": 0.45,
            "narrative": 0.75,
        } if academic_pace else {}

        def start_stage(stage_id: str, title: str, message: str) -> tuple[float, Dict[str, Any]]:
            stage_started = time.time()
            return stage_started, self._pipeline_event(stage_id, title, "running", message)

        def finish_stage(
            stage_id: str,
            title: str,
            status: str,
            message: str,
            stage_started: float,
            detail: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            elapsed = time.time() - stage_started
            min_seconds = min_stage_seconds.get(stage_id, 0.0)
            if elapsed < min_seconds:
                time.sleep(min_seconds - elapsed)
                elapsed = time.time() - stage_started
            return self._pipeline_event(stage_id, title, status, message, elapsed, detail)

        parse_started, event = start_stage("parse", "Parsing symbol from query", "Reading the query and extracting the CSE symbol")
        yield event
        symbol = self.extract_symbol(query)
        yield finish_stage(
            "parse",
            "Parsing symbol from query",
            "done",
            f"Resolved {query!r} to {symbol}",
            parse_started,
            {"symbol": symbol},
        )

        fetch_started, event = start_stage("fetch", "Fetching CSE REST + microstructure proxy", "Collecting historical prices, order book, and latest market snapshot")
        yield event
        data_provider = self.data_provider if demo_mode is None else self._provider_for_mode(demo_mode)
        data_source_mode = self.settings.data_source_mode if demo_mode is None else ("offline_demo" if demo_mode else "live_cse_rest")
        node_status: Dict[str, Dict[str, Any]] = {}
        df = data_provider.historical_ohlcv(symbol)
        node_status["historical_data"] = {"status": "ok"}
        try:
            order_book = data_provider.order_book(symbol)
            node_status["order_book"] = {"status": "ok"}
        except Exception as exc:
            order_book = self._fallback_order_book(symbol, exc)
            node_status["order_book"] = {"status": "degraded", "error": str(exc)}
        try:
            microstructure = data_provider.microstructure(symbol)
            node_status["microstructure"] = {"status": "ok"}
        except Exception as exc:
            microstructure = self._fallback_microstructure(symbol, df, exc)
            node_status["microstructure"] = {"status": "degraded", "error": str(exc)}
        provider_metadata = getattr(data_provider, "metadata", {})
        yield finish_stage(
            "fetch",
            "Fetching CSE REST + microstructure proxy",
            "done" if all(status["status"] == "ok" for status in node_status.values()) else "degraded",
            f"Loaded {len(df)} historical rows from {provider_metadata.get('historical_source', 'IN_MEMORY_DEMO')}",
            fetch_started,
            {
                "historical_rows": len(df),
                "historical_source": provider_metadata.get("historical_source", "IN_MEMORY_DEMO"),
                "order_book": node_status["order_book"]["status"],
                "microstructure": node_status["microstructure"]["status"],
                "live_source": provider_metadata.get("live_source", "IN_MEMORY_DEMO"),
            },
        )

        models_started, event = start_stage("models", "Running statistical models", "Running ARIMA, volatility, anomaly, trend, and drawdown models")
        yield event
        analysis = self.analytics_engine.run(df)
        arima = analysis.get("arima", {})
        volatility = analysis.get("volatility", {})
        yield finish_stage(
            "models",
            "Running statistical models",
            "done",
            f"Selected {arima.get('model_used', 'ARIMA model')} and classified risk as {volatility.get('risk_level', 'unknown')}",
            models_started,
            {
                "model": arima.get("model_used"),
                "risk_level": volatility.get("risk_level"),
                "trend": analysis.get("trend", {}).get("trend_direction"),
                "data_points": analysis.get("data_points"),
            },
        )

        confidence_started, event = start_stage("confidence", "Computing confidence score", "Combining model quality, data sufficiency, liquidity, and warning penalties")
        yield event
        confidence = analysis["confidence"]
        indicator_vote = analysis["indicator_vote"]
        yield finish_stage(
            "confidence",
            "Computing confidence score",
            "done",
            f"Confidence is {confidence['label']} at {confidence['score']:.2f}; signal is {indicator_vote['signal']}",
            confidence_started,
            {
                "score": confidence["score"],
                "label": confidence["label"],
                "signal": indicator_vote["signal"],
                "warnings": len(confidence.get("reasons", [])),
            },
        )

        narrative_started, event = start_stage("narrative", "Generating analyst summary", "Converting computed evidence into a short research summary")
        yield event
        llm_provider = getattr(self.narrator, "model", "deterministic_template")
        if not isinstance(self.narrator, (DeepSeekNarrator, OpenRouterNarrator)):
            llm_provider = "deterministic_template"
        try:
            llm_explanation = self.narrator.explain(symbol, analysis)
            node_status["narrative"] = {"status": "ok", "provider": llm_provider}
        except Exception as exc:
            llm_explanation = self._fallback_narrative(symbol, analysis, exc)
            llm_provider = "deterministic_template_fallback"
            node_status["narrative"] = {"status": "degraded", "provider": llm_provider, "error": str(exc)}
        yield finish_stage(
            "narrative",
            "Generating analyst summary",
            "done" if node_status["narrative"]["status"] == "ok" else "degraded",
            f"Narrative provider: {llm_provider}",
            narrative_started,
            {"provider": llm_provider},
        )

        provider_quality = getattr(data_provider, "last_quality_flags", {})
        historical_source = provider_metadata.get("historical_source", "IN_MEMORY_DEMO")
        live_source = provider_metadata.get("live_source", "IN_MEMORY_DEMO")
        order_book_source = provider_metadata.get("order_book_source", "IN_MEMORY_DEMO") if node_status["order_book"]["status"] == "ok" else "UNAVAILABLE"
        last_historical_timestamp = getattr(data_provider, "last_historical_timestamp", None)
        price_history = self._price_history_slice(df)

        yield {
            "event": "final",
            "data": {
            "query": query,
            "symbol": symbol,
            "company_name": None,
            "timestamp": analysis["analysis_timestamp"],
            "processing_time": time.time() - started,
            "data_source_mode": data_source_mode,
            "data_lineage": {
                "historical_source": historical_source,
                "live_source": live_source,
                "order_book_source": order_book_source,
                "llm_provider": llm_provider,
                "historical_rows": analysis["data_points"],
                "tick_rows": microstructure.get("tick_count", 0),
                "last_historical_timestamp": last_historical_timestamp or (str(df["timestamp"].iloc[-1]) if "timestamp" in df.columns else None),
                "last_tick_timestamp": microstructure.get("last_update"),
            },
            "node_status": node_status,
            "confidence": analysis["confidence"],
            "indicator_vote": analysis["indicator_vote"],
            "ensemble": analysis["indicator_vote"],
            "ensemble_signal": analysis["indicator_vote"]["signal"],
            "math_results": analysis,
            "order_book": order_book,
            "microstructure": microstructure,
            "price_history": price_history,
            "llm_explanation": llm_explanation,
            "quality_flags": {
                "has_missing_values": bool(provider_quality.get("has_missing_values", df.isna().any().any())),
                "has_null_open_prices": bool(provider_quality.get("has_null_open_prices", False)),
                "used_open_price_proxy": bool(provider_quality.get("used_open_price_proxy", False)),
                "is_stale": False,
                "low_liquidity_warning": analysis["regime"]["liquidity_regime"] == "THIN",
                "api_latency_warning": False,
                "model_warning": not analysis["arima"]["beats_naive"],
                "warnings": list(provider_quality.get("warnings", [])) + analysis["confidence"].get("reasons", []) + self._node_warnings(node_status),
            },
            "error": None,
            },
        }

    def _pipeline_event(
        self,
        stage_id: str,
        title: str,
        status: str,
        message: str,
        elapsed: Optional[float] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "stage_id": stage_id,
            "title": title,
            "status": status,
            "message": message,
            "timestamp": time.time(),
        }
        if elapsed is not None:
            ms = round(elapsed * 1000)
            if status in {"done", "degraded", "error"} and ms < 1:
                ms = 1
            data["elapsed_ms"] = ms
        if detail:
            data["detail"] = detail
        return {"event": "pipeline", "data": data}

    @staticmethod
    def _price_history_slice(df, window: int = 30) -> Dict[str, Any]:
        """Last N daily closes for the forecast chart — real CSE OHLCV, not synthetic."""
        if df is None or getattr(df, "empty", True) or "close" not in df.columns:
            return {"closes": [], "timestamps": [], "window": 0}
        tail = df.tail(window)
        closes = [float(value) for value in tail["close"].tolist()]
        timestamps = (
            [str(value) for value in tail["timestamp"].tolist()]
            if "timestamp" in tail.columns
            else []
        )
        return {"closes": closes, "timestamps": timestamps, "window": len(closes)}

    def _fallback_order_book(self, symbol: str, exc: Exception) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "bids": 0,
            "asks": 0,
            "pressure": 0.0,
            "spread_estimate": None,
            "error": str(exc),
        }

    def _fallback_microstructure(self, symbol: str, df, exc: Exception) -> Dict[str, Any]:
        latest_price = float(df["close"].iloc[-1]) if df is not None and not df.empty and "close" in df.columns else 0.0
        latest_timestamp = str(df["timestamp"].iloc[-1]) if df is not None and not df.empty and "timestamp" in df.columns else None
        return {
            "symbol": symbol,
            "latest_price": latest_price,
            "vwap": latest_price,
            "trade_intensity": 0,
            "price_momentum": 0.0,
            "window_volume": 0,
            "tick_count": 0,
            "last_update": latest_timestamp,
            "source": "HISTORICAL_CLOSE_FALLBACK",
            "error": str(exc),
        }

    def _fallback_narrative(self, symbol: str, analysis: Dict[str, Any], exc: Exception) -> Dict[str, Any]:
        vote = analysis["indicator_vote"]
        confidence = analysis["confidence"]
        return {
            "summary": (
                f"Template fallback narrative: {symbol} has a {vote['signal'].lower()} analytical lean "
                f"with {confidence['label'].lower()} confidence. External LLM is not configured or failed."
            ),
            "risk_notes": [
                "Narrative was generated deterministically from computed metrics.",
                f"Narrative node error: {exc}",
            ],
            "confidence_explanation": "; ".join(confidence.get("reasons", [])) or "No major confidence penalties.",
            "disclaimer": "Research analytics only. Not investment advice.",
        }

    def _node_warnings(self, node_status: Dict[str, Dict[str, Any]]) -> list:
        warnings = []
        for node, status in node_status.items():
            if status.get("status") == "degraded":
                warnings.append(f"{node} node degraded: {status.get('error', 'unknown error')}")
        return warnings

    @staticmethod
    def _build_narrator(app_settings: Settings) -> LLMNarrator:
        deepseek_key = app_settings.deepseek_api_key
        if deepseek_key and deepseek_key != "REPLACE_WITH_DEEPSEEK_API_KEY":
            return DeepSeekNarrator(api_key=deepseek_key, model=app_settings.deepseek_model)

        key = app_settings.openrouter_api_key
        if key and key != "REPLACE_WITH_OPENROUTER_API_KEY":
            model = app_settings.openrouter_model
            if model in ("openrouter/auto", ""):
                model = "openrouter/free"
            return OpenRouterNarrator(api_key=key, model=model)
        return TemplateNarrator()

    def _provider_for_mode(self, demo_mode: bool) -> MarketDataProvider:
        if demo_mode:
            return InMemoryMarketDataProvider()
        return CseRestMarketDataProvider()

    def extract_symbol(self, query: str) -> str:
        upper = query.upper()
        full_match = re.search(r"[A-Z]{3,4}\.N\d{4}", upper)
        if full_match:
            return full_match.group(0)
        for short, full in COMMON_SYMBOLS.items():
            if re.search(rf"\b{short}\b", upper):
                return full
        candidates = re.findall(r"\b[A-Z]{3,4}\b", upper)
        for candidate in candidates:
            if candidate not in QUERY_STOP_WORDS:
                return f"{candidate}.N0000"
        return "JKH.N0000"
