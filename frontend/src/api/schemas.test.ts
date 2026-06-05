import { describe, expect, it } from 'vitest'

import { argusAnalysisSchema, healthSchema, liveSnapshotSchema } from './schemas'

const analysisPayload = {
  query: 'Analyze COMB',
  symbol: 'COMB.N0000',
  company_name: null,
  timestamp: '2026-05-24T17:35:00.000Z',
  processing_time: 0.42,
  data_source_mode: 'offline_demo',
  data_lineage: {
    historical_source: 'IN_MEMORY_DEMO',
    live_source: 'IN_MEMORY_DEMO',
    order_book_source: 'IN_MEMORY_DEMO',
    llm_provider: 'template',
    historical_rows: 120,
    tick_rows: 86,
    last_historical_timestamp: '2026-04-30 00:00:00',
    last_tick_timestamp: 1779692257.732016,
  },
  confidence: {
    score: 0.75,
    label: 'HIGH',
    penalties: {
      insufficient_rows: 0,
      model_underperformance: 0,
      arima_diagnostics: 0,
      missing_values: 0,
      thin_liquidity: 0,
      flat_high_low: 0,
    },
    reasons: ['Sufficient daily data available within CSE API cap'],
  },
  indicator_vote: {
    signal: 'NEUTRAL',
    score: 0.02,
    confidence: 0.75,
    drivers: ['Confidence driver'],
    components: {
      trend_score: 0,
      volatility_score: 0.05,
      liquidity_score: 0.1,
      anomaly_score: -0.15,
    },
  },
  ensemble: {
    signal: 'NEUTRAL',
    score: 0.02,
    confidence: 0.75,
    drivers: ['Confidence driver'],
    components: {
      trend_score: 0,
      volatility_score: 0.05,
      liquidity_score: 0.1,
      anomaly_score: -0.15,
    },
  },
  ensemble_signal: 'NEUTRAL',
  math_results: {
    arima: {
      model_used: 'ARIMA(1, 1, 0)',
      candidate_models: ['ARIMA(0, 1, 0)', 'ARIMA(1, 1, 0)'],
      selected_order: [1, 1, 0],
      aic: -1300.41,
      aicc: -1300.3,
      bic: -1294.85,
      forecast: [219.55, 217.74, 216.12],
      confidence_interval: {
        lower: [219.1, 216.8, 214.6],
        upper: [219.9, 218.6, 217.6],
      },
      trend: 'DOWN',
      beats_naive: true,
      forecast_confidence: 'MODERATE',
      residual_white_noise_pvalue: 1,
      error: null,
    },
    volatility: {
      daily_volatility_pct: 0.26,
      ewma_lambda: 0.94,
      var_95_pct: 0.34,
      historical_var_95_pct: 0.09,
      historical_var_99_pct: 0.09,
      parkinson_volatility_pct: 1.44,
      flat_high_low_ratio: 0,
      volatility_percentile: 100,
      risk_level: 'LOW',
      error: null,
    },
    anomaly: {
      return_zscore: -4.24,
      volume_zscore: -1.54,
      price_zscore: -4.24,
      modified_return_zscore: -1792.53,
      modified_price_zscore: -1792.53,
      modified_volume_zscore: -1.21,
      return_anomaly: true,
      price_anomaly: true,
      volume_anomaly: false,
      is_anomalous: true,
      lookback_days: 20,
      error: null,
    },
    zscore: {
      return_zscore: -4.24,
      volume_zscore: -1.54,
      price_zscore: -4.24,
      modified_return_zscore: -1792.53,
      modified_price_zscore: -1792.53,
      modified_volume_zscore: -1.21,
      return_anomaly: true,
      price_anomaly: true,
      volume_anomaly: false,
      is_anomalous: true,
      lookback_days: 20,
      error: null,
    },
    drawdown: {
      current_drawdown_pct: -1,
      max_drawdown_pct: -1,
      drawdown_duration_days: 1,
      error: null,
    },
    trend: {
      slope: 0.001,
      r_squared: 0.47,
      p_value: 0.02,
      std_error: 0.001,
      trend_direction: 'UP',
      is_strong_trend: true,
      days_analyzed: 30,
      error: null,
    },
    linreg: {
      slope: 0.001,
      r_squared: 0.47,
      p_value: 0.02,
      std_error: 0.001,
      trend_direction: 'UP',
      is_strong_trend: true,
      days_analyzed: 30,
      error: null,
    },
    regime: {
      trend_regime: 'UP',
      volatility_regime: 'HIGH',
      liquidity_regime: 'LIQUID',
      volume_percentile: 100,
      volatility_percentile: 100,
    },
    confidence: {
      score: 0.75,
      label: 'HIGH',
      penalties: {
        insufficient_rows: 0,
        model_underperformance: 0,
        arima_diagnostics: 0,
        missing_values: 0,
        thin_liquidity: 0,
        flat_high_low: 0,
      },
      reasons: ['Sufficient daily data available within CSE API cap'],
    },
    indicator_vote: {
      signal: 'NEUTRAL',
      score: 0.02,
      confidence: 0.75,
      drivers: ['Confidence driver'],
      components: {
        trend_score: 0,
        volatility_score: 0.05,
        liquidity_score: 0.1,
        anomaly_score: -0.15,
      },
    },
    data_points: 120,
    analysis_timestamp: '2026-05-24T17:35:00.000Z',
    overall_health: 'HEALTHY',
  },
  order_book: {
    symbol: 'COMB.N0000',
    bids: 324649,
    asks: 164686,
    pressure: 0.3269,
    spread_estimate: 0.25,
    last_updated: '2026-05-24T10:01:10.000Z',
  },
  microstructure: {
    symbol: 'COMB.N0000',
    latest_price: 203,
    vwap: 206.53,
    trade_intensity: 18,
    price_momentum: -3.25,
    window_volume: 168192,
    tick_count: 86,
    last_update: 1779642986.105901,
  },
  price_history: {
    closes: Array.from({ length: 30 }, (_, i) => 200 + i * 0.1),
    timestamps: Array.from({ length: 30 }, (_, i) => `2026-04-${String(i + 1).padStart(2, '0')} 00:00:00`),
    window: 30,
  },
  llm_explanation: {
    summary: 'COMB.N0000 has a neutral analytical lean with high confidence.',
    risk_notes: ['Research output only.'],
    confidence_explanation: 'Sufficient data.',
    disclaimer: 'Research analytics only. Not investment advice.',
  },
  quality_flags: {
    has_missing_values: false,
    has_null_open_prices: false,
    used_open_price_proxy: false,
    is_stale: false,
    low_liquidity_warning: false,
    api_latency_warning: false,
    model_warning: false,
    warnings: ['Sufficient daily data available within CSE API cap'],
  },
  error: null,
}

