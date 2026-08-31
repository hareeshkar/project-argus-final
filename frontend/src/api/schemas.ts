import { z } from 'zod'

const nullableNumber = z.number().nullable().optional()
const nullableString = z.string().nullable().optional()

const keyedNumbersSchema = z.record(z.string(), z.number())

export const healthSchema = z.object({
  status: z.string(),
  version: z.string().optional(),
  service: z.string().optional(),
  components: z.record(z.string(), z.any()),
})

const nodeStatusSchema = z.object({
  status: z.string(),
  error: z.string().optional(),
  provider: z.string().optional(),
})

export const liveSnapshotSchema = z.object({
  mode: z.string(),
  requested_real_capture: z.boolean(),
  requested_duration_seconds: z.number(),
  live_ticks_captured: z.number(),
  last_error: z.unknown().nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).default({}),
  memory_stats: z.object({
    total_symbols: z.number(),
    total_ticks: z.number(),
    max_ticks_per_symbol: z.number(),
  }),
  symbols: z.array(z.string()).default([]),
  symbol_metrics: z.record(
    z.string(),
    z.object({
      symbol: z.string(),
      latest_price: nullableNumber,
      vwap: nullableNumber,
      trade_intensity: nullableNumber,
      price_momentum: nullableNumber,
      window_volume: nullableNumber,
      tick_count: nullableNumber,
      last_update: z.union([z.string(), z.number()]).nullable().optional(),
      source: z.string().optional(),
    }),
  ).default({}),
  latest_summary: z.record(z.string(), z.unknown()).default({}),
  latest_most_active_trades: z.array(z.record(z.string(), z.unknown())).default([]),
  latest_share_price: z.record(z.string(), z.unknown()).default({}),
  captured_sample: z.array(z.record(z.string(), z.unknown())).default([]),
})

export const confidenceSchema = z.object({
  score: z.number(),
  label: z.string(),
  penalties: keyedNumbersSchema.default({}),
  reasons: z.array(z.string()).default([]),
})

export const indicatorVoteSchema = z.object({
  signal: z.string(),
  score: z.number(),
  confidence: z.number(),
  drivers: z.array(z.string()).default([]),
  components: keyedNumbersSchema.default({}),
  daily_score: nullableNumber,
  intraday_nudge: nullableNumber,
})

