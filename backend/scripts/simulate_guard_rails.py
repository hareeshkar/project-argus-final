#!/usr/bin/env python3
"""Simulate abnormal market conditions to demonstrate the multi-model guard rails.

Scenario 1: a gradual three-day ramp (+8 percent per day, 4x volume).
Scenario 2: a single-day shock (+15 percent, 6x volume).
Run from backend/:  python3 scripts/simulate_guard_rails.py
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from argus_final.analytics.engine import AnalyticsConfig, AnalyticsEngine
from argus_final.data.cse_provider import CseRestMarketDataProvider


def main():
    provider = CseRestMarketDataProvider()
    df = provider.historical_ohlcv("COMB.N0000")
    engine = AnalyticsEngine(AnalyticsConfig())
    base = engine.run(df)

    ramp = copy.deepcopy(df)
    for i in range(1, 4):
        ramp.iloc[-i, ramp.columns.get_loc("close")] = ramp["close"].iloc[-i] * 1.08
        ramp.iloc[-i, ramp.columns.get_loc("volume")] = ramp["volume"].iloc[-i] * 4
    s1 = engine.run(ramp)

    shock = copy.deepcopy(df)
    shock.iloc[-1, shock.columns.get_loc("close")] = shock["close"].iloc[-1] * 1.15
    shock.iloc[-1, shock.columns.get_loc("volume")] = shock["volume"].iloc[-1] * 6
    s2 = engine.run(shock)

    def line(label, b, s, fmt="{:.2f}"):
        print(f"  {label:30s} baseline={fmt.format(b)}   scenario={fmt.format(s)}")

    for name, sim, note in [
        ("SCENARIO 1: gradual 3-day ramp (+8%/day, 4x volume)", s1,
         "volatility and regime guard rails react; point anomalies stay quiet by design"),
        ("SCENARIO 2: single-day shock (+15%, 6x volume)", s2,
         "anomaly guard rails fire and the ensemble dampens to neutral"),
    ]:
        a, v, c, r, vote = sim["anomaly"], sim["volatility"], sim["confidence"], sim["regime"], sim["indicator_vote"]
        ba, bv, bc, bvot = base["anomaly"], base["volatility"], base["confidence"], base["indicator_vote"]
        print("=" * 66)
        print(name)
        print(f"  ({note})")
        line("return z-score", ba["return_zscore"], a["return_zscore"])
        line("modified (MAD) price z", ba["modified_price_zscore"], a["modified_price_zscore"])
        line("modified (MAD) volume z", ba["modified_volume_zscore"], a["modified_volume_zscore"])
        print(f"  {'anomaly flag':30s} baseline={ba['is_anomalous']}   scenario={a['is_anomalous']}")
        line("daily volatility %", bv["daily_volatility_pct"], v["daily_volatility_pct"])
        line("VaR 95 %", bv["var_95_pct"], v["var_95_pct"])
        line("volatility percentile", bv["volatility_percentile"], v["volatility_percentile"], "{:.1f}")
        print(f"  {'volatility regime':30s} baseline={bvot and base['regime']['volatility_regime']}   scenario={r['volatility_regime']}")
        print(f"  {'liquidity regime':30s} baseline={base['regime']['liquidity_regime']}   scenario={r['liquidity_regime']}")
        print(f"  {'ensemble signal':30s} baseline={bvot['signal']}   scenario={vote['signal']}")
        line("ensemble score", bvot["score"], vote["score"], "{:.3f}")
        print(f"  {'confidence':30s} baseline={bc['label']} {bc['score']:.2f}   scenario={c['label']} {c['score']:.2f}")
    print("=" * 66)


if __name__ == "__main__":
    main()
