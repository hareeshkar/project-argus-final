from __future__ import annotations

from typing import Dict, Optional, Protocol

import numpy as np
import pandas as pd


class MarketDataProvider(Protocol):
    def historical_ohlcv(self, symbol: str) -> pd.DataFrame:
        ...

    def order_book(self, symbol: str) -> Dict[str, float]:
        ...

    def microstructure(self, symbol: str) -> Dict[str, float]:
        ...


class InMemoryMarketDataProvider:
    """Deterministic provider for tests, offline demos, and viva safety."""

    def __init__(self, rows: int = 120):
        self.rows = rows
        self._last_frame: Optional[pd.DataFrame] = None

    def historical_ohlcv(self, symbol: str) -> pd.DataFrame:
        base = 200.0 if symbol.startswith("COMB") else 100.0
        x = np.arange(self.rows, dtype=float)
        trend = base + x * (base * 0.0009)
        seasonal = np.sin(x / 5.5) * (base * 0.006)
        micro_cycle = np.cos(x / 2.7) * (base * 0.0025)
        close = pd.Series(trend + seasonal + micro_cycle, dtype=float)
        close.iloc[-1] = close.iloc[-2] * 0.9985
        volume = pd.Series(48_000 + (np.sin(x / 4.0) * 9_000) + x * 120, dtype=float)

        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=self.rows, freq="D"),
                "open": close.shift(1).fillna(close.iloc[0]),
                "high": close * 1.012,
                "low": close * 0.988,
                "close": close,
                "volume": volume,
            }
        )
        self._last_frame = frame
        return frame

    def order_book(self, symbol: str) -> Dict[str, float]:
        bids = 324_649
        asks = 164_686
        pressure = (bids - asks) / (bids + asks)
        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "pressure": round(pressure, 4),
            "spread_estimate": 0.25,
            "last_updated": pd.Timestamp.utcnow().timestamp(),
        }

    def microstructure(self, symbol: str) -> Dict[str, float]:
        # Synthesize a coherent intraday window from the last daily bar so demo
        # mode exercises the intraday context layer (Panel 14) without a live
        # WebSocket. Small bullish drift consistent with the bid-heavy book.
        last_close = 200.0
        if self._last_frame is not None and not self._last_frame.empty:
            try:
                last_close = float(self._last_frame["close"].iloc[-1])
            except Exception:
                last_close = 200.0
        latest_price = round(last_close * 1.002, 4)
        vwap = round(last_close * 1.0005, 4)
        return {
            "symbol": symbol,
            "latest_price": latest_price,
            "vwap": vwap,
            "trade_intensity": 18,
            "price_momentum": round(latest_price - last_close, 4),
            "window_volume": 168_192,
            "tick_count": 86,
            "last_update": pd.Timestamp.utcnow().timestamp(),
            "source": "DEMO_INTRADAY",
        }

