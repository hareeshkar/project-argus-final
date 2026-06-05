from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from argus_final import __version__
from argus_final.core.settings import Settings, settings
from argus_final.data.websocket_provider import LiveTickStore, WebSocketMarketDataProvider
from argus_final.data.providers import MarketDataProvider
from argus_final.data.cse_provider import CseRestMarketDataProvider
from argus_final.llm import DeepSeekNarrator, OpenRouterNarrator, TemplateNarrator
from argus_final.services import AnalysisService


class AnalysisRequest(BaseModel):
    query: str
    demo_mode: Optional[bool] = None


_trade_summary_cache: Dict[str, Any] = {"ts": 0.0, "rows": {}}


def _trade_summary_by_symbol(max_age_seconds: float = 1.0) -> Dict[str, Dict[str, Any]]:
    """Shared 1s cache so per-symbol live polls do not hammer CSE tradeSummary."""
    now = time.time()
    if now - _trade_summary_cache["ts"] < max_age_seconds and _trade_summary_cache["rows"]:
        return _trade_summary_cache["rows"]
    provider = CseRestMarketDataProvider()
    rows = provider.trade_summary_rows(refresh=True)
    by_symbol = {row["symbol"]: row for row in rows if row.get("symbol")}
    _trade_summary_cache["ts"] = now
    _trade_summary_cache["rows"] = by_symbol
    return by_symbol


