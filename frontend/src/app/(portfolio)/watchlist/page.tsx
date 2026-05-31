'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar, formatPercent } from '@/lib/utils/format'

interface WatchlistStock {
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
const SWR_KEY = `/watchlists/${WATCHLIST_ID}`

export default function WatchlistPage() {
  const { data, isLoading, error } = useSWR<WatchlistDetail>(SWR_KEY, fetchAPI)
  const [addCode, setAddCode] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')

  const ensureWatchlistExists = async () => {
    try {
      await fetchAPI(SWR_KEY)
    } catch {
      await fetchAPI('/watchlists', {
        method: 'POST',
        body: JSON.stringify({ name: WATCHLIST_ID, stocks: [] }),
      })
    }
  }

  const handleAdd = async () => {
    const code = addCode.trim().toUpperCase()
    if (!code) return
    setAdding(true)
    setAddError('')
    try {
      await ensureWatchlistExists()
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
    const currentStocks = data?.stocks.map(s => s.stock_id) ?? []
    const updated = currentStocks.filter(s => s !== stock_id)
    await fetchAPI(SWR_KEY, {
      method: 'PUT',
      body: JSON.stringify({ stocks: updated }),
    })
    await mutate(SWR_KEY)
  }

  const stocks = data?.stocks ?? []

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>自選股</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>追蹤關注的股票報價</p>
      </div>

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
          <p className="text-lg mb-2" style={{ color: 'var(--muted-foreground)' }}>自選股清單為空</p>
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            在上方輸入股票代號，新增到自選股追蹤
          </p>
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
    </div>
  )
}
