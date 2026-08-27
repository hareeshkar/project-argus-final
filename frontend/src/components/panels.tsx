import { useState } from 'react'

import type { ArgusAnalysis, Health, PipelineStage } from '../api/schemas'
import type { LivePriceQuote } from '../hooks/useLivePrice'
import { ForecastChart, RiskBars } from './charts'
import { fmt } from '../lib/format'
import { useCopyMode } from '../lib/copy'
import { GLOSSARY } from '../lib/glossary'
import {
  Badge,
  ConfidenceGauge,
  ContribBars,
  InfoTip,
  JsonView,
  Kpi,
  Panel,
  ScoreMeter,
  SignalBadge,
  Sparkline,
  Warning,
} from './primitives'

// ─── Top bar ──────────────────────────────────────────────────────────────────

export function TopBar({
  health,
  data,
  latency,
  marketOpen,
  onMethodology,
  onRaw,
  onChat,
}: {
  health?: Health
  data?: ArgusAnalysis
  latency?: number
  marketOpen?: boolean
  onMethodology: () => void
  onRaw: () => void
  onChat: () => void
}) {
  const copy = useCopyMode()
  const signal = data?.indicator_vote ?? data?.ensemble
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" />
        <span className="brand-name">
          PROJECT ARGUS<span className="sub">v2.0 · cse analytics</span>
        </span>
      </div>
      <div className="topbar-meta">
        <div className="topbar-cell" style={{ minWidth: 130 }}>
          <span className="lbl">API Health</span>
          <span className="val">
            <span className={`dot ${health?.status === 'ok' ? 'ok' : 'warn'}`} />
            {health?.status?.toUpperCase() ?? '—'} · {latency != null ? `${latency}ms` : '—'}
          </span>
        </div>
        <div className="topbar-cell" style={{ minWidth: 160 }}>
          <span className="lbl">Active Symbol</span>
          <span className="val">{data?.symbol ?? '—'}</span>
        </div>
        <div className="topbar-cell" style={{ minWidth: 110 }}>
          <span className="lbl">CSE Market</span>
          <span className="val">
            <span className={`dot ${marketOpen ? 'live' : 'idle'}`} />
            {marketOpen ? 'OPEN' : 'CLOSED'}
          </span>
        </div>
        <div className="topbar-cell" style={{ minWidth: 120 }}>
          <span className="lbl">{copy.topbar('signal')}</span>
          <span className="val">
            <span
              className={
                signal?.signal === 'BULLISH'
                  ? 'up'
                  : signal?.signal === 'BEARISH'
                    ? 'down'
                    : 'neutral'
              }
            >
              {copy.badge('signal', signal?.signal)}
            </span>
          </span>
        </div>
        <div className="topbar-cell" style={{ minWidth: 130 }}>
          <span className="lbl">{copy.topbar('dataMode')}</span>
          <span className="val accent-txt">
            {data?.data_source_mode?.replace(/_/g, ' ').toUpperCase() ?? '—'}
          </span>
        </div>
        <div className="topbar-spacer" />
      </div>
      <div className="topbar-actions">
        <div className="copy-mode-toggle" role="radiogroup" aria-label="Copy mode">
          <button
            type="button"
            role="radio"
            aria-checked={copy.mode === 'simple'}
            aria-label="Simple mode"
            className={copy.mode === 'simple' ? 'active' : ''}
            onClick={() => copy.setMode('simple')}
          >
            SIMPLE
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={copy.mode === 'experience'}
            aria-label="Experience mode"
            className={copy.mode === 'experience' ? 'active' : ''}
            onClick={() => copy.setMode('experience')}
          >
            EXPERIENCE
          </button>
        </div>
        <button type="button" onClick={onChat}>
          CHAT
        </button>
        <button type="button" onClick={onMethodology}>
          METHODOLOGY
        </button>
        <button type="button" onClick={onRaw}>
          RAW JSON
        </button>
      </div>
    </header>
  )
}

// ─── Query console ────────────────────────────────────────────────────────────

export function QueryConsole({
  query,
  setQuery,
  demoMode,
  setDemoMode,
  busy,
  onSubmit,
}: {
  query: string
  setQuery: (q: string) => void
  demoMode: boolean
  setDemoMode: (v: boolean) => void
  busy: boolean
  onSubmit: () => void
}) {
  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') onSubmit()
  }
  return (
    <div className="query-console">
      <div className="query-input">
        <span className="caret">▸</span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Analyze COMB · What about JKH? · HNB.N0000"
        />
        <button type="button" className="submit" onClick={onSubmit}>
          {busy ? 'RUNNING…' : 'RUN ↵'}
        </button>
      </div>
      <div className="query-row2">
        <div className="query-hint">
          <span className="key">↵</span> submit · queries are parsed for symbols
        </div>
        <label className="demo-toggle">
          <input
            type="checkbox"
            checked={demoMode}
            onChange={(e) => setDemoMode(e.target.checked)}
          />
          demo
        </label>
      </div>
    </div>
  )
}

// ─── Loading pipeline ─────────────────────────────────────────────────────────

const PIPELINE_STAGE_IDS = ['parse', 'fetch', 'models', 'confidence', 'narrative'] as const

function pipelineIcon(status: PipelineStage['status']) {
  if (status === 'done') return 'ok'
  if (status === 'degraded') return '!'
  if (status === 'error') return 'x'
  if (status === 'running') return '>'
  if (status === 'queued') return '·'
  return '.'
}

function pipelineTime(stage?: PipelineStage) {
  if (!stage) return 'queued'
  if (stage.status === 'running') return 'running...'
  if (stage.elapsed_ms != null) {
    const ms = stage.elapsed_ms < 1 ? 1 : stage.elapsed_ms
    return `${stage.status} · ${ms}ms`
  }
  return stage.status
}

function pipelineDetail(stage?: PipelineStage) {
  if (!stage?.detail) return stage?.message
  const detail = Object.entries(stage.detail)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .slice(0, 4)
    .map(([key, value]) => `${key.replace(/_/g, ' ')}: ${String(value)}`)
    .join(' · ')
  return detail || stage.message
}