export const argusAnalysisSchema = z.object({
  query: z.string(),
  symbol: z.string(),
  company_name: nullableString,
  timestamp: z.string(),
  processing_time: z.number(),
  data_source_mode: z.string(),
  copy_mode: z.string().optional(),
  data_lineage: z.object({
    historical_source: z.string().optional(),
    live_source: z.string().optional(),
    order_book_source: z.string().optional(),
    intraday_context_source: z.string().nullable().optional(),
    llm_provider: z.string().optional(),
    copy_mode: z.string().optional(),
    scenarios: z.string().optional(),
    historical_rows: nullableNumber,
    tick_rows: nullableNumber,
    last_historical_timestamp: z.union([z.string(), z.number()]).nullable().optional(),
    last_tick_timestamp: z.union([z.string(), z.number()]).nullable().optional(),
  }),
  node_status: z.record(z.string(), nodeStatusSchema).optional(),
  confidence: confidenceSchema,
  indicator_vote: indicatorVoteSchema,
  ensemble: indicatorVoteSchema.optional(),
  ensemble_signal: z.string().optional(),
  math_results: z.object({
    arima: z
      .object({
        model_used: z.string().optional(),
        candidate_models: z.array(z.string()).default([]),
        selected_order: z.array(z.number()).default([]),
        aic: nullableNumber,
        aicc: nullableNumber,
        bic: nullableNumber,
        forecast: z.array(z.number()).default([]),
        confidence_interval: z
          .object({
            lower: z.array(z.number()).default([]),
            upper: z.array(z.number()).default([]),
          })
          .optional(),
        trend: z.string().optional(),
        beats_naive: z.boolean().optional(),
        forecast_confidence: z.string().optional(),
        residual_white_noise_pvalue: nullableNumber,
        oos_evaluation: z
          .object({
            holdout_size: z.number().optional(),
            model_oos_rmse: z.number().optional(),
            naive_flat_rmse: z.number().optional(),
            naive_drift_rmse: z.number().optional(),
            beats_naive_oos: z.boolean().optional(),
          })
          .optional(),
        error: nullableString,
      })
      .optional(),
    volatility: z
      .object({
        daily_volatility_pct: nullableNumber,
        ewma_lambda: nullableNumber,
        var_95_pct: nullableNumber,
        historical_var_95_pct: nullableNumber,
        historical_var_99_pct: nullableNumber,
        parkinson_volatility_pct: nullableNumber,
        flat_high_low_ratio: nullableNumber,
        volatility_percentile: nullableNumber,
        risk_level: z.string().optional(),
        error: nullableString,
      })
      .optional(),
    anomaly: z
      .object({
        return_zscore: nullableNumber,
        volume_zscore: nullableNumber,
        price_zscore: nullableNumber,
        modified_return_zscore: nullableNumber,
        modified_price_zscore: nullableNumber,
        modified_volume_zscore: nullableNumber,
        return_anomaly: z.boolean().optional(),
        price_anomaly: z.boolean().optional(),
        volume_anomaly: z.boolean().optional(),
        is_anomalous: z.boolean().optional(),
        lookback_days: nullableNumber,
        error: nullableString,
      })
      .optional(),
    zscore: z.unknown().optional(),
    drawdown: z
      .object({
        current_drawdown_pct: nullableNumber,
        max_drawdown_pct: nullableNumber,
        drawdown_duration_days: nullableNumber,
        error: nullableString,
      })
      .optional(),
    trend: z
      .object({
        slope: nullableNumber,
        r_squared: nullableNumber,
        p_value: nullableNumber,
        std_error: nullableNumber,
        trend_direction: z.string().optional(),
        is_strong_trend: z.boolean().optional(),
        days_analyzed: nullableNumber,
        error: nullableString,
      })
      .optional(),
    linreg: z.unknown().optional(),
    regime: z
      .object({
        trend_regime: z.string().optional(),
        volatility_regime: z.string().optional(),
        liquidity_regime: z.string().optional(),
        volume_percentile: nullableNumber,
        volatility_percentile: nullableNumber,
      })
      .optional(),
    confidence: confidenceSchema.optional(),
    indicator_vote: indicatorVoteSchema.optional(),
    data_points: z.number().optional(),
    analysis_timestamp: z.string().optional(),
    overall_health: z.string().optional(),
  }),
  order_book: z
    .object({
      symbol: z.string().optional(),
      bids: nullableNumber,
      asks: nullableNumber,
      pressure: nullableNumber,
      spread_estimate: nullableNumber,
      last_updated: z.union([z.string(), z.number()]).nullable().optional(),
    })
    .optional(),
  microstructure: z
    .object({
      symbol: z.string().optional(),
      latest_price: nullableNumber,
      vwap: nullableNumber,
      trade_intensity: nullableNumber,
      price_momentum: nullableNumber,
      window_volume: nullableNumber,
      tick_count: nullableNumber,
      last_update: z.union([z.string(), z.number()]).nullable().optional(),
      source: z.string().optional(),
      volume_estimated: z.boolean().optional(),
    })
    .optional(),
  intraday_context: z
    .object({
      available: z.boolean().optional(),
      source: z.string().nullable().optional(),
      latest_price: nullableNumber,
      last_daily_close: nullableNumber,
      price_divergence_pct: nullableNumber,
      vwap: nullableNumber,
      vwap_deviation_pct: nullableNumber,
      trade_intensity: nullableNumber,
      tick_count: nullableNumber,
      order_flow_pressure: nullableNumber,
      is_stale: z.boolean().optional(),
      staleness_seconds: nullableNumber,
      last_update: z.union([z.string(), z.number()]).nullable().optional(),
      warnings: z.array(z.string()).default([]),
    })
    .optional(),
  price_history: z
    .object({
      closes: z.array(z.number()).default([]),
      timestamps: z.array(z.string()).default([]),
      window: z.number().optional(),
    })
    .optional(),
  llm_explanation: z.union([
    z.string(),
    z.object({
      headline: z.string().optional(),
      summary: z.string().optional(),
      risk_notes: z.array(z.string()).default([]),
      confidence_explanation: z.string().optional(),
      disclaimer: z.string().optional(),
    }),
  ]),
  quality_flags: z.object({
    has_missing_values: z.boolean().optional(),
    has_null_open_prices: z.boolean().optional(),
    used_open_price_proxy: z.boolean().optional(),
    is_stale: z.boolean().optional(),
    order_book_snapshot: z.boolean().optional(),
    intraday_context_available: z.boolean().optional(),
    low_liquidity_warning: z.boolean().optional(),
    api_latency_warning: z.boolean().optional(),
    model_warning: z.boolean().optional(),
    warnings: z.array(z.string()).default([]),
  }),
  error: z.string().nullable(),
})

export const pipelineStageSchema = z.object({
  stage_id: z.string(),
  title: z.string(),
  status: z.enum(['queued', 'running', 'done', 'degraded', 'error']),
  message: z.string(),
  timestamp: z.number().optional(),
  elapsed_ms: z.number().optional(),
  detail: z.record(z.string(), z.unknown()).optional(),
})

export type Health = z.infer<typeof healthSchema>
export type ArgusAnalysis = z.infer<typeof argusAnalysisSchema>
export type LiveSnapshot = z.infer<typeof liveSnapshotSchema>
export type PipelineStage = z.infer<typeof pipelineStageSchema>

export const chatMessageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant']),
  content: z.string(),
  created_at: z.string(),
  symbol: z.string().optional(),
  provider: z.string().optional(),
})

export const chatResponseSchema = z.object({
  reply: z.string(),
  symbol: z.string(),
  provider: z.string(),
  rag_sources: z.array(z.string()).default([]),
  disclaimer: z.string(),
  analysis_refreshed: z.boolean(),
  copy_mode: z.string().optional(),
  analysis: argusAnalysisSchema.optional(),
  rag_stats: z
    .object({
      char_count: z.number(),
      section_count: z.number(),
      sections: z.array(z.string()),
    })
    .optional(),
})

export type ChatMessage = z.infer<typeof chatMessageSchema>
export type ChatResponse = z.infer<typeof chatResponseSchema>
