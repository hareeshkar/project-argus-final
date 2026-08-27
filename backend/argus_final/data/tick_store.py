from __future__ import annotations

import json
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Protocol, runtime_checkable

try:
    import redis
except ImportError:  # pragma: no cover - optional until requirements installed
    redis = None  # type: ignore


def calculate_metrics_from_ticks(
    snapshot: List[Dict[str, Any]],
    symbol: str,
    last_update: Optional[float] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    if not snapshot:
        return {
            "symbol": symbol,
            "latest_price": 0.0,
            "vwap": 0.0,
            "trade_intensity": 0,
            "price_momentum": 0.0,
            "window_volume": 0,
            "tick_count": 0,
            "last_update": last_update,
        }

    prices: List[float] = []
    volumes: List[int] = []
    timestamps: List[float] = []
    for tick in snapshot:
        try:
            price = float(tick.get("price", 0))
            volume = int(float(tick.get("volume", 0)))
            timestamp = float(tick.get("timestamp", time.time()))
        except Exception:
            continue
        if price > 0 and volume > 0:
            prices.append(price)
            volumes.append(volume)
            timestamps.append(timestamp)

    if not prices:
        return {
            "symbol": symbol,
            "latest_price": 0.0,
            "vwap": 0.0,
            "trade_intensity": 0,
            "price_momentum": 0.0,
            "window_volume": 0,
            "tick_count": 0,
            "last_update": last_update,
        }

    current_time = now if now is not None else time.time()
    total_volume = sum(volumes)
    total_value = sum(price * volume for price, volume in zip(prices, volumes))
    return {
        "symbol": symbol,
        "latest_price": prices[-1],
        "vwap": total_value / total_volume if total_volume else 0.0,
        "trade_intensity": len([timestamp for timestamp in timestamps if current_time - timestamp <= 60]),
        "price_momentum": prices[-1] - prices[0] if len(prices) > 1 else 0.0,
        "window_volume": total_volume,
        "tick_count": len(prices),
        "last_update": last_update,
    }


@runtime_checkable
class TickStore(Protocol):
    def update_tick(self, symbol: str, tick: Dict[str, Any]) -> None: ...

    def get_ticks(self, symbol: str) -> List[Dict[str, Any]]: ...

    def get_all_symbols(self) -> List[str]: ...

    def memory_stats(self) -> Dict[str, int]: ...

    def store_stats(self) -> Dict[str, int]: ...

    def calculate_metrics(self, symbol: str, now: Optional[float] = None) -> Dict[str, Any]: ...


class InMemoryTickStore:
    """Bounded in-memory tick store with safe snapshot-based metrics."""

    def __init__(self, max_ticks_per_symbol: int = 100):
        self.max_ticks_per_symbol = max_ticks_per_symbol
        self._ticks: Dict[str, Deque[Dict[str, Any]]] = {}
        self._last_update: Dict[str, float] = {}

    def update_tick(self, symbol: str, tick: Dict[str, Any]) -> None:
        if symbol not in self._ticks:
            self._ticks[symbol] = deque(maxlen=self.max_ticks_per_symbol)
        if "timestamp" not in tick or tick["timestamp"] is None:
            tick["timestamp"] = time.time()
        self._ticks[symbol].append(dict(tick))
        self._last_update[symbol] = time.time()

    def get_ticks(self, symbol: str) -> List[Dict[str, Any]]:
        return list(self._ticks.get(symbol, []))

    def get_all_symbols(self) -> List[str]:
        return sorted(self._ticks.keys())

    def memory_stats(self) -> Dict[str, int]:
        return self.store_stats()

    def store_stats(self) -> Dict[str, int]:
        return {
            "total_symbols": len(self._ticks),
            "total_ticks": sum(len(ticks) for ticks in self._ticks.values()),
            "max_ticks_per_symbol": self.max_ticks_per_symbol,
        }

    def calculate_metrics(self, symbol: str, now: Optional[float] = None) -> Dict[str, Any]:
        return calculate_metrics_from_ticks(
            self.get_ticks(symbol),
            symbol,
            self._last_update.get(symbol),
            now,
        )


LiveTickStore = InMemoryTickStore


class RedisTickStore:
    """Shared Redis-backed tick store (LPUSH + LTRIM + TTL)."""

    def __init__(
        self,
        client: "redis.Redis",
        *,
        max_ticks_per_symbol: int = 100,
        ttl_seconds: int = 3600,
        key_prefix: str = "argus:ticks",
    ):
        self.client = client
        self.max_ticks_per_symbol = max_ticks_per_symbol
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix

    def _list_key(self, symbol: str) -> str:
        return f"{self.key_prefix}:{symbol}"

    def _lu_key(self, symbol: str) -> str:
        return f"{self.key_prefix}:{symbol}:lu"

    def update_tick(self, symbol: str, tick: Dict[str, Any]) -> None:
        if "timestamp" not in tick or tick["timestamp"] is None:
            tick["timestamp"] = time.time()
        payload = json.dumps(tick, default=str)
        list_key = self._list_key(symbol)
        lu_key = self._lu_key(symbol)
        pipe = self.client.pipeline()
        pipe.lpush(list_key, payload)
        pipe.ltrim(list_key, 0, self.max_ticks_per_symbol - 1)
        pipe.set(lu_key, str(time.time()))
        pipe.expire(list_key, self.ttl_seconds)
        pipe.expire(lu_key, self.ttl_seconds)
        pipe.execute()

    def get_ticks(self, symbol: str) -> List[Dict[str, Any]]:
        raw_items = self.client.lrange(self._list_key(symbol), 0, -1)
        ticks: List[Dict[str, Any]] = []
        for raw in reversed(raw_items):
            try:
                ticks.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return ticks

    def get_all_symbols(self) -> List[str]:
        symbols: List[str] = []
        for key in self.client.scan_iter(f"{self.key_prefix}:*"):
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            if key_str.endswith(":lu"):
                continue
            suffix = key_str.removeprefix(f"{self.key_prefix}:")
            if suffix:
                symbols.append(suffix)
        return sorted(set(symbols))

    def store_stats(self) -> Dict[str, int]:
        symbols = self.get_all_symbols()
        total_ticks = sum(self.client.llen(self._list_key(symbol)) for symbol in symbols)
        return {
            "total_symbols": len(symbols),
            "total_ticks": int(total_ticks),
            "max_ticks_per_symbol": self.max_ticks_per_symbol,
        }

    def memory_stats(self) -> Dict[str, int]:
        return self.store_stats()

    def calculate_metrics(self, symbol: str, now: Optional[float] = None) -> Dict[str, Any]:
        lu_raw = self.client.get(self._lu_key(symbol))
        last_update = float(lu_raw) if lu_raw else None
        return calculate_metrics_from_ticks(self.get_ticks(symbol), symbol, last_update, now)

    def close(self) -> None:
        self.client.close()


def build_tick_store(settings) -> TickStore:
    """Create Redis store when enabled and reachable; otherwise in-memory."""
    if getattr(settings, "redis_ticks_enabled", False) and redis is not None:
        try:
            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            return RedisTickStore(
                client,
                max_ticks_per_symbol=settings.max_ticks_per_symbol,
                ttl_seconds=settings.tick_ttl_seconds,
            )
        except Exception:
            pass
    return InMemoryTickStore(max_ticks_per_symbol=settings.max_ticks_per_symbol)
