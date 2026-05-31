import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'

export interface WatchlistStock {
  stock_id: string
  name: string
  industry?: string
  price: number | null
  change_pct: number | null
}

interface WatchlistDetail {
  id: string
  name: string
  stocks_count: number
  stocks: WatchlistStock[]
}

const WATCHLIST_ID = 'default'

/** 預設自選股清單（供 Sidebar 快捷導覽與自選股頁共用）。 */
export function useWatchlist() {
  const { data, error, isLoading, mutate } = useSWR<WatchlistDetail>(
    `/watchlists/${WATCHLIST_ID}`,
    (path: string) => fetchAPI<WatchlistDetail>(path),
    { refreshInterval: 60000, revalidateOnFocus: true, shouldRetryOnError: false }
  )

  return {
    stocks: data?.stocks ?? [],
    isLoading,
    isError: !!error,
    refresh: mutate,
  }
}
