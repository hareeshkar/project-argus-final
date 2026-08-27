import type { CopyMode } from './mode'

export type RiskKpiKey =
  | 'dailyVol'
  | 'var95'
  | 'hist95'
  | 'hist99'
  | 'parkinson'
  | 'percentile'
  | 'drawdown'
  | 'maxDrawdown'

export type RiskKpiCopy = { label: string; sub: string; tip: string }

const SIMPLE: Record<RiskKpiKey, RiskKpiCopy> = {
  dailyVol: {
    label: 'Daily Volatility',
    sub: 'typical daily move',
    tip: 'How much the share price typically moves in one day. Higher means more ups and downs.',
  },
  var95: {
    label: 'Bad Day Loss (95%)',
    sub: 'model estimate',
    tip: 'Estimated worst single-day loss on a normal-ish day — about 1 day in 20 could be worse than this.',
  },
  hist95: {
    label: 'Worst Day (95%)',
    sub: 'from history',
    tip: 'Worst day seen in recent history (95% of days were better). Uses actual past moves, not a formula.',
  },
  hist99: {
    label: 'Very Bad Day (99%)',
    sub: 'from history',
    tip: 'Very bad day from history — only about 1 day in 100 was worse.',
  },
  parkinson: {
    label: 'Range Volatility',
    sub: 'high–low based',
    tip: 'Volatility estimated from each day’s high–low range, not just the closing price.',
  },
  percentile: {
    label: 'Vol vs History',
    sub: 'for this stock',
    tip: 'Today’s volatility compared with this stock’s own past — high means unusually jumpy lately.',
  },
  drawdown: {
    label: 'Drop from Peak',
    sub: 'current fall',
    tip: 'How far the price has fallen from its recent peak, shown as a percentage.',
  },
  maxDrawdown: {
    label: 'Largest Drop',
    sub: 'in data window',
    tip: 'Largest peak-to-trough drop in the data window we have.',
  },
}

const EXPERIENCE: Record<RiskKpiKey, RiskKpiCopy> = {
  dailyVol: {
    label: 'Daily Volatility (EWMA σ)',
    sub: 'σ daily',
    tip: 'EWMA daily volatility σ — exponentially weighted standard deviation of returns.',
  },
  var95: {
    label: 'EWMA VaR 95',
    sub: 'parametric tail',
    tip: 'EWMA Value-at-Risk at 95% — parametric one-day loss estimate.',
  },
  hist95: {
    label: 'Historical VaR 95',
    sub: 'empirical tail',
    tip: 'Historical simulation VaR 95 — worst day in recent empirical window.',
  },
  hist99: {
    label: 'Historical VaR 99',
    sub: 'empirical tail',
    tip: 'Historical simulation VaR 99 — 1-in-100 tail day from history.',
  },
  parkinson: {
    label: 'Parkinson Volatility',
    sub: 'high–low estimator',
    tip: 'Parkinson range-based volatility estimator using daily high–low.',
  },
  percentile: {
    label: 'σ Percentile',
    sub: 'symbol-relative',
    tip: 'Current σ percentile vs this symbol’s own historical distribution.',
  },
  drawdown: {
    label: 'Current Drawdown',
    sub: 'peak-to-trough',
    tip: 'Current drawdown from rolling peak close.',
  },
  maxDrawdown: {
    label: 'Max Drawdown',
    sub: 'window max',
    tip: 'Maximum peak-to-trough drawdown in the analysis window.',
  },
}

export function riskKpi(mode: CopyMode, key: RiskKpiKey): RiskKpiCopy {
  return mode === 'experience' ? EXPERIENCE[key] : SIMPLE[key]
}

export function riskPanelMeta(mode: CopyMode): string {
  return mode === 'experience'
    ? 'EWMA · Historical VaR · Parkinson · Drawdown'
    : 'Daily moves · bad days · drawdown'
}

export function riskBarLabels(mode: CopyMode): string[] {
  if (mode === 'experience') {
    return ['EWMA VaR 95', 'Hist VaR 95', 'Hist VaR 99', 'Max DD']
  }
  return ['Bad Day Loss (95%)', 'Worst Day (95%)', 'Very Bad Day (99%)', 'Largest Drop']
}

export function riskTailWarning(mode: CopyMode): { text: string; source: string } {
  if (mode === 'experience') {
    return {
      text: 'Empirical historical VaR exceeds parametric EWMA VaR — tail risk is heavier than normal-distribution assumption implies.',
      source: 'volatility.historical_var_95_pct > volatility.var_95_pct',
    }
  }
  return {
    text: 'Past worst days were worse than the model expects — tail risk may be heavier than the estimate suggests.',
    source: 'historical tail > model tail',
  }
}

export function riskFootnote(mode: CopyMode): string {
  return mode === 'experience'
    ? '// σ percentile is relative to this stock\'s own historical distribution, not market-wide'
    : '// volatility percentile compares this stock to its own past, not the whole market'
}