export function LoadingPipeline({
  query,
  stages,
  complete,
}: {
  query: string
  stages: PipelineStage[]
  complete?: boolean
}) {
  const copy = useCopyMode()
  return (
    <div style={{ padding: 24 }}>
      <div className="pipeline">
        <h3>
          <span>▸ pipeline.run({JSON.stringify(query)})</span>
          {complete && <em>trace retained</em>}
        </h3>
        {PIPELINE_STAGE_IDS.map((id, i) => {
          const stage = stages.find((item) => item.stage_id === id)
          const status = stage?.status ?? 'queued'
          return (
            <div key={id} className={`pipeline-step ${status}`}>
              <span className="ico">{pipelineIcon(status)}</span>
              <span className="name">
                [{String(i + 1).padStart(2, '0')}] {stage?.title ?? copy.pipelineStage(id)}
                <small>{pipelineDetail(stage)}</small>
              </span>
              <span className="time">{pipelineTime(stage)}</span>
            </div>
          )
        })}
        <div className="pipeline-note">
          Live progress is streamed from the backend so the trace reflects the actual analysis path.
          </div>
      </div>
    </div>
  )
}

// ─── 01 — Analysis overview ───────────────────────────────────────────────────

export function AnalysisOverview({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('01')
  const signal = data.indicator_vote ?? data.ensemble
  const m = data.microstructure
  const c = data.confidence
  const tone =
    signal?.signal === 'BULLISH' ? 'up' : signal?.signal === 'BEARISH' ? 'down' : 'neutral'
  const lowConf = c.score < 0.5
  return (
    <Panel
      idx="01"
      title={p.title}
      meta={data.symbol}
      right={
        <Badge kind="accent">
          {data.data_source_mode?.replace(/_/g, ' ').toUpperCase() ?? '—'}
        </Badge>
      }
      flush
    >
      <div className="hero-grid">
        <div className="hero-cell">
          <div className="lbl">{copy.hero('confidence')}</div>
          <div className="row gap-12" style={{ alignItems: 'baseline' }}>
            <span
              className="val"
              style={{
                color: lowConf ? 'var(--down)' : c.score < 0.7 ? 'var(--warn)' : 'var(--up)',
              }}
            >
              {fmt.score(c.score)}
            </span>
            <span className="lbl-strong">{copy.badge('confidence', c.label)}</span>
          </div>
          <div className="companion">{copy.hero('confidenceCompanion')}</div>
        </div>
        <div className="hero-cell" style={{ opacity: lowConf ? 0.55 : 1 }}>
          <div className="lbl">{copy.hero('signal')}</div>
          <div className="row gap-8">
            <span className={`val ${tone}`}>{copy.badge('signal', signal?.signal)}</span>
            <SignalBadge signal={signal?.signal} label={copy.badge('signal', signal?.signal)} />
          </div>
          <div className="companion">
            score {fmt.signed(signal?.score, 2)} · conf {fmt.score(signal?.confidence)}
          </div>
        </div>
        <div className="hero-cell">
          <div className="lbl">{copy.hero('price')}</div>
          <div className="val">{fmt.price(m?.latest_price)}</div>
          <div className="companion">{copy.hero('priceCompanion')}</div>
        </div>
        <div className="hero-cell">
          <div className="lbl">{copy.hero('pipeline')}</div>
          <div className="val mono" style={{ fontSize: 16 }}>
            {fmt.score(data.processing_time)}s
          </div>
          <div className="companion">{fmt.time(data.timestamp)}</div>
        </div>
      </div>
    </Panel>
  )
}

// ─── 02 — Ensemble signal ─────────────────────────────────────────────────────

export function SignalPanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('02')
  const e = data.indicator_vote ?? data.ensemble
  if (!e) return null

  const components = e.components ?? {}
  const items = [
    { name: 'trend', value: components.trend_score },
    { name: 'volatility', value: components.volatility_score },
    { name: 'liquidity', value: components.liquidity_score },
    { name: 'anomaly', value: components.anomaly_score },
    { name: 'order flow', value: components.order_flow_score },
    { name: 'intraday', value: components.intraday_score },
  ]
  const scale = copy.scoreMeter()
  const dailyScore = e.daily_score
  const intradayNudge = e.intraday_nudge
  const hasIntraday = dailyScore != null && intradayNudge != null && Math.abs(intradayNudge) > 1e-9

  return (
    <Panel
      idx="02"
      title={p.title}
      meta={p.meta}
      right={<SignalBadge signal={e.signal} label={copy.badge('signal', e.signal)} />}
    >
      <div className="stack-12">
        <ScoreMeter value={e.score ?? 0} scale={scale} />
        <div className="between">
          <span className="lbl">Aggregate Score</span>
          <span className="num" style={{ fontSize: 16 }}>
            {fmt.signed(e.score, 2)}
          </span>
        </div>
        {hasIntraday && (
          <div className="muted mono" style={{ fontSize: 10 }}>
            daily {fmt.signed(dailyScore, 3)} · intraday nudge {fmt.signed(intradayNudge, 3)}
          </div>
        )}
        <div className="divider" />
        <div className="lbl-strong">Component Contributions</div>
        <ContribBars items={items} />
        <div className="muted" style={{ fontSize: 10 }}>
          trend · volatility · liquidity · anomaly = daily stats; order flow · intraday = live snapshot nudge
        </div>
        <div className="divider" />
        <div className="lbl-strong">Drivers</div>
        <ul style={{ margin: 0, paddingLeft: 16 }} className="dim">
          {(e.drivers ?? []).map((d, i) => (
            <li key={i} style={{ fontSize: 12, lineHeight: 1.55, fontFamily: 'var(--font-mono)' }}>
              {d}
            </li>
          ))}
        </ul>
        <div className="ascii" style={{ fontSize: 10 }}>
          // not a buy/sell recommendation — analytical signal only
        </div>
      </div>
    </Panel>
  )
}

// ─── 03 — Confidence & data quality ──────────────────────────────────────────

