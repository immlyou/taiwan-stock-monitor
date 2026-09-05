'use client'

import { useState } from 'react'
import useSWR, { useSWRConfig } from 'swr'
import { useRefreshInterval } from '@/lib/hooks/useRefreshInterval'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar, formatPercent } from '@/lib/utils/format'
import { ScreenshotImportDialog, type ImportedHolding } from '@/components/shared/ScreenshotImportDialog'
import {
  getBatchQuoteRefreshInterval,
  quoteStatusColor,
  quoteStatusLabel,
  quoteTimeLabel,
} from '@/lib/quotes/realtime'

interface WatchlistStock {
  stock_id: string
  name: string
  industry?: string
  price: number | null
  change_pct: number | null
  source?: string
  is_realtime?: boolean
  freshness?: string
  market_state?: string
  timestamp?: string | null
  quote_date?: string | null
}

interface WatchlistDetail {
  id: string
  name: string
  stocks_count: number
  stocks: WatchlistStock[]
}

const WATCHLIST_ID = 'default'
const SWR_KEY = `/watchlists/${WATCHLIST_ID}`

export default function WatchlistPage() {
  const refreshInterval = useRefreshInterval()
  const { mutate } = useSWRConfig()
  const { data, isLoading, error } = useSWR<WatchlistDetail>(SWR_KEY, fetchAPI, {
    refreshInterval: (latest) => refreshInterval(getBatchQuoteRefreshInterval(latest?.stocks.length ?? 1)),
    dedupingInterval: 10_000,
    revalidateOnFocus: true,
  })
  const [addCode, setAddCode] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')
  const [importOpen, setImportOpen] = useState(false)

  const handleAdd = async () => {
    const code = addCode.trim().toUpperCase()
    if (!code) return
    setAdding(true)
    setAddError('')
    try {
      const currentStocks = data?.stocks.map(s => s.stock_id) ?? []
      if (currentStocks.includes(code)) {
        setAddError(`${code} 已在自選股清單中`)
        return
      }
      await fetchAPI(SWR_KEY, {
        method: 'PUT',
        body: JSON.stringify({ stocks: [...currentStocks, code] }),
      })
      await mutate(SWR_KEY)
      setAddCode('')
    } catch {
      setAddError(`新增 ${code} 失敗，請確認代號正確`)
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (stock_id: string) => {
    setAddError('')
    try {
      const currentStocks = data?.stocks.map(s => s.stock_id) ?? []
      const updated = currentStocks.filter(s => s !== stock_id)
      await fetchAPI(SWR_KEY, {
        method: 'PUT',
        body: JSON.stringify({ stocks: updated }),
      })
      await mutate(SWR_KEY)
    } catch {
      setAddError(`移除 ${stock_id} 失敗，請稍後再試`)
    }
  }

  const handleScreenshotImport = async (items: ImportedHolding[]) => {
    const codes = items.map((i) => i.stock_id).filter(Boolean)
    if (!codes.length) return
    setAddError('')
    try {
      const currentStocks = data?.stocks.map((s) => s.stock_id) ?? []
      const merged = Array.from(new Set([...currentStocks, ...codes]))
      await fetchAPI(SWR_KEY, {
        method: 'PUT',
        body: JSON.stringify({ stocks: merged }),
      })
      await mutate(SWR_KEY)
    } catch {
      setAddError('截圖自選股匯入失敗，請稍後再試')
    }
  }

  const stocks = data?.stocks ?? []

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>自選股</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>追蹤關注股票，盤中每 15 秒更新</p>
      </div>

      {error && data && (
        <p className="mb-4 text-sm" role="alert" style={{ color: 'var(--destructive)' }}>自選股更新失敗，目前顯示上次成功載入的快取。</p>
      )}

      {/* 新增輸入 */}
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={addCode}
            onChange={(e) => setAddCode(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder="輸入股票代號（例：2330）"
            className="flex-1 h-9 rounded-md border px-3 text-sm"
            style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
          />
          <button
            onClick={handleAdd}
            disabled={adding || !addCode.trim()}
            className="h-9 px-4 rounded-md text-sm font-medium disabled:opacity-60"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            {adding ? '新增中...' : '新增自選'}
          </button>
          <button
            onClick={() => setImportOpen(true)}
            className="h-9 px-4 rounded-md text-sm font-medium whitespace-nowrap"
            style={{ background: 'var(--secondary)', color: 'var(--foreground)', border: '1px solid var(--border)' }}
          >
            📷 截圖匯入
          </button>
        </div>
        {addError && (
          <p className="mt-2 text-xs" style={{ color: 'var(--destructive)' }}>{addError}</p>
        )}
      </div>

      {/* 自選股卡片 */}
      {error && !data ? (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p className="font-medium" style={{ color: 'var(--destructive)' }}>自選股載入失敗</p>
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            API 暫時無法回應，請稍後重試。
          </p>
          <button
            type="button"
            onClick={() => mutate(SWR_KEY)}
            className="mt-4 h-9 rounded-md px-4 text-sm font-medium"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            重新載入
          </button>
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-28 rounded-lg animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : stocks.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {stocks.map((item) => (
            <div
              key={item.stock_id}
              className="rounded-lg p-4 relative"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              {/* 移除按鈕 */}
              <button
                onClick={() => handleRemove(item.stock_id)}
                className="absolute top-3 right-3 text-xs opacity-50 hover:opacity-100 transition-opacity"
                style={{ color: 'var(--muted-foreground)' }}
              >
                x
              </button>

              {/* 代號名稱 */}
              <div className="mb-2">
                <span className="font-semibold" style={{ color: 'var(--foreground)' }}>{item.stock_id}</span>
                <span className="ml-2 text-sm" style={{ color: 'var(--muted-foreground)' }}>{item.name}</span>
              </div>

              {/* 價格 */}
              <div className="flex items-end gap-3 mb-2">
                <span className="text-2xl font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>
                  {item.price != null ? item.price.toFixed(2) : '—'}
                </span>
                {item.change_pct != null && (
                  <span
                    className="text-sm font-semibold tabular-nums"
                    style={{ color: getChangeColorVar(item.change_pct) }}
                  >
                    {formatPercent(item.change_pct, 2, true)}
                  </span>
                )}
              </div>

              {/* 行業 */}
              {item.industry && (
                <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {item.industry}
                </div>
              )}
              {item.source && (
                <div className="text-[11px] mt-1" style={{ color: quoteStatusColor(item) }}>
                  {quoteStatusLabel(item)} · {quoteTimeLabel({ timestamp: item.timestamp, date: item.quote_date })}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p className="text-lg mb-2" style={{ color: 'var(--muted-foreground)' }}>自選股清單為空</p>
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            在上方輸入股票代號，新增到自選股追蹤
          </p>
        </div>
      )}

      <ScreenshotImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        mode="codes"
        title="📷 截圖匯入自選股"
        confirmLabel="加入自選"
        onConfirm={handleScreenshotImport}
      />
    </div>
  )
}
