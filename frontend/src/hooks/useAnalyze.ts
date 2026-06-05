import { useMutation } from '@tanstack/react-query'

import { analyze } from '../api/argus'

export function useAnalyze() {
  return useMutation({
    mutationFn: ({ query, demoMode }: { query: string; demoMode: boolean }) => analyze(query, demoMode),
  })
}
