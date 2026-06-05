import { useQuery } from '@tanstack/react-query'

import { getLiveSnapshot } from '../api/argus'

export function useLiveSnapshot(enabled: boolean, marketOpen: boolean) {
  const real = enabled && marketOpen
  return useQuery({
    queryKey: ['live-snapshot', real],
    queryFn: () => getLiveSnapshot(real, real ? 3 : 1),
    enabled,
    refetchInterval: real ? 8_000 : 30_000,
    staleTime: real ? 5_000 : 20_000,
  })
}