export function ConfidencePanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('03')
  const c = data.confidence
  const pens = c.penalties ?? {}
  const penRows = Object.entries(pens).map(([name, v]) => [name, v] as [string, number])
  const maxPen = Math.max(0.25, ...penRows.map(([, v]) => v))

  return (
    <Panel
      idx="03"
      title={p.title}
      meta={p.meta}
      right={
        <Badge kind={c.score < 0.5 ? 'err' : c.score < 0.7 ? 'warn' : 'ok'}>
          {copy.badge('confidence', c.label)}
        </Badge>
      }
    >
      <div className="stack-12">
        <ConfidenceGauge value={c.score} label={copy.badge('confidence', c.label)} />
        <div>
          <div className="lbl-strong" style={{ marginBottom: 6 }}>
            Penalty Breakdown
          </div>
          <div className="stack-4">
            {penRows.map(([name, v]) => (
              <div
                className="contrib-row"
                key={name}
                style={{ gridTemplateColumns: '140px 1fr 44px' }}
              >
                <span className="name">{name}</span>
                <span className="contrib-bar">
                  <span
                    className="fill warn"
                    style={{
                      left: 0,
                      width: `${(v / maxPen) * 100}%`,
                      background: v > 0 ? 'var(--warn)' : 'transparent',
                    }}
                  />
                </span>
                <span className={`val ${v > 0 ? 'down' : 'muted'}`}>−{v.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="lbl-strong" style={{ marginBottom: 6 }}>
            Reasons
          </div>
          <ul style={{ margin: 0, paddingLeft: 16 }} className="dim">
            {(c.reasons ?? []).map((r, i) => (
              <li
                key={i}
                style={{ fontSize: 11.5, lineHeight: 1.55, fontFamily: 'var(--font-mono)' }}
              >
                {r}
              </li>
            ))}
          </ul>
        </div>
        <div className="ascii" style={{ fontSize: 10 }}>
          // confidence = trust in analysis, NOT predicted profit probability
        </div>
      </div>
    </Panel>
  )
}

// ─── 04 — Forecast & ARIMA diagnostics ───────────────────────────────────────

export function ForecastPanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('04')
  const a = data.math_results.arima
  const [showCandidates, setShowCandidates] = useState(false)
  const history = data.price_history?.closes ?? []
  const lastClose = history.length > 0 ? history[history.length - 1] : null
  const livePrice = data.microstructure?.latest_price
  const priceGap =
    lastClose != null && livePrice != null && lastClose > 0
      ? Math.abs(livePrice - lastClose) / lastClose
      : 0

  if (!a) return null

  return (
    <Panel
      idx="04"
      title={p.title}
      meta={`${a.model_used} · ${history.length} daily closes`}
      right={
        <span className="row gap-4">
          <Badge kind={a.beats_naive ? 'ok' : 'err'}>
            {a.beats_naive ? 'BEATS NAIVE' : 'FAILS NAIVE'}
          </Badge>
          <Badge
            kind={
              a.forecast_confidence === 'HIGH'
                ? 'ok'
                : a.forecast_confidence === 'MODERATE'
                  ? 'warn'
                  : 'err'
            }
          >
            FC {a.forecast_confidence}
          </Badge>
        </span>
      }
    >
      <div className="stack-12">
        <ForecastChart
          history={history}
          forecast={a.forecast ?? []}
          lower={a.confidence_interval?.lower ?? []}
          upper={a.confidence_interval?.upper ?? []}
        />
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <Kpi
            label="t+1"
            value={fmt.price(a.forecast?.[0])}
            sub={`[${fmt.price(a.confidence_interval?.lower?.[0])}, ${fmt.price(a.confidence_interval?.upper?.[0])}]`}
          />
          <Kpi
            label="t+2"
            value={fmt.price(a.forecast?.[1])}
            sub={`[${fmt.price(a.confidence_interval?.lower?.[1])}, ${fmt.price(a.confidence_interval?.upper?.[1])}]`}
          />
          <Kpi
            label="t+3"
            value={fmt.price(a.forecast?.[2])}
            sub={`[${fmt.price(a.confidence_interval?.lower?.[2])}, ${fmt.price(a.confidence_interval?.upper?.[2])}]`}
          />
          <Kpi
            label="Trend Est."
            value={a.trend ?? '—'}
            sub={`order (${(a.selected_order ?? []).join(',')})`}
          />
        </div>
        <div className="between">
          <dl className="kv">
            <dt>AIC</dt>
            <dd>{fmt.score(a.aic)}</dd>
            <dt>AICc</dt>
            <dd>{fmt.score(a.aicc)}</dd>
            <dt>BIC</dt>
            <dd>{fmt.score(a.bic)}</dd>
            {a.oos_evaluation && (a.oos_evaluation.model_oos_rmse ?? null) != null && (
              <>
                <dt>OOS RMSE</dt>
                <dd>{fmt.score(a.oos_evaluation.model_oos_rmse)}</dd>
                <dt>Naive RMSE</dt>
                <dd>{fmt.score(a.oos_evaluation.naive_flat_rmse)}</dd>
                <dt>Holdout</dt>
                <dd>{a.oos_evaluation.holdout_size} days</dd>
              </>
            )}
          </dl>
          <button
            type="button"
            className="badge"
            onClick={() => setShowCandidates((s) => !s)}
          >
            {showCandidates ? '▾ HIDE' : '▸ SHOW'} CANDIDATES
          </button>
        </div>
        {showCandidates && (
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--line)',
              padding: 10,
            }}
          >
            <div className="lbl-strong" style={{ marginBottom: 6 }}>
              Candidate Models (selected via AIC)
            </div>
            <div className="row wrap gap-4">
              {(a.candidate_models ?? []).map((m) => (
                <span key={m} className={`badge${m === a.model_used ? ' accent' : ''}`}>
                  {m}
                  {m === a.model_used && ' ✓'}
                </span>
              ))}
            </div>
          </div>
        )}
        {a.beats_naive === false && (
          <Warning
            kind="warn"
            text={
              a.oos_evaluation?.model_oos_rmse != null
                ? `Forecast lost to the naive baseline on a ${a.oos_evaluation.holdout_size}-day holdout (model RMSE ${fmt.score(a.oos_evaluation.model_oos_rmse)} vs naive ${fmt.score(a.oos_evaluation.naive_flat_rmse)}). Treat forecast as informational only.`
                : 'Forecast model did not beat naive baseline. Treat forecast as informational only.'
            }
            source="arima.beats_naive = false (out-of-sample evaluation)"
          />
        )}
        {history.length === 0 && (
          <Warning kind="warn" text="No historical closes available for chart — forecast numbers still come from the full daily series." />
        )}
        {priceGap > 0.005 && (
          <Warning
            kind="info"
            text={`Chart ends at last daily close (${fmt.price(lastClose)}). Live price (${fmt.price(livePrice)}) may differ when the market is open or after the last session close.`}
          />
        )}
        <div className="ascii" style={{ fontSize: 10 }}>
          // gray = real CSE daily closes · yellow = ARIMA 3-day forecast + 95% CI · residual LB p-value:{' '}
          {fmt.score(a.residual_white_noise_pvalue)}
          {a.oos_evaluation?.beats_naive_oos != null
            ? ` · beats naive on holdout: ${a.oos_evaluation.beats_naive_oos ? 'YES' : 'NO'} (OOS)`
            : ''}
        </div>
      </div>
    </Panel>
  )
}

// ─── 05 — Risk metrics ────────────────────────────────────────────────────────

