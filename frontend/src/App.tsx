import { useEffect, useMemo, useState } from 'react'

import { CopyModeProvider, useCopyMode } from './lib/copy'
import './App.css'
import {
  AnalysisOverview,
  AnomalyPanel,
  ConfidencePanel,
  ForecastPanel,
  IntradayContextPanel,
  LineagePanel,
  LLMPanel,
  LoadingPipeline,
  MethodologyDrawer,
  MicrostructurePanel,
  OrderBookPanel,
  QualityFlagsPanel,
  QueryConsole,
  RawJsonDrawer,
  RegimePanel,
  RiskPanel,
  SignalPanel,
  TopBar,
  TrendPanel,
} from './components/panels'
import { ChatDrawer } from './components/chat'
import { useAnalyzeStream } from './hooks/useAnalyzeStream'
import { useChat } from './hooks/useChat'
import { useHealth } from './hooks/useHealth'
import { useLivePrice } from './hooks/useLivePrice'
import { useMarketPrices } from './hooks/useMarketPrices'

function isCseOpen(): boolean {
  const now = new Date()
  // Sri Lanka Time = UTC+5:30
  const sl = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Colombo' }))
  const day = sl.getDay() // 0=Sun, 6=Sat
  if (day === 0 || day === 6) return false
  const mins = sl.getHours() * 60 + sl.getMinutes()
  return mins >= 570 && mins < 870 // 09:30–14:30
}

// ─── Watchlist ────────────────────────────────────────────────────────────────

const WATCHLIST = [
  { sym: 'COMB.N0000', name: 'Commercial Bank' },
  { sym: 'JKH.N0000', name: 'John Keells' },
  { sym: 'SAMP.N0000', name: 'Sampath Bank' },
  { sym: 'LOLC.N0000', name: 'LOLC Holdings' },
  { sym: 'TOK.N0000', name: 'Tokyo Cement' },
  { sym: 'HAYC.N0000', name: 'Hayleys' },
  { sym: 'VONE.N0000', name: 'Vallibel One' },
  { sym: 'BFL.N0000', name: 'Bairaha Farms' },
  { sym: 'WIND.N0000', name: 'Windforce' },
  { sym: 'RICH.N0000', name: 'Richard Pieris' },
]

