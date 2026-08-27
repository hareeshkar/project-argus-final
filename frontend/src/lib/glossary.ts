/** Plain-language hover explanations for analytics terms. */

export const GLOSSARY = {
  dailyVolatility:
    'How much the share price typically moves in one day. Higher means more ups and downs.',
  varEwma95:
    'Estimated worst single-day loss on a normal-ish day — about 1 day in 20 could be worse than this.',
  histVar95:
    'Worst day seen in recent history (95% of days were better). Uses actual past moves, not a formula.',
  histVar99:
    'Very bad day from history — only about 1 day in 100 was worse.',
  parkinsonVol:
    'Volatility estimated from each day’s high–low range, not just the closing price.',
  volPercentile:
    'Today’s volatility compared with this stock’s own past — high means unusually jumpy lately.',
  currentDrawdown:
    'How far the price has fallen from its recent peak, shown as a percentage.',
  maxDrawdown:
    'Largest peak-to-trough drop in the data window we have.',
  vwap:
    'Volume-weighted average price — the average price paid today, weighted by how many shares traded.',
  priceMomentum:
    'How much the price moved over the recent live window. Positive = ticking up, negative = ticking down.',
  tradeIntensity:
    'How many trades happened in the last minute. Higher = busier tape.',
  windowVolume:
    'Total shares traded in the live capture window.',
  tickCount:
    'Number of individual trade updates captured for this symbol.',
  liveTrading:
    'Last traded price from the exchange trade summary, refreshed every second during market hours.',
  liveSnapshot:
    'A short burst of live trades captured from the Colombo Stock Exchange WebSocket.',
  confidenceScore:
    'How much we trust this analysis given data quality, model fit, and market conditions.',
  ensembleSignal:
    'Combined lean from trend, volatility, liquidity, and anomaly checks — not a buy/sell call.',
  arimaForecast:
    'Statistical guess of where the price might go next few days, based on past daily closes.',
  modifiedZscore:
    'Robust outlier check — flags unusual price or volume vs recent history.',
  orderFlowPressure:
    'Bid vs ask imbalance from the order book snapshot. Positive = more buyers than sellers queued; negative = more sellers. One snapshot, not a time series.',
  priceDivergence:
    'How far today’s live price is from the last daily close. A large gap can mean the close is stale or the stock moved sharply.',
  vwapDeviation:
    'How far the live price is from today’s volume-weighted average price. Above VWAP = buyers paying up; below = sellers hitting bids.',
  intradayStale:
    'The live snapshot has not updated recently, so intraday context is treated as low-weight and unreliable.',
  intradayContext:
    'A separate layer that uses order-book pressure and live ticks to nudge the ensemble and flag data quality — without entering the daily ARIMA/VaR models.',
  intradayNudge:
    'The small amount the intraday context adds to (or subtracts from) the daily ensemble score. Capped at ±0.20 and damped to zero when stale.',
  intradayUnavailable:
    'No live intraday window was available for this symbol, so the analysis is daily-only. The ensemble and confidence reflect the daily statistical models alone.',
} as const
