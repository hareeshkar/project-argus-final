# Project Argus — Demo Guide (COMB vs WIND)

Research analytics dashboard for the **Colombo Stock Exchange (CSE)**. Not investment advice.

---

## 1. What this system is

Argus ingests **public CSE data**, runs **statistical models** (ARIMA, EWMA VaR, drawdown, anomaly, regime), combines them into an **ensemble signal**, and explains results in **plain English**. It explicitly flags when forecasts or data are weak.

**Demo story:** Compare a **liquid, model-friendly** stock (**COMB — Commercial Bank**) with a **thin, hard-to-model** stock (**WIND — Windforce**).

---

## 2. CSE API limits (know these for Q&A)

| Source | Endpoint | What you get | Limit / note |
|--------|----------|--------------|--------------|
| **Historical OHLCV** | `companyChartDataByStock` (period=5) | ~**240 daily** open/high/low/close/volume | Powers ARIMA, VaR, trend, chart gray line |
| **Live prices** | `tradeSummary` | Last price, change, day volume, high/low | Polled every **1s** (market open) or **30s** (closed) via `/api/live-price` |
| **Watchlist** | `tradeSummary` (all symbols) | Price + % change | Refreshed every **5s** |
| **Order book** | `orderBook` | Total bids vs asks → pressure | Snapshot at analysis time; **not** a full depth book |
| **WebSocket** | `/topic/daytrade` | Sparse trade ticks | Used in tests/snapshot only; **not** the main UI live path |

**Market hours:** Mon–Fri **09:30–14:30** Sri Lanka Time (UTC+5:30).

**When market is closed:** Live Price shows **last available tradeSummary** prices. Forecast still uses **last daily close** from the 240-row history.

**Demo checkbox:** Forces **in-memory synthetic data** — leave **unchecked** for a real CSE demo.

---

## 3. Pre-demo checklist

```bash
# Backend (from project-argus-final/backend/)
PYTHONPATH=. ../../project-argus/venv/bin/uvicorn argus_final.api.main:app --reload --port 8000

# Frontend (from project-argus-final/frontend/)
npm run dev
# Open http://localhost:5173
```

- [ ] **DEMO** checkbox is **off**
- [ ] Top bar: **API OK**, **DATA MODE: LIVE CSE REST**
- [ ] Run **`Analyze COMB`** first, then **`Analyze WIND`**

---

## 4. End-to-end flow (query → pipeline → panels)

### Step A — Query bar

Type or click watchlist:

- `Analyze COMB` → resolves to **COMB.N0000**
- `Analyze WIND` → **WIND.N0000**

Click **RUN ↵**. The pipeline streams live:

| Stage | What happens |
|-------|----------------|
| **[01] Parse** | Extracts symbol from natural language |
| **[02] Fetch** | ~240 daily candles + order book + tradeSummary snapshot |
| **[03] Models** | ARIMA, volatility, VaR, trend, anomaly, regime |
| **[04] Confidence** | Trust score + ensemble signal (BULLISH/BEARISH/NEUTRAL) |
| **[05] Narrative** | DeepSeek plain-English summary (~5–8s) |

### Step B — Watchlist (left column)

Ten sample CSE symbols with **live prices** from `tradeSummary` (5s refresh).

- Click a row to re-run analysis for that symbol.
- **TOK** may show `—` if absent from tradeSummary (illiquid / no row).

### Step C — Ticker tape (top)

Scrolling strip of watchlist prices and % changes — same REST source as the watchlist.

---

## 5. Panel-by-panel reference

### 01 — Analysis Overview

**What:** Snapshot hero — confidence, signal, price at analysis time, pipeline duration.

**Say:** *“Confidence is trust in the **analysis pipeline**, not probability of profit.”*

| Field | COMB (typical) | WIND (typical) |
|-------|----------------|----------------|
| Confidence | HIGH (~0.9) | HIGH (~0.75) |
| Signal | BEARISH | NEUTRAL |
| Latest price | Last tradeSummary / daily close at fetch | Same |

---

### 02 — Ensemble Signal

**What:** Weighted vote from four components (−1 bearish … +1 bullish):

- **trend** — OLS / price direction  
- **volatility** — risk level contribution  
- **liquidity** — thin vs normal volume  
- **anomaly** — outlier flags  

**Say:** *“Not buy/sell — a composite lean from multiple checks.”*

---

### 03 — Confidence & Data Quality (right column)

**What:** Gauge + penalty bars (missing data, thin liquidity, ARIMA diagnostics, etc.).

**Say:** *“Penalties explain **why** trust is high or reduced.”*

---

### 04 — Forecast & ARIMA Diagnostics ⭐

**What:** 3-day ahead forecast from **ARIMA** on **real daily closes**.

**Chart (now fully real):**

- **Gray line** = last **30 actual daily closes** from CSE (`price_history` in API)
- **Yellow dashed line** = 3-step forecast (t+1, t+2, t+3)
- **Yellow shaded band** = **95% confidence interval**
- **t** = last observed daily close; **t+1…t+3** = next 3 trading days

**KPI boxes:**

| Label | Meaning |
|-------|---------|
| **t+1, t+2, t+3** | Predicted close each day ahead |
| **[lower, upper]** | 95% CI — wider = more uncertainty |
| **BEATS NAIVE / FAILS NAIVE** | Did ARIMA beat “tomorrow = today”? |
| **FC HIGH/MOD/LOW** | Forecast quality label |