function AppShell() {
  const { mode: copyMode } = useCopyMode()
  const [query, setQuery]             = useState('Analyze COMB')
  const [demoMode, setDemoMode]       = useState(false)
  const [scenarios, setScenarios]     = useState<string[]>([])
  const [drawerOpen, setDrawerOpen]   = useState(false)
  const [methodOpen, setMethodOpen]   = useState(false)
  const [chatOpen, setChatOpen]       = useState(false)
  const [pipelineQuery, setPipelineQuery] = useState(query)

  const health        = useHealth()
  const analyze       = useAnalyzeStream()
  const chat          = useChat()
  const marketPrices  = useMarketPrices(!demoMode)
  const [marketOpen, setMarketOpen] = useState(isCseOpen())
  const busy = analyze.isPending
  const data = analyze.data
  const livePrice     = useLivePrice(data?.symbol, !demoMode && Boolean(data?.symbol), marketOpen)

  // re-evaluate market status every minute
  useEffect(() => {
    const id = setInterval(() => setMarketOpen(isCseOpen()), 60_000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setDrawerOpen(false)
      setMethodOpen(false)
      setChatOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const runAnalysis = (sym?: string) => {
    const q = sym ? `Analyze ${sym.split('.')[0]}` : query
    if (sym) setQuery(q)
    setPipelineQuery(q)
    analyze.run({ query: q, demoMode, copyMode, scenarios })
  }

  const showPipeline = busy || analyze.pipeline.length > 0

  // Ticker tape items
  const tapeItems = useMemo(() => {
    return WATCHLIST.map((w) => {
      const mp = marketPrices.data?.[w.sym]
      if (!mp?.price) return { sym: w.sym.replace('.N0000', ''), text: '—' }
      const arrow = (mp.change ?? 0) > 0 ? '↑' : (mp.change ?? 0) < 0 ? '↓' : ''
      const chg = mp.pct_change != null ? `${arrow}${mp.pct_change.toFixed(2)}%` : '—'
      return { sym: w.sym.replace('.N0000', ''), text: `${mp.price.toFixed(2)} · ${chg}` }
    })
  }, [marketPrices.data])

  // Health component status
  const hc = health.data?.components ?? {}

  return (
    <div className="app">
      {/* Top bar */}
        <TopBar
          health={health.data}
          data={data}
          latency={analyze.latencyMs}
          marketOpen={marketOpen}
          onMethodology={() => setMethodOpen(true)}
          onRaw={() => setDrawerOpen(true)}
          onChat={() => setChatOpen(true)}
      />

      {/* Ticker tape */}
      <div className="ticker">
        <span className="ticker-label">LK · CSE</span>
        <div className="ticker-scroll">
          <div className="ticker-track">
            {[...tapeItems, ...tapeItems].map((item, i) => (
              <b key={i}>
                {item.sym} <em>{item.text}</em>
              </b>
            ))}
          </div>
        </div>
      </div>

      {/* Three-column main */}
      <div className="main">
        {/* ── Left col ── */}
        <div className="col">
          <QueryConsole
            query={query}
            setQuery={setQuery}
            demoMode={demoMode}
            setDemoMode={setDemoMode}
            scenarios={scenarios}
            setScenarios={setScenarios}
            busy={busy}
            onSubmit={() => runAnalysis()}
          />

          {showPipeline && (
            <div className="pipeline-mobile">
              <LoadingPipeline
                query={pipelineQuery}
                stages={analyze.pipeline}
                complete={!busy && Boolean(analyze.data)}
              />
            </div>
          )}

          <div className="watchlist-section">
            <div className="watchlist-head">
              <span>Watchlist</span>
              <span style={{ color: 'var(--ink-faint)' }}>Sample CSE stocks</span>
            </div>
            {WATCHLIST.map((w) => {
              const mp     = marketPrices.data?.[w.sym]
              const active = data?.symbol === w.sym
              // active symbol: prefer fresh analysis price, fall back to tradeSummary
              const price  = active
                ? (data?.microstructure?.latest_price ?? mp?.price ?? null)
                : (mp?.price ?? null)
              const chg    = mp?.change ?? null
              const pct    = mp?.pct_change ?? null
              const tone   = (chg ?? 0) > 0 ? 'up' : (chg ?? 0) < 0 ? 'down' : 'muted'
              const arrow  = (chg ?? 0) > 0 ? '↑' : (chg ?? 0) < 0 ? '↓' : ''
              return (
                <button
                  key={w.sym}
                  type="button"
                  className={`watchlist-row${active ? ' active' : ''}`}
                  onClick={() => runAnalysis(w.sym)}
                >
                  <span>
                    <b className="sym">{w.sym.replace('.N0000', '')}</b>
                    <span className="name">{w.name}</span>
                  </span>
                  <span className="price">{price != null ? price.toFixed(2) : '—'}</span>
                  <span className={`chg ${tone}`}>
                    {chg != null
                      ? `${arrow}${pct != null ? pct.toFixed(2) + '%' : chg.toFixed(2)}`
                      : '—'}
                  </span>
                </button>
              )
            })}
          </div>

          <div className="disclaimer-panel">
            <p>
              Argus surfaces what the data is saying and how much to trust it. It is not a
              buy/sell tool. All outputs are analytical — no investment decisions should be
              based on them.
            </p>
          </div>
        </div>

        {/* ── Center col ── */}
        <div className="col">
          {showPipeline && (
            <div className="pipeline-desktop">
              <LoadingPipeline
                query={pipelineQuery}
                stages={analyze.pipeline}
                complete={!busy && Boolean(analyze.data)}
              />
            </div>
          )}

          {analyze.isError && (
            <div style={{ margin: 16 }}>
              <div className="warning err">
                <span className="icon">■</span>
                <div className="body">{(analyze.error as Error).message}</div>
              </div>
            </div>
          )}

          {!data && !busy && !analyze.isError && <EmptyState />}

          {data && (
            <>
              <AnalysisOverview data={data} />
              <SignalPanel data={data} />
              <ForecastPanel data={data} />
              <RiskPanel data={data} />
              <TrendPanel data={data} />
              <AnomalyPanel data={data} />
              <RegimePanel data={data} />
              <OrderBookPanel data={data} />
              <IntradayContextPanel data={data} />
              <LineagePanel data={data} />
              <QualityFlagsPanel data={data} />
            </>
          )}
        </div>

        {/* ── Right col ── */}
        <div className="col">
          {data && (
            <>
              <ConfidencePanel data={data} />
              <MicrostructurePanel
                data={data}
                liveQuote={livePrice.quote}
                sparkData={livePrice.prices}
                marketOpen={marketOpen}
                isLive={livePrice.isLive}
                polling={livePrice.polling}
              />
              <LLMPanel data={data} />
            </>
          )}

          {!data && (
            <div style={{ padding: '16px 12px' }}>
              <div className="lbl" style={{ marginBottom: 8 }}>Right rail</div>
              <p className="muted" style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5 }}>
                Confidence gauge, live price, and analyst summary appear here after
                running an analysis.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Status bar */}
      <footer className="statusbar">
        <span>
          <span className={`dot ${health.data?.status === 'ok' ? 'ok' : 'warn'}`} />
          API: {hc.api ?? '—'}
        </span>
        <span>data_provider: {hc.data_provider ?? '—'}</span>
        <span>analytics_engine: {hc.analytics_engine ?? '—'}</span>
        <span>narrative: {hc.narrative_provider ?? '—'}</span>
        {data && <span>rows: {data.data_lineage?.historical_rows ?? '—'}</span>}
        {data && <span>health: {data.math_results?.overall_health ?? '—'}</span>}
        <span className="status-right">
          ARGUS FINAL · analytical output only · not investment advice
        </span>
      </footer>

      {drawerOpen && (
        <RawJsonDrawer data={data} latency={analyze.latencyMs} onClose={() => setDrawerOpen(false)} />
      )}
      {methodOpen && <MethodologyDrawer onClose={() => setMethodOpen(false)} />}
      <ChatDrawer
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        analysis={data}
        demoMode={demoMode}
        messages={chat.messages}
        isPending={chat.isPending}
        isRefreshing={chat.isRefreshing}
        error={chat.error}
        onClear={chat.clear}
        onSend={(message, refreshAnalysis) =>
          chat.send({
            message,
            analysis: data,
            demoMode,
            copyMode,
            refreshAnalysis,
            onAnalysisUpdate: analyze.applyAnalysis,
          })
        }
      />
    </div>
  )
}

function EmptyState() {
  return (
    <div className="empty-state">
      <span className="lbl">ready</span>
      <h2>Ask Argus to read the market.</h2>
      <p>
        Try <b>Analyze COMB</b>, <b>What about JKH?</b>, or <b>HNB.N0000</b>. The dashboard
        shows confidence first, then signal, risk, anomaly, regime, data lineage, and live
        microstructure.
      </p>
      <div className="empty-hint">
        <span>Mode</span>
        <strong>Live CSE REST</strong>
        <span>Output</span>
        <strong>Evidence only</strong>
        <span>Rows</span>
        <strong>≈120 cap</strong>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <CopyModeProvider>
      <AppShell />
    </CopyModeProvider>
  )
}
