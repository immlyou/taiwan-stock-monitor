import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import type { MarketSummary } from '@/lib/types'

const REFRESH_INTERVAL = 30000 // 30 秒自動更新

export function useMarketSummary() {
  const { data, error, isLoading, mutate } = useSWR<MarketSummary>(
    '/market/summary',
    (path: string) => fetchAPI<MarketSummary>(path),
    {
      refreshInterval: REFRESH_INTERVAL,
      revalidateOnFocus: true,
      dedupingInterval: 5000,
    }
  )

  return {
    summary: data,
    isLoading,
    isError: !!error,
    error,
    refresh: mutate,
  }
}
