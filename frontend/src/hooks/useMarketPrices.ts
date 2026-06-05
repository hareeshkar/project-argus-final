import { useQuery } from '@tanstack/react-query'
import { apiBaseUrl } from '../api/client'

interface SymbolPrice {
  price: number | null
  change: number | null
  pct_change: number | null
}

async function fetchMarketPrices(): Promise<Record<string, SymbolPrice>> {
  const res = await fetch(`${apiBaseUrl()}/api/market-prices`)
  if (!res.ok) throw new Error(`market-prices ${res.status}`)
  const data = await res.json()
  return data.prices ?? {}
}

export function useMarketPrices(enabled = true) {
  return useQuery({
    queryKey: ['market-prices'],
    queryFn: fetchMarketPrices,
    enabled,
    refetchInterval: 5_000,
    staleTime: 3_000,
  })
}
