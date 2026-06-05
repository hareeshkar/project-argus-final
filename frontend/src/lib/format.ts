export const fmt = {
  price(n?: number | null): string {
    if (n == null) return '—'
    return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  },
  pct(n?: number | null, d = 2): string {
    if (n == null) return '—'
    return `${n.toFixed(d)}%`
  },
  score(n?: number | null): string {
    if (n == null) return '—'
    return n.toFixed(2)
  },
  signed(n?: number | null, d = 2): string {
    if (n == null) return '—'
    return `${n > 0 ? '+' : ''}${n.toFixed(d)}`
  },
  signedPct(n?: number | null, d = 2): string {
    if (n == null) return '—'
    return `${n > 0 ? '+' : ''}${n.toFixed(d)}%`
  },
  compact(n?: number | null): string {
    if (n == null) return '—'
    const abs = Math.abs(n)
    if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`
    if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`
    if (abs >= 1e3) return `${(n / 1e3).toFixed(1)}K`
    return n.toString()
  },
  time(iso?: string | number | null): string {
    if (iso == null) return '—'
    const d =
      typeof iso === 'number'
        ? new Date(iso * (iso < 1e12 ? 1000 : 1))
        : new Date(iso)
    return Number.isNaN(d.getTime())
      ? String(iso)
      : d.toISOString().replace('T', ' ').replace(/\.\d+Z$/, 'Z')
  },
  hhmmss(ms?: number | null): string {
    if (ms == null) return '—'
    const d = new Date(ms)
    return d.toISOString().slice(11, 19)
  },
  ago(iso?: string | number | null): string {
    if (iso == null) return '—'
    const t =
      typeof iso === 'number'
        ? iso * (iso < 1e12 ? 1000 : 1)
        : Date.parse(iso as string)
    const s = Math.floor((Date.now() - t) / 1000)
    if (s < 60) return `${s}s ago`
    if (s < 3600) return `${Math.floor(s / 60)}m ago`
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`
    return `${Math.floor(s / 86400)}d ago`
  },
  number(n?: number | null, d = 2): string {
    if (n == null) return '—'
    return n.toFixed(d)
  },
}
