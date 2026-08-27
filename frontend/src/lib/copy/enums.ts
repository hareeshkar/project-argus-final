import type { CopyMode } from './mode'

export function translateEnum(mode: CopyMode, category: string, value?: string | null): string {
  const token = (value ?? '—').toUpperCase()
  if (mode === 'experience') return token

  if (category === 'signal') {
    return (
      {
        BULLISH: 'Prices lean up',
        BEARISH: 'Prices lean down',
        NEUTRAL: 'Mixed / no clear direction',
      }[token] ?? token
    )
  }
  if (category === 'confidence') {
    return (
      {
        HIGH: 'High trust',
        MODERATE: 'Moderate trust',
        LOW: 'Low trust',
      }[token] ?? token
    )
  }
  if (category === 'risk') {
    return (
      {
        LOW: 'Low risk',
        MODERATE: 'Moderate risk',
        HIGH: 'High risk',
      }[token] ?? token
    )
  }
  if (category === 'trend') {
    return (
      {
        UP: 'Trending up',
        DOWN: 'Trending down',
        FLAT: 'Flat / sideways',
        SIDEWAYS: 'Sideways',
      }[token] ?? token
    )
  }
  if (category === 'volRegime') {
    return (
      {
        HIGH: 'High volatility',
        LOW: 'Low volatility',
        NORMAL: 'Normal volatility',
      }[token] ?? token
    )
  }
  if (category === 'liquidity') {
    return (
      {
        THIN: 'Thin trading',
        LIQUID: 'Healthy volume',
      }[token] ?? token
    )
  }
  return token
}

export function displayBadge(mode: CopyMode, category: string, value?: string | null): string {
  if (mode === 'experience') return (value ?? '—').toUpperCase()
  return translateEnum(mode, category, value)
}
