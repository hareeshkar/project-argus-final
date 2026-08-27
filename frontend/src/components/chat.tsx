import { useEffect, useRef, useState } from 'react'

import type { ArgusAnalysis } from '../api/schemas'
import { useCopyMode } from '../lib/copy'

export function ChatDrawer({
  open,
  onClose,
  analysis,
  demoMode,
  onSend,
  messages,
  isPending,
  isRefreshing,
  error,
  onClear,
}: {
  open: boolean
  onClose: () => void
  analysis?: ArgusAnalysis
  demoMode: boolean
  onSend: (message: string, refreshAnalysis: boolean) => void
  messages: Array<{
    id: string
    role: 'user' | 'assistant'
    content: string
    provider?: string
  }>
  isPending: boolean
  isRefreshing?: boolean
  error?: Error
  onClear: () => void
}) {
  const copy = useCopyMode()
  const [input, setInput] = useState('')
  const [refreshNext, setRefreshNext] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [open, messages, isPending])

  if (!open) return null

  const symbol = analysis?.symbol?.split('.')[0] ?? '—'
  const hasContext = Boolean(analysis)

  const handleSubmit = () => {
    const text = input.trim()
    if (!text || isPending) return
    onSend(text, refreshNext)
    setInput('')
    setRefreshNext(false)
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer drawer-chat" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2>Argus Chat · RAG</h2>
          <span className={`badge ${hasContext ? 'ok' : 'warn'}`}>
            {hasContext ? `${symbol} · context loaded` : 'no context'}
          </span>
          <span className="badge neutral">{copy.mode === 'simple' ? 'SIMPLE' : 'EXPERIENCE'}</span>
          <span style={{ flex: 1 }} />
          <button type="button" className="badge" onClick={onClear} disabled={messages.length === 0}>
            CLEAR
          </button>
          <button type="button" className="badge accent" onClick={onClose}>
            ESC ✕
          </button>
        </div>

        <div className={`chat-rag-banner ${hasContext ? 'live' : ''}`}>
          <span className={`dot ${hasContext ? 'ok' : 'warn'}`} />
          {hasContext ? (
            <p>
              Grounded in dashboard analysis for <strong>{analysis?.symbol}</strong> — forecast,
              risk, confidence, intraday context, lineage, and summary retrieved as RAG context.
            </p>
          ) : (
            <p>
              Run an analysis first, or ask about a symbol (e.g. &quot;What is the risk for
              COMB?&quot;) — Argus will fetch data, then answer from it.
            </p>
          )}
        </div>

        <div className="chat-messages drawer-body">
          {messages.length === 0 && (
            <div className="chat-empty">
              <p className="lbl-strong">Try asking</p>
              <ul className="chat-suggestions">
                {[
                  `Why is confidence ${copy.mode === 'simple' ? 'at this level' : 'MODERATE'}?`,
                  'Explain the forecast and main risks',
                  'How do live ticks and order flow affect the signal?',
                ].map((q) => (
                  <li key={q}>
                    <button type="button" onClick={() => setInput(q)} disabled={isPending}>
                      {q}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`chat-bubble ${m.role}`}>
              <div className="chat-meta">
                {m.role === 'user' ? 'You' : 'Argus'}
                {m.provider && <span className="muted"> · {m.provider}</span>}
              </div>
              <div className="chat-text">{m.content}</div>
            </div>
          ))}
          {isPending && (
            <div className="chat-bubble assistant pending">
              <div className="chat-meta">
                Argus · {isRefreshing ? 'refreshing analysis' : 'retrieving'}
              </div>
              <div className="chat-text muted">
                <span className="chat-typing">
                  {isRefreshing
                    ? 'Re-running analysis pipeline for fresh numbers'
                    : 'Composing reply from retrieved evidence'}
                </span>
                <span className="chat-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </div>
          )}
          {error && (
            <div className="warning err" style={{ marginTop: 8 }}>
              <span className="icon">!</span>
              <div className="body">{error.message}</div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <footer className="chat-compose">
          <label className="chat-refresh">
            <input
              type="checkbox"
              checked={refreshNext}
              onChange={(e) => setRefreshNext(e.target.checked)}
              disabled={isPending}
            />
            Refresh analysis before reply
          </label>
          <div className="chat-input-row">
            <span className="chat-input-caret">▸</span>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit()
                }
              }}
              placeholder={
                hasContext
                  ? `Ask about ${symbol}…`
                  : 'Ask about a CSE symbol…'
              }
              disabled={isPending}
            />
            <button type="button" className="chat-send" onClick={handleSubmit} disabled={isPending || !input.trim()}>
              {isPending ? '…' : 'SEND ↵'}
            </button>
          </div>
          <div className="chat-hint">
            <span>↵ send</span>
            <span>·</span>
            <span>RAG from dashboard evidence</span>
            <span>·</span>
            <span>not investment advice</span>
            {demoMode && <span className="accent-txt"> · demo</span>}
          </div>
        </footer>
      </div>
    </div>
  )
}