export function RiskPanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('05')
  const v = data.math_results.volatility ?? {}
  const dd = data.math_results.drawdown ?? {}
  const tailRisk = (v.historical_var_95_pct ?? 0) > (v.var_95_pct ?? 0)
  const daily = copy.risk('dailyVol')
  const var95 = copy.risk('var95')
  const hist95 = copy.risk('hist95')
  const hist99 = copy.risk('hist99')
  const parkinson = copy.risk('parkinson')
  const percentile = copy.risk('percentile')
  const drawdown = copy.risk('drawdown')
  const maxDd = copy.risk('maxDrawdown')
  const tail = copy.riskWarning()

  return (
    <Panel
      idx="05"
      title={p.title}
      meta={copy.riskMeta()}
      right={
        <Badge
          kind={
            v.risk_level === 'HIGH' ? 'err' : v.risk_level === 'MODERATE' ? 'warn' : 'ok'
          }
        >
          {copy.badge('risk', v.risk_level)}
        </Badge>
      }
    >
      <div className="stack-12">
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <Kpi
            label={daily.label}
            value={fmt.pct(v.daily_volatility_pct)}
            sub={daily.sub}
            tip={daily.tip}
          />
          <Kpi
            label={var95.label}
            value={fmt.pct(v.var_95_pct)}
            sub={var95.sub}
            tip={var95.tip}
          />
          <Kpi
            label={hist95.label}
            value={fmt.pct(v.historical_var_95_pct)}
            sub={tailRisk ? (copy.mode === 'simple' ? 'heavier than normal' : 'empirical > EWMA') : hist95.sub}
            tone={tailRisk ? 'down' : ''}
            tip={hist95.tip}
          />
          <Kpi
            label={hist99.label}
            value={fmt.pct(v.historical_var_99_pct)}
            sub={hist99.sub}
            tip={hist99.tip}
          />
        </div>
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <Kpi
            label={parkinson.label}
            value={fmt.pct(v.parkinson_volatility_pct)}
            sub={parkinson.sub}
            tip={parkinson.tip}
          />
          <Kpi
            label={percentile.label}
            value={v.volatility_percentile != null ? `${v.volatility_percentile.toFixed(1)}%` : '—'}
            sub={percentile.sub}
            tip={percentile.tip}
          />
          <Kpi
            label={drawdown.label}
            value={fmt.pct(dd.current_drawdown_pct)}
            sub={`${dd.drawdown_duration_days ?? '—'} days`}
            tone="down"
            tip={drawdown.tip}
          />
          <Kpi
            label={maxDd.label}
            value={fmt.pct(dd.max_drawdown_pct)}
            sub={maxDd.sub}
            tone="down"
            tip={maxDd.tip}
          />
        </div>
        <RiskBars data={data} barLabels={copy.riskBars()} />
        {tailRisk && <Warning text={tail.text} source={tail.source} />}
        <div className="ascii" style={{ fontSize: 10 }}>
          {copy.riskNote()}
        </div>
      </div>
    </Panel>
  )
}

// ─── 06 — Trend / OLS regression ─────────────────────────────────────────────

export function TrendPanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('06')
  const lr = data.math_results.trend ?? {}
  const regime = data.math_results.regime?.trend_regime
  const slopeTone: 'up' | 'down' | 'neutral' =
    (lr.slope ?? 0) > 0 ? 'up' : (lr.slope ?? 0) < 0 ? 'down' : 'neutral'

  return (
    <Panel
      idx="06"
      title={p.title}
      meta={p.meta ?? `${lr.days_analyzed ?? '—'}-day window`}
      right={
        <Badge kind={(lr.r_squared ?? 0) > 0.5 ? 'ok' : (lr.r_squared ?? 0) > 0.25 ? 'warn' : 'err'}>
          {lr.is_strong_trend ? 'STRONG FIT' : 'WEAK FIT'}
        </Badge>
      }
    >
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <Kpi
          label="Slope (β)"
          value={(lr.slope ?? 0).toFixed(4)}
          sub={(lr.slope ?? 0) > 0 ? 'upward fit' : 'downward fit'}
          tone={slopeTone}
        />
        <Kpi
          label="R²"
          value={fmt.score(lr.r_squared)}
          sub={(lr.r_squared ?? 0) > 0.5 ? 'moderate fit' : 'low explanatory'}
        />
        <Kpi
          label="Direction"
          value={copy.enumLabel('trend', lr.trend_direction)}
          sub={`regime: ${copy.enumLabel('trend', regime)}`}
          tone={slopeTone}
        />
        <Kpi label="N (days)" value={lr.days_analyzed ?? '—'} sub="OLS on log-close" />
      </div>
      <div className="ascii" style={{ fontSize: 10, marginTop: 8 }}>
        // linear slope is descriptive only — no causal interpretation
      </div>
    </Panel>
  )
}

// ─── 07 — Anomaly detection ───────────────────────────────────────────────────

export function AnomalyPanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('07')
  const z = data.math_results.anomaly
  if (!z || z.error) return null

  const classicalAnomaly =
    Math.abs(z.price_zscore ?? z.return_zscore ?? 0) >= 2 ||
    Math.abs(z.volume_zscore ?? 0) >= 2
  const modifiedAnomaly =
    Math.abs(z.modified_price_zscore ?? z.modified_return_zscore ?? 0) >= 2 ||
    Math.abs(z.modified_volume_zscore ?? 0) >= 2
  const disagree = classicalAnomaly !== modifiedAnomaly

  const pZ = z.price_zscore ?? z.return_zscore ?? 0
  const modZ = z.modified_price_zscore ?? z.modified_return_zscore ?? 0
  const volZ = z.volume_zscore ?? 0
  const modVolZ = z.modified_volume_zscore ?? 0

  return (
    <Panel
      idx="07"
      title={p.title}
      meta={p.meta ?? `Z-score · lookback ${z.lookback_days ?? 20}d`}
      right={
        <Badge kind={z.is_anomalous ? 'warn' : 'ok'}>
          {z.is_anomalous ? 'ANOMALY FLAGGED' : 'WITHIN NORMS'}
        </Badge>
      }
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 1,
          background: 'var(--line)',
          border: '1px solid var(--line)',
        }}
      >
        <div style={{ background: 'var(--bg)', padding: 10 }}>
          <div className="lbl">Classical (Z)</div>
          <div className="stack-4" style={{ marginTop: 6 }}>
            <div className="between">
              <span className="muted mono">price</span>
              <span className={`num${Math.abs(pZ) > 2 ? ' down' : ''}`}>
                {fmt.signed(pZ, 3)}
              </span>
            </div>
            <div className="between">
              <span className="muted mono">volume</span>
              <span className={`num${Math.abs(volZ) > 2 ? ' down' : ''}`}>
                {fmt.signed(volZ, 3)}
              </span>
            </div>
          </div>
        </div>
        <div style={{ background: 'var(--bg)', padding: 10 }}>
          <div className="lbl">Modified (MAD)</div>
          <div className="stack-4" style={{ marginTop: 6 }}>
            <div className="between">
              <span className="muted mono">price</span>
              <span className={`num${Math.abs(modZ) > 2 ? ' down' : ''}`}>
                {fmt.signed(modZ, 3)}
              </span>
            </div>
            <div className="between">
              <span className="muted mono">volume</span>
              <span className={`num${Math.abs(modVolZ) > 2 ? ' down' : ''}`}>
                {fmt.signed(modVolZ, 3)}
              </span>
            </div>
          </div>
        </div>
      </div>
      <div className="row gap-4" style={{ marginTop: 10 }}>
        {z.price_anomaly && <Badge kind="warn">PRICE ANOMALY</Badge>}
        {z.volume_anomaly && <Badge kind="warn">VOLUME ANOMALY</Badge>}
        {!z.price_anomaly && !z.volume_anomaly && <Badge kind="ok">NO INDIVIDUAL FLAG</Badge>}
      </div>
      {disagree && (
        <div style={{ marginTop: 10 }}>
          <Warning text="Classical and robust anomaly measures disagree. Modified Z-score (MAD-based) is recommended for illiquid CSE stocks where outliers contaminate the sample mean." />
        </div>
      )}
      <div className="ascii" style={{ fontSize: 10, marginTop: 8 }}>
        // MAD-based modified Z is more robust to extreme thin-volume prints
      </div>
    </Panel>
  )
}

