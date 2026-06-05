import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { apiBaseUrl } from '../api/client'

export type LivePriceQuote = {
  symbol: string
  found: boolean
  price?: number | null
  change?: number | null
  pct_change?: number | null
  quantity?: number | null
  sharevolume?: number | null
  tradevolume?: number | null
  turnover?: number | null
  high?: number | null
  low?: number | null
  last_traded_time?: number | null
  source?: string
  updated_at?: number
}

async function fetchLivePrice(symbol: string): Promise<LivePriceQuote> {
  const params = new URLSearchParams({ symbol })
  const res = await fetch(`${apiBaseUrl()}/api/live-price?${params.toString()}`)
  if (!res.ok) throw new Error(`live-price ${res.status}`)
  return res.json()
}

export function useLivePrice(
  symbol: string | undefined,
  enabled: boolean,
  marketOpen: boolean,
) {
  const query = useQuery({
    queryKey: ['live-price', symbol],
    queryFn: () => fetchLivePrice(symbol!),
    enabled: enabled && Boolean(symbol),
    refetchInterval: marketOpen ? 1_000 : 30_000,
    staleTime: marketOpen ? 500 : 20_000,
    retry: 2,
  })

  const [prices, setPrices] = useState<number[]>([])

  useEffect(() => {
    setPrices([])
  }, [symbol])

  useEffect(() => {
    const price = query.data?.price
    if (price == null) return
    setPrices((current) => {
      const last = current[current.length - 1]
      if (last === price && current.length > 0) return current
      return [...current.slice(-59), price]
    })
  }, [query.data?.price, query.dataUpdatedAt])

  return {
    quote: query.data,
    prices,
    polling: query.isFetching,
    isLive: enabled && marketOpen && query.isSuccess && Boolean(query.data?.found),
    error: query.error,
  }
}
