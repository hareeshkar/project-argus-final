# Project Argus Final

A confidence-aware stock market analytics system for the Colombo Stock Exchange (CSE): a FastAPI analytics backend and a React/Vite analyst workstation that turn public exchange data into plain-language, trust-scored research evidence.

> Research analytics only. The system does not produce investment advice.

## Structure

```text
project-argus-final/
  backend/    # FastAPI, analytics engine (ARIMA, EWMA, VaR), CSE providers, narrative + chat, tests
  frontend/   # React + Vite + TypeScript analyst workstation
  docker-compose.yml  # optional Redis / Celery / WebSocket-ingest stack
```

## Quick Start (examiner / agent path)

```bash
# 1. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. .venv/bin/uvicorn argus_final.api.main:app --host 127.0.0.1 --port 8000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Open `http://localhost:5173`, type **Analyze COMB.N0000**, press Run. The dashboard streams a five-stage pipeline (parse, fetch, models, confidence, narrative) and renders the full evidence panels.

**No environment setup is required**: `backend/.env.local` ships preconfigured (demo mode on, local Ollama narration). The backend starts in demo mode and works fully offline; live CSE REST data is used automatically when `demo_mode` is off and the exchange is reachable.

## Backend Setup

Requirements: Python 3.11+.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp -n .env.example .env.local   # only if .env.local does not exist; this submission ships one preconfigured - do NOT overwrite it
```

Run the API:

```bash
PYTHONPATH=. .venv/bin/uvicorn argus_final.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify:

```bash
curl http://127.0.0.1:8000/health
# {"status": "ok", "version": "2.0.0", "components": {"api": "ok", ...}}
```

Key configuration (all optional - defaults work out of the box):

| Variable | Default | Purpose |
|---|---|---|
| `ARGUS_DEMO_MODE` | `true` | Deterministic in-memory data; `false` = live CSE REST |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama for narration (Gemma 4) |
| `OLLAMA_MODEL` | `gemma4` | Narration model |
| `ARGUS_CORS_ORIGINS` | localhost origins | Allowed browser origins |

Narration runs local-first through Ollama; if the local model is unreachable, deterministic template narrators keep every explanation layer functional. Provider overrides are env-configurable (see `backend/.env.example`).

## Frontend Setup

Requirements: Node 18+.

```bash
cd frontend
npm install
npm run dev        # dev server on http://localhost:5173
npm run build      # production build
```

The frontend reads `VITE_ARGUS_API_BASE_URL` (default `http://localhost:8000`); override via `frontend/.env`.

## Optional Infrastructure (docker-compose)

Redis tick store, Celery LLM offload, and persistent WebSocket ingest are available but **off by default** (local dev stays simple):

```bash
docker compose up -d redis            # shared tick store + Celery broker
docker compose up -d celery-worker    # narrative offload
docker compose up -d ws-ingest        # persistent CSE WebSocket -> Redis
# then set in backend env: ARGUS_REDIS_TICKS_ENABLED=true ARGUS_LLM_QUEUE_ENABLED=true ARGUS_WS_INGEST_ENABLED=true
```

## Demo Mode vs Live CSE REST

The frontend toggle (or the `demo_mode` request field) selects the data path:

```json
{ "query": "Analyze COMB", "demo_mode": true }
```

- **Demo (`true`)**: deterministic in-memory dataset - no internet, no market hours, fully reproducible.
- **Live (`false`)**: real CSE REST data (~240 daily candles, order-book totals, trade summary). Response lineage reports its sources, e.g. `historical_source: CSE_REST`, `live_source: CSE_REST_TRADE_SUMMARY` (or `CSE_WEBSOCKET_DAYTRADE` when the tick store has live ticks).

The intraday/live layer never enters ARIMA or VaR maths; it only adds a bounded, capped nudge to the ensemble and feeds quality flags.

## Tests

### Backend (Python unittest, 68 tests)

```bash
cd backend
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -v
```

Covers: offline demo determinism, live CSE REST ingestion, WebSocket diagnostics, API surface (`/health`, `/api/analyze`), confidence penalties, quality flags, scenario guard rails, narrative/chat services, and fallback behaviour.

Compile check:

```bash
PYTHONPATH=. .venv/bin/python -m compileall -q argus_final tests
```

### Frontend (Vitest)

```bash
cd frontend
npm test
```

## AAA Agent (Automated Assessment) Guide

For an evaluating agent operating the repository non-interactively:

1. **Environment**: Python 3.11+, Node 18+. No API keys or external services are required for the default path.
2. **Backend up**:
   ```bash
   cd backend && python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   PYTHONPATH=. .venv/bin/uvicorn argus_final.api.main:app --host 127.0.0.1 --port 8000 &
   ```
3. **Health gate**: `GET http://127.0.0.1:8000/health` must return `"status": "ok"` with `components.api == "ok"`.
4. **Functional probe** (deterministic, offline):
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/analyze -H 'Content-Type: application/json' \
        -d '{"query": "Analyze COMB.N0000", "demo_mode": true}'
   ```
   Expect a payload containing `confidence`, `ensemble`, `forecast`, `risk`, `data_lineage` (with `data_source_mode: offline_demo`) and `quality_flags`.
5. **Backend suite**: `PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -v` - expect all tests passing.
6. **Frontend suite**: `cd frontend && npm ci || npm install`, then `npm test` - expect all tests passing; `npm run dev` serves the workstation on port 5173 (proxies to the API base URL above).
7. **Evidence map**: manual test cases TC-01..TC-25 map to the automated suites as documented in Chapter 7 of the dissertation; the API contract mirrors the panels (confidence vector, ensemble vote, forecast diagnostics, risk block, lineage, quality flags).

## API Surface

- `GET /health` - component status (api, data provider, analytics engine, narrative)
- `POST /api/analyze` - streamed (SSE) five-stage analysis: parse -> fetch -> models -> confidence -> narrative
- `GET /api/market-prices` - watchlist tape (10 CSE symbols)
- `GET /api/live-price?symbol=...` - last trade snapshot (1 s poll open / 30 s closed)
- `POST /api/chat` - RAG-grounded question answering over the loaded analysis (advice refusal enforced)

## Framing

This is a research analytics system, not a trading system. It exposes trend, volatility, anomaly, liquidity and confidence diagnostics under the public CSE data constraints (~240 daily rows per symbol), and it treats honest communication of uncertainty - documented penalties, quality flags, naive-baseline validation - as a first-class requirement.

## Troubleshooting & Diagnostics

| Symptom | Check | Expected |
|---|---|---|
| Backend won't start | `curl http://127.0.0.1:8000/health` | `{"status": "ok", ...}` within a few seconds |
| Port already in use | `lsof -i :8000` / `lsof -i :5173` | kill the stale process or use `--port 8001` (+ set `VITE_ARGUS_API_BASE_URL`) |
| First narrative takes ~15-17 s | normal | local model handshake, then timeout with template/provider fallback - subsequent runs are faster |
| Dashboard shows `CLOSED` badge | CSE trades 09:30-14:30 Sri Lanka time (Mon-Fri) | outside those hours prices freeze at the last session close; demo mode always works |
| Live mode returns dashes | market closed or CSE temporarily empty | switch on the demo toggle for a deterministic offline run |
| npm test fails to start | Node 18+ required | `node --version`, then `npm install` again |
