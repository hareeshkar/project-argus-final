# Project Argus — Frontend

React 19 + Vite + TypeScript financial intelligence terminal for the Colombo Stock Exchange (CSE). Connects to the FastAPI backend at `project-argus-final/backend/`.

---

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Start the backend first (from project-argus-final/backend/)
PYTHONPATH=. \
OPENROUTER_API_KEY="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" \
../../project-argus/venv/bin/uvicorn argus_final.api.main:app --reload --port 8000

# 3. Start the frontend dev server
npm run dev
# → http://localhost:5173
```

---

## Environment Variables

Create a `.env.local` in this directory to override defaults:

```env
# Backend API base URL (default: http://127.0.0.1:8000)
VITE_ARGUS_API_BASE_URL=http://localhost:8000
```

The backend reads these env vars at startup:

```env
# OpenRouter LLM narrative (optional — falls back to deterministic template)
OPENROUTER_API_KEY=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
OPENROUTER_MODEL=openrouter/free   # auto-routes to best available free model

# CORS (add your frontend origin if running on a different port)
ARGUS_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Force demo mode on all requests (default: false — uses live CSE REST)
ARGUS_DEMO_MODE=false
```

---

## Commands

```bash
npm run dev       # Vite dev server with HMR
npm run build     # tsc -b && vite build (type-checks + bundles)
npm run preview   # Preview the production build locally
npm test          # vitest run (unit tests)
npm run lint      # ESLint
```

---

## Architecture

### Layer overview

```
src/
├── api/
│   ├── client.ts          # fetch wrapper, ApiError, apiBaseUrl()
│   ├── argus.ts           # typed API calls: analyze(), getLiveSnapshot(), streamAnalysis()
│   └── schemas.ts         # Zod schemas for all backend responses
├── hooks/
│   ├── useAnalyzeStream.ts  # SSE streaming hook (primary analysis path)
│   ├── useAnalyze.ts        # TanStack Mutation fallback (POST /api/analyze)
│   ├── useHealth.ts         # polled /health every 30s
│   ├── useLiveSnapshot.ts   # polled /api/live-snapshot every 10–15s
│   └── useMarketPrices.ts   # polled /api/market-prices every 30s (watchlist prices)
├── components/
│   ├── panels.tsx           # All 13 numbered dashboard panels + TopBar/drawers
│   ├── primitives.tsx       # Panel, Kpi, ScoreMeter, ContribBars, ConfidenceGauge, Badge, Sparkline
│   └── charts.tsx           # ForecastChart (SVG, no Recharts), RiskBars, useSyntheticHistory
├── lib/
│   └── format.ts            # fmt.price / fmt.pct / fmt.score / fmt.ago helpers
└── App.tsx                  # 3-column shell, watchlist, market status, drawer routing
```

### Data flow

1. User types a query → `runAnalysis()` in App.tsx
2. `useAnalyzeStream.run()` opens an `EventSource` to `GET /api/analyze/stream?query=...`
3. Backend emits SSE `pipeline` events for each stage (parse → fetch → models → confidence → narrative)
4. `LoadingPipeline` renders the live stage progress in the center column
5. Backend emits a final SSE `final` event with the complete analysis payload
6. All 13 panels render from the `ArgusAnalysis` object

### SSE streaming endpoint

`GET /api/analyze/stream?query=Analyze+COMB&demo_mode=false&pace=academic`

Emits these event types:
- `pipeline` — `{ stage_id, title, status, message, elapsed_seconds?, detail? }`
- `final` — full `ArgusAnalysis` JSON object
- `analysis_error` — `{ message, stage_id, status }`

### Market prices (watchlist)

`GET /api/market-prices` returns `{ prices: { "COMB.N0000": { price, change, pct_change }, ... }, count }` sourced from the CSE `tradeSummary` REST endpoint. Refreshed every 30s. Feeds all 10 watchlist rows with live price, ↑/↓ arrow, and % change.

### Market status

Derived client-side from current Sri Lanka Time (UTC+5:30). CSE trading hours: Mon–Fri 09:30–14:30 SLT. No backend dependency. Re-evaluated every 60 seconds.

---

## Panels reference

| # | Panel | Key backend fields |
|---|---|---|
| 01 | Analysis Overview | `confidence`, `indicator_vote`, `microstructure.latest_price` |
| 02 | Ensemble Signal | `indicator_vote.score/signal/components` |
| 03 | Confidence & Data Quality | `confidence.score/label/penalties` |
| 04 | Forecast & ARIMA Diagnostics | `math_results.arima.*` |
| 05 | Risk Metrics | `math_results.volatility.*`, `math_results.drawdown.*` |
| 06 | Trend / OLS Regression | `math_results.trend.*` |
| 07 | Anomaly Detection | `math_results.anomaly.*` |
| 08 | Market Regime | `math_results.regime.*` |
| 09 | Order Book Pressure | `order_book.bids/asks/pressure` |
| 10 | Live Microstructure | `microstructure.*` + `useLiveSnapshot` |
| 11 | Analyst Summary | `llm_explanation.*` (OpenRouter/free or deterministic template) |
| 12 | Data Lineage | `data_lineage.*` |
| 13 | Quality Flags | `quality_flags.*`, `node_status.*` |

---

## LLM Narrative

When `OPENROUTER_API_KEY` is set, panel 11 uses the OpenRouter `openrouter/free` meta-router (auto-selects the best available free model from 22+ options). Falls back to a deterministic template narrator if the key is absent or the LLM call fails. The status bar shows `narrative: openrouter/free` or `narrative: deterministic_template`.