// ─── 08 — Market regime ───────────────────────────────────────────────────────

export function RegimePanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('08')
  const r = data.math_results.regime
  if (!r) return null

  return (
    <Panel idx="08" title={p.title} meta={p.meta}>
      <div className="regime-grid">
        <div className="regime-cell">
          <div className="lbl">Trend Regime</div>
          <div className="val">{copy.enumLabel('trend', r.trend_regime)}</div>
        </div>
        <div className="regime-cell">
          <div className="lbl">Volatility Regime</div>
          <div className={`val${r.volatility_regime === 'HIGH' ? ' down' : ''}`}>
            {copy.enumLabel('volRegime', r.volatility_regime)}
          </div>
          {r.volatility_percentile != null && (
            <>
              <div className="pct-bar">
                <span
                  className="fill"
                  style={{
                    width: `${r.volatility_percentile}%`,
                    background:
                      r.volatility_regime === 'HIGH' ? 'var(--down)' : 'var(--accent)',
                  }}
                />
              </div>
              <div className="pct">percentile {r.volatility_percentile.toFixed(1)}</div>
            </>
          )}
        </div>
        <div className="regime-cell">
          <div className="lbl">Liquidity Regime</div>
          <div className={`val${r.liquidity_regime === 'THIN' ? ' warn' : ''}`}>
            {copy.enumLabel('liquidity', r.liquidity_regime)}
          </div>
          {r.volume_percentile != null && (
            <>
              <div className="pct-bar">
                <span
                  className="fill"
                  style={{
                    width: `${r.volume_percentile}%`,
                    background:
                      r.liquidity_regime === 'THIN' ? 'var(--warn)' : 'var(--up)',
                  }}
                />
              </div>
              <div className="pct">percentile {r.volume_percentile.toFixed(1)}</div>
            </>
          )}
        </div>
      </div>
    </Panel>
  )
}

// ─── 09 — Order book pressure ─────────────────────────────────────────────────

export function OrderBookPanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('09')
  const ob = data.order_book
  if (!ob || (ob.bids == null && ob.asks == null)) return null

  const total = (ob.bids ?? 0) + (ob.asks ?? 0)
  const bidPct = total ? ((ob.bids ?? 0) / total) * 100 : 50
  const askPct = 100 - bidPct
  const press = ob.pressure ?? 0

  return (
    <Panel
      idx="09"
      title={p.title}
      meta={p.meta}
      right={
        <Badge kind={press > 0.15 ? 'ok' : press < -0.15 ? 'err' : 'neutral'}>
          {press > 0 ? 'BID-WEIGHTED' : press < 0 ? 'ASK-WEIGHTED' : 'BALANCED'}
        </Badge>
      }
    >
      <div className="ob">
        <div className="ob-side bid">
          <div className="head">BIDS</div>
          <div className="qty">{fmt.compact(ob.bids)}</div>
          <div className="muted mono" style={{ fontSize: 10 }}>
            {bidPct.toFixed(1)}% of book
          </div>
        </div>
        <div className="ob-side ask">
          <div className="head" style={{ textAlign: 'right' }}>
            ASKS
          </div>
          <div className="qty" style={{ textAlign: 'right' }}>
            {fmt.compact(ob.asks)}
          </div>
          <div className="muted mono" style={{ fontSize: 10, textAlign: 'right' }}>
            {askPct.toFixed(1)}% of book
          </div>
        </div>
        <div className="ob-pressure">
          <div className="ob-bar">
            <span className="b solid" style={{ width: `${bidPct}%` }} />
            <span className="a solid" style={{ width: `${askPct}%` }} />
          </div>
          <div className="between" style={{ marginTop: 8 }}>
            <span className="lbl">Pressure</span>
            <span
              className="num"
              style={{
                color: press > 0 ? 'var(--up)' : press < 0 ? 'var(--down)' : 'var(--neutral)',
              }}
            >
              {fmt.signed(press, 4)}
            </span>
          </div>
          <ScoreMeter
            value={Math.max(-1, Math.min(1, press))}
            scale={['ASK-HEAVY', 'BAL', 'BID-HEAVY']}
          />
          {ob.spread_estimate != null && (
            <div className="muted mono" style={{ fontSize: 10, marginTop: 8 }}>
              spread est. {fmt.price(ob.spread_estimate)}
            </div>
          )}
        </div>
      </div>
    </Panel>
  )
}

// ─── 10 — Live price (REST, 1s refresh) ───────────────────────────────────────

