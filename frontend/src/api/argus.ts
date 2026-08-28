import { apiBaseUrl, apiFetch } from './client'
import { argusAnalysisSchema, chatResponseSchema, healthSchema, liveSnapshotSchema, pipelineStageSchema } from './schemas'
import type { ArgusAnalysis, ChatResponse, Health, LiveSnapshot, PipelineStage } from './schemas'

export async function getHealth(): Promise<Health> {
  const payload = await apiFetch<unknown>('/health')
  return healthSchema.parse(payload)
}

export async function analyze(
  query: string,
  demoMode: boolean,
  copyMode: 'simple' | 'experience' = 'simple',
  scenarios: string[] = [],
): Promise<ArgusAnalysis> {
  const payload = await apiFetch<unknown>('/api/analyze', {
    method: 'POST',
    body: JSON.stringify({ query, demo_mode: demoMode, copy_mode: copyMode, scenarios }),
  })

  const parsed = argusAnalysisSchema.safeParse(payload)
  if (!parsed.success) {
    throw new Error(`Argus response schema mismatch: ${parsed.error.issues.map((issue) => `${issue.path.join('.')}: ${issue.message}`).join('; ')}`)
  }

  return parsed.data
}

export async function getLiveSnapshot(real = false, duration = 3): Promise<LiveSnapshot> {
  const params = new URLSearchParams({ real: String(real), duration: String(duration) })
  const payload = await apiFetch<unknown>(`/api/live-snapshot?${params.toString()}`)
  return liveSnapshotSchema.parse(payload)
}

export function streamAnalysis({
  query,
  demoMode,
  copyMode = 'simple',
  scenarios = [],
  pace = 'fast',
  onStage,
  onFinal,
  onError,
}: {
  query: string
  demoMode: boolean
  copyMode?: 'simple' | 'experience'
  scenarios?: string[]
  pace?: 'fast' | 'academic'
  onStage: (stage: PipelineStage) => void
  onFinal: (payload: ArgusAnalysis) => void
  onError: (error: Error) => void
}): EventSource {
  const params = new URLSearchParams({
    query,
    demo_mode: String(demoMode),
    copy_mode: copyMode,
    scenarios: scenarios.join(','),
    pace,
  })
  const source = new EventSource(`${apiBaseUrl()}/api/analyze/stream?${params.toString()}`)

  source.addEventListener('pipeline', (event) => {
    try {
      onStage(pipelineStageSchema.parse(JSON.parse(event.data)))
    } catch (error) {
      onError(error instanceof Error ? error : new Error(String(error)))
      source.close()
    }
  })

  source.addEventListener('final', (event) => {
    try {
      onFinal(argusAnalysisSchema.parse(JSON.parse(event.data)))
      source.close()
    } catch (error) {
      onError(error instanceof Error ? error : new Error(String(error)))
      source.close()
    }
  })

  source.addEventListener('analysis_error', (event) => {
    try {
      const payload = JSON.parse(event.data) as { message?: string }
      onError(new Error(payload.message ?? 'Argus streaming analysis failed'))
    } catch {
      onError(new Error('Argus streaming analysis failed'))
    }
    source.close()
  })

  source.onerror = () => {
    if (source.readyState !== EventSource.CLOSED) {
      onError(new Error('Argus streaming connection failed'))
      source.close()
    }
  }

  return source
}

export async function postChat({
  message,
  history,
  analysis,
  symbol,
  demoMode,
  copyMode = 'simple',
  refreshAnalysis = false,
}: {
  message: string
  history?: Array<{ role: string; content: string }>
  analysis?: ArgusAnalysis
  symbol?: string
  demoMode?: boolean
  copyMode?: 'simple' | 'experience'
  refreshAnalysis?: boolean
}): Promise<ChatResponse> {
  const payload = await apiFetch<unknown>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      history,
      analysis,
      symbol,
      demo_mode: demoMode,
      copy_mode: copyMode,
      refresh_analysis: refreshAnalysis,
    }),
  })
  return chatResponseSchema.parse(payload)
}