def create_app(
    data_provider: Optional[MarketDataProvider] = None,
    narrator=None,
    app_settings: Settings = settings,
) -> FastAPI:
    service = AnalysisService(data_provider=data_provider, narrator=narrator, app_settings=app_settings)
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.version,
        description="Confidence-aware CSE analytics API. Research use only; not investment advice.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in app_settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    def narrator_provider_name(narrator) -> str:
        if isinstance(narrator, DeepSeekNarrator):
            return narrator.model
        if isinstance(narrator, OpenRouterNarrator):
            return narrator.model
        return "deterministic_template"

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "version": __version__,
            "service": app_settings.app_name,
            "components": {
                "api": "ok",
                "data_provider": "ok",
                "analytics_engine": "ok",
                "narrative_provider": narrator_provider_name(service.narrator),
            },
        }

    @app.post("/api/analyze")
    async def analyze(request: AnalysisRequest):
        return service.analyze(request.query, demo_mode=request.demo_mode)

    @app.get("/api/analyze/stream")
    async def analyze_stream(
        request: Request,
        query: str,
        demo_mode: Optional[bool] = None,
        pace: str = "academic",
    ):
        """Stream the analysis pipeline as Server-Sent Events, then emit the final payload."""

        def sse(event_name: str, payload) -> str:
            return f"event: {event_name}\ndata: {json.dumps(payload, default=str)}\n\n"

        async def event_stream():
            try:
                academic_pace = pace.lower() not in {"fast", "none", "off", "0"}
                for event in service.iter_analysis_events(query, demo_mode=demo_mode, academic_pace=academic_pace):
                    if await request.is_disconnected():
                        break
                    yield sse(event["event"], event["data"])
            except Exception as exc:
                yield sse(
                    "analysis_error",
                    {
                        "message": str(exc),
                        "stage_id": "pipeline",
                        "status": "error",
                    },
                )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/market-prices")
    async def market_prices():
        """Return latest price, change, and pct_change for all CSE symbols from tradeSummary."""
        try:
            by_symbol = _trade_summary_by_symbol(max_age_seconds=1.0)
            result = {}
            for sym, row in by_symbol.items():
                result[sym] = {
                    "price": row.get("price"),
                    "change": row.get("change"),
                    "pct_change": row.get("percentageChange"),
                }
            return {"prices": result, "count": len(result)}
        except Exception as exc:
            return {"prices": {}, "count": 0, "error": str(exc)}

    @app.get("/api/live-price")
    async def live_price(symbol: str):
        """Latest tradeSummary row for one symbol — polled by the UI every second during market hours."""
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol query parameter is required")
        try:
            by_symbol = _trade_summary_by_symbol(max_age_seconds=1.0)
            row = by_symbol.get(symbol, {})
            if not row:
                return {"symbol": symbol, "found": False, "source": "CSE_REST_TRADE_SUMMARY"}
            return {
                "symbol": symbol,
                "found": True,
                "price": row.get("price"),
                "change": row.get("change"),
                "pct_change": row.get("percentageChange"),
                "quantity": row.get("quantity"),
                "sharevolume": row.get("sharevolume") or row.get("shareVolume"),
                "tradevolume": row.get("tradevolume") or row.get("tradeVolume"),
                "turnover": row.get("turnover"),
                "high": row.get("high"),
                "low": row.get("low"),
                "last_traded_time": row.get("lastTradedTime"),
                "source": "CSE_REST_TRADE_SUMMARY",
                "updated_at": time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/live-snapshot")
    async def live_snapshot(duration: int = 5, real: bool = False):
        duration = max(1, min(duration, 30))
        provider = WebSocketMarketDataProvider(store=LiveTickStore(max_ticks_per_symbol=100))
        captured = []

        def on_trade(symbol, tick, metrics):
            captured.append({"symbol": symbol, "tick": tick, "metrics": metrics})

        if real:
            await provider.capture_for_seconds(duration, on_trade=on_trade)

        if not captured:
            _inject_demo_ticks(provider.store)

        symbol_metrics = {symbol: provider.microstructure(symbol) for symbol in provider.store.get_all_symbols()}
        return {
            "mode": "live_cse_websocket" if real and captured else "deterministic_fallback",
            "requested_real_capture": real,
            "requested_duration_seconds": duration,
            "live_ticks_captured": len(captured),
            "last_error": provider.last_error,
            "metadata": provider.metadata,
            "memory_stats": provider.memory_stats(),
            "symbols": provider.store.get_all_symbols(),
            "symbol_metrics": symbol_metrics,
            "latest_summary": provider.latest_summary,
            "latest_most_active_trades": provider.latest_most_active_trades[:10],
            "latest_share_price": provider.latest_share_price,
            "captured_sample": captured[:20],
        }

    @app.get("/api/ticks/stream")
    async def tick_stream(request: Request, symbol: Optional[str] = None):
        """Stream live CSE trade ticks to the browser via Server-Sent Events."""

        def sse(event_name: str, payload) -> str:
            return f"event: {event_name}\ndata: {json.dumps(payload, default=str)}\n\n"

        async def event_stream():
            provider = WebSocketMarketDataProvider(store=LiveTickStore(max_ticks_per_symbol=100))
            rest_provider = CseRestMarketDataProvider()
            queue: asyncio.Queue = asyncio.Queue(maxsize=500)
            state = {"disconnected": False}

            def on_trade(trade_symbol: str, tick, metrics):
                payload = {"symbol": trade_symbol, "tick": tick, "metrics": metrics}
                try:
                    queue.put_nowait({"event": "tick", "payload": payload})
                    if symbol and trade_symbol == symbol:
                        queue.put_nowait({"event": "metrics", "payload": {"symbol": trade_symbol, "metrics": metrics}})
                except asyncio.QueueFull:
                    pass

            async def pump_feed():
                await provider.run_live_feed(
                    on_trade=on_trade,
                    should_continue=lambda: not state["disconnected"],
                )

            async def pump_rest_prices():
                while not state["disconnected"]:
                    await asyncio.sleep(8.0)
                    if not symbol or state["disconnected"]:
                        continue
                    try:
                        row = rest_provider.trade_summary(symbol)
                        price = row.get("price")
                        if price is None:
                            continue
                        store_metrics = provider.store.calculate_metrics(symbol)
                        metrics = {
                            "symbol": symbol,
                            "latest_price": float(price),
                            "vwap": store_metrics.get("vwap") or float(price),
                            "trade_intensity": store_metrics.get("trade_intensity", 0),
                            "price_momentum": store_metrics.get("price_momentum", 0.0),
                            "window_volume": store_metrics.get("window_volume", 0),
                            "tick_count": store_metrics.get("tick_count", 0),
                            "last_update": time.time(),
                            "source": "CSE_REST_TRADE_SUMMARY",
                        }
                        queue.put_nowait(
                            {
                                "event": "rest_price",
                                "payload": {
                                    "symbol": symbol,
                                    "price": float(price),
                                    "change": row.get("change"),
                                    "pct_change": row.get("percentageChange"),
                                    "metrics": metrics,
                                },
                            }
                        )
                    except Exception:
                        continue

            feed_task = asyncio.create_task(pump_feed())
            rest_task = asyncio.create_task(pump_rest_prices())
            yield sse("connected", {"symbol": symbol, "status": "streaming"})

            try:
                while not await request.is_disconnected():
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=12.0)
                    except asyncio.TimeoutError:
                        if symbol:
                            store_metrics = provider.store.calculate_metrics(symbol)
                            if store_metrics.get("tick_count", 0) > 0:
                                yield sse("metrics", {"symbol": symbol, "metrics": store_metrics})
                        yield sse("heartbeat", {"ts": time.time()})
                        continue

                    event_name = item.get("event", "tick")
                    payload = item.get("payload", item)
                    if event_name == "tick" and symbol and payload.get("symbol") != symbol:
                        continue
                    yield sse(event_name, payload)
            finally:
                state["disconnected"] = True
                provider.running = False
                feed_task.cancel()
                rest_task.cancel()
                for task in (feed_task, rest_task):
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()


def _inject_demo_ticks(store: LiveTickStore) -> None:
    now = time.time()
    ticks = [
        {"symbol": "COMB.N0000", "price": 203.0, "volume": 1000, "timestamp": now - 20},
        {"symbol": "COMB.N0000", "price": 203.25, "volume": 2000, "timestamp": now - 10},
        {"symbol": "COMB.N0000", "price": 202.75, "volume": 1500, "timestamp": now},
        {"symbol": "JKH.N0000", "price": 20.5, "volume": 5000, "timestamp": now - 5},
        {"symbol": "JKH.N0000", "price": 20.6, "volume": 8000, "timestamp": now},
    ]
    for tick in ticks:
        store.update_tick(tick["symbol"], tick)
