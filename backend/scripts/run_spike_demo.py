#!/usr/bin/env python3
"""Simulation harness: serve the real app with a +15% single-day shock and 6x
volume injected into the live COMB history, so the UI can be captured reacting
to an abnormal market. Used only for dissertation evidence captures."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argus_final.data.cse_provider as cse_provider
from argus_final.api.main import create_app
from argus_final.core.settings import Settings

_orig = cse_provider.CseRestMarketDataProvider.historical_ohlcv


def spiked(self, symbol):
    df = _orig(self, symbol).copy()
    df.iloc[-1, df.columns.get_loc("close")] = df["close"].iloc[-1] * 1.15
    df.iloc[-1, df.columns.get_loc("volume")] = df["volume"].iloc[-1] * 6
    print(f"[SIM] shock injected for {symbol}: close +15%, volume x6", flush=True)
    return df


cse_provider.CseRestMarketDataProvider.historical_ohlcv = spiked

app = create_app(app_settings=Settings())

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8000, log_level="warning")