export function MicrostructurePanel({
  data,
  liveQuote,
  sparkData,
  marketOpen,
  isLive = false,
  polling = false,
}: {
  data: ArgusAnalysis
  liveQuote?: LivePriceQuote
  sparkData: number[]
  marketOpen: boolean
  isLive?: boolean
  polling?: boolean
}) {
  const copy = useCopyMode()
  const p = copy.panel('10')
  const base = data.microstructure ?? {}
  const price = liveQuote?.price ?? base.latest_price
  const change = liveQuote?.change ?? null
  const pctChange = liveQuote?.pct_change ?? null
  const dayVolume = liveQuote?.sharevolume ?? base.window_volume
  const lastTrade = liveQuote?.last_traded_time ?? base.last_update
  const tone = (pctChange ?? change ?? 0) >= 0 ? 'up' : 'down'

  return (
    <Panel
      idx="10"
      title={p.title}
      meta={p.meta ?? (marketOpen ? 'CSE trade summary · 1s' : 'last close')}
      right={
        <span className="row gap-4">
          <InfoTip text={GLOSSARY.liveTrading} />
          <span className={`dot ${isLive ? 'live' : marketOpen ? 'idle' : 'idle'}`} />
          <span className="lbl">
            {isLive ? (polling ? 'UPDATING' : 'LIVE') : marketOpen ? 'WAITING' : 'CLOSED'}
          </span>
        </span>
      }
    >
      <div className="stack-12">
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
          <Kpi label="Latest Price" value={fmt.price(price)} large tip="Last traded price from CSE trade summary." />
          <Kpi
            label="Change Today"
            value={fmt.signed(change, 2)}
            sub={fmt.signedPct(pctChange)}
            tone={tone as 'up' | 'down'}
            tip="Price change vs previous close."
          />
        </div>
        <Sparkline
          values={sparkData.length > 0 ? sparkData : price != null ? [price] : []}
          stroke={tone === 'up' ? 'var(--up)' : 'var(--down)'}
        />
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
          <Kpi
            label="Day Volume"
            value={fmt.compact(dayVolume)}
            sub="shares today"
            tip="Total shares traded today from the exchange summary."
          />
          <Kpi
            label="Last Trade"
            value={fmt.ago(lastTrade)}
            sub={fmt.hhmmss(typeof lastTrade === 'number' ? lastTrade : null)}
            tip="When the exchange last reported a trade for this symbol."
          />
          {liveQuote?.high != null && liveQuote?.low != null && (
            <>
              <Kpi label="Day High" value={fmt.price(liveQuote.high)} tip="Highest price traded today." />
              <Kpi label="Day Low" value={fmt.price(liveQuote.low)} tip="Lowest price traded today." />
            </>
          )}
        </div>
        {!marketOpen && (
          <Warning kind="info" text="Market is closed (Mon–Fri 09:30–14:30 Sri Lanka time). Showing last available prices." />
        )}
        {marketOpen && !isLive && (
          <Warning kind="info" text="Waiting for live price from the exchange — this refreshes every second during market hours." />
        )}
        {data.intraday_context && data.intraday_context.available && (
          <div className="muted mono" style={{ fontSize: 10, lineHeight: 1.6 }}>
            intraday ctx:{' '}
            {data.intraday_context.source === 'CSE_WEBSOCKET_DAYTRADE'
              ? 'websocket ticks'
              : data.intraday_context.source === 'CSE_REST_TRADE_SUMMARY'
                ? 'rest snapshot'
                : data.intraday_context.source === 'DEMO_INTRADAY'
                  ? 'demo (synthetic)'
                  : (data.intraday_context.source ?? '—')}
            {data.intraday_context.price_divergence_pct != null && (
              <> · vs close {fmt.signed(data.intraday_context.price_divergence_pct, 2)}%</>
            )}
            {data.intraday_context.vwap_deviation_pct != null && (
              <> · vs vwap {fmt.signed(data.intraday_context.vwap_deviation_pct, 2)}%</>
            )}
            {data.intraday_context.is_stale && <> · stale</>}
          </div>
        )}
      </div>
    </Panel>
  )
}

// ─── 14 — Intraday context ────────────────────────────────────────────────────

export function IntradayContextPanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('14')
  const ctx = data.intraday_context
  const vote = data.indicator_vote
  const components = vote?.components ?? {}

  // Daily-only state: no live intraday window for this symbol.
  if (!ctx || !ctx.available) {
    return (
      <Panel idx="14" title={p.title} meta={p.meta}>
        <div className="stack-12">
          <Badge kind="neutral">DAILY-ONLY</Badge>
          <Warning kind="info" text={GLOSSARY.intradayUnavailable} />
          <div className="muted mono" style={{ fontSize: 10 }}>
            source: {ctx?.source ?? 'UNAVAILABLE'} · ensemble nudge 0.000
          </div>
        </div>
      </Panel>
    )
  }

  const pressure = ctx.order_flow_pressure ?? 0
  const divergence = ctx.price_divergence_pct
  const vwapDev = ctx.vwap_deviation_pct
  const stale = Boolean(ctx.is_stale)
  const isDemo = ctx.source === 'DEMO_INTRADAY'
  const sourceLabel =
    ctx.source === 'CSE_WEBSOCKET_DAYTRADE'
      ? 'WEBSOCKET TICKS'
      : ctx.source === 'CSE_REST_TRADE_SUMMARY'
        ? 'REST SNAPSHOT'
        : ctx.source === 'DEMO_INTRADAY'
          ? 'DEMO (synthetic)'
          : (ctx.source ?? '—')

  const nudge = vote?.intraday_nudge
  const dailyScore = vote?.daily_score
  const combinedScore = vote?.score
  const hasNudge = nudge != null && dailyScore != null

  return (
    <Panel
      idx="14"
      title={p.title}
      meta={p.meta}
      right={
        <span className="row gap-4">
          <InfoTip text={GLOSSARY.intradayContext} />
          <span className={`dot ${stale || isDemo ? 'idle' : 'live'}`} />
          <Badge kind={stale ? 'warn' : isDemo ? 'neutral' : 'ok'}>
            {stale ? 'STALE' : isDemo ? 'DEMO' : 'LIVE'}
          </Badge>
        </span>
      }
    >
      <div className="stack-12">
        <div className="muted mono" style={{ fontSize: 10 }}>
          source: {sourceLabel}
          {ctx.tick_count != null && <> · {ctx.tick_count} ticks</>}
          {ctx.last_update != null && <> · updated {fmt.ago(ctx.last_update)}</>}
        </div>

        {isDemo && (
          <div className="ascii" style={{ fontSize: 10 }}>
            // synthetic intraday window — demo mode has no live exchange feed
          </div>
        )}

        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
          <Kpi
            label="vs Last Close"
            value={fmt.signedPct(divergence)}
            tip={GLOSSARY.priceDivergence}
          />
          <Kpi
            label="vs VWAP"
            value={fmt.signedPct(vwapDev)}
            tip={GLOSSARY.vwapDeviation}
          />
          <Kpi
            label="Order Flow"
            value={fmt.signed(pressure, 4)}
            sub={pressure > 0.15 ? 'bid-heavy' : pressure < -0.15 ? 'ask-heavy' : 'balanced'}
            tip={GLOSSARY.orderFlowPressure}
          />
          <Kpi
            label="Trade Intensity"
            value={ctx.trade_intensity != null ? `${ctx.trade_intensity}/min` : '—'}
            tip={GLOSSARY.tradeIntensity}
          />
        </div>

        <div className="divider" />
        <div className="lbl-strong">
          Ensemble nudge <InfoTip text={GLOSSARY.intradayNudge} />
        </div>
        <ContribBars
          items={[
            { name: 'order flow', value: components.order_flow_score },
            { name: 'intraday', value: components.intraday_score },
          ]}
        />
        {hasNudge && (
          <div className="muted mono" style={{ fontSize: 10 }}>
            daily {fmt.signed(dailyScore, 3)} + nudge {fmt.signed(nudge, 3)} = {fmt.signed(combinedScore, 3)}
          </div>
        )}

        {stale && <Warning kind="warn" text={GLOSSARY.intradayStale} />}
        {ctx.warnings.length > 0 && (
          <ul style={{ margin: 0, paddingLeft: 16 }} className="dim">
            {ctx.warnings.map((w, i) => (
              <li key={i} style={{ fontSize: 11, lineHeight: 1.5, fontFamily: 'var(--font-mono)' }}>
                {w}
              </li>
            ))}
          </ul>
        )}

        <div className="ascii" style={{ fontSize: 10 }}>
          // separate from ARIMA/VaR — daily models stay on daily data
        </div>
      </div>
    </Panel>
  )
}

