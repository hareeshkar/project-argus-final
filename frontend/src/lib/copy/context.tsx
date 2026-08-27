import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'

import { displayBadge, translateEnum } from './enums'
import { HERO, LLM_SECTIONS, PIPELINE_STAGES, SCORE_METER, TOPBAR, panelCopy } from './labels'
import {
  DEFAULT_COPY_MODE,
  loadCopyMode,
  saveCopyMode,
  type CopyMode,
} from './mode'
import { riskBarLabels, riskFootnote, riskKpi, riskPanelMeta, riskTailWarning, type RiskKpiCopy, type RiskKpiKey } from './risk'

type CopyContextValue = {
  mode: CopyMode
  setMode: (mode: CopyMode) => void
  panel: (idx: string) => ReturnType<typeof panelCopy>
  hero: (key: keyof typeof HERO.simple) => string
  topbar: (key: keyof typeof TOPBAR.simple) => string
  llmSection: (key: keyof typeof LLM_SECTIONS.simple) => string
  pipelineStage: (stageId: string) => string
  scoreMeter: () => [string, string, string]
  enumLabel: (category: string, value?: string | null) => string
  badge: (category: string, value?: string | null) => string
  risk: (key: RiskKpiKey) => RiskKpiCopy
  riskMeta: () => string
  riskBars: () => string[]
  riskWarning: () => ReturnType<typeof riskTailWarning>
  riskNote: () => string
}

const CopyModeContext = createContext<CopyContextValue | null>(null)

export function CopyModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<CopyMode>(() => loadCopyMode())

  const setMode = (next: CopyMode) => {
    setModeState(next)
    saveCopyMode(next)
  }

  const value = useMemo<CopyContextValue>(
    () => ({
      mode,
      setMode,
      panel: (idx) => panelCopy(mode, idx),
      hero: (key) => HERO[mode][key],
      topbar: (key) => TOPBAR[mode][key],
      llmSection: (key) => LLM_SECTIONS[mode][key],
      pipelineStage: (stageId) => PIPELINE_STAGES[mode][stageId] ?? stageId,
      scoreMeter: () => SCORE_METER[mode],
      enumLabel: (category, value) => translateEnum(mode, category, value),
      badge: (category, value) => displayBadge(mode, category, value),
      risk: (key) => riskKpi(mode, key),
      riskMeta: () => riskPanelMeta(mode),
      riskBars: () => riskBarLabels(mode),
      riskWarning: () => riskTailWarning(mode),
      riskNote: () => riskFootnote(mode),
    }),
    [mode],
  )

  return <CopyModeContext.Provider value={value}>{children}</CopyModeContext.Provider>
}

export function useCopyMode(): CopyContextValue {
  const ctx = useContext(CopyModeContext)
  if (!ctx) throw new Error('useCopyMode must be used within CopyModeProvider')
  return ctx
}

export { DEFAULT_COPY_MODE, type CopyMode }
