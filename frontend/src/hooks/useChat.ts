import { useCallback, useState } from 'react'

import { postChat } from '../api/argus'
import type { ArgusAnalysis, ChatMessage } from '../api/schemas'

let msgId = 0
function nextId() {
  msgId += 1
  return `msg-${msgId}-${Date.now()}`
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isPending, setIsPending] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<Error>()

  const send = useCallback(
    async ({
      message,
      analysis,
      symbol,
      demoMode,
      copyMode,
      refreshAnalysis = false,
      onAnalysisUpdate,
    }: {
      message: string
      analysis?: ArgusAnalysis
      symbol?: string
      demoMode: boolean
      copyMode: 'simple' | 'experience'
      refreshAnalysis?: boolean
      onAnalysisUpdate?: (analysis: ArgusAnalysis) => void
    }) => {
      const trimmed = message.trim()
      if (!trimmed) return

      const userMsg: ChatMessage = {
        id: nextId(),
        role: 'user',
        content: trimmed,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMsg])
      setIsPending(true)
      setIsRefreshing(refreshAnalysis)
      setError(undefined)

      try {
        const history = [...messages, userMsg].map((m) => ({
          role: m.role,
          content: m.content,
        }))
        const response = await postChat({
          message: trimmed,
          history,
          analysis,
          symbol: symbol ?? analysis?.symbol,
          demoMode,
          copyMode,
          refreshAnalysis,
        })
        if (response.analysis) {
          onAnalysisUpdate?.(response.analysis)
        }
        const assistantMsg: ChatMessage = {
          id: nextId(),
          role: 'assistant',
          content: response.reply,
          created_at: new Date().toISOString(),
          symbol: response.symbol,
          provider: response.provider,
        }
        setMessages((prev) => [...prev, assistantMsg])
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)))
      } finally {
        setIsPending(false)
        setIsRefreshing(false)
      }
    },
    [messages],
  )

  const clear = useCallback(() => {
    setMessages([])
    setError(undefined)
  }, [])

  return { messages, send, clear, isPending, isRefreshing, error }
}
