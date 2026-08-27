# Project Argus Final Backend

Project Argus Final is the cleaned backend target for a confidence-aware Colombo Stock Exchange analytics system.

This folder intentionally contains only the enterprise backend surface needed for the final system:

- `argus_final/analytics`: bounded ARIMA diagnostics, EWMA, Historical VaR, Parkinson volatility, MAD anomalies, drawdown, regime labels, confidence vector, indicator vote.
- `argus_final/data`: provider boundary, deterministic offline provider, and native CSE REST provider.
- `argus_final/services`: analysis orchestration without LangGraph dependency.
- `argus_final/llm`: deterministic narrative fallback. LLMs are optional presentation layers.
- `argus_final/api`: FastAPI app with `/health` and `/api/analyze`.
- `tests`: verbose executable tests for offline demo, live CSE REST, WebSocket diagnostics, and API behavior.

## Run

```bash
cd /Users/hareeshkar/Documents/cse/project-argus-final/backend
PYTHONPATH=. ../../project-argus/venv/bin/uvicorn argus_final.api.main:app --reload
```

## Demo Mode vs Live CSE REST

The API supports a frontend toggle through the `demo_mode` request field.

Demo mode uses deterministic in-memory data:

```json
{
  "query": "Analyze COMB",
  "demo_mode": true
}
```

Live CSE REST mode uses the native final CSE provider:

```json
{
  "query": "Analyze COMB",
  "demo_mode": false
}
```

When `demo_mode` is `false`, the response lineage should show:

```json
{
  "historical_source": "CSE_REST",
  "order_book_source": "CSE_REST_ORDERBOOK",
  "live_source": "CSE_REST_TRADE_SUMMARY",
  "intraday_context_source": "CSE_REST_TRADE_SUMMARY"
}
```

`live_source` is `CSE_REST_TRADE_SUMMARY` for REST-only analysis (microstructure proxy from `tradeSummary`). When the shared WebSocket tick store has live ticks for the symbol, `live_source` becomes `CSE_WEBSOCKET_DAYTRADE` and the intraday context layer prefers real ticks. `CseRestMarketDataProvider` is intentionally REST-only; `WebSocketMarketDataProvider` owns `/topic/daytrade` ticks.

## Live Volume Enrichment

Runtime browser and WebSocket inspection showed that CSE `/topic/daytrade` frequently emits price/change ticks without true quantity:

```json
{
  "symbol": "JKH.N0000",
  "price": 20.4,
  "change": 0.4,
  "changePercentage": 2.0
}
```

The official site combines that WebSocket feed with REST endpoints that do include quantity-rich fields:

- `/api/tradeSummary`: `quantity`, `sharevolume`, `tradevolume`, `turnover`, `lastTradedTime`
- `/api/mostActiveTrades`: `tradeVolume`, `shareVolume`, `turnover`
- `/api/mostActiveVolumes`: `tradeVolume`, `shareVolume`, `turnover`
- `/api/marketSummery`: market-level `tradeVolume`, `shareVolume`, `trades`
- `/api/allSectors`: sector-level `sectorVolumeToday`, `sectorTurnoverToday`, `percentage`
- `/api/approvedAnnouncement`, `/api/news/web`: context for analyst/chat explanations

`CseRestMarketDataProvider` exposes:

- `trade_summary(symbol)`
- `most_active_trades()`
- `most_active_volumes()`
- `estimate_tick_volume(symbol)`
- `market_status()`
- `market_summary()`
- `all_sectors()`
- `approved_announcements()`
- `news_top()`

`WebSocketMarketDataProvider` accepts an optional `volume_estimator` callback. If a live WebSocket tick has no volume, it can enrich the tick from REST `tradeSummary`. If no enrichment is configured, the tick is still accepted with `volume=1` and `volume_estimated=true` so tick-count and price-momentum metrics remain usable but honest.

`WebSocketMarketDataProvider` also processes these confirmed live topics:

- `/topic/daytrade`, `/user/topic/daytrade`
- `/topic/today-sharePrice`, `/user/topic/today-sharePrice`
- `/topic/summary`, `/user/topic/summary`
- `/topic/most-active-trades`, `/user/topic/most-active-trades`

## Intraday Context Layer

