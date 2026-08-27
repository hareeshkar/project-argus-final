from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import random
import string
import time
from typing import Any, Callable, Dict, List, Optional

import websockets

from argus_final.data.tick_store import InMemoryTickStore, LiveTickStore, TickStore


CSE_WS_BASE = "wss://www.cse.lk/api/ws"
CSE_LEGACY_WS_BASE = "wss://www.cse.lk/ws/8"
CSE_WS_HEADERS = {
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


@dataclass
class StompFrame:
    command: str
    headers: Dict[str, str]
    body: str

    @staticmethod
    def build(command: str, headers: Optional[Dict[str, str]] = None, body: str = "") -> str:
        lines = [command]
        for key, value in (headers or {}).items():
            lines.append(f"{key}:{value}")
        return "\n".join(lines) + f"\n\n{body}\x00"

    @staticmethod
    def parse(message: str) -> "StompFrame":
        clean_message = message.rstrip("\x00")
        head, _, body = clean_message.partition("\n\n")
        lines = head.split("\n") if head else [""]
        command = lines[0]
        headers: Dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key] = value
        return StompFrame(command=command, headers=headers, body=body)


class WebSocketMarketDataProvider:
    """Native final STOMP/SockJS WebSocket provider for CSE daytrade ticks."""

    def __init__(
        self,
        store: Optional[TickStore] = None,
        volume_estimator: Optional[Callable[[str], Dict[str, Any]]] = None,
        websocket_base: str = CSE_WS_BASE,
        fallback_websocket_base: str = CSE_LEGACY_WS_BASE,
        open_timeout: float = 10.0,
        ping_interval: float = 20.0,
        ping_timeout: float = 30.0,
        close_timeout: float = 5.0,
    ):
        self.store = store or InMemoryTickStore()
        self.volume_estimator = volume_estimator
        self.websocket_base = websocket_base.rstrip("/")
        self.fallback_websocket_base = fallback_websocket_base.rstrip("/")
        self.open_timeout = open_timeout
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.close_timeout = close_timeout
        self.running = False
        self.last_error: Optional[Dict[str, Any]] = None
        self.latest_summary: Dict[str, Any] = {}
        self.latest_most_active_trades: List[Dict[str, Any]] = []
        self.latest_share_price: Dict[str, Dict[str, Any]] = {}
        self.metadata = {
            "historical_source": "NOT_CONFIGURED",
            "order_book_source": "NOT_CONFIGURED",
            "live_source": "CSE_WEBSOCKET_DAYTRADE",
            "provider": "WebSocketMarketDataProvider",
            "topics": [
                "/topic/daytrade",
                "/user/topic/daytrade",
                "/topic/today-sharePrice",
                "/user/topic/today-sharePrice",
                "/topic/summary",
                "/user/topic/summary",
                "/topic/most-active-trades",
                "/user/topic/most-active-trades",
            ],
            "primary_base": self.websocket_base,
            "fallback_base": self.fallback_websocket_base,
        }

    def websocket_url(self, use_fallback: bool = False) -> str:
        server_id = random.randint(100, 999)
        session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        base = self.fallback_websocket_base if use_fallback else self.websocket_base
        return f"{base}/{server_id}/{session_id}/websocket"

    def connect_frame(self) -> str:
        # Match the proven root dashboard/tester handshake. The CSE SockJS
        # endpoint accepts STOMP 1.2 and does not require a host header here.
        return StompFrame.build("CONNECT", {"accept-version": "1.2,1.1,1.0", "heart-beat": "10000,10000"})

    def subscribe_frame(self) -> str:
        return StompFrame.build("SUBSCRIBE", {"id": "sub-0", "destination": "/topic/daytrade"})

    def user_subscribe_frame(self) -> str:
        return StompFrame.build("SUBSCRIBE", {"id": "sub-1", "destination": "/user/topic/daytrade"})

    def request_daytrade_frame(self) -> str:
        return StompFrame.build("SEND", {"destination": "/app/request-daytrade"})

    def subscription_frames(self) -> List[str]:
        frames = [
            StompFrame.build("SUBSCRIBE", {"id": "sub-0", "destination": "/topic/daytrade"}),
            StompFrame.build("SUBSCRIBE", {"id": "sub-1", "destination": "/user/topic/daytrade"}),
            StompFrame.build("SEND", {"destination": "/app/request-daytrade"}),
            StompFrame.build("SUBSCRIBE", {"id": "sub-2", "destination": "/topic/today-sharePrice"}),
            StompFrame.build("SUBSCRIBE", {"id": "sub-3", "destination": "/user/topic/today-sharePrice"}),
            StompFrame.build("SEND", {"destination": "/app/request-today-sharePrice"}),
            StompFrame.build("SUBSCRIBE", {"id": "sub-4", "destination": "/topic/summary"}),
            StompFrame.build("SUBSCRIBE", {"id": "sub-5", "destination": "/user/topic/summary"}),
            StompFrame.build("SEND", {"destination": "/app/request-summary"}),
            StompFrame.build("SUBSCRIBE", {"id": "sub-6", "destination": "/topic/most-active-trades"}),
            StompFrame.build("SUBSCRIBE", {"id": "sub-7", "destination": "/user/topic/most-active-trades"}),
            StompFrame.build("SEND", {"destination": "/app/request-most-active-trades"}),
        ]
        return frames

    async def process_stomp_message(self, message: str, on_trade: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]] = None) -> int:
        processed = 0
        for stomp_message in self.decode_sockjs_message(message):
            frame = StompFrame.parse(stomp_message)
            if frame.command == "MESSAGE" and frame.body:
                topic = frame.headers.get("destination", "").split("/")[-1]
                processed += await self.process_topic_payload(topic, frame.body, on_trade=on_trade)
        return processed

    async def process_topic_payload(
        self,
        topic: str,
        body: str,
        on_trade: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]] = None,
    ) -> int:
        if topic == "daytrade":
            return await self.process_trade_payload(body, on_trade=on_trade, source_topic=topic)
        if topic == "today-sharePrice":
            return await self.process_trade_payload(body, on_trade=on_trade, source_topic=topic)
        if topic == "summary":
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    self.latest_summary = parsed
            except json.JSONDecodeError as exc:
                self.last_error = {"stage": "summary_decode", "message": str(exc)}
            return 0
        if topic == "most-active-trades":
            try:
                parsed = json.loads(body)
                self.latest_most_active_trades = parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError as exc:
                self.last_error = {"stage": "most_active_decode", "message": str(exc)}
            return 0
        return 0

    def encode_sockjs_frame(self, stomp_frame: str) -> str:
        """SockJS websocket transport expects client messages as JSON arrays."""
        return json.dumps([stomp_frame])

    def decode_sockjs_message(self, message: str) -> List[str]:
        """Decode SockJS server frames into raw STOMP messages."""
        if message == "o" or message == "h" or not message:
            return []
        if message.startswith("a"):
            try:
                payload = json.loads(message[1:])
                return [item for item in payload if isinstance(item, str)]
            except json.JSONDecodeError as exc:
                self.last_error = {"stage": "sockjs_decode", "message": str(exc), "raw": message[:200]}
                return []
        if message.startswith("c"):
            self.last_error = {"stage": "sockjs_close", "message": message}
            return []
        # Some test fixtures and non-SockJS transports may provide raw STOMP.
        return [message]

    async def process_trade_payload(
        self,
        body: str,
        on_trade: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]] = None,
        source_topic: str = "daytrade",
    ) -> int:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            self.last_error = {"stage": "decode", "message": str(exc)}
            return 0

        trades = parsed if isinstance(parsed, list) else [parsed]
        processed = 0
        for trade in trades:
            tick = self._normalize_trade(trade, source_topic=source_topic)
            if tick is None:
                continue
            if tick.get("volume_estimated") and self.volume_estimator:
                enrichment = self.volume_estimator(tick["symbol"])
                estimated_volume = int(enrichment.get("estimated_volume") or tick["volume"])
                tick["volume"] = max(1, estimated_volume)
                tick["volume_estimation"] = enrichment
            symbol = tick["symbol"]
            if source_topic == "today-sharePrice":
                self.latest_share_price[symbol] = dict(trade)
            self.store.update_tick(symbol, tick)
            metrics = self.store.calculate_metrics(symbol)
            processed += 1
            if on_trade:
                on_trade(symbol, tick, metrics)
        return processed

    def _normalize_trade(self, trade: Any, source_topic: str = "daytrade") -> Optional[Dict[str, Any]]:
        if not isinstance(trade, dict):
            return None

        symbol = trade.get("symbol") or trade.get("s") or trade.get("security")
        price = trade.get("price") or trade.get("p") or trade.get("tradePrice") or trade.get("lastTradedPrice")
        volume = trade.get("volume") or trade.get("q") or trade.get("qty") or trade.get("quantity") or trade.get("shareVolume")
        timestamp = trade.get("timestamp") or trade.get("t") or trade.get("tradesTime") or trade.get("tradeDate") or time.time()
        volume_estimated = volume is None

        try:
            price = float(price)
            volume = 1 if volume_estimated else int(float(volume))
            timestamp = float(timestamp)
        except Exception:
            return None

        if not symbol or price <= 0 or volume <= 0:
            return None

        # CSE often emits millisecond timestamps; normalize to seconds.
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0

        return {
            "symbol": str(symbol),
            "price": price,
            "volume": volume,
            "volume_estimated": volume_estimated,
            "change": trade.get("change"),
            "changePercentage": trade.get("changePercentage"),
            "source_topic": source_topic,
            "timestamp": timestamp,
            "trade_time": time.time(),
        }

    def microstructure(self, symbol: str) -> Dict[str, Any]:
        metrics = self.store.calculate_metrics(symbol)
        metrics["source"] = "CSE_WEBSOCKET_DAYTRADE"
        return metrics

    def memory_stats(self) -> Dict[str, int]:
        return self.store.store_stats() if hasattr(self.store, "store_stats") else self.store.memory_stats()

    async def capture_for_seconds(
        self,
        seconds: int,
        on_trade: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]] = None,
    ) -> int:
        """Attempt a bounded live capture. Raises no exception to callers."""
        self.running = True
        captured = 0
        started = time.time()
        for use_fallback in (False, True):
            captured += await self._capture_once(seconds, on_trade, started, use_fallback)
            if captured > 0 or not self.last_error:
                break
        self.running = False
        return captured

    async def _capture_once(
        self,
        seconds: int,
        on_trade: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]],
        started: float,
        use_fallback: bool,
    ) -> int:
        captured = 0
        try:
            async with websockets.connect(
                self.websocket_url(use_fallback=use_fallback),
                additional_headers=CSE_WS_HEADERS,
                open_timeout=self.open_timeout,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                close_timeout=self.close_timeout,
            ) as websocket:
                self.last_error = None
                sent_handshake = False
                while self.running and time.time() - started < seconds:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue

                    if message == "o" and not sent_handshake:
                        await websocket.send(self.encode_sockjs_frame(self.connect_frame()))
                        sent_handshake = True
                        continue

                    for stomp_message in self.decode_sockjs_message(message):
                        frame = StompFrame.parse(stomp_message)
                        if frame.command == "CONNECTED":
                            for outgoing_frame in self.subscription_frames():
                                await websocket.send(self.encode_sockjs_frame(outgoing_frame))
                        elif frame.command == "MESSAGE":
                            topic = frame.headers.get("destination", "").split("/")[-1]
                            captured += await self.process_topic_payload(topic, frame.body, on_trade=on_trade)
        except Exception as exc:
            self.last_error = {
                "stage": "capture",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "base": self.fallback_websocket_base if use_fallback else self.websocket_base,
            }
        return captured

    async def run_live_feed(
        self,
        on_trade: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]] = None,
        should_continue: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Stream live trades until should_continue() returns False."""
        self.running = True
        should_continue = should_continue or (lambda: True)
        backoff = 1.0
        while self.running and should_continue():
            captured = 0
            for use_fallback in (False, True):
                captured = await self._capture_once(3600, on_trade, time.time(), use_fallback)
                if captured > 0 or not self.last_error:
                    backoff = 1.0
                    break
            if not should_continue():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
        self.running = False

    async def stop(self) -> None:
        self.running = False
