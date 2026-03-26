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
  code: string
  name: string
  price: number
  change: number
  changePercent: number
  open: number
  high: number
  low: number
  volume: number
  bid: number
  ask: number
}

interface BatchQuoteResponse {
  quotes: RealtimeQuote[]
  updatedAt: string
}

const POLL_INTERVAL = 5000

function useRealtimeQuotes() {
  const { data, error, isLoading } = useSWR<BatchQuoteResponse>(
    '/quote/realtime/batch',
    (path: string) => fetchAPI<BatchQuoteResponse>(path),
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
      {[...Array(8)].map((_, i) => (
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
  changePercent,
  isLoading,
}: {
  label: string
  value: number
  change: number
  changePercent: number
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
            {formatChange(change)} ({formatPercent(changePercent)})
          </span>
        </div>
      )}
    </div>
  )
}

export default function RealtimePage() {
  const { data, isLoading, isError } = useRealtimeQuotes()
  const { summary, isLoading: indexLoading } = useMarketIndex()

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
          {data?.updatedAt && (
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              更新時間：{new Date(data.updatedAt).toLocaleTimeString('zh-TW')}
            </span>
          )}
        </div>
      </div>

      {/* 大盤指數 */}
      <div className="flex flex-wrap gap-3 mb-6">
        <IndexBadge
          label="加權指數"
          value={summary?.taiex?.close ?? 0}
          change={summary?.taiex?.change ?? 0}
          changePercent={summary?.taiex?.changePercent ?? 0}
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
                  {['代號', '名稱', '現價', '漲跌', '漲跌幅', '開盤', '最高', '最低', '成交量(張)'].map(
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
                        key={q.code}
                        className="border-b transition-colors hover:bg-white/5"
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <td
                          className="px-4 py-3 font-mono font-semibold"
                          style={{ color: 'var(--primary)' }}
                        >
                          {q.code}
                        </td>
                        <td className="px-4 py-3" style={{ color: 'var(--foreground)' }}>
                          {q.name}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums font-bold text-base"
                          style={{ color: getChangeColorVar(q.change) }}
                        >
                          {q.price.toFixed(2)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: getChangeColorVar(q.change) }}
                        >
                          {formatChange(q.change)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: getChangeColorVar(q.changePercent) }}
                        >
                          {formatPercent(q.changePercent)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: 'var(--foreground)' }}
                        >
                          {q.open.toFixed(2)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: 'var(--stock-up)' }}
                        >
                          {q.high.toFixed(2)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: 'var(--stock-down)' }}
                        >
                          {q.low.toFixed(2)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: 'var(--foreground)' }}
                        >
                          {q.volume.toLocaleString()}
                        </td>
                      </tr>
                    ))
                  : null}
                {!isLoading && !data?.quotes?.length && (
                  <tr>
                    <td colSpan={9}>
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
