"""Intraday context layer + live tick preference tests.

These lock in the behaviour that order-book / microstructure snapshots are kept
in a separate, lightly-weighted context layer that nudges the daily ensemble and
informs confidence/quality flags without entering ARIMA/VaR. They also verify
that the analysis service prefers the shared live tick window over the REST
microstructure proxy when ticks are available.
"""

from __future__ import annotations

import time
import unittest

import pandas as pd

from argus_final.analytics.intraday_context import (
    MAX_INTRADAY_NUDGE,
    build_intraday_context,
    combine_ensemble,
    intraday_confidence_penalties,
    intraday_scores,
)
from argus_final.data.providers import InMemoryMarketDataProvider
from argus_final.data.tick_store import InMemoryTickStore
from argus_final.services import AnalysisService


def _df(last_close: float = 200.0, rows: int = 130) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=rows, freq="D"),
            "open": last_close,
            "high": last_close * 1.01,
            "low": last_close * 0.99,
            "close": last_close,
            "volume": 50_000,
        }
    )


class IntradayContextUnitTests(unittest.TestCase):
    def test_unavailable_context_produces_zero_nudge_and_warning(self):
        ctx = build_intraday_context(_df(), {"source": "UNAVAILABLE"}, {})
        self.assertFalse(ctx["available"])
        self.assertEqual(intraday_scores(ctx), (0.0, 0.0, 0.0))
        self.assertIn("Intraday context unavailable; analysis is daily-only", ctx["warnings"])

    def test_order_flow_pressure_caps_nudge_and_combines_with_daily_vote(self):
        df = _df(last_close=200.0)
        # price 210 vs close 200 => +5% divergence; vwap 205 => +2.4% deviation.
        # Both intraday terms saturate, so intraday_score hits its 0.10 cap and
        # together with order_flow (pressure=1 -> 0.10) the nudge reaches 0.20.
        micro = {"latest_price": 210.0, "vwap": 205.0, "trade_intensity": 12, "tick_count": 20, "source": "CSE_WEBSOCKET_DAYTRADE", "last_update": time.time()}
        ob = {"pressure": 1.0}
        ctx = build_intraday_context(df, micro, ob)
        order_flow, intraday, nudge = intraday_scores(ctx)
        self.assertGreater(order_flow, 0)
        self.assertGreater(intraday, 0)
        self.assertAlmostEqual(nudge, MAX_INTRADAY_NUDGE, places=4)

        daily = {"signal": "NEUTRAL", "score": 0.0, "confidence": 0.8, "components": {"trend_score": 0.0}}
        combined = combine_ensemble(daily, ctx, 0.8)
        self.assertGreaterEqual(combined["score"], 0.2)
        self.assertEqual(combined["signal"], "BULLISH")
        self.assertIn("order_flow_score", combined["components"])
        self.assertIn("intraday_score", combined["components"])
        self.assertEqual(combined["daily_score"], 0.0)

    def test_stale_snapshot_damps_nudge_to_zero(self):
        df = _df()
        micro = {"latest_price": 202.0, "vwap": 201.0, "tick_count": 5, "source": "CSE_WEBSOCKET_DAYTRADE", "last_update": time.time() - 9999}
        ctx = build_intraday_context(df, micro, {"pressure": 1.0})
        self.assertTrue(ctx["is_stale"])
        _, _, nudge = intraday_scores(ctx)
        self.assertEqual(nudge, 0.0)

    def test_price_divergence_raises_confidence_penalty(self):
        df = _df(last_close=200.0)
        micro = {"latest_price": 210.0, "vwap": 205.0, "tick_count": 10, "source": "CSE_REST_TRADE_SUMMARY", "last_update": time.time()}
        ctx = build_intraday_context(df, micro, {"pressure": 0.0})
        penalties = intraday_confidence_penalties(ctx)
        self.assertIn("price_divergence", penalties)
        self.assertGreater(penalties["price_divergence"], 0.0)
        self.assertLessEqual(penalties["price_divergence"], 0.10)


class AnalysisServiceIntradayTests(unittest.TestCase):
    def test_live_tick_store_is_preferred_over_rest_microstructure(self):
        tick_store = InMemoryTickStore()
        now = time.time()
        for price, ts in ((203.0, now - 20), (203.25, now - 10), (202.75, now)):
            tick_store.update_tick("COMB.N0000", {"symbol": "COMB.N0000", "price": price, "volume": 1000, "timestamp": ts})

        service = AnalysisService(
            data_provider=InMemoryMarketDataProvider(),
            tick_store=tick_store,
        )
        payload = service.analyze("Analyze COMB", demo_mode=True)

        self.assertEqual(payload["data_lineage"]["live_source"], "CSE_WEBSOCKET_DAYTRADE")
        self.assertEqual(payload["microstructure"]["source"], "CSE_WEBSOCKET_DAYTRADE")
        self.assertGreater(payload["microstructure"]["tick_count"], 0)
        self.assertIn("intraday_context", payload)
        self.assertTrue(payload["intraday_context"]["available"])
        self.assertEqual(payload["intraday_context"]["source"], "CSE_WEBSOCKET_DAYTRADE")
        # math_results stays the pure daily ensemble; combined vote is top-level.
        self.assertIn("order_flow_score", payload["indicator_vote"]["components"])
        self.assertNotIn("order_flow_score", payload["math_results"]["indicator_vote"]["components"])
        self.assertIn("order_book_snapshot", payload["quality_flags"])

    def test_demo_mode_produces_synthetic_intraday_context(self):
        # In offline demo mode (no live WebSocket), the in-memory provider now
        # synthesizes a coherent intraday window so the intraday context layer
        # is exercised end-to-end. It is clearly tagged as synthetic demo data
        # and derives from the last daily bar so price divergence is small and
        # consistent (never the stale -8% mismatch seen with fixed demo prices).
        service = AnalysisService(data_provider=InMemoryMarketDataProvider())
        payload = service.analyze("Analyze COMB", demo_mode=True)

        self.assertEqual(payload["data_lineage"]["live_source"], "IN_MEMORY_DEMO")
        ctx = payload["intraday_context"]
        self.assertTrue(ctx["available"])
        self.assertEqual(ctx["source"], "DEMO_INTRADAY")
        # Synthetic intraday nudges the ensemble; never dominates the daily vote.
        nudge = payload["indicator_vote"]["intraday_nudge"]
        self.assertGreater(nudge, 0.0)
        self.assertLessEqual(nudge, MAX_INTRADAY_NUDGE)
        # Coherent with the last daily close: divergence is small, no false alarm.
        self.assertIsNotNone(ctx["price_divergence_pct"])
        self.assertLess(abs(ctx["price_divergence_pct"]), 1.0)
        self.assertFalse(ctx["is_stale"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
