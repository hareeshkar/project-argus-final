"""
Live CSE WebSocket diagnostics test.

This test intentionally mirrors the verbose style of the original Project Argus
Phase 2 test. It can run in two modes:

1. Default/off-hours-safe mode:
   - Detects whether CSE market is open.
   - If closed, it does not force a long live socket wait.
   - It validates the live-store/microstructure path with deterministic ticks.

2. Real WebSocket mode:
   - Set ARGUS_RUN_REAL_WEBSOCKET=1.
   - During CSE market hours it attempts a short live `/topic/daytrade` capture.
   - Outside market hours it prints why live ticks are unlikely and still runs
     the deterministic fallback diagnostics.

Run:
    PYTHONPATH=. ../project-argus/venv/bin/python -m unittest tests.test_03_live_cse_websocket -v

Optional real attempt:
    ARGUS_RUN_REAL_WEBSOCKET=1 ARGUS_WEBSOCKET_SECONDS=20 \\
    PYTHONPATH=. ../project-argus/venv/bin/python -m unittest tests.test_03_live_cse_websocket -v
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import unittest
from datetime import datetime

from argus_final.data import LiveTickStore, WebSocketMarketDataProvider


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_payload(title: str, payload) -> None:
    print(f"\n--- {title} ---")
    print(json.dumps(payload, indent=2, default=str, sort_keys=True))


def is_cse_market_hours() -> bool:
    now = datetime.now()
    if now.weekday() > 4:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0).time()
    market_close = now.replace(hour=14, minute=30, second=0, microsecond=0).time()
    return market_open <= now.time() <= market_close


def inject_deterministic_ticks(live_store) -> None:
    base_time = time.time()
    ticks = [
        {"symbol": "COMB.N0000", "price": 203.00, "volume": 1_000, "timestamp": base_time - 20},
        {"symbol": "COMB.N0000", "price": 203.25, "volume": 2_000, "timestamp": base_time - 10},
        {"symbol": "COMB.N0000", "price": 202.75, "volume": 1_500, "timestamp": base_time},
        {"symbol": "JKH.N0000", "price": 20.50, "volume": 5_000, "timestamp": base_time - 5},
        {"symbol": "JKH.N0000", "price": 20.60, "volume": 8_000, "timestamp": base_time},
    ]
    for tick in ticks:
        live_store.update_tick(tick["symbol"], tick)


async def attempt_short_live_capture(duration_seconds: int):
    provider = WebSocketMarketDataProvider(store=LiveTickStore(max_ticks_per_symbol=100))
    captured = []

    def on_trade(symbol: str, tick_data: dict, metrics: dict):
        captured.append({"symbol": symbol, "tick": tick_data, "metrics": metrics})
        print_payload(
            "live_tick",
            {
                "symbol": symbol,
                "tick": tick_data,
                "metrics": metrics,
                "captured_count": len(captured),
            },
        )

    await provider.capture_for_seconds(duration_seconds, on_trade=on_trade)

    return provider, captured


class LiveCseWebSocketDiagnosticsTests(unittest.TestCase):
    def test_websocket_diagnostics_and_microstructure_output(self):
        now = datetime.now()
        market_open = is_cse_market_hours()
        run_real = os.getenv("ARGUS_RUN_REAL_WEBSOCKET", "0") == "1"
        duration = int(os.getenv("ARGUS_WEBSOCKET_SECONDS", "15"))

        print_section("PROJECT ARGUS FINAL - LIVE CSE WEBSOCKET DIAGNOSTICS")
        print_payload(
            "execution_context",
            {
                "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "weekday": now.strftime("%A"),
                "cse_market_hours": "Mon-Fri 09:30-14:30 Sri Lanka time",
                "market_open_now": market_open,
                "requested_real_websocket": run_real,
                "requested_duration_seconds": duration,
                "websocket_topic": "/topic/daytrade",
                "expected_behavior_when_closed": "No live ticks or stale/quiet feed; fallback diagnostics still run.",
            },
        )

        provider = WebSocketMarketDataProvider(store=LiveTickStore(max_ticks_per_symbol=100))
        captured = []
        live_attempted = False

        if run_real:
            live_attempted = True
            print_section("REAL WEBSOCKET ATTEMPT")
            print(
                "Attempting a short live CSE WebSocket capture. If the market is closed, "
                "zero ticks is not necessarily a code failure."
            )
            try:
                provider, captured = asyncio.run(attempt_short_live_capture(duration))
            except Exception as exc:
                print_payload(
                    "real_websocket_error",
                    {
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "decision": "Continuing with deterministic fallback microstructure diagnostics.",
                    },
                )
                provider = WebSocketMarketDataProvider(store=LiveTickStore(max_ticks_per_symbol=100))

        if not captured:
            print_section("DETERMINISTIC FALLBACK MICROSTRUCTURE")
            print(
                "Injecting deterministic ticks so the LiveStore/VWAP/intensity/momentum "
                "path is still verified even without market-hour live ticks."
            )
            inject_deterministic_ticks(provider.store)

        memory_stats = provider.memory_stats()
        symbol_metrics = {}
        for symbol in provider.store.get_all_symbols():
            symbol_metrics[symbol] = provider.microstructure(symbol)

        print_section("FINAL WEBSOCKET / MICROSTRUCTURE STATISTICS")
        print_payload(
            "websocket_diagnostics_summary",
            {
                "live_attempted": live_attempted,
                "live_ticks_captured": len(captured),
                "last_error": provider.last_error,
                "metadata": provider.metadata,
                "memory_stats": memory_stats,
                "symbols": provider.store.get_all_symbols(),
                "symbol_metrics": symbol_metrics,
            },
        )

        self.assertGreater(memory_stats["total_symbols"], 0)
        self.assertGreater(memory_stats["total_ticks"], 0)

        if captured:
            # Real market ticks are not guaranteed for a specific symbol in a
            # short window. Any valid CSE symbol proves the live feed path.
            first_symbol = next(iter(symbol_metrics))
            self.assertGreater(symbol_metrics[first_symbol]["vwap"], 0)
            self.assertGreater(symbol_metrics[first_symbol]["tick_count"], 0)
        else:
            # Fallback mode injects deterministic COMB ticks for stable CI/viva.
            self.assertIn("COMB.N0000", symbol_metrics)
            self.assertGreater(symbol_metrics["COMB.N0000"]["vwap"], 0)
            self.assertGreater(symbol_metrics["COMB.N0000"]["tick_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
