from __future__ import annotations

import asyncio
import logging

from argus_final.core.settings import settings
from argus_final.data.cse_provider import CseRestMarketDataProvider
from argus_final.data.tick_store import build_tick_store
from argus_final.data.websocket_provider import WebSocketMarketDataProvider

logger = logging.getLogger(__name__)


async def run_ws_ingest_loop(store=None) -> None:
    """Persistent CSE WebSocket ingest writing ticks into the shared tick store."""
    tick_store = store or build_tick_store(settings)
    rest = CseRestMarketDataProvider()

    def volume_estimator(symbol: str):
        return rest.estimate_tick_volume(symbol, refresh=True)

    provider = WebSocketMarketDataProvider(store=tick_store, volume_estimator=volume_estimator)
    logger.info("Starting CSE WebSocket ingest worker (store=%s)", type(tick_store).__name__)
    await provider.run_live_feed()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_ws_ingest_loop())


if __name__ == "__main__":
    main()
