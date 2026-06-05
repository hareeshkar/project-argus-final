import { useQuery } from '@tanstack/react-query'

import { getHealth } from '../api/argus'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15_000,
    retry: 1,
  })
}
