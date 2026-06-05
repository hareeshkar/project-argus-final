"""
Unit tests for the native final WebSocket provider internals.
"""

from __future__ import annotations

import asyncio
import json
import unittest

from argus_final.data.websocket_provider import LiveTickStore, StompFrame, WebSocketMarketDataProvider


class WebSocketProviderUnitTests(unittest.TestCase):
    def test_live_tick_store_calculates_vwap_intensity_and_momentum(self):
        store = LiveTickStore(max_ticks_per_symbol=3)
        store.update_tick("COMB.N0000", {"symbol": "COMB.N0000", "price": 203.0, "volume": 1000, "timestamp": 1000.0})
        store.update_tick("COMB.N0000", {"symbol": "COMB.N0000", "price": 204.0, "volume": 2000, "timestamp": 1010.0})
        store.update_tick("COMB.N0000", {"symbol": "COMB.N0000", "price": 202.0, "volume": 3000, "timestamp": 1020.0})
        store.update_tick("COMB.N0000", {"symbol": "COMB.N0000", "price": 205.0, "volume": 4000, "timestamp": 1030.0})

        metrics = store.calculate_metrics("COMB.N0000", now=1030.0)

        self.assertEqual(metrics["tick_count"], 3)
        self.assertAlmostEqual(metrics["vwap"], (204 * 2000 + 202 * 3000 + 205 * 4000) / 9000)
        self.assertEqual(metrics["trade_intensity"], 3)
        self.assertEqual(metrics["price_momentum"], 1.0)

        print("\n\n=== websocket_live_tick_store_metrics ===")
        print(json.dumps(metrics, indent=2, sort_keys=True))

    def test_stomp_frame_parses_message_body(self):
        body = json.dumps([{"symbol": "COMB.N0000", "price": 203.0, "volume": 1000, "timestamp": 1770000000000}])
        frame = f"MESSAGE\ndestination:/topic/daytrade\n\n{body}\x00"

        parsed = StompFrame.parse(frame)

        self.assertEqual(parsed.command, "MESSAGE")
        self.assertEqual(parsed.headers["destination"], "/topic/daytrade")
        self.assertEqual(parsed.body, body)

    def test_provider_preserves_cse_required_url_headers_and_frames(self):
        provider = WebSocketMarketDataProvider()

        primary_url = provider.websocket_url()
        fallback_url = provider.websocket_url(use_fallback=True)
        connect_frame = StompFrame.parse(provider.connect_frame())
        subscribe_frame = StompFrame.parse(provider.subscribe_frame())
        user_subscribe_frame = StompFrame.parse(provider.user_subscribe_frame())
        request_frame = StompFrame.parse(provider.request_daytrade_frame())

        self.assertIn("wss://www.cse.lk/api/ws/", primary_url)
        self.assertIn("wss://www.cse.lk/ws/8/", fallback_url)
        self.assertTrue(primary_url.endswith("/websocket"))
        self.assertTrue(fallback_url.endswith("/websocket"))

        self.assertEqual(connect_frame.command, "CONNECT")
        self.assertEqual(connect_frame.headers["accept-version"], "1.2,1.1,1.0")
        self.assertEqual(connect_frame.headers["heart-beat"], "10000,10000")

        self.assertEqual(subscribe_frame.command, "SUBSCRIBE")
        self.assertEqual(subscribe_frame.headers["destination"], "/topic/daytrade")
        self.assertEqual(user_subscribe_frame.command, "SUBSCRIBE")
        self.assertEqual(user_subscribe_frame.headers["destination"], "/user/topic/daytrade")
        self.assertEqual(request_frame.command, "SEND")
        self.assertEqual(request_frame.headers["destination"], "/app/request-daytrade")

        print("\n\n=== websocket_cse_required_handshake ===")
        print(json.dumps({
            "primary_url_sample": primary_url,
            "fallback_url_sample": fallback_url,
            "sockjs_encoded_connect": provider.encode_sockjs_frame(provider.connect_frame()).replace("\\u0000", "^@"),
            "connect_headers": connect_frame.headers,
            "subscribe_headers": subscribe_frame.headers,
            "user_subscribe_headers": user_subscribe_frame.headers,
            "request_headers": request_frame.headers,
            "provider_metadata": provider.metadata,
        }, indent=2, sort_keys=True))

    def test_provider_processes_daytrade_payload(self):
        provider = WebSocketMarketDataProvider()
        body = json.dumps(
            [
                {"symbol": "COMB.N0000", "price": 203.0, "volume": 1000, "timestamp": 1770000000000},
                {"symbol": "COMB.N0000", "price": 204.0, "volume": 2000, "timestamp": 1770000010000},
            ]
        )

        processed = asyncio.run(provider.process_trade_payload(body))
        metrics = provider.microstructure("COMB.N0000")

        self.assertEqual(processed, 2)
        self.assertEqual(metrics["tick_count"], 2)
        self.assertGreater(metrics["vwap"], 0)
        self.assertEqual(provider.metadata["live_source"], "CSE_WEBSOCKET_DAYTRADE")

        print("\n\n=== websocket_provider_processed_metrics ===")
        print(json.dumps(metrics, indent=2, sort_keys=True))

    def test_provider_accepts_real_cse_price_only_daytrade_ticks(self):
        provider = WebSocketMarketDataProvider()
        body = json.dumps(
            [
                {"symbol": "JKH.N0000", "price": 20.4, "change": 0.4, "changePercentage": 2.0},
                {"symbol": "ACL.N0000", "price": 100.75, "change": 2.35, "changePercentage": 2.38},
            ]
        )

        processed = asyncio.run(provider.process_trade_payload(body))
        jkh_tick = provider.store.get_ticks("JKH.N0000")[0]

        self.assertEqual(processed, 2)
        self.assertEqual(jkh_tick["volume"], 1)
        self.assertTrue(jkh_tick["volume_estimated"])
        self.assertEqual(provider.microstructure("JKH.N0000")["tick_count"], 1)

    def test_provider_enriches_missing_volume_with_rest_estimator(self):
        def estimator(symbol: str):
            return {
                "symbol": symbol,
                "estimated_volume": 777,
                "method": "quantity",
                "volume_estimated": False,
            }

        provider = WebSocketMarketDataProvider(volume_estimator=estimator)
        body = json.dumps([{"symbol": "JKH.N0000", "price": 20.4, "change": 0.4, "changePercentage": 2.0}])

        processed = asyncio.run(provider.process_trade_payload(body))
        tick = provider.store.get_ticks("JKH.N0000")[0]

        self.assertEqual(processed, 1)
        self.assertEqual(tick["volume"], 777)
        self.assertEqual(tick["volume_estimation"]["method"], "quantity")
        self.assertEqual(provider.microstructure("JKH.N0000")["window_volume"], 777)

    def test_provider_processes_today_share_price_quantity_topic(self):
        provider = WebSocketMarketDataProvider()
        body = json.dumps(
            [
                {
                    "symbol": "COMB.N0000",
                    "lastTradedPrice": 203.5,
                    "quantity": 250,
                    "tradesTime": 1779686000000,
                    "open": 203.0,
                    "high": 205.0,
                    "low": 202.5,
                }
            ]
        )
        frame = f"MESSAGE\ndestination:/user/topic/today-sharePrice\n\n{body}\x00"

        processed = asyncio.run(provider.process_stomp_message("a" + json.dumps([frame])))
        tick = provider.store.get_ticks("COMB.N0000")[0]

        self.assertEqual(processed, 1)
        self.assertEqual(tick["volume"], 250)
        self.assertFalse(tick["volume_estimated"])
        self.assertEqual(tick["source_topic"], "today-sharePrice")
        self.assertEqual(provider.microstructure("COMB.N0000")["window_volume"], 250)

    def test_provider_stores_summary_and_most_active_snapshots(self):
        provider = WebSocketMarketDataProvider()
        summary_body = json.dumps({"tradeVolume": 890506247.95, "shareVolume": 45353761, "trades": 10865})
        active_body = json.dumps([{"symbol": "SAMP.N0000", "tradeVolume": 354, "shareVolume": 192469, "turnover": 27903208.5}])
        frames = [
            f"MESSAGE\ndestination:/topic/summary\n\n{summary_body}\x00",
            f"MESSAGE\ndestination:/user/topic/most-active-trades\n\n{active_body}\x00",
        ]

        processed = 0
        for frame in frames:
            processed += asyncio.run(provider.process_stomp_message("a" + json.dumps([frame])))

        self.assertEqual(processed, 0)
        self.assertEqual(provider.latest_summary["shareVolume"], 45353761)
        self.assertEqual(provider.latest_most_active_trades[0]["symbol"], "SAMP.N0000")

    def test_provider_handles_malformed_payload_without_crashing(self):
        provider = WebSocketMarketDataProvider()

        processed = asyncio.run(provider.process_trade_payload("{bad-json"))

        self.assertEqual(processed, 0)
        self.assertEqual(provider.last_error["stage"], "decode")
        self.assertEqual(provider.memory_stats()["total_ticks"], 0)

    def test_provider_decodes_sockjs_wrapped_stomp_message(self):
        provider = WebSocketMarketDataProvider()
        body = json.dumps({"symbol": "COMB.N0000", "price": 203.0, "volume": 1000, "timestamp": 1770000000000})
        stomp_message = f"MESSAGE\ndestination:/topic/daytrade\n\n{body}\x00"
        sockjs_message = "a" + json.dumps([stomp_message])

        decoded = provider.decode_sockjs_message(sockjs_message)
        processed = asyncio.run(provider.process_stomp_message(sockjs_message))

        self.assertEqual(decoded, [stomp_message])
        self.assertEqual(processed, 1)
        self.assertEqual(provider.microstructure("COMB.N0000")["tick_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
