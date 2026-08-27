import type { ReactNode } from 'react'

// ─── Panel chrome ────────────────────────────────────────────────────────────

export function Panel({
  idx,
  title,
  meta,
  right,
  children,
  flush = false,
  tight = false,
}: {
  idx?: string
  title: string
  meta?: string
  right?: ReactNode
  children: ReactNode
  flush?: boolean
  tight?: boolean
}) {
  return (
    <section className="panel">
      <header className="panel-head">
        {idx && <span className="index">{idx}</span>}
        <span className="title">{title}</span>
        {meta && <span className="meta">— {meta}</span>}
        <span className="spacer" />
        {right}
      </header>
      <div className={`panel-body${flush ? ' flush' : ''}${tight ? ' tight' : ''}`}>
        {children}
      </div>
    </section>
  )
}

// ─── KPI metric cell ──────────────────────────────────────────────────────────

export function Kpi({
  label,
  value,
  sub,
  tone,
  large,
  tip,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: 'up' | 'down' | 'neutral' | 'warn' | ''
  large?: boolean
  tip?: string
}) {
  return (
    <div className="kpi">
      <div className="lbl">
        {label}
        {tip ? <InfoTip text={tip} /> : null}
      </div>
      <div className={`val${large ? ' lg' : ''}${tone ? ` ${tone}` : ''}`}>{value}</div>
      {sub != null && <div className="sub">{sub}</div>}
    </div>
  )
}

// ─── Info tooltip (hover for plain-language help) ─────────────────────────────

export function InfoTip({ text }: { text: string }) {
  return (
    <span className="info-tip" tabIndex={0} role="note" aria-label={text}>
      <span className="info-tip-icon" aria-hidden="true">
        i
      </span>
      <span className="info-tip-body">{text}</span>
    </span>
  )
}

// ─── Score meter (−1 .. +1) ───────────────────────────────────────────────────

export function ScoreMeter({
  value,
  scale = ['BEARISH', 'NEUTRAL', 'BULLISH'],
}: {
  value: number
  scale?: [string, string, string]
}) {
  const v = Math.max(-1, Math.min(1, value))
  const pct = ((v + 1) / 2) * 100
  const fillLeft = v < 0 ? pct : 50
  const fillWidth = v < 0 ? 50 - pct : pct - 50
  const tone = v > 0.05 ? 'up' : v < -0.05 ? 'down' : 'neutral'
  return (
    <div className="meter">
      <div className="meter-scale">
        <span className="l">← {scale[0]}</span>
        <span className="r">{scale[2]} →</span>
      </div>
      <div className="meter-track">
        <span className="midline" />
        <span
          className={`meter-fill ${tone}`}
          style={{ left: `${fillLeft}%`, width: `${fillWidth}%` }}
        />
        <span className="meter-marker" style={{ left: `calc(${pct}% - 1px)` }} />
      </div>
      <div className="meter-ticks">
        <span>−1.00</span>
        <span>−0.50</span>
        <span>0.00</span>
        <span>+0.50</span>
        <span>+1.00</span>
      </div>
    </div>
  )
}

// ─── Contribution bars ────────────────────────────────────────────────────────

