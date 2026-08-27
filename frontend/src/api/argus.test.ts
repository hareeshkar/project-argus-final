import { describe, expect, it, vi } from 'vitest'

import { streamAnalysis } from './argus'

describe('streamAnalysis copy_mode', () => {
  it('includes copy_mode in the EventSource URL', () => {
    let capturedUrl = ''
    class MockEventSource {
      addEventListener = vi.fn()
      close = vi.fn()
      onerror = null
      readyState = 0
      constructor(url: string) {
        capturedUrl = url
      }
    }
    vi.stubGlobal('EventSource', MockEventSource)

    streamAnalysis({
      query: 'Analyze COMB',
      demoMode: false,
      copyMode: 'experience',
      onStage: () => {},
      onFinal: () => {},
      onError: () => {},
    })

    expect(capturedUrl).toContain('copy_mode=experience')
    vi.unstubAllGlobals()
  })
})
