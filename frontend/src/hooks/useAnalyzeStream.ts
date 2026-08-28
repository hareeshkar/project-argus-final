import { useEffect, useRef, useState } from 'react'

import { streamAnalysis } from '../api/argus'
import type { ArgusAnalysis, PipelineStage } from '../api/schemas'

const STAGE_ORDER = ['parse', 'fetch', 'models', 'confidence', 'narrative']

function sortStages(stages: PipelineStage[]) {
  return [...stages].sort((a, b) => STAGE_ORDER.indexOf(a.stage_id) - STAGE_ORDER.indexOf(b.stage_id))
}

function upsertStage(stages: PipelineStage[], next: PipelineStage) {
  const existing = stages.findIndex((stage) => stage.stage_id === next.stage_id)
  if (existing === -1) return sortStages([...stages, next])
  const copy = [...stages]
  copy[existing] = next
  return sortStages(copy)
}

export function useAnalyzeStream() {
  const sourceRef = useRef<EventSource | null>(null)
  const startedRef = useRef(0)
  const [data, setData] = useState<ArgusAnalysis>()
  const [pipeline, setPipeline] = useState<PipelineStage[]>([])
  const [error, setError] = useState<Error>()
  const [isPending, setIsPending] = useState(false)
  const [latencyMs, setLatencyMs] = useState<number>()

  useEffect(() => {
    return () => sourceRef.current?.close()
  }, [])

  const run = ({
    query,
    demoMode,
    copyMode = 'simple',
    scenarios = [] as string[],
  }: {
    query: string
    demoMode: boolean
    copyMode?: 'simple' | 'experience'
    scenarios?: string[]
  }) => {
    sourceRef.current?.close()
    startedRef.current = performance.now()
    setError(undefined)
    setPipeline([])
    setIsPending(true)
    setLatencyMs(undefined)

    sourceRef.current = streamAnalysis({
      query,
      demoMode,
      copyMode,
      scenarios,
      onStage: (stage) => setPipeline((current) => upsertStage(current, stage)),
      onFinal: (payload) => {
        setData(payload)
        setLatencyMs(Math.round(performance.now() - startedRef.current))
        setIsPending(false)
        sourceRef.current = null
      },
      onError: (nextError) => {
        setError(nextError)
        setIsPending(false)
        setPipeline((current) => upsertStage(current, {
          stage_id: 'pipeline',
          title: 'Analysis pipeline',
          status: 'error',
          message: nextError.message,
        }))
        sourceRef.current = null
      },
    })
  }

  return {
    data,
    pipeline,
    error,
    isError: Boolean(error),
    isPending,
    latencyMs,
    run,
    applyAnalysis: setData,
  }
}