export function ContribBars({
  items,
}: {
  items: Array<{ name: string; value: number | null | undefined }>
}) {
  return (
    <div className="contrib">
      {items.map((it) => {
        const v = Math.max(-1, Math.min(1, it.value ?? 0))
        const pct = Math.abs(v) * 50
        const tone = v >= 0 ? 'up' : 'down'
        const left = v < 0 ? 50 - pct : 50
        return (
          <div className="contrib-row" key={it.name}>
            <span className="name">{it.name}</span>
            <span className="contrib-bar">
              <span className="mid" />
              <span
                className={`fill ${tone}`}
                style={{ left: `${left}%`, width: `${pct}%` }}
              />
            </span>
            <span className={`val ${tone}`}>
              {v > 0 ? '+' : ''}
              {v.toFixed(2)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ─── Semicircle confidence gauge ──────────────────────────────────────────────

export function ConfidenceGauge({ value, label }: { value: number; label: string }) {
  const v = Math.max(0, Math.min(1, value))
  const r = 60
  const cx = 70
  const cy = 70
  const startAngle = Math.PI
  const endAngle = Math.PI * 2
  const angle = startAngle + v * (endAngle - startAngle)

  const arc = (a0: number, a1: number, sw: number, color: string) => {
    const large = a1 - a0 > Math.PI ? 1 : 0
    const x0 = cx + r * Math.cos(a0)
    const y0 = cy + r * Math.sin(a0)
    const x1 = cx + r * Math.cos(a1)
    const y1 = cy + r * Math.sin(a1)
    return (
      <path
        d={`M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`}
        stroke={color}
        strokeWidth={sw}
        fill="none"
        strokeLinecap="butt"
      />
    )
  }

  const color = v < 0.5 ? '#e5484d' : v < 0.7 ? '#f5a623' : '#4ec9a4'

  return (
    <div className="gauge">
      <svg className="gauge-svg" viewBox="0 0 140 90">
        {arc(startAngle, endAngle, 6, '#1c222c')}
        {arc(startAngle, angle, 6, color)}
        {[0, 0.25, 0.5, 0.75, 1].map((t, i) => {
          const a = startAngle + t * Math.PI
          const x0 = cx + (r - 4) * Math.cos(a)
          const y0 = cy + (r - 4) * Math.sin(a)
          const x1 = cx + (r + 4) * Math.cos(a)
          const y1 = cy + (r + 4) * Math.sin(a)
          return <line key={i} x1={x0} y1={y0} x2={x1} y2={y1} stroke="#475064" strokeWidth="1" />
        })}
        <text x="10" y="84" fontFamily="JetBrains Mono" fontSize="8" fill="#6b7484">0.00</text>
        <text x="123" y="84" fontFamily="JetBrains Mono" fontSize="8" fill="#6b7484">1.00</text>
      </svg>
      <div className="gauge-label">
        <span className="num" style={{ color }}>{value.toFixed(2)}</span>
        <span className="denom"> / 1.00</span>
        <div className="badge" style={{ color, borderColor: color + '55', marginTop: 4 }}>
          {label}
        </div>
      </div>
    </div>
  )
}

// ─── Badges ───────────────────────────────────────────────────────────────────

export function Badge({
  kind = '',
  children,
  dot,
}: {
  kind?: 'ok' | 'warn' | 'err' | 'info' | 'accent' | 'bull' | 'bear' | 'neutral' | ''
  children: ReactNode
  dot?: boolean
}) {
  return (
    <span className={`badge${kind ? ` ${kind}` : ''}`}>
      {dot && (
        <span
          className={`dot ${kind === 'ok' || kind === 'bull' ? 'ok' : kind === 'warn' ? 'warn' : kind === 'err' || kind === 'bear' ? 'err' : 'idle'}`}
        />
      )}
      {children}
    </span>
  )
}

export function SignalBadge({ signal, label }: { signal?: string; label?: string }) {
  const map: Record<string, 'bull' | 'bear' | 'neutral' | 'err'> = {
    BULLISH: 'bull',
    BEARISH: 'bear',
    NEUTRAL: 'neutral',
    ERROR: 'err',
  }
  const kind = signal ? (map[signal] ?? '') : ''
  return (
    <Badge kind={kind as 'bull' | 'bear' | 'neutral' | 'err' | ''}>{label ?? signal ?? '—'}</Badge>
  )
}

// ─── Sparkline ────────────────────────────────────────────────────────────────

export function Sparkline({
  values,
  height = 38,
  stroke = 'var(--accent)',
}: {
  values: number[]
  height?: number
  stroke?: string
}) {
  if (!values || values.length === 0)
    return <svg className="spark" viewBox={`0 0 100 ${height}`} />

  if (values.length === 1) {
    const y = height / 2
    return (
      <svg className="spark" viewBox={`0 0 100 ${height}`}>
        <circle cx={50} cy={y} r="2" fill={stroke} />
      </svg>
    )
  }

  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const W = 100

  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W
    const y = height - ((v - min) / span) * (height - 4) - 2
    return [x, y] as [number, number]
  })

  const d = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`).join(' ')
  const lastY = pts[pts.length - 1][1]
  const fillD = `${d} L ${W} ${height} L 0 ${height} Z`

  return (
    <svg
      className="spark"
      viewBox={`0 0 ${W} ${height}`}
      preserveAspectRatio="none"
    >
      <path d={fillD} fill={stroke} opacity="0.08" />
      <path d={d} fill="none" stroke={stroke} strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <circle cx={W} cy={lastY} r="1.6" fill={stroke} />
    </svg>
  )
}

// ─── Warning row ──────────────────────────────────────────────────────────────

export function Warning({
  kind = 'warn',
  text,
  source,
}: {
  kind?: 'warn' | 'err' | 'info'
  text: string
  source?: string
}) {
  const icon = kind === 'err' ? '■' : kind === 'info' ? '●' : '▲'
  return (
    <div className={`warning${kind === 'err' ? ' err' : kind === 'info' ? ' info' : ''}`}>
      <span className="icon">{icon}</span>
      <div>
        <div className="body">{text}</div>
        {source && <div className="src">{source}</div>}
      </div>
    </div>
  )
}

// ─── JSON pretty-print ────────────────────────────────────────────────────────

export function JsonView({ obj }: { obj: unknown }) {
  const json = JSON.stringify(obj, null, 2)
  const html = json
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"([^"\\]*?)":/g, '<span class="k">"$1"</span>:')
    .replace(/: "([^"\\]*)"/g, ': <span class="s">"$1"</span>')
    .replace(/: (-?\d+\.?\d*)/g, ': <span class="n">$1</span>')
    .replace(/: (true|false)/g, ': <span class="b">$1</span>')
    .replace(/: (null)/g, ': <span class="null">$1</span>')
  // biome-ignore lint/security/noDangerouslySetInnerHtml: controlled JSON syntax highlighting
  return <pre className="json" dangerouslySetInnerHTML={{ __html: html }} />
}