import { pipelineStageSchema } from './schemas'

describe('Argus API schemas', () => {
  it('accepts queued pipeline stage status from SSE stream', () => {
    const parsed = pipelineStageSchema.parse({
      stage_id: 'narrative',
      title: 'Generating analyst summary',
      status: 'queued',
      message: 'Narrative queued in background worker',
      timestamp: Date.now() / 1000,
    })

    expect(parsed.status).toBe('queued')
  })

  it('parses the real /api/analyze contract used by the backend tests', () => {
    const parsed = argusAnalysisSchema.parse(analysisPayload)

    expect(parsed.symbol).toBe('COMB.N0000')
    expect(parsed.indicator_vote.components.anomaly_score).toBe(-0.15)
    expect(parsed.math_results.arima?.forecast).toHaveLength(3)
  })

  it('parses /health component status', () => {
    const parsed = healthSchema.parse({
      status: 'ok',
      version: '2.0.0',
      service: 'Project Argus Final API',
      components: {
        api: 'ok',
        data_provider: 'ok',
        analytics_engine: 'ok',
        llm_provider: 'template',
      },
    })

    expect(parsed.components.analytics_engine).toBe('ok')
  })

  it('parses /api/live-snapshot payloads used by the live tape', () => {
    const parsed = liveSnapshotSchema.parse({
      mode: 'deterministic_fallback',
      requested_real_capture: false,
      requested_duration_seconds: 1,
      live_ticks_captured: 0,
      last_error: null,
      metadata: { live_source: 'CSE_WEBSOCKET_DAYTRADE' },
      memory_stats: { total_symbols: 2, total_ticks: 5, max_ticks_per_symbol: 100 },
      symbols: ['COMB.N0000'],
      symbol_metrics: {
        'COMB.N0000': {
          symbol: 'COMB.N0000',
          latest_price: 203,
          vwap: 203.02,
          trade_intensity: 3,
          price_momentum: -0.25,
          window_volume: 4500,
          tick_count: 3,
          source: 'CSE_WEBSOCKET_DAYTRADE',
        },
      },
      latest_summary: {},
      latest_most_active_trades: [],
      latest_share_price: {},
      captured_sample: [],
    })

    expect(parsed.symbol_metrics['COMB.N0000'].tick_count).toBe(3)
  })
})
