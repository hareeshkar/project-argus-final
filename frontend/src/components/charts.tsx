import type { ArgusAnalysis } from '../api/schemas'

// ─── SVG Forecast Chart (history + forecast + CI band) ───────────────────────

export function ForecastChart({
  history,
  forecast,
  lower,
  upper,
}: {
  history: number[]
  forecast: number[]
  lower: number[]
  upper: number[]
}) {
  const allLow = [...history, ...lower]
  const allHigh = [...history, ...upper, ...forecast]
  const min = Math.min(...allLow)
  const max = Math.max(...allHigh)
  const span = max - min || 1

  const W = 460
  const H = 160
  const PAD_L = 36
  const PAD_R = 12
  const PAD_T = 10
  const PAD_B = 22
  const innerW = W - PAD_L - PAD_R
  const innerH = H - PAD_T - PAD_B
  const N = history.length + forecast.length

  const xAt = (i: number) => PAD_L + (i / (N - 1)) * innerW
  const yAt = (v: number) => PAD_T + innerH - ((v - min) / span) * innerH

  const histPath = history
    .map((v, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`)
    .join(' ')

  const lastIdx = history.length - 1
  const fcStart = history.length - 1
  const fcPath = [history[history.length - 1], ...forecast]
    .map((v, i) => `${i === 0 ? 'M' : 'L'} ${xAt(fcStart + i).toFixed(1)} ${yAt(v).toFixed(1)}`)
    .join(' ')

  const bandUp = upper.map(
    (v, i) => `${xAt(history.length + i).toFixed(1)},${yAt(v).toFixed(1)}`,
  )
  const bandLo = lower
    .map((v, i) => `${xAt(history.length + i).toFixed(1)},${yAt(v).toFixed(1)}`)
    .reverse()
  const anchorX = xAt(lastIdx).toFixed(1)
  const anchorY = yAt(history[lastIdx]).toFixed(1)
  const bandPoly = [`${anchorX},${anchorY}`, ...bandUp, ...bandLo].join(' ')

  const gridY = [0, 0.25, 0.5, 0.75, 1].map((t) => PAD_T + t * innerH)
  const gridV = [0, 0.25, 0.5, 0.75, 1].map((t) => max - t * span)

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      preserveAspectRatio="none"
      style={{ display: 'block' }}
    >
      {gridY.map((y, i) => (
        <g key={i}>
          <line x1={PAD_L} y1={y} x2={W - PAD_R} y2={y} stroke="#1c222c" strokeDasharray="2 4" />
          <text
            x={PAD_L - 4}
            y={y + 3}
            textAnchor="end"
            fontFamily="JetBrains Mono"
            fontSize="9"
            fill="#475064"
          >
            {gridV[i].toFixed(0)}
          </text>
        </g>
      ))}
      <line
        x1={xAt(lastIdx)}
        y1={PAD_T}
        x2={xAt(lastIdx)}
        y2={H - PAD_B}
        stroke="#3a2e10"
        strokeDasharray="1 2"
      />
      <text
        x={xAt(lastIdx) + 4}
        y={PAD_T + 9}
        fontFamily="JetBrains Mono"
        fontSize="9"
        fill="#ffb020"
      >
        ↦ forecast
      </text>
      {bandUp.length > 0 && (
        <polygon points={bandPoly} fill="#ffb02022" stroke="none" />
      )}
      <path
        d={histPath}
        fill="none"
        stroke="#aab2bf"
        strokeWidth="1.2"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d={fcPath}
        fill="none"
        stroke="#ffb020"
        strokeWidth="1.4"
        strokeDasharray="3 2"
        vectorEffect="non-scaling-stroke"
      />
      {forecast.map((v, i) => (
        <circle key={i} cx={xAt(history.length + i)} cy={yAt(v)} r="2" fill="#ffb020" />
      ))}
      <text x={PAD_L} y={H - 6} fontFamily="JetBrains Mono" fontSize="9" fill="#6b7484">
        t−{history.length - 1}
      </text>
      <text
        x={xAt(lastIdx)}
        y={H - 6}
        textAnchor="middle"
        fontFamily="JetBrains Mono"
        fontSize="9"
        fill="#6b7484"
      >
        t
      </text>
      <text
        x={W - PAD_R}
        y={H - 6}
        textAnchor="end"
        fontFamily="JetBrains Mono"
        fontSize="9"
        fill="#6b7484"
      >
        t+{forecast.length}
      </text>
    </svg>
  )
}

// ─── Risk bar chart (simple, no recharts) ────────────────────────────────────

export function RiskBars({ data }: { data: ArgusAnalysis }) {
  const v = data.math_results.volatility
  const dd = data.math_results.drawdown

  const rows = [
    { name: 'EWMA VaR 95', value: v?.var_95_pct ?? 0 },
    { name: 'Hist VaR 95', value: v?.historical_var_95_pct ?? 0 },
    { name: 'Hist VaR 99', value: v?.historical_var_99_pct ?? 0 },
    { name: 'Max DD', value: Math.abs(dd?.max_drawdown_pct ?? 0) },
  ]
  const maxVal = Math.max(...rows.map((r) => r.value), 0.01)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {rows.map((row) => (
        <div key={row.name} className="contrib-row" style={{ gridTemplateColumns: '80px 1fr 52px' }}>
          <span className="name" style={{ fontSize: 10 }}>
            {row.name}
          </span>
          <span className="contrib-bar">
            <span
              className="fill down"
              style={{ left: 0, width: `${(row.value / maxVal) * 100}%` }}
            />
          </span>
          <span className="val down">{row.value.toFixed(2)}%</span>
        </div>
      ))}
    </div>
  )
}
