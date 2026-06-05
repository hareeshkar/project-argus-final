from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
import pandas as pd


CSE_BASE_URL = "https://www.cse.lk/api"
CSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.cse.lk/",
    "Origin": "https://www.cse.lk",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json, text/plain, */*",
}

CHART_MAP = {
    "p": "close",
    "q": "volume",
    "h": "high",
    "l": "low",
    "t": "timestamp",
    "o": "open",
    "s": "turnover",
}


class CseRestProviderError(RuntimeError):
    """Structured provider failure after retries are exhausted."""

    def __init__(self, endpoint: str, message: str, attempts: int):
        super().__init__(f"CSE REST {endpoint} failed after {attempts} attempts: {message}")
        self.endpoint = endpoint
        self.message = message
        self.attempts = attempts


def clean_cse_chart_data(raw_candles: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Map CSE minified chart fields into an OHLCV frame with quality metadata."""
    quality = {
        "has_missing_values": False,
        "has_null_open_prices": False,
        "used_open_price_proxy": False,
        "open_price_proxy_ratio": 0.0,
        "raw_rows": len(raw_candles or []),
        "clean_rows": 0,
        "warnings": [],
    }

    if not raw_candles:
        quality["warnings"].append("CSE returned no chart rows")
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]), quality

    frame = pd.DataFrame(raw_candles).rename(columns=CHART_MAP)
    available = [column for column in CHART_MAP.values() if column in frame.columns]
    frame = frame[available]

    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms")

    for column in ["open", "high", "low", "close", "volume", "turnover"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if "open" not in frame.columns:
        frame["open"] = pd.NA

    null_open = frame["open"].isna()
    quality["has_null_open_prices"] = bool(null_open.any())
    quality["open_price_proxy_ratio"] = float(null_open.mean())
    if quality["has_null_open_prices"]:
        frame.loc[null_open, "open"] = frame.loc[null_open, "close"]
        quality["used_open_price_proxy"] = True
        quality["warnings"].append("CSE open prices were null; close price proxy used")

    required = ["timestamp", "open", "high", "low", "close", "volume"]
    for column in required:
        if column not in frame.columns:
            frame[column] = pd.NA

    quality["has_missing_values"] = bool(frame[required].isna().any().any())
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    quality["clean_rows"] = len(frame)

    return frame, quality


class CseRestMarketDataProvider:
    """Native final live provider for CSE REST historical and order-book data."""

    def __init__(
        self,
        base_url: str = CSE_BASE_URL,
        timeout_seconds: float = 10.0,
        verify_tls: bool = False,
        max_retries: int = 3,
        retry_sleep_seconds: float = 0.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.verify_tls = verify_tls
        self.max_retries = max(1, max_retries)
        self.retry_sleep_seconds = max(0.0, retry_sleep_seconds)
        self.symbol_to_id: Dict[str, int] = {}
        self.last_quality_flags: Dict[str, Any] = {}
        self.last_historical_timestamp: Optional[str] = None
        self.last_historical_frame: Optional[pd.DataFrame] = None
        self.last_error: Optional[Dict[str, Any]] = None
        self._trade_summary_cache: Optional[List[Dict[str, Any]]] = None
        self.metadata = {
            "historical_source": "CSE_REST",
            "order_book_source": "CSE_REST_ORDERBOOK",
            "live_source": "NOT_CONFIGURED",
            "provider": "CseRestMarketDataProvider",
        }

    def _post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        last_message = "unknown error"
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(
                    headers=CSE_HEADERS,
                    timeout=self.timeout_seconds,
                    verify=self.verify_tls,
                ) as client:
                    response = client.post(f"{self.base_url}/{endpoint}", data=data or {})
                    response.raise_for_status()
                    self.last_error = None
                    return response.json()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                last_message = f"HTTP {status_code}: {exc}"
            except httpx.RequestError as exc:
                last_message = str(exc)
            except ValueError as exc:
                last_message = f"Invalid JSON response: {exc}"

            if attempt < self.max_retries and self.retry_sleep_seconds:
                time.sleep(self.retry_sleep_seconds * attempt)

        self.last_error = {
            "endpoint": endpoint,
            "message": last_message,
            "attempts": self.max_retries,
        }
        raise CseRestProviderError(endpoint, last_message, self.max_retries)

    def sync_symbols(self) -> Dict[str, int]:
        payload = self._post("tradeSummary")
        stocks = payload.get("reqTradeSummery", [])
        self._trade_summary_cache = stocks
        self.symbol_to_id = {
            item["symbol"]: item["id"]
            for item in stocks
            if isinstance(item, dict) and "symbol" in item and "id" in item
        }
        return self.symbol_to_id

    def trade_summary_rows(self, refresh: bool = False) -> List[Dict[str, Any]]:
        if self._trade_summary_cache is None or refresh:
            payload = self._post("tradeSummary")
            self._trade_summary_cache = payload.get("reqTradeSummery", [])
        return self._trade_summary_cache or []

    def trade_summary(self, symbol: str, refresh: bool = False) -> Dict[str, Any]:
        for row in self.trade_summary_rows(refresh=refresh):
            if row.get("symbol") == symbol:
                return row
        return {}

    def most_active_trades(self) -> List[Dict[str, Any]]:
        payload = self._post("mostActiveTrades")
        return payload if isinstance(payload, list) else []

    def most_active_volumes(self) -> List[Dict[str, Any]]:
        payload = self._post("mostActiveVolumes")
        return payload if isinstance(payload, list) else []

    def market_status(self) -> Dict[str, Any]:
        return self._post("marketStatus")

    def market_summary(self) -> Dict[str, Any]:
        return self._post("marketSummery")

    def all_sectors(self, period: Optional[int] = None) -> List[Dict[str, Any]]:
        data = {"period": str(period)} if period is not None else {}
        payload = self._post("allSectors", data)
        return payload if isinstance(payload, list) else []

    def approved_announcements(self) -> List[Dict[str, Any]]:
        payload = self._post("approvedAnnouncement")
        return payload.get("approvedAnnouncements", []) if isinstance(payload, dict) else []

    def news_top(self, news_type: str = "CN", number_of_records: int = 3) -> List[Dict[str, Any]]:
        payload = self._post(f"news/web?top=true&type={news_type}&numberOfRecord={number_of_records}")
        return payload.get(news_type, []) if isinstance(payload, dict) else []

    def estimate_tick_volume(self, symbol: str, refresh: bool = False) -> Dict[str, Any]:
        """Estimate live tick volume when WebSocket daytrade omits quantity.

        CSE `/topic/daytrade` often carries price/change only. `/api/tradeSummary`
        carries quantity, sharevolume, tradevolume, turnover, and lastTradedTime.
        This helper prefers `quantity` for the latest symbol-level trade size and
        includes cumulative fields for downstream confidence/liquidity logic.
        """
        row = self.trade_summary(symbol, refresh=refresh)
        if not row:
            return {
                "symbol": symbol,
                "estimated_volume": 1,
                "method": "fallback_unit",
                "volume_estimated": True,
                "warning": "No tradeSummary row available for symbol",
            }

        quantity = int(float(row.get("quantity") or 0))
        sharevolume = int(float(row.get("sharevolume") or row.get("shareVolume") or 0))
        tradevolume = int(float(row.get("tradevolume") or row.get("tradeVolume") or 0))
        estimated_volume = quantity if quantity > 0 else 1
        method = "quantity" if quantity > 0 else "fallback_unit"

        return {
            "symbol": symbol,
            "estimated_volume": estimated_volume,
            "method": method,
            "volume_estimated": method != "quantity",
            "quantity": quantity,
            "sharevolume": sharevolume,
            "tradevolume": tradevolume,
            "turnover": float(row.get("turnover") or 0.0),
            "lastTradedTime": row.get("lastTradedTime"),
        }

    def historical_ohlcv(self, symbol: str) -> pd.DataFrame:
        if not self.symbol_to_id:
            self.sync_symbols()

        stock_id = self.symbol_to_id.get(symbol)
        if not stock_id:
            raise ValueError(f"Symbol {symbol} not found in CSE universe")

        payload = self._post("companyChartDataByStock", {"stockId": stock_id, "period": "5"})
        raw_data = payload.get("chartData", [])
        frame, quality = clean_cse_chart_data(raw_data)
        self.last_quality_flags = quality
        self.last_historical_timestamp = str(frame["timestamp"].iloc[-1]) if not frame.empty else None
        self.last_historical_frame = frame
        return frame

    def order_book(self, symbol: str) -> Dict[str, Any]:
        payload = self._post("orderBook", {"symbol": symbol})
        totals = payload.get("reqOrderBookTotal", {})
        bids = int(totals.get("totalBids", 0) or 0)
        asks = int(totals.get("totalAsks", 0) or 0)
        pressure = (bids - asks) / (bids + asks) if (bids + asks) > 0 else 0.0
        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "pressure": round(pressure, 4),
        }

    def microstructure(self, symbol: str) -> Dict[str, Any]:
        latest_price = 0.0
        window_volume = 0
        last_update = None
        if self.last_historical_frame is not None and not self.last_historical_frame.empty:
            latest_row = self.last_historical_frame.iloc[-1]
            latest_price = float(latest_row.get("close") or 0.0)
            window_volume = int(float(latest_row.get("volume") or 0))
            last_update = self.last_historical_timestamp
        trade_row = self.trade_summary(symbol)
        summary_price = float(trade_row.get("lastTradedPrice") or trade_row.get("price") or 0.0) if trade_row else 0.0
        if summary_price > 0:
            latest_price = summary_price
            last_update = trade_row.get("lastTradedTime") or last_update
        quantity = int(float(trade_row.get("quantity") or 0)) if trade_row else 0
        if quantity > 0:
            window_volume = quantity

        return {
            "symbol": symbol,
            "latest_price": latest_price,
            "vwap": latest_price,
            "trade_intensity": 0,
            "price_momentum": 0.0,
            "window_volume": window_volume,
            "tick_count": 0,
            "last_update": last_update,
            "source": "CSE_REST_TRADE_SUMMARY",
            "note": "REST-only microstructure proxy; WebSocket tick stream is not wired into this provider",
        }