**Naive** = ARIMA(0,1,0) random walk: *tomorrow’s price ≈ today’s*.

| | COMB | WIND |
|---|------|------|
| Model | ARIMA(1,1,0) | ARIMA(0,1,0) |
| Beats naive | **Yes** | **No** |
| FC confidence | MODERATE | LOW |
| Forecast | Declining (~201.6 → 201.5) | **Flat** (44.8, 44.8, 44.8) |
| Chart | Gray = real history; yellow moves | Flat yellow = no model edge |

**Say for WIND:** *“Flat forecast + FAILS NAIVE means the system admits it has no predictive edge — that’s honest analytics.”*

---

### 05 — Risk Metrics

**What:** Daily volatility (EWMA), Historical VaR 95/99%, Parkinson vol, drawdown.

**Say:** *“How bumpy the stock is and how bad a typical bad day might look — from past returns, not guesses.”*

---

### 06 — Trend (OLS Regression)

**What:** Linear trend on log prices — slope, R², UP/DOWN/FLAT label.

---

### 07 — Anomaly Detection

**What:** Modified Z-score on recent returns/volume — flags unusual days.

---

### 08 — Market Regime

**What:** Labels like volatility regime (NORMAL/HIGH) and **liquidity (THIN/NORMAL)**.

**WIND** often shows **THIN** liquidity — ties to weaker forecasts.

---

### 09 — Order Book Pressure

**What:** CSE `orderBook` totals — bid vs ask imbalance (single snapshot).

**Say:** *“Order-flow pressure proxy, not a full Level-2 book.”*

---

### 10 — Live Price (right column)

**What:** `/api/live-price` polls **tradeSummary** every **1s** (open) / **30s** (closed).

Shows: latest price, change today, day volume, last trade time, day high/low, sparkline.

**Say when closed:** *“Last exchange-reported price — market is closed, so it won’t tick every second.”*

---

### 11 — Plain-English Summary

**What:** DeepSeek narrative — headline, what data says, things to watch, how much to trust.

**Say:** *“LLM explains computed metrics; it cannot invent prices. Falls back to template if API fails.”*

---

### 12 — Data Lineage

**What:** Audit trail — `CSE_REST`, row counts (~240), LLM provider, timestamps.

Use this if examiner asks *“where did the data come from?”*

---

### 13 — Quality Flags

**What:** Warnings list — null opens, thin liquidity, **model_warning** when ARIMA fails naive.

---

## 6. Scripted demo (5 minutes)

### Part 1 — COMB (Commercial Bank) ~2.5 min

1. Type **`Analyze COMB`**, click **RUN**.
2. Point at pipeline: *240 rows, CSE_REST, ~8s total*.
3. **Overview:** HIGH confidence, BEARISH lean — explain ensemble ≠ buy/sell.
4. **Forecast:** Gray = **real** 30-day closes. Yellow line **slopes down**. **BEATS NAIVE**, FC MODERATE.
5. **Risk / Trend / Regime:** Briefly — moderate vol, downward trend component.
6. **Live Price:** Last traded price from exchange (may match or differ slightly from last daily close).
7. **Plain-English Summary:** Read headline aloud.

### Part 2 — WIND (Windforce) ~2.5 min

1. Click **WIND** in watchlist.
2. **Overview:** NEUTRAL signal, still HIGH confidence in *data* quality.
3. **Forecast:** **FAILS NAIVE**, **FC LOW**, flat 44.8 × 3. Yellow line horizontal.
4. **Regime:** THIN liquidity. **Quality flags:** ARIMA warning.
5. **Contrast:** *“Same pipeline, different honesty — COMB has modest forecast edge; WIND does not.”*

### Closing line

> “Argus is a **research dashboard** that combines CSE data, statistical models, and explicit quality flags. It tells you when to trust the output and when to treat forecasts as flat/no-edge — especially on thin names like WIND.”

---

## 7. Test results (last run)

```bash
# Backend — 33 tests
PYTHONPATH=. ../../project-argus/venv/bin/python -m unittest discover -s tests -v

# Frontend — 8 tests + build
npm test && npm run build
```

- Backend: API integration, offline demo, live REST (when network up), WebSocket unit tests  
- Frontend: Zod schema validation (includes new `price_history`), component tests  
- Live REST tests require CSE network access; WebSocket real capture skips off-hours  

---

## 8. Examiner FAQ

**Q: Is the forecast chart fake?**  
A: **No.** Gray history is the last 30 **real daily closes** from CSE. Yellow is ARIMA output on the full ~240-day series.

**Q: Why does forecast price differ from Live Price?**  
A: Forecast uses **last daily close** from the chart series. Live Price uses **tradeSummary** (can differ intraday or after hours).

**Q: What is naive?**  
A: Random walk — tomorrow equals today. **Beats naive** means our ARIMA fit history better than that baseline.

**Q: Why HIGH confidence but FAILS NAIVE on WIND?**  
A: **Confidence** = data + pipeline quality. **Forecast badges** = model predictive power. They are separate by design.

**Q: Is this a trading bot?**  
A: **No.** Research analytics only. Every panel states this.

---

## 9. Recent fixes (defense improvements)

- ✅ Forecast chart uses **real CSE daily closes** (removed synthetic gray line)
- ✅ Live Price uses **REST tradeSummary** (1s poll), not misleading WebSocket tick counts
- ✅ API returns `price_history` for auditable chart provenance
- ✅ Lineage panel documents ~240-row CSE limit accurately