// ─── 11 — Analyst summary (LLM) ───────────────────────────────────────────────

export function LLMPanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('11')
  const l = data.llm_explanation
  if (!l) return null

  const isString = typeof l === 'string'
  const obj = isString ? null : l
  const signal = data.indicator_vote?.signal ?? data.ensemble_signal
  const tone =
    signal === 'BULLISH' ? 'up' : signal === 'BEARISH' ? 'down' : 'neutral'

  return (
    <Panel
      idx="11"
      title={p.title}
      meta={data.data_lineage?.llm_provider ?? 'analyst'}
      right={<Badge kind="warn">NOT ADVICE</Badge>}
    >
      {isString ? (
        <div style={{ fontSize: 13, lineHeight: 1.65, color: 'var(--ink-dim)' }}>{l}</div>
      ) : (
        <div className="stack-12">
          {obj?.headline && (
            <div
              style={{
                fontSize: 15,
                fontWeight: 600,
                lineHeight: 1.45,
                color: 'var(--ink)',
                fontFamily: 'var(--font-sans, system-ui, sans-serif)',
              }}
            >
              {obj.headline}
            </div>
          )}
          {obj?.summary && (
            <div style={{ borderLeft: '2px solid var(--accent)', paddingLeft: 12 }}>
              <div className="lbl-strong" style={{ marginBottom: 6 }}>
                {copy.llmSection('summary')}
                <InfoTip text={copy.llmSection('summaryTip')} />
              </div>
              <div style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--ink-dim)' }}>
                {obj.summary}
              </div>
              {signal && (
                <div style={{ marginTop: 8, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--ink-mute)' }}>
                  {copy.llmSection('modelLean')}:{' '}
                  <span className={tone === 'up' ? 'up' : tone === 'down' ? 'down' : ''}>
                    {copy.badge('signal', signal)}
                  </span>
                  {' · '}
                  {copy.llmSection('trustLabel')}: {copy.badge('confidence', data.confidence?.label)}
                </div>
              )}
            </div>
          )}
          {(obj?.risk_notes ?? []).length > 0 && (
            <div>
              <div className="lbl-strong" style={{ marginBottom: 6 }}>
                {copy.llmSection('risks')}
                <InfoTip text={copy.llmSection('risksTip')} />
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--ink-dim)' }}>
                {(obj?.risk_notes ?? []).map((r, i) => (
                  <li key={i} style={{ fontSize: 12.5, lineHeight: 1.65, marginBottom: 4 }}>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {obj?.confidence_explanation && (
            <div>
              <div className="lbl-strong" style={{ marginBottom: 4 }}>
                {copy.llmSection('trust')}
                <InfoTip text={GLOSSARY.confidenceScore} />
              </div>
              <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--ink-dim)' }}>
                {obj.confidence_explanation}
              </div>
            </div>
          )}
          <div className="warning" style={{ border: '1px solid var(--line)' }}>
            <span className="icon">▲</span>
            <div className="body">
              {obj?.disclaimer ?? 'This output is analytical and not investment advice.'}
            </div>
          </div>
        </div>
      )}
    </Panel>
  )
}

// ─── 12 — Data lineage ────────────────────────────────────────────────────────

export function LineagePanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('12')
  const l = data.data_lineage ?? {}
  return (
    <Panel idx="12" title={p.title} meta={p.meta}>
      <dl className="kv">
        <dt>data_source_mode</dt>
        <dd>{data.data_source_mode ?? '—'}</dd>
        <dt>historical_source</dt>
        <dd>{l.historical_source ?? '—'}</dd>
        <dt>live_source</dt>
        <dd>{l.live_source ?? '—'}</dd>
        <dt>order_book_source</dt>
        <dd>{l.order_book_source ?? '—'}</dd>
        <dt>intraday_context</dt>
        <dd>{l.intraday_context_source ?? '—'}</dd>
        <dt>copy_mode</dt>
        <dd>{l.copy_mode ?? data.copy_mode ?? '—'}</dd>
        <dt>llm_provider</dt>
        <dd>{l.llm_provider ?? '—'}</dd>
        <dt>historical_rows</dt>
        <dd>
          {l.historical_rows ?? '—'} <span className="faint">/ ~240 via companyChartDataByStock</span>
        </dd>
        <dt>tick_rows</dt>
        <dd>{l.tick_rows ?? '—'}</dd>
        <dt>last_historical</dt>
        <dd>{fmt.time(l.last_historical_timestamp)}</dd>
        <dt>last_tick</dt>
        <dd>{fmt.time(l.last_tick_timestamp)}</dd>
      </dl>
      <div className="warning info" style={{ marginTop: 10, border: '1px solid var(--line)' }}>
        <span className="icon">●</span>
        <div className="body">
          CSE REST provides ~240 daily OHLCV rows per symbol (period=5 chart endpoint) which feed
          ARIMA/VaR/trend. Order book and live microstructure are a separate intraday context layer
          — a lightly weighted ensemble nudge plus quality flags, never mixed into the daily models.
          When the WebSocket tick store has live ticks for a symbol, it is preferred over the REST
          tradeSummary proxy. Demo checkbox forces in-memory synthetic data for offline runs; in demo
          mode a synthetic intraday window (DEMO_INTRADAY) is generated from the last daily bar so the
          intraday layer is still exercised and labeled honestly as synthetic.
        </div>
      </div>
    </Panel>
  )
}

// ─── 13 — Quality flags ───────────────────────────────────────────────────────

export function QualityFlagsPanel({ data }: { data: ArgusAnalysis }) {
  const copy = useCopyMode()
  const p = copy.panel('13')
  const q = data.quality_flags ?? {}
  const ns = data.node_status ?? {}

  const flags: [string, boolean | undefined][] = [
    ['has_missing_values', q.has_missing_values],
    ['has_null_open_prices', q.has_null_open_prices],
    ['used_open_price_proxy', q.used_open_price_proxy],
    ['is_stale', q.is_stale],
    ['order_book_snapshot', q.order_book_snapshot],
    ['intraday_context_available', q.intraday_context_available],
    ['low_liquidity_warning', q.low_liquidity_warning],
    ['api_latency_warning', q.api_latency_warning],
    ['model_warning', q.model_warning],
  ]

  return (
    <Panel idx="13" title={p.title} meta={p.meta}>
      <div className="stack-4">
        {flags.map(([k, v]) => (
          <div
            key={k}
            className="between"
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}
          >
            <span className="muted">{k}</span>
            <span style={{ color: v ? 'var(--warn)' : 'var(--ink-faint)' }}>
              {v ? '▲ TRUE' : '· false'}
            </span>
          </div>
        ))}
      </div>
      {Object.keys(ns).length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="lbl-strong" style={{ marginBottom: 6 }}>
            Node Status
          </div>
          <div className="stack-4">
            {Object.entries(ns).map(([k, v]) => (
              <div
                key={k}
                className="between"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}
              >
                <span className="muted">{k}</span>
                <Badge kind={v.status === 'ok' ? 'ok' : 'warn'}>{v.status}</Badge>
              </div>
            ))}
          </div>
        </div>
      )}
      {(q.warnings ?? []).length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div className="lbl-strong" style={{ marginBottom: 6 }}>
            Warnings
          </div>
          <div className="warning-list">
            {(q.warnings ?? []).map((w, i) => (
              <Warning key={i} text={w} />
            ))}
          </div>
        </div>
      )}
    </Panel>
  )
}