Order book pressure and live microstructure live on a different time scale than the daily OHLCV history, so they are **not** fed into ARIMA/VaR. Instead `argus_final/analytics/intraday_context.py` builds a separate context block from the resolved microstructure + order book snapshot:

- descriptive metrics: price divergence vs last daily close, VWAP deviation, trade intensity, order-flow pressure,
- a small, **staleness-damped** ensemble nudge (`order_flow_score` + `intraday_score`, capped at ±0.20) added on top of the daily `indicator_vote` score,
- confidence penalties for material price divergence / stale snapshots,
- quality flags (`is_stale`, `order_book_snapshot`, `intraday_context_available`).

`math_results.indicator_vote` stays the pure daily ensemble; the top-level `indicator_vote` / `ensemble` is the combined daily + intraday view. When the shared tick store has live ticks for a symbol, `AnalysisService` prefers them over the REST `tradeSummary` microstructure proxy and lineage reports `live_source: CSE_WEBSOCKET_DAYTRADE`; otherwise it falls back to REST and labels it honestly.

## Test Commands

All commands assume the reusable virtual environment from the original `project-argus` folder:

```bash
cd /Users/hareeshkar/Documents/cse/project-argus-final/backend
```

### 1. Offline Demo Test

Use this when you want a deterministic run that does not need internet, CSE availability, WebSocket market hours, or LLM keys.

```bash
PYTHONPATH=. ../../project-argus/venv/bin/python -m unittest tests.test_01_offline_demo -v
```

This prints:

- deterministic OHLCV analysis for `COMB.N0000`
- ARIMA/AICc forecast diagnostics
- volatility, Historical VaR, Parkinson volatility
- MAD anomaly output
- confidence vector
- indicator vote
- data lineage and quality flags

### 2. Live CSE REST Test

Use this to fetch real CSE REST historical OHLCV and order-book data, then run the final analytics engine on the real dataset.

```bash
PYTHONPATH=. ../../project-argus/venv/bin/python -m unittest tests.test_02_live_cse_rest -v
```

This prints:

- live CSE REST mode
- real `COMB.N0000` historical row count
- date range
- latest OHLCV candle
- live REST order-book pressure
- final analytics output from real CSE data

### 3. Live CSE WebSocket Diagnostics Test

Default safe mode does not force a live market-hour socket capture. It prints market status and verifies the microstructure path with deterministic ticks.

```bash
PYTHONPATH=. ../../project-argus/venv/bin/python -m unittest tests.test_03_live_cse_websocket -v
```

To attempt a real `/topic/daytrade` WebSocket capture during market hours:

```bash
ARGUS_RUN_REAL_WEBSOCKET=1 ARGUS_WEBSOCKET_SECONDS=20 \
PYTHONPATH=. \
../../project-argus/venv/bin/python -m unittest tests.test_03_live_cse_websocket -v
```

This prints:

- current time and CSE market-open status
- whether real WebSocket capture was attempted
- live tick count if any ticks arrive
- final LiveStore memory statistics
- per-symbol VWAP, trade intensity, momentum, volume, and tick count

### 4. API Test

Use this to verify the final FastAPI surface with deterministic data.

```bash
PYTHONPATH=. ../../project-argus/venv/bin/python -m unittest tests.test_api -v
```

This prints:

- `/api/analyze` payload summary
- top-level response keys
- math-result sections
- data lineage
- `demo_mode` frontend toggle behavior
- quality flags
- `/health` component status

### 5. Run All Tests

Use this as the full agent handoff verification command.

```bash
PYTHONPATH=. ../../project-argus/venv/bin/python -m unittest discover -s tests -v
```

### 6. Compile Check

Use this before claiming the backend is structurally valid.

```bash
../../project-argus/venv/bin/python -m compileall -q argus_final tests
```

## Environment Placeholders

If OpenRouter is wired later, replace these placeholders with real secrets:

```bash
export OPENROUTER_API_KEY="REPLACE_WITH_OPENROUTER_API_KEY"
export OPENROUTER_MODEL="openrouter/auto"
export ARGUS_CORS_ORIGINS="http://localhost:5173,http://localhost:8000"
```

Do not commit real API keys.

## Framing

This is not a trading system and does not produce investment advice. It is a research analytics backend that exposes trend, volatility, anomaly, liquidity, and confidence diagnostics under the public CSE data constraints.
