'use client'

import useSWR from 'swr'
import { useRefreshInterval } from '@/lib/hooks/useRefreshInterval'
import { fetchAPI } from '@/lib/api/client'
import { EmptyState } from '@/components/shared/EmptyState'
import { StaleBanner } from '@/components/shared/StaleBanner'
import { Skeleton } from '@/components/ui/skeleton'
import {
  formatCurrency,
  formatPercent,
  formatChange,
  formatPrice,
  formatVolume,
  formatVolumeValue,
  getChangeColorVar,
} from '@/lib/utils/format'
import type { MarketSummary } from '@/lib/types'
import {
  getBatchQuoteRefreshInterval,
  quoteStatusColor,
  quoteStatusLabel,
  quoteTimeLabel,
  type RealtimeQuote,
} from '@/lib/quotes/realtime'

interface BatchQuoteResponse {
  quotes: RealtimeQuote[]
  total: number
  date?: string
  has_realtime: boolean
  market_state: string
  sources: string[]
}

const DEFAULT_STOCKS = ['2330', '2317', '2454', '2881', '0050', '2303', '2882', '1301', '2308', '3711']

interface WatchlistDetail {
  stocks: Array<{ stock_id: string }>
}

function useRealtimeQuotes() {
  const refreshInterval = useRefreshInterval()
  // 直接取 default 明細；列表端點只有數量，不含股票代號。
  const { data: wlData } = useSWR<WatchlistDetail>(
    '/watchlists/default',
    (path: string) => fetchAPI<WatchlistDetail>(path),
  )

  // 決定要查詢的股票：自選股或預設清單
  const watchlistIds = wlData?.stocks?.map((stock) => stock.stock_id) ?? []
  const stockIds = watchlistIds.length
    ? watchlistIds
    : DEFAULT_STOCKS

  const { data, error, isLoading } = useSWR<BatchQuoteResponse>(
    stockIds.length ? ['quote-batch', stockIds.join(',')] : null,
    // POST body 從 SWR key 衍生而非閉包捕捉 stockIds：
    // 避免 watchlist 從預設清單切換到使用者清單時，快取中的舊 fetcher
    // 帶著過期的股票組合送出請求（key 與 body 脫鉤）。
    ([, ids]: [string, string]) =>
      fetchAPI<BatchQuoteResponse>('/quote/realtime/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stock_ids: ids.split(',') }),
      }),
    {
      refreshInterval: () => refreshInterval(getBatchQuoteRefreshInterval(stockIds.length)),
      revalidateOnFocus: true,
      dedupingInterval: 10_000,
    }
  )
  return { data, isLoading, isError: !!error }
}

function useMarketIndex() {
  const { data, isLoading } = useSWR<MarketSummary>(
    '/market/summary',
    (path: string) => fetchAPI<MarketSummary>(path),
    { refreshInterval: 60_000, dedupingInterval: 10_000 }
  )
  return { summary: data, isLoading }
}

function QuoteRowSkeleton() {
  return (
    <tr>
      {[...Array(7)].map((_, i) => (
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
              盤中每 15 秒更新；Fugle / TWSE 無資料時自動顯示 FinLab 收盤價
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
      {isError && data && <StaleBanner />}
      {isError && !data ? (
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
                  {['代號', '名稱', '現價', '漲跌幅', '成交量', '成交金額', '狀態'].map(
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
                          style={{ color: 'var(--foreground)' }}
                        >
                          {q.price != null ? formatPrice(q.price) : '-'}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums font-semibold"
                          style={{ color: getChangeColorVar(q.change_pct) }}
                        >
                          {formatPercent(q.change_pct, 2, true)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: 'var(--muted-foreground)' }}
                        >
                          {q.volume != null ? formatVolume(q.volume) : '—'}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: 'var(--muted-foreground)' }}
                        >
                          {q.amount != null ? formatVolumeValue(q.amount) : '—'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <div className="text-xs font-medium" style={{ color: quoteStatusColor(q) }}>
                            {quoteStatusLabel(q)}
                          </div>
                          <div className="text-[11px] mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                            {quoteTimeLabel(q)}
                          </div>
                        </td>
                      </tr>
                    ))
                  : null}
                {!isLoading && !data?.quotes?.length && (
                  <tr>
                    <td colSpan={7}>
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
