from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Dict, Optional

from argus_final.analytics.engine import AnalyticsConfig, AnalyticsEngine
from argus_final.analytics.intraday_context import (
    build_intraday_context,
    combine_ensemble,
    intraday_confidence_penalties,
)
from argus_final.copy import (
    localize_confidence_reason,
    localize_quality_warning,
    normalize_copy_mode,
    pipeline_done_message,
    pipeline_queued_message,
    pipeline_running_message,
    pipeline_stage_title,
)
from argus_final.core.settings import Settings, settings
from argus_final.data.cse_provider import CseRestMarketDataProvider
from argus_final.data.providers import InMemoryMarketDataProvider, MarketDataProvider
from argus_final.data.tick_store import TickStore
from argus_final.llm import DeepSeekNarrator, LLMNarrator, OpenRouterNarrator, TemplateNarrator
from argus_final.services.narrative_service import resolve_narrative_async, should_use_celery


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
        tick_store: Optional[TickStore] = None,
    ):
        self.data_provider = data_provider or self._provider_for_mode(app_settings.demo_mode)
        arima_config = AnalyticsConfig(
            arima_mode=app_settings.arima_mode,
            arima_max_p=app_settings.arima_max_p,
            arima_max_q=app_settings.arima_max_q,
            arima_max_d=app_settings.arima_max_d,
        )
        self.analytics_engine = analytics_engine or AnalyticsEngine(arima_config)
        self.narrator = narrator or self._build_narrator(app_settings)
        self.settings = app_settings
        # Optional shared live tick store (wired from the FastAPI lifespan).
        # When present and populated for a symbol, live ticks are preferred over
        # the REST microstructure proxy; otherwise we fall back to the provider.
        self.tick_store = tick_store

    def analyze(
        self,
        query: str,
        demo_mode: Optional[bool] = None,
        copy_mode: Optional[str] = "simple",
    ) -> Dict[str, Any]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.analyze_async(query, demo_mode=demo_mode, copy_mode=copy_mode))

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(
                lambda: asyncio.run(
                    self.analyze_async(query, demo_mode=demo_mode, copy_mode=copy_mode)
                )
            ).result()

    async def analyze_async(
        self,
        query: str,
        demo_mode: Optional[bool] = None,
        copy_mode: Optional[str] = "simple",
    ) -> Dict[str, Any]:
        final_payload = None
        async for event in self.iter_analysis_events(
            query,
            demo_mode=demo_mode,
            copy_mode=copy_mode,
        ):
            if event["event"] == "final":
                final_payload = event["data"]
        if final_payload is None:
            raise RuntimeError("analysis pipeline ended without a final payload")
        return final_payload

    async def iter_analysis_events(
        self,
        query: str,
        demo_mode: Optional[bool] = None,
        academic_pace: bool = False,
        copy_mode: Optional[str] = "simple",
    ):
        mode = normalize_copy_mode(copy_mode)
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

        async def finish_stage(
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
                await asyncio.sleep(min_seconds - elapsed)
                elapsed = time.time() - stage_started
            return self._pipeline_event(stage_id, title, status, message, elapsed, detail)

        parse_started, event = start_stage(
            "parse",
            pipeline_stage_title("parse", mode),
            pipeline_running_message("parse", mode),
        )
        yield event
        symbol = self.extract_symbol(query)
        yield await finish_stage(
            "parse",
            pipeline_stage_title("parse", mode),
            "done",
            pipeline_done_message("parse", mode, query=query, symbol=symbol),
            parse_started,
            {"symbol": symbol},
        )

        fetch_started, event = start_stage(
            "fetch",
            pipeline_stage_title("fetch", mode),
            pipeline_running_message("fetch", mode),
        )
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
        # Prefer the shared live tick window when it actually has data for this
        # symbol; the REST provider is a single-snapshot proxy (tick_count=0).
        provider_metadata = getattr(data_provider, "metadata", {})
        historical_source = provider_metadata.get("historical_source", "IN_MEMORY_DEMO")
        microstructure, live_source = self._resolve_microstructure(
            symbol, data_provider, microstructure, historical_source
        )
        yield await finish_stage(
            "fetch",
            pipeline_stage_title("fetch", mode),
            "done" if all(status["status"] == "ok" for status in node_status.values()) else "degraded",
            pipeline_done_message(
                "fetch",
                mode,
                historical_rows=len(df),
                historical_source=historical_source,
            ),
            fetch_started,
            {
                "historical_rows": len(df),
                "historical_source": historical_source,
                "order_book": node_status["order_book"]["status"],
                "microstructure": node_status["microstructure"]["status"],
                "live_source": live_source,
            },
        )

        models_started, event = start_stage(
            "models",
            pipeline_stage_title("models", mode),
            pipeline_running_message("models", mode),
        )
        yield event
        analysis = self.analytics_engine.run(df)
        arima = analysis.get("arima", {})
        volatility = analysis.get("volatility", {})
        # Intraday context is a separate, lightly-weighted layer built from the
        # live microstructure + order book snapshot. It never enters ARIMA/VaR;
        # it only nudges the ensemble and informs confidence/quality flags.
        intraday_context = build_intraday_context(df, microstructure, order_book)
        yield await finish_stage(
            "models",
            pipeline_stage_title("models", mode),
            "done",
            pipeline_done_message(
                "models",
                mode,
                model_used=arima.get("model_used", "ARIMA model"),
                risk_level=volatility.get("risk_level", "unknown"),
            ),
            models_started,
            {
                "model": arima.get("model_used"),
                "risk_level": volatility.get("risk_level"),
                "trend": analysis.get("trend", {}).get("trend_direction"),
                "data_points": analysis.get("data_points"),
                "intraday_context_source": intraday_context.get("source"),
                "intraday_available": intraday_context.get("available"),
            },
        )

        confidence_started, event = start_stage(
            "confidence",
            pipeline_stage_title("confidence", mode),
            pipeline_running_message("confidence", mode),
        )
        yield event
        daily_confidence = analysis["confidence"]
        daily_vote = analysis["indicator_vote"]
        # Combine daily ensemble with the intraday nudge; apply intraday
        # penalties (price divergence, staleness) on top of the daily confidence.
        combined_vote = combine_ensemble(daily_vote, intraday_context, daily_confidence.get("score", 0.0))
        combined_confidence = self._apply_intraday_confidence(daily_confidence, intraday_context, mode)
        confidence = combined_confidence
        indicator_vote = combined_vote
        yield await finish_stage(
            "confidence",
            pipeline_stage_title("confidence", mode),
            "done",
            pipeline_done_message(
                "confidence",
                mode,
                label=confidence["label"],
                score=confidence["score"],
                signal=indicator_vote["signal"],
            ),
            confidence_started,
            {
                "score": confidence["score"],
                "label": confidence["label"],
                "signal": indicator_vote["signal"],
                "warnings": len(confidence.get("reasons", [])),
                "intraday_nudge": combined_vote.get("intraday_nudge", 0.0),
            },
        )

        narrative_started, event = start_stage(
            "narrative",
            pipeline_stage_title("narrative", mode),
            pipeline_running_message("narrative", mode),
        )
        yield event
        if should_use_celery(self.settings, self.narrator):
            yield self._pipeline_event(
                "narrative",
                pipeline_stage_title("narrative", mode),
                "queued",
                pipeline_queued_message(mode),
            )
        llm_explanation, llm_provider, narrative_status = await resolve_narrative_async(
            symbol,
            analysis,
            self.narrator,
            self.settings,
            copy_mode=mode,
        )
        node_status["narrative"] = {"status": narrative_status, "provider": llm_provider}
        yield await finish_stage(
            "narrative",
            pipeline_stage_title("narrative", mode),
            "done" if narrative_status == "ok" else "degraded",
            pipeline_done_message("narrative", mode, provider=llm_provider),
            narrative_started,
            {"provider": llm_provider},
        )

        provider_quality = getattr(data_provider, "last_quality_flags", {})
        historical_source = provider_metadata.get("historical_source", "IN_MEMORY_DEMO")
        order_book_source = provider_metadata.get("order_book_source", "IN_MEMORY_DEMO") if node_status["order_book"]["status"] == "ok" else "UNAVAILABLE"
        last_historical_timestamp = getattr(data_provider, "last_historical_timestamp", None)
        price_history = self._price_history_slice(df)

        localized_reasons = [
            localize_confidence_reason(reason, mode) for reason in confidence.get("reasons", [])
        ]
        localized_provider_warnings = [
            localize_quality_warning(warning, mode) for warning in provider_quality.get("warnings", [])
        ]
        localized_node_warnings = self._node_warnings(node_status, mode)
        localized_intraday_warnings = [
            localize_quality_warning(warning, mode) for warning in intraday_context.get("warnings", [])
        ]

        yield {
            "event": "final",
            "data": {
            "query": query,
            "symbol": symbol,
            "company_name": None,
            "timestamp": analysis["analysis_timestamp"],
            "processing_time": time.time() - started,
            "data_source_mode": data_source_mode,
            "copy_mode": mode,
            "data_lineage": {
                "historical_source": historical_source,
                "live_source": live_source,
                "order_book_source": order_book_source,
                "intraday_context_source": intraday_context.get("source"),
                "llm_provider": llm_provider,
                "copy_mode": mode,
                "historical_rows": analysis["data_points"],
                "tick_rows": microstructure.get("tick_count", 0),
                "last_historical_timestamp": last_historical_timestamp or (str(df["timestamp"].iloc[-1]) if "timestamp" in df.columns else None),
                "last_tick_timestamp": microstructure.get("last_update"),
            },
            "node_status": node_status,
            "confidence": {
                **confidence,
                "reasons": localized_reasons,
            },
            "indicator_vote": {
                **indicator_vote,
                "drivers": localized_reasons,
            },
            "ensemble": indicator_vote,
            "ensemble_signal": indicator_vote["signal"],
            "math_results": analysis,
            "order_book": order_book,
            "microstructure": microstructure,
            "intraday_context": intraday_context,
            "price_history": price_history,
            "llm_explanation": llm_explanation,
            "quality_flags": {
                "has_missing_values": bool(provider_quality.get("has_missing_values", df.isna().any().any())),
                "has_null_open_prices": bool(provider_quality.get("has_null_open_prices", False)),
                "used_open_price_proxy": bool(provider_quality.get("used_open_price_proxy", False)),
                "is_stale": bool(intraday_context.get("is_stale")),
                "order_book_snapshot": node_status["order_book"]["status"] == "ok",
                "intraday_context_available": bool(intraday_context.get("available")),
                "low_liquidity_warning": analysis["regime"]["liquidity_regime"] == "THIN",
                "api_latency_warning": False,
                "model_warning": not analysis["arima"]["beats_naive"],
                "warnings": (
                    localized_provider_warnings
                    + localized_reasons
                    + localized_node_warnings
                    + localized_intraday_warnings
                ),
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

    def _resolve_microstructure(
        self,
        symbol: str,
        data_provider: MarketDataProvider,
        rest_microstructure: Dict[str, Any],
        historical_source: str = "IN_MEMORY_DEMO",
    ) -> tuple[Dict[str, Any], str]:
        """Prefer the shared live tick window when it has data for this symbol.

        Returns the chosen microstructure dict and the live source label to
        surface in data lineage. Falls back to the provider's REST proxy when no
        live ticks are available.
        """
        tick_store = getattr(self, "tick_store", None)
        if tick_store is not None:
            try:
                live_metrics = tick_store.calculate_metrics(symbol)
            except Exception:
                live_metrics = None
            if live_metrics and live_metrics.get("tick_count", 0) > 0:
                live_metrics = dict(live_metrics)
                live_metrics["symbol"] = symbol
                live_metrics["source"] = "CSE_WEBSOCKET_DAYTRADE"
                return live_metrics, "CSE_WEBSOCKET_DAYTRADE"

        source = (rest_microstructure or {}).get("source") or "CSE_REST_TRADE_SUMMARY"
        if historical_source == "IN_MEMORY_DEMO":
            live_label = "IN_MEMORY_DEMO"
        elif source in ("HISTORICAL_CLOSE_FALLBACK", "UNAVAILABLE"):
            live_label = source
        else:
            live_label = "CSE_REST_TRADE_SUMMARY"
        return rest_microstructure, live_label

    def _apply_intraday_confidence(
        self,
        daily_confidence: Dict[str, Any],
        intraday_context: Dict[str, Any],
        mode: str,
    ) -> Dict[str, Any]:
        """Re-derive the confidence score/label after adding intraday penalties.

        ``math_results.confidence`` stays pure (daily-only); this combined
        confidence is what the dashboard and chat surface.
        """
        penalties = dict(daily_confidence.get("penalties") or {})
        penalties.update(intraday_confidence_penalties(intraday_context))
        score = max(0.0, min(1.0, 1.0 - sum(penalties.values())))
        label = "HIGH" if score >= 0.75 else ("MODERATE" if score >= 0.5 else "LOW")

        reasons = list(daily_confidence.get("reasons") or [])
        if intraday_context.get("is_stale") and "stale_intraday" in penalties:
            reasons.append("Intraday snapshot is stale; live context treated as low-weight")
        if penalties.get("price_divergence"):
            reasons.append("Live price diverges materially from the last daily close")
        if not intraday_context.get("available"):
            reasons.append("No live intraday window; analysis is daily-only")

        return {
            "score": round(float(score), 4),
            "label": label,
            "penalties": penalties,
            "reasons": reasons,
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

    def _node_warnings(self, node_status: Dict[str, Dict[str, Any]], mode: str = "simple") -> list:
        warnings = []
        for node, status in node_status.items():
            if status.get("status") == "degraded":
                msg = f"{node} node degraded: {status.get('error', 'unknown error')}"
                if mode == "simple":
                    msg = f"{node.replace('_', ' ')} data unavailable: {status.get('error', 'unknown error')}"
                warnings.append(msg)
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