// ─── Methodology drawer ───────────────────────────────────────────────────────

export function MethodologyDrawer({ onClose }: { onClose: () => void }) {
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2>Methodology</h2>
          <span className="lbl muted">— statistical framework &amp; honest limitations</span>
          <span style={{ flex: 1 }} />
          <button type="button" className="badge" onClick={onClose}>
            ESC ✕
          </button>
        </div>
        <div className="drawer-body">
          <h3>01 · Data ingestion</h3>
          <p>
            Historical daily bars are pulled from the <code>CSE_REST</code> endpoint, capped at
            approximately <code>120–240</code> rows per symbol. When the shared WebSocket tick store
            has live <code>DAYTRADE</code> ticks for a symbol, analysis prefers them over the REST
            trade-summary proxy and lineage reports <code>CSE_WEBSOCKET_DAYTRADE</code>; otherwise it
            falls back to <code>CSE_REST_TRADE_SUMMARY</code>. Order-book snapshots come from the REST
            order-book endpoint. Live ticks and order book feed a separate <strong>intraday context
            layer</strong> — they never enter the daily models.
          </p>
          <h3>02 · ARIMA selection</h3>
          <p>
            Candidate orders <code>(0,1,0)</code> through <code>(2,1,2)</code> are fitted and ranked
            by <code>AICc</code>. The selected model is evaluated against a naive last-value
            baseline. If the model does not beat naive, the UI surfaces a hard{' '}
            <strong>FAILS NAIVE</strong> badge.
          </p>
          <h3>03 · Volatility &amp; risk</h3>
          <p>
            EWMA volatility (<code>λ=0.94</code>, RiskMetrics convention) and Historical VaR at 95%
            and 99% empirically. Parkinson high–low volatility is shown as a sanity check on
            intraday range. When empirical Historical VaR exceeds parametric EWMA VaR, the panel
            calls this out — it indicates heavier tails than a normal assumption.
          </p>
          <h3>04 · Anomalies</h3>
          <p>
            Classical Z-score alongside the <strong>modified Z-score</strong> based on Median
            Absolute Deviation (MAD). MAD is more robust on thin CSE volumes where one extreme
            print can shift the sample mean. Disagreement between measures is surfaced.
          </p>
          <h3>05 · Ensemble signal</h3>
          <p>
            Weighted combination of trend, volatility, liquidity, and anomaly components from the
            daily models. Score range is −1 to +1. A separate <strong>intraday context layer</strong>
            then adds a small, staleness-damped nudge (capped at ±0.20) from order-flow pressure and
            live price vs VWAP/close divergence — shown as <code>order flow</code> and{' '}
            <code>intraday</code> contributions in Panel 02. <code>math_results.indicator_vote</code>{' '}
            stays the pure daily ensemble; the top-level vote is the combined view.{' '}
            <code>NEUTRAL</code> is a legitimate, common outcome. This is not a buy/sell signal.
          </p>
          <h3>06 · Confidence</h3>
          <p>
            Confidence (0–1) measures trust in the analysis, not probability of profit. Computed as{' '}
            <code>1 − Σ penalties</code> across insufficient data rows, model underperformance,
            ARIMA diagnostics, missing values, thin liquidity, and flat high-low ratio. The intraday
            context layer adds penalties for material price divergence from the last daily close and
            for stale live snapshots.
          </p>
          <h3>07 · Disclaimer</h3>
          <p>
            <strong>
              Project Argus is an analytical and decision-support system. Outputs are not investment
              advice.
            </strong>{' '}
            Authored as a BSc final-year research artifact.
          </p>
        </div>
      </div>
    </div>
  )
}

// ─── Raw JSON drawer ──────────────────────────────────────────────────────────

export function RawJsonDrawer({
  data,
  latency,
  onClose,
}: {
  data?: ArgusAnalysis
  latency?: number
  onClose: () => void
}) {
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer drawer-wide" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2>Raw Response · /api/analyze</h2>
          <span className="lbl muted">— developer view</span>
          <span style={{ flex: 1 }} />
          <button type="button" className="badge" onClick={onClose}>
            ESC ✕
          </button>
        </div>
        <div className="drawer-body">
          {data && (
            <>
              <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 12 }}>
                <Kpi label="HTTP" value="200 OK" tone="up" />
                <Kpi label="Latency" value={latency != null ? `${latency}ms` : '—'} />
                <Kpi label="processing_time" value={`${data.processing_time}s`} />
                <Kpi
                  label="overall_health"
                  value={data.math_results?.overall_health ?? '—'}
                  tone="up"
                />
              </div>
              <JsonView obj={data} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
