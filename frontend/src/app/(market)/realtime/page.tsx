'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  formatCurrency,
  formatPercent,
  formatChange,
  getChangeColorVar,
} from '@/lib/utils/format'
import type { MarketSummary } from '@/lib/types'

interface RealtimeQuote {
  stock_id: string
  name: string
  price: number
  change_pct: number
}

interface BatchQuoteResponse {
  quotes: RealtimeQuote[]
  total: number
  date: string
}

const POLL_INTERVAL = 5000
const DEFAULT_STOCKS = ['2330', '2317', '2454', '2881', '0050', '2303', '2882', '1301', '2308', '3711']

interface WatchlistResponse {
  total: number
  watchlists: { id: string; name: string; stock_ids: string[] }[]
}

function useRealtimeQuotes() {
  // 先取自選股清單
  const { data: wlData } = useSWR<WatchlistResponse>(
    '/watchlists',
    (path: string) => fetchAPI<WatchlistResponse>(path),
  )

  // 決定要查詢的股票：自選股或預設清單
  const stockIds = wlData?.watchlists?.[0]?.stock_ids?.length
    ? wlData.watchlists[0].stock_ids
    : DEFAULT_STOCKS

  const { data, error, isLoading } = useSWR<BatchQuoteResponse>(
    stockIds.length ? ['quote-batch', stockIds.join(',')] : null,
    () =>
      fetchAPI<BatchQuoteResponse>('/quote/realtime/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stock_ids: stockIds }),
      }),
    {
      refreshInterval: POLL_INTERVAL,
      revalidateOnFocus: true,
      dedupingInterval: 2000,
    }
  )
  return { data, isLoading, isError: !!error }
}

function useMarketIndex() {
  const { data, isLoading } = useSWR<MarketSummary>(
    '/market/summary',
    (path: string) => fetchAPI<MarketSummary>(path),
    { refreshInterval: POLL_INTERVAL, dedupingInterval: 2000 }
  )
  return { summary: data, isLoading }
}

function QuoteRowSkeleton() {
  return (
    <tr>
      {[...Array(4)].map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-14" style={{ background: 'var(--secondary)' }} />
        </td>
      ))}
    </tr>
  )
}

function IndexBadge({
  label,
  value,
  change,
  changePct,
  isLoading,
}: {
  label: string
  value: number
  change: number
  changePct: number
  isLoading: boolean
}) {
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-lg"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      <span className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>
        {label}
      </span>
      {isLoading ? (
        <Skeleton className="h-5 w-20" style={{ background: 'var(--secondary)' }} />
      ) : (
        <div className="flex items-center gap-2">
          <span className="text-base font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>
            {formatCurrency(value)}
          </span>
          <span
            className="text-xs tabular-nums font-semibold"
            style={{ color: getChangeColorVar(change) }}
          >
            {formatChange(change)} ({formatPercent(changePct)})
          </span>
        </div>
      )}
    </div>
  )
}

export default function RealtimePage() {
  const { data, isLoading, isError } = useRealtimeQuotes()
  const { summary, isLoading: indexLoading } = useMarketIndex()

  // 計算加權指數漲跌幅
  const taiexIndex = summary?.taiex_index ?? 0
  const taiexChange = summary?.taiex_change ?? 0
  const taiexChangePct = taiexIndex > 0 && taiexChange !== 0
    ? (taiexChange / (taiexIndex - taiexChange)) * 100
    : 0

  return (
    <div>
      {/* 頁面標題 */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
              即時報價
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
              自選股即時報價，每 5 秒自動更新
            </p>
          </div>
          {data?.date && (
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              資料日期：{data.date}
            </span>
          )}
        </div>
      </div>

      {/* 大盤指數 */}
      <div className="flex flex-wrap gap-3 mb-6">
        <IndexBadge
          label="加權指數"
          value={taiexIndex}
          change={taiexChange}
          changePct={taiexChangePct}
          isLoading={indexLoading}
        />
      </div>

      {/* 即時報價表格 */}
      {isError ? (
        <EmptyState
          title="無法載入即時報價"
          description="請確認後端服務是否正常運行，或稍後再試"
          icon="!"
        />
      ) : (
        <div
          className="rounded-lg overflow-hidden"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['代號', '名稱', '現價', '漲跌幅'].map(
                    (h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-left font-medium"
                        style={{ color: 'var(--muted-foreground)' }}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? [...Array(8)].map((_, i) => <QuoteRowSkeleton key={i} />)
                  : data?.quotes?.length
                  ? data.quotes.map((q) => (
                      <tr
                        key={q.stock_id}
                        className="border-b transition-colors hover:bg-white/5"
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <td
                          className="px-4 py-3 font-mono font-semibold"
                          style={{ color: 'var(--primary)' }}
                        >
                          {q.stock_id}
                        </td>
                        <td className="px-4 py-3" style={{ color: 'var(--foreground)' }}>
                          {q.name}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums font-bold text-base"
                          style={{ color: getChangeColorVar(q.change_pct) }}
                        >
                          {q.price?.toFixed(2) ?? '-'}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums font-semibold"
                          style={{ color: getChangeColorVar(q.change_pct) }}
                        >
                          {formatPercent(q.change_pct)}
                        </td>
                      </tr>
                    ))
                  : null}
                {!isLoading && !data?.quotes?.length && (
                  <tr>
                    <td colSpan={4}>
                      <EmptyState
                        title="暫無自選股報價"
                        description="尚未設定任何自選股"
                        icon="+"
                      />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
