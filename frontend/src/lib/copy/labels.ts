import type { CopyMode } from './mode'

type PanelCopy = { title: string; meta?: string }

export const PANELS: Record<CopyMode, Record<string, PanelCopy>> = {
  simple: {
    '01': { title: 'Snapshot' },
    '02': { title: 'Overall lean', meta: 'down · flat · up' },
    '03': { title: 'Trust & data quality', meta: '0.00–1.00 trust gauge' },
    '04': { title: 'Price forecast', meta: 'next few days' },
    '05': { title: 'Risk at a glance' },
    '06': { title: 'Price direction', meta: 'recent trend' },
    '07': { title: 'Unusual moves', meta: 'price & volume checks' },
    '08': { title: 'Market conditions', meta: 'trend · volatility · volume' },
    '09': { title: 'Buy vs sell pressure', meta: 'order book snapshot' },
    '10': { title: 'Live price', meta: 'CSE trade summary · 1s' },
    '11': { title: 'Plain-English summary' },
    '12': { title: 'Where data came from', meta: 'sources & row counts' },
    '13': { title: 'Data quality checks', meta: 'flags & warnings' },
    '14': { title: 'Live read on the stock', meta: 'order flow · live ticks' },
  },
  experience: {
    '01': { title: 'Analysis Overview' },
    '02': { title: 'Ensemble Signal', meta: '−1 bearish · 0 neutral · +1 bullish' },
    '03': { title: 'Confidence & Data Quality', meta: '0.00–1.00 trust gauge' },
    '04': { title: 'Forecast & ARIMA Diagnostics' },
    '05': { title: 'Risk Metrics' },
    '06': { title: 'Trend / OLS Regression' },
    '07': { title: 'Anomaly Detection', meta: 'Z-score · MAD lookback' },
    '08': { title: 'Market Regime', meta: 'trend · vol · liquidity' },
    '09': { title: 'Order Book Pressure', meta: 'aggregate REST snapshot' },
    '10': { title: 'Live Price', meta: 'CSE trade summary · 1s' },
    '11': { title: 'Analyst Summary' },
    '12': { title: 'Data Lineage', meta: 'provenance for thesis audit' },
    '13': { title: 'Quality Flags', meta: 'schema integrity' },
    '14': { title: 'Intraday Context', meta: 'order flow · VWAP · staleness' },
  },
}

export const HERO: Record<CopyMode, Record<string, string>> = {
  simple: {
    confidence: 'How much to trust this',
    confidenceCompanion: 'Trust in this analysis, not probability of profit.',
    signal: 'Overall lean',
    price: 'Latest price (LKR)',
    priceCompanion: 'At analysis time · last daily close from CSE',
    pipeline: 'Run time',
  },
  experience: {
    confidence: 'Confidence Score',
    confidenceCompanion: 'Trust in this analysis, not probability of profit.',
    signal: 'Ensemble Signal',
    price: 'Latest Price (LKR)',
    priceCompanion: 'at analysis time · last daily close from CSE REST',
    pipeline: 'Pipeline',
  },
}

export const TOPBAR: Record<CopyMode, Record<string, string>> = {
  simple: {
    signal: 'Lean',
    dataMode: 'Data source',
  },
  experience: {
    signal: 'Signal',
    dataMode: 'Data Mode',
  },
}

export const LLM_SECTIONS: Record<CopyMode, Record<string, string>> = {
  simple: {
    summary: 'What the data says',
    summaryTip: 'A plain-language read of the computed metrics — not a buy or sell call.',
    risks: 'Things to watch',
    risksTip: 'Caveats and risks pulled from the data — not predictions.',
    trust: 'How much to trust this',
    modelLean: 'Overall lean',
    trustLabel: 'Trust',
  },
  experience: {
    summary: 'Summary',
    summaryTip: 'Technical read of computed metrics — not a buy or sell call.',
    risks: 'Risk notes',
    risksTip: 'Model and data caveats from the evidence block.',
    trust: 'Confidence rationale',
    modelLean: 'Signal',
    trustLabel: 'Confidence',
  },
}

export const PIPELINE_STAGES: Record<CopyMode, Record<string, string>> = {
  simple: {
    parse: 'Finding the stock symbol',
    fetch: 'Loading market data',
    models: 'Running the numbers',
    confidence: 'Checking how much to trust this',
    narrative: 'Writing a plain summary',
  },
  experience: {
    parse: 'Parsing symbol from query',
    fetch: 'Fetching CSE REST + microstructure proxy',
    models: 'Running statistical models',
    confidence: 'Computing confidence score',
    narrative: 'Generating analyst summary',
  },
}

export const SCORE_METER: Record<CopyMode, [string, string, string]> = {
  simple: ['Down', 'Flat', 'Up'],
  experience: ['BEARISH', 'NEUTRAL', 'BULLISH'],
}

export function panelCopy(mode: CopyMode, idx: string): PanelCopy {
  return PANELS[mode][idx] ?? PANELS.experience[idx] ?? { title: idx }
}
