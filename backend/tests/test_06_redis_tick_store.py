import unittest

import fakeredis

from argus_final.data.tick_store import RedisTickStore


class RedisTickStoreTests(unittest.TestCase):
    def test_ltrim_keeps_max_ticks(self):
        client = fakeredis.FakeRedis(decode_responses=True)
        store = RedisTickStore(client, max_ticks_per_symbol=100, ttl_seconds=3600)
        symbol = "COMB.N0000"
        for index in range(101):
            store.update_tick(symbol, {"price": 200 + index * 0.01, "volume": 100, "timestamp": index})
        ticks = store.get_ticks(symbol)
        self.assertEqual(len(ticks), 100)
        self.assertAlmostEqual(ticks[-1]["price"], 200 + 100 * 0.01, places=4)

    def test_metrics_and_symbols(self):
        client = fakeredis.FakeRedis(decode_responses=True)
        store = RedisTickStore(client, max_ticks_per_symbol=10, ttl_seconds=3600)
        store.update_tick("WIND.N0000", {"price": 44.0, "volume": 50, "timestamp": 1})
        store.update_tick("WIND.N0000", {"price": 44.5, "volume": 75, "timestamp": 2})
        metrics = store.calculate_metrics("WIND.N0000")
        self.assertEqual(metrics["tick_count"], 2)
        self.assertEqual(metrics["latest_price"], 44.5)
        self.assertIn("WIND.N0000", store.get_all_symbols())


if __name__ == "__main__":
    unittest.main()
