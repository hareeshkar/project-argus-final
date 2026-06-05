"""
Native final CSE REST provider tests.

These tests verify the final project has its own provider implementation and
does not need to import the old project-argus REST client in production code.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import httpx

from argus_final.data.cse_provider import CseRestMarketDataProvider, CseRestProviderError, clean_cse_chart_data


def print_payload(title: str, payload) -> None:
    print(f"\n\n=== {title} ===")
    print(json.dumps(payload, indent=2, default=str, sort_keys=True))


class CseRestProviderTests(unittest.TestCase):
    def test_clean_cse_chart_data_maps_minified_fields_and_tracks_open_proxy(self):
        raw = [
            {"p": 100.0, "q": 1000, "h": 101.0, "l": 99.0, "t": 1770000000000, "o": None, "s": 10},
            {"p": 102.0, "q": 1500, "h": 103.0, "l": 100.0, "t": 1770086400000, "o": None, "s": 20},
        ]

        frame, quality = clean_cse_chart_data(raw)

        self.assertEqual(len(frame), 2)
        self.assertTrue({"timestamp", "open", "high", "low", "close", "volume", "turnover"}.issubset(frame.columns))
        self.assertEqual(float(frame["open"].iloc[0]), 100.0)
        self.assertTrue(quality["has_null_open_prices"])
        self.assertTrue(quality["used_open_price_proxy"])
        self.assertEqual(quality["open_price_proxy_ratio"], 1.0)

        print_payload("clean_cse_chart_data_quality", quality)
        print_payload("clean_cse_chart_data_rows", frame.to_dict(orient="records"))

    def test_provider_metadata_defaults_are_live_cse_rest(self):
        provider = CseRestMarketDataProvider()

        self.assertEqual(provider.metadata["historical_source"], "CSE_REST")
        self.assertEqual(provider.metadata["order_book_source"], "CSE_REST_ORDERBOOK")
        self.assertEqual(provider.metadata["live_source"], "NOT_CONFIGURED")

        print_payload("cse_provider_metadata_defaults", provider.metadata)

    def test_provider_raises_structured_error_after_retries(self):
        provider = CseRestMarketDataProvider(max_retries=2, retry_sleep_seconds=0)

        def failing_post(*args, **kwargs):
            raise httpx.ConnectError("network down")

        with patch.object(httpx.Client, "post", side_effect=failing_post):
            with self.assertRaises(CseRestProviderError) as ctx:
                provider.sync_symbols()

        self.assertEqual(ctx.exception.endpoint, "tradeSummary")
        self.assertEqual(provider.last_error["endpoint"], "tradeSummary")
        self.assertEqual(provider.last_error["attempts"], 2)
        self.assertIn("network down", provider.last_error["message"])

        print_payload("cse_provider_structured_error", provider.last_error)

    def test_trade_summary_helpers_extract_quantity_rich_fields(self):
        provider = CseRestMarketDataProvider(max_retries=1, retry_sleep_seconds=0)
        provider._trade_summary_cache = [
            {
                "symbol": "COMB.N0000",
                "quantity": 500,
                "sharevolume": 25000,
                "tradevolume": 50,
                "turnover": 5_000_000.0,
                "lastTradedTime": 1779685000000,
            }
        ]

        row = provider.trade_summary("COMB.N0000")
        volume_estimate = provider.estimate_tick_volume("COMB.N0000")

        self.assertEqual(row["symbol"], "COMB.N0000")
        self.assertEqual(volume_estimate["estimated_volume"], 500)
        self.assertEqual(volume_estimate["method"], "quantity")
        self.assertEqual(volume_estimate["sharevolume"], 25000)
        self.assertEqual(volume_estimate["tradevolume"], 50)

        print_payload("trade_summary_volume_enrichment", volume_estimate)

    def test_context_endpoint_helpers_return_normalized_payloads(self):
        provider = CseRestMarketDataProvider(max_retries=1, retry_sleep_seconds=0)

        def fake_post(endpoint, data=None):
            samples = {
                "marketStatus": {"status": "Regular Trading"},
                "marketSummery": {"tradeVolume": 1000, "shareVolume": 5000, "trades": 25},
                "allSectors": [{"symbol": "BNK", "sectorVolumeToday": 100, "sectorTurnoverToday": 1000.0}],
                "approvedAnnouncement": {"approvedAnnouncements": [{"announcementId": 1, "company": "TEST PLC"}]},
                "news/web?top=true&type=CN&numberOfRecord=3": {"CN": [{"title": "Market News"}]},
            }
            return samples[endpoint]

        provider._post = fake_post

        self.assertEqual(provider.market_status()["status"], "Regular Trading")
        self.assertEqual(provider.market_summary()["shareVolume"], 5000)
        self.assertEqual(provider.all_sectors()[0]["symbol"], "BNK")
        self.assertEqual(provider.approved_announcements()[0]["company"], "TEST PLC")
        self.assertEqual(provider.news_top()[0]["title"], "Market News")

        print_payload(
            "context_endpoint_helpers",
            {
                "market_status": provider.market_status(),
                "market_summary": provider.market_summary(),
                "all_sectors": provider.all_sectors(),
                "approved_announcements": provider.approved_announcements(),
                "news_top": provider.news_top(),
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
